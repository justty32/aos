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
sys.path.insert(0, LIB)

import aos_daemon  # noqa: E402
import aos_inst  # noqa: E402
from aos_directives import DirectiveError, resolve  # noqa: E402
from aos_loop import Loop, LoopError  # noqa: E402


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
    def run_inst(self, name, sh, **kw):
        keys = kw.pop("keys", {})
        aos_inst.run(aos_inst.load(self.inst(name, sh, exit=name + ".exit", **keys)), **kw)
        return self.read(name + ".exit")

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

    def test_returns_code(self):
        self.assertEqual(aos_inst.run(aos_inst.load(self.inst("r", "exit 7"))), 7)
        self.assertEqual(aos_inst.run(aos_inst.load(self.inst("r2", "sleep 5")), timeout_ms=100), 143)

    def test_exit_and_streams(self):
        self.assertEqual(self.run_inst("a", "echo hi; echo err >&2; exit 3",
                                       keys={"stdout": "a.out", "stderr_merge": True}), "3\n")
        self.assertEqual(self.read("a.out"), "hi\nerr\n")

    def test_timeout_and_grace(self):
        self.assertEqual(self.run_inst("t", "sleep 5", timeout_ms=100), "143\n")
        t0 = time.monotonic()
        self.assertEqual(self.run_inst("k", "trap '' TERM; sleep 5", timeout_ms=100, grace_ms=200), "137\n")
        self.assertLess(time.monotonic() - t0, 2)

    def test_stop(self):
        stop = threading.Event()
        threading.Timer(0.1, stop.set).start()
        self.assertEqual(self.run_inst("s", "sleep 5", stop=stop, stop_poll_ms=10), "143\n")

    def test_new_session_clears_grandchildren(self):
        # 子程式起一個背景孫程式、印出 pid 就結束；new_session 開著，孫程式要被清掉
        self.run_inst("g", "sleep 30 & echo $! > g.pid", new_session=True)
        pid = int(self.read("g.pid"))
        self.until(lambda: not alive(pid))

    def test_errors(self):
        for keys, code in (({"argv": []}, "FieldType"), ({"argv": ["/no/such/prog"]}, "CommandNotFound"),
                           ({"argv": ["true"], "stdout": "x", "stdout_inherit": True}, "Conflict"),
                           ({"argv": ["true"], "cwd": "/no/such/dir"}, "CwdMissing")):
            with self.subTest(keys=keys), self.assertRaises(aos_inst.InstError) as c:
                aos_inst.run(aos_inst.parse(keys, self.tmp))
            self.assertEqual(c.exception.code, code)

    def test_cli(self):
        d = self.inst("c", "exit 5", exit="c.exit")
        r = subprocess.run([sys.executable, os.path.join(LIB, "aos_inst.py"), d], capture_output=True)
        self.assertEqual((r.returncode, self.read("c.exit")), (5, "5\n"))
        self.write("x.json", "#!/bin/sh\n")
        self.write("nf.json", {"argv": ["/no/such/prog"]})
        self.write("nx.json", {"argv": [self.p("x.json")]})
        for target, code, err in (("nope.json", 125, "ReadFailed"), ("nf.json", 127, "CommandNotFound"),
                                  ("nx.json", 126, "CommandNotExecutable")):
            r = subprocess.run([sys.executable, os.path.join(LIB, "aos_inst.py"), self.p(target)],
                               capture_output=True, text=True)
            self.assertEqual((r.returncode, r.stderr.split(":")[0]), (code, err))


