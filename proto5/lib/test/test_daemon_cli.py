"""aos-daemon boot／halt 的 CLI、家的三種來源、flock 探測與逾時契約（09-24 fix-r4 改名）。"""
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
        self.root = Path(temporary.name)
        self.home = self.root / "D"
        self.env = {k: v for k, v in os.environ.items() if k != "AOS_DAEMON_HOME"}

    def cli(self, *args, env=None, cwd=None):
        return subprocess.run([sys.executable, str(CLI), *map(str, args)],
                              capture_output=True, text=True, timeout=8,
                              env=self.env if env is None else env, cwd=cwd)

    def start(self, *args, env=None, cwd=None, home=None):
        daemon = subprocess.Popen([sys.executable, str(CLI), "boot", *map(str, args)],
                                  stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL, start_new_session=True,
                                  env=self.env if env is None else env, cwd=cwd)
        def cleanup():
            if daemon.poll() is None:
                daemon.kill()
            daemon.wait(timeout=6)
        self.addCleanup(cleanup)
        home = self.home if home is None else home
        wait_for(lambda: read_json(home / "state.json", {}).get("pid") == daemon.pid)
        return daemon

    def test_boot_and_halt_running_daemon(self):
        daemon = self.start("--target", self.home)
        result = self.cli("halt", "--target", self.home)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "stopped\n", ""))
        self.assertEqual(daemon.wait(timeout=6), 0)
        with self.assertRaises(ProcessLookupError):
            os.kill(daemon.pid, 0)
        self.assertFalse(aos_daemon.is_alive(self.home))

    def test_boot_and_halt_default_home_from_environment(self):
        env = dict(self.env, AOS_DAEMON_HOME=str(self.home))
        daemon = self.start(env=env, cwd=self.root)
        result = self.cli("halt", env=env, cwd=self.root)
        self.assertEqual((result.returncode, result.stdout), (0, "stopped\n"))
        self.assertEqual(daemon.wait(timeout=6), 0)

    def test_boot_and_halt_default_home_is_current_directory(self):
        self.home.mkdir()
        daemon = self.start(cwd=self.home)
        self.assertTrue((self.home / ".daemon.lock").exists())
        self.assertTrue(aos_daemon.is_alive(self.home))
        result = self.cli("halt", cwd=self.home)
        self.assertEqual((result.returncode, result.stdout), (0, "stopped\n"))
        self.assertEqual(daemon.wait(timeout=6), 0)

    def test_bare_daemon_is_usage_error(self):
        result = self.cli(cwd=self.root)
        self.assertEqual(result.returncode, 2)
        self.assertIn("usage: aos-daemon", result.stderr)
        self.assertIn("aos-daemon boot", result.stderr)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_halt_not_running_does_not_post_or_create_home(self):
        for existing in (False, True):
            with self.subTest(existing=existing):
                if existing:
                    self.home.mkdir()
                    aos_home.ensure_queue(self.home)
                    aos_home.post_request(self.home, "kept.json", {"kept": True})
                before = sorted(self.home.rglob("*")) if existing else []
                result = self.cli("halt", "--target", self.home)
                self.assertEqual((result.returncode, result.stdout), (0, "not running\n"))
                self.assertEqual(sorted(self.home.rglob("*")), before)
                self.assertEqual(self.home.exists(), existing)

    def test_help(self):
        for args in (("-h",), ("boot", "-h"), ("halt", "-h")):
            with self.subTest(args=args):
                result = self.cli(*args)
                self.assertEqual(result.returncode, 0)
                self.assertIn("--target" if args[0] != "-h" else "halt", result.stdout)
                self.assertNotIn("--home", result.stdout)
                self.assertIn("AOS_DAEMON_HOME" if args[0] != "-h" else "boot", result.stdout)

    def test_usage_errors(self):
        for args in (("unknown",), ("stop",), ("halt", "--wait-ms", "-1"),
                     ("halt", "--wait-ms", "nan"), ("halt", "--target", ""), ("boot", "--target", ""),
                     ("--home", str(self.home)), ("boot", "--home", str(self.home)), ("--wait-ms", "1")):
            with self.subTest(args=args):
                self.assertEqual(self.cli(*args).returncode, 2)

    def test_timeout_keeps_notification_and_names_source(self):
        self.home.mkdir()
        aos_home.ensure_queue(self.home)
        with (self.home / ".daemon.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            result = self.cli("halt", "--wait-ms", "0", env=dict(self.env, AOS_DAEMON_HOME=str(self.home)))
            self.assertEqual(result.returncode, 1)
            self.assertTrue(result.stderr.startswith("aos-daemon: Timeout:"))
            self.assertIn("未撤回", result.stderr)
            self.assertTrue(result.stderr.rstrip().endswith("（D＝%s，取自 AOS_DAEMON_HOME）" % self.home), result.stderr)
            requests = list((self.home / "requests").iterdir())
            self.assertEqual(len(requests), 1)
            self.assertTrue(requests[0].name.startswith("stop-"))
            self.assertEqual(json.loads(requests[0].read_text()), {"jsonrpc": "2.0", "method": "stop"})

    def test_boot_error_names_cwd_source(self):
        self.home.mkdir()
        aos_home.write_json(self.home / "info.json", {"_metainfo": {"_type": "kernel", "_version": 1}})
        result = self.cli("boot", cwd=self.home)
        self.assertEqual(result.returncode, 1)
        self.assertTrue(result.stderr.rstrip().endswith(
            "（D＝%s，取自 目前資料夾（沒給 --target、也沒設 AOS_DAEMON_HOME））" % self.home), result.stderr)

    def test_default_wait_and_parser(self):
        with mock.patch.object(aos_daemon, "stop", return_value=0) as stop:
            self.assertEqual(aos_daemon.main(["halt", "--target", str(self.home)]), 0)
            stop.assert_called_once_with(str(self.home), 30000)
        with mock.patch.object(aos_daemon, "run", return_value=0) as run:
            self.assertEqual(aos_daemon.main(["boot", "--target", str(self.home)]), 0)
            run.assert_called_once_with(str(self.home))
