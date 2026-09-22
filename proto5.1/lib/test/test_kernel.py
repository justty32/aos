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
import aos_exec
import aos_inst
import aos_kernel as kernel

CLI = Path(__file__).resolve().parents[2] / "cli"


class KernelTests(unittest.TestCase):
    def setUp(self):
        build = CLI.parent / ".build"
        build.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=build)
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
        if not boot:
            # 只保存 boot 的 daemon 家，手動 tick 案例不啟動 kernel runner。
            with patch.object(aos_daemon, "request"):
                kernel.boot(self.k)
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
        self.assertEqual(list((self.k / "cpus").glob("*.lock")), [])
        self.assertFalse(cfg["kill_tree"])
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
        self.until(lambda: any(cur and cur["name"] == "job" for cur in self.state()["cpus"].values()))
        result = self.cli("rm", self.k, "job")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("removed job", result.stdout)
        self.assertFalse(any(cur and cur["name"] == "job" for cur in self.state()["cpus"].values()))
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
        cur = {"name": "same", "runs_at": 0, "seen_runs": 0}
        st["cpus"] = {"0": cur, "1": cur}
        (self.k / "state.json").write_text(json.dumps(st))
        self.assertIn("FieldTypeMismatch", self.cli("ls", self.k).stderr)

    def test_two_ticks_are_serialized(self):
        self.setup_kernel()
        with kernel._lock(self.k / ".kernel.lock"):
            self.assertEqual(self.cli("tick", cwd=self.k).returncode, 0)

    def runner_states(self):
        return {n: kernel._run(aos_daemon.read_state()["runs"].get(str(self.k / "cpus" / (str(n) + ".json"))))
                for n in range(kernel.load(self.k)[1]["ncpu"])}

    def test_swap_busy_two_second_job_blocks_other_cpu_at_zero_interval(self):
        self.setup_kernel(2, interval=0, quantum=1)
        kernel.add(self.k, self.inst("x", "open('x-starts','a').write('s'); import time; time.sleep(2)"), "x")
        self.start(boot=False)
        kernel.tick(self.k)
        target = str(self.k / "procs/x.json")
        # CPU1 的 idle 在 interval=0 也會短暫 busy/null，合法擋住所有候選；
        # 先 hold 它，讓這個案例只驗 X 忙碌時不能跨 CPU 重疊。
        idle_home = Path(aos_daemon.read_state()["runs"][str(self.k / "cpus/1.json")]["home"])
        idle_control = idle_home / "ctl.json"
        idle_control.write_text('{"op":"hold"}')
        self.until(lambda: self.runner_states()[1].get("held", False))
        def x_busy_again():
            status = self.runner_states()[0]
            return status["busy"] and status["target"] == target and status["runs"] >= 1
        self.until(x_busy_again)
        # Y 留在 CPU0，避免 pass 在下一次觀察前用完量子，又合法換回 X。
        kernel.add(self.k, self.inst("y", "import time; time.sleep(2)"), "y")
        before = aos_daemon.read_state()["runs"]
        kernel.tick(self.k)
        self.assertEqual(self.state()["cpus"]["0"]["name"], "y")
        self.assertIsNone(self.state()["cpus"]["1"])
        self.assertEqual(aos_daemon.read_state()["runs"], before)
        self.assertTrue((self.k / "cpus/0.json").is_symlink())
        self.assertEqual((self.k / "cpus/0.json").resolve(), self.k / "procs/y.json")
        self.assertTrue(self.runner_states()[0]["busy"])
        for _ in range(10):
            kernel.tick(self.k)
            states = self.runner_states()
            self.assertEqual(states[0]["target"], target)
            self.assertTrue(states[0]["busy"])
            self.assertFalse(states[1]["busy"] and states[1]["target"] == target)
            self.assertIsNone(self.state()["cpus"]["1"])
            time.sleep(.025)
        def migrated():
            kernel.tick(self.k)
            return self.state()["cpus"]["1"] is not None
        self.until(migrated)
        self.assertEqual(self.state()["cpus"]["1"]["name"], "x")
        idle_control.unlink()
        self.until(lambda: self.runner_states()[1]["busy"] and self.runner_states()[1]["target"] == target)
        self.assertFalse(self.runner_states()[0]["busy"] and self.runner_states()[0]["target"] == target)

    def test_busy_null_blocks_assignment_and_missing_run_is_unknown(self):
        self.setup_kernel()
        kernel.add(self.k, self.inst("x"), "x")
        home = self.root / "runner"
        home.mkdir()
        entry = {"home": str(home)}
        runs = {str(self.k / "cpus/0.json"): entry}
        st = self.state()
        kernel._queue(self.k, st, [])
        kernel._schedule(self.k, kernel.load(self.k)[1], st, runs, [])
        self.assertIsNone(st["cpus"]["0"])
        status = {"busy": True, "target": None, "runs": 3, "last_kind": "child", "last_exit": 0}
        (home / "run.json").write_text(json.dumps(status))
        kernel._schedule(self.k, kernel.load(self.k)[1], st, runs, [])
        self.assertIsNone(st["cpus"]["0"])
        status["busy"] = False
        (home / "run.json").write_text(json.dumps(status))
        kernel._schedule(self.k, kernel.load(self.k)[1], st, runs, [])
        self.assertEqual(st["cpus"]["0"]["name"], "x")

    def test_old_completion_and_busy_last_exit_not_counted_for_new_proc(self):
        self.setup_kernel(quantum=100)
        kernel.add(self.k, self.inst("x"), "x")
        home = self.root / "runner"
        home.mkdir()
        st = self.state()
        st["cpus"]["0"] = {"name": "x", "runs_at": 0, "seen_runs": 0}
        runs = {str(self.k / "cpus/0.json"): {"home": str(home)}}
        for busy, target in ((False, "old.json"), (True, str(self.k / "procs/x.json"))):
            (home / "run.json").write_text(json.dumps({"busy": busy, "target": target, "runs": 1,
                                                        "last_target": "old.json", "last_kind": "child", "last_exit": 100}))
            kernel._schedule(self.k, kernel.load(self.k)[1], st, runs, [])
            self.assertEqual(st["cpus"]["0"]["seen_runs"], 0)
            self.assertFalse((self.k / "procs/done/x.json").exists())

    def test_busy_last_target_completion_counted_once(self):
        self.setup_kernel(quantum=100, bad_after=2)
        kernel.add(self.k, self.inst("x"), "x")
        home = self.root / "runner"
        home.mkdir()
        st = self.state()
        st["cpus"]["0"] = {"name": "x", "runs_at": 0, "seen_runs": 0}
        runs = {str(self.k / "cpus/0.json"): {"home": str(home)}}
        status = {"busy": True, "target": None, "last_target": str(self.k / "procs/x.json"),
                  "runs": 3, "last_kind": "child", "last_exit": 7}
        (home / "run.json").write_text(json.dumps(status))
        cfg = kernel.load(self.k)[1]
        kernel._schedule(self.k, cfg, st, runs, [])
        self.assertEqual(st["cpus"]["0"]["bad_runs"], 1)
        self.assertEqual(st["cpus"]["0"]["seen_runs"], 3)
        self.assertNotIn("bad_exit", st["cpus"]["0"])
        kernel._schedule(self.k, cfg, st, runs, [])
        self.assertEqual(st["cpus"]["0"]["bad_runs"], 1)
        self.assertFalse((self.k / "procs/bad/x.json").exists())
        status.update(runs=4, last_exit=100)
        (home / "run.json").write_text(json.dumps(status))
        kernel._schedule(self.k, cfg, st, runs, [])
        self.assertTrue((self.k / "procs/done/x.json").exists())

    def test_queue_does_not_rewrite_frozen_inst(self):
        self.setup_kernel()
        kernel.add(self.k, self.inst("x"), "x")
        path = self.k / "procs/x.json"
        before = path.stat()
        st = self.state()
        for _ in range(3):
            kernel._queue(self.k, st, [])
        after = path.stat()
        self.assertEqual(after.st_ino, before.st_ino)
        self.assertEqual(after.st_mtime_ns, before.st_mtime_ns)

    def test_failed_syscall_has_flat_error(self):
        self.setup_kernel()
        (self.k / "syscalls/no.json").write_text('{"op":"rm","name":"missing"}')
        kernel._syscalls(self.k, kernel.load(self.k)[1], self.state(), {}, [])
        reply = json.loads((self.k / "syscalls/done/no.json").read_text())
        self.assertEqual(reply, {"ok": False, "code": "NotRunning", "msg": "找不到行程：missing"})

    def test_boot_pins_daemon_home_for_tick_ls_rm(self):
        self.setup_kernel()
        self.start(boot=False)
        self.assertEqual(json.loads((self.k / "info.json").read_text())["daemon"], str(self.d))
        with patch.dict(os.environ, {"AOS_DAEMON_HOME": str(self.root / "different")}):
            self.assertEqual(kernel.tick(self.k), 0)
            self.assertIn("daemon=%s" % self.daemon.pid, kernel.status(self.k))
            with self.assertRaisesRegex(kernel.KernelError, "ReadFailed"):
                kernel.remove(self.k, "missing", timeout=0)
        call = json.loads(next((self.k / "syscalls").glob("*.json")).read_text())
        self.assertEqual(call, {"op": "rm", "name": "missing"})
        info = self.d / "info.json"
        original = info.read_text()
        try:
            info.write_text('{"_metainfo":{"_type":"kernel","_version":1}}')
            for action in (lambda: kernel.tick(self.k), lambda: kernel.status(self.k),
                           lambda: kernel.remove(self.k, "missing", timeout=0)):
                with self.assertRaisesRegex(aos_daemon.DaemonError, "NotAHome"):
                    action()
        finally:
            info.write_text(original)

    def test_boot_preserves_whole_info_reference_and_local_daemon_binding(self):
        self.setup_kernel()
        info = self.k / "info.json"
        source = self.k / "settings.json"
        settings = json.loads(info.read_text())
        source.write_text(json.dumps(settings))
        info.write_text('{"$ref":"settings.json"}')
        self.start(boot=False)
        self.assertEqual(json.loads(info.read_text()), {"$ref": "settings.json", "daemon": str(self.d)})
        settings["quantum"] = 9
        source.write_text(json.dumps(settings))
        cfg = kernel.load(self.k)[1]
        self.assertEqual(cfg["daemon"], str(self.d))
        self.assertEqual(cfg["quantum"], 9)
        self.assertEqual(kernel.tick(self.k), 0)

    def test_failed_boot_keeps_original_daemon_binding(self):
        self.setup_kernel()
        self.start()
        info = self.k / "info.json"
        original = json.loads(info.read_text())
        before = info.stat()
        with self.assertRaisesRegex(aos_daemon.DaemonError, "AlreadyRunning"):
            kernel.boot(self.k)
        self.assertEqual(info.stat().st_ino, before.st_ino)
        self.assertEqual(json.loads(info.read_text()), original)
        other = self.root / "stopped-daemon"
        (other / "requests/done").mkdir(parents=True)
        (other / "info.json").write_text('{"_metainfo":{"_type":"daemon","_version":1}}')
        (other / "state.json").write_text('{"pid":0,"runs":{}}')
        with patch.dict(os.environ, {"AOS_DAEMON_HOME": str(other)}):
            with self.assertRaisesRegex(aos_daemon.DaemonError, "NotRunning"):
                kernel.boot(self.k)
            self.assertEqual(info.stat().st_ino, before.st_ino)
            self.assertEqual(json.loads(info.read_text()), original)
            # 檢查時還在、交件時已停：失敗後也恢復原 binding。
            with patch.object(aos_daemon, "_active", return_value=True), patch.object(
                    aos_daemon, "request", side_effect=aos_daemon.DaemonError("NotRunning", "已停止")):
                with self.assertRaisesRegex(aos_daemon.DaemonError, "NotRunning"):
                    kernel.boot(self.k)
            self.assertEqual(json.loads(info.read_text()), original)
            self.assertIn("daemon=%s" % self.daemon.pid, kernel.status(self.k))

    def test_unbooted_kernel_does_not_select_daemon_from_environment(self):
        self.setup_kernel()
        self.assertIn("daemon=None", kernel.status(self.k))
        for action in (lambda: kernel.tick(self.k), lambda: kernel.remove(self.k, "x", timeout=0)):
            with self.assertRaisesRegex(kernel.KernelError, "NotRunning"):
                action()

    def test_idle_resolve_then_slot_assignment_keeps_selected_inst(self):
        self.setup_kernel()
        kernel.add(self.k, self.inst("x", "open('unexpected-x','w').write('ran')"), "x")
        slot = self.k / "cpus/0.json"
        self.assertTrue(slot.is_symlink())
        selected = []
        def before_load(target):
            selected.append(target)
            kernel._assign(slot, self.k / "procs/x.json")
        result = aos_exec.run_target(str(slot), on_target=before_load)
        self.assertEqual(result, (0, "child"))
        self.assertEqual(selected, [str(self.k / "idle.json")])
        self.assertFalse((self.root / "unexpected-x").exists())
        self.assertEqual(slot.resolve(), self.k / "procs/x.json")

    def test_unknown_runs_between_baseline_and_assignment_do_not_inflate_failures(self):
        self.setup_kernel(bad_after=2)
        cfg = kernel.load(self.k)[1]
        # 基線後 idle 完成一次，接著 X 第一次失敗：只能確定最後那一次屬於 X。
        cur = {"name": "x", "runs_at": 0, "seen_runs": 0}
        status = {"busy": False, "target": str(self.k / "procs/x.json"), "runs": 2,
                  "last_kind": "child", "last_exit": 7}
        kernel._observe(cfg, cur, status)
        self.assertEqual(cur["bad_runs"], 1)
        self.assertIsNone(kernel._retire(cfg, cur, status))
        kernel._observe(cfg, cur, status)
        self.assertEqual(cur["bad_runs"], 1)
        status["runs"] = 3
        kernel._observe(cfg, cur, status)
        self.assertEqual(kernel._retire(cfg, cur, status), "bad")

    def test_kill_tree_bool_and_forwarding(self):
        self.setup_kernel()
        path = self.k / "info.json"
        cfg = json.loads(path.read_text())
        cfg["kill_tree"] = 1
        path.write_text(json.dumps(cfg))
        with self.assertRaisesRegex(kernel.KernelError, "kill_tree"):
            kernel.load(self.k)
        cfg["kill_tree"] = True
        path.write_text(json.dumps(cfg))
        self.start(boot=False)
        with patch.object(aos_daemon, "request", return_value={"home": str(self.root)}) as request:
            kernel.boot(self.k)
            self.assertTrue(request.call_args.kwargs["kill_tree"])
            kernel._schedule(self.k, kernel.load(self.k)[1], self.state(), {}, [])
            self.assertTrue(request.call_args.kwargs["kill_tree"])

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
        names = [cur["name"] for cur in st["cpus"].values() if cur]
        self.assertEqual(len(names), len(set(names)))


if __name__ == "__main__":
    unittest.main()
