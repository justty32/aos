#!/usr/bin/env python3
"""test_cli.py：aos-llm-kernel 命令列的測試（ctest 會跑）。只用標準庫（unittest）。

    python3 tests/test_cli.py bin/aos-llm-kernel

每個案例一個暫存資料夾：stack/（AOS_STACK）、mb/（信箱）、kernel.json。信是測試自己寫的（假裝是閘門寄的）：
信號照 aos-gate 的格式 <奈秒>.<pid>.<started_at_ticks>；「寄信的人還在」＝測試自己 flock 住信裡的 sender.flock（同閘門），
要「寄信的人不在了」就留一個沒人鎖的 sender.flock（或乾脆沒有）。
A 段：命令列與設定；B 段：排隊（level、deadline、等了幾次、先來先上、aging）；C 段：slots；D 段：回信的各種錯
（DeadlineMissed、LetterBad、單子壞）；E 段：收拾（寄信的人不在、上一次 kernel 死了留在 cur/）；F 段：鎖、訊號、環境與 cwd、逾時；
G 段 `_metainfo`、H 段 token 回報與額度；I 段 accept（只跑名單裡的單子，10-24 堵沙箱信箱後門）。
"""
import fcntl
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

BIN = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else
                      os.path.join(os.path.dirname(__file__), "..", "bin", "aos-llm-kernel"))
IMPLS = Path(__file__).resolve().parent.parent.parent
EXEC_BIN = IMPLS / "aos-exec" / "bin"


def ticks(pid):
    return int(Path("/proc/%d/stat" % pid).read_text().rpartition(")")[2].split()[19])


SEQ = [0]


def new_id(pid=None, t=None):
    """跟 aos-gate 的 letter_id 同格式；pid 預設＝測試自己（寄信的人還在）。"""
    SEQ[0] += 1
    pid = pid or os.getpid()
    t = ticks(pid) if t is None else t
    return "%020d.%d.%d" % (time.time_ns() + SEQ[0], pid, t)


def dead_id():
    p = subprocess.Popen(["true"])
    t = ticks(p.pid)
    p.wait()
    return new_id(p.pid, t)


class Case(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.t = Path(self.td.name)
        self.stack = self.t / "stack"
        self.stack.mkdir()
        self.mb = self.t / "mb"
        self.cfg({"mailbox": str(self.mb), "slots": 1})
        self.locks = []

    def tearDown(self):
        for f in self.locks:
            f.close()
        self.td.cleanup()

    def cfg(self, doc):
        (self.t / "kernel.json").write_text(json.dumps(doc))

    def env(self, extra=None, stack=True):
        e = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        e["PATH"] = str(EXEC_BIN) + os.pathsep + e.get("PATH", "")
        if stack:
            e["AOS_STACK"] = str(self.stack)
        e.update(extra or {})
        return e

    def run_k(self, args=("kernel.json",), extra=None, stack=True, timeout=30):
        r = subprocess.run([BIN, *args], capture_output=True, text=True, env=self.env(extra, stack), cwd=self.t,
                           timeout=timeout)
        return r

    def own_error(self, r, code):
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)
        self.assertTrue(r.stderr.startswith("aos-llm-kernel: %s " % code), r.stderr)

    def post(self, argv=None, priority=None, id=None, inst=None, env=None, box="new", raw=None, alive=True):
        """寫一封信進 mb/<box>/<id>/；回 id。alive＝像閘門那樣 flock 住 sender.flock（False＝鎖檔在、沒人鎖）。"""
        id = id or new_id()
        d = self.mb / box / id
        d.mkdir(parents=True)
        f = open(d / "sender.flock", "w")
        if alive:
            fcntl.flock(f, fcntl.LOCK_EX)
            self.locks.append(f)
        else:
            f.close()
        if raw is not None:
            (d / "letter.json").write_text(raw)
            return id
        if inst is None:
            inst = {"argv": argv or ["true"], "cwd": str(self.t)}
        letter = {"inst": inst, "env": env if env is not None else {"PATH": os.environ["PATH"]}}
        if priority is not None:
            letter["priority"] = priority
        (d / "letter.json").write_text(json.dumps(letter))
        return id

    def mark(self, name):
        """一張單子：在 t/marks 追加自己的名字（看誰先跑）。"""
        return ["sh", "-c", 'echo %s >> "%s"' % (name, self.t / "marks")]

    def marks(self):
        p = self.t / "marks"
        return p.read_text().split() if p.exists() else []

    def reply(self, id):
        return json.loads((self.mb / "done" / id / "reply.json").read_text())

    def served(self):
        p = self.stack / "served.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []


