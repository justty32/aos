#!/usr/bin/env python3
"""test_cli.py：aos-kernel-llm 命令列的測試（ctest 會跑）。只用標準庫（unittest）。

    python3 tests/test_cli.py bin/aos-kernel-llm

每個案例一個暫存資料夾：stack/（AOS_STACK）、mb/（信箱）、kernel.json。信是測試自己寫的（假裝是閘門寄的）：
信號照 aos-gate 的格式 <奈秒>.<pid>.<started_at_ticks>，pid 用測試自己（所以「寄信的人還在」）；要「寄信的人不在了」就用一個已經結束的行程。
A 段：命令列與設定；B 段：排隊（level、deadline、等了幾次、先來先上、aging）；C 段：slots；D 段：回信的各種錯
（DeadlineMissed、LetterBad、單子壞）；E 段：收拾（寄信的人不在、上一次 kernel 死了留在 cur/）；F 段：鎖、訊號、環境與 cwd、逾時。
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
                      os.path.join(os.path.dirname(__file__), "..", "bin", "aos-kernel-llm"))
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

    def tearDown(self):
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
        self.assertTrue(r.stderr.startswith("aos-kernel-llm: %s " % code), r.stderr)

    def post(self, argv=None, priority=None, id=None, inst=None, env=None, box="new", raw=None):
        """寫一封信進 mb/<box>/<id>/；回 id。"""
        id = id or new_id()
        d = self.mb / box / id
        d.mkdir(parents=True)
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
        self.assertEqual(json.loads((self.stack / "queue.json").read_text()), {"runs": 1, "seen_at_runs": {}})
        self.assertEqual(self.run_k().returncode, 0)
        self.assertEqual(json.loads((self.stack / "queue.json").read_text())["runs"], 2)

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
        self.assertEqual([x["waited_runs"] for x in s], [0, 1, 2, 3, 4, 5, 6])
        self.assertEqual(list(os.listdir(self.mb / "done")), [i for i in os.listdir(self.mb / "done")])

    def test_aging(self):
        old = self.post(self.mark("low_old"), "low")
        self.post(self.mark("normal_new"))
        (self.stack / "queue.json").write_text(json.dumps({"runs": 20, "seen_at_runs": {old: 0}}))
        self.drain(1)   # low 等了 21 次：-1＋2＝1 級，比 normal 先
        self.assertEqual(self.marks(), ["low_old"])

    def test_aging_not_yet(self):
        old = self.post(self.mark("low_old"), "low")
        self.post(self.mark("normal_new"))
        (self.stack / "queue.json").write_text(json.dumps({"runs": 5, "seen_at_runs": {old: 0}}))
        self.drain(1)   # 等了 6 次還不到 10：normal 先
        self.assertEqual(self.marks(), ["normal_new"])

    def test_seen_kept_and_pruned(self):
        a = self.post(self.mark("a"))
        b = self.post(self.mark("b"))
        self.drain(1)
        q = json.loads((self.stack / "queue.json").read_text())
        self.assertEqual(q, {"runs": 1, "seen_at_runs": {b: 1}})
        self.drain(1)
        self.assertEqual(json.loads((self.stack / "queue.json").read_text()), {"runs": 2, "seen_at_runs": {}})
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
        n = self.post(self.mark("dead"), id=dead_id())
        t = self.post(id=dead_id(), box="tmp")
        d = self.post(id=dead_id(), box="done")
        alive_done = self.post(box="done")
        junk = self.post(id="not-an-id", box="tmp")
        self.run_k()
        self.assertEqual(self.marks(), [])
        for box, i in (("new", n), ("tmp", t), ("done", d), ("tmp", junk)):
            self.assertFalse((self.mb / box / i).exists(), (box, i))
        self.assertTrue((self.mb / "done" / alive_done).exists())   # 寄信的人還在：等它來拿

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
        with open(self.mb / ".lock", "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            self.post(self.mark("x"))
            self.own_error(self.run_k(), "LockFailed")
            self.assertEqual(self.marks(), [])
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


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]], verbosity=1)
