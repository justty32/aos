"""Test aos-asuser mappings, validation, environment isolation, exit status and file recovery."""
import os
from pathlib import Path
import pwd
import runpy
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[3]
CMD = PROTO / "cmd" / "aos-asuser" / "bin" / "aos-asuser"
USER = pwd.getpwuid(os.getuid()).pw_name


class Asuser(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(dir=os.environ.get("KERNEL_TEST_TMP")))
        self.subuid = self.tmp / "subuid"
        self.subgid = self.tmp / "subgid"
        for path in (self.subuid, self.subgid):
            path.write_text("%s:100000:65536\n" % USER)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        for name in ("newuidmap", "newgidmap"):
            path = self.bin / name
            path.write_text("#!/bin/sh\n# 測試用對照表工具只供 dry-run 查找。\nexit 1\n")
            path.chmod(0o755)
        self.env = dict(os.environ, AOS_ASUSER_SUBUID=str(self.subuid),
                        AOS_ASUSER_SUBGID=str(self.subgid), PYTHONDONTWRITEBYTECODE="1",
                        PATH=str(self.bin) + os.pathsep + os.environ.get("PATH", os.defpath))

    def run_cmd(self, *args, real=False, cwd=None, **env):
        child_env = dict(self.env)
        if real:
            child_env = {key: value for key, value in os.environ.items()
                         if key not in ("AOS_ASUSER_SUBUID", "AOS_ASUSER_SUBGID")}
            child_env["PYTHONDONTWRITEBYTECODE"] = "1"
        child_env.update(env)
        return subprocess.run([sys.executable, str(CMD), *map(str, args)],
                              capture_output=True, text=True, env=child_env,
                              cwd=cwd or self.tmp, timeout=30)

    def require_namespaces(self):
        result = self.run_cmd("sub:1", "--", "true", real=True)
        if result.returncode:
            self.skipTest("user namespaces with subuids are not available here")

    def assert_error(self, code, *args, **env):
        result = self.run_cmd(*args, **env)
        self.assertEqual(result.returncode, 1, result)
        self.assertEqual(result.stdout, "")
        self.assertEqual(len(result.stderr.splitlines()), 1, result.stderr)
        self.assertTrue(result.stderr.startswith("aos-asuser: error: %s " % code), result.stderr)

    def test_real_identity_and_environment(self):
        self.require_namespaces()
        cases = [(("sub:5", "--", "id", "-u"), "5\n"),
                 (("sub:5", "--", "sh", "-c", "echo $HOME"), "/nonexistent\n"),
                 (("sub:5", "--", "sh", "-c", "echo ${SECRET_KEY:-none}"), "none\n"),
                 (("--env-all", "sub:5", "--", "sh", "-c", "echo $SECRET_KEY"), "x\n")]
        for args, expected in cases:
            with self.subTest(args=args):
                result = self.run_cmd(*args, real=True, SECRET_KEY="x")
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, expected, ""))

    def test_real_private_file_denied(self):
        self.require_namespaces()
        folder = Path(tempfile.mkdtemp())
        folder.chmod(0o755)
        path = folder / "private"
        path.write_text("secret\n")
        path.chmod(0o600)
        result = self.run_cmd("sub:5", "--", "cat", path, real=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_real_exit_status(self):
        self.require_namespaces()
        for script, expected in (("exit 7", 7), ("kill -TERM $$", 143)):
            with self.subTest(script=script):
                result = self.run_cmd("sub:5", "--", "sh", "-c", script, real=True)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (expected, "", ""))
        result = self.run_cmd("sub:5", "--", "/no-such-asuser-program", real=True)
        self.assertEqual(result.returncode, 127)
        self.assertIn("aos-asuser: error: CommandMissing cannot start", result.stderr)

    def test_real_file_recovery(self):
        self.require_namespaces()
        folder = Path(tempfile.mkdtemp(dir="/tmp"))
        folder.chmod(0o777)
        result = self.run_cmd("sub:5", "--", "sh", "-c", "echo hi > f; chmod 600 f",
                              real=True, cwd=folder)
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        path = folder / "f"
        self.assertEqual(path.stat().st_uid, 100004)
        with self.assertRaises(PermissionError):
            path.read_text()
        result = self.run_cmd("--fix", path, real=True)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))
        self.assertEqual(path.stat().st_uid, os.getuid())
        self.assertEqual(path.read_text(), "hi\n")

    def test_real_git_safe(self):
        self.require_namespaces()
        result = self.run_cmd("--git-safe", "/x", "sub:5", "--", "sh", "-c", "echo $GIT_CONFIG_VALUE_0", real=True)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "/x\n", ""))

    def test_dry_run_exact_mappings(self):
        result = self.run_cmd("--dry-run", "sub:5", "--", "true")
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertEqual(result.stdout.splitlines(), [
            "newuidmap PID 0 %s 1 5 100004 1" % os.getuid(),
            "newgidmap PID 0 %s 1 5 100004 1" % os.getgid(),
            "exec 5:5 true",
        ])

    def test_dry_run_group_and_program_flags(self):
        result = self.run_cmd("sub:60000", "--dry-run", "--group", "sub:65536", "--", "echo", "--help", "a b")
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertEqual(result.stdout.splitlines(), [
            "newuidmap PID 0 %s 1 60000 159999 1" % os.getuid(),
            "newgidmap PID 0 %s 1 65536 165535 1" % os.getgid(),
            "exec 60000:65536 echo --help a b",
        ])

    def test_dry_run_fix_no_recursive_expansion(self):
        path = self.tmp / "dir"
        path.mkdir()
        (path / "child").touch()
        result = self.run_cmd("--fix", "--recursive", "--dry-run", path, self.subuid)
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertEqual(result.stdout.splitlines(), [
            "newuidmap PID 0 %s 1 1 100000 65536" % os.getuid(),
            "newgidmap PID 0 %s 1 1 100000 65536" % os.getgid(),
            "fix %s" % path, "fix %s" % self.subuid,
        ])

    def test_argument_errors(self):
        for value in ("sub:0", "sub:60001", "sub:01", "sub:+1", "sub:-1", "sub: 1", "sub:1 ", "5"):
            with self.subTest(value=value):
                self.assert_error("ArgumentsBad", "--dry-run", value, "--", "true")
        cases = [(), ("sub:5", "true"), ("sub:5", "--"), ("--fix", "sub:5"),
                 ("--fix",), ("--recursive", "sub:5", "--", "true"),
                 ("--fix", "--env-all", str(self.subuid)),
                 ("--fix", "--group", "sub:5", str(self.subuid)),
                 ("--fix", str(self.subuid), "--", "true")]
        for args in cases:
            with self.subTest(args=args):
                self.assert_error("ArgumentsBad", *args)
        for value in ("sub:0", "sub:65537", "sub:01", "1"):
            self.assert_error("ArgumentsBad", "--group", value, "sub:5", "--", "true")
        self.assert_error("FlagUnknown", "--bogus")

    def test_subid_errors_and_first_matching_line(self):
        self.subuid.write_text("nobody-else:100000:65536\n")
        self.assert_error("SubidMissing", "--dry-run", "sub:5", "--", "true")
        self.subuid.write_text("%s:100000:4\n%s:200000:65536\n" % (USER, USER))
        self.assert_error("SubidMissing", "--dry-run", "sub:5", "--", "true")
        self.assert_error("SubidMissing", "--dry-run", "sub:1", "--", "true",
                          AOS_ASUSER_SUBUID=str(self.tmp / "missing"))
        self.subuid.write_text("\n# comment\n%s:100000:65536\n%s:200000:65536\n" % (os.getuid(), USER))
        self.subgid.write_text("%s:100000:4\n" % USER)
        self.assert_error("SubidMissing", "--dry-run", "sub:1", "--group", "sub:5", "--", "true")
        self.subgid.write_text("%s:100000:65536\n" % USER)
        result = self.run_cmd("--dry-run", "sub:5", "--", "true")
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertIn("5 100004 1\n", result.stdout)

    def test_missing_path_and_command(self):
        self.assert_error("PathMissing", "--fix", self.tmp / "missing")
        self.assert_error("CommandMissing", "--dry-run", "sub:5", "--", "true", PATH="")
        (self.bin / "newuidmap").rename(self.bin / "uidmap.saved")
        self.assert_error("CommandMissing", "--dry-run", "sub:5", "--", "true", PATH=str(self.bin))

    def test_help(self):
        for flag in ("--help", "-h"):
            result = self.run_cmd(flag)
            self.assertEqual((result.returncode, result.stderr), (0, ""))
            self.assertTrue(result.stdout.startswith("aos-asuser - "))


