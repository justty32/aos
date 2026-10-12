"""proto8/lib 的自動測試。只用標準庫：

    python3 -m unittest discover -s proto8/lib/tests

每個測試在 mktemp 建的暫存資料夾裡跑，跑完刪掉。daemon 的測試起真的 daemon 行程、走控制資料夾。
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest

LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INST = os.path.join(LIB, "aos_inst.py")
LOOP = os.path.join(LIB, "aos_loop.py")
DAEMON = os.path.join(LIB, "aos_daemon.py")
sys.path.insert(0, LIB)

import aos_daemon  # noqa: E402
import aos_inst  # noqa: E402
from aos_directives import DirectiveError, resolve  # noqa: E402
import aos_loop  # noqa: E402


class Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="aos-test-")
        self.addCleanup(shutil.rmtree, self.tmp)

    def p(self, *parts):
        return os.path.join(self.tmp, *parts)

    def write(self, name, doc):
        path = self.p(name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(doc if isinstance(doc, str) else json.dumps(doc))
        return path

    def read(self, name):
        with open(self.p(name)) as f:
            return f.read()

    def inst(self, name, sh, **keys):
        """寫 NAME/inst.json：在暫存資料夾裡用 sh 跑 SH。回資料夾的絕對路徑。"""
        self.write(name + "/inst.json", dict({"argv": ["sh", "-c", sh], "cwd": self.tmp}, **keys))
        return self.p(name)

    def until(self, cond, timeout=5):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            v = cond()
            if v:
                return v
            time.sleep(0.02)
        self.fail("等不到")


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


class Directives(Tmp):
    def code(self, doc):
        with self.assertRaises(DirectiveError) as c:
            resolve(doc, self.tmp)
        return c.exception.code

    def test_ref_env_at(self):
        self.write("a.json", {"x": [1, {"y": "z"}]})
        os.environ["AOS_TEST_V"] = "v"
        doc = {"f": {"$ref": "a.json#/x/1/y"}, "g": {"$ref": "a.json", "$at": "/x/0"},
               "h": {"$env": "AOS_TEST_V"}, "i": {"$ref": "#/g"}, "j": {"k": {"$ref": "#../../h"}}}
        self.assertEqual(resolve(doc, self.tmp), {"f": "z", "g": 1, "h": "v", "i": 1, "j": {"k": "v"}})
        self.assertIn("$ref", doc["f"])

    def test_errors(self):
        self.write("bad.json", "{")
        self.assertEqual(self.code({"$nope": 1}), "UnknownDirective")
        self.assertEqual(self.code({"$env": 1}), "DirectiveValueTypeMismatch")
        self.assertEqual(self.code({"$env": "AOS_TEST_NO_SUCH_VAR"}), "EnvironmentVariableMissing")
        self.assertEqual(self.code({"$ref": "missing.json"}), "ReferenceReadFailed")
        self.assertEqual(self.code({"$ref": "bad.json"}), "ReferenceJsonInvalid")
        self.assertEqual(self.code({"a": 1, "b": {"$ref": "#/c"}}), "ReferencePointerInvalid")
        self.assertEqual(self.code({"a": {"$ref": "#/a"}}), "ReferenceCycle")
        self.assertEqual(self.code({"a": {"b": {"$ref": "#/a"}}}), "ReferenceCycle")


class Inst(Tmp):
    def run_inst(self, name, sh, **keys):
        """寫 NAME/inst.json、run() 一次，回 exit 檔的內容。"""
        self.assertIsNone(aos_inst.run(self.inst(name, sh, exit=name + ".exit", **keys)))
        return self.read(name + ".exit")

    def cli(self, target):
        return subprocess.run([sys.executable, INST, target], capture_output=True, text=True, cwd=self.tmp)

    def test_find(self):
        d = self.inst("a", "true")
        self.assertEqual(aos_inst.find(d), os.path.realpath(d + "/inst.json"))
        self.write("b/.aos/inst.json", {"argv": ["true"]})
        self.write("b/inst.json", {"argv": ["true"]})
        self.assertEqual(aos_inst.find(self.p("b")), os.path.realpath(self.p("b/.aos/inst.json")))
        os.makedirs(self.p("empty"))
        with self.assertRaises(aos_inst.InstError) as c:
            aos_inst.find(self.p("empty"))
        self.assertEqual(c.exception.code, "NotFound")

    def test_child_code_only_in_exit_file(self):
        self.assertEqual(self.run_inst("r", "exit 7"), "7\n")
        self.assertIsNone(aos_inst.run(self.inst("n", "exit 7")))      # 沒寫 exit：沒人記，run() 照樣正常

    def test_exit_and_streams(self):
        self.assertEqual(self.run_inst("a", "echo hi; echo err >&2; exit 3", stdout="a.out", stderr_merge=True), "3\n")
        self.assertEqual(self.read("a.out"), "hi\nerr\n")

    def test_exit_append_and_read_exit(self):
        for sh in ("exit 1", "exit 2"):
            self.run_inst("a", sh, exit_append=True)
        self.assertEqual(self.read("a.exit"), "1\n2\n")
        self.assertEqual(aos_inst.read_exit(self.p("a.exit")), 2)
        self.assertIsNone(aos_inst.read_exit(self.p("nope.exit")))

    def test_timeout_and_grace_in_json(self):
        self.assertEqual(self.run_inst("t", "sleep 5", timeout_ms=100), "143\n")
        t0 = time.monotonic()
        self.assertEqual(self.run_inst("k", "trap '' TERM; sleep 5", timeout_ms=100, grace_ms=200), "137\n")
        self.assertLess(time.monotonic() - t0, 2)

    def test_timeout_grace_types(self):
        for keys in ({"timeout_ms": 0}, {"timeout_ms": "5s"}, {"grace_ms": -1}, {"grace_ms": True}):
            with self.subTest(keys=keys), self.assertRaises(aos_inst.InstError) as c:
                aos_inst.parse(dict({"argv": ["true"]}, **keys), self.tmp)
            self.assertEqual(c.exception.code, "FieldType")

    def test_errors(self):
        for keys, code in (({"argv": []}, "FieldType"), ({"argv": ["/no/such/prog"]}, "CommandNotFound"),
                           ({"argv": ["true"], "stdout": "x", "stdout_inherit": True}, "Conflict"),
                           ({"argv": ["true"], "cwd": "/no/such/dir"}, "CwdMissing")):
            with self.subTest(keys=keys), self.assertRaises(aos_inst.InstError) as c:
                aos_inst.run(self.write("e.json", keys))
            self.assertEqual(c.exception.code, code)

    def test_error_names_file(self):
        self.write("e.json", {"argv": ["x", {"$env": "AOS_TEST_NOPE"}]})
        with self.assertRaises(aos_inst.InstError) as c:
            aos_inst.load(self.p("e.json"))
        self.assertIn(os.path.realpath(self.p("e.json")) + ":/argv/1", c.exception.msg)

    def test_cli(self):
        # 退出碼只說 aos_inst 自己：子程式回 5 照樣 0，5 在 exit 檔
        d = self.inst("c", "exit 5", exit="c.exit")
        self.assertEqual((self.cli(d).returncode, self.read("c.exit")), (0, "5\n"))
        self.write("x.json", "#!/bin/sh\n")
        self.write("nf.json", {"argv": ["/no/such/prog"]})
        self.write("nx.json", {"argv": [self.p("x.json")]})
        for target, code, err in (("nope.json", 125, "ReadFailed"), ("nf.json", 127, "CommandNotFound"),
                                  ("nx.json", 126, "CommandNotExecutable")):
            r = self.cli(self.p(target))
            self.assertEqual((r.returncode, r.stderr.split(":")[0]), (code, err))

    def test_cli_forwards_signal_then_grace(self):
        # 收到 SIGTERM 轉給子程式；子程式不理就過 grace_ms SIGKILL；aos_inst 自己照樣 0
        d = self.inst("s", "trap '' TERM; echo go > s.go; sleep 30", exit="s.exit", grace_ms=200)
        proc = subprocess.Popen([sys.executable, INST, d], cwd=self.tmp)
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        self.until(lambda: os.path.exists(self.p("s.go")))
        t0 = time.monotonic()
        proc.send_signal(signal.SIGTERM)
        self.assertEqual(proc.wait(5), 0)
        self.assertLess(time.monotonic() - t0, 2)
        self.assertEqual(self.read("s.exit"), "137\n")


class LoopTest(Tmp):
    def loop(self, name="l", sh="true", **outer):
        """寫 NAME.loop.json（inst 內嵌：在暫存資料夾用 sh 跑 SH、exit 附加到 NAME.exit），回路徑。"""
        inst = outer.pop("inst", {"argv": ["sh", "-c", sh], "cwd": self.tmp, "exit": name + ".exit", "exit_append": True})
        return self.write(name + ".loop.json", dict({"inst": inst, "ctl_poll_ms": 20}, **outer))

    def cli(self, path, timeout=10):
        return subprocess.run([sys.executable, LOOP, path], capture_output=True, text=True, cwd=self.tmp, timeout=timeout)

    def start(self, path):
        proc = subprocess.Popen([sys.executable, LOOP, path], cwd=self.tmp, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: proc.poll() is None and proc.kill() or proc.stderr.close())
        return proc

    def state(self, name="l.state.json"):
        try:
            return json.loads(self.read(name))
        except (OSError, ValueError):
            return None

    def ctl(self, doc, name="l.ctl.json"):
        self.write("." + name, doc)
        os.replace(self.p("." + name), self.p(name))

    def test_times_and_last_code(self):
        path = self.loop(sh="echo x >> l.out; exit 3", times=3, state="l.state.json")
        r = self.cli(path)
        self.assertEqual(r.returncode, 0, r.stderr)     # 子程式回 3 不算 loop 出錯
        self.assertEqual((self.read("l.out"), self.read("l.exit")), ("x\nx\nx\n", "3\n3\n3\n"))
        st = self.state()
        self.assertEqual((st["id"], st["state"], st["runs"], st["last_code"]),
                         (os.path.realpath(path), "done", 3, 3))
        self.assertEqual(list(st)[:2], ["id", "state"])

    def test_run_api_and_ref(self):
        self.inst("job", "echo y >> j.out")
        path = self.loop(inst={"$ref": "job/inst.json"}, times=2)
        cwd = os.getcwd()
        os.chdir(self.tmp)                  # 相對路徑從呼叫者的 cwd 算
        self.addCleanup(os.chdir, cwd)
        self.assertIsNone(aos_loop.run(path))
        self.assertEqual(self.read("j.out"), "y\ny\n")

    def test_read_once_at_start(self):
        # loop.json（含 inst）只在起來時解一次：跑到一半改檔不影響；要改只能走 ctl.json
        self.inst("job", "echo a >> j.out")
        path = self.loop(inst={"$ref": "job/inst.json"}, times=None, interval_ms=50, ctl="l.ctl.json")
        self.ctl({})
        proc = self.start(path)
        self.until(lambda: os.path.exists(self.p("j.out")))
        self.inst("job2", "echo b >> j.out")
        os.replace(self.p("job2/inst.json"), self.p("job/inst.json"))
        self.write("l.loop.json", {"inst": {"argv": ["false"]}})
        time.sleep(0.3)
        self.ctl({"stop": True})
        self.assertEqual(proc.wait(5), 0)
        self.assertEqual(set(self.read("j.out").split()), {"a"})

    def test_bad_inst_fails_start(self):
        r = self.cli(self.loop(inst={"argv": [{"$env": "AOS_TEST_NOPE"}]}))
        self.assertEqual(r.returncode, 125)
        self.assertIn("EnvironmentVariableMissing", r.stderr)
        self.assertEqual(self.cli(self.loop(inst={"argv": []})).returncode, 125)

    def test_no_exit_last_code_null(self):
        self.loop(inst={"argv": ["true"]}, state="l.state.json")
        self.assertEqual(self.cli(self.p("l.loop.json")).returncode, 0)
        self.assertIsNone(self.state()["last_code"])

    def test_inst_error_inherited(self):
        path = self.loop(inst={"argv": ["/no/such/prog"]}, times=2, error_wait_ms=50, state="l.state.json")
        r = self.cli(path)
        self.assertEqual(r.returncode, 127)
        self.assertIn("CommandNotFound", r.stderr)
        self.assertTrue(self.state()["last_error"].startswith("CommandNotFound"))
        # 中途出錯後來好了不算：最後一次正常＝0
        self.write("ok.exit", "")
        self.loop("m", inst={"argv": ["sh", "-c", "[ -e flag ] || { touch flag; exec /no/such; }"], "cwd": self.tmp},
                  times=2, error_wait_ms=10)
        self.assertEqual(self.cli(self.p("m.loop.json")).returncode, 0)

    def test_bad_loop_json(self):
        for doc in ({"times": 1}, {"inst": {"argv": ["true"]}, "times": -1},
                    {"inst": {}, "interval_mode": "x"}, "{"):
            with self.subTest(doc=doc):
                r = self.cli(self.write("bad.json", doc))
                self.assertEqual(r.returncode, 125)
        self.assertEqual(self.cli(self.p("nope.json")).returncode, 125)

    def test_want_reverts_to_initial(self):
        init = {"paused": (False, False), "times": 3}
        self.assertEqual(aos_loop.want(init, {"times": 5})["times"], 5)
        self.assertEqual(aos_loop.want(init, {})["times"], 3)
        self.assertEqual(aos_loop.parse_ctl({"stop": True, "paused": {"val": True, "now": True}, "x": 1}),
                         {"stop": (True, False), "paused": (True, True)})
        for bad in ([], {"stop": "yes"}, {"paused": {"now": True}}, {"times": "5"}, {"interval_mode": "x"}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                aos_loop.parse_ctl(bad)

    def test_ctl_pause_resume_times_stop(self):
        self.ctl({"paused": True})
        path = self.loop(sh="echo x >> l.out", times=None, interval_ms=20, ctl="l.ctl.json", state="l.state.json")
        proc = self.start(path)
        self.until(lambda: (self.state() or {}).get("state") == "paused")
        time.sleep(0.2)
        self.assertFalse(os.path.exists(self.p("l.out")))
        self.ctl({"times": 2})                          # paused 沒寫＝回到初始值（false）
        self.until(lambda: (self.state() or {}).get("state") == "done")
        self.assertEqual(self.read("l.out"), "x\nx\n")
        self.ctl({"times": 3})                          # done 不是終點，改大再跑
        self.until(lambda: (self.state() or {}).get("runs") == 3)
        st = self.state()
        self.assertEqual(st["ctl_mtime"], os.stat(self.p("l.ctl.json")).st_mtime)
        self.ctl({"times": 3, "stop": True})
        self.assertEqual(proc.wait(5), 0)
        self.assertEqual(self.state()["state"], "stopped")

    def test_ctl_now_kills_current(self):
        self.ctl({})
        path = self.loop(sh="echo $$ > l.pid; exec sleep 30", times=None, ctl="l.ctl.json", state="l.state.json")
        proc = self.start(path)
        self.until(lambda: os.path.exists(self.p("l.pid")))
        self.ctl({"paused": {"val": True, "now": True}})
        self.until(lambda: (self.state() or {}).get("state") == "paused")
        self.assertEqual(self.read("l.exit"), "143\n")
        self.ctl({"stop": {"val": True, "now": False}})
        self.assertEqual(proc.wait(5), 0)

    def test_stop_now_and_bad_ctl(self):
        self.ctl({})
        path = self.loop(sh="echo $$ > l.pid; exec sleep 30", times=None, ctl="l.ctl.json")
        proc = self.start(path)
        self.until(lambda: os.path.exists(self.p("l.pid")))
        self.ctl("{")                                   # 壞檔：整份不採用、印一次、照跑
        time.sleep(0.15)
        os.remove(self.p("l.ctl.json"))                 # 不見了：維持上一次
        time.sleep(0.2)
        self.assertIsNone(proc.poll())
        self.ctl({"stop": {"val": True, "now": True}})
        self.assertEqual(proc.wait(5), 0)
        err = proc.stderr.read()
        self.assertEqual((err.count("CtlBad"), err.count("CtlMissing")), (1, 1), err)

    def test_sigterm_clears_group(self):
        path = self.loop(sh="sleep 30 & echo $! > l.pid; wait", times=None, grace_ms=300)
        proc = self.start(path)
        self.until(lambda: os.path.exists(self.p("l.pid")) and self.read("l.pid").strip())
        pid = int(self.read("l.pid"))
        proc.send_signal(signal.SIGTERM)
        self.assertEqual(proc.wait(5), 128 + signal.SIGTERM)
        self.until(lambda: not alive(pid))

    def test_grandchildren_cleared_after_run(self):
        self.cli(self.loop(sh="sleep 30 & echo $! > l.pid"))
        pid = int(self.read("l.pid"))
        self.until(lambda: not alive(pid))

    def test_fixed_skips_missed_ticks(self):
        path = self.loop(sh="sleep 0.25", times=3, interval_ms=100, interval_mode="fixed", state="l.state.json")
        t0 = time.monotonic()
        self.assertEqual(self.cli(path).returncode, 0)
        st = self.state()
        self.assertGreaterEqual(st["skipped"], 4)       # 每次 0.25 秒、週期 0.1 秒：每次跳過兩拍
        self.assertLess(time.monotonic() - t0, 2)

    def test_error_wait(self):
        path = self.loop(inst={"argv": ["/no/such/prog"]}, times=None, error_wait_ms=100, state="l.state.json")
        proc = self.start(path)
        time.sleep(0.45)
        proc.send_signal(signal.SIGINT)
        self.assertEqual(proc.wait(5), 128 + signal.SIGINT)
        self.assertIn(self.state()["runs"], (3, 4, 5, 6))


class Daemon(Tmp):
    def start(self, **cfg):
        self.ctl = self.p("ctl")
        self.write("daemon.json", dict({"control_dir": self.ctl, "interval_ms": 20, "ctl_poll_ms": 20,
                                        "grace_ms": 3000}, **cfg))
        self.d = subprocess.Popen([sys.executable, DAEMON, self.p("daemon.json")],
                                  cwd=self.tmp, stderr=subprocess.PIPE, text=True)
        self.addCleanup(self.stop, signal.SIGKILL)
        self.n = 0

    def stop(self, sig=signal.SIGTERM):
        if self.d.poll() is None:
            self.d.send_signal(sig)
        code = self.d.wait(10)
        self.d.stderr.close()
        return code

    def loop(self, name, sh="true", **outer):
        """寫 NAME.loop.json（inst 內嵌，loop 的 ctl_poll_ms 20），回絕對路徑。"""
        inst = {"argv": ["sh", "-c", sh], "cwd": self.tmp, "exit": name + ".exit", "exit_append": True}
        return self.write(name + ".loop.json", dict({"inst": inst, "ctl_poll_ms": 20}, **outer))

    def put(self, cmd):
        self.n += 1
        name = "%03d.json" % self.n
        self.until(lambda: os.path.isdir(self.ctl))
        self.write("ctl/." + name, cmd)
        os.replace(self.p("ctl/." + name), self.p("ctl", name))
        return self.p("ctl", name + ".done")

    def get(self, done, timeout=5):
        self.until(lambda: os.path.exists(done), timeout)
        with open(done) as f:
            reply = json.load(f)
        os.remove(done)
        return reply

    def send(self, cmd):
        return self.get(self.put(cmd))

    def ok(self, cmd):
        r = self.send(cmd)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["request"], cmd)
        return r["result"]

    def err(self, cmd):
        r = self.send(cmd)
        self.assertFalse(r["ok"], r)
        return r["error"]["code"]

    def test_commands(self):
        self.start()
        a = self.loop("a", times=0)
        ident = self.ok({"op": "add", "id": a})
        self.assertEqual(ident, os.path.realpath(a))
        self.until(lambda: self.ok({"op": "state", "id": a}) == "done")
        st = self.ok({"op": "set", "id": a, "how": {"interval_ms": 5}})
        self.assertEqual((list(st)[:2], st["interval_ms"]), (["id", "state"], 5))
        self.assertEqual([s["id"] for s in self.ok({"op": "list"})], [ident])
        self.assertEqual(self.err({"op": "add", "id": a}), "Exists")
        self.assertEqual(self.err({"op": "add", "id": "a.loop.json"}), "FieldType")
        self.assertEqual(self.err({"op": "add", "id": self.p("nope.json")}), "NotFound")
        self.assertEqual(self.err({"op": "set", "id": a, "how": {"timeout_ms": 5}}), "FieldType")
        self.assertEqual(self.err({"op": "jump"}), "UnknownOp")
        self.assertEqual(self.err({"op": "add_times", "id": a, "delta": "x"}), "FieldType")
        self.assertEqual(self.err({"op": "save", "path": self.p("no/such/dir/x.json")}), "WriteFailed")
        self.assertEqual(self.err({"op": "load", "path": self.p("nope.json")}), "ReadFailed")
        self.write("ctl/bad.json", "{")
        r = self.get(self.p("ctl/bad.json.done"))
        self.assertEqual((r["request"], r["error"]["code"]), ("{", "BadCommand"))
        self.assertEqual(self.stop(), 0)
        self.assertEqual(os.listdir(self.p("loops")), [])          # 包裝檔收工時刪掉

    def test_add_times_and_wrapper(self):
        self.start()
        a = self.loop("a", "echo x >> a.out", times=1)
        self.ok({"op": "add", "id": a})
        self.until(lambda: self.ok({"op": "get", "id": a}).get("runs") == 1)
        self.assertEqual(self.ok({"op": "add_times", "id": a, "delta": 2})["times"], 3)
        self.until(lambda: self.ok({"op": "get", "id": a}).get("state") == "done" and self.read("a.out") == "x\n" * 3)
        self.assertEqual(json.loads(self.read("loops/1/ctl.json")), {"times": 3})
        self.ok({"op": "set", "id": a, "how": {"times": None}})
        self.assertEqual(self.err({"op": "add_times", "id": a, "delta": 1}), "Conflict")

    def test_add_inst_json_runs_once(self):
        self.start()
        d = self.inst("a", "echo x >> a.out", exit="a.exit")
        ident = self.ok({"op": "add", "id": d + "/inst.json"})
        self.assertEqual(ident, os.path.realpath(d + "/inst.json"))
        self.until(lambda: self.ok({"op": "get", "id": ident}).get("state") == "done")
        st = self.ok({"op": "add_times", "id": ident, "delta": 1})
        self.assertEqual(st["times"], 2)
        self.until(lambda: self.ok({"op": "get", "id": ident}).get("runs") == 2)
        self.assertEqual(self.read("a.out"), "x\nx\n")
        self.write("bad.json", {"argv": []})
        self.assertEqual(self.err({"op": "add", "id": self.p("bad.json")}), "FieldType")

    def test_own_ctl_state_used(self):
        self.start()
        a = self.loop("a", times=0, ctl="a.ctl.json", state="a.state.json")
        self.ok({"op": "add", "id": a})
        self.ok({"op": "pause", "id": a})
        self.assertEqual(json.loads(self.read("a.ctl.json")), {"paused": {"val": True, "now": False}})
        self.assertEqual(json.loads(self.read("a.state.json"))["state"], "paused")
        self.assertFalse(os.path.exists(self.p("loops")))

    def test_pause_now_and_remove_wait(self):
        self.start()
        a = self.loop("a", "echo $$ > a.pid; exec sleep 30", times=None)
        self.ok({"op": "add", "id": a})
        self.until(lambda: os.path.exists(self.p("a.pid")))
        st = self.ok({"op": "pause", "id": a, "wait": False})
        self.assertEqual(st["state"], "paused")
        self.assertEqual(self.read("a.exit"), "143\n")
        st = self.ok({"op": "resume", "id": a})
        self.until(lambda: self.ok({"op": "state", "id": a}) == "running")
        # remove 等這次跑完：指令檔留在原地，跑完才回
        b = self.loop("b", "sleep 0.4", times=None)
        self.ok({"op": "add", "id": b})
        self.until(lambda: self.ok({"op": "state", "id": b}) == "running")
        done = self.put({"op": "remove", "id": b})
        time.sleep(0.15)
        self.assertFalse(os.path.exists(done))
        self.assertEqual(self.get(done)["result"]["state"], "stopped")
        self.assertEqual(self.err({"op": "get", "id": b}), "NotFound")
        self.ok({"op": "add", "id": b})

    def test_save_load(self):
        self.start()
        a, b = self.loop("a", times=0), self.loop("b", times=0, interval_ms=9)
        self.ok({"op": "add", "id": a})
        self.ok({"op": "add", "id": b})
        self.ok({"op": "pause", "id": b})
        self.assertEqual(self.ok({"op": "save", "path": self.p("t.json")}), 2)
        saved = json.loads(self.read("t.json"))
        self.assertEqual(saved, [{"loop": os.path.realpath(a), "ctl": {}},
                                 {"loop": os.path.realpath(b), "ctl": {"paused": {"val": True, "now": False}}}])
        self.assertEqual(self.err({"op": "load", "path": self.p("t.json")}), "Exists")
        self.ok({"op": "remove", "id": a})
        self.assertEqual(self.err({"op": "load", "path": self.p("t.json")}), "Exists")
        self.assertEqual(len(self.ok({"op": "list"})), 1)
        self.ok({"op": "remove", "id": b})
        self.assertEqual(len(self.ok({"op": "load", "path": self.p("t.json")})), 2)
        self.until(lambda: self.ok({"op": "state", "id": b}) == "paused")

    def test_load_rejects_live_pid(self):
        a = self.loop("a", times=0, state="a.state.json")
        self.write("a.state.json", {"pid": os.getpid()})
        self.write("t.json", [{"loop": os.path.realpath(a), "ctl": {}}])
        self.start(load=self.p("t.json"))
        self.assertEqual(self.d.wait(10), 1)
        self.assertTrue(self.d.stderr.read().startswith("Exists"))

    def test_sigterm_saves_and_clears_loops(self):
        a = self.loop("a", "echo $$ > a.pid; exec sleep 30", times=None)
        self.write("t.json", [{"loop": os.path.realpath(a), "ctl": {"times": None}}])
        self.start(load=self.p("t.json"), save=self.p("t.json"))
        self.until(lambda: os.path.exists(self.p("a.pid")))
        pid = int(self.read("a.pid"))
        self.assertEqual(self.stop(signal.SIGTERM), 0)
        self.assertFalse(alive(pid))
        self.assertEqual(json.loads(self.read("t.json")), [{"loop": os.path.realpath(a), "ctl": {"times": None}}])

    def test_sigint_does_not_save(self):
        self.start(save=self.p("t.json"))
        self.ok({"op": "list"})
        self.assertEqual(self.stop(signal.SIGINT), 0)
        self.assertFalse(os.path.exists(self.p("t.json")))

    def test_own_ctl_pause_and_stop(self):
        self.write("d.ctl.json", {"paused": True})
        self.start(ctl=self.p("d.ctl.json"), state=self.p("d.state.json"), save=self.p("t.json"))
        self.until(lambda: os.path.exists(self.p("d.state.json")))
        done = self.put({"op": "list"})
        time.sleep(0.2)
        self.assertFalse(os.path.exists(done))         # 暫停＝不掃，指令堆著
        self.write("d.ctl.json", {})
        self.get(done)
        self.write("d.ctl.json", {"stop": True})
        self.assertEqual(self.d.wait(10), 0)
        self.assertEqual(json.loads(self.read("t.json")), [])
        self.assertEqual(json.loads(self.read("d.state.json"))["state"], "stopped")

    def test_times_one_shot(self):
        os.makedirs(self.p("ctl"))
        self.write("ctl/001.json", {"op": "list"})
        self.start(times=1)
        self.assertEqual(self.d.wait(10), 0)
        self.assertTrue(json.loads(self.read("ctl/001.json.done"))["ok"])

    def test_bad_config(self):
        for doc in ({"interval_ms": 10}, {"control_dir": "c", "ctl": "c/x.json"}):
            self.write("c.json", doc)
            with self.subTest(doc=doc), self.assertRaises(aos_daemon.DaemonError):
                aos_daemon.load_config(self.p("c.json"))


if __name__ == "__main__":
    unittest.main()
