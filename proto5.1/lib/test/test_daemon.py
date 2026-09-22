"""真 daemon／runner、檔案收件顺序與停止清理。"""
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

import aos_daemon as d

CLI = Path(__file__).resolve().parents[2] / "cli"
FIELDS = {"pid", "target", "args", "state", "home"}


def wait_for(fn, timeout=5):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = fn()
        if value:
            return value
        time.sleep(.02)
    raise AssertionError("等待條件逾時")


def alive(pid):
    try:
        return Path("/proc/%d/stat" % pid).read_text().split(") ", 1)[1].split()[0] != "Z"
    except FileNotFoundError:
        return False


class DaemonTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root / "D"
        self.env = dict(os.environ, AOS_DAEMON_HOME=str(self.home), PYTHONDONTWRITEBYTECODE="1")
        self.proc = None
        self.runners = []

    def tearDown(self):
        if self.proc is not None:
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=13)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait()
            self.proc.stdout.close()
            self.proc.stderr.close()
        for pid in self.runners:
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        self.tmp.cleanup()

    def start(self):
        self.proc = subprocess.Popen([sys.executable, str(CLI / "aos-daemon")], env=self.env,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        wait_for(lambda: (self.home / "state.json").exists() or self.proc.poll() is not None)
        self.assertIsNone(self.proc.poll(), self.proc.stderr.read() if self.proc.poll() is not None else "")

    def inst(self, code="pass", name="x.json"):
        target = self.root / name
        target.write_text(json.dumps({"argv": [sys.executable, "-c", code]}))
        return str(target)

    def req(self, op, target=None, args=None, kill_tree=False):
        result = d.request(op, target, args, home=self.home, kill_tree=kill_tree)
        if op == "add":
            self.runners.append(result["pid"])
        return result

    def state(self):
        return d.read_state(self.home)

    def status(self, target):
        entry = self.state()["runs"].get(target)
        if not entry:
            return {}
        try:
            return json.loads(Path(entry["home"], "run.json").read_text())
        except FileNotFoundError:
            return {}

    def ctl(self, *args):
        return subprocess.run([sys.executable, str(CLI / "aos-daemon-ctl"), *args], env=self.env,
                              capture_output=True, text=True, timeout=17)

    def test_home_environment_and_default(self):
        with patch.dict(os.environ, {"AOS_DAEMON_HOME": str(self.home)}):
            self.assertEqual(d.home(), str(self.home))
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(d.home().endswith("/.aos-daemon"))

    def test_missing_home_named_error(self):
        out = self.ctl("ls")
        self.assertEqual(out.returncode, 1)
        self.assertTrue(out.stderr.startswith("aos-daemon: NotAHome:"))

    def test_non_directory_home(self):
        self.home.write_text("x")
        out = subprocess.run([sys.executable, str(CLI / "aos-daemon")], env=self.env, capture_output=True, text=True)
        self.assertEqual(out.returncode, 1)
        self.assertIn("NotAHome", out.stderr)

    def test_lifecycle_state_and_remove(self):
        self.start()
        target = self.inst("raise SystemExit(7)")
        added = self.req("add", target, ["--interval-ms", "100"])
        self.assertEqual(set(added), FIELDS)
        state = wait_for(lambda: (e if (e := self.status(target)) and e["runs"] else None))
        self.assertEqual((state["last_exit"], state["last_kind"]), (7, "child"))
        final = self.req("remove", target)
        self.assertEqual(final["state"], "stopping")
        self.assertFalse(json.loads(Path(final["home"], "run.json").read_text())["busy"])
        self.assertFalse(alive(added["pid"]))
        self.assertEqual(self.state()["runs"], {})

    def test_duplicate_daemon_is_rejected(self):
        self.start()
        out = subprocess.run([sys.executable, str(CLI / "aos-daemon")], env=self.env, capture_output=True, text=True)
        self.assertEqual(out.returncode, 1)
        self.assertIn("AlreadyRunning", out.stderr)
        self.assertIsNone(self.proc.poll())

    def test_killed_daemon_runner_finishes_current_and_restart_refuses_live_runner(self):
        self.start()
        begun, finished = self.root / "begun", self.root / "finished"
        target = self.inst("from pathlib import Path; import time; Path(%r).touch(); "
                           "time.sleep(2); Path(%r).touch()" % (str(begun), str(finished)))
        entry = self.req("add", target, ["--interval-ms", "0"])
        wait_for(begun.exists)
        self.proc.kill()
        self.assertEqual(self.proc.wait(timeout=3), -signal.SIGKILL)
        out = subprocess.run([sys.executable, str(CLI / "aos-daemon")], env=self.env,
                             capture_output=True, text=True, timeout=3)
        self.assertEqual(out.returncode, 1)
        self.assertIn("AlreadyRunning", out.stderr)
        wait_for(lambda: not alive(entry["pid"]))
        self.assertTrue(finished.exists())
        state = json.loads(Path(entry["home"], "run.json").read_text())
        self.assertEqual((state["runs"], state["busy"], state["last_exit"]), (1, False, 0))

    def test_start_rejects_live_runner_even_without_daemon_state(self):
        path = self.home / "runners/old/run.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"pid": os.getpid()}))
        out = subprocess.run([sys.executable, str(CLI / "aos-daemon")], env=self.env,
                             capture_output=True, text=True, timeout=3)
        self.assertEqual(out.returncode, 1)
        self.assertIn("AlreadyRunning", out.stderr)
        self.assertFalse((self.home / "state.json").exists())

    def test_idle_state_is_not_rewritten(self):
        self.start()
        path = self.home / "state.json"
        before = path.stat().st_mtime_ns
        time.sleep(.5)
        self.assertEqual(path.stat().st_mtime_ns, before)

    def test_daemon_creates_identity_and_ctl_rejects_wrong_home(self):
        self.start()
        path = self.home / "info.json"
        self.assertEqual(json.loads(path.read_text()), {"_metainfo": {"_type": "daemon", "_version": 1}})
        path.write_text('{"_metainfo":{"_type":"kernel","_version":1}}')
        out = self.ctl("ls")
        self.assertEqual(out.returncode, 1)
        self.assertIn("NotAHome", out.stderr)

    def test_requests_directories_alone_are_not_a_home(self):
        (self.home / "requests/done").mkdir(parents=True)
        out = self.ctl("ls")
        self.assertEqual(out.returncode, 1)
        self.assertIn("NotAHome", out.stderr)

    def test_duplicate_target_and_absent_remove(self):
        self.start()
        target = self.inst()
        self.req("add", target)
        for op, path, code in (("add", target, "AlreadyRunning"), ("remove", target + ".json", "NotRunning")):
            with self.assertRaises(d.DaemonError) as caught:
                self.req(op, path)
            self.assertEqual(caught.exception.code, code)

    def test_missing_json_can_appear_later(self):
        self.start()
        target = str(self.root / "later.json")
        self.req("add", target, ["--interval-ms", "100"])
        wait_for(lambda: self.status(target).get("last_kind") == "aos")
        self.inst("raise SystemExit(12)", "later.json")
        wait_for(lambda: self.status(target).get("last_exit") == 12)

    def test_stop_publishes_empty_state_and_removes_pid(self):
        self.start()
        self.req("add", self.inst())
        self.assertEqual(self.req("stop"), {"stopped": True})
        self.assertEqual(self.proc.wait(timeout=3), 0)
        self.assertEqual(self.state(), {"pid": 0, "runs": {}})
        self.assertFalse((self.home / "daemon.pid").exists())
        self.assertFalse(alive(self.runners[0]))
        self.assertEqual(self.proc.stderr.read(), b"")

    def test_term_also_stops_runner(self):
        self.start()
        self.req("add", self.inst())
        self.proc.terminate()
        self.assertEqual(self.proc.wait(timeout=13), 0)
        self.assertFalse(alive(self.runners[0]))

    def test_ctl_all_commands_and_ls_does_not_enqueue(self):
        self.start()
        target = self.inst()
        out = self.ctl("add", target, "--interval-ms", "100", "--stop-exit", "100")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.runners.append(json.loads(out.stdout)["pid"])
        before = sorted((self.home / "requests/done").iterdir())
        self.assertEqual(self.ctl("ls").returncode, 0)
        self.assertEqual(sorted((self.home / "requests/done").iterdir()), before)
        self.assertEqual(self.ctl("rm", target).returncode, 0)
        self.assertEqual(self.ctl("stop").returncode, 0)

    def test_ctl_usage_errors(self):
        for args in (("pause",), ("add", "x.json", "--timeout-ms", "-1"), ("add", "x.json", "--status-fd", "3")):
            self.assertEqual(self.ctl(*args).returncode, 2)

    def test_request_names_and_original_fields(self):
        self.start()
        target = self.inst()
        self.req("add", target)
        paths = list((self.home / "requests/done").glob("*.json"))
        self.assertEqual(len(paths), 1)
        self.assertRegex(paths[0].name, r"^\d+-\d+-[0-9a-f]{4}\.json$")
        reply = json.loads(paths[0].read_text())
        self.assertEqual((reply["op"], reply["target"], reply["ok"]), ("add", target, True))
        self.assertFalse((self.home / "requests" / paths[0].name).exists())

    def test_raw_bad_request_returns_named_error(self):
        self.start()
        for n, payload, code in ((1, "{", "JsonSyntax"), (2, "[]", "FieldTypeMismatch"),
                                  (3, '{"op":"restart"}', "FieldTypeMismatch"),
                                  (4, '{"op":"add","target":"relative.json"}', "FieldTypeMismatch"),
                                  (5, '{"op":"add","target":"/x.json","args":["--status-fd","3"]}', "FieldTypeMismatch"),
                                  (6, '{"op":"add","target":"/x.json","kill_tree":1}', "FieldTypeMismatch")):
            name = "%d.json" % n
            (self.home / "requests" / name).write_text(payload)
            done = self.home / "requests/done" / name
            wait_for(done.exists)
            reply = json.loads(done.read_text())
            self.assertFalse(reply["ok"])
            self.assertEqual(set(reply), {"ok", "code", "msg"})
            self.assertEqual(reply["code"], code)
        self.assertIsNone(self.proc.poll())

    def test_raw_ls_rejected(self):
        self.start()
        path = self.home / "requests/raw-ls.json"
        path.write_text('{"op":"ls","note":"preserved"}')
        done = path.parent / "done" / path.name
        wait_for(done.exists)
        reply = json.loads(done.read_text())
        self.assertEqual(set(reply), {"ok", "code", "msg"})
        self.assertFalse(reply["ok"])
        self.assertEqual(reply["code"], "FieldTypeMismatch")

    def test_done_published_before_unlink(self):
        path = self.root / "requests/r.json"
        (path.parent / "done").mkdir(parents=True)
        path.write_text('{"op":"ls"}')
        original = Path.unlink
        seen = []
        def unlink(p, *args, **kwargs):
            if p == path:
                seen.append(json.loads((p.parent / "done" / p.name).read_text())["ok"])
            return original(p, *args, **kwargs)
        with patch.object(Path, "unlink", unlink):
            d._finish_request(path, {"op": "ls"}, True, {})
        self.assertEqual(seen, [True])

    def test_done_publish_failure_keeps_original(self):
        path = self.root / "requests/r.json"
        (path.parent / "done").mkdir(parents=True)
        path.write_text('{"op":"ls"}')
        with patch.object(d, "_write", side_effect=OSError("full")):
            with self.assertRaises(OSError):
                d._finish_request(path, {"op": "ls"}, True, {})
        self.assertTrue(path.exists())

    def test_existing_done_only_deletes_original(self):
        self.start()
        name = "replay.json"
        done = self.home / "requests/done" / name
        done.write_text('{"op":"stop","ok":true,"result":{}}')
        src = self.home / "requests" / name
        src.write_text('{"op":"stop"}')
        wait_for(lambda: not src.exists())
        self.assertIsNone(self.proc.poll())
        self.assertEqual(json.loads(done.read_text())["result"], {})

    def test_not_running_after_stop(self):
        self.start()
        self.req("stop")
        self.proc.wait(timeout=3)
        out = self.ctl("stop")
        self.assertEqual(out.returncode, 1)
        self.assertIn("NotRunning", out.stderr)
        self.assertEqual(self.ctl("ls").returncode, 0)

    def test_read_state_errors(self):
        (self.home / "requests/done").mkdir(parents=True)
        (self.home / "info.json").write_text('{"_metainfo":{"_type":"daemon","_version":1}}')
        path = self.home / "state.json"
        for content, code in ((None, "ReadFailed"), (b"\xff", "JsonSyntax"), (b'{"pid":true,"runs":{}}', "FieldTypeMismatch")):
            if content is not None:
                path.write_bytes(content)
            with self.assertRaises(d.DaemonError) as caught:
                self.state()
            self.assertEqual(caught.exception.code, code)

    def test_stop_kills_term_ignoring_child_and_grandchild(self):
        self.start()
        marker = self.root / "pids"
        code = ("import os,signal,time; from pathlib import Path; "
                "signal.signal(signal.SIGTERM,signal.SIG_IGN); child=os.fork(); "
                "f=open(%r,'a'); f.write(str(os.getpid())+'\\n'); f.close(); time.sleep(60)" % str(marker))
        self.req("add", self.inst(code), kill_tree=True)
        wait_for(lambda: marker.exists() and len(marker.read_text().splitlines()) == 2)
        pids = [int(x) for x in marker.read_text().splitlines()]
        self.req("stop")
        self.proc.wait(timeout=3)
        for pid in pids:
            wait_for(lambda pid=pid: not alive(pid))

    def test_default_ten_second_fallback_kills_runner_group(self):
        self.start()
        target = self.inst()
        entry = self.req("add", target, ["--interval-ms", "10000"])
        wait_for(lambda: self.status(target).get("runs", 0) >= 1)
        os.kill(entry["pid"], signal.SIGSTOP)
        started = time.monotonic()
        self.req("remove", target)
        elapsed = time.monotonic() - started
        self.assertGreaterEqual(elapsed, 9.8)
        self.assertLess(elapsed, 12)
        self.assertFalse(alive(entry["pid"]))

    def test_explicit_home_propagates_to_runner(self):
        self.env["AOS_DAEMON_HOME"] = str(self.root / "wrong")
        self.proc = subprocess.Popen([sys.executable, str(CLI / "aos-daemon"), "--home", str(self.home)],
                                     env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        wait_for(lambda: (self.home / "state.json").exists())
        marker = self.root / "actual-home"
        target = self.inst("import os; from pathlib import Path; Path(%r).write_text(os.environ['AOS_DAEMON_HOME'])" % str(marker))
        self.req("add", target)
        wait_for(marker.exists)
        self.assertEqual(marker.read_text(), str(self.home))

    def test_disk_failure_still_cleans_all_runners(self):
        script = ("import aos_daemon as d; from pathlib import Path; original=d._write\n"
                  "def fail(path,obj):\n"
                  " if (Path(d.home())/'fail').exists(): raise OSError('disk failed')\n"
                  " return original(path,obj)\n"
                  "d._write=fail\nraise SystemExit(d.main())\n")
        self.proc = subprocess.Popen([sys.executable, "-c", script], env=self.env,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        wait_for(lambda: (self.home / "state.json").exists())
        for i in range(2):
            self.req("add", self.inst(name="io%d.json" % i))
        (self.home / "fail").touch()
        (self.home / "requests/fail.json").write_text('{"op":"stop"}')
        self.assertEqual(self.proc.wait(timeout=13), 1)
        self.assertTrue(all(not alive(pid) for pid in self.runners))
        error = self.proc.stderr.read().decode()
        self.assertIn("aos-daemon: ReadFailed:", error)
        self.assertNotIn("Traceback", error)

    def test_signal_during_spawn_stops_newly_registered_runner(self):
        (self.home / "requests/done").mkdir(parents=True)
        original = subprocess.Popen
        with open(self.home / "daemon.log", "ab") as log:
            daemon = d._Daemon(self.home, log)
            def spawn(*args, **kwargs):
                child = original(*args, **kwargs)
                daemon.stop()
                return child
            with patch.object(d.subprocess, "Popen", spawn):
                entry = daemon.add(self.inst(), [])
            self.runners.append(entry["pid"])
            self.assertEqual(entry["state"], "stopping")
            wait_for(lambda: (daemon.reap() or not daemon.jobs))
            self.assertFalse(alive(entry["pid"]))

    def test_stop_all_runners_in_parallel(self):
        self.start()
        for i in range(2):
            target = self.inst(name="x%d.json" % i)
            entry = self.req("add", target, ["--interval-ms", "10000"])
            wait_for(lambda: self.status(target).get("runs", 0) >= 1)
            os.kill(entry["pid"], signal.SIGSTOP)
        started = time.monotonic()
        self.req("stop")
        self.assertGreaterEqual(time.monotonic() - started, 9.8)
        self.assertLess(time.monotonic() - started, 12)
        self.proc.wait(timeout=3)
        self.assertTrue(all(not alive(pid) for pid in self.runners))

    def test_kill_tree_five_second_fallback(self):
        self.start()
        target = self.inst()
        entry = self.req("add", target, ["--interval-ms", "10000"], kill_tree=True)
        wait_for(lambda: self.status(target).get("runs", 0) >= 1)
        os.kill(entry["pid"], signal.SIGSTOP)
        start = time.monotonic()
        self.req("remove", target)
        self.assertGreaterEqual(time.monotonic() - start, 4.8)
        self.assertLess(time.monotonic() - start, 7)
        self.assertFalse(alive(entry["pid"]))

    def test_ctl_kill_tree_flag_and_fresh_runner_home(self):
        self.start()
        target = self.inst()
        out = self.ctl("add", target, "--kill-tree")
        self.assertEqual(out.returncode, 0, out.stderr)
        entry = json.loads(out.stdout)
        self.runners.append(entry["pid"])
        self.assertEqual(Path(entry["home"]).parent, self.home / "runners")
        self.req("remove", target)
        Path(entry["home"], "ctl.json").write_text('{"op":"hold"}')
        new = self.req("add", target)
        self.assertNotEqual(new["home"], entry["home"])
        wait_for(lambda: self.status(target).get("runs", 0) >= 1)

    def test_kill_tree_rejects_non_boolean(self):
        self.start()
        target = self.inst()
        for value in (None, 1, "false", {}):
            with self.assertRaises(d.DaemonError) as caught:
                self.req("add", target, kill_tree=value)
            self.assertEqual(caught.exception.code, "FieldTypeMismatch")
        self.assertEqual(self.state()["runs"], {})

    def test_symlink_target_stays_slot_path(self):
        self.start()
        target = self.inst()
        slot = self.root / "slot.json"
        slot.symlink_to(target)
        entry = self.req("add", str(slot))
        self.assertEqual(entry["target"], str(slot))
        wait_for(lambda: self.status(str(slot)).get("target") == target)
        self.req("remove", str(slot))

    def test_default_stop_second_term_ends_child(self):
        self.start()
        marker = self.root / "started"
        target = self.inst("from pathlib import Path; import time; Path(%r).touch(); time.sleep(30)" % str(marker))
        self.req("add", target)
        wait_for(marker.exists)
        start = time.monotonic()
        self.req("stop")
        self.assertGreaterEqual(time.monotonic() - start, 4.8)
        self.assertLess(time.monotonic() - start, 7)
        self.proc.wait(timeout=3)


if __name__ == "__main__":
    unittest.main()
