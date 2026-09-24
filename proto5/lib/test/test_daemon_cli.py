"""aos-daemon 的 CLI：boot／halt（家的三種來源、flock 探測、逾時契約）與 proto5-2 的 ls／scale／kill。"""
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
import aos_daemon_cli
import aos_home
from _daemon_util import DaemonCase, wait_for, read_json, write_json

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


class PoolCliTest(DaemonCase):
    """ls 偷看檔案；scale／kill 放單等回音。"""

    def cli(self, *args):
        env = {k: v for k, v in os.environ.items() if k != "AOS_DAEMON_HOME"}
        return subprocess.run([sys.executable, str(CLI), args[0], "--target", str(self.home), *map(str, args[1:])],
                              capture_output=True, text=True, timeout=15, env=env)

    def test_scale_creates_cli_pool_then_ls_and_kill(self):
        self.start()
        result = self.cli("scale", "--pool", "w", "--count", "2")
        self.assertEqual(result.returncode, 2)                      # 池不在要 --inst
        self.assertIn("--inst", result.stderr)
        target = self.targets(4, pool="w")
        result = self.cli("scale", "--pool", "w", "--count", "2", "--inst", target,
                          "--home", str(self.root / "h/{name}"))
        self.assertEqual((result.returncode, result.stdout), (0, "pool w count 0 -> 2 (ver 1)\n"), result.stderr)
        self.assertEqual(read_json(self.home / "pools/w/pool.json")["owner"], "cli")
        self.running("w", 2)
        (self.root / "h/1").mkdir(parents=True)
        write_json(self.root / "h/1/state.json", {"current": {"name": "x"}})
        out = self.cli("ls").stdout.splitlines()
        self.assertTrue(out[0].startswith("daemon running  pid %d  pools 1  children 2" % self.proc.pid), out)
        self.assertRegex(out[1], r"^w  owner cli  want 2  running 2  busy 1  pending 0  dead 0  "
                                 r"failed 0  killing 0  draining 0$")
        # restarting 是 running 的子集：>0 才在 running 那格寫「（含 restarting N）」（使用者代裁）
        view = {"pool": "w", "owner": "cli", "count": 2, "running": 2, "busy": 1, "restarting": 1,
                "pending": 0, "dead": 0, "failed": 0, "killing": 0, "draining": 0}
        self.assertEqual(aos_daemon_cli._table([aos_daemon_cli._summary_row(view)])[0],
                         "w  owner cli  want 2  running 2（含 restarting 1）  busy 1  pending 0  dead 0  "
                         "failed 0  killing 0  draining 0")
        self.assertIn("busy -", self.cli("ls", "--no-busy").stdout)
        lines = self.cli("ls", "--pool", "w").stdout.splitlines()
        self.assertEqual(len(lines), 4, lines)
        self.assertRegex(lines[2], r"^0  running  pid \d+  gen 1  idle  exits 0  streak 0  since \d\d:\d\d:\d\d$")
        self.assertRegex(lines[3], r"^1  running  pid \d+  gen 1  busy  exits 0")
        data = json.loads(self.cli("ls", "--pool", "w", "--json").stdout)
        self.assertEqual((data["daemon"]["running"], data["summary"]["running"], data["children"]["1"]["busy"]),
                         (True, 2, True))
        self.assertEqual(json.loads(self.cli("ls", "--json").stdout)["pools"]["w"]["busy"], 1)
        result = self.cli("kill", "--pool", "w", "1", "5")
        self.assertEqual((result.returncode, result.stdout), (0, "killed 1\nskipped 5 (not-member)\n"), result.stderr)
        wait_for(lambda: len(self.starts("w", 1)) == 2)
        self.assertEqual(self.cli("kill", "--pool", "w", "--all").stdout, "killed 0 1\n")
        self.assertEqual(self.cli("scale", "--pool", "w", "--count", "3", "--skip", "0").stdout,
                         "pool w count 2 -> 3 (ver 2)\n")
        wait_for(lambda: (self.summary("w") or {}).get("running") == 3 and self.kid("w", 0) is None)
        # --skip 省略＝沿用現在的
        self.assertEqual(self.cli("scale", "--pool", "w", "--count", "3").stdout, "pool w count 3 -> 3 (ver 2)\n")
        result = self.cli("kill", "--pool", "zz", "--all")
        self.assertEqual(result.returncode, 1)
        self.assertTrue(result.stderr.startswith("aos-daemon: NotFound:"), result.stderr)
        self.halt()
        out = self.cli("ls", "--pool", "w").stdout.splitlines()
        self.assertEqual(out[0], "daemon not running（以下是最後的摘要）")
        self.assertRegex(out[2], r"^1  pending  pid -  gen 3")

    def test_scale_owned_needs_force(self):
        self.start()
        target = self.targets(2)
        self.ok(self.scale(count=1, owner="/abs/K", target=target))
        result = self.cli("scale", "--pool", "p", "--count", "2")
        self.assertEqual(result.returncode, 1)
        self.assertTrue(result.stderr.startswith("aos-daemon: Owned:"), result.stderr)
        self.assertIn("aos-kernel cpu add", result.stderr)
        self.assertEqual(read_json(self.home / "pools/p/pool.json")["count"], 1)
        result = self.cli("scale", "--pool", "p", "--count", "2", "--force")
        self.assertEqual(result.stdout, "pool p count 1 -> 2 (ver 2)\n", result.stderr)
        self.assertEqual(read_json(self.home / "pools/p/pool.json")["owner"], "/abs/K")
        self.halt()

    def test_not_running_and_usage(self):
        result = self.cli("scale", "--pool", "p", "--count", "1", "--inst", "/x/{name}.json")
        self.assertEqual(result.returncode, 1)
        self.assertTrue(result.stderr.startswith("aos-daemon: NotRunning:"), result.stderr)
        self.assertEqual(list((self.home).iterdir()), [self.home / "info.json"])     # 沒放單
        out = self.cli("ls").stdout
        self.assertEqual(out, "daemon not running（以下是最後的摘要）  pools 0  children 0\n")
        result = self.cli("ls", "--pool", "p")
        self.assertEqual(result.returncode, 1)
        self.assertIn("NotFound", result.stderr)
        for args in (("kill", "--pool", "p"), ("kill", "--pool", "p", "--all", "1"), ("kill", "--pool", "p", "01"),
                     ("scale", "--pool", "p", "--count", "-1"), ("scale", "--pool", "p", "--count", "1", "--skip", "1,1"),
                     ("scale", "--pool", "../p", "--count", "1"), ("scale", "--count", "1"),
                     ("scale", "--pool", "p", "--count", "1", "--inst", "/x/a.json"), ("ls", "--pool", "a/b")):
            with self.subTest(args=args):
                self.assertEqual(self.cli(*args).returncode, 2)