class A_Cli(Case):
    def test_usage(self):
        self.own_error(self.run_k(()), "ArgumentsBad")
        self.own_error(self.run_k(("kernel.json", "x")), "ArgumentsBad")
        self.own_error(self.run_k(("--cfg", "kernel.json")), "FlagUnknown")

    def test_stack_missing(self):
        self.own_error(self.run_k(stack=False), "StackMissing")

    def test_cfg_errors(self):
        self.own_error(self.run_k(("nope.json",)), "CfgMissing")
        for bad in ({"slots": 0}, {"slots": "2"}, {"mailbox": 3}, {"mailbox": ""}, [1]):
            self.cfg(bad)
            self.own_error(self.run_k(), "CfgBad")
        self.cfg({"mailbox": {"$env": "NOPE_NOT_SET"}})
        self.own_error(self.run_k(), "DirectiveBad")

    def test_empty_mailbox_default_under_stack(self):
        self.cfg({"_entry": "ignored"})   # mailbox 沒寫＝$AOS_STACK/mailbox；其他 key 忽略
        r = self.run_k()
        self.assertEqual(r.returncode, 0, r.stderr)
        for box in ("tmp", "new", "cur", "done"):
            self.assertTrue((self.stack / "mailbox" / box).is_dir())
        self.assertEqual(json.loads((self.stack / "queue.json").read_text()), {"counter_runs": 1, "seen_at_runs": {}})
        self.assertEqual(self.run_k().returncode, 0)
        self.assertEqual(json.loads((self.stack / "queue.json").read_text())["counter_runs"], 2)

    def test_mailbox_directive(self):
        self.cfg({"mailbox": {"$env": "MB"}, "slots": {"$env": "N"}})   # 指示詞先解（slots 解出來是字串＝壞）
        r = self.run_k(extra={"MB": str(self.t / "m2"), "N": "1"})
        self.own_error(r, "CfgBad")
        self.cfg({"mailbox": {"$env": "MB"}})
        r = self.run_k(extra={"MB": str(self.t / "m2")})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.t / "m2" / "new").is_dir())

    def test_queue_bad(self):
        (self.stack / "queue.json").write_text("{")
        self.own_error(self.run_k(), "QueueBad")


