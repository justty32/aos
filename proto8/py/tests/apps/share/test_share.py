"""Test aos-share templates, strict subid resolution, dry runs, errors and ancestor warnings."""
import os
from pathlib import Path
import pwd
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[4]
CMD = PROTO / "bin" / "aos-share"                       # the entry install.py writes
SOURCE = PROTO / "py" / "aos" / "apps" / "share" / "main.py"
ME = os.getuid()
USER = pwd.getpwuid(ME).pw_name


class Share(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(dir=os.environ.get("KERNEL_TEST_TMP")))
        self.subuid = self.tmp / "subuid"
        self.subgid = self.tmp / "subgid"
        for path in (self.subuid, self.subgid):
            path.write_text("%s:200000:65536\n" % USER)
        self.env = dict(os.environ, AOS_SHARE_SUBUID=str(self.subuid),
                        AOS_SHARE_SUBGID=str(self.subgid), PYTHONDONTWRITEBYTECODE="1")

    def run_cmd(self, *args, **env):
        return subprocess.run([sys.executable, str(CMD), *map(str, args)],
                              capture_output=True, text=True, env=dict(self.env, **env), timeout=30)

    def acl(self, path):
        result = subprocess.run(["getfacl", "-n", "--omit-header", "--absolute-names", str(path)],
                                capture_output=True, text=True, check=True)
        return result.stdout

    def require_acls(self):
        probe = self.tmp / "probe"
        probe.touch()
        result = subprocess.run(["setfacl", "-m", "g:200599:r", str(probe)],
                                capture_output=True, text=True)
        if result.returncode:
            self.skipTest("cannot set ACLs for foreign ids here")

    def assert_ok(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def assert_error(self, code, *args, **env):
        result = self.run_cmd(*args, **env)
        self.assertEqual(result.returncode, 1, result)
        self.assertEqual(result.stdout, "")
        self.assertEqual(len(result.stderr.splitlines()), 1, result.stderr)
        self.assertTrue(result.stderr.startswith("aos-share: error: %s " % code), result.stderr)

    def test_team_and_idempotence(self):
        self.require_acls()
        path = self.tmp / "team"
        self.assert_ok(self.run_cmd("team", path, "--group", "sub:600"))
        before = self.acl(path)
        for entry in ("group:200599:rwx", "default:group:200599:rwx", "default:user:%s:rwx" % ME):
            self.assertIn(entry + "\n", before)
        self.assertEqual(path.stat().st_mode & 0o7777, 0o2770)
        self.assert_ok(self.run_cmd("team", path, "--group", "sub:600"))
        self.assertEqual(self.acl(path), before)

    def test_work(self):
        self.require_acls()
        path = self.tmp / "work"
        self.assert_ok(self.run_cmd("work", path, "--group", "sub:600"))
        self.assertIn("group:200599:rwx\n", self.acl(path))
        self.assertIn("default:user:%s:rwx\n" % ME, self.acl(path))

    def test_drop_inheritance_and_idempotence(self):
        self.require_acls()
        path = self.tmp / "drop"
        self.assert_ok(self.run_cmd("drop", path, "--group", "sub:600"))
        for folder in (path, path / "tmp", path / "new", path / "cur"):
            self.assertTrue(folder.is_dir())
        before = {folder: self.acl(folder) for folder in (path, path / "tmp", path / "new", path / "cur")}
        new = path / "new"
        self.assertEqual(new.stat().st_mode & 0o7777, 0o1730)
        self.assertIn("default:group::---\n", before[new])
        self.assertIn("default:user:%s:rwx\n" % ME, before[new])
        self.assertEqual((path / "cur").stat().st_mode & 0o7777, 0o700)
        self.assertNotIn("default:", before[path / "cur"])
        child = new / "letter"
        child.mkdir(mode=0o777)
        entry = next(line for line in self.acl(child).splitlines() if line.startswith("user:%s:" % ME))
        self.assertEqual(entry, "user:%s:rwx" % ME)
        self.assert_ok(self.run_cmd("drop", path, "--group", "sub:600"))
        for folder, acl in before.items():
            self.assertEqual(self.acl(folder), acl)

    def test_key(self):
        self.require_acls()
        path = self.tmp / "key"
        path.touch()
        self.assert_ok(self.run_cmd("key", path, "--uid", "sub:5"))
        acl = self.acl(path)
        for entry in ("user:200004:r--", "group::---", "mask::r--", "other::---"):
            self.assertIn(entry + "\n", acl)
        self.assertEqual(path.stat().st_mode & 0o7777, 0o640)
        self.assert_ok(self.run_cmd("key", path, "--uid", "sub:5"))
        self.assertEqual(self.acl(path), acl)

    def test_read_multiple_groups(self):
        self.require_acls()
        path = self.tmp / "read"
        child = path / "child"
        child.mkdir(parents=True)
        file = child / "file"
        file.write_text("sample\n")
        args = ("read", path, "--group", "sub:600", "--group", "sub:601")
        self.assert_ok(self.run_cmd(*args))
        before = {item: self.acl(item) for item in (path, child, file)}
        for item in (path, child):
            for gid in (200599, 200600):
                self.assertIn("group:%s:r-x\n" % gid, before[item])
                self.assertIn("default:group:%s:r-x\n" % gid, before[item])
        for gid in (200599, 200600):
            self.assertIn("group:%s:r--\n" % gid, before[file])
        self.assert_ok(self.run_cmd(*args))
        for item, acl in before.items():
            self.assertEqual(self.acl(item), acl)

    def test_stack(self):
        self.require_acls()
        path = self.tmp / "stack"
        self.assert_ok(self.run_cmd("stack", path, "--uid", "sub:5"))
        acl = self.acl(path)
        for entry in ("user:200004:rwx", "default:user:%s:rwx" % ME, "group::---", "other::---"):
            self.assertIn(entry + "\n", acl)
        self.assertEqual(path.stat().st_mode & 0o7777, 0o770)
        self.assert_ok(self.run_cmd("stack", path, "--uid", "sub:5"))
        self.assertEqual(self.acl(path), acl)

    def test_dry_run_team(self):
        path = self.tmp / "absent" / "team"
        result = self.run_cmd("--dry-run", "team", path, "--group", "sub:600")
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertEqual(result.stdout.splitlines(), [
            "mkdir -p %s" % path,
            "chmod 2770 %s" % path,
            "setfacl -m g:200599:rwx,d:g:200599:rwx,d:u:%s:rwx,m::rwx,d:m::rwx %s" % (ME, path),
        ])
        self.assertFalse(path.parent.exists())

    def test_dry_run_missing_read_and_key(self):
        for kind, flag in (("read", "--group"), ("key", "--uid")):
            with self.subTest(kind=kind):
                path = self.tmp / kind
                result = self.run_cmd(kind, path, flag, "0", "--dry-run", PATH="")
                self.assertEqual((result.returncode, result.stderr), (0, ""))
                self.assertTrue(result.stdout.startswith("setfacl" if kind == "read" else "chmod"))
                self.assertFalse(path.exists())

    def test_argument_errors(self):
        path = self.tmp / "absent"
        cases = [(), ("unknown", str(path)), ("team",), ("team", str(path)),
                 ("team", str(path), "--uid", "sub:5"),
                 ("team", str(path), "--group", "1", "--group", "2"),
                 ("stack", str(path), "--uid", "1", "--uid", "2"),
                 ("key", str(path), "--uid", "1", "--group", "2")]
        for args in cases:
            with self.subTest(args=args):
                self.assert_error("ArgumentsBad", *args)
        self.assert_error("FlagUnknown", "team", path, "--bogus")
        for value in ("sub:0", "sub:01", "sub:65537", "sub:-1", "sub:+1", "sub: 1", "sub:1 ",
                      "01", "+1", "-1", " 1", "1 ", "abc"):
            with self.subTest(value=value):
                self.assert_error("ArgumentsBad", "--dry-run", "team", path, "--group=" + value)

    def test_subid_errors(self):
        path = self.tmp / "absent"
        self.subgid.write_text("not-the-current-user:200000:65536\n")
        self.assert_error("SubidMissing", "--dry-run", "team", path, "--group", "sub:1")
        self.subgid.write_text("%s:200000:4\n%s:300000:65536\n" % (USER, USER))
        self.assert_error("SubidMissing", "--dry-run", "team", path, "--group", "sub:5")
        self.assert_error("SubidMissing", "--dry-run", "team", path, "--group", "sub:1",
                          AOS_SHARE_SUBGID=str(self.tmp / "missing"))

    def test_subid_comments_numeric_owner_and_first_match(self):
        self.subgid.write_text("\n# comment\n%s:200000:65536\n%s:300000:65536\n" % (ME, USER))
        for value, resolved in (("sub:1", "200000"), ("sub:65536", "265535"), ("0", "0"), ("200599", "200599")):
            with self.subTest(value=value):
                result = self.run_cmd("--dry-run", "team", self.tmp / "team", "--group", value)
                self.assertEqual((result.returncode, result.stderr), (0, ""))
                self.assertIn("g:%s:rwx" % resolved, result.stdout)

    def test_path_errors(self):
        path = self.tmp / "absent"
        self.assert_error("PathMissing", "key", path, "--uid", "sub:5")
        self.assert_error("PathMissing", "read", path, "--group", "sub:600")
        self.assert_error("PathMissing", "key", self.tmp, "--uid", "sub:5")

    def test_command_missing(self):
        self.assert_error("CommandMissing", "team", self.tmp / "team", "--group", "1", PATH="")
        self.assertFalse((self.tmp / "team").exists())

    def test_subid_range_bounds(self):
        maximum = 2**32 - 2
        for path, kind, flag in ((self.subuid, "stack", "--uid"), (self.subgid, "team", "--group")):
            for start, count in (("9" * 4301, "1"), ("1", "9" * 4301),
                                 (str(maximum + 1), "1"), (str(maximum), "2"),
                                 ("0", str(maximum + 1))):
                with self.subTest(path=path, start_length=len(start), count_length=len(count)):
                    path.write_text("%s:%s:%s\n" % (USER, start, count))
                    result = self.run_cmd("--dry-run", kind, self.tmp / kind, flag, "sub:1")
                    self.assertEqual((result.returncode, result.stdout), (1, ""))
                    self.assertEqual(result.stderr, "aos-share: error: SubidMissing range for %s in %s is out of bounds\n" % (USER, path))
            path.write_text("%s:%s:1\n" % (USER, maximum))
            result = self.run_cmd("--dry-run", kind, self.tmp / kind, flag, "sub:1")
            self.assertEqual((result.returncode, result.stderr), (0, ""))
            self.assertIn(str(maximum), result.stdout)

    def test_ancestor_query_failure_warns_and_continues(self):
        self.require_acls()
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "getfacl"
        fake.write_text("#!/bin/sh\n# 測試用祖先查詢失敗替身。\necho acl-query-unavailable >&2\nexit 1\n")
        fake.chmod(0o755)
        parent = self.tmp / "A"
        parent.mkdir(mode=0o700)
        path = parent / "B"
        result = self.run_cmd("team", path, "--group", "sub:600",
                              PATH=str(bin_dir) + os.pathsep + os.environ.get("PATH", os.defpath))
        self.assert_ok(result)
        for folder in (self.tmp, parent):
            self.assertIn("aos-share: warning: cannot check %s: acl-query-unavailable\n" % folder, result.stderr)
        self.assertNotIn("aos-share: error:", result.stderr)
        self.assertIn("group:200599:rwx\n", self.acl(path))

    def test_ancestor_stat_failure_warns_and_continues(self):
        sys.path.insert(0, str(PROTO / "py"))
        module = runpy.run_path(str(SOURCE), run_name="share_tests")
        parent = self.tmp / "A"
        parent.mkdir(mode=0o700)
        real_stat = os.stat

        def stat_or_fail(path, *args, **kwargs):
            if str(path) == str(self.tmp):
                raise PermissionError(13, "denied")
            return real_stat(path, *args, **kwargs)

        with mock.patch.object(os, "stat", side_effect=stat_or_fail), \
                mock.patch("subprocess.run", return_value=mock.Mock(returncode=0, stdout="", stderr="")), \
                mock.patch("aos.flags.warn") as warn:
            module["warn_ancestors"](str(parent / "B"), "group", ["200599"])
        messages = [call.args[1] for call in warn.call_args_list]
        self.assertIn("cannot check %s: denied" % self.tmp, messages)
        self.assertIn("%s gives no x to others: uid/gid 200599 cannot reach %s" % (parent, parent / "B"), messages)

    def test_help(self):
        for flag in ("--help", "-h"):
            result = self.run_cmd(flag)
            self.assertEqual((result.returncode, result.stderr), (0, ""))
            self.assertTrue(result.stdout.startswith("aos-share - "))

    def test_ancestor_warning(self):
        self.require_acls()
        parent = self.tmp / "A"
        parent.mkdir(mode=0o700)
        path = parent / "B"
        result = self.run_cmd("team", path, "--group", "sub:600")
        self.assert_ok(result)
        warning = "aos-share: warning: %s gives no x to others: uid/gid 200599 cannot reach %s" % (parent, path)
        self.assertEqual(result.stderr.splitlines().count(warning), 1)

    def test_ancestor_effective_permissions(self):
        self.require_acls()
        parent = self.tmp / "A"
        parent.mkdir(mode=0o700)
        subprocess.run(["setfacl", "-m", "g:200599:rwx,m::r--", str(parent)],
                       capture_output=True, text=True, check=True)
        path = parent / "B"
        result = self.run_cmd("team", path, "--group", "sub:600")
        self.assert_ok(result)
        self.assertIn("%s gives no x to others" % parent, result.stderr)
        subprocess.run(["setfacl", "-m", "m::rwx", str(parent)], capture_output=True, text=True, check=True)
        result = self.run_cmd("team", path, "--group", "sub:600")
        self.assert_ok(result)
        self.assertNotIn("%s gives no x to others" % parent, result.stderr)


if __name__ == "__main__":
    unittest.main()
