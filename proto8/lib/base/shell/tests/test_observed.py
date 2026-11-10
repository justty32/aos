"""Verify command ledgers preserve inner outcomes and block unwritable execution."""
import json
import os
from pathlib import Path
import subprocess
import signal
import time
import tempfile
import unittest

ENTRY = Path(__file__).resolve().parents[1] / "_entry"
PYTHON = ENTRY.parent.name == "run_python"


class ObservedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.stack = self.root / "stack"

    def run_tool(self, bash, python, *, stack=True, timeout=5):
        env = dict(os.environ, AOS_WS=str(self.root))
        env.pop("AOS_STACK", None)
        if stack:
            env["AOS_STACK"] = str(self.stack)
        args = {"code" if PYTHON else "command": python if PYTHON else bash,
                "timeout_s": timeout}
        return subprocess.run([str(ENTRY)], input=json.dumps(args), text=True,
                              capture_output=True, env=env, timeout=10)

    def rows(self):
        return [json.loads(line) for line in (self.stack / "observed.jsonl").read_text().splitlines()]

    def test_nonzero_inner_exit_and_raw_bytes(self):
        result = self.run_tool("printf abc; exit 7", "import sys; print('abc', end=''); sys.exit(7)")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[exit code 7]", result.stdout)
        rows = self.rows()
        self.assertEqual(rows[0]["kind"], "self")
        cmd = rows[-1]
        self.assertEqual((cmd["kind"], cmd["exit"], cmd["out_bytes"]), ("cmd", 7, 3))
        self.assertGreaterEqual(cmd["elapsed_ms"], 0)
        self.assertEqual(json.loads((self.stack / "interfaces.json").read_text())["aos-observed"]["file"], "observed.jsonl")

    def test_timeout_records_actual_signal_exit(self):
        result = self.run_tool("printf abc; sleep 5", "import time; print('abc', end='', flush=True); time.sleep(5)", timeout=.1)
        self.assertEqual(result.returncode, 1)
        self.assertIn("CommandFailed", result.stderr)
        cmd = self.rows()[-1]
        self.assertEqual(cmd["exit"], 143)
        self.assertEqual(cmd["out_bytes"], 3)

    def test_readonly_does_not_execute(self):
        self.stack.mkdir()
        self.stack.chmod(0o555)
        self.addCleanup(self.stack.chmod, 0o755)
        result = self.run_tool("touch marker", "from pathlib import Path; Path(%r).touch()" % str(self.root / "marker"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("LogFailed", result.stderr)
        self.assertEqual(len(result.stderr.splitlines()), 1)
        self.assertFalse((self.root / "marker").exists())
        self.assertFalse((self.stack / "main.py").exists())

    def test_external_term_records_once_and_reaps_inner(self):
        marker = self.root / "started"
        command = "printf abc; echo $$ > %s; exec sleep 30" % marker
        code = ("import os, time; from pathlib import Path; "
                "print('abc', end='', flush=True); Path(%r).write_text(str(os.getpid())); "
                "time.sleep(30)") % str(marker)
        env = dict(os.environ, AOS_WS=str(self.root), AOS_STACK=str(self.stack))
        args = {"code" if PYTHON else "command": code if PYTHON else command}
        proc = subprocess.Popen([str(ENTRY)], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, env=env)
        try:
            proc.stdin.write(json.dumps(args))
            proc.stdin.close()
            proc.stdin = None
            deadline = time.monotonic() + 5
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertTrue(marker.exists(), "inner process did not start")
            inner_pid = int(marker.read_text())
            proc.send_signal(signal.SIGTERM)
            _, stderr = proc.communicate(timeout=5)
            self.assertEqual(proc.returncode, 143, stderr)
            cmds = [row for row in self.rows() if row["kind"] == "cmd"]
            self.assertEqual(len(cmds), 1)
            self.assertEqual((cmds[0]["exit"], cmds[0]["out_bytes"]), (143, 3))
            with self.assertRaises(ProcessLookupError):
                os.kill(inner_pid, 0)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()

    def test_without_stack_runs_without_ledger(self):
        result = self.run_tool("printf ok", "print('ok')", stack=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok", result.stdout)
        self.assertFalse(list(self.root.rglob("observed.jsonl")))


if __name__ == "__main__":
    unittest.main()
