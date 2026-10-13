"""proto8/lib 的自動測試：daemon（aos_daemon）；起真的 daemon 行程、走控制資料夾。只用標準庫：

    python3 -m unittest discover -s proto8/lib/tests

共用的 `Tmp`、路徑在 helpers.py。
"""
import json
import os
import signal
import subprocess
import sys
import time
import unittest

from helpers import DAEMON, Tmp, alive
import aos_daemon  # noqa: E402
import aos_loop  # noqa: E402


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
        a = self.loop("a", times=None, interval_ms=100000)
        ident = self.ok({"op": "add", "id": a})
        self.assertEqual(ident, os.path.realpath(a))
        self.until(lambda: self.ok({"op": "get", "id": a}).get("runs") == 1)
        self.assertEqual(self.ok({"op": "state", "id": a}), "waiting")
        st = self.ok({"op": "set", "id": a, "how": {"interval_ms": 50000}})
        self.assertEqual((list(st)[:2], st["interval_ms"]), (["id", "state"], 50000))
        z = self.loop("z", times=0)                     # 次數跑完的 loop 自己退出，留在表上、state done
        self.ok({"op": "add", "id": z})
        self.until(lambda: self.ok({"op": "state", "id": z}) == "done")
        self.ok({"op": "remove", "id": z})
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
        a = self.loop("a", "sleep 0.3; echo x >> a.out", times=1)
        self.ok({"op": "add", "id": a})
        self.until(lambda: self.ok({"op": "state", "id": a}) == "running")
        self.assertEqual(self.ok({"op": "add_times", "id": a, "delta": 2})["times"], 3)    # 跑完之前加
        self.until(lambda: self.ok({"op": "get", "id": a}).get("state") == "done" and self.read("a.out") == "x\n" * 3)
        self.assertEqual(json.loads(self.read("loops/1/ctl.json")), {"times": 3})
        self.ok({"op": "set", "id": a, "how": {"times": None}})
        self.assertEqual(self.err({"op": "add_times", "id": a, "delta": 1}), "Conflict")

    def test_add_inst_json_runs_once(self):
        self.start()
        d = self.inst("a", "sleep 1.5; echo x >> a.out", exit="a.exit")   # 包裝檔的 ctl_poll_ms 是預設 1000
        ident = self.ok({"op": "add", "id": d + "/inst.json"})
        self.assertEqual(ident, os.path.realpath(d + "/inst.json"))
        self.until(lambda: self.ok({"op": "state", "id": ident}) == "running")
        self.assertEqual(self.ok({"op": "add_times", "id": ident, "delta": 1})["times"], 2)
        self.until(lambda: self.ok({"op": "get", "id": ident}).get("state") == "done", 10)
        self.assertEqual((self.read("a.out"), self.read("a.exit")), ("x\nx\n", "0\n"))
        self.write("bad.json", {"argv": []})
        self.assertEqual(self.err({"op": "add", "id": self.p("bad.json")}), "FieldType")

    def test_own_ctl_state_used(self):
        self.start()
        a = self.loop("a", times=None, interval_ms=100000, ctl="a.ctl.json", state="a.state.json")
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
        a, b = self.loop("a", times=None, interval_ms=100000), self.loop("b", times=None, interval_ms=100000)
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

    def test_target_pointer(self):
        # 一份檔放好幾格：同一份檔兩個位置＝兩個 loop；inst 那格包成只跑一次；save／load 帶著 #/位置
        self.start()
        path = self.write("node.json", {
            "a": {"inst": {"argv": ["sh", "-c", "echo a >> a.out"], "cwd": self.tmp}, "times": None,
                  "interval_ms": 100000, "ctl_poll_ms": 20},
            "b": {"inst": {"argv": ["true"]}, "times": None, "interval_ms": 100000, "ctl_poll_ms": 20},
            "c": {"argv": ["sh", "-c", {"$ref": "#../../../a/inst/argv/2"}], "cwd": self.tmp, "exit": "c.exit"},
            "x": 1})
        real = os.path.realpath(path)
        a = self.ok({"op": "add", "id": path + "#/a"})
        b = self.ok({"op": "add", "id": path + "#/./b"})
        self.assertEqual((a, b), (real + "#/a", real + "#/b"))
        self.until(lambda: self.ok({"op": "get", "id": a}).get("runs") == 1)
        self.assertEqual(self.ok({"op": "get", "id": a})["id"], a)
        self.assertEqual(self.err({"op": "add", "id": path + "#/b/../b"}), "Exists")
        c = self.ok({"op": "add", "id": path + "#/c"})
        self.until(lambda: self.ok({"op": "state", "id": c}) == "done")
        self.assertEqual((self.read("a.out"), self.read("c.exit")), ("a\na\n", "0\n"))
        self.assertEqual(self.err({"op": "add", "id": path + "#/x"}), "FieldType")
        self.assertEqual(self.err({"op": "add", "id": path + "#/nope"}), "ReferencePointerInvalid")
        self.assertEqual(self.err({"op": "add", "id": path + "#a"}), "ReferencePointerInvalid")
        self.assertEqual(self.err({"op": "add", "id": "node.json#/a"}), "FieldType")
        self.ok({"op": "remove", "id": c})
        self.ok({"op": "pause", "id": b})
        self.ok({"op": "save", "path": self.p("t.json")})
        self.assertEqual([it["loop"] for it in json.loads(self.read("t.json"))], [a, b])
        self.ok({"op": "remove", "id": a})
        self.ok({"op": "remove", "id": b})
        self.assertEqual(self.ok({"op": "load", "path": self.p("t.json")}), [a, b])
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

    def test_state_skeleton_shared_with_loop(self):
        """daemon 的 state.json 跟 loop 同一份骨架：interval_mode 回音、last_error、loops＝個數、狀態值在 STATES 裡。"""
        self.start(state=self.p("d.state.json"), interval_mode="fixed", ctl=self.p("d.ctl.json"))
        a = self.loop("a", times=None, interval_ms=100000, state=self.p("a.state.json"), ctl=self.p("a.ctl.json"))
        self.ok({"op": "add", "id": a})
        st = self.until(lambda: (lambda d: d if d and d.get("loops") else None)(self.dstate()))
        self.assertEqual(st["loops"], 1)
        self.assertEqual(st["interval_mode"], "fixed")
        self.assertIsNone(st["last_error"])
        self.assertIn("skipped", st)
        la = self.until(lambda: self.ok({"op": "get", "id": a}).get("runs") == 1 and self.ok({"op": "get", "id": a}))
        common = {"id", "state", "pid", "runs", "times", "interval_ms", "interval_mode", "ctl_mtime", "last_error"}
        self.assertLessEqual(common, set(st))
        self.assertLessEqual(common, set(la))
        self.write("d.ctl.json", {"interval_mode": "after"})
        self.until(lambda: self.dstate()["interval_mode"] == "after")
        self.assertEqual(self.stop(), 0)
        st = self.dstate()
        self.assertEqual((st["state"], st["loops"]), ("stopped", 0))
        for v in (st["state"], la["state"]):
            self.assertIn(v, aos_loop.STATES)

    def test_state_last_error_scan_failed(self):
        self.start(state=self.p("d.state.json"))
        self.until(lambda: self.dstate())
        os.chmod(self.ctl, 0)
        self.addCleanup(os.chmod, self.ctl, 0o755)
        if os.access(self.ctl, os.R_OK):
            self.skipTest("root 不受權限限制")
        self.until(lambda: (self.dstate()["last_error"] or "").startswith("ScanFailed"))
        os.chmod(self.ctl, 0o755)
        self.until(lambda: self.dstate()["last_error"] is None)

    def dstate(self):
        try:
            return json.loads(self.read("d.state.json"))
        except (OSError, ValueError):
            return None

    def test_bad_config(self):
        for doc in ({"interval_ms": 10}, {"control_dir": "c", "ctl": "c/x.json"},
                    {"control_dir": "c", "interval_mode": "x"}):
            self.write("c.json", doc)
            with self.subTest(doc=doc), self.assertRaises(aos_daemon.DaemonError):
                aos_daemon.load_config(self.p("c.json"))


if __name__ == "__main__":
    unittest.main()
