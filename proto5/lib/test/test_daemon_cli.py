"""aos-daemon stop 的 CLI、flock 探測與逾時契約。"""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import aos_daemon
import aos_home
from _daemon_util import wait_for, read_json

CLI = Path(__file__).resolve().parents[2] / "cli" / "aos-daemon"


class DaemonCliTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="aos-daemon-cli-")
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name) / "D"

    def cli(self, *args, env=None):
        return subprocess.run([sys.executable, str(CLI), *map(str, args)],
                              capture_output=True, text=True, timeout=8, env=env)

    def test_stop_running_daemon(self):
        daemon = subprocess.Popen([sys.executable, str(CLI), "--home", str(self.home)],
                                  stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL, start_new_session=True)
        def cleanup():
            if daemon.poll() is None:
                daemon.kill()
            daemon.wait(timeout=6)
        self.addCleanup(cleanup)
        wait_for(lambda: read_json(self.home / "state.json", {}).get("pid") == daemon.pid)
        result = self.cli("stop", "--home", self.home)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "stopped\n", ""))
        self.assertEqual(daemon.wait(timeout=6), 0)
        with self.assertRaises(ProcessLookupError):
            os.kill(daemon.pid, 0)
        self.assertFalse(aos_daemon.is_alive(self.home))

    def test_stop_not_running_does_not_post_or_create_home(self):
        for existing in (False, True):
            with self.subTest(existing=existing):
                if existing:
                    self.home.mkdir()
                    aos_home.ensure_queue(self.home)
                    aos_home.post_request(self.home, "kept.json", {"kept": True})
                before = sorted(self.home.rglob("*")) if existing else []
                result = self.cli("stop", "--home", self.home)
                self.assertEqual((result.returncode, result.stdout), (0, "not running\n"))
                self.assertEqual(sorted(self.home.rglob("*")), before)
                self.assertEqual(self.home.exists(), existing)

    def test_help_and_stop_help(self):
        for args in (("-h",), ("stop", "-h")):
            with self.subTest(args=args):
                result = self.cli(*args)
                self.assertEqual(result.returncode, 0)
                self.assertIn("stop", result.stdout)
                self.assertIn("--home", result.stdout)

    def test_usage_errors(self):
        for args in (("unknown",), ("stop", "--wait-ms", "-1"),
                     ("stop", "--wait-ms", "nan"), ("--home", ""),
                     ("--wait-ms", "1")):
            with self.subTest(args=args):
                self.assertEqual(self.cli(*args).returncode, 2)

    def test_stop_uses_environment_home(self):
        env = dict(os.environ, AOS_DAEMON_HOME=str(self.home))
        result = self.cli("stop", env=env)
        self.assertEqual((result.returncode, result.stdout), (0, "not running\n"))
        self.assertFalse(self.home.exists())

    def test_timeout_keeps_notification(self):
        self.home.mkdir()
        aos_home.ensure_queue(self.home)
        with (self.home / ".daemon.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            result = self.cli("stop", "--home", self.home, "--wait-ms", "0")
            self.assertEqual(result.returncode, 1)
            self.assertTrue(result.stderr.startswith("aos-daemon: Timeout:"))
            self.assertIn("未撤回", result.stderr)
            requests = list((self.home / "requests").iterdir())
            self.assertEqual(len(requests), 1)
            self.assertTrue(requests[0].name.startswith("stop-"))
            self.assertEqual(json.loads(requests[0].read_text()), {"jsonrpc": "2.0", "method": "stop"})

    def test_default_wait_and_legacy_home_parser(self):
        with mock.patch.object(aos_daemon, "stop", return_value=0) as stop:
            self.assertEqual(aos_daemon.main(["stop", "--home", str(self.home)]), 0)
            stop.assert_called_once_with(str(self.home), 30000)
        with mock.patch.object(aos_daemon, "run", return_value=0) as run:
            self.assertEqual(aos_daemon.main(["--home", str(self.home)]), 0)
            run.assert_called_once_with(str(self.home))
