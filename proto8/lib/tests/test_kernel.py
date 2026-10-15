"""proto8/lib 的自動測試：通用 kernel（aos_kernel ＋ 判官 aos_kernel_judge、judge_rules）。只用標準庫：

    python3 -m unittest discover -s proto8/lib/tests

多數直接用 aos_gate.post() 丟信、在本行程呼叫 aos_kernel.tick()，看 log 與回信。
判官是暫存資料夾裡的小 python 腳本（stdin＝state 窗、stdout {"run", "defer", "reject"}）；有的會把被叫的次數記進檔。
端到端：閘門起真的行程；最後一個起真的 daemon＋loop，收工後查沒有漏行程。
"""
import json
import os
import signal
import subprocess
import sys
import threading
import time

from helpers import DAEMON, LIB, Tmp

import aos_gate
import aos_kernel as K

GATE = os.path.join(LIB, "aos_gate.py")
RULES = os.path.join(LIB, "judge_rules.py")
WAIT_ANS = "while [ ! -f ans ]; do sleep 0.02; done; cat"


def judge_py(body):
    """判官腳本：snap＝state 窗、q＝排隊的 id（字典序）；body 要 print 一份答案。每被叫一次往 calls 追加一行。"""
    return ("import json, os, sys\nsnap = json.load(sys.stdin)\nq = sorted(snap['queue'])\n"
            "open('calls', 'a').write('x\\n')\n" + body)


