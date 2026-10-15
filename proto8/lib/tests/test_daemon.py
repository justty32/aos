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
        self.write("daemon.json", dict({"ctl_dir": self.ctl, "interval_ms": 20, "ctl_poll_ms": 20,
                                        "grace_ms": 3000, "ctl": self.p("d.ctl.json"), "state": self.p("d.state.json")},
                                       **cfg))
        self.d = subprocess.Popen([sys.executable, DAEMON, self.p("daemon.json")],
                                  cwd=self.tmp, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True)
        self.addCleanup(self.stop)
        self.n = 0

    def stop(self, sig=signal.SIGTERM):
        """收 daemon。收尾一律 SIGTERM（子項整群收掉）；SIGKILL 只留給要造孤兒的測試——子 loop 自成 session、
        不跟著 daemon 死（接回靠這個），測試自己得收。SIGTERM 等不到才補 SIGKILL。"""
        if self.d.poll() is None:
            self.d.send_signal(sig)
        try:
            code = self.d.wait(10)
        except subprocess.TimeoutExpired:
            self.d.kill()
            code = self.d.wait(5)
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
        self.assertEqual(self.err({"op": "jump"}), "OpUnknown")
        self.assertEqual(self.err({"op": "add_times", "id": a, "delta": "x"}), "FieldType")
        self.assertEqual(self.err({"op": "save", "path": self.p("x.json")}), "OpUnknown")     # save／load 併進 table 窗
        self.write("ctl/bad.json", "{")
        r = self.get(self.p("ctl/bad.json.done"))
        self.assertEqual((r["request"], r["error"]["code"]), ("{", "CommandBad"))
        self.assertEqual(self.stop(), 0)
        self.assertEqual(os.listdir(self.p("loops")), ["1"])        # remove 刪那格；收工留著（給下次接回）

    def test_add_times_and_wrapper(self):
        self.start()
        a = self.loop("a", "sleep 0.3; echo x >> a.out", times=1)
        self.ok({"op": "add", "id": a})
        self.until(lambda: self.ok({"op": "state", "id": a}) == "running")
        self.assertEqual(self.ok({"op": "add_times", "id": a, "delta": 2})["times"], 3)    # 跑完之前加
        self.until(lambda: self.ok({"op": "get", "id": a}).get("state") == "done" and self.read("a.out") == "x\n" * 3)
        self.assertEqual(json.loads(self.read("loops/1/ctl.json"))["times"], 3)
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

    def test_add_does_not_check_inside(self):
        # daemon 只管自己這一層（C-52；10-15 深夜使用者「不留」）：子項的 loop 設定、inst 寫錯，add 照樣 ok，
        # 錯由子 loop 自己報（退 1、stderr 落 work_dir/N/err.json），daemon 只看到它結束（phase exited、state stopped）
        self.start()
        bad = {"argv": ["sh", "-c", "true"], "cwd": self.tmp}
        cases = (("e", {"inst": dict(bad, argv=[])}, "FieldType"),
                 ("i", {"inst": dict(bad, stdin_inherit=True)}, "Conflict"),          # 子 loop 從 stdin 灌 inst
                 ("m", {"inst": bad, "interval_mode": "x"}, "FieldType"),              # loop 層的 key 也不驗
                 ("s", dict(bad, stdin_inherit=True), "Conflict"))                     # inst.json 包成 loop 也一樣
        for n, (name, doc, code) in enumerate(cases, 1):
            with self.subTest(name=name):
                path = self.write(name + ".json", doc)
                self.assertEqual(self.ok({"op": "add", "id": path}), os.path.realpath(path))
                st = self.until(lambda: (lambda s: s if s.get("phase") == "exited" else None)(self.ok({"op": "get", "id": path})))
                self.assertEqual(st["state"], "stopped")
                err = [json.loads(x) for x in self.read("loops/%d/err.json" % n).splitlines()]
                self.assertEqual(err[-1]["error"]["code"], code)
        self.write("w.json", {"inst": bad, "ctl": 3})                                  # daemon 自己要用的窗才驗
        self.assertEqual(self.err({"op": "add", "id": self.p("w.json")}), "FieldType")
        self.assertEqual(sorted(os.listdir(self.p("loops"))), ["1", "2", "3", "4"])     # 那格收回

    def test_own_ctl_state_used(self):
        self.start()
        a = self.loop("a", times=None, interval_ms=100000, ctl="a.ctl.json", state="a.state.json")
        self.ok({"op": "add", "id": a})
        self.ok({"op": "pause", "id": a})
        self.assertEqual(json.loads(self.read("a.ctl.json")), {"seq": 1, "paused": {"val": True, "now": False}})
        st = json.loads(self.read("a.state.json"))
        self.assertEqual((st["state"], st["ctl_seq"]), ("paused", 1))      # 回音以 seq 為準
        self.assertFalse(os.path.exists(self.p("loops/1/ctl.json")))

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

    def test_table_window_and_load(self):
        # table 窗：子項六態；收工後 load: true 接回——行程還活著的認領、不重起
        self.start(table=self.p("t.json"))
        a = self.loop("a", "echo x >> a.out", times=None, interval_ms=100000)
        self.ok({"op": "add", "id": a})
        self.until(lambda: os.path.exists(self.p("a.out")))     # 先等第一次跑完，pause 才不會搶在它前面
        self.ok({"op": "pause", "id": a})
        t = json.loads(self.read("t.json"))
        self.assertEqual(t["kind"], "aos-daemon-table")
        row = t["children"][0]
        self.assertEqual((row["id"], row["phase"], row["exits"]), (os.path.realpath(a), "running", 0))
        self.assertTrue(row["pid"] and row["started"])
        self.d.send_signal(signal.SIGKILL)                  # daemon 死掉，子項變孤兒
        self.d.wait(5)
        self.d.stderr.close()
        self.start(table=self.p("t.json"), load=True)
        st = self.ok({"op": "get", "id": a})
        self.assertEqual((st["pid"], st["phase"], st["state"]), (row["pid"], "running", "paused"))
        self.assertEqual(self.read("a.out"), "x\n")         # 沒重起
        self.ok({"op": "remove", "id": a, "wait": False})
        self.until(lambda: not alive(row["pid"]))
        self.assertEqual(json.loads(self.read("t.json"))["children"], [])

    def test_children_policy_inst_body(self):
        # 候選 g：children 當初始表、policies.child_exit 策略格、inst＝daemon 每拍的身體；ctl_dir 選填
        a = self.loop("a", "echo x >> a.out", times=1)
        self.write("pol.json", {"argv": ["sh", "-c", 'n=$(grep -o \'"exits": [0-9]*\' | grep -o "[0-9]*"); '
                                                  '[ "$n" -lt 3 ] && echo \'{"action": "restart", "after_ms": 10}\' '
                                                  '|| echo \'{"action": "remove"}\'']})
        self.start(ctl_dir=None, children=[a], policies={"child_exit": self.p("pol.json")}, table=self.p("t.json"),
                   inst={"argv": ["sh", "-c", "echo b >> body.out"], "cwd": self.tmp}, times=None, interval_ms=50)
        self.until(lambda: os.path.exists(self.p("a.out")) and self.read("a.out") == "x\n" * 3
                   and json.loads(self.read("t.json"))["children"] == [])
        self.until(lambda: len(self.read("body.out").split()) >= 2)
        self.assertFalse(os.path.exists(self.ctl))
        self.assertEqual(self.stop(), 0)
        self.assertFalse(os.path.exists(self.p("loops", "1")))   # remove 掉了，那格刪掉

    def test_loop_json_runs_as_daemon(self):
        # 嚴格超集：一份合法的 loop.json 丟給 aos-daemon 也能跑（inst＝每拍的身體）
        path = self.loop("l", "echo y >> l.out", times=2, ctl="l.ctl.json", state="l.state.json")
        r = subprocess.run([sys.executable, DAEMON, path], cwd=self.tmp, capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read("l.out"), "y\ny\n")
        out = [json.loads(x) for x in r.stdout.splitlines()]
        self.assertEqual(out[-1], {"end": "done", "runs": 2, "skipped": 0, "last_code": 0, "signal": None})

    def test_no_inst_only_summary(self):
        # 沒 inst 的拍不吐每拍那份，stdout 只有結束總結
        path = self.write("d.json", {"times": 3, "interval_ms": 10, "ctl": "d.ctl.json", "state": "d.state.json"})
        r = subprocess.run([sys.executable, DAEMON, path], cwd=self.tmp, capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = [json.loads(x) for x in r.stdout.splitlines()]
        self.assertEqual(out, [{"end": "done", "runs": 3, "skipped": 0, "last_code": None, "signal": None}])

    def test_target_pointer(self):
        # 一份檔放好幾格：同一份檔兩個位置＝兩個 loop；inst 那格包成只跑一次
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

    def test_sigterm_clears_loops(self):
        a = self.loop("a", "echo $$ > a.pid; exec sleep 30", times=None)
        self.start(children=[a])
        self.until(lambda: os.path.exists(self.p("a.pid")))
        pid = int(self.read("a.pid"))
        self.assertEqual(self.stop(signal.SIGTERM), 0)
        self.assertFalse(alive(pid))

    def test_windows_required(self):
        for cfg in ({"state": None}, {"ctl": None}):
            with self.subTest(cfg=cfg):
                self.start(**cfg)
                self.assertEqual(self.d.wait(10), 1)
                self.assertIn("WindowMissing", self.d.stderr.read())
                self.d.stderr.close()

    def test_own_ctl_pause_and_stop(self):
        self.write("d.ctl.json", {"paused": True})
        self.start(table=self.p("t.json"))
        self.until(lambda: os.path.exists(self.p("d.state.json")))
        done = self.put({"op": "list"})
        time.sleep(0.2)
        self.assertFalse(os.path.exists(done))         # 暫停＝不掃，指令堆著
        self.write("d.ctl.json", {})
        self.get(done)
        self.write("d.ctl.json", {"stop": True})
        self.assertEqual(self.d.wait(10), 0)
        self.assertEqual(json.loads(self.read("t.json"))["children"], [])
        self.assertEqual(json.loads(self.read("d.state.json"))["state"], "stopped")

    def test_times_one_shot(self):
        os.makedirs(self.p("ctl"))
        self.write("ctl/001.json", {"op": "list"})
        self.start(times=1)
        self.assertEqual(self.d.wait(10), 0)
        self.assertTrue(json.loads(self.read("ctl/001.json.done"))["ok"])

    def test_state_skeleton_shared_with_loop(self):
        """daemon 的 state.json 跟 loop 同一份骨架：interval_mode 回音、last_error、loops＝個數、狀態值在 STATES 裡。"""
        self.start(interval_mode="fixed")
        a = self.loop("a", times=None, interval_ms=100000, state=self.p("a.state.json"), ctl=self.p("a.ctl.json"))
        self.ok({"op": "add", "id": a})
        st = self.until(lambda: (lambda d: d if d and d.get("loops") else None)(self.dstate()))
        self.assertEqual(st["loops"], 1)
        self.assertEqual(st["interval_mode"], "fixed")
        self.assertIsNone(st["last_error"])
        self.assertIn("skipped", st)
        la = self.until(lambda: self.ok({"op": "get", "id": a}).get("runs") == 1 and self.ok({"op": "get", "id": a}))
        common = {"id", "state", "pid", "started", "boot_id", "beat", "runs", "times", "interval_ms", "interval_mode",
                  "ctl_seq", "last_error", "last_warning"}
        self.assertLessEqual(common, set(st))
        self.assertLessEqual(common, set(la))
        self.write("d.ctl.json", {"interval_mode": "after"})
        self.until(lambda: self.dstate()["interval_mode"] == "after")
        self.assertEqual(self.stop(), 0)
        st = self.dstate()
        self.assertEqual((st["state"], st["loops"]), ("stopped", 1))     # 收工表留著（給下次接回）
        for v in (st["state"], la["state"]):
            self.assertIn(v, aos_loop.STATES)

    def test_policy_failed_goes_to_state_not_stderr(self):
        # 策略格回的不對＝當 leave，原因記在 state 窗的 last_warning，不寫 stderr（N-43；10-15「都按照推薦。」）
        self.write("pol.json", {"argv": ["sh", "-c", "echo '{\"action\": \"fly\"}'"]})
        a = self.loop("a", times=1)
        self.start(children=[a], policies={"child_exit": self.p("pol.json")})
        self.until(lambda: ((self.dstate() or {}).get("last_warning") or "").startswith("PolicyFailed"))
        self.d.send_signal(signal.SIGTERM)
        self.assertEqual(self.d.wait(10), 0)
        self.assertEqual(self.d.stderr.read(), "")

    def test_state_last_error_scan_failed(self):
        self.start()
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
        w = {"ctl": "x.json", "state": "s.json"}
        for doc in (dict(w, interval_ms=-1), {"ctl_dir": "c", "ctl": "c/x.json", "state": "s.json"},
                    dict(w, interval_mode="x"), dict(w, load=True), dict(w, children={}),
                    dict(w, policies={"child_exit": 3})):
            self.write("c.json", doc)
            with self.subTest(doc=doc), self.assertRaises(aos_daemon.DaemonError):
                aos_daemon.load_config(self.p("c.json"))


if __name__ == "__main__":
    unittest.main()
