"""Test shared child-group shutdown, escalation, reaping, and signal-handler delegation."""
import ast
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time
import unittest
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parents[3])]
import cmd_call


class KillGroup(unittest.TestCase):
    def test_term_ignoring_child_is_killed_and_reaped_within_grace(self):
        p = subprocess.Popen(
            [sys.executable, "-c", "import signal,time; "
             "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
             "print('ready', flush=True); time.sleep(60)"],
            start_new_session=True, stdout=subprocess.PIPE, text=True,
        )
        try:
            self.assertTrue(select.select([p.stdout], [], [], 5)[0], "child did not become ready")
            self.assertEqual(p.stdout.readline(), "ready\n")
            started = time.monotonic()
            cmd_call.kill_group(p)
            elapsed = time.monotonic() - started
            self.assertEqual(p.returncode, -signal.SIGKILL)
            self.assertLess(elapsed, 7, "shutdown exceeded the 5-second grace plus 2 seconds")
            with self.assertRaises(ProcessLookupError):
                os.kill(p.pid, 0)
            with self.assertRaises(ChildProcessError):
                os.waitpid(p.pid, os.WNOHANG)
        finally:
            if p.poll() is None:
                cmd_call.kill_group(p)
            p.stdout.close()

    def test_shared_stop_parameters_and_final_reap(self):
        p = Mock()
        with patch.object(cmd_call.process_group, "stop") as stop:
            cmd_call.kill_group(p)
        stop.assert_called_once_with(p, 5, 5, OSError)
        p.wait.assert_called_once_with()

    def test_signal_handler_uses_shared_shutdown(self):
        p = Mock()
        with patch.object(cmd_call, "child", p), patch.object(cmd_call, "kill_group") as stop:
            with self.assertRaises(SystemExit) as raised:
                cmd_call.on_term(signal.SIGTERM, None)
        stop.assert_called_once_with(p)
        self.assertEqual(raised.exception.code, 128 + signal.SIGTERM)

    def test_agent_def_signal_handler_uses_shared_shutdown(self):
        entry = Path(__file__).resolve().parents[1] / "agent_def" / "_entry"
        tree = ast.parse(entry.read_text(encoding="utf-8"))
        handler = next(node for node in tree.body
                       if isinstance(node, ast.FunctionDef) and node.name == "on_term")
        p, stop = Mock(), Mock()
        namespace = {"child": p, "kill_group": stop, "sys": sys}
        exec(compile(ast.Module(body=[handler], type_ignores=[]), str(entry), "exec"), namespace)
        with self.assertRaises(SystemExit) as raised:
            namespace["on_term"](signal.SIGTERM, None)
        stop.assert_called_once_with(p)
        self.assertEqual(raised.exception.code, 128 + signal.SIGTERM)

    def test_signal_handler_without_child_preserves_exit_code(self):
        with patch.object(cmd_call, "child", None):
            with self.assertRaises(SystemExit) as raised:
                cmd_call.on_term(signal.SIGINT, None)
        self.assertEqual(raised.exception.code, 130)


if __name__ == "__main__":
    unittest.main()
