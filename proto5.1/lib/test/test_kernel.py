"""Kernel 的真 daemon／runner／工作進程，所有家都在暫存目錄。"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import aos_daemon
import aos_inst
import aos_kernel as kernel

CLI = Path(__file__).resolve().parents[2] / "cli"


class KernelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.k = self.root / "K"
        self.d = self.root / "D"
        self.env = dict(os.environ, AOS_DAEMON_HOME=str(self.d), PYTHONDONTWRITEBYTECODE="1")
        self.patchenv = patch.dict(os.environ, self.env)
        self.patchenv.start()
        self.daemon = None
        self.log = None

    def tearDown(self):
        if self.daemon:
            if self.daemon.poll() is None:
                try:
                    aos_daemon.request("stop", timeout=9)
                except Exception:
                    self.daemon.terminate()
                try:
                    self.daemon.wait(timeout=9)
                except subprocess.TimeoutExpired:
                    self.daemon.kill()
                    self.daemon.wait()
            self.log.close()
        self.patchenv.stop()
        self.tmp.cleanup()

    def cli(self, *args, cwd=None):
        return subprocess.run([sys.executable, str(CLI / "aos-kernel"), *map(str, args)],
                              cwd=cwd, env=self.env, text=True, capture_output=True, timeout=15)

    def setup_kernel(self, ncpu=1, interval=80, quantum=1, bad_after=10):
        result = self.cli("init", self.k, "--ncpu", ncpu)
        self.assertEqual(result.returncode, 0, result.stderr)
        cfg = json.loads((self.k / "info.json").read_text())
        cfg.update(interval_ms=interval, quantum=quantum, bad_after=bad_after)
        (self.k / "info.json").write_text(json.dumps(cfg))

    def start(self, boot=True):
        self.log = open(self.root / "daemon-output", "w+")
        self.daemon = subprocess.Popen([sys.executable, str(CLI / "aos-daemon")],
                                       env=self.env, stdout=self.log, stderr=self.log)
        self.until(lambda: (self.d / "state.json").exists())
        if boot:
            result = self.cli("boot", self.k)
            self.assertEqual(result.returncode, 0, result.stderr)

    def until(self, predicate, seconds=8):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if predicate():
                return
            if self.daemon and self.daemon.poll() is not None:
                self.log.seek(0)
                self.fail("daemon 提早退出：" + self.log.read())
            time.sleep(.025)
        self.fail("條件逾時；state=" + ((self.k / "state.json").read_text() if self.k.exists() else "none"))

    def inst(self, name, code="pass", **extra):
        path = self.root / (name + ".json")
        path.write_text(json.dumps({"argv": [sys.executable, "-c", code], "cwd": str(self.root), **extra}))
        return path

    def state(self):
        return json.loads((self.k / "state.json").read_text())

    def test_init_cli_and_defaults(self):
        self.setup_kernel(3)
        root, cfg = kernel.load(self.k)
        self.assertEqual(root, self.k)
        self.assertEqual(cfg["ncpu"], 3)
        self.assertEqual(cfg["done_exit"], 100)
        self.assertEqual(cfg["wait_exit"], 101)
        self.assertEqual(len(list((self.k / "cpus").glob("*.lock"))), 3)
        self.assertEqual(self.cli("init", self.k, "--ncpu", 3).returncode, 1)
        self.assertEqual(self.cli("init", self.root / "bad", "--ncpu", 0).returncode, 2)

    def test_info_directives(self):
        self.setup_kernel()
        info = self.k / "info.json"
        obj = json.loads(info.read_text())
        obj["quantum"] = {"$ref": "vals.json#/q"}
        obj["_metainfo"] = {"_type": {"$env": "KTYPE"}, "_version": 1}
        (self.k / "vals.json").write_text('{"q":7}')
        info.write_text(json.dumps(obj))
        self.assertEqual(kernel.load(self.k, env={"KTYPE": "kernel"})[1]["quantum"], 7)

    def test_info_bool_is_not_integer(self):
        self.setup_kernel()
        obj = json.loads((self.k / "info.json").read_text())
        obj["ncpu"] = True
        (self.k / "info.json").write_text(json.dumps(obj))
        with self.assertRaisesRegex(kernel.KernelError, "FieldTypeMismatch"):
            kernel.load(self.k)

    def test_named_cli_errors(self):
        result = self.cli("ls", self.k)
        self.assertEqual(result.returncode, 1)
        self.assertIn("aos-kernel: NotAHome:", result.stderr)
        self.setup_kernel()
        (self.k / "info.json").write_text("{")
        self.assertIn("aos-kernel: JsonSyntax:", self.cli("ls", self.k).stderr)

    def test_add_full_inst_resolves_before_move(self):
        self.setup_kernel()
        source = self.root / "source.json"
        body = {"argv": {"$ref": str(self.root / "vals.json") + "#/argv"},
                "cwd": {"$opt": "mkdir", "$val": "future"},
                "envs": {"$opt": "clear", "$val": {"A": {"$env": "FROM"}}},
                "stdout": {"$opt": ["append", "mkdir"], "$val": "logs/o"},
                "stderr": {"$opt": "merge"}, "stdin": {"$opt": "inherit"}}
        (self.root / "vals.json").write_text(json.dumps({"argv": [sys.executable, "-c", "pass"], "body": body}))
        source.write_text(json.dumps({"$ref": "vals.json#/body"}))
        with patch.dict(os.environ, {"FROM": "resolved"}):
            self.assertEqual(kernel.add(self.k, source, "full"), "full")
        inst = aos_inst.load(self.k / "procs/full.json", self.k / "procs")
        self.assertTrue(inst["cwd_mkdir"])
        self.assertTrue(inst["envs_clear"])
        self.assertEqual(inst["envs"], {"A": "resolved"})
        self.assertEqual(inst["cwd"], str(self.root / "future"))
        self.assertEqual(inst["stdout"]["path"], str(self.root / "future/logs/o"))
        self.assertTrue(inst["stdout"]["append"])
        self.assertTrue(inst["stderr"]["merge"])
        self.assertTrue(inst["stdin"]["inherit"])

    def test_add_does_not_reject_missing_executable(self):
        self.setup_kernel()
        path = self.root / "source.json"
        path.write_text('{"argv":["./not-yet-installed"]}')
        self.assertEqual(kernel.add(self.k, path), "1")

    def test_add_invalid_duplicate_and_name(self):
        self.setup_kernel()
        path = self.inst("job")
        kernel.add(self.k, path, "one")
        with self.assertRaisesRegex(kernel.KernelError, "AlreadyRunning"):
            kernel.add(self.k, path, "one")
        for name in ("", "../escape", "..", "a\0b"):
            with self.assertRaises(kernel.KernelError):
                kernel.add(self.k, path, name)
        path.write_text('{"argv":[]}')
        with self.assertRaisesRegex(kernel.KernelError, "FieldTypeMismatch"):
            kernel.add(self.k, path, "bad")

    def test_boot_tick_done_and_ls_real_cli(self):
        self.setup_kernel()
        path = self.inst("done", "import sys; sys.exit(100)")
        self.assertEqual(self.cli("add", self.k, path, "--name", "done").returncode, 0)
        self.start(boot=False)
        self.assertEqual(self.cli("tick", cwd=self.k).returncode, 0)
        self.assertEqual(self.cli("boot", self.k).returncode, 0)
        self.until(lambda: (self.k / "procs/done/done.json").exists())
        result = self.cli("ls", self.k)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("done: done", result.stdout)

    def test_empty_tick_returns_zero(self):
        self.setup_kernel()
        self.start(boot=False)
        self.assertEqual(self.cli("tick", cwd=self.k).returncode, 0)
        self.assertEqual(self.state()["queue"], [])

    def test_rm_live_via_syscall(self):
        self.setup_kernel(interval=100)
        kernel.add(self.k, self.inst("job", "import sys; sys.exit(101)"), "job")
        self.start()
        self.until(lambda: any(cur and cur["pid"] == "job" for cur in self.state()["cpus"].values()))
        result = self.cli("rm", self.k, "job")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("removed job", result.stdout)
        self.assertFalse(any(cur and cur["pid"] == "job" for cur in self.state()["cpus"].values()))
        replies = list((self.k / "syscalls/done").glob("*.json"))
        self.assertEqual(len(replies), 1)
        self.assertTrue(json.loads(replies[0].read_text())["ok"])

    def test_wait_101_yields_before_quantum(self):
        self.setup_kernel(quantum=100)
        kernel.add(self.k, self.inst("a", "import sys; sys.exit(101)"), "a")
        kernel.add(self.k, self.inst("b", "open('seen-b','w').write('yes'); import sys; sys.exit(100)"), "b")
        self.start()
        self.until(lambda: (self.root / "seen-b").exists())
        self.until(lambda: (self.k / "procs/done/b.json").exists())
        self.assertFalse((self.k / "procs/bad/a.json").exists())

    def test_quantum_one_rotates_zero_exit(self):
        self.setup_kernel(quantum=1)
        for name in ("a", "b"):
            kernel.add(self.k, self.inst(name, "open('seen-%s','a').write('x')" % name), name)
        self.start()
        self.until(lambda: all((self.root / ("seen-" + n)).exists() for n in ("a", "b")))
        self.assertFalse(list((self.k / "procs/bad").glob("*.json")))

    def test_bad_after_survives_quantum_switches(self):
        self.setup_kernel(quantum=1, bad_after=4, interval=140)
        kernel.add(self.k, self.inst("a", "import sys; sys.exit(7)"), "a")
        kernel.add(self.k, self.inst("b", "import sys; sys.exit(101)"), "b")
        self.start()
        self.until(lambda: self.state()["waiting"].get("a", {}).get("bad_runs", 0) > 0)
        self.until(lambda: (self.k / "procs/bad/a.json").exists())
        self.assertFalse((self.k / "procs/bad/b.json").exists())

    def test_aos_error_retires_after_two_observed_runs(self):
        self.setup_kernel()
        path = self.inst("a", cwd=str(self.root / "absent"))
        kernel.add(self.k, path, "a")
        self.start()
        self.until(lambda: (self.k / "procs/bad/a.json").exists())

    def test_raw_queue_complete_directives_and_invalid(self):
        self.setup_kernel()
        source = self.inst("source", "import sys;sys.exit(100)")
        (self.k / "procs/good.json").write_text(json.dumps({"$ref": str(source)}))
        (self.k / "procs/broken.json").write_text('{"argv":false}')
        self.start()
        self.until(lambda: (self.k / "procs/done/good.json").exists())
        self.assertTrue((self.k / "procs/bad/broken.json").exists())

    def test_duplicate_cpu_state_rejected(self):
        self.setup_kernel(2)
        st = self.state()
        cur = {"pid": "same", "runs_at": 0, "seen_runs": 0}
        st["cpus"] = {"0": cur, "1": cur}
        (self.k / "state.json").write_text(json.dumps(st))
        self.assertIn("FieldTypeMismatch", self.cli("ls", self.k).stderr)

    def test_two_ticks_are_serialized(self):
        self.setup_kernel()
        with kernel._lock(self.k / ".kernel.lock"):
            self.assertEqual(self.cli("tick", cwd=self.k).returncode, 0)

    def test_false_snapshot_cannot_switch_a_running_slot(self):
        self.setup_kernel(interval=300, quantum=1)
        kernel.add(self.k, self.inst("a", "open('started','w').write('yes'); import time; time.sleep(1)"), "a")
        self.start(boot=False)
        self.assertEqual(kernel.tick(self.k), 0)
        self.until(lambda: (self.root / "started").exists())
        kernel.add(self.k, self.inst("b"), "b")
        snapshot = aos_daemon.read_state()
        entry = snapshot["runs"][str(self.k / "cpus/0.json")]
        entry.update(running=False, runs=1, last_exit=0, last_kind="child")
        with patch.object(aos_daemon, "read_state", return_value=snapshot), patch.object(aos_daemon, "request") as request:
            self.assertEqual(kernel.tick(self.k), 0)
            request.assert_not_called()
        self.assertEqual(self.state()["cpus"]["0"]["pid"], "a")
        self.assertTrue((self.k / "procs/b.json").exists())

    def test_running_snapshot_requests_yield_then_next_tick_switches(self):
        self.setup_kernel(interval=0, quantum=1)
        kernel.add(self.k, self.inst("a", "open('started','a').write('x'); import time; time.sleep(.4)"), "a")
        self.start(boot=False)
        kernel.tick(self.k)
        self.until(lambda: (self.root / "started").exists())
        kernel.add(self.k, self.inst("b"), "b")
        snapshot = aos_daemon.read_state()
        entry = snapshot["runs"][str(self.k / "cpus/0.json")]
        entry.update(running=True, runs=1, last_exit=0, last_kind="child")
        with patch.object(aos_daemon, "read_state", return_value=snapshot), patch.object(aos_daemon, "request") as request:
            kernel.tick(self.k)
            request.assert_not_called()
        self.assertEqual(self.state()["cpus"]["0"]["pid"], "a")
        self.assertEqual((self.k / "cpus/0.json.lock").read_bytes(), b"Y")
        self.until(lambda: not aos_daemon.read_state()["runs"][str(self.k / "cpus/0.json")]["running"])
        before = (self.root / "started").read_text()
        time.sleep(.15)
        self.assertEqual((self.root / "started").read_text(), before)
        # 重跑 tick 恢復，包括上次 kernel 若在寫 Y 後結束的情況。
        kernel.tick(self.k)
        self.assertEqual(self.state()["cpus"]["0"]["pid"], "b")
        self.assertEqual((self.k / "cpus/0.json.lock").read_bytes(), b"")

    def test_cancelled_swap_clears_yield_under_slot_lock(self):
        self.setup_kernel()
        path = self.k / "cpus/0.json"
        kernel._yield_intent(path, True)
        self.start(boot=False)
        kernel.tick(self.k)
        self.assertEqual(Path(str(path) + ".lock").read_bytes(), b"")

    def test_remove_failure_keeps_yield_and_assignment(self):
        self.setup_kernel()
        kernel.add(self.k, self.inst("a"), "a")
        kernel.add(self.k, self.inst("b"), "b")
        st = self.state()
        st["cpus"]["0"] = {"pid": "a", "runs_at": 0, "seen_runs": 0}
        st["queue"] = ["b"]
        path = self.k / "cpus/0.json"
        os.replace(self.k / "procs/a.json", path)
        entry = {"runs": 1, "last_exit": 0, "last_kind": "child", "running": False}
        with patch.object(aos_daemon, "request", side_effect=aos_daemon.DaemonError("NotRunning", "gone")):
            with self.assertRaises(aos_daemon.DaemonError):
                kernel._schedule(self.k, kernel.load(self.k)[1], st, {str(path): entry}, [])
        self.assertEqual(st["cpus"]["0"]["pid"], "a")
        self.assertTrue((self.k / "procs/b.json").exists())
        self.assertEqual(Path(str(path) + ".lock").read_bytes(), b"Y")

    def test_done_exit_zero_disables_retirement(self):
        self.setup_kernel()
        info = self.k / "info.json"
        obj = json.loads(info.read_text())
        obj["done_exit"] = 0
        info.write_text(json.dumps(obj))
        self.assertEqual(kernel.load(self.k)[1]["done_exit"], 0)
        kernel.add(self.k, self.inst("a", "open('ran','a').write('x')"), "a")
        self.start()
        self.until(lambda: (self.root / "ran").exists() and len((self.root / "ran").read_text()) >= 3)
        self.assertFalse((self.k / "procs/done/a.json").exists())

    def test_new_numeric_names_queue_in_numeric_order(self):
        self.setup_kernel()
        st = self.state()
        for name in ("10", "2", "1", "word"):
            kernel.add(self.k, self.inst("job"), name)
        kernel._queue(self.k, st, [])
        self.assertEqual(st["queue"], ["1", "2", "10", "word"])

    def test_long_jobs_three_procs_two_cpus_never_overlap_or_term(self):
        self._long_jobs(15)

    def test_zero_interval_long_jobs_do_not_starve(self):
        self._long_jobs(0)

    def _long_jobs(self, interval):
        self.setup_kernel(2, interval=interval, quantum=1)
        for name in ("a", "b", "c"):
            code = """import fcntl, os, signal, time
from pathlib import Path
name = %r
f = open(name + '.active', 'a')
try:
    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    open('overlap', 'a').write(name)
    raise
signal.signal(signal.SIGTERM, lambda *a: (open('unexpected-term', 'a').write(name), exit(77)))
open(name + '.runs', 'a').write('s')
time.sleep(.22)
open(name + '.runs', 'a').write('d')
""" % name
            kernel.add(self.k, self.inst(name, code), name)
        self.start()
        self.until(lambda: all((self.root / (n + ".runs")).exists() and
                               (self.root / (n + ".runs")).read_text().count("d") >= 3 for n in ("a", "b", "c")), seconds=12)
        self.assertFalse((self.root / "overlap").exists())
        self.assertFalse((self.root / "unexpected-term").exists())
        self.assertIn("cpu", (self.k / "kernel.log").read_text())
        st = self.state()
        names = [cur["pid"] for cur in st["cpus"].values() if cur]
        self.assertEqual(len(names), len(set(names)))


if __name__ == "__main__":
    unittest.main()
