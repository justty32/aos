"""Test the shared runner in agents_cmd waits in bounded segments, cleans up on expiry, polls short on the clock, and that subagent checks wait arguments before touching the daemon."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

sys.dont_write_bytecode = True
TOOL = Path(__file__).resolve().parents[1] / "_entry"
sys.path[:0] = [str(TOOL.parents[1]), str(TOOL.parents[2])]
import agents_cmd  # noqa: E402
import tool_io  # noqa: E402


class Raised(Exception):
    pass


class Runner(unittest.TestCase):
    def scope(self, times, poll=0):
        proc = mock.Mock(returncode=0, pid=12345)
        proc.poll.return_value = poll
        proc.communicate.side_effect = [subprocess.TimeoutExpired("fake", 1), (b"answer", b"")]
        patches = [mock.patch.object(agents_cmd.subprocess, "Popen", return_value=proc),
                   mock.patch.object(agents_cmd.time, "monotonic", side_effect=times),
                   mock.patch.object(agents_cmd, "kill_group"),
                   mock.patch.object(agents_cmd, "die", side_effect=lambda *a: (_ for _ in ()).throw(Raised(a))),
                   mock.patch.object(agents_cmd.tool_io, "workspace", return_value="/")]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        return proc

    def test_large_seconds_wait_in_segments(self):
        proc = self.scope([0, 0, 86400, 86400])
        self.assertEqual(agents_cmd.run(["aos-agent", "listen"], timeout_s=1e9), ("answer", None))
        self.assertTrue(all(c.kwargs["timeout"] <= 86400 for c in proc.communicate.call_args_list))
        self.assertIsNone(agents_cmd.child)
        proc.wait.assert_called_once()

    def test_expired_wait_cleans_up(self):
        proc = self.scope([0, 0, 2], poll=None)
        with self.assertRaises(Raised):
            agents_cmd.run(["aos-agent", "listen"], timeout_s=1)
        agents_cmd.kill_group.assert_called_once_with(proc)
        proc.wait.assert_called_once()
        self.assertIsNone(agents_cmd.child)

    def test_clock_wait_keeps_short_poll(self):
        proc = self.scope([0])
        with mock.patch.object(tool_io, "expired", return_value=False), mock.patch.object(tool_io, "deadline_after", return_value=(True, 10)):
            self.assertEqual(agents_cmd.run(["aos-agent", "listen"], timeout_cycles=10), ("answer", None))
        self.assertTrue(all(c.kwargs["timeout"] == .2 for c in proc.communicate.call_args_list))


class EntryChecks(unittest.TestCase):
    def test_seconds_checked_before_the_daemon(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        for value, code in [(1e9, "StackMissing"), (0, "ArgumentsBad"), (-1, "ArgumentsBad"), (float("inf"), "ArgumentsBad"),
                            (float("-inf"), "ArgumentsBad"), (float("nan"), "ArgumentsBad")]:
            with self.subTest(timeout_s=value):
                r = subprocess.run([str(TOOL)], input=json.dumps(dict(op="ask", name="kid", text="hello", timeout_s=value)),
                                   text=True, capture_output=True, env=env, timeout=10)
                self.assertEqual(r.returncode, 1)
                self.assertIn("error: " + code + " ", r.stdout)
                self.assertNotIn("Traceback", r.stderr)

    def test_cycles_checked(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        for value in (0, -3, 2 ** 63, True):
            r = subprocess.run([str(TOOL)], input=json.dumps(dict(op="listen", name="kid", timeout_cycles=value)),
                               text=True, capture_output=True, env=env, timeout=10)
            self.assertIn("error: ArgumentsBad", r.stdout, value)

    def test_kernel_alone_is_not_a_daemon(self):
        """11-12：只設 AOS_KERNEL＝aos-agent 找不到 daemon 表（ctl who）＝它的 DaemonMissing 接成自己的；什麼信都沒寄到 kernel。"""
        import tempfile
        proto = TOOL.parents[3]
        bins = [str(p) for p in sorted((proto / "impls").glob("*/bin"))] + [str(p) for p in sorted((proto / "cmd").glob("*/bin"))]
        with tempfile.TemporaryDirectory() as tmp:
            kernel, ws = os.path.join(tmp, "kernel"), os.path.join(tmp, "ws")
            os.makedirs(ws)
            for stage in ("tmp", "new", "cur"):
                os.makedirs(os.path.join(kernel, stage))
            env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
            env.update(PATH=os.pathsep.join(bins + [env["PATH"]]), AOS_KERNEL=kernel, AOS_STACK=tmp, AOS_WS=ws)
            r = subprocess.run([str(TOOL)], input=json.dumps(dict(op="ls")), text=True, capture_output=True, env=env, cwd=tmp, timeout=30)
            self.assertEqual(r.returncode, 1)
            self.assertTrue(r.stdout.startswith("subagent: error: DaemonMissing "), r.stdout)
            self.assertEqual(os.listdir(os.path.join(kernel, "new")), [])


if __name__ == "__main__":
    unittest.main()