class KernelTest(Tmp):
    def setUp(self):
        super().setUp()
        self.box = aos_gate.mailbox(self.p("mb"))

    def cfg(self, judge=None, **kw):
        if isinstance(judge, str) and not judge.endswith(".py"):
            self.write("judge.py", judge_py(judge))
            judge = {"argv": [sys.executable, "judge.py"], "cwd": self.tmp, "timeout_ms": 5000}
        elif isinstance(judge, str):
            judge = {"argv": [sys.executable, judge], "cwd": self.tmp}
        return K.check(dict({"mailbox": self.p("mb"), "state": self.p("k.state.json"), "log": self.p("log.jsonl"),
                             "judge": judge, "slots": {"llm": 1}, "poll_ms": 10}, **kw))

    def send(self, text, res="llm", sh="cat", priority=None, **inst):
        doc = dict({"argv": ["sh", "-c", sh], "cwd": self.tmp}, **inst,
                   priority=aos_gate.normalize_priority(priority), sent=time.time())     # 信＝那張 inst＋私有 key
        if res is not None:
            doc["_metainfo"] = {"resource": res}
        name = aos_gate.post(self.box, doc, text)
        time.sleep(0.002)
        return name

    def reply(self, name):
        with open(os.path.join(self.box["reply"], name)) as f:
            return json.load(f)

    def stdout(self, name):
        with open(aos_gate.side(os.path.join(self.box["reply"], name), "stdout")) as f:
            return f.read()

    def log(self, event=None):
        try:
            with open(self.p("log.jsonl")) as f:
                recs = [json.loads(x) for x in f]
        except OSError:
            return []
        return [r for r in recs if event is None or r["event"] == event]

    def calls(self):
        try:
            return len(self.read("calls").split())
        except OSError:
            return 0

    def state(self):
        return json.loads(self.read("k.state.json"))

    def started(self, names):
        return [names[r["letter"]] for r in self.log("start")]

    # ---- 判官的答案 ----

    def test_judge_decision_honored(self):
        names = {self.send(x): x for x in "abc"}
        cfg = self.cfg("print(json.dumps({'run': [q[-1]]}))")   # 只點最後來的
        out = K.tick(cfg)
        self.assertEqual(self.started(names)[0], "c")
        self.assertEqual(self.log("decide")[0]["how"], "judge")
        self.assertEqual(sorted(s["letter"] for s in out["served"]), sorted(names))   # 之後局面變了再問，最後都跑完
        self.assertEqual(self.stdout(next(k for k, v in names.items() if v == "c")), "c")

    def test_judge_stdin_is_state_window(self):
        a, b = self.send("a"), self.send("b", priority="high")
        K.tick(self.cfg("json.dump(snap, open('snap', 'w')); print(json.dumps({'run': [q[0]]}))"))
        snap = json.loads(self.read("snap"))
        for k in ("state", "pid", "runs", "beat", "queue", "running", "slots", "budget", "judge_fails"):
            self.assertIn(k, snap)
        self.assertEqual(sorted(snap["queue"]), [a, b])
        self.assertEqual(snap["queue"][b]["priority"], {"level": "high"})
        self.assertEqual(snap["slots"], {"llm": {"total": 1, "used": 0}})
        st = self.state()                                            # 拍完的 state 窗：同一套 key，queue 空了
        self.assertEqual((st["state"], st["runs"], st["queue"], st["served"]), ("waiting", 1, {}, 2))

    def test_unnamed_is_defer(self):
        self.send("a")
        self.send("b")
        out = K.tick(self.cfg("print(json.dumps({}))"))
        self.assertEqual(out["served"], [])
        self.assertEqual(out["waiting"], 2)
        self.assertEqual(self.log("decide")[0]["run"], [])

    def test_overflow_truncated(self):
        self.send("a")
        self.send("b")
        self.send("c")
        K.tick(self.cfg("print(json.dumps({'run': q}))"))
        d = self.log("decide")[0]
        self.assertEqual((len(d["run"]), d["cut"]), (1, 2))
        self.assertEqual(len(self.log("done")), 3)

    def test_cheap_runs_without_slot_or_judge(self):
        self.send("x", res=None)
        self.send("y", res="none")
        out = K.tick(self.cfg("sys.exit(1)", slots={"llm": 0}))
        self.assertEqual(len(out["served"]), 2)
        self.assertEqual(self.calls(), 0)

    def test_unknown_resource(self):
        n = self.send("x", res="tpu")
        K.tick(self.cfg())
        self.assertEqual(self.reply(n)["error"]["code"], "ResourceUnknown")

    # ---- 判官錯、後援 ----

    def test_judge_failure_falls_back(self):
        for body in ("sys.exit(1)", "print('不是 JSON')", "print(json.dumps({'go': q}))",
                     "print(json.dumps({'reject': [{'id': q[0], 'code': 'X'}]}))", "print(json.dumps({'run': q, 'defer': q}))", "import time; time.sleep(5)"):
            with self.subTest(body=body):
                for f in ("k.state.json", "log.jsonl"):
                    if os.path.exists(self.p(f)):
                        os.remove(self.p(f))
                self.send("a", priority="low")
                self.send("b", priority="high")
                cfg = self.cfg(body)
                cfg["judge"]["timeout_ms"] = 300
                out = K.tick(cfg)
                self.assertEqual([r["how"] for r in self.log("decide")][0], "fallback")
                self.assertEqual(len(out["served"]), 2)
                self.assertEqual(self.stdout(self.log("start")[0]["letter"]), "b")   # 規則：high 先
                self.assertGreaterEqual(self.state()["judge_fails"], 1)
                self.assertTrue(self.state()["judge_error"])

    def test_max_fails_stays_on_rules_until_cleared(self):
        cfg = self.cfg("sys.exit(3)", max_fails=2)
        for _ in range(4):
            self.send("a")
            self.send("b")
            out = K.tick(cfg)
        self.assertEqual(self.calls(), 2)
        self.assertTrue(out["judge"]["on_rules"])
        self.assertIn("rules", [r["how"] for r in self.log("decide")])
        st = self.state()
        st["judge_fails"] = 0                                        # 人把它歸零
        with open(self.p("k.state.json"), "w") as f:
            json.dump(st, f)
        self.send("a")
        self.send("b")
        K.tick(cfg)
        self.assertEqual(self.calls(), 3)

    def test_skip_judge_when_unchanged(self):
        self.send("a")
        self.send("b")
        cfg = self.cfg("print(json.dumps({'defer': q}))")
        K.tick(cfg)
        out = K.tick(cfg)
        self.assertEqual(self.calls(), 1)
        self.assertEqual(out["judge"]["skipped"], 1)
        self.send("c")
        K.tick(cfg)
        self.assertEqual(self.calls(), 2)

    def test_single_letter_with_free_slot_skips_judge(self):
        self.send("a")
        K.tick(self.cfg("sys.exit(1)"))
        self.assertEqual((self.calls(), self.log("decide")[0]["how"]), (0, "direct"))

    def test_reject_reaches_caller_as_n29_error(self):
        cfg = self.cfg("print(json.dumps({'reject': [{'id': x, 'error': {'code': 'TooExpensive', "
                       "'msg': '太貴'}} for x in q]}))", slots={"llm": 0})
        stop = threading.Event()

        def beat():
            while not stop.is_set():
                K.tick(cfg)
                time.sleep(0.02)
        t = threading.Thread(target=beat, daemon=True)
        t.start()
        try:
            p = subprocess.run([sys.executable, GATE, "--target", json.dumps({"argv": ["cat"], "_metainfo": {"resource": "llm"}}),
                                "--mailbox", self.p("mb")], input="hi", capture_output=True, text=True, timeout=10)
        finally:
            stop.set()
            t.join()
        self.assertEqual(p.returncode, 125)
        self.assertEqual(json.loads(p.stderr)["error"], {"code": "TooExpensive", "msg": "太貴"})

    # ---- human 格、遞迴、重起 ----

    def test_human_slot_freed_on_reply(self):
        names = {self.send(x, res="human", sh=WAIT_ANS): x for x in ("h1", "h2")}
        cfg = self.cfg(RULES, slots={"human": 1})
        res = {}
        t = threading.Thread(target=lambda: res.update(K.tick(cfg)))
        t.start()
        self.until(lambda: self.log("start"))
        time.sleep(0.2)
        self.assertEqual(len(self.log("start")), 1)                  # 人還沒回：格佔著，第二封不起
        self.write("ans", "")
        t.join(10)
        self.assertEqual(self.started(names), ["h1", "h2"])
        self.assertEqual(len(res["served"]), 2)

    def test_human_slot_freed_on_timeout(self):
        a = self.send("h1", res="human", sh=WAIT_ANS, timeout_ms=300)
        b = self.send("h2", res="human", sh="cat")
        K.tick(self.cfg(RULES, slots={"human": 1}))
        self.assertTrue(self.reply(a)["timed_out"])
        self.assertEqual(self.stdout(b), "h2")

    def test_judge_env_has_no_own_mailbox(self):
        self.send("a")
        self.send("b")
        body = "open('env', 'w').write(os.environ.get('AOS_KERNEL', '-') + ' ' + os.environ.get('X', '-')); print('{}')"
        cfg = self.cfg(body)
        cfg["judge"]["envs"] = {"X": "1"}
        old = os.environ.get("AOS_KERNEL")
        os.environ["AOS_KERNEL"] = self.p("mb")
        try:
            K.tick(cfg)
            self.assertEqual(self.read("env"), "- 1")
            cfg["judge"]["envs"] = {"AOS_KERNEL": self.p("mb")}    # 自己寫也一樣拿掉
            self.send("c")
            self.send("c2")
            K.tick(cfg)
            self.assertEqual(self.read("env"), "- -")
            cfg["judge"]["envs"] = {"AOS_KERNEL": self.p("other")}  # 別的信箱（例 LLM kernel）照給
            self.send("d")
            self.send("d2")
            K.tick(cfg)
            self.assertEqual(self.read("env"), self.p("other") + " -")
        finally:
            if old is None:
                os.environ.pop("AOS_KERNEL", None)
            else:
                os.environ["AOS_KERNEL"] = old

    def test_restart_cur_letter(self):
        n = self.send("a")
        os.rename(os.path.join(self.box["new"], n), os.path.join(self.box["cur"], n))
        out = K.tick(self.cfg())
        self.assertEqual(self.reply(n)["error"]["code"], "KernelRestarted")
        self.assertEqual(out["dropped"], [{"letter": n, "error": "KernelRestarted"}])

    def test_bad_config(self):
        for bad in ({"slots": {"llm": -1}}, {"slots": "2"}, {"max_fails": 0}, {"judge": 3}):
            with self.subTest(bad=bad):
                with self.assertRaises(K.KernelError):
                    K.check(dict({"mailbox": "m", "state": "s"}, **bad))
        with self.assertRaises(K.KernelError) as e:
            K.check({"mailbox": "m"})
        self.assertEqual(e.exception.code, "WindowMissing")