class Helpers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = runpy.run_path(str(CMD), run_name="asuser_tests")

    def test_fix_recursive_repairs_root_and_does_not_follow_symlink(self):
        folder = Path(tempfile.mkdtemp(dir=os.environ.get("KERNEL_TEST_TMP")))
        root = folder / "root"
        root.mkdir()
        child = root / "child"
        child.mkdir()
        file = child / "file"
        file.touch()
        target = folder / "outside"
        target.touch()
        target.chmod(0o400)
        link = root / "link"
        link.symlink_to(target)
        file.chmod(0o000)
        child.chmod(0o400)
        root.chmod(0o400)
        with mock.patch.object(os, "lchown") as chown:
            self.assertEqual(self.module["fix_paths"]([str(root)], True), 0)
        visited = [call.args[0] for call in chown.call_args_list]
        self.assertEqual(visited[0], str(root))
        self.assertEqual(set(visited), set(map(str, (root, child, file, link))))
        self.assertEqual(root.stat().st_mode & 0o700, 0o700)
        self.assertEqual(child.stat().st_mode & 0o700, 0o700)
        self.assertEqual(file.stat().st_mode & 0o600, 0o600)
        self.assertEqual(target.stat().st_mode & 0o777, 0o400)

    def test_fix_continues_after_failure(self):
        with mock.patch.object(os, "lchown", side_effect=[PermissionError(1, "denied"), None]) as chown, \
                mock.patch.object(os, "lstat", return_value=mock.Mock(st_mode=0o100400)), \
                mock.patch.object(os, "chmod"), mock.patch("aos_flags.warn") as warn:
            self.assertEqual(self.module["fix_paths"](["first", "second"], False), 1)
            self.assertEqual(chown.call_count, 2)
            self.assertIn("cannot fix first", warn.call_args.args[1])

    def test_wait_child_status(self):
        for status, expected in ((7 << 8, 7), (signal.SIGTERM, 143)):
            with mock.patch.object(os, "waitpid", return_value=(123, status)):
                self.assertEqual(self.module["wait_child"](123), expected)


if __name__ == "__main__":
    unittest.main()
