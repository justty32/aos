"""〔B10-01〕aos7-audit 入口：用法／help 不留檔，未預期例外不出 traceback。"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOP = Path(__file__).resolve().parents[3]
ENTRY = TOP / "modules/audit/aos7-audit"


class TestAuditEntry(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="fx1-c-entry-aos7-audit-")
        self.addCleanup(self.tmp.cleanup)
        self.cwd = Path(self.tmp.name)
        self.home = self.cwd / "home"
        self.home.mkdir()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("AOS")}
        self.env.pop("PYTHONDONTWRITEBYTECODE", None)
        self.env.update(HOME=str(self.home), TMPDIR=str(self.cwd))

    def cli(self, *argv, entry=ENTRY):
        return subprocess.run([sys.executable, str(entry), *argv], cwd=self.cwd, env=self.env,
                              capture_output=True, text=True, timeout=10)

    def snapshot(self):
        return sorted((str(p.relative_to(self.cwd)), p.stat().st_mtime_ns)
                      for p in self.cwd.rglob("*"))

    def test_cli_help_is_read_only(self):
        before = self.snapshot()
        for flag in ("--help", "-h"):
            r = self.cli(flag)
            self.assertEqual((r.returncode, r.stderr), (0, ""), r)
            self.assertTrue(r.stdout.strip())
        self.assertEqual(self.snapshot(), before)

    def test_cli_bad_args_are_one_line_and_read_only(self):
        before = self.snapshot()
        r = self.cli("--no-such-option")
        self.assertEqual(r.returncode, 2, r)
        self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)
        self.assertTrue(r.stderr.startswith("aos7-audit: "), r.stderr)
        self.assertIn("。例：", r.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_cli_unexpected_exception_is_unsure(self):
        # Inject into main before any work, through the real executable boundary.
        code = """import runpy, sys
entry = sys.argv[1]
def fail(frame, event, arg):
    if event == 'call' and frame.f_code.co_name == 'main':
        sys.settrace(None)
        raise RuntimeError('fx1-test-key')
    return fail
sys.argv = [entry]
sys.settrace(fail)
runpy.run_path(entry, run_name='__main__')
"""
        r = subprocess.run([sys.executable, "-B", "-c", code, str(ENTRY)], cwd=self.cwd,
                           env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 3, r)
        self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)
        self.assertTrue(r.stderr.startswith("aos7-audit: 不確定："), r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertNotIn("fx1-test-key", r.stderr)


    def test_cli_child_exit_code_is_preserved(self):
        r = self.cli("--", sys.executable, "-B", "-c", "raise SystemExit(7)")
        self.assertEqual(r.returncode, 7, r)
        self.assertEqual(r.stderr, "")
        r = self.cli("--", "fx1-command-does-not-exist")
        self.assertEqual(r.returncode, 127, r)


if __name__ == "__main__":
    unittest.main()
