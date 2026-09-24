"""daemon.md 的真父子行程測試：握手、重拉、階梯、鎖與崩潰接手。"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import aos_client
import aos_home
import aos_daemon

CLI = Path(__file__).resolve().parents[2] / "cli"
PY = sys.executable

from _daemon_util import CHILD, CLOCK_DRIVER, wait_for, read_json


class DaemonTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aos-daemon-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / "D"
        self.home.mkdir()
        self.info = {"_metainfo": {"_type": "daemon", "_version": 1}, "poll_ms": 5,
                     "restart_delay_ms": 80, "stop_wait_ms": 80, "kill_wait_ms": 80}
        self.write(self.home / "info.json", self.info)
        self.child = self.root / "child.py"
        self.child.write_text(CHILD)
        self.proc = None
        self.groups = set()
        self.addCleanup(self.cleanup_groups)

    def write(self, path, value):
        aos_home.write_json(path, value)
        return str(path)

    def cleanup_groups(self):
        for pid in self.groups:
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def start(self, ready=True, controlled=False):
        log = open(self.root / "daemon.log", "ab")
        self.addCleanup(log.close)
        command = [PY, str(CLI / "aos-daemon"), "--home", str(self.home)]
        if controlled:
            self.write(self.root / "clock.json", 10)
            command = [PY, "-c", CLOCK_DRIVER, str(CLI.parent / "lib"), str(self.home),
                       str(self.root / "clock.json"), str(self.root / "clock-state.json"),
                       str(self.root / "signals.jsonl")]
        proc = subprocess.Popen(command,
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=log, start_new_session=True)
        self.proc = proc
        def cleanup():
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.cleanup_groups()
                    proc.kill()
            proc.wait(timeout=4)
        self.addCleanup(cleanup)
        if ready:
            wait_for(lambda: self.state().get("pid") == proc.pid)
        return proc

    def clock_state(self):
        return read_json(self.root / "clock-state.json", {})

    def advance(self, value):
        self.write(self.root / "clock.json", value)
        return wait_for(lambda: self.clock_state().get("clock") == value and self.clock_state())

    def stage(self, name="child", stage="stop"):
        return wait_for(lambda: self.clock_state().get("stages", {}).get(name, [None])[0] == stage
                        and self.clock_state()["stages"][name])

    def signals(self):
        path = self.root / "signals.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def state(self):
        return read_json(self.home / "state.json", {})

    def children(self):
        return self.state().get("children", {})

    def target(self, mode="normal", name="child"):
        ready = self.root / (name + ".ready")
        target = self.root / (name + ".json")
        self.write(target, {"argv": [PY, str(self.child), mode, str(ready)]})
        return str(target), ready

    def call(self, method, params=None, **kwargs):
        return aos_client.call(self.home, method, params, timeout_ms=6000, poll_ms=5, **kwargs)

    def spawn(self, target, name="child", restart=False):
        response = self.call("spawn", {"name": name, "target": target, "restart": restart})
        self.assertIn("result", response, response)
        pid = response["result"]["pid"]
        self.groups.add(pid)
        return pid

    def stop(self):
        aos_home.post_request(self.home, aos_client.new_name("stop"),
                              {"jsonrpc": "2.0", "method": "stop"})
        self.assertEqual(self.proc.wait(timeout=5), 0, (self.root / "daemon.log").read_text())
        self.assertEqual(self.children(), {})
        self.assertEqual(self.state()["pid"], 0)

    def test_spawn_real_cpu_idempotent_restart_update_and_name_taken(self):
        cpu = self.root / "cpu"
        cpu.mkdir()
        self.write(cpu / "info.json", {"_metainfo": {"_type": "exec_cpu", "_version": 1}, "poll_ms": 5})
        target = self.write(cpu / "inst.json", {"argv": [PY, str(CLI / "aos-cpu"), str(cpu)]})
        self.start()
        pid = self.spawn(target)
        wait_for(lambda: read_json(cpu / "state.json", {}).get("pid") == pid)
        self.assertEqual(self.spawn(target, restart=True), pid)
        self.assertTrue(self.children()["child"]["restart"])
        other, _ = self.target(name="different")
        error = self.call("spawn", {"name": "child", "target": other})["error"]
        self.assertEqual(error["data"]["code"], "NameTaken")
        result = aos_client.call(cpu, "aos-exec", {"target": str(cpu / "absent.json")}, timeout_ms=4000, poll_ms=5)
        self.assertEqual(result["result"]["kind"], "aos")
        self.stop()
        self.assertIsNone(read_json(cpu / "state.json")["current"])

    def test_children_have_own_group_same_session(self):
        self.start()
        target, ready = self.target()
        pid = self.spawn(target)
        child = wait_for(lambda: read_json(ready))
        self.assertEqual(child["pgid"], pid)
        self.assertEqual(child["sid"], os.getsid(self.proc.pid))
        self.assertNotEqual(child["pgid"], os.getpgid(self.proc.pid))
        self.stop()

    def test_nonzero_restart_and_target_reread(self):
        self.info["restart_delay_ms"] = 200
        self.write(self.home / "info.json", self.info)
        self.start(controlled=True)
        target, ready = self.target("exit7")
        original = self.spawn(target, restart=True)
        wait_for(lambda: self.children().get("child", {}).get("state") == "dead")
        dead = self.children()["child"]
        self.assertEqual(dead["last_exit"], 7)
        wait_for(lambda: self.clock_state().get("restarts", {}).get("child"))
        self.advance(10.199)
        self.assertEqual(self.children()["child"]["state"], "dead")
        self.target("normal")
        self.advance(10.201)
        new = wait_for(lambda: self.children().get("child", {}).get("pid") != original and
                       self.children().get("child", {}).get("state") == "running" and self.children()["child"])
        self.groups.add(new["pid"])
        self.assertEqual(new["exits"], 1)
        self.stop()

    def test_zero_exit_not_restarted(self):
        self.start()
        target, _ = self.target("exit0")
        self.spawn(target, restart=True)
        wait_for(lambda: not self.children())
        self.assertEqual(self.children(), {})
        self.stop()

    def test_kill_running_does_not_restart(self):
        self.start()
        target, ready = self.target()
        pid = self.spawn(target, restart=True)
        wait_for(lambda: ready.exists())
        self.assertEqual(self.call("kill", {"name": "child"})["result"]["pid"], pid)
        wait_for(lambda: not self.children())
        self.assertEqual(self.call("kill", {"name": "child"})["error"]["data"]["code"], "NotFound")
        self.stop()

    def test_kill_dead_cancels_restart(self):
        self.info["restart_delay_ms"] = 1000
        self.write(self.home / "info.json", self.info)
        self.start(controlled=True)
        target, _ = self.target("exit3")
        pid = self.spawn(target, restart=True)
        wait_for(lambda: self.children().get("child", {}).get("state") == "dead")
        self.assertEqual(self.call("kill", {"name": "child"})["result"]["pid"], pid)
        self.assertNotIn("child", self.children())
        self.stop()

    def test_spawn_dead_restarts_immediately(self):
        self.start(controlled=True)
        target, _ = self.target("exit3")
        first = self.spawn(target, restart=True)
        wait_for(lambda: self.clock_state().get("restarts", {}).get("child"))
        self.target("normal")
        self.assertNotEqual(self.spawn(target, restart=True), first)
        self.assertEqual(read_json(self.root / "clock.json"), 10)
        self.stop()

    def test_spawn_killing_rejected_and_kill_idempotent(self):
        self.start(controlled=True)
        target, ready = self.target("kill")
        pid = self.spawn(target)
        wait_for(ready.exists)
        self.call("kill", {"name": "child"})
        deadline = self.stage()
        self.assertEqual(self.call("spawn", {"name": "child", "target": target})["error"]["data"]["code"], "Killing")
        self.assertEqual(self.call("kill", {"name": "child"})["result"]["pid"], pid)
        self.advance(10.01)
        self.assertEqual(self.stage(), deadline)
        self.advance(11)
        self.stage(stage="term")
        self.advance(12)
        wait_for(lambda: not self.children())
        self.stop()

    def test_stop_pipe_stage(self):
        self.start()
        target, ready = self.target()
        self.spawn(target)
        wait_for(lambda: ready.exists())
        self.stop()
        self.assertFalse(Path(str(ready) + ".term").exists())

    def test_stop_term_stage(self):
        self.start(controlled=True)
        target, ready = self.target("term")
        pid = self.spawn(target)
        wait_for(ready.exists)
        aos_home.post_request(self.home, aos_client.new_name("stop"), {"jsonrpc": "2.0", "method": "stop"})
        self.stage()
        self.advance(10.079)
        self.assertEqual(self.signals(), [])
        self.advance(10.081)
        self.assertEqual(self.proc.wait(timeout=6), 0)
        self.assertEqual(self.signals(), [[pid, signal.SIGTERM, False, 10.081]])

    def test_stop_kill_stage_and_children_parallel(self):
        self.start(controlled=True)
        pids = set()
        for i in range(4):
            target, ready = self.target("kill", "child%d" % i)
            pids.add(self.spawn(target, "child%d" % i))
            wait_for(ready.exists)
        aos_home.post_request(self.home, aos_client.new_name("stop"), {"jsonrpc": "2.0", "method": "stop"})
        for i in range(4):
            self.assertEqual(self.stage("child%d" % i), ["stop", 10.08])
        self.advance(10.079)
        self.assertEqual(self.signals(), [])
        self.advance(10.081)
        for i in range(4):
            self.assertEqual(self.stage("child%d" % i, "term"), ["term", 10.161])
        self.assertEqual({tuple(row[:3]) for row in self.signals()},
                         {(pid, signal.SIGTERM, False) for pid in pids})
        self.advance(10.162)
        self.assertEqual(self.proc.wait(timeout=6), 0)
        self.assertEqual({tuple(row[:3]) for row in self.signals()[4:]},
                         {(pid, signal.SIGKILL, True) for pid in pids})
        self.assertEqual(self.children(), {})

    def test_epipe_skips_stop_wait(self):
        self.info.update(stop_wait_ms=1500, kill_wait_ms=60)
        self.write(self.home / "info.json", self.info)
        self.start(controlled=True)
        target, ready = self.target("epipe")
        pid = self.spawn(target)
        wait_for(ready.exists)
        aos_home.post_request(self.home, aos_client.new_name("stop"), {"jsonrpc": "2.0", "method": "stop"})
        self.assertEqual(self.stage(stage="term"), ["term", 10.06])
        self.assertEqual(self.signals(), [[pid, signal.SIGTERM, False, 10]])
        self.advance(10.061)
        self.assertEqual(self.proc.wait(timeout=6), 0)
        self.assertEqual(self.signals()[-1], [pid, signal.SIGKILL, True, 10.061])

    def test_lock_refuses_second_daemon_and_shared_probe(self):
        self.assertFalse(aos_daemon.is_alive(self.home))
        self.start()
        self.assertTrue(aos_daemon.is_alive(self.home))
        second = subprocess.run([PY, str(CLI / "aos-daemon"), "--home", str(self.home)],
                                stdin=subprocess.DEVNULL, capture_output=True, timeout=4)
        self.assertEqual(second.returncode, 1)
        self.assertIn(b"AlreadyRunning", second.stderr)
        self.stop()
        self.assertFalse(aos_daemon.is_alive(self.home))

    def test_signal_stops_daemon(self):
        self.start()
        target, ready = self.target()
        self.spawn(target)
        wait_for(lambda: ready.exists())
        self.proc.send_signal(signal.SIGINT)
        self.assertEqual(self.proc.wait(timeout=4), 0)
        self.assertEqual(self.children(), {})

    def test_spawn_validation_and_failure_do_not_register(self):
        self.start()
        target, _ = self.target()
        for params in ({}, {"name": "x", "target": "relative.json"},
                       {"name": "../x", "target": target}, {"name": "x", "target": target, "restart": 1}):
            self.assertEqual(self.call("spawn", params)["error"]["code"], -32602)
        for field in ("stdin", "stdout"):
            inst = self.write(self.root / (field + ".json"), {"argv": [PY, "-c", "pass"], field: ""})
            self.assertEqual(self.call("spawn", {"name": field, "target": inst})["error"]["code"], -32602)
        error = self.call("spawn", {"name": "missing", "target": str(self.root / "missing.json")})["error"]
        self.assertEqual(error["data"]["code"], "SpawnFailed")
        self.assertEqual(self.children(), {})
        self.stop()

    def test_requests_ack_and_reconciliation(self):
        aos_home.ensure_queue(self.home)
        original = "interrupted.json"
        aos_home.post_request(self.home, original, {"jsonrpc": "2.0", "id": "saved", "method": "spawn"})
        self.write(self.home / "state.json", {"pid": 0, "children": {}, "current": {
            "name": original, "id": "saved", "notify": False}})
        self.start()
        response = aos_client.wait_response(self.home, original, timeout_ms=3000, poll_ms=5)
        self.assertEqual(response["error"]["data"]["code"], "Interrupted")
        self.assertEqual(response["id"], "saved")
        ack = aos_client.ack(self.home, original)
        wait_for(lambda: not (self.home / "requests" / ack).exists())
        self.assertFalse((self.home / "responses" / original).exists())
        self.assertEqual(self.call("unknown")["error"]["code"], -32601)
        self.stop()

    def test_default_home_info_creation_and_bad_info(self):
        os.unlink(self.home / "info.json")
        self.start()
        self.assertEqual(read_json(self.home / "info.json")["_metainfo"]["_type"], "daemon")
        self.stop()
        self.write(self.home / "info.json", {"_metainfo": {"_type": "wrong", "_version": 1}})
        bad = subprocess.run([PY, str(CLI / "aos-daemon"), "--home", str(self.home)],
                             stdin=subprocess.DEVNULL, capture_output=True, timeout=4)
        self.assertEqual(bad.returncode, 1)
        self.assertIn(b"NotAHome", bad.stderr)

    def test_killed_daemon_restart_reaps_old_children_in_isolated_driver(self):
        from _daemon_util import ORPHAN_DRIVER
        target, ready = self.target("kill")
        driver = self.root / "restart-driver.py"
        driver.write_text(ORPHAN_DRIVER)
        proc = subprocess.Popen([PY, str(driver), str(CLI.parent / "lib"),
                                 str(CLI / "aos-daemon"), str(self.home), target, str(ready)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        def cleanup():
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT)  # 讓 driver 的 finally 收養並收屍
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child = read_json(ready, {}).get("pid")
                    if child is not None:
                        try:
                            os.killpg(child, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=4)
            proc.stdout.close()
            proc.stderr.close()
        self.addCleanup(cleanup)
        stdout, stderr = proc.communicate(timeout=14)
        self.assertEqual(proc.returncode, 0, stderr.decode())
        self.assertEqual(json.loads(stdout)["children"], {})

    def test_failure_before_child_table_write_closes_pipe_without_go(self):
        cpu = self.root / "untouched-cpu"
        cpu.mkdir()
        target = self.write(self.root / "cpu-inst.json", {"argv": [PY, str(CLI / "aos-cpu"), str(cpu)]})
        owner = aos_daemon.Daemon(self.home, self.info)
        self.addCleanup(owner.close)
        with mock.patch.object(owner, "save", side_effect=aos_home.HomeError("WriteFailed", "injected")):
            with self.assertRaises(aos_home.HomeError):
                owner.spawn({"name": "cpu", "target": target})
        proc = owner.procs["cpu"].process
        def cleanup():
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=4)
        self.addCleanup(cleanup)
        owner.close()
        self.assertEqual(proc.wait(timeout=4), 0)
        self.assertEqual(list(cpu.iterdir()), [])

    def test_stopping_rejects_spawn_and_kill_remains_available(self):
        self.start(controlled=True)
        target, ready = self.target("kill")
        self.spawn(target)
        wait_for(ready.exists)
        aos_home.post_request(self.home, aos_client.new_name("stop"), {"jsonrpc": "2.0", "method": "stop"})
        self.stage()
        error = self.call("spawn", {"name": "new", "target": target})["error"]
        self.assertEqual(error["data"]["code"], "Stopping")
        self.assertIn("result", self.call("kill", {"name": "child"}))
        self.advance(11)
        self.stage(stage="term")
        self.advance(12)
        self.assertEqual(self.proc.wait(timeout=6), 0)

    def test_stop_deadline_is_per_child_and_repeat_kill_does_not_reset(self):
        owner = aos_daemon.Daemon(self.home, self.info)
        owner.state["children"] = {
            "a": {"pid": 101, "state": "running"}, "b": {"pid": 102, "state": "running"}}
        with mock.patch.object(owner, "save"), mock.patch.object(owner, "_send"), \
             mock.patch("aos_daemon.time.monotonic", return_value=10):
            owner.kill({"name": "a"})
        with mock.patch.object(owner, "save"), mock.patch.object(owner, "_send"), \
             mock.patch("aos_daemon.time.monotonic", return_value=11):
            owner.kill({"name": "a"})
            owner.kill({"name": "b"})
        self.assertEqual(owner.stages["a"], ("stop", 10.08))
        self.assertEqual(owner.stages["b"], ("stop", 11.08))
        for name in ("a", "b"):
            handle = mock.Mock()
            handle.process.poll.return_value = None
            owner.procs[name] = handle
        with mock.patch("aos_daemon.time.monotonic", return_value=10.09), \
             mock.patch("aos_daemon._signal_pid") as send:
            owner.advance_stops()
            send.assert_called_once_with(101, signal.SIGTERM)
        with mock.patch("aos_daemon.time.monotonic", return_value=10.18), \
             mock.patch("aos_daemon._signal_pid") as send:
            owner.advance_stops()
            send.assert_called_once_with(101, signal.SIGKILL, group=True)
        self.assertEqual(owner.stages["b"], ("stop", 11.08))

    def test_exit_file_failure_does_not_turn_zero_exit_into_restart(self):
        owner = aos_daemon.Daemon(self.home, self.info)
        owner.children["child"] = {"pid": 123, "state": "running", "restart": True,
                                   "alive": True, "exits": 0, "last_exit": None}
        handle = mock.Mock()
        handle.process.poll.return_value = 0
        handle.finish.return_value = (1, "aos")
        owner.procs["child"] = handle
        with mock.patch.object(owner, "save"), mock.patch("aos_daemon._log"):
            owner.reap()
        self.assertEqual(owner.children, {})
        self.assertEqual(owner.restarts, {})
        self.assertEqual(owner.procs, {})

    def test_restart_target_missing_then_restored_retries(self):
        self.info["restart_delay_ms"] = 150
        self.write(self.home / "info.json", self.info)
        self.start(controlled=True)
        target, _ = self.target("exit9")
        old = self.spawn(target, restart=True)
        wait_for(lambda: self.children().get("child", {}).get("state") == "dead")
        wait_for(lambda: self.clock_state().get("restarts", {}).get("child"))
        Path(target).unlink()
        self.advance(10.151)
        wait_for(lambda: "SpawnFailed" in (self.root / "daemon.log").read_text())
        self.assertEqual(self.children()["child"]["state"], "dead")
        self.target("normal")
        self.advance(10.302)
        new = wait_for(lambda: self.children().get("child", {}).get("pid") != old and
                       self.children().get("child", {}).get("state") == "running" and self.children()["child"])
        self.groups.add(new["pid"])
        self.stop()

    def test_notification_and_broken_json_follow_shared_envelopes(self):
        self.start()
        name = aos_client.new_name("notification")
        aos_home.post_request(self.home, name, {"jsonrpc": "2.0", "method": "unknown"})
        wait_for(lambda: not (self.home / "requests" / name).exists())
        self.assertFalse((self.home / "responses" / name).exists())
        broken = self.home / "requests" / "broken.tmp"
        broken.write_bytes(b"{")
        os.link(broken, self.home / "requests" / "broken.json")
        broken.unlink()
        response = aos_client.wait_response(self.home, "broken.json", timeout_ms=3000, poll_ms=5)
        self.assertEqual(response["error"]["code"], -32700)
        aos_client.ack(self.home, "broken.json")
        self.stop()

    def test_home_resolution_precedence(self):
        with mock.patch.dict(os.environ, {"AOS_DAEMON_HOME": str(self.home), "HOME": str(self.root)}):
            self.assertEqual(aos_daemon.daemon_home(), str(self.home))
            self.assertEqual(aos_daemon.daemon_home(str(self.root / "explicit")), str(self.root / "explicit"))
        with mock.patch.dict(os.environ, {"HOME": str(self.root)}, clear=True):
            self.assertEqual(aos_daemon.daemon_home(), str(self.root / ".aos-daemon"))

    def test_missing_plain_target_is_spawn_failed(self):
        self.start()
        error = self.call("spawn", {"name": "missing", "target": str(self.root / "absent")})["error"]
        self.assertEqual((error["code"], error["data"]["code"]), (-32000, "SpawnFailed"))
        self.assertEqual(self.children(), {})
        self.stop()

    def test_directory_missing_dir_target_is_spawn_failed(self):
        self.start()
        error = self.call("spawn", {"name": "missing", "target": str(self.root),
                                    "dir_target": "absent.json"})["error"]
        self.assertEqual((error["code"], error["data"]["code"]), (-32000, "SpawnFailed"))
        self.assertEqual(self.children(), {})
        self.stop()