class B_Order(Case):
    def drain(self, n):
        for _ in range(n):
            r = self.run_k()
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_level_deadline_fifo(self):
        self.post(self.mark("low1"), "low")
        self.post(self.mark("normal1"))                          # 沒寫＝normal
        self.post(self.mark("normal_dl_late"), {"deadline": time.time() + 3600})
        self.post(self.mark("high_num"), 5)                      # 數字 > 0＝high
        self.post(self.mark("normal2"), {"level": "normal", "class": "chat"})   # 其他 key 不管
        self.post(self.mark("normal_dl_soon"), {"level": 0, "deadline": time.strftime(
            "%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(time.time() + 600))})
        self.post(self.mark("low_num"), -2)
        self.drain(7)
        self.assertEqual(self.marks(), ["high_num", "normal_dl_soon", "normal_dl_late", "normal1", "normal2",
                                        "low1", "low_num"])
        s = self.served()
        self.assertEqual([x["level"] for x in s], ["high", "normal", "normal", "normal", "normal", "low", "low"])
        self.assertEqual([x["counter_waited_runs"] for x in s], [0, 1, 2, 3, 4, 5, 6])
        for x in s:   # 這封被處理的時間（10-25 前叫 at）
            self.assertRegex(x["served_at"], r"\A\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}")
            self.assertNotIn("at", x)
        self.assertEqual(list(os.listdir(self.mb / "done")), [i for i in os.listdir(self.mb / "done")])

    def test_aging(self):
        old = self.post(self.mark("low_old"), "low")
        self.post(self.mark("normal_new"))
        (self.stack / "queue.json").write_text(json.dumps({"counter_runs": 20, "seen_at_runs": {old: 0}}))
        self.drain(1)   # low 等了 21 次：-1＋2＝1 級，比 normal 先
        self.assertEqual(self.marks(), ["low_old"])

    def test_aging_not_yet(self):
        old = self.post(self.mark("low_old"), "low")
        self.post(self.mark("normal_new"))
        (self.stack / "queue.json").write_text(json.dumps({"counter_runs": 5, "seen_at_runs": {old: 0}}))
        self.drain(1)   # 等了 6 次還不到 10：normal 先
        self.assertEqual(self.marks(), ["normal_new"])

    def test_seen_kept_and_pruned(self):
        a = self.post(self.mark("a"))
        b = self.post(self.mark("b"))
        self.drain(1)
        q = json.loads((self.stack / "queue.json").read_text())
        self.assertEqual(q, {"counter_runs": 1, "seen_at_runs": {b: 1}})
        self.drain(1)
        self.assertEqual(json.loads((self.stack / "queue.json").read_text()), {"counter_runs": 2, "seen_at_runs": {}})
        self.assertNotIn(a, q["seen_at_runs"])


class C_Slots(Case):
    def test_slots_run_together(self):
        self.cfg({"mailbox": str(self.mb), "slots": 2})
        for n in ("x", "y", "z"):
            self.post(["sh", "-c", "sleep 1; echo %s >> '%s'" % (n, self.t / "marks")])
        t0 = time.monotonic()
        r = self.run_k()
        took = time.monotonic() - t0
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sorted(self.marks()), ["x", "y"])    # 前兩封一起跑
        self.assertLess(took, 1.8)
        self.assertEqual(len(os.listdir(self.mb / "new")), 1)  # 第三封還在排

    def test_slots_one_is_serial(self):
        for n in ("x", "y"):
            self.post(self.mark(n))
        self.run_k()
        self.assertEqual(self.marks(), ["x"])


class D_Replies(Case):
    def test_code_signal_and_streams(self):
        i = self.post(["sh", "-c", "echo out; echo err >&2; exit 7"])
        self.run_k()
        self.assertEqual(self.reply(i), {"code": 7, "signal": None})
        self.assertEqual((self.mb / "done" / i / "stdout.txt").read_text(), "out\n")
        self.assertEqual((self.mb / "done" / i / "stderr.txt").read_text(), "err\n")
        self.assertEqual(self.served()[0]["code"], 7)

    def test_own_stdout_not_overridden(self):
        i = self.post(inst={"argv": ["sh", "-c", "echo mine"], "cwd": str(self.t), "stdout": "o.txt"})
        self.run_k()
        self.assertEqual((self.t / "o.txt").read_text(), "mine\n")
        self.assertFalse((self.mb / "done" / i / "stdout.txt").exists())

    def test_deadline_missed_not_run(self):
        i = self.post(self.mark("late"), {"level": "high", "deadline": time.time() - 1})
        j = self.post(self.mark("ok"), {"deadline": "2000-01-01T00:00:00Z"})
        self.run_k()
        self.assertEqual(self.marks(), [])
        for x in (i, j):
            self.assertEqual(self.reply(x)["error"]["code"], "DeadlineMissed")
        self.assertEqual([s["error"] for s in self.served()], ["DeadlineMissed", "DeadlineMissed"])

    def test_letter_bad(self):
        ids = [self.post(raw="{"), self.post(raw="[]"), self.post(inst=["true"]),
               self.post(self.mark("x"), "urgent"), self.post(self.mark("x"), True),
               self.post(self.mark("x"), {"deadline": "tomorrow"}),
               self.post(self.mark("x"), {"deadline": "2026-10-24T18:00:00"})]   # 沒時區不猜
        r = self.run_k()
        self.assertEqual(r.returncode, 0, r.stderr)
        for i in ids:
            self.assertEqual(self.reply(i)["error"]["code"], "LetterBad", i)
        self.assertEqual(self.marks(), [])

    def test_envelope_not_checked(self):
        """10-29 信封（kind、sender、sent_at）不檢查也不擋：寫了、寫怪、沒寫都照跑；不認得的 key 忽略（N-16）。"""
        env = {"PATH": os.environ["PATH"]}
        inst = {"argv": self.mark("a"), "cwd": str(self.t)}
        i = self.post(raw=json.dumps({"kind": "letter", "sender": "/home/u/ws", "sent_at": "2026-10-29T08:12:33.123+00:00",
                                      "inst": inst, "env": env}))
        j = self.post(raw=json.dumps({"kind": 3, "sender": None, "sent_at": [], "body": {"x": 1}, "whatever": True,
                                      "inst": {"argv": self.mark("b"), "cwd": str(self.t)}, "env": env}))
        for _ in range(2):   # slots 1：一次跑一封
            r = self.run_k()
            self.assertEqual(r.returncode, 0, r.stderr)
        for x in (i, j):
            self.assertEqual(self.reply(x), {"code": 0, "signal": None}, x)
        self.assertEqual(sorted(self.marks()), ["a", "b"])

    def test_inst_bad_is_reply_not_kernel_error(self):
        i = self.post(inst={"cwd": str(self.t)})
        j = self.post(inst={"argv": ["/nope/x"], "cwd": str(self.t)})
        r = self.run_k()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.reply(i)["error"]["code"], "EntryBad")
        self.assertTrue(self.reply(i)["error"]["msg"].startswith("單子跑不起來："))
        r = self.run_k()
        self.assertEqual(self.reply(j)["error"]["code"], "LaunchFailed")


class E_Sweep(Case):
    def test_dead_sender_dropped(self):
        n = self.post(self.mark("dead"), alive=False)
        t = self.post(box="tmp", alive=False)
        d = self.post(box="done", alive=False)
        alive_done = self.post(box="done")
        junk = "not-a-letter"
        (self.mb / "tmp" / junk).mkdir()                            # 沒有 sender.flock＝不在
        writing = self.post(id=".w1", box="tmp")                    # 閘門正在寫（. 開頭、鎖著）：不碰
        bare = ".w2"
        (self.mb / "tmp" / bare).mkdir()                            # 正在寫、還沒建鎖檔的那一瞬間：不碰
        (self.mb / "tmp" / ".w4").mkdir()
        (self.mb / "tmp" / ".w4" / "sender.flock").write_text("")   # 建了鎖檔、還沒上鎖（也還沒寫信）：不碰
        gone = self.post(id=".w3", box="tmp", alive=False)          # 寫好信了、閘門死了：刪
        self.run_k()
        self.assertEqual(self.marks(), [])
        for box, i in (("new", n), ("tmp", t), ("done", d), ("tmp", junk), ("tmp", gone)):
            self.assertFalse((self.mb / box / i).exists(), (box, i))
        self.assertTrue((self.mb / "done" / alive_done).exists())   # 寄信的人還在：等它來拿
        self.assertTrue((self.mb / "tmp" / writing).exists())
        self.assertTrue((self.mb / "tmp" / bare).exists())
        self.assertTrue((self.mb / "tmp" / ".w4").exists())

    def test_alive_is_the_lock_not_the_pid(self):
        """10-24（S15）：名字裡的 pid 是死掉的行程也照跑，只要 sender.flock 有人鎖著（沙箱裡的閘門 pid 在外面對不上）；
        反過來 pid 是活的（測試自己）但沒人鎖＝不在。"""
        a = self.post(self.mark("a"), id=dead_id())
        b = self.post(self.mark("b"), alive=False)
        self.run_k()
        self.assertEqual(self.marks(), ["a"])
        self.assertFalse((self.mb / "new" / b).exists())

    def test_orphan_in_cur(self):
        a = self.post(self.mark("a"), "high", box="cur")
        b = self.post(box="cur")
        (self.mb / "cur" / b / "reply.json").write_text(json.dumps({"code": 3, "signal": None}))
        r = self.run_k()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.reply(a)["error"]["code"], "RunFailed")
        self.assertEqual(self.reply(b), {"code": 3, "signal": None})   # 跑完、只差搬：照它
        self.assertEqual(os.listdir(self.mb / "cur"), [])
        self.assertEqual(self.marks(), [])   # 不重跑（10-15 六題 6「回錯」）
        s = {x["letter"]: x for x in self.served()}
        self.assertEqual(s[a]["level"], "high")


    def test_orphan_with_live_runner_kept(self):
        a = self.post(box="cur")
        (self.mb / "cur" / a / "runner.json").write_text(json.dumps({"pid": os.getpid(),
                                                                     "started_at_ticks": ticks(os.getpid())}))
        self.post(self.mark("waiting"))
        r = self.run_k()   # slots 1：那一格被還在跑的佔著，這次不跑新的
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.mb / "cur" / a).exists())
        self.assertEqual(self.marks(), [])
        (self.mb / "cur" / a / "reply.json").write_text(json.dumps({"code": 0, "signal": None}))
        self.run_k()       # 回信寫好了：搬 done/、空出格子
        self.assertEqual(self.reply(a), {"code": 0, "signal": None})
        self.assertEqual(self.marks(), ["waiting"])

    def test_dead_runner_is_run_failed(self):
        a = self.post(box="cur")
        d = dead_id().split(".")
        (self.mb / "cur" / a / "runner.json").write_text(json.dumps({"pid": int(d[1]), "started_at_ticks": int(d[2])}))
        self.run_k()
        self.assertEqual(self.reply(a)["error"]["code"], "RunFailed")


