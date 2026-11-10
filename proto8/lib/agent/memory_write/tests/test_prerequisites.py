"""Verify hard-link failures preserve nodes and explain filesystem prerequisites."""
import contextlib
import errno
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HERE), str(HERE.parent), str(HERE.parents[1])]
import locking
import writing


class PrerequisiteTest(unittest.TestCase):
    def test_hard_link_errors_explain_requirement_and_clean_temporary(self):
        for code in sorted({errno.EPERM, errno.EOPNOTSUPP, errno.ENOTSUP, errno.EXDEV}):
            with self.subTest(errno=code), tempfile.TemporaryDirectory() as folder:
                target = Path(folder) / "node.md"
                out, err = io.StringIO(), io.StringIO()
                with patch.object(writing.os, "link", side_effect=OSError(code, "mock link failure")):
                    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                        with self.assertRaises(SystemExit) as stopped:
                            writing.write_text(str(target), b"# Node\n", exclusive=True)
                self.assertEqual(stopped.exception.code, 1)
                self.assertEqual(out.getvalue(), err.getvalue())
                self.assertIn("error: WriteFailed ", err.getvalue())
                self.assertIn("(memory_write needs a file system with hard links and atomic rename)", err.getvalue())
                self.assertEqual(list(Path(folder).iterdir()), [])

    def test_existing_node_keeps_original_error_and_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "node.md"
            target.write_bytes(b"# Original\n")
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                with self.assertRaises(SystemExit):
                    writing.write_text(str(target), b"# New\n", exclusive=True)
            self.assertIn("error: NodeExists ", err.getvalue())
            self.assertNotIn("needs a file system", err.getvalue())
            self.assertEqual(target.read_bytes(), b"# Original\n")
            self.assertEqual(list(Path(folder).iterdir()), [target])

    def test_acquire_waits_ten_seconds_and_command_timeout_allows_it(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(locking, "run_lock", return_value=(0, b"")) as run:
                with locking.with_lock(folder, "test"):
                    self.assertIn("10000", run.call_args.args[0])
            with patch.object(locking.subprocess, "Popen") as popen:
                popen.return_value.communicate.return_value = (b"", None)
                popen.return_value.returncode = 0
                locking.run_lock(["acquire", "--wait-ms", "10000", folder + "/"])
                self.assertGreater(popen.return_value.communicate.call_args.kwargs["timeout"], 10)


if __name__ == "__main__":
    unittest.main()
