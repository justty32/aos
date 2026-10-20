"""aos-loop 直接叫（不經 aos-exec）的案例：PATH 原樣、訊號轉給那拍（ideas § 24）。
訊號案例移植自 proto8/impls/aos-loop/tests/test_cli.py 的 C 段；其他 aos-loop 案例在 test_exec.py（經 agent 叫）。"""
import json, os, signal, subprocess, tempfile, time, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "bin"
LOOP = str(BIN / "aos-loop")


def env_of(extra=None):
    # aos 的程式都不動 PATH：字串 run 要叫的 aos-exec 由呼叫者放進 PATH
    e = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    e["PATH"] = str(BIN) + os.pathsep + e.get("PATH", "")
    e.update(extra or {})
    return e


def wait_file(path, secs=10):
    end = time.monotonic() + secs
    while time.monotonic() < end:
        if Path(path).exists():
            return True
        time.sleep(0.02)
    return False


class T(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.t = Path(self._t.name)
        self.addCleanup(self._t.cleanup)

    def prog(self, name, body):
        d = self.t / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "_exec").write_text("#!/bin/sh\n" + body)
        (d / "_exec").chmod(0o755)

    def loop(self, cfg):
        (self.t / "loop.json").write_text(json.dumps(cfg))

    def start(self, env=None):
        return subprocess.Popen([LOOP, "loop.json"], cwd=str(self.t), env=env_of(env), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)

    def test_string_run_path_as_is(self):
        # ideas § 24：字串 run 那拍看到的 PATH 跟 loop 收到的一樣（不加任何 bin）
        self.prog("cell", 'echo "$PATH" > "$AOS_STACK/path"\n')
        self.loop({"run": "cell", "max": 1})
        path = str(BIN) + ":/usr/bin:/bin"
        r = subprocess.run([LOOP, "loop.json"], cwd=str(self.t), env=env_of({"PATH": path}), capture_output=True,
                           text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.t / ".aos" / "path").read_text().strip(), path)

    def test_sigterm_forwarded_to_string_lap(self):
        # 那拍收到 SIGTERM 收好自己、退 0；loop 不起下一拍，以 143 結束
        self.prog("c", 'trap \'echo got >> "$AOS_STACK/log"; exit 0\' TERM\n'
                       'echo lap >> "$AOS_STACK/log"; touch "$AOS_STACK/up"\nwhile :; do sleep 0.05; done\n')
        self.loop({"run": "c", "max": 5})
        p = self.start()
        ok = wait_file(self.t / ".aos" / "up")
        p.send_signal(signal.SIGTERM)
        out, err = p.communicate(timeout=20)
        self.assertEqual((ok, p.returncode, out, err, (self.t / ".aos" / "log").read_text().split()),
                         (True, 143, "", "", ["lap", "got"]))

    def test_sigint_forwarded_to_inst_lap(self):
        s = self.t / "stack"
        s.mkdir()
        self.loop({"run": {"argv": ["sh", "-c", 'trap \'echo got > "$AOS_STACK/got"; exit 0\' INT; '
                                    'touch "$AOS_STACK/up"; while :; do sleep 0.05; done']}, "max": 5})
        p = self.start({"AOS_STACK": str(s)})
        ok = wait_file(s / "up")
        p.send_signal(signal.SIGINT)
        out, err = p.communicate(timeout=20)
        self.assertEqual((ok, p.returncode, err, (s / "got").exists()), (True, 130, "", True))

    def test_sighup_lap_dies(self):
        # 那拍不接、被 SIGHUP 停掉：loop 還是以 128＋1 結束（不另說「第幾圈失敗」）
        self.prog("c", 'touch "$AOS_STACK/up"\nexec sleep 30\n')
        self.loop({"run": "c", "max": 5})
        p = self.start()
        ok = wait_file(self.t / ".aos" / "up")
        p.send_signal(signal.SIGHUP)
        out, err = p.communicate(timeout=20)
        self.assertEqual((ok, p.returncode, err), (True, 129, ""))