class LoopTest(Tmp):
    def setUp(self):
        super().setUp()
        self.loop = Loop(stop_poll_ms=10)
        self.addCleanup(self.loop.shutdown)

    def code(self, f, *a):
        with self.assertRaises(LoopError) as c:
            f(*a)
        return c.exception.code

    def test_times_and_add_times(self):
        d = self.inst("a", "echo x >> a.out")
        ident = self.loop.add(d, {"times": 2})
        self.assertEqual(ident, os.path.realpath(d + "/inst.json"))
        self.until(lambda: self.loop.state(d) == "done")
        self.assertEqual(self.read("a.out"), "x\nx\n")
        st = self.loop.add_times(ident, 1)
        self.assertEqual(list(st)[:2], ["id", "state"])
        self.until(lambda: self.loop.get(d)["runs"] == 3 and self.loop.state(d) == "done")

    def test_id_must_be_absolute(self):
        self.inst("a", "true")
        self.assertEqual(self.code(self.loop.add, "a"), "FieldType")
        self.assertEqual(self.code(self.loop.add, os.path.relpath(self.p("a"))), "FieldType")
        self.assertEqual(self.code(self.loop.get, self.p("nope")), "NotFound")
        self.assertEqual(self.code(self.loop.add, self.p("missing.json")), "NotFound")

    def test_errors(self):
        d = self.inst("a", "true")
        self.loop.add(d, {"times": 0})
        self.assertEqual(self.code(self.loop.add, d), "Exists")
        self.assertEqual(self.code(self.loop.set, d, {"bogus": 1}), "FieldType")
        self.assertEqual(self.code(self.loop.set, d, {"timeout_ms": 0}), "FieldType")
        self.loop.set(d, {"times": None})
        self.loop.pause(d)
        self.assertEqual(self.code(self.loop.add_times, d, 1), "Conflict")

    def test_pause_resume(self):
        d = self.inst("a", "sleep 5")
        self.loop.add(d)
        self.until(lambda: self.loop.state(d) == "running")
        ready = self.loop.pause(d, wait=False)
        st = self.until(ready)
        self.assertEqual((st["state"], st["runs"], st["times"]), ("paused", 1, 0))
        self.loop.add_times(d, 1)
        self.assertEqual(self.loop.resume(d)["state"], "waiting")
        self.until(lambda: self.loop.state(d) == "running")

    def test_pause_wait_lets_run_finish(self):
        d = self.inst("a", "sleep 0.3; echo ok > a.out")
        self.loop.add(d, {"times": 3})
        self.until(lambda: self.loop.state(d) == "running")
        ready = self.loop.pause(d, wait=True)
        self.assertIsNone(ready())
        self.assertEqual(self.until(ready)["state"], "paused")
        self.assertEqual(self.read("a.out"), "ok\n")

    def test_remove(self):
        d = self.inst("a", "sleep 5")
        self.loop.add(d)
        self.until(lambda: self.loop.state(d) == "running")
        st = self.until(self.loop.remove(d, wait=False))
        self.assertEqual(st["state"], "removed")
        self.assertEqual(self.code(self.loop.get, d), "NotFound")
        self.loop.add(d, {"times": 0})

    def test_snapshot_restore(self):
        a, b = self.inst("a", "true"), self.inst("b", "true")
        self.loop.add(a, {"times": 0, "interval_ms": 7})
        self.loop.add(b, {"times": 0})
        self.loop.pause(b)
        snap = self.loop.snapshot()
        other = Loop(stop_poll_ms=10)
        self.addCleanup(other.shutdown)
        other.restore(json.loads(json.dumps(snap)))
        self.assertEqual(other.snapshot(), snap)

    def test_restore_all_or_nothing(self):
        a = self.inst("a", "true")
        ident = aos_inst.find(a)
        good = {"id": ident, "how": {"times": 0}, "paused": False, "runs": 0, "last_code": None, "last_error": None}
        missing = dict(good, id=self.p("nope/inst.json"))
        self.assertEqual(self.code(self.loop.restore, [good, missing]), "NotFound")
        self.assertEqual(self.code(self.loop.restore, [good, good]), "Exists")
        self.assertEqual(self.code(self.loop.restore, [good, dict(good, runs=-1)]), "FieldType")
        self.assertEqual(self.code(self.loop.restore, [dict(good, id="a/inst.json")]), "FieldType")
        self.assertEqual(self.loop.list(), [])
        self.loop.restore([good])
        self.assertEqual(self.code(self.loop.restore, [good]), "Exists")

    def test_inst_error_recorded(self):
        d = self.inst("a", "true")
        self.write("a/inst.json", {"argv": ["/no/such/prog"]})
        self.loop.add(d)
        self.until(lambda: self.loop.state(d) == "done")
        st = self.loop.get(d)
        self.assertTrue(st["last_error"].startswith("CommandNotFound"))
        self.assertIsNone(st["last_code"])

    def test_last_code(self):
        d = self.inst("a", "exit 3")
        self.loop.add(d)
        self.until(lambda: self.loop.state(d) == "done")
        self.assertEqual(self.loop.get(d)["last_code"], 3)

    def test_error_wait(self):
        # aos_inst 自己出錯又不限次數：不空轉，隔 error_wait_ms 才再試；remove 不用等它
        d = self.inst("a", "true")
        self.write("a/inst.json", {"argv": ["/no/such/prog"]})
        self.loop.add(d, {"times": None})
        time.sleep(0.3)
        self.assertEqual(self.loop.get(d)["runs"], 1)
        t0 = time.monotonic()
        self.until(self.loop.remove(d))
        self.assertLess(time.monotonic() - t0, 0.5)
        fast = Loop(stop_poll_ms=10, error_wait_ms=100)
        self.addCleanup(fast.shutdown)
        fast.add(d, {"times": None})
        time.sleep(0.35)
        self.assertIn(fast.get(d)["runs"], (3, 4, 5))


