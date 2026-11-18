"""Test aos-share check (secret-open, acl-masked, acl-missing, acl-present, unreadable) and reset, red before and green after."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[4]
CMD = PROTO / "bin" / "aos-share"
ME = os.getuid()


class CheckReset(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(dir=os.environ.get("KERNEL_TEST_TMP")))
        self.env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        probe = self.tmp / "probe"
        probe.touch()
        if subprocess.run(["setfacl", "-m", "u:%s:rw" % ME, str(probe)], capture_output=True).returncode:
            self.skipTest("cannot set ACLs here")
        probe.unlink()

    def run_cmd(self, *args, **env):
        return subprocess.run([sys.executable, str(CMD), *map(str, args)],
                              capture_output=True, text=True, env=dict(self.env, **env), timeout=30)

    def setfacl(self, *args):
        subprocess.run(["setfacl", *map(str, args)], capture_output=True, text=True, check=True)

    def extended(self, path):
        """getfacl lines other than the three base entries, for PATH and everything below it."""
        result = subprocess.run(["getfacl", "-R", "-n", "--omit-header", "--absolute-names", str(path)],
                                capture_output=True, text=True, check=True)
        base = ("user::", "group::", "other::", "# file:")
        return [line for line in result.stdout.splitlines() if line and not line.startswith(base)]

    def assert_red(self, args, expected):
        result = self.run_cmd("check", *args)
        self.assertEqual((result.returncode, result.stderr), (1, ""), result)
        lines = result.stdout.splitlines()
        self.assertEqual(lines[-1], "total: %d" % (len(lines) - 1))
        for line in expected:
            self.assertIn(line, lines)
        return lines

    def assert_green(self, args):
        result = self.run_cmd("check", *args)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "total: 0\n", ""))

    def reset(self, *args):
        result = self.run_cmd("reset", *args)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_secret_open(self):
        top = self.tmp / "def"
        top.mkdir()
        names = ("token.json", ".env", "brain.env", "tokens", "my_token_x.json", "id.key", "exec.json", "the-secret")
        for name in names:
            (top / name).write_text("x\n")
            (top / name).chmod(0o644)
        (top / "creds.txt").write_text("K=V\n")
        (top / "creds.txt").chmod(0o640)
        (top / "plain.json").write_text("{}\n")
        (top / "plain.json").chmod(0o644)
        (top / "tools.json").write_text('{"tools": {"t": {"path": "t", "env_file": "creds.txt"}, "u": {"path": "u"}}}\n')
        (top / "tools.json").chmod(0o600)
        expected = ["secret-open %s mode=0644" % (top / name) for name in names]
        expected.append("secret-open %s mode=0640" % (top / "creds.txt"))
        lines = self.assert_red(["-R", top], expected)
        self.assertEqual(len(lines), len(expected) + 1, lines)
        # without -R only PATH itself is checked
        self.assert_green([top])
        # reset does not touch rwx bits: still red afterwards; chmod 600 makes it green
        self.reset("-R", top)
        self.assert_red(["-R", top], expected)
        for name in names + ("creds.txt",):
            (top / name).chmod(0o600)
        self.assert_green(["-R", top])
        self.assertEqual(self.extended(top), [])

    def test_acl_masked(self):
        path = self.tmp / "masked"
        path.mkdir()
        self.setfacl("-m", "u:%s:rwx,m::r" % ME, path)
        self.setfacl("-d", "-m", "u:%s:rwx,m::rx" % ME, path)
        self.assert_red([path], ["acl-masked %s entry=u:%s:rwx effective=r--" % (path, ME),
                                 "acl-masked %s entry=d:u:%s:rwx effective=r-x" % (path, ME)])
        self.reset(path)
        self.assert_green(["--list-acl", path])
        self.assertEqual(self.extended(path), [])

    def test_acl_missing_after_mv(self):
        box = self.tmp / "box"
        box.mkdir()
        self.setfacl("-d", "-m", "u:%s:rwx" % ME, box)
        # created inside: inherits the default ACL (0777 keeps the mask at rwx, so nothing is masked)
        os.close(os.open(box / "made", os.O_CREAT | os.O_WRONLY, 0o777))
        outside = self.tmp / "outside"
        outside.write_text("moved in\n")
        moved = box / "moved"
        outside.rename(moved)
        lines = self.assert_red(["-R", box], ["acl-missing %s (parent has default ACL)" % moved])
        self.assertEqual(lines, ["acl-missing %s (parent has default ACL)" % moved, "total: 1"])
        self.reset("-R", box)
        self.assert_green(["-R", "--list-acl", box])
        self.assertEqual(self.extended(box), [])

    def test_acl_present_only_with_list_acl(self):
        top = self.tmp / "present"
        child = top / "child"
        child.mkdir(parents=True)
        (top / "file").write_text("x\n")
        self.setfacl("-m", "u:%s:rw" % ME, top / "file")
        self.setfacl("-m", "u:%s:rwx" % ME, child)
        self.assert_green(["-R", top])
        lines = self.assert_red(["--list-acl", "-R", top], ["acl-present %s" % child, "acl-present %s" % (top / "file")])
        self.assertEqual(len(lines), 3, lines)
        self.reset("-R", top)
        self.assert_green(["--list-acl", "-R", top])
        self.assertEqual(self.extended(top), [])

    def test_reset_clears_special_bits_and_dry_run_changes_nothing(self):
        top = self.tmp / "team"
        inner = top / "inner"
        inner.mkdir(parents=True)
        (top / "file").write_text("x\n")
        (top / "file").chmod(0o640)
        for folder, mode in ((top, 0o2770), (inner, 0o3770)):
            folder.chmod(mode)
            self.setfacl("-m", "u:%s:rwx,d:u:%s:rwx" % (ME, ME), folder)
        before = self.extended(top)
        result = self.run_cmd("reset", "--dry-run", "-R", top)
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertEqual(result.stdout.splitlines(), [
            "setfacl -R -b %s" % top, "chmod g-s,-t %s" % top, "chmod g-s,-t %s" % inner])
        self.assertEqual(self.extended(top), before)
        self.assertEqual(top.stat().st_mode & 0o7777, 0o2770)
        result = self.run_cmd("reset", inner, "--dry-run")
        self.assertEqual(result.stdout.splitlines(), ["setfacl -b %s" % inner, "chmod g-s,-t %s" % inner])
        self.reset("-R", top)
        self.assertEqual(self.extended(top), [])
        self.assertEqual(top.stat().st_mode & 0o7777, 0o770)
        self.assertEqual(inner.stat().st_mode & 0o7777, 0o770)
        self.assertEqual((top / "file").stat().st_mode & 0o7777, 0o640)
        self.reset("-R", top)
        self.assertEqual(top.stat().st_mode & 0o7777, 0o770)

    def test_reset_without_recursion_keeps_children(self):
        top = self.tmp / "top"
        inner = top / "inner"
        inner.mkdir(parents=True)
        self.setfacl("-m", "u:%s:rwx" % ME, inner)
        self.setfacl("-m", "u:%s:rwx" % ME, top)
        self.reset(top)
        self.assertEqual(self.extended(top), self.extended(inner))
        self.assertNotEqual(self.extended(inner), [])

    def test_unreadable(self):
        self.assert_red([self.tmp / "absent"], ["unreadable %s ENOENT" % (self.tmp / "absent")])
        if os.geteuid() == 0:
            self.skipTest("root can list any folder")
        top = self.tmp / "top"
        closed = top / "closed"
        closed.mkdir(parents=True)
        closed.chmod(0)
        try:
            self.assert_red(["-R", top], ["unreadable %s EACCES" % closed])
        finally:
            closed.chmod(0o700)

    def test_symlinks_are_skipped_below_path(self):
        top = self.tmp / "links"
        top.mkdir()
        target = self.tmp / "token.json"
        target.write_text("x\n")
        target.chmod(0o644)
        (top / "token.json").symlink_to(target)
        self.assert_green(["-R", top])

    def test_errors(self):
        for name, usage in (("check", "check [-R] [--list-acl] PATH..."), ("reset", "reset [-R] [--dry-run] PATH...")):
            with self.subTest(name=name):
                result = self.run_cmd(name)
                self.assertEqual((result.returncode, result.stdout), (1, ""))
                self.assertEqual(result.stderr, "aos-share: error: ArgumentsBad expected at least one PATH (usage: aos-share %s)\n" % usage)
                result = self.run_cmd(name, "--bogus", self.tmp)
                self.assertEqual((result.returncode, result.stdout), (1, ""))
                self.assertTrue(result.stderr.startswith("aos-share: error: FlagUnknown "), result.stderr)
        for args in (("check", "--dry-run", self.tmp), ("reset", "--list-acl", self.tmp)):
            with self.subTest(args=args):
                self.assertTrue(self.run_cmd(*args).stderr.startswith("aos-share: error: FlagUnknown "))
        result = self.run_cmd("reset", self.tmp / "absent")
        self.assertEqual(result.stderr, "aos-share: error: PathMissing %s does not exist\n" % (self.tmp / "absent"))
        result = self.run_cmd("reset", self.tmp, PATH="")
        self.assertEqual(result.stderr, "aos-share: error: CommandMissing setfacl not found on PATH\n")
        # the old dispatch is untouched: a subcommand name after a flag is still not a KIND
        result = self.run_cmd("--dry-run", "check", self.tmp)
        self.assertTrue(result.stderr.startswith("aos-share: error: ArgumentsBad KIND must be one of "), result.stderr)

    def test_help_lists_subcommands(self):
        result = self.run_cmd("check", "--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("aos-share check [-R] [--list-acl] PATH...", result.stdout)
        self.assertIn("aos-share reset [-R] [--dry-run] PATH...", result.stdout)


if __name__ == "__main__":
    unittest.main()
