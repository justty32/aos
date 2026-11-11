# Check --stack-lazy (11-11 tool-cells-lazy): the stack is made absolute and exported but not created; without it the stack is created as before.
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

BIN = Path(__file__).resolve().parents[1] / "bin" / "aos-exec"
ENV = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}


class StackLazy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aos-exec-lazy-")
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(os.path.realpath(self.tmp.name))
        tool = self.d / "t"
        tool.write_text("#!/bin/sh\necho \"$AOS_STACK\"\n")
        tool.chmod(0o755)

    def run_exec(self, *flags, stack="a/b"):
        env = dict(ENV, AOS_STACK=stack)
        return subprocess.run([str(BIN), *flags, "./t"], cwd=self.d, env=env, capture_output=True, text=True, timeout=10)

    def test_lazy_does_not_create(self):
        p = self.run_exec("--stack-lazy")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.strip(), str(self.d / "a" / "b") + "/")
        self.assertFalse((self.d / "a").exists())

    def test_lazy_with_stack_flag(self):
        p = self.run_exec("--stack-lazy", "--stack", "c")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.strip(), str(self.d / "c") + "/")
        self.assertFalse((self.d / "c").exists())

    def test_default_still_creates(self):
        p = self.run_exec()
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue((self.d / "a" / "b").is_dir())

    def test_lazy_takes_no_value(self):
        p = self.run_exec("--stack-lazy=1")
        self.assertEqual(p.returncode, 1)
        self.assertIn("ArgumentsBad", p.stderr)


if __name__ == "__main__":
    unittest.main()