class Daemon(Tmp):
    def start(self, **cfg):
        self.ctl = self.p("ctl")
        self.write("daemon.json", dict({"control_dir": self.ctl, "control_poll_ms": 20, "stop_poll_ms": 10}, **cfg))
        self.d = subprocess.Popen([sys.executable, os.path.join(LIB, "aos_daemon.py"), self.p("daemon.json")],
                                  cwd=self.tmp, stderr=subprocess.PIPE, text=True)
        self.addCleanup(self.stop, signal.SIGKILL)
        self.n = 0

    def stop(self, sig=signal.SIGTERM):
        if self.d.poll() is None:
            self.d.send_signal(sig)
        code = self.d.wait(10)
        self.d.stderr.close()
        return code

    def put(self, cmd):
        self.n += 1
        name = "%03d.json" % self.n
        self.until(lambda: os.path.isdir(self.ctl))
        self.write("ctl/." + name, cmd)
        os.replace(self.p("ctl/." + name), self.p("ctl", name))
        return self.p("ctl", name + ".done")

    def get(self, done):
        self.until(lambda: os.path.exists(done))
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
        d = self.inst("a", "true")
        ident = self.ok({"op": "add", "id": d, "how": {"times": 0}})
        self.assertEqual(self.ok({"op": "state", "id": ident}), "done")
        self.assertEqual(self.ok({"op": "set", "id": d, "how": {"interval_ms": 5}})["interval_ms"], 5)
        self.assertEqual([s["id"] for s in self.ok({"op": "list"})], [ident])
        self.assertEqual(self.err({"op": "add", "id": "a"}), "FieldType")
        self.assertEqual(self.err({"op": "jump"}), "UnknownOp")
        self.assertEqual(self.err({"op": "add_times", "id": d, "delta": "x"}), "FieldType")
        self.assertEqual(self.err({"op": "save", "path": self.p("no/such/dir/x.json")}), "WriteFailed")
        self.assertEqual(self.err({"op": "load", "path": self.p("nope.json")}), "ReadFailed")
        self.write("ctl/bad.json", "{")
        r = self.get(self.p("ctl/bad.json.done"))
        self.assertEqual((r["request"], r["error"]["code"]), ("{", "BadCommand"))
        self.assertEqual(self.stop(), 0)

    def test_pause_remove_reply_after_stop(self):
        self.start()
        d = self.inst("a", "trap '' TERM; sleep 5")
        self.ok({"op": "add", "id": d, "how": {"grace_ms": 400}})
        self.until(lambda: self.ok({"op": "state", "id": d}) == "running")
        t0 = time.monotonic()
        done = self.put({"op": "remove", "id": d, "wait": False})
        time.sleep(0.2)
        self.assertFalse(os.path.exists(done))
        self.assertEqual(self.get(done)["result"]["state"], "removed")
        self.assertGreater(time.monotonic() - t0, 0.35)
        self.ok({"op": "add", "id": d, "how": {"times": 0}})

    def test_save_load(self):
        self.start()
        a, b = self.inst("a", "true"), self.inst("b", "true")
        self.ok({"op": "add", "id": a, "how": {"times": 0}})
        self.ok({"op": "add", "id": b, "how": {"times": 0, "interval_ms": 9}})
        self.assertEqual(self.ok({"op": "save", "path": self.p("t.json")}), 2)
        self.assertEqual(self.err({"op": "load", "path": self.p("t.json")}), "Exists")
        self.ok({"op": "remove", "id": a})
        self.assertEqual(self.err({"op": "load", "path": self.p("t.json")}), "Exists")
        self.assertEqual(len(self.ok({"op": "list"})), 1)
        self.ok({"op": "remove", "id": b})
        self.assertEqual(len(self.ok({"op": "load", "path": self.p("t.json")})), 2)

    def test_config_load_save(self):
        a = self.inst("a", "true")
        self.write("t.json", [{"id": aos_inst.find(a), "how": {"times": 0}, "paused": True, "runs": 4,
                               "last_code": None, "last_error": None}])
        self.start(load=self.p("t.json"), save=self.p("t.json"))
        self.assertEqual(self.ok({"op": "get", "id": a})["runs"], 4)
        self.ok({"op": "add_times", "id": a, "delta": 2})
        self.assertEqual(self.stop(signal.SIGTERM), 0)
        self.assertEqual(json.loads(self.read("t.json"))[0]["how"]["times"], 2)

    def test_sigint_does_not_save(self):
        self.start(save=self.p("t.json"))
        self.ok({"op": "list"})
        self.assertEqual(self.stop(signal.SIGINT), 0)
        self.assertFalse(os.path.exists(self.p("t.json")))

    def test_bad_load_fails_start(self):
        self.write("t.json", [{"id": self.p("nope/inst.json"), "how": {}, "paused": False, "runs": 0,
                               "last_code": None, "last_error": None}])
        self.start(load=self.p("t.json"))
        self.assertEqual(self.d.wait(10), 1)
        self.assertTrue(self.d.stderr.read().startswith("NotFound"))

    def test_bad_config(self):
        self.write("c.json", {"control_poll_ms": 10})
        with self.assertRaises(aos_daemon.DaemonError) as c:
            aos_daemon.load_config(self.p("c.json"))
        self.assertEqual(c.exception.code, "FieldType")


if __name__ == "__main__":
    unittest.main()