def procs_in(root):
    """命令列或 cwd 落在 root 底下的行程（不收殭屍）。"""
    root = os.path.realpath(root)
    found = []
    for d in os.listdir("/proc"):
        if not d.isdigit() or int(d) == os.getpid():
            continue
        try:
            cwd = os.readlink("/proc/%s/cwd" % d)
            with open("/proc/%s/cmdline" % d, "rb") as f:
                cmd = f.read().replace(b"\0", b" ").decode(errors="replace")
            with open("/proc/%s/stat" % d) as f:
                if f.read().rsplit(")", 1)[1].split()[0] == "Z":
                    continue
        except OSError:
            continue
        if root in cmd or cwd == root or cwd.startswith(root + os.sep):
            found.append((int(d), cmd))
    return found


class KernelDaemonTest(Tmp):
    def test_daemon_end_to_end_no_leftovers(self):
        mb, kernel = self.p("mb"), os.path.join(LIB, "aos_kernel.py")
        self.write("kernel.json", {"mailbox": mb, "state": self.p("k.state.json"), "slots": {"llm": 1, "human": 1},
                                   "judge": {"argv": [sys.executable, os.path.join(LIB, "judge_rules.py")]}})
        self.write("loop.json", {"inst": {"argv": [sys.executable, kernel, self.p("kernel.json")], "cwd": self.tmp},
                                 "times": None, "interval_ms": 50})
        self.write("daemon.json", {"children": [self.p("loop.json")], "interval_ms": 50,
                                   "ctl": self.p("d.ctl.json"), "state": self.p("d.state.json")})
        d = subprocess.Popen([sys.executable, DAEMON, self.p("daemon.json")], cwd=self.tmp, stdout=subprocess.DEVNULL)
        try:
            env = dict(os.environ, AOS_KERNEL=mb)
            calls = [subprocess.Popen([sys.executable, GATE, "--target", json.dumps(
                {"argv": ["sh", "-c", sh], "cwd": self.tmp, "_metainfo": {"resource": r}})], env=env, cwd=self.tmp,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True) for r, sh in
                (("llm", "sleep 0.2; cat"), ("llm", "cat"), ("human", "sleep 30"))]
            calls[2].stdin.close()
            outs = [p.communicate("q%d" % i, timeout=10)[0] for i, p in enumerate(calls[:2])]
            self.assertEqual(outs, ["q0", "q1"])
            self.until(lambda: os.listdir(os.path.join(mb, "cur")))   # human 那封正在等人
        finally:
            d.send_signal(signal.SIGTERM)
            d.wait(15)
        calls[2].kill()
        calls[2].wait()
        for p in calls:
            p.stdout.close()
        self.until(lambda: not procs_in(self.tmp), timeout=5)


if __name__ == "__main__":
    import unittest
    unittest.main()
