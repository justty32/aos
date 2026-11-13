"""Test aos-tree-start: refuses inherited AOS_* (names only, never values), --force warns and goes on, a clean shell execs aos-exec ARGS (a fake aos-exec on PATH; nothing real starts)."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[3]
CMD = PROTO / "cmd" / "aos-tree-start" / "bin" / "aos-tree-start"
FAKE = """#!/bin/sh
# fake aos-exec: prints its argv, its cwd and the AOS_* names it got
echo "argv: $*"
echo "cwd: $(pwd)"
echo "aos: $(env | grep -o '^AOS_[A-Za-z0-9_]*' | sort | tr '\\n' ' ')"
exit 7
"""


class TreeStart(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="tree-start-"))
        (self.tmp / "bin").mkdir()
        (self.tmp / "bin" / "aos-exec").write_text(FAKE)
        (self.tmp / "bin" / "aos-exec").chmod(0o755)
        (self.tmp / "tree").mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_cmd(self, *args, path=None, **aos):
        env = {"PATH": "%s:/usr/bin:/bin" % (path or self.tmp / "bin"), "HOME": str(self.tmp), "PYTHONDONTWRITEBYTECODE": "1"}
        env.update(aos)
        p = subprocess.run([sys.executable, str(CMD), *args], env=env, cwd=self.tmp / "tree",
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        return p.returncode, p.stdout.decode(), p.stderr.decode()

    def test_clean_execs_aos_exec_root(self):
        rc, out, err = self.run_cmd("root", AOS_HOME=str(self.tmp / "tree"))
        self.assertEqual((rc, err), (7, ""))   # 7＝fake aos-exec 的結束碼：是 exec 過去、照轉
        self.assertIn("argv: root\n", out)
        self.assertIn("cwd: %s\n" % (self.tmp / "tree"), out)
        self.assertIn("aos: AOS_HOME \n", out)

    def test_inherited_refused_names_only(self):
        secret = "/elsewhere/ws/.stack/procs/eca_main"
        rc, out, err = self.run_cmd("root", AOS_HOME="/elsewhere", AOS_STACK=secret, AOS_DAEMON="/elsewhere/ws/.stack", AOS_WS="/w")
        self.assertEqual((rc, out), (1, ""))
        lines = err.splitlines()
        self.assertEqual(len(lines), 1, err)
        self.assertTrue(lines[0].startswith("aos-tree-start: error: EnvBad AOS_DAEMON, AOS_STACK, AOS_WS set in this shell"), err)
        self.assertNotIn(secret, err)
        self.assertNotIn("/elsewhere", err)

    def test_any_aos_name_counts(self):
        rc, out, err = self.run_cmd("root", AOS_SOME_NEW_VAR="x")
        self.assertEqual(rc, 1)
        self.assertIn("EnvBad AOS_SOME_NEW_VAR set", err)

    def test_force_warns_and_passes_args(self):
        rc, out, err = self.run_cmd("--force", "--", "--stack", "stacks/root", "defs", AOS_STACK="/x")
        self.assertEqual(rc, 7)
        self.assertEqual(err, "aos-tree-start: warning: starting with inherited AOS_STACK (--force)\n")
        self.assertIn("argv: --stack stacks/root defs\n", out)
        self.assertIn("aos: AOS_STACK \n", out)

    def test_no_aos_exec(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        rc, out, err = self.run_cmd("root", path=empty)
        self.assertEqual(rc, 1)
        self.assertTrue(err.startswith("aos-tree-start: error: CommandMissing "), err)

    def test_help_and_bad_flag(self):
        rc, out, err = self.run_cmd("--help", AOS_STACK="/x")
        self.assertEqual((rc, err), (0, ""))
        self.assertTrue(out.startswith("aos-tree-start - "))
        rc, out, err = self.run_cmd("--bogus")
        self.assertEqual(rc, 1)
        self.assertTrue(err.startswith("aos-tree-start: error: FlagUnknown "), err)
        rc, out, err = self.run_cmd()
        self.assertEqual((rc, out), (1, ""))
        self.assertTrue(err.startswith("aos-tree-start: error: ArgumentsBad missing AOS_EXEC_ARG"), err)


if __name__ == "__main__":
    unittest.main()
