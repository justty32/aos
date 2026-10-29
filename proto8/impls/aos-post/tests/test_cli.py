#!/usr/bin/env python3
"""test_cli.py：aos-post 命令列的測試（ctest 會跑）。只用標準庫（unittest）。

    python3 tests/test_cli.py bin/aos-post

A 段：命令列與信箱的錯；B 段：寄（信號、letter.json 信封、sender）；C 段：認領（claim、claim-all、tmp/ 不碰）；
D 段：並發（20 個寄信人 200 封、一個處理者不漏不重）；E 段：撤回；F 段：check（好信、壞信）；
G 段：finish（刪、--keep、壞信丟掉）；H 段：finish --reply（回信落在 reply_to、in_reply_to 對）；
I 段：send --ordered（50 個寄信人序號連續、持有者死了收屍繼續、亂 kill -9 不重號、order.json 壞）。
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

BIN = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else
                      os.path.join(os.path.dirname(__file__), "..", "bin", "aos-post"))

ID = re.compile(r"^\d{20}\.\d+\.-?\d+$")
AT = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}\+00:00$")


class Case(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.t = Path(self.td.name)
        self.mb = self.t / "mb"
        self.home = self.t / "home"
        self.home.mkdir()

    def tearDown(self):
        self.td.cleanup()

    def env(self, extra=None):
        e = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        e["HOME"] = str(self.home)
        e.update(extra or {})
        return e

    def run_p(self, *args, stdin="", extra=None):
        return subprocess.run([BIN, *[str(a) for a in args]], input=stdin, env=self.env(extra), cwd=self.t,
                              capture_output=True, text=True, timeout=60)

    def ok(self, *args, stdin="", extra=None):
        r = self.run_p(*args, stdin=stdin, extra=extra)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, "")
        return r.stdout

    def own_error(self, r, code):
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)
        self.assertTrue(r.stderr.startswith("aos-post: %s " % code), r.stderr)

    def init(self, mb=None):
        self.ok("init", mb or self.mb)

    def send(self, body=None, mb=None, flags=(), extra=None):
        out = self.ok("send", *flags, mb or self.mb, stdin=json.dumps({} if body is None else body), extra=extra)
        return out.strip()

    def ls(self, part, mb=None):
        return sorted(os.listdir((mb or self.mb) / part))

    def letter(self, part, id, mb=None):
        return json.loads(((mb or self.mb) / part / id / "letter.json").read_text())

    # ---------- A：命令列與信箱的錯 ----------
    def test_a1_no_args(self):
        self.own_error(self.run_p(), "ArgumentsBad")

    def test_a2_unknown_command(self):
        self.own_error(self.run_p("post", self.mb), "CommandUnknown")

    def test_a3_mailbox_missing(self):
        self.own_error(self.run_p("send", self.mb, stdin="{}"), "MailboxMissing")
        self.own_error(self.run_p("claim", self.mb), "MailboxMissing")

    def test_a4_mailbox_half_built(self):
        (self.mb / "tmp").mkdir(parents=True)
        (self.mb / "new").mkdir()
        self.own_error(self.run_p("claim-all", self.mb), "MailboxMissing")   # 少 cur/

    def test_a5_positional_count_and_id(self):
        self.init()
        self.own_error(self.run_p("claim"), "ArgumentsBad")
        self.own_error(self.run_p("check", self.mb), "ArgumentsBad")
        self.own_error(self.run_p("finish", self.mb, "a/b"), "ArgumentsBad")
        self.own_error(self.run_p("withdraw", self.mb, ".x"), "ArgumentsBad")
        self.own_error(self.run_p("send", self.mb, "--reply-to", "x", stdin="{}"), "ArgumentsBad")   # 旗標要在位置參數前

    def test_a6_flags(self):
        self.init()
        self.own_error(self.run_p("send", "--nope", "1", self.mb, stdin="{}"), "FlagUnknown")
        self.own_error(self.run_p("finish", "--keep=1", self.mb, "x"), "ArgumentsBad")

    def test_a7_body_bad(self):
        self.init()
        self.own_error(self.run_p("send", self.mb, stdin="{nope"), "InputBad")
        self.own_error(self.run_p("send", self.mb, stdin="1 2"), "InputExtra")
        self.assertEqual(self.ls("new"), [])
        self.assertEqual(self.ls("tmp"), [])

    # ---------- B：寄 ----------
    def test_b1_init_idempotent(self):
        self.init(self.t / "a" / "b")
        self.init(self.t / "a" / "b")
        self.assertEqual(sorted(os.listdir(self.t / "a" / "b")), ["cur", "new", "tmp"])

    def test_b2_letter(self):
        self.init()
        ws = self.t / "ws"
        id = self.send({"x": [1, 2]}, flags=("--reply-to", "rb", "--in-reply-to", "000.1.2"),
                       extra={"AOS_WS": str(ws)})
        self.assertRegex(id, ID)
        self.assertEqual(self.ls("new"), [id])
        self.assertEqual(self.ls("tmp"), [])
        self.assertEqual(os.listdir(self.mb / "new" / id), ["letter.json"])
        doc = self.letter("new", id)
        self.assertEqual(list(doc), ["kind", "sender", "sent_at", "reply_to", "in_reply_to", "body"])
        self.assertEqual(doc["kind"], "letter")
        self.assertEqual(doc["sender"], str(ws))
        self.assertRegex(doc["sent_at"], AT)
        self.assertEqual(doc["reply_to"], str(self.t / "rb"))   # 相對路徑從 cwd 轉絕對
        self.assertEqual(doc["in_reply_to"], "000.1.2")
        self.assertEqual(doc["body"], {"x": [1, 2]})
        # 信號的奈秒跟 sent_at 是同一刻
        ms = int(id.split(".")[0]) // 1000000
        self.assertEqual(doc["sent_at"][20:23], "%03d" % (ms % 1000))

    def test_b3_sender_home(self):
        self.init()
        id = self.send()
        self.assertEqual(self.letter("new", id)["sender"], str(self.home))
        id = self.send(extra={"AOS_WS": ""})   # 空的＝沒設
        self.assertEqual(self.letter("new", id)["sender"], str(self.home))

    def test_b4_empty_stdin_and_scalar_body(self):
        self.init()
        id = self.ok("send", self.mb, stdin="").strip()
        self.assertEqual(self.letter("new", id)["body"], {})
        id = self.send("hi")
        self.assertEqual(self.letter("new", id)["body"], "hi")
        self.assertNotIn("reply_to", self.letter("new", id))

    # ---------- C：認領 ----------
    def test_c1_claim_one(self):
        self.init()
        r = self.run_p("claim", self.mb)
        self.assertEqual((r.returncode, r.stdout, r.stderr), (10, "", ""))
        a = self.send({"n": 1})
        b = self.send({"n": 2})
        self.assertEqual(self.ok("claim", self.mb).strip(), min(a, b))
        self.assertEqual(self.ls("new"), [max(a, b)])
        self.assertEqual(self.ls("cur"), [min(a, b)])

    def test_c2_claim_all_sorted(self):
        self.init()
        ids = [self.send({"n": i}) for i in range(5)]
        self.assertEqual(self.ok("claim-all", self.mb).split(), sorted(ids))
        self.assertEqual(self.ls("new"), [])
        self.assertEqual(self.ls("cur"), sorted(ids))
        self.assertEqual(self.run_p("claim-all", self.mb).returncode, 10)

    def test_c3_tmp_never_claimed(self):
        self.init()
        half = self.mb / "tmp" / "00000000000000000001.1.1"
        half.mkdir()
        (half / "letter.json").write_text('{"kind": "let')
        self.assertEqual(self.run_p("claim-all", self.mb).returncode, 10)
        a = self.send()
        self.assertEqual(self.ok("claim-all", self.mb).split(), [a])
        self.assertEqual(self.run_p("claim", self.mb).returncode, 10)
        self.assertTrue(half.exists())
        self.assertEqual(self.ls("tmp"), [half.name])

    def test_c4_dot_names_skipped(self):
        self.init()
        (self.mb / "new" / ".x").mkdir()
        self.assertEqual(self.run_p("claim-all", self.mb).returncode, 10)
        self.assertEqual(self.ls("new"), [".x"])

    # ---------- D：並發 ----------
    def test_d1_twenty_senders_one_taker(self):
        self.init()
        sent, got = [], []
        lock = threading.Lock()

        def sender(k):
            for i in range(10):
                id = self.send({"k": k, "i": i})
                with lock:
                    sent.append(id)

        stop = threading.Event()

        def taker():
            while True:
                last = stop.is_set()
                r = self.run_p("claim-all", self.mb)
                self.assertIn(r.returncode, (0, 10), r.stderr)
                got.extend(r.stdout.split())
                if last:
                    return

        ts = [threading.Thread(target=sender, args=(k,)) for k in range(20)]
        tk = threading.Thread(target=taker)
        tk.start()
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        stop.set()
        tk.join()
        self.assertEqual(len(sent), 200)
        self.assertEqual(len(got), 200, "有漏或有重")
        self.assertEqual(sorted(got), sorted(sent))
        self.assertEqual(self.ls("new"), [])
        self.assertEqual(self.ls("tmp"), [])
        self.assertEqual(self.ls("cur"), sorted(sent))
        bodies = sorted((d["body"]["k"], d["body"]["i"]) for d in (self.letter("cur", id) for id in sent))
        self.assertEqual(bodies, [(k, i) for k in range(20) for i in range(10)])

    # ---------- E：撤回 ----------
    def test_e1_withdraw_new(self):
        self.init()
        a = self.send()
        b = self.send()
        self.assertEqual(self.ok("withdraw", self.mb, a), "")
        self.assertEqual(self.ls("new"), [b])
        self.assertEqual(self.ls("tmp"), [])

    def test_e2_withdraw_claimed_fails(self):
        self.init()
        a = self.send()
        self.ok("claim", self.mb)
        self.own_error(self.run_p("withdraw", self.mb, a), "WithdrawFailed")
        self.assertEqual(self.ls("cur"), [a])
        self.own_error(self.run_p("withdraw", self.mb, "nope"), "WithdrawFailed")

    # ---------- F：check ----------
    def test_f1_check_good(self):
        self.init()
        a = self.send({"q": 1})
        self.ok("claim", self.mb)
        out = self.ok("check", self.mb, a)
        self.assertEqual(len(out.splitlines()), 1)
        self.assertEqual(json.loads(out), self.letter("cur", a))

    def test_f2_check_bad(self):
        self.init()
        bad = {
            "notjson": "{nope",
            "array": "[]",
            "kind": json.dumps({"kind": "x", "sender": "/", "sent_at": "t", "body": 1}),
            "nobody": json.dumps({"kind": "letter", "sender": "/", "sent_at": "t"}),
            "nosender": json.dumps({"kind": "letter", "sent_at": "t", "body": 1}),
            "replyto": json.dumps({"kind": "letter", "sender": "/", "sent_at": "t", "body": 1, "reply_to": 3}),
        }
        for name, text in bad.items():
            d = self.mb / "cur" / name
            d.mkdir()
            (d / "letter.json").write_text(text)
            self.own_error(self.run_p("check", self.mb, name), "LetterBad")
        (self.mb / "cur" / "empty").mkdir()
        self.own_error(self.run_p("check", self.mb, "empty"), "LetterBad")

    def test_f3_check_missing(self):
        self.init()
        a = self.send()
        self.own_error(self.run_p("check", self.mb, a), "LetterMissing")   # 還在 new/，不算

    # ---------- G：finish ----------
    def test_g1_finish_deletes(self):
        self.init()
        a = self.send()
        self.ok("claim", self.mb)
        self.assertEqual(self.ok("finish", self.mb, a), "")
        self.assertEqual(self.ls("cur"), [])
        self.assertEqual(self.ls("tmp"), [])
        self.assertFalse((self.mb / "done").exists())
        self.own_error(self.run_p("finish", self.mb, a), "LetterMissing")

    def test_g2_finish_keep(self):
        self.init()
        a = self.send({"z": 1})
        self.ok("claim", self.mb)
        self.ok("finish", "--keep", self.mb, a)
        self.assertEqual(self.ls("done"), [a])
        self.assertEqual(self.letter("done", a)["body"], {"z": 1})
        self.assertEqual(self.ls("cur"), [])

    def test_g3_bad_letter_dropped(self):
        self.init()
        for name in ("bad1", "bad2"):
            d = self.mb / "new" / name
            d.mkdir()
            (d / "letter.json").write_text("{nope")
        (self.mb / "new" / "file").write_text("x")   # 不是資料夾的也認領得到、丟得掉
        self.assertEqual(self.ok("claim-all", self.mb).split(), ["bad1", "bad2", "file"])
        self.ok("finish", self.mb, "bad1")
        self.ok("finish", "--keep", self.mb, "bad2")   # 壞信不管 --keep，一律丟掉
        self.ok("finish", "--keep", self.mb, "file")
        self.assertEqual(self.ls("cur"), [])
        self.assertEqual(self.ls("tmp"), [])
        self.assertFalse((self.mb / "done").exists())

    # ---------- H：finish --reply ----------
    def test_h1_reply(self):
        self.init()
        rb = self.t / "rb"
        self.init(rb)
        a = self.send({"ask": 1}, flags=("--reply-to", rb), extra={"AOS_WS": str(self.t / "asker")})
        self.ok("claim", self.mb)
        out = self.ok("finish", "--reply", self.mb, a, stdin=json.dumps({"answer": 2}),
                      extra={"AOS_WS": str(self.t / "taker")})
        rid = out.strip()
        self.assertRegex(rid, ID)
        self.assertEqual(self.ls("new", rb), [rid])
        doc = self.letter("new", rid, rb)
        self.assertEqual(doc["in_reply_to"], a)
        self.assertEqual(doc["body"], {"answer": 2})
        self.assertEqual(doc["sender"], str(self.t / "taker"))
        self.assertNotIn("reply_to", doc)
        self.assertEqual(self.ls("cur"), [])

    def test_h2_no_reply_to(self):
        self.init()
        a = self.send()
        self.ok("claim", self.mb)
        self.assertEqual(self.ok("finish", "--reply", "--keep", self.mb, a, stdin="{}"), "")
        self.assertEqual(self.ls("done"), [a])

    def test_h3_reply_box_missing_keeps_letter(self):
        self.init()
        a = self.send(flags=("--reply-to", self.t / "nobox"))
        self.ok("claim", self.mb)
        self.own_error(self.run_p("finish", "--reply", self.mb, a, stdin="{}"), "MailboxMissing")
        self.assertEqual(self.ls("cur"), [a])   # 回信寄不出去，信留在 cur/，可以再 finish 一次
        self.ok("finish", self.mb, a)
        self.assertEqual(self.ls("cur"), [])

    # ---------- I：有順序的投遞（send --ordered） ----------
    def seqs(self):
        names = self.ls("new")
        for n in names:
            self.assertRegex(n, r"^\d{12}\.\d{20}\.\d+\.-?\d+$")
        return [int(n.split(".")[0]) for n in names]

    def counter(self):
        return json.loads((self.mb / "order.json").read_text())["counter_letters"]

    def hold_order_lock(self):
        """手寫一把 order.lock/：持有者是一個活著的 sleep。回它的 Popen。"""
        p = subprocess.Popen(["sleep", "60"])
        stat = Path("/proc/%d/stat" % p.pid).read_text()
        d = self.mb / "order.lock"
        d.mkdir()
        (d / "holder.json").write_text(json.dumps({
            "holder": "/x", "pid": p.pid, "started_at_ticks": int(stat[stat.rfind(")") + 1:].split()[19]),
            "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
            "acquired_at": "2026-10-29T00:00:00.000+00:00"}))
        return p

    def ordered_senders(self, n):
        return [subprocess.Popen([BIN, "send", "--ordered", str(self.mb)], stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.env(), text=True)
                for _ in range(n)]

    def test_i1_ordered_basic(self):
        self.init()
        names = [self.send({"i": i}, flags=("--ordered",)) for i in range(3)]
        self.assertEqual([n.split(".")[0] for n in names], ["000000000001", "000000000002", "000000000003"])
        self.assertEqual(self.ls("new"), names)
        self.assertEqual(self.counter(), 3)
        self.assertEqual(sorted(os.listdir(self.mb)), ["cur", "new", "order.json", "tmp"])   # 鎖放掉了
        self.assertEqual(self.letter("new", names[1])["body"], {"i": 1})
        self.assertEqual(self.ok("claim-all", self.mb).split(), names)
        self.ok("check", self.mb, names[0])

    def test_i2_fifty_concurrent(self):
        self.init()
        ps = self.ordered_senders(50)
        outs = [p.communicate(timeout=60) for p in ps]
        for p, (out, err) in zip(ps, outs):
            self.assertEqual((p.returncode, err), (0, ""))
        self.assertEqual(sorted(o.strip() for o, _ in outs), self.ls("new"))
        self.assertEqual(self.seqs(), list(range(1, 51)))   # 從 1 連續無缺、不重
        self.assertEqual(self.counter(), 50)
        self.assertEqual(self.ls("tmp"), [])
        self.assertFalse((self.mb / "order.lock").exists())

    def test_i3_dead_holder_reaped_gap(self):
        self.init()
        (self.mb / "order.json").write_text('{"counter_letters": 1}')   # 持有者取了 1 號、還沒投進去就死了
        holder = self.hold_order_lock()
        ps = self.ordered_senders(20)
        time.sleep(0.5)
        self.assertTrue(all(p.poll() is None for p in ps), "持有者活著時應該都在等")
        self.assertEqual(self.ls("new"), [])
        holder.kill()
        holder.wait()
        for p in ps:
            out, err = p.communicate(timeout=60)
            self.assertEqual((p.returncode, err), (0, ""))
        self.assertEqual(self.seqs(), list(range(2, 22)))   # 1 號缺了（照實：可以缺號、不會重號）
        self.assertEqual(self.counter(), 21)

    def test_i4_kill9_senders_midway(self):
        self.init()
        ps = self.ordered_senders(50)
        killed = ps[::5]
        for p in killed:
            p.kill()   # 有的拿著鎖、有的還沒拿、有的已經寄完
        for p in ps:
            p.communicate(timeout=60)
        survivors = [p for p in ps if p not in killed]
        self.assertTrue(all(p.returncode == 0 for p in survivors))
        seqs = self.seqs()
        self.assertEqual(len(seqs), len(set(seqs)), "序號重複")
        self.assertGreaterEqual(len(seqs), len(survivors))
        self.assertGreaterEqual(self.counter(), max(seqs))   # 缺號只會在計數以內
        # 鎖沒卡住：再寄一封拿得到下一個號
        nxt = self.send(flags=("--ordered",))
        self.assertEqual(int(nxt.split(".")[0]), self.counter())
        self.assertGreater(self.counter(), max(seqs))

    def test_i5_order_bad(self):
        self.init()
        (self.mb / "order.json").write_text('{"counter_letters": -1}')
        self.own_error(self.run_p("send", "--ordered", self.mb, stdin="{}"), "OrderBad")
        self.assertEqual(self.ls("new"), [])
        self.assertEqual(self.ls("tmp"), [])
        self.assertFalse((self.mb / "order.lock").exists())   # 出錯也放鎖


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0], "-v"])
