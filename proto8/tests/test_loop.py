"""aos-loop 直接叫（不經 aos-exec）的案例：PATH 原樣、訊號轉給那次（ideas § 24）、命令列（10-21 傍晚 ideas § 9）。
訊號案例移植自 proto8/impls/aos-loop/tests/test_cli.py 的 C 段；其他 aos-loop 案例在 test_exec.py（經 agent 叫）。"""
import datetime, json, os, signal, subprocess, tempfile, time, unittest
from pathlib import Path
import own_error  # noqa: E402
own_error.install()   # 錯誤一行的代號（照 10-23 命名統合）：檢查對得上原因開頭再拿掉

from aos_bins import ROOT, tool, path_with  # noqa: E402  四支 C++ 在 impls/<名>/bin/、aos-tick 在 proto8/bin/（10-23）
LOOP = tool("aos-loop")


def env_of(extra=None):
    # aos 的程式都不動 PATH：字串 run 要叫的 aos-exec 由呼叫者放進 PATH
    e = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    e["PATH"] = path_with(e.get("PATH", ""))
    e.update(extra or {})
    return e


def wait_file(path, secs=10):
    end = time.monotonic() + secs
    while time.monotonic() < end:
        if Path(path).exists():
            return True
        time.sleep(0.02)
    return False


class Base(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.t = Path(self._t.name)
        self.addCleanup(self._t.cleanup)

    def prog(self, name, body):
        d = self.t / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "_entry").write_text("#!/bin/sh\n" + body)
        (d / "_entry").chmod(0o755)

    def loop(self, cfg):
        (self.t / "loop.json").write_text(json.dumps(cfg))

    def start(self, env=None):
        return subprocess.Popen([LOOP, "loop.json"], cwd=str(self.t), env=env_of(env), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)


class T(Base):
    def test_string_val_path_as_is(self):
        # ideas § 24：字串 run 那次看到的 PATH 跟 loop 收到的一樣（不加任何 bin）
        self.prog("cell", 'echo "$PATH" > "$AOS_STACK/path"\n')
        self.loop({"run": "cell", "max": 1})
        path = path_with("/usr/bin:/bin")
        r = subprocess.run([LOOP, "loop.json"], cwd=str(self.t), env=env_of({"PATH": path}), capture_output=True,
                           text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.t / ".stack" / "path").read_text().strip(), path)

    def test_sigterm_forwarded_to_string_beat(self):
        # 那次收到 SIGTERM 收好自己、退 0；loop 不起下一次，以 143 結束
        self.prog("c", 'trap \'echo got >> "$AOS_STACK/log"; exit 0\' TERM\n'
                       'echo beat >> "$AOS_STACK/log"; touch "$AOS_STACK/up"\nwhile :; do sleep 0.05; done\n')
        self.loop({"run": "c", "max": 5})
        p = self.start()
        ok = wait_file(self.t / ".stack" / "up")
        p.send_signal(signal.SIGTERM)
        out, err = p.communicate(timeout=20)
        self.assertEqual((ok, p.returncode, out, err, (self.t / ".stack" / "log").read_text().split()),
                         (True, 143, "", "", ["beat", "got"]))

    def test_sigint_forwarded_to_inst_beat(self):
        s = self.t / "stack"
        s.mkdir()
        # 內嵌單子寫 loop.json#/body（10-21）：那次是 aos-exec 行程內跑單子，loop 轉給 aos-exec、它再轉給整群
        self.loop({"run": "loop.json#/body", "max": 5,
                   "body": {"argv": ["sh", "-c", 'trap \'echo got > "$AOS_STACK/got"; exit 0\' INT; '
                                     'touch "$AOS_STACK/up"; while :; do sleep 0.05; done']}})
        p = self.start({"AOS_STACK": str(s)})
        ok = wait_file(s / "up")
        p.send_signal(signal.SIGINT)
        out, err = p.communicate(timeout=20)
        self.assertEqual((ok, p.returncode, err, (s / "got").exists()), (True, 130, "", True))

    def test_sighup_lap_dies(self):
        # 那次不接、被 SIGHUP 停掉：loop 還是以 128＋1 結束（不另說「第幾次失敗」）
        self.prog("c", 'touch "$AOS_STACK/up"\nexec sleep 30\n')
        self.loop({"run": "c", "max": 5})
        p = self.start()
        ok = wait_file(self.t / ".stack" / "up")
        p.send_signal(signal.SIGHUP)
        out, err = p.communicate(timeout=20)
        self.assertEqual((ok, p.returncode, err), (True, 129, ""))


