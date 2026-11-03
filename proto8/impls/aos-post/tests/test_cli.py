#!/usr/bin/env python3
"""test_cli.py：aos-post 命令列的測試（ctest 會跑）。只用標準庫（unittest）。

    python3 tests/test_cli.py bin/aos-post

A 段：命令列與信箱的錯（各子命令只驗自己用到的格）；B 段：寄（信件名稱、letter.json 信封、sender 四級順序）；
C 段：認領（take、take-all、tmp/ 不碰、cur/ 沒有就建）；D 段：並發（20 個寄信人 200 封、一個處理者不漏不重）；
E 段：撤回（regret）；F 段：see（好信、壞信、kind 有也忽略）；G 段：done（刪、--keep 進 archive/、壞信丟掉）；
H 段：done --reply（回信落在 reply_to、in_reply_to 對）；I 段：send --ordered（50 個寄信人序號連續、持有者死了收屍繼續、
亂 kill -9 不重號、order.json 壞）；J 段：自己給信件名稱（合法、不像有序名、撞名 LetterExists）；
K 段：有序無序同箱（有序先、缺號直接下一號、無序照時間／照名字）；L 段：see／done 不給信件名稱；
M 段：send 的可寫檢查（MailboxBad）與 reply_to 的驗法。
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
        self.own_error(self.run_p("take", self.mb), "MailboxMissing")
        self.own_error(self.run_p("see", self.mb), "MailboxMissing")
        (self.t / "file").write_text("x")
        self.own_error(self.run_p("take", self.t / "file"), "MailboxMissing")   # 信箱要是資料夾

    def test_a4_mailbox_half_built(self):
        """各子命令只驗自己用到的格。"""
        self.mb.mkdir()
        self.own_error(self.run_p("send", self.mb, stdin="{}"), "MailboxMissing")   # 少 tmp/、new/
        (self.mb / "tmp").mkdir()
        self.own_error(self.run_p("send", self.mb, stdin="{}"), "MailboxMissing")   # 少 new/
        self.own_error(self.run_p("take", self.mb), "MailboxMissing")
        self.own_error(self.run_p("regret", self.mb, "x"), "MailboxMissing")
        self.own_error(self.run_p("see", self.mb, "x"), "MailboxMissing")           # 少 cur/
        self.own_error(self.run_p("done", self.mb, "x"), "MailboxMissing")
        (self.mb / "new").mkdir()
        a = self.send()                                                             # send 不看 cur/
        self.assertEqual(self.ls("new"), [a])
        self.assertFalse((self.mb / "cur").exists())
        (self.mb / "cur").mkdir()
        (self.mb / "tmp").rmdir()
        self.own_error(self.run_p("done", self.mb, a), "MailboxMissing")            # done 要 tmp/
        self.own_error(self.run_p("regret", self.mb, a), "MailboxMissing")          # regret 要 tmp/

    def test_a5_positional_count_and_id(self):
        self.init()
        self.own_error(self.run_p("take"), "ArgumentsBad")
        self.own_error(self.run_p("take", self.mb, "x"), "ArgumentsBad")
        self.own_error(self.run_p("see", self.mb, "x", "y"), "ArgumentsBad")
        self.own_error(self.run_p("see", self.mb, ""), "ArgumentsBad")
        self.own_error(self.run_p("done", self.mb, "a/b"), "ArgumentsBad")
        self.own_error(self.run_p("regret", self.mb, ".x"), "ArgumentsBad")
        self.own_error(self.run_p("regret", self.mb), "ArgumentsBad")              # 撤回要給名字
        self.own_error(self.run_p("send", self.mb, "--reply-to", "x", stdin="{}"), "ArgumentsBad")   # 旗標要在位置參數前
        self.own_error(self.run_p("send", "--in-reply-to", "a/b", self.mb, stdin="{}"), "ArgumentsBad")
        for old in ("claim", "claim-all", "check", "finish", "withdraw"):            # 舊名不留
            self.own_error(self.run_p(old, self.mb), "CommandUnknown")
        self.assertEqual(self.ls("new"), [])

    def test_a6_flags(self):
        self.init()
        self.own_error(self.run_p("send", "--nope", "1", self.mb, stdin="{}"), "FlagUnknown")
        self.own_error(self.run_p("done", "--keep=1", self.mb, "x"), "ArgumentsBad")

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
        self.init(self.t / "rb")
        ws = self.t / "ws"
        id = self.send({"x": [1, 2]}, flags=("--reply-to", "rb", "--in-reply-to", "000.1.2"),
                       extra={"AOS_WS": str(ws)})
        self.assertRegex(id, ID)
        self.assertEqual(self.ls("new"), [id])
        self.assertEqual(self.ls("tmp"), [])
        self.assertEqual(os.listdir(self.mb / "new" / id), ["letter.json"])
        doc = self.letter("new", id)
        self.assertEqual(list(doc), ["sender", "sent_at", "reply_to", "in_reply_to", "body"])   # 沒有 kind（11-03）
        self.assertEqual(doc["sender"], str(ws))
        self.assertRegex(doc["sent_at"], AT)
        self.assertEqual(doc["reply_to"], str(self.t / "rb"))   # 相對路徑從 cwd 轉絕對
        self.assertEqual(doc["in_reply_to"], "000.1.2")
        self.assertEqual(doc["body"], {"x": [1, 2]})
        # 預設信件名稱的奈秒跟 sent_at 是同一刻
        ms = int(id.split(".")[0]) // 1000000
        self.assertEqual(doc["sent_at"][20:23], "%03d" % (ms % 1000))

    def test_b3_sender_order(self):
        """sender＝AOS_WS ＞ AOS_STACK ＞ AOS_CF ＞ cwd；空字串算沒設；轉絕對路徑；HOME 不看。"""
        self.init()
        cwd = os.path.realpath(self.t)
        for extra, want in (({}, cwd),
                            ({"AOS_CF": "cf"}, os.path.join(cwd, "cf")),
                            ({"AOS_CF": "/cf", "AOS_STACK": "/st/./x/.."}, "/st"),
                            ({"AOS_CF": "/cf", "AOS_STACK": "/st", "AOS_WS": "/ws"}, "/ws"),
                            ({"AOS_CF": "/cf", "AOS_STACK": "", "AOS_WS": ""}, "/cf")):
            id = self.send(extra=extra)
            self.assertEqual(self.letter("new", id)["sender"], want, extra)

    def test_b4_empty_stdin_and_scalar_body(self):
        self.init()
        id = self.ok("send", self.mb, stdin="").strip()
        self.assertEqual(self.letter("new", id)["body"], {})
        id = self.send("hi")
        self.assertEqual(self.letter("new", id)["body"], "hi")
        self.assertNotIn("reply_to", self.letter("new", id))

    # ---------- C：認領 ----------
    def test_c1_take_one(self):
        self.init()
        r = self.run_p("take", self.mb)
        self.assertEqual((r.returncode, r.stdout, r.stderr), (10, "", ""))
        a = self.send({"n": 1})
        b = self.send({"n": 2})
        self.assertEqual(self.ok("take", self.mb).strip(), min(a, b))
        self.assertEqual(self.ls("new"), [max(a, b)])
        self.assertEqual(self.ls("cur"), [min(a, b)])

    def test_c2_take_all_sorted(self):
        self.init()
        ids = [self.send({"n": i}) for i in range(5)]
        self.assertEqual(self.ok("take-all", self.mb).split(), sorted(ids))
        self.assertEqual(self.ls("new"), [])
        self.assertEqual(self.ls("cur"), sorted(ids))
        self.assertEqual(self.run_p("take-all", self.mb).returncode, 10)

    def test_c3_tmp_never_taken(self):
        self.init()
        half = self.mb / "tmp" / "00000000000000000001.1.1"
        half.mkdir()
        (half / "letter.json").write_text('{"sende')
        self.assertEqual(self.run_p("take-all", self.mb).returncode, 10)
        a = self.send()
        self.assertEqual(self.ok("take-all", self.mb).split(), [a])
        self.assertEqual(self.run_p("take", self.mb).returncode, 10)
        self.assertTrue(half.exists())
        self.assertEqual(self.ls("tmp"), [half.name])

    def test_c4_dot_names_skipped(self):
        self.init()
        (self.mb / "new" / ".x").mkdir()
        self.assertEqual(self.run_p("take-all", self.mb).returncode, 10)
        self.assertEqual(self.ls("new"), [".x"])

    def test_c5_take_makes_cur(self):
        """cur/ 沒有：take／take-all 自己建。"""
        for cmd in ("take", "take-all"):
            mb = self.t / cmd
            (mb / "tmp").mkdir(parents=True)
            (mb / "new").mkdir()
            a = self.send(mb=mb)
            self.assertEqual(self.ok(cmd, mb).split(), [a])
            self.assertEqual(self.ls("cur", mb), [a])
            (mb / "cur" / a / "letter.json").unlink()
            (mb / "cur" / a).rmdir()
            (mb / "cur").rmdir()
            self.assertEqual(self.run_p(cmd, mb).returncode, 10)   # 沒信也建
            self.assertTrue((mb / "cur").is_dir())

    def test_c6_take_skips_same_name_in_cur(self):
        """cur/ 已有同名的（還在處理）：跳過、那封留在 new/。"""
        self.init()
        self.ok("send", self.mb, "same", stdin="{}")
        self.ok("take", self.mb)
        self.ok("send", self.mb, "same", stdin="{}")   # cur/ 有同名的，send 不擋
        b = self.send()
        self.assertEqual(self.ok("take", self.mb).strip(), b)
        self.assertEqual(self.ls("new"), ["same"])
        self.assertEqual(self.run_p("take", self.mb).returncode, 10)

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
                r = self.run_p("take-all", self.mb)
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
    def test_e1_regret_new(self):
        self.init()
        a = self.send()
        b = self.send()
        self.assertEqual(self.ok("regret", self.mb, a), "")
        self.assertEqual(self.ls("new"), [b])
        self.assertEqual(self.ls("tmp"), [])

    def test_e2_regret_taken_fails(self):
        self.init()
        a = self.send()
        self.ok("take", self.mb)
        self.own_error(self.run_p("regret", self.mb, a), "RegretFailed")
        self.assertEqual(self.ls("cur"), [a])
        self.own_error(self.run_p("regret", self.mb, "nope"), "RegretFailed")
        o = self.send(flags=("--ordered",))
        self.ok("regret", self.mb, o)   # 有序名在命令列其他地方合法
        self.assertEqual(self.ls("new"), [])

    # ---------- F：see ----------
    def test_f1_see_good(self):
        self.init()
        a = self.send({"q": 1})
        self.ok("take", self.mb)
        out = self.ok("see", self.mb, a)
        self.assertEqual(len(out.splitlines()), 1)
        self.assertEqual(json.loads(out), self.letter("cur", a))

    def test_f2_see_bad(self):
        self.init()
        bad = {
            "notjson": "{nope",
            "array": "[]",
            "nobody": json.dumps({"sender": "/", "sent_at": "t"}),
            "nosender": json.dumps({"sent_at": "t", "body": 1}),
            "sentat": json.dumps({"sender": "/", "sent_at": 1, "body": 1}),
            "replyto": json.dumps({"sender": "/", "sent_at": "t", "body": 1, "reply_to": 3}),
            "inreplyto": json.dumps({"sender": "/", "sent_at": "t", "body": 1, "in_reply_to": None}),
        }
        for name, text in bad.items():
            d = self.mb / "cur" / name
            d.mkdir()
            (d / "letter.json").write_text(text)
            self.own_error(self.run_p("see", self.mb, name), "LetterBad")
        (self.mb / "cur" / "empty").mkdir()
        self.own_error(self.run_p("see", self.mb, "empty"), "LetterBad")

    def test_f3_see_missing(self):
        self.init()
        a = self.send()
        self.own_error(self.run_p("see", self.mb, a), "LetterMissing")   # 還在 new/，不算

    def test_f4_kind_ignored(self):
        """kind 拿掉了：有也只是不認得的 key，忽略（寫什麼都一樣是好信）；名字無序也不算壞信。"""
        self.init()
        for name, kind in (("old", "letter"), ("odd", "x")):
            d = self.mb / "cur" / name
            d.mkdir()
            doc = {"kind": kind, "sender": "/", "sent_at": "t", "body": 1}
            (d / "letter.json").write_text(json.dumps(doc))
            self.assertEqual(json.loads(self.ok("see", self.mb, name)), doc)

    # ---------- G：done ----------
    def test_g1_done_deletes(self):
        self.init()
        a = self.send()
        self.ok("take", self.mb)
        self.assertEqual(self.ok("done", self.mb, a), "")
        self.assertEqual(self.ls("cur"), [])
        self.assertEqual(self.ls("tmp"), [])
        self.assertFalse((self.mb / "archive").exists())
        self.own_error(self.run_p("done", self.mb, a), "LetterMissing")

    def test_g2_done_keep(self):
        self.init()
        a = self.send({"z": 1})
        self.ok("take", self.mb)
        self.ok("done", "--keep", self.mb, a)   # archive/ 沒有就建
        self.assertEqual(self.ls("archive"), [a])
        self.assertEqual(self.letter("archive", a)["body"], {"z": 1})
        self.assertEqual(self.ls("cur"), [])
        self.assertFalse((self.mb / "done").exists())

    def test_g3_bad_letter_dropped(self):
        self.init()
        for name in ("bad1", "bad2"):
            d = self.mb / "new" / name
            d.mkdir()
            (d / "letter.json").write_text("{nope")
        (self.mb / "new" / "file").write_text("x")   # 不是資料夾的也認領得到、丟得掉
        self.assertEqual(self.ok("take-all", self.mb).split(), ["bad1", "bad2", "file"])
        self.ok("done", self.mb, "bad1")
        self.ok("done", "--keep", self.mb, "bad2")   # 壞信不管 --keep，一律丟掉
        self.ok("done", "--keep", self.mb, "file")
        self.assertEqual(self.ls("cur"), [])
        self.assertEqual(self.ls("tmp"), [])
        self.assertFalse((self.mb / "archive").exists())

    # ---------- H：done --reply ----------
    def test_h1_reply(self):
        self.init()
        rb = self.t / "rb"
        self.init(rb)
        a = self.send({"ask": 1}, flags=("--reply-to", rb), extra={"AOS_WS": str(self.t / "asker")})
        self.ok("take", self.mb)
        out = self.ok("done", "--reply", self.mb, a, stdin=json.dumps({"answer": 2}),
                      extra={"AOS_WS": str(self.t / "taker")})
        rid = out.strip()
        self.assertRegex(rid, ID)
        self.assertEqual(self.ls("new", rb), [rid])
        doc = self.letter("new", rid, rb)
        self.assertEqual(doc["in_reply_to"], a)
        self.assertEqual(doc["body"], {"answer": 2})
        self.assertEqual(doc["sender"], str(self.t / "taker"))
        self.assertNotIn("reply_to", doc)
        self.assertNotIn("kind", doc)
        self.assertEqual(self.ls("cur"), [])

    def test_h2_no_reply_to(self):
        self.init()
        a = self.send()
        self.ok("take", self.mb)
        self.assertEqual(self.ok("done", "--reply", "--keep", self.mb, a, stdin="{}"), "")
        self.assertEqual(self.ls("archive"), [a])

    def test_h3_reply_box_gone_keeps_letter(self):
        self.init()
        rb = self.t / "rb"
        self.init(rb)
        a = self.send(flags=("--reply-to", rb))
        (rb / "new").rmdir()   # 寄的時候還好好的，回信時壞了
        self.ok("take", self.mb)
        self.own_error(self.run_p("done", "--reply", self.mb, a, stdin="{}"), "MailboxMissing")
        self.assertEqual(self.ls("cur"), [a])   # 回信寄不出去，信留在 cur/，可以再 done 一次
        self.ok("done", self.mb, a)
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
        self.assertEqual(self.ok("take-all", self.mb).split(), names)
        self.ok("see", self.mb, names[0])

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

    # ---------- J：自己給信件名稱 ----------
    def test_j1_own_name(self):
        self.init()
        self.assertEqual(self.ok("send", self.mb, "hello.1", stdin='{"a": 1}').strip(), "hello.1")
        self.assertEqual(self.ls("new"), ["hello.1"])
        doc = self.letter("new", "hello.1")
        self.assertEqual(list(doc), ["sender", "sent_at", "body"])
        self.assertRegex(doc["sent_at"], AT)
        o = self.ok("send", "--ordered", self.mb, "hi", stdin="{}").strip()   # --ordered＋自己給的＝<序號>.<名>
        self.assertEqual(o, "000000000001.hi")
        self.assertEqual(self.ls("new"), [o, "hello.1"])
        self.assertEqual(self.ls("tmp"), [])

    def test_j2_own_name_bad(self):
        self.init()
        for name in ("", "a/b", ".x", "000000000001.x", "123456789012."):
            self.own_error(self.run_p("send", self.mb, name, stdin="{}"), "ArgumentsBad")
            self.own_error(self.run_p("send", "--ordered", self.mb, name, stdin="{}"), "ArgumentsBad")
        for name in ("00000000001.x", "000000000001", "0000000000012.x", "x000000000001.y"):   # 不像有序名：合法
            self.assertEqual(self.ok("send", self.mb, name, stdin="{}").strip(), name)
        self.assertEqual(self.ls("tmp"), [])
        self.assertFalse((self.mb / "order.json").exists())

    def test_j3_own_name_exists(self):
        self.init()
        self.ok("send", self.mb, "x", stdin='{"n": 1}')
        self.own_error(self.run_p("send", self.mb, "x", stdin='{"n": 2}'), "LetterExists")   # new/ 撞名
        self.assertEqual(self.letter("new", "x")["body"], {"n": 1})
        self.assertEqual(self.ls("tmp"), [])                                                 # 半截自己刪
        (self.mb / "tmp" / "y").mkdir()                                                       # tmp/ 撞名（別人正在寫）
        self.own_error(self.run_p("send", self.mb, "y", stdin="{}"), "LetterExists")
        self.own_error(self.run_p("send", "--ordered", self.mb, "y", stdin="{}"), "LetterExists")
        self.assertEqual(self.ls("tmp"), ["y"])
        self.assertEqual(self.ls("new"), ["x"])
        self.ok("take", self.mb)
        self.assertEqual(self.ok("send", self.mb, "x", stdin="{}").strip(), "x")             # cur/ 有同名的不擋
        self.ok("done", "--keep", self.mb, "x")
        self.ok("take", self.mb)
        self.own_error(self.run_p("done", "--keep", self.mb, "x"), "WriteFailed")            # archive/ 已有同名＝搬不進
        self.assertEqual(self.ls("cur"), ["x"])

    # ---------- K：有序、無序同箱 ----------
    def test_k1_ordered_first(self):
        self.init()
        u1 = self.send({"u": 1})
        u2 = self.send({"u": 2})
        o1 = self.send({"o": 1}, flags=("--ordered",))
        o2 = self.send({"o": 2}, flags=("--ordered",))
        self.ok("send", self.mb, "aaa", stdin="{}")   # 自己給的無序名照字面排：比時間開頭的 0… 後
        self.assertEqual(self.ok("take", self.mb).strip(), o1)
        self.assertEqual(self.ok("take-all", self.mb).split(), [o2, u1, u2, "aaa"])

    def test_k2_gap_takes_next(self):
        """缺號不等：直接拿下一個（不逐號探、不讀 order.json）。"""
        self.init()
        u = self.send()
        for name in ("000000000700.b", "000000000003.a", "000000123456.c"):
            d = self.mb / "new" / name
            d.mkdir()
            (d / "letter.json").write_text(json.dumps({"sender": "/", "sent_at": "t", "body": {}}))
        (self.mb / "order.json").write_text('{"counter_letters": 1}')   # 跟 new/ 對不上也不看
        t0 = time.monotonic()
        self.assertEqual(self.ok("take", self.mb).strip(), "000000000003.a")
        self.assertEqual(self.ok("take", self.mb).strip(), "000000000700.b")
        self.assertLess(time.monotonic() - t0, 5)
        self.assertEqual(self.ok("take-all", self.mb).split(), ["000000123456.c", u])
        (self.mb / "order.json").write_text('{"counter_letters": 500}')
        self.assertEqual(self.send(flags=("--ordered",)).split(".")[0], "000000000501")

    def test_k3_ordered_jumps_queue(self):
        """無序的被有序的一直插隊也接受。"""
        self.init()
        u = self.send()
        for i in range(3):
            o = self.send(flags=("--ordered",))
            self.assertEqual(self.ok("take", self.mb).strip(), o)
        self.assertEqual(self.ok("take", self.mb).strip(), u)

    # ---------- L：see／done 不給信件名稱 ----------
    def test_l1_default_first_in_cur(self):
        self.init()
        for cmd in ("see", "done"):
            r = self.run_p(cmd, self.mb)
            self.assertEqual((r.returncode, r.stdout, r.stderr), (10, "", ""))   # cur/ 空
        u = self.send({"u": 1})
        o = self.send({"o": 1}, flags=("--ordered",))
        self.assertEqual(self.ok("take-all", self.mb).split(), [o, u])
        self.assertEqual(json.loads(self.ok("see", self.mb))["body"], {"o": 1})   # 處理順序第一封
        self.ok("done", "--keep", self.mb)
        self.assertEqual(self.ls("archive"), [o])
        self.assertEqual(json.loads(self.ok("see", self.mb))["body"], {"u": 1})
        self.ok("done", self.mb)
        self.assertEqual(self.ls("cur"), [])
        self.assertEqual(self.run_p("done", "--reply", self.mb, stdin="{}").returncode, 10)

    def test_l2_default_reply(self):
        self.init()
        rb = self.t / "rb"
        self.init(rb)
        a = self.send(flags=("--reply-to", rb))
        self.ok("take", self.mb)
        rid = self.ok("done", "--reply", self.mb, stdin='{"r": 1}').strip()
        self.assertEqual(self.letter("new", rid, rb)["in_reply_to"], a)
        self.assertEqual(self.ls("cur"), [])

    # ---------- M：send 的可寫檢查、reply_to 的驗法 ----------
    @unittest.skipIf(os.geteuid() == 0, "root 不受權限位元限制")
    def test_m1_not_writable(self):
        self.init()
        for part in ("tmp", "new"):
            d = self.mb / part
            d.chmod(0o555)
            try:
                self.own_error(self.run_p("send", self.mb, stdin="{}"), "MailboxBad")
            finally:
                d.chmod(0o755)
        self.assertEqual(self.ls("new"), [])
        self.assertEqual(self.ls("tmp"), [])

    def test_m2_reply_to_checked(self):
        self.init()
        self.own_error(self.run_p("send", "--reply-to", self.t / "nobox", self.mb, stdin="{}"), "MailboxMissing")
        half = self.t / "half"
        (half / "tmp").mkdir(parents=True)
        self.own_error(self.run_p("send", "--reply-to", half, self.mb, stdin="{}"), "MailboxMissing")   # 少 new/
        (half / "new").mkdir()
        a = self.send(flags=("--reply-to", half))   # 有 tmp/、new/ 就行（cur/ 不看）
        self.assertEqual(self.letter("new", a)["reply_to"], str(half))
        if os.geteuid() != 0:
            (half / "new").chmod(0o555)
            try:
                self.own_error(self.run_p("send", "--reply-to", half, self.mb, stdin="{}"), "MailboxBad")
            finally:
                (half / "new").chmod(0o755)
        self.assertEqual(self.ls("new"), [a])
        self.assertEqual(self.ls("tmp"), [])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0], "-v"])
