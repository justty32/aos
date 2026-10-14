"""proto8/lib 的自動測試：loop（aos_loop）；起真的 loop 行程、走檔案。只用標準庫：

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
from unittest import mock

from helpers import LOOP, Tmp, alive
import aos_loop  # noqa: E402


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

    def test_target_pointer(self):
        # loop.json 的一格當 loop 本體；inst 裡的 ../ 照整份檔算；id＝realpath#/位置
        path = self.write("node.json", {"cmd": "echo z >> n.out",
                                        "job": {"inst": {"argv": ["sh", "-c", {"$ref": "#../../../../cmd"}], "cwd": self.tmp},
                                                "times": 2, "state": "n.state.json"},
                                        "x": [1]})
        r = self.cli(path + "#/job")
        self.assertEqual((r.returncode, self.read("n.out")), (0, "z\nz\n"), r.stderr)
        self.assertEqual(self.state("n.state.json")["id"], os.path.realpath(path) + "#/job")
        r = self.cli(path + "#/x")                                      # 指到的不是物件
        self.assertEqual((r.returncode, r.stderr.split(":")[0]), (125, "FieldType"))
        self.assertIn(os.path.realpath(path) + "#/x", r.stderr)
        r = self.cli(path + "#job")
        self.assertEqual((r.returncode, r.stderr.split(":")[0]), (125, "ReferencePointerInvalid"))

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

    def test_ctl_same_stat_change_detected(self):
        """4 ms 內等長改名蓋過：ino／mtime／size 全撞（ext4 實測會發生），第二次仍要讀到；壞檔維持上一次、回音照寫。"""
        ctl = aos_loop.CtlFile(self.p("c.json"))
        aos_loop.write_json(self.p("c.json"), {"times": 5})
        fixed = os.stat(self.p("c.json"))
        with mock.patch("os.stat", return_value=fixed), mock.patch("os.fstat", return_value=fixed):
            ctl.poll()
            self.assertEqual(ctl.good, {"times": 5})
            aos_loop.write_json(self.p("c.json"), {"times": 6})     # 等長
            ctl.poll()
            self.assertEqual(ctl.good, {"times": 6})
            aos_loop.write_json(self.p("c.json"), {"paused": True})
            ctl.poll()
            self.assertEqual(ctl.good, {"paused": (True, False)})
            with open(self.p("c.json"), "w") as f:                    # 壞檔：維持上一次
                f.write("{")
            ctl.poll()
            self.assertEqual(ctl.good, {"paused": (True, False)})
        self.assertEqual(ctl.mtime, fixed.st_mtime)
        aos_loop.write_json(self.p("c.json"), {"paused": True})       # 內容同上一份好的、檔是新的：回音跟上
        os.utime(self.p("c.json"), ns=(fixed.st_mtime_ns + 10**9,) * 2)
        ctl.poll()
        self.assertEqual(ctl.mtime, os.stat(self.p("c.json")).st_mtime)

    def test_ctl_pause_then_times_exits_when_done(self):
        self.ctl({"paused": True})
        path = self.loop(sh="echo x >> l.out", times=None, interval_ms=20, ctl="l.ctl.json", state="l.state.json")
        proc = self.start(path)
        self.until(lambda: (self.state() or {}).get("state") == "paused")
        time.sleep(0.2)
        self.assertFalse(os.path.exists(self.p("l.out")))
        self.ctl({"times": 2})                          # paused 沒寫＝回到初始值（false）
        self.assertEqual(proc.wait(5), 0)               # 次數跑完就退出，有 ctl 也一樣
        self.assertEqual(self.read("l.out"), "x\nx\n")
        st = self.state()
        self.assertEqual((st["state"], st["runs"]), ("done", 2))
        self.assertEqual(st["ctl_mtime"], os.stat(self.p("l.ctl.json")).st_mtime)

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


if __name__ == "__main__":
    unittest.main()