class Windows(T):
    """loop.json 的選填 key：interval_ms、ctl、state（N-06～N-09、N-17、N-32、N-33；rewrite-order ④）。"""

    def stack(self):
        s = self.t / "stack"
        s.mkdir(exist_ok=True)
        return s

    def loop(self, cfg):
        # count() 指到 loop.json 裡的 body：每次數一下（10-21 起 run 只收字串，內嵌單子走 loop.json#/body）
        super().loop(dict({"body": {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/runs"']}}, **cfg))

    def run_loop(self, cfg, env=None, timeout=20):
        self.loop(cfg)
        return subprocess.run([LOOP, "loop.json"], cwd=str(self.t), env=env_of(env), capture_output=True,
                              text=True, timeout=timeout)

    def count(self):
        return "loop.json#/body"

    def test_state_written_with_heartbeat(self):
        s = self.stack()
        r = self.run_loop({"run": self.count(), "max": 3, "state": "state.json"}, {"AOS_STACK": str(s)})
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        st = json.loads((s / "state.json").read_text())
        self.assertEqual((st["kind"], st["phase"], st["runs"], st["code"], st["max"], st["ctl_seq"]),
                         ("state", "done", 3, 0, 3, None))
        self.assertIsInstance(st["pid"], int)
        # 10-23 命名統合：phase、runs、started_at_ticks、at（ISO 8601 UTC 到毫秒）（10-23 統合前叫 state、lap、started、beat）
        self.assertEqual(list(st), ["kind", "phase", "runs", "max", "interval_ms", "paused", "ctl_seq", "ctl_warning",
                                    "code", "pid", "started_at_ticks", "boot_id", "at"])
        self.assertRegex(st["at"], r"\A\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}\+00:00\Z")
        datetime.datetime.fromisoformat(st["at"])
        self.assertFalse((s / ".state.json").exists())

    def test_no_windows_no_files(self):
        s = self.stack()
        r = self.run_loop({"run": self.count(), "max": 2}, {"AOS_STACK": str(s)})
        self.assertEqual((r.returncode, sorted(p.name for p in s.iterdir())), (0, ["runs"]))

    def test_window_without_stack_is_own_error(self):
        r = self.run_loop({"run": self.count(), "max": 1, "ctl": "ctl.json"})
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("aos-loop: ") and "AOS_STACK" in r.stderr, r.stderr)

    def test_bad_interval_is_own_error(self):
        r = self.run_loop({"run": self.count(), "interval_ms": -1})
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("aos-loop: "), r.stderr)

    def test_interval_spaces_laps(self):
        s = self.stack()
        t0 = time.monotonic()
        r = self.run_loop({"run": self.count(), "max": 3, "interval_ms": 300}, {"AOS_STACK": str(s)})
        self.assertEqual(r.returncode, 0)
        self.assertGreaterEqual(time.monotonic() - t0, 0.6)
        self.assertEqual(len((s / "runs").read_text().split()), 3)

    def test_ctl_stopped_and_seq(self):
        s = self.stack()
        (s / "ctl.json").write_text(json.dumps({"stopped": True, "seq": 7}))
        r = self.run_loop({"run": self.count(), "max": 3, "ctl": "ctl.json", "state": "state.json"},
                          {"AOS_STACK": str(s)})
        st = json.loads((s / "state.json").read_text())
        self.assertEqual((r.returncode, r.stderr, st["phase"], st["runs"], st["ctl_seq"], (s / "runs").exists()),
                         (0, "", "stopped", 0, 7, False))

    def test_ctl_max_overrides(self):
        s = self.stack()
        (s / "ctl.json").write_text(json.dumps({"max": 1}))
        r = self.run_loop({"run": self.count(), "max": 5, "ctl": "ctl.json"}, {"AOS_STACK": str(s)})
        self.assertEqual((r.returncode, len((s / "runs").read_text().split())), (0, 1))

    def test_bad_ctl_kept_last_good_and_warned(self):
        s = self.stack()
        (s / "ctl.json").write_text(json.dumps({"max": "two"}))
        r = self.run_loop({"run": self.count(), "max": 2, "ctl": "ctl.json", "state": "state.json"},
                          {"AOS_STACK": str(s)})
        st = json.loads((s / "state.json").read_text())
        self.assertEqual((r.returncode, r.stderr, len((s / "runs").read_text().split())), (0, "", 2))
        self.assertIn("max", st["ctl_warning"])

    def test_ctl_pause_then_resume(self):
        s = self.stack()
        (s / "ctl.json").write_text(json.dumps({"paused": True}))
        self.loop({"run": self.count(), "max": 2, "ctl": "ctl.json", "state": "state.json"})
        p = self.start({"AOS_STACK": str(s)})
        ok = wait_file(s / "state.json")
        time.sleep(0.5)
        paused = json.loads((s / "state.json").read_text())["phase"]
        self.assertFalse((s / "runs").exists())
        (s / "ctl.json").write_text(json.dumps({"paused": False}))
        out, err = p.communicate(timeout=20)
        self.assertEqual((ok, paused, p.returncode, err, len((s / "runs").read_text().split())),
                         (True, "paused", 0, "", 2))

    def test_signal_while_waiting(self):
        # 兩次之間（睡 interval）收到 SIGTERM：不起下一次、直接 143，state 寫 stopped
        s = self.stack()
        self.loop({"run": self.count(), "max": 5, "interval_ms": 5000, "state": "state.json"})
        p = self.start({"AOS_STACK": str(s)})
        ok = wait_file(s / "runs")
        time.sleep(0.2)
        p.send_signal(signal.SIGTERM)
        out, err = p.communicate(timeout=20)
        st = json.loads((s / "state.json").read_text())
        self.assertEqual((ok, p.returncode, err, st["phase"], st["code"], len((s / "runs").read_text().split())),
                         (True, 143, "", "stopped", 143, 1))


class Cli(Base):
    """命令列（10-21 傍晚 ideas § 9；原 10-21 plan § 2 的 --cfg 與命令列 XXX 拿掉）：
    `aos-loop [--max] [--interval-ms] [--ctl] [--state] 設定檔`，設定檔必給、只能一個、可寫 檔#/指標；run 可以是陣列。"""

    def stack(self):
        s = self.t / "stack"
        s.mkdir(exist_ok=True)
        return s

    def runs(self, s):
        return (s / "runs").read_text().splitlines() if (s / "runs").exists() else []

    def loop_cli(self, *argv, env=None, timeout=30):
        return subprocess.run([LOOP, *argv], cwd=str(self.t), env=env_of(env), capture_output=True, text=True,
                              timeout=timeout)

    def mark(self, name):
        # 每次在 runs 記一行「名字 args...」
        self.prog(name, 'echo "%s $*" >> "$AOS_STACK/runs"\n' % name)

    def test_flags_override_cfg(self):
        s = self.stack()
        self.mark("a")
        self.loop({"run": "a", "max": 5, "interval_ms": 0})
        t0 = time.monotonic()
        r = self.loop_cli("--max", "2", "--interval-ms=300", "loop.json", env={"AOS_STACK": str(s)})
        self.assertEqual((r.returncode, r.stderr, len(self.runs(s))), (0, "", 2))
        self.assertGreaterEqual(time.monotonic() - t0, 0.3)

    def test_flag_windows(self):
        s = self.stack()
        self.mark("a")
        (s / "c.json").write_text(json.dumps({"stopped": True, "seq": 3}))
        self.loop({"run": "a", "max": 2})
        r = self.loop_cli("--ctl", "c.json", "--state=st.json", "loop.json", env={"AOS_STACK": str(s)})
        st = json.loads((s / "st.json").read_text())
        self.assertEqual((r.returncode, r.stderr, st["phase"], st["ctl_seq"], self.runs(s)), (0, "", "stopped", 3, []))

    def test_val_array_args_each_beat(self):
        # run＝[目標, 參數...]：每次 aos-exec -- 目標 參數...（參數照字面，--max 也只是參數）
        s = self.stack()
        self.mark("b")
        self.loop({"run": ["b", "x", "--max", "y"], "max": 2})
        r = self.loop_cli("loop.json", env={"AOS_STACK": str(s)})
        self.assertEqual((r.returncode, r.stderr, self.runs(s)), (0, "", ["b x --max y"] * 2))

    def test_cfg_with_pointer(self):
        # 設定檔可寫 檔#/指標＝那份檔裡那個位置的物件（~0、~1 照 JSON pointer）
        s = self.stack()
        self.mark("b")
        (self.t / "big.json").write_text(json.dumps({"loops": {"a": {"run": ["b", "1"], "max": 3},
                                                               "x~/y": {"run": "b", "max": 1}}}))
        r = self.loop_cli("big.json#/loops/a", env={"AOS_STACK": str(s)})
        r2 = self.loop_cli("big.json#/loops/x~0~1y", env={"AOS_STACK": str(s)})
        self.assertEqual((r.returncode, r.stderr, r2.returncode, r2.stderr, self.runs(s)),
                         (0, "", 0, "", ["b 1"] * 3 + ["b "]))

    def test_cfg_shebang_line_skipped(self):
        # 10-22 使用者要 Python 照 C++ 的寬鬆：設定檔第一行 #! 跳過（原本算「不是 JSON」）；檔#/指標也一樣
        s = self.stack()
        self.mark("a")
        (self.t / "loop.json").write_text("#!/usr/bin/env aos-loop\n" + json.dumps({"run": "a", "max": 2, "in": {"run": "a", "max": 1}}))
        r = self.loop_cli("loop.json", env={"AOS_STACK": str(s)})
        r2 = self.loop_cli("loop.json#/in", env={"AOS_STACK": str(s)})
        self.assertEqual((r.returncode, r.stderr, r2.returncode, r2.stderr, len(self.runs(s))), (0, "", 0, "", 3))

    def test_no_max_is_unlimited(self):
        # L8：沒寫 max、沒給 --max＝不限（原本 10）；這裡靠第 12 次退 10 收工
        s = self.stack()
        self.prog("c", 'echo x >> "$AOS_STACK/runs"; [ "$(wc -l < "$AOS_STACK/runs")" -ge 12 ] && exit 10; exit 0\n')
        self.loop({"run": "c"})
        r = self.loop_cli("loop.json", env={"AOS_STACK": str(s)})
        self.assertEqual((r.returncode, r.stderr, len(self.runs(s))), (0, "", 12))

    def test_val_object_is_own_error(self):
        s = self.stack()
        self.loop({"run": {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/runs"']}, "max": 1})
        r = self.loop_cli("loop.json", env={"AOS_STACK": str(s)})
        self.assertEqual((r.returncode, len(r.stderr.splitlines()), self.runs(s)), (1, 1, []))
        self.assertTrue(r.stderr.startswith("aos-loop: ") and "loop.json#/body" in r.stderr, r.stderr)

    def test_dash_target_not_flag(self):
        # L10：loop 叫 aos-exec 時寫 `aos-exec -- 目標`，- 開頭的目標不會被 aos-exec 當旗標
        s = self.stack()
        self.mark("-p")
        self.loop({"run": "-p", "max": 1})
        r1 = self.loop_cli("loop.json", env={"AOS_STACK": str(s)})
        self.loop({"run": ["-p", "z"], "max": 1})
        r2 = self.loop_cli("--", "loop.json", env={"AOS_STACK": str(s)})
        self.assertEqual((r1.returncode, r1.stderr, r2.returncode, r2.stderr, self.runs(s)),
                         (0, "", 0, "", ["-p ", "-p z"]))

    def test_usage_and_own_errors(self):
        self.mark("a")
        self.loop({"run": "a", "max": 1})
        (self.t / "norun.json").write_text(json.dumps({"max": 1}))
        bads = ([], ["a", 1], {"x": 1}, 3)
        for i, bad in enumerate(bads):
            (self.t / ("bad%d.json" % i)).write_text(json.dumps({"run": bad, "max": 1}))
        usage = ((), ("loop.json", "a"), ("--cfg", "loop.json"), ("--max=abc",), ("--max",), ("--bogus", "1", "loop.json"))
        own = (("--max=abc", "loop.json"), ("--max", "-1", "loop.json"), ("--interval-ms", "1.5", "loop.json"),
               ("nope.json",), ("norun.json",), ("loop.json#a",), ("loop.json#/nope",), ("loop.json#/run",)) + \
            tuple(("bad%d.json" % i,) for i in range(len(bads)))
        for argv in usage + own:
            r = self.loop_cli(*argv)
            self.assertEqual((r.returncode, len(r.stderr.splitlines())), (1, 1), (argv, r.stderr))
            self.assertTrue(r.stderr.startswith("aos-loop: "), (argv, r.stderr))
            self.assertEqual("usage" in r.stderr, argv in usage, (argv, r.stderr))
        self.assertIn("沒有東西可跑", self.loop_cli("norun.json").stderr)
        self.assertIn("沒有設定檔", self.loop_cli().stderr)

    def test_aos_exec_loop_json_via_exec_key(self):
        # loop.json 帶 _entry＝["aos-loop", ..., {"$env": "AOS_CF"}]，`aos-exec loop.json` 就把 loop 跑起來
        # （沒 argv 的物件當資料夾、取 _entry；AOS_CF＝那份 loop.json；cwd＝它的資料夾，所以 run 的相對路徑是旁邊那個）
        d = self.t / "agent"
        d.mkdir()
        (d / "loop.json").write_text(json.dumps({
            "_entry": ["aos-loop", "--interval-ms", "0", {"$env": "AOS_CF"}], "run": ["loop.json#/body", "q"], "max": 2,
            "body": {"argv": ["sh", "-c", 'echo "x $1" >> "$AOS_STACK/runs"', "sh"]}}))
        ws = self.t / "ws"
        ws.mkdir()
        r = subprocess.run([tool("aos-exec"), "--ws", str(ws), str(d / "loop.json")], cwd=str(self.t),
                           env=env_of(), capture_output=True, text=True, timeout=30)
        self.assertEqual((r.returncode, r.stderr, self.runs(ws / ".stack")), (0, "", ["x q"] * 2))

    def test_aos_exec_big_json_pointer(self):
        # 大 JSON 裡的 loop：_entry 用 {"$env": "AOS_CF", "$path": "#/loops/a"} 指回自己那一格（$path 字串拼接，10-21 傍晚）
        (self.t / "big.json").write_text(json.dumps({"loops": {"a": {
            "_entry": ["aos-loop", {"$env": "AOS_CF", "$path": "#/loops/a"}], "run": "big.json#/loops/a/body", "max": 3,
            "body": {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/runs"']}}}}))
        ws = self.t / "ws"
        ws.mkdir()
        r = subprocess.run([tool("aos-exec"), "--ws", str(ws), str(self.t / "big.json") + "#/loops/a"],
                           cwd=str(self.t), env=env_of(), capture_output=True, text=True, timeout=30)
        self.assertEqual((r.returncode, r.stderr, len(self.runs(ws / ".stack"))), (0, "", 3))


if __name__ == "__main__":
    unittest.main()