class F_Run(Case):
    def test_lock(self):
        (self.mb).mkdir()
        with open(self.mb / ".flock", "w") as f:   # 10-29 改名（原 .lock；.lock/ 留給 N-15 的資料夾鎖）
            fcntl.flock(f, fcntl.LOCK_EX)
            self.post(self.mark("x"))
            self.own_error(self.run_k(), "LockFailed")
            self.assertEqual(self.marks(), [])
        self.assertEqual(self.run_k().returncode, 0)
        self.assertEqual(self.marks(), ["x"])
        self.assertTrue((self.mb / ".flock").is_file())
        self.assertFalse((self.mb / ".lock").exists())

    def test_old_lock_name_not_used(self):
        """10-29：別人 flock 住舊名 .lock 不算鎖著（不留舊名）；kernel 只認 .flock。"""
        (self.mb).mkdir()
        with open(self.mb / ".lock", "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            self.post(self.mark("x"))
            self.assertEqual(self.run_k().returncode, 0)
        self.assertEqual(self.marks(), ["x"])

    def test_env_and_cwd_from_letter(self):
        (self.t / "w").mkdir()
        i = self.post(inst={"argv": ["sh", "-c", 'echo "$FOO|${KERNEL_ONLY-unset}|$(pwd)"; cat'],
                            "cwd": str(self.t / "w")},
                      env={"PATH": os.environ["PATH"], "FOO": "from-gate"})
        r = self.run_k(extra={"KERNEL_ONLY": "x"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.mb / "done" / i / "stdout.txt").read_text(),
                         "from-gate|unset|%s\n" % (self.t / "w"))   # stdin 是 /dev/null（cat 馬上結束）

    def test_timeout_in_inst(self):
        i = self.post(inst={"argv": ["sleep", "5"], "cwd": str(self.t), "timeout_ms": 200})
        t0 = time.monotonic()
        self.run_k()
        self.assertLess(time.monotonic() - t0, 4)
        rep = self.reply(i)
        self.assertNotEqual(rep["code"], 0)

    def test_sigterm_forwarded(self):
        i = self.post(["sh", "-c", "trap 'echo got >> \"%s\"; exit 5' TERM; sleep 5 & wait" % (self.t / "marks")])
        p = subprocess.Popen([BIN, "kernel.json"], env=self.env(), cwd=self.t, stderr=subprocess.PIPE, text=True)
        end = time.monotonic() + 5
        while not list((self.mb / "cur").glob("*")) and time.monotonic() < end:
            time.sleep(0.02)
        time.sleep(0.3)
        p.send_signal(signal.SIGTERM)
        p.wait(timeout=10)
        self.assertEqual(p.returncode, 128 + signal.SIGTERM, p.stderr.read())
        self.assertEqual(self.marks(), ["got"])
        self.assertEqual(self.reply(i), {"code": 5, "signal": None})

    def test_signal_early_leaves_nothing_half(self):
        self.post(["sleep", "3"])
        p = subprocess.Popen([BIN, "kernel.json"], env=self.env(), cwd=self.t)
        end = time.monotonic() + 5   # 等它擋好訊號（還沒擋就收到＝直接被殺，那是任何程式都一樣的起跑空窗）
        while time.monotonic() < end:
            st = Path("/proc/%d/status" % p.pid).read_text()
            if any(l.startswith("SigBlk:") and int(l.split()[1], 16) & (1 << (signal.SIGTERM - 1))
                   for l in st.splitlines()):
                break
        p.send_signal(signal.SIGTERM)   # 認領前收到＝不跑、還在 new/；認領後收到＝轉給單子、回信進 done/。兩種都不留在 cur/
        p.wait(timeout=10)
        self.assertIn(p.returncode, (0, 128 + signal.SIGTERM))
        self.assertEqual(os.listdir(self.mb / "cur"), [])
        self.assertEqual(len(os.listdir(self.mb / "new")) + len(os.listdir(self.mb / "done")), 1)


class G_Metainfo(Case):
    """10-24：單子的 `_metainfo`（time_ms、llm_tokens）——同級同時限時宣告短的先；寫壞照樣跑、記在 served。"""
    def meta_post(self, name, meta, priority=None):
        inst = {"argv": self.mark(name), "cwd": str(self.t)}
        if meta is not None:
            inst["_metainfo"] = meta
        return self.post(inst=inst, priority=priority)

    def drain(self, n):
        for _ in range(n):
            self.assertEqual(self.run_k().returncode, 0)

    def test_short_first_even_if_later(self):
        self.meta_post("long", {"time_ms": 60000})
        self.meta_post("none", None)
        self.meta_post("short", {"time_ms": {"val": 500, "max": 2000}, "llm_tokens": 300})
        self.drain(3)
        self.assertEqual(self.marks(), ["short", "long", "none"])   # 有寫的在沒寫的前面
        s = self.served()
        self.assertEqual([x["time_ms"] for x in s], [500, 60000, None])
        self.assertEqual([x["metainfo_bad"] for x in s], [[], [], []])
        self.assertTrue(all(isinstance(x["elapsed_ms"], int) for x in s))

    def test_level_and_deadline_still_win(self):
        self.meta_post("short_low", {"time_ms": 1}, "low")
        self.meta_post("long_dl", {"time_ms": 99999}, {"deadline": time.time() + 600})
        self.meta_post("long_normal", {"time_ms": 99999})
        self.meta_post("short_normal", {"time_ms": 1})
        self.drain(4)
        self.assertEqual(self.marks(), ["long_dl", "short_normal", "long_normal", "short_low"])

    def test_bad_shapes_still_run(self):
        a = self.meta_post("a", {"time_ms": "fast", "llm_tokens": -3})
        b = self.meta_post("b", "not an object")
        c = self.meta_post("c", {"time_ms": {"max": 10}, "other": 1})
        self.drain(3)
        self.assertEqual(sorted(self.marks()), ["a", "b", "c"])
        bad = {x["letter"]: x["metainfo_bad"] for x in self.served()}
        self.assertEqual(bad, {a: ["time_ms", "llm_tokens"], b: ["_metainfo"], c: ["time_ms"]})
        for i in (a, b, c):
            self.assertEqual(self.reply(i), {"code": 0, "signal": None})


class H_Report(Case):
    """10-24：token 回報（AOS_KERNEL_REPORT）與額度（kernel.json 的 budget、$AOS_STACK/used.json）。"""
    def usage(self, name, usage, raw=None):
        """一張單子：記下名字，再照 AOS_KERNEL_REPORT 寫回報（usage 是 dict；raw 是原樣的字；兩個都 None＝不寫）。"""
        text = raw if raw is not None else (json.dumps(usage) if usage is not None else None)
        cmd = 'echo %s >> "%s"' % (name, self.t / "marks")
        if text is not None:
            cmd += "; printf '%%s' '%s' > \"$AOS_KERNEL_REPORT\"" % text
        return self.post(["sh", "-c", cmd])

    def used(self):
        return json.loads((self.stack / "used.json").read_text())

    def drain(self, n):
        for _ in range(n):
            r = self.run_k()
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_env_points_into_letter(self):
        i = self.post(["sh", "-c", 'echo "$AOS_KERNEL_REPORT"'], env={"PATH": os.environ["PATH"],
                                                                        "AOS_KERNEL_REPORT": "/from/gate"})
        self.drain(1)
        self.assertEqual((self.mb / "done" / i / "stdout.txt").read_text().strip(),
                         str(self.mb / "cur" / i / "report.json"))   # 信小格裡的檔，蓋掉信裡帶來的

    def test_written_missing_and_bad(self):
        a = self.usage("a", {"prompt_tokens": 30, "completion_tokens": 12, "total_tokens": 42})
        b = self.usage("b", {"prompt_tokens": 5, "completion_tokens": 3})          # 沒 total：兩個相加
        c = self.usage("c", None)                                                    # 沒寫：只算次數
        d = self.usage("d", None, raw="{")                                           # 寫壞
        e = self.usage("e", {"total_tokens": -1})
        f = self.usage("f", None, raw="[1]")
        self.drain(6)
        got = {x["letter"]: (x["counter_tokens"], x["report_bad"]) for x in self.served()}
        self.assertEqual(got, {a: (42, False), b: (8, False), c: (None, False), d: (None, True),
                               e: (None, True), f: (None, True)})
        u = self.used()
        self.assertEqual((u["window"], u["counter_calls"], u["counter_tokens"], u["counter_all_calls"], u["counter_all_tokens"]), ("day", 6, 50, 6, 50))
        self.assertRegex(u["since"], r"^\d{4}-\d\d-\d\dT00:00:00[+-]\d\d:\d\d$")

    def test_not_run_not_counted(self):
        self.post(raw="{")                                               # LetterBad
        self.post(self.mark("late"), {"deadline": time.time() - 1})     # DeadlineMissed
        self.drain(1)
        self.assertEqual(self.used()["counter_calls"] if (self.stack / "used.json").exists() else 0, 0)
        self.assertEqual([x["counter_tokens"] for x in self.served()], [None, None])

    def test_budget_calls_refuse(self):
        self.cfg({"mailbox": str(self.mb), "slots": 1, "budget": {"max_calls": 2}})
        ids = [self.usage(n, {"total_tokens": 10}) for n in ("x", "y", "z")]
        self.drain(3)
        self.assertEqual(self.marks(), ["x", "y"])
        rep = self.reply(ids[2])
        self.assertEqual(rep["error"]["code"], "BudgetMissing")
        s = {x["letter"]: x for x in self.served()}   # 第二次跑 y 時就看得出 z 會超過：z 當場回錯（比 y 的那行先寫）
        self.assertEqual([s[i]["error"] for i in ids], [None, None, "BudgetMissing"])
        self.assertEqual((s[ids[2]]["level"], s[ids[2]]["counter_tokens"]), ("normal", None))
        self.assertEqual((self.used()["counter_calls"], self.used()["counter_tokens"]), (2, 20))   # 回錯的不算

    def test_budget_tokens_refuse_all_waiting(self):
        self.cfg({"mailbox": str(self.mb), "slots": 1, "budget": {"max_tokens": 100, "window": "hour"}})
        self.usage("big", {"total_tokens": 150})
        y = self.usage("y", {"total_tokens": 1})
        z = self.usage("z", {"total_tokens": 1})
        self.drain(1)   # 跑之前還沒到頂；跑完 150 > 100（事後才知道，會超過一點）
        self.drain(1)   # 到頂：排著的全回錯，不留著
        self.assertEqual(self.marks(), ["big"])
        for i in (y, z):
            self.assertEqual(self.reply(i)["error"]["code"], "BudgetMissing")
        self.assertRegex(self.used()["since"], r"T\d\d:00:00[+-]")

    def test_budget_wait_then_next_window(self):
        self.cfg({"mailbox": str(self.mb), "slots": 2, "budget": {"max_calls": 1, "spent": "wait"}})
        self.usage("x", {"total_tokens": 7})
        y = self.usage("y", {"total_tokens": 7})
        self.drain(2)   # slots 2 也只跑 1 封；第二次到頂：留在 new/
        self.assertEqual(self.marks(), ["x"])
        self.assertTrue((self.mb / "new" / y).is_dir())
        self.assertEqual(len(self.served()), 1)   # 等著的不寫 served
        u = self.used()
        u["since"] = "2000-01-01T00:00:00+00:00"   # 假裝這一窗是很久以前開的＝換窗了
        (self.stack / "used.json").write_text(json.dumps(u))
        self.drain(1)
        self.assertEqual(self.marks(), ["x", "y"])
        u = self.used()
        self.assertEqual((u["counter_calls"], u["counter_tokens"], u["counter_all_calls"], u["counter_all_tokens"]), (1, 7, 2, 14))   # 這一窗歸零、總數照留
        self.assertEqual(self.served()[1]["counter_waited_runs"], 2)

    def test_window_all_never_resets(self):
        self.cfg({"mailbox": str(self.mb), "budget": {"window": "all"}})
        self.usage("x", {"total_tokens": 3})
        self.drain(1)
        u = self.used()
        self.assertEqual((u["window"], u["since"], u["counter_calls"]), ("all", None, 1))
        self.cfg({"mailbox": str(self.mb)})   # 改回 day＝換窗：這一窗歸零、總數照留
        self.usage("y", {"total_tokens": 4})
        self.drain(1)
        u = self.used()
        self.assertEqual((u["window"], u["counter_calls"], u["counter_tokens"], u["counter_all_calls"], u["counter_all_tokens"]), ("day", 1, 4, 2, 7))

    def test_budget_cfg_and_used_bad(self):
        for bad in ({"max_calls": -1}, {"max_tokens": "9"}, {"window": "week"}, {"spent": "drop"}, {"max_calls": True}, [1],
                    {"calls": 2}, {"tokens": 100}):   # 後兩個是 10-25 前的上限名，不認
            self.cfg({"mailbox": str(self.mb), "budget": bad})
            self.own_error(self.run_k(), "CfgBad")
        self.cfg({"mailbox": str(self.mb)})
        for bad in ("{", "[]", json.dumps({"window": "day", "since": None, "counter_calls": 1}),
                    json.dumps({"window": "day", "since": None, "calls": 0, "tokens": 0, "all_calls": 0, "all_tokens": 0})):   # 舊名（10-25 前）不認
            (self.stack / "used.json").write_text(bad)
            self.own_error(self.run_k(), "UsedBad")


class I_Accept(Case):
    """10-24 堵沙箱信箱後門：kernel.json 寫了 accept＝只跑名單裡的單子（argv、cwd 一字不差、不自帶 envs 與串流），環境用 kernel 自己的＋信裡 AOS_ 開頭的。"""

    def setUp(self):
        super().setUp()
        (self.t / "brain").mkdir()
        (self.t / "secret.txt").write_text("SECRET")
        self.brain = ["sh", "-c", 'echo "brain|$AOS_WS|${FOO-unset}|${KEY-unset}"']
        self.cfg({"mailbox": str(self.mb), "slots": 4, "accept": [{"argv": self.brain, "cwd": "brain"}]})   # cwd 從 kernel.json 的資料夾算

    def test_only_listed_inst_runs(self):
        ok = self.post(inst={"argv": self.brain, "cwd": str(self.t / "brain")},
                       env={"PATH": "/nowhere", "AOS_WS": "/w", "FOO": "from-letter", "LD_PRELOAD": "/x.so"})
        cat = self.post(inst={"argv": ["cat", str(self.t / "secret.txt")], "cwd": str(self.t / "brain")})
        cwd = self.post(inst={"argv": self.brain, "cwd": str(self.t)})                    # cwd 不同
        out = self.post(inst={"argv": self.brain, "cwd": str(self.t / "brain"), "stdout": str(self.t / "o.txt")})
        envs = self.post(inst={"argv": self.brain, "cwd": str(self.t / "brain"), "envs": {"A": "1"}})
        r = self.run_k(extra={"KEY": "kernel-key"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.reply(ok), {"code": 0, "signal": None})
        # PATH 用 kernel 的（信裡的 /nowhere 不算）、AOS_* 照信、其他（FOO）不帶、key 用 kernel 這邊的
        self.assertEqual((self.mb / "done" / ok / "stdout.txt").read_text(), "brain|/w|unset|kernel-key\n")
        for i in (cat, cwd, out, envs):
            self.assertEqual(self.reply(i)["error"]["code"], "InstUnknown", i)
            self.assertFalse((self.mb / "done" / i / "stdout.txt").exists())
        self.assertFalse((self.t / "o.txt").exists())
        self.assertEqual(sorted(s["error"] or "" for s in self.served()), ["", "InstUnknown", "InstUnknown", "InstUnknown", "InstUnknown"])
        self.assertEqual(self.used()["counter_calls"], 1)                                          # 沒跑的不算

    def test_accept_cfg_bad(self):
        for bad in ({"argv": [], "cwd": "."}, {"argv": ["x"]}, {"argv": "x", "cwd": "."}, {"argv": [1], "cwd": "."}, "x"):
            self.cfg({"mailbox": str(self.mb), "accept": bad if bad == "x" else [bad]})
            self.own_error(self.run_k(), "CfgBad")

    def used(self):
        return json.loads((self.stack / "used.json").read_text())


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]], verbosity=1)