class Windows(T):
    """loop.json 的選填 key：interval_ms、ctl、state（N-06～N-09、N-17、N-32、N-33；rewrite-order ④）。"""

    def stack(self):
        s = self.t / "stack"
        s.mkdir(exist_ok=True)
        return s

    def run_loop(self, cfg, env=None, timeout=20):
        self.loop(cfg)
        return subprocess.run([LOOP, "loop.json"], cwd=str(self.t), env=env_of(env), capture_output=True,
                              text=True, timeout=timeout)

    def count(self):
        return {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/laps"']}

    def test_state_written_with_heartbeat(self):
        s = self.stack()
        r = self.run_loop({"run": self.count(), "max": 3, "state": "state.json"}, {"AOS_STACK": str(s)})
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        st = json.loads((s / "state.json").read_text())
        self.assertEqual((st["kind"], st["state"], st["lap"], st["code"], st["max"], st["ctl_seq"]),
                         ("state", "done", 3, 0, 3, None))
        self.assertIsInstance(st["pid"], int)
        for k in ("started", "boot_id", "beat"):
            self.assertIn(k, st)
        self.assertFalse((s / ".state.json").exists())

    def test_no_windows_no_files(self):
        s = self.stack()
        r = self.run_loop({"run": self.count(), "max": 2}, {"AOS_STACK": str(s)})
        self.assertEqual((r.returncode, sorted(p.name for p in s.iterdir())), (0, ["laps"]))

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
        self.assertEqual(len((s / "laps").read_text().split()), 3)

    def test_ctl_stop_and_seq(self):
        s = self.stack()
        (s / "ctl.json").write_text(json.dumps({"stop": True, "seq": 7}))
        r = self.run_loop({"run": self.count(), "max": 3, "ctl": "ctl.json", "state": "state.json"},
                          {"AOS_STACK": str(s)})
        st = json.loads((s / "state.json").read_text())
        self.assertEqual((r.returncode, r.stderr, st["state"], st["lap"], st["ctl_seq"], (s / "laps").exists()),
                         (0, "", "stopped", 0, 7, False))

    def test_ctl_max_overrides(self):
        s = self.stack()
        (s / "ctl.json").write_text(json.dumps({"max": 1}))
        r = self.run_loop({"run": self.count(), "max": 5, "ctl": "ctl.json"}, {"AOS_STACK": str(s)})
        self.assertEqual((r.returncode, len((s / "laps").read_text().split())), (0, 1))

    def test_bad_ctl_kept_last_good_and_warned(self):
        s = self.stack()
        (s / "ctl.json").write_text(json.dumps({"max": "two"}))
        r = self.run_loop({"run": self.count(), "max": 2, "ctl": "ctl.json", "state": "state.json"},
                          {"AOS_STACK": str(s)})
        st = json.loads((s / "state.json").read_text())
        self.assertEqual((r.returncode, r.stderr, len((s / "laps").read_text().split())), (0, "", 2))
        self.assertIn("max", st["last_warning"])

    def test_ctl_pause_then_resume(self):
        s = self.stack()
        (s / "ctl.json").write_text(json.dumps({"paused": True}))
        self.loop({"run": self.count(), "max": 2, "ctl": "ctl.json", "state": "state.json"})
        p = self.start({"AOS_STACK": str(s)})
        ok = wait_file(s / "state.json")
        time.sleep(0.5)
        paused = json.loads((s / "state.json").read_text())["state"]
        self.assertFalse((s / "laps").exists())
        (s / "ctl.json").write_text(json.dumps({"paused": False}))
        out, err = p.communicate(timeout=20)
        self.assertEqual((ok, paused, p.returncode, err, len((s / "laps").read_text().split())),
                         (True, "paused", 0, "", 2))

    def test_signal_while_waiting(self):
        # 拍與拍之間（睡 interval）收到 SIGTERM：不起下一拍、直接 143，state 寫 stopped
        s = self.stack()
        self.loop({"run": self.count(), "max": 5, "interval_ms": 5000, "state": "state.json"})
        p = self.start({"AOS_STACK": str(s)})
        ok = wait_file(s / "laps")
        time.sleep(0.2)
        p.send_signal(signal.SIGTERM)
        out, err = p.communicate(timeout=20)
        st = json.loads((s / "state.json").read_text())
        self.assertEqual((ok, p.returncode, err, st["state"], st["code"], len((s / "laps").read_text().split())),
                         (True, 143, "", "stopped", 143, 1))


if __name__ == "__main__":
    unittest.main()
