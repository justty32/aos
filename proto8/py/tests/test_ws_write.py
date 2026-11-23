"""Test workspace-only text writing, modes, byte limits, and safe create publication."""

import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1] / "tools" / "base"
ENTRY = BASE / "ws_write" / "_entry"


class WorkspaceWriteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ws, self.out = self.root / "ws", self.root / "out"
        self.ws.mkdir()
        self.out.mkdir()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        self.env["AOS_WS"] = str(self.ws)
        self.env["PYTHONDONTWRITEBYTECODE"] = "1"

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, env=None, command=None, **args):
        return subprocess.run(command or [sys.executable, str(ENTRY)], input=json.dumps(args),
                              text=True, capture_output=True,
                              env=self.env if env is None else env)

    def ok(self, expected, **args):
        result = self.call(**args)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, expected + "\n")
        self.assertEqual(result.stderr, "")

    def error(self, code, **args):
        result = self.call(**args)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertTrue(result.stdout.startswith("ws_write: error: %s " % code), result.stdout)
        self.assertEqual(result.stdout, result.stderr)
        self.assertEqual(len(result.stdout.splitlines()), 1)
        return result.stdout

    def test_relative_and_nested_new_folders(self):
        self.ok("wrote 6 bytes to report.md", path="report.md", content="hello\n")
        self.assertEqual((self.ws / "report.md").read_bytes(), b"hello\n")
        self.ok("wrote 4 bytes to notes/deep/report.md", path="notes/deep/report.md", content="text")
        self.assertEqual((self.ws / "notes/deep/report.md").read_bytes(), b"text")

    def test_relative_escape_refused_before_mkdir(self):
        self.error("PathBad", path="../x", content="no")
        self.assertFalse((self.root / "x").exists())
        self.error("PathBad", path="../out/new/deep/x", content="no")
        self.assertEqual(list(self.out.iterdir()), [])

    def test_absolute_outside_and_workspace_prefix_sibling_refused(self):
        for target in (self.out / "x", self.root / "ws-other" / "x"):
            with self.subTest(target=target):
                line = self.error("PathBad", path=str(target), content="no")
                self.assertIn("%s is outside the workspace" % target, line)
                self.assertFalse(target.exists())
        self.assertFalse((self.root / "ws-other").exists())

    def test_own_stack_and_definition_inside_workspace_refused(self):
        stack, definition = self.ws / ".stack" / "procs" / "me", self.ws / "defs" / "me"
        stack.mkdir(parents=True)
        definition.mkdir(parents=True)
        env = dict(self.env, AOS_STACK=str(stack), AOS_CD=str(definition))
        for target, var in ((stack / "tools.json", "AOS_STACK"), (stack / "queue" / "new" / "x", "AOS_STACK"),
                            (definition / "system.txt", "AOS_CD")):
            for mode in ("create", "append"):
                with self.subTest(target=target, mode=mode):
                    result = self.call(env=env, path=str(target), content="no", mode=mode)
                    self.assertEqual(result.returncode, 1, result.stdout)
                    self.assertTrue(result.stdout.startswith("ws_write: error: PathBad "), result.stdout)
                    self.assertIn("inside $%s" % var, result.stdout)
                    self.assertFalse(target.exists())
        self.assertFalse((stack / "queue").exists())
        for target in (".stack/procs/other/queue/new/x", ".stack/procs/other.md", ".stack/daemon.json", "sub/.stack/x"):
            with self.subTest(neighbour=target):                                    # other agents' stacks and any .stack folder
                result = self.call(env=env, path=target, content="no")
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertTrue(result.stdout.startswith("ws_write: error: PathBad "), result.stdout)
                self.assertFalse((self.ws / target).exists())
        self.assertFalse((self.ws / "sub").exists())
        result = self.call(env=env, path="notes.md", content="ok")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_stack_outside_dot_stack_still_guards_neighbours(self):
        procs = self.ws / "state" / "procs"
        (procs / "me").mkdir(parents=True)
        (procs / "other").mkdir()
        env = dict(self.env, AOS_STACK=str(procs / "me"))
        line = self.call(env=env, path="state/procs/other/tools.json", content="no")
        self.assertEqual(line.returncode, 1, line.stdout)
        self.assertIn("PathBad", line.stdout)
        self.assertIn("folder of agent stacks", line.stdout)
        self.assertFalse((procs / "other" / "tools.json").exists())
        ok = self.call(env=env, path="state/notes.md", content="ok")
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)

    def daemon_with_me(self, table=None):
        """ws/state = a daemon stack whose table has me (stack procs/me, def ws/defs/me); env as aos-tools call gives it."""
        daemon = self.ws / "state"
        (daemon / "procs" / "me").mkdir(parents=True)
        (self.ws / "defs" / "me").mkdir(parents=True)
        (daemon / "procs_state.json").write_text(table if table is not None else json.dumps({"procs": {
            "me": {"stack": "procs/me", "def": "../defs/me"}, "other": {"stack": "procs/other", "def": None}}}))
        return dict(self.env, AOS_DAEMON=str(daemon) + "/", AOS_STACK=str(daemon / "procs" / "me" / "tools" / "ws_write") + "/",
                    AOS_STACK_IN_CALLER="tools/ws_write", AOS_CD=str(self.root / "lib" / "ws_write"))

    def test_through_aos_tools_the_definition_comes_from_the_daemon_table(self):
        env = self.daemon_with_me()                          # 11-23 (user "1.補。"): $AOS_CD is the tool's folder here
        for target in ("defs/me/system.txt", "defs/me/sub/tools.json"):
            with self.subTest(target=target):
                line = self.error("PathBad", env=env, path=target, content="no")
                self.assertIn("inside the agent's own definition (defs/me, the def of its row on the daemon table)", line)
                self.assertFalse((self.ws / target).exists())
        self.ok("wrote 2 bytes to ok/fine.md", env=env, path="ok/fine.md", content="ok")
        self.ok("wrote 2 bytes to defs/other.md", env=env, path="defs/other.md", content="ok")   # next to it is fine

    def test_without_a_daemon_the_definition_is_not_checked(self):
        env = self.daemon_with_me()
        env.pop("AOS_DAEMON")                                # no daemon: nothing names the definition (documented)
        self.ok("wrote 2 bytes to defs/me/system.txt", env=env, path="defs/me/system.txt", content="ok")
        (self.ws / "state" / "procs_state.json").write_text(json.dumps({"procs": {}}))
        env["AOS_DAEMON"] = str(self.ws / "state")           # a table without my row: not checked either
        self.ok("appended 2 bytes to defs/me/system.txt", env=env, path="defs/me/system.txt", content="ok", mode="append")

    def test_a_broken_daemon_table_is_table_bad(self):
        env = self.daemon_with_me(table="{broken")
        line = self.error("TableBad", env=env, path="ok/fine.md", content="no")
        self.assertIn("procs_state.json of AOS_DAEMON", line)
        self.assertFalse((self.ws / "ok").exists())

    def test_through_aos_tools_the_callers_stack_is_guarded(self):
        procs = self.ws / "state" / "procs"                  # 11-23: AOS_STACK is only the tool's cell under aos-tools call
        (procs / "me").mkdir(parents=True)
        (procs / "other").mkdir()
        env = dict(self.env, AOS_STACK=str(procs / "me" / "tools" / "ws_write") + "/", AOS_STACK_IN_CALLER="tools/ws_write")
        for target, says in (("state/procs/me/tools.json", "inside $AOS_STACK"),
                             ("state/procs/me/tools/ws_write/x", "inside $AOS_STACK"),
                             ("state/procs/other/tools.json", "folder of agent stacks (state/procs)")):
            with self.subTest(target=target):
                line = self.error("PathBad", env=env, path=target, content="no")
                self.assertIn(says, line)
                self.assertFalse((self.ws / target).exists())
        self.ok("wrote 2 bytes to state/notes.md", env=env, path="state/notes.md", content="ok")
        env["AOS_STACK_IN_CALLER"] = "tools/other"           # does not match the cell: the cell itself is the stack
        self.ok("wrote 2 bytes to state/procs/me/tools.json", env=env, path="state/procs/me/tools.json", content="ok")

    def test_stack_right_under_the_workspace_does_not_refuse_everything(self):
        stack = self.ws / "st"
        stack.mkdir()
        env = dict(self.env, AOS_STACK=str(stack / "tools" / "ws_write"), AOS_STACK_IN_CALLER="tools/ws_write")
        self.error("PathBad", env=env, path="st/tools.json", content="no")
        self.ok("wrote 2 bytes to notes.md", env=env, path="notes.md", content="ok")

    def test_missing_content_is_arguments_bad(self):
        self.error("ArgumentsBad", path="x.md")
        self.assertFalse((self.ws / "x.md").exists())

    def test_absolute_inside(self):
        self.ok("wrote 3 bytes to inside.md", path=str(self.ws / "inside.md"), content="yes")
        self.assertEqual((self.ws / "inside.md").read_bytes(), b"yes")

    def test_symlink_folder_outside(self):
        (self.ws / "link").symlink_to(self.out, target_is_directory=True)
        for mode in ("create", "append", "replace"):
            with self.subTest(mode=mode):
                self.error("PathBad", path="link/new/deep/x", content="no", mode=mode)
        self.assertEqual(list(self.out.iterdir()), [])

    def test_symlink_file_outside(self):
        target = self.out / "keep.md"
        target.write_bytes(b"keep")
        (self.ws / "link.md").symlink_to(target)
        (self.ws / "dangling.md").symlink_to(self.out / "missing.md")
        for path in ("link.md", "dangling.md"):
            for mode in ("create", "append", "replace"):
                with self.subTest(path=path, mode=mode):
                    self.error("PathBad", path=path, content="no", mode=mode)
        self.assertEqual(target.read_bytes(), b"keep")
        self.assertFalse((self.out / "missing.md").exists())

    def test_symlinks_inside_resolve_to_target(self):
        (self.ws / "real").mkdir()
        (self.ws / "alias").symlink_to(self.ws / "real", target_is_directory=True)
        (self.ws / "link.md").symlink_to(self.ws / "real" / "report.md")
        self.ok("wrote 3 bytes to real/report.md", path="alias/report.md", content="one")
        self.ok("wrote 3 bytes to real/report.md", path="link.md", content="two", mode="replace")
        self.assertTrue((self.ws / "link.md").is_symlink())
        self.assertEqual((self.ws / "real/report.md").read_bytes(), b"two")

    def test_workspace_itself_refused(self):
        for path in (".", str(self.ws), "new/.."):
            with self.subTest(path=path):
                self.error("PathBad", path=path, content="no")
        self.assertEqual(list(self.ws.iterdir()), [])

    def test_directory_refused_in_each_mode(self):
        (self.ws / "folder").mkdir()
        for mode in ("create", "append", "replace"):
            with self.subTest(mode=mode):
                self.error("FileBad", path="folder", content="no", mode=mode)
        self.assertEqual(list((self.ws / "folder").iterdir()), [])

    def test_utf8_size_boundary(self):
        content = "\u00e9" * 131072
        self.ok("wrote 262144 bytes to limit.md", path="limit.md", content=content)
        self.assertEqual((self.ws / "limit.md").read_bytes(), content.encode("utf-8"))
        for mode in ("create", "append", "replace"):
            with self.subTest(mode=mode):
                path = "new/deep/too-big.md" if mode == "create" else "limit.md"
                line = self.error("TextTooBig", path=path, content=content + "x", mode=mode)
                self.assertIn("262145", line)
                self.assertIn("262144", line)
        self.assertFalse((self.ws / "new").exists())
        self.assertEqual((self.ws / "limit.md").read_bytes(), content.encode("utf-8"))

    def test_create_default_and_explicit_refuse_existing(self):
        self.ok("wrote 3 bytes to default.md", path="default.md", content="one")
        self.error("PathExists", path="default.md", content="two")
        self.error("PathExists", path="default.md", content="two", mode="create")
        self.assertEqual((self.ws / "default.md").read_bytes(), b"one")
        self.ok("wrote 0 bytes to empty.md", path="empty.md", content="", mode="create")
        self.assertEqual((self.ws / "empty.md").read_bytes(), b"")

    def test_append_creates_and_adds_no_newline(self):
        self.ok("appended 3 bytes to new/append.md", path="new/append.md", content="one", mode="append")
        target = self.ws / "new/append.md"
        inode = target.stat().st_ino
        self.ok("appended 3 bytes to new/append.md", path="new/append.md", content="two", mode="append")
        self.ok("appended 0 bytes to new/append.md", path="new/append.md", content="", mode="append")
        self.assertEqual(target.read_bytes(), b"onetwo")
        self.assertEqual(target.stat().st_ino, inode)

    def test_replace_missing_does_not_create_parents(self):
        self.error("PathMissing", path="missing/deep/report.md", content="no", mode="replace")
        self.assertFalse((self.ws / "missing").exists())

    def test_replace_is_atomic_and_keeps_mode(self):
        target = self.ws / "report.md"
        target.write_bytes(b"old")
        target.chmod(0o751)
        inode = target.stat().st_ino
        self.ok("wrote 3 bytes to report.md", path="report.md", content="new", mode="replace")
        self.assertEqual(target.read_bytes(), b"new")
        self.assertNotEqual(target.stat().st_ino, inode)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o751)
        self.assertEqual(sorted(p.name for p in self.ws.iterdir()), ["report.md"])

    def test_create_does_not_overwrite_concurrent_creator(self):
        script = """import os, runpy, sys
entry = sys.argv[1]
sys.argv = [entry]
original_link = os.link
def raced_link(source, target):
    with open(target, 'xb') as stream:
        stream.write(b'concurrent')
    original_link(source, target)
os.link = raced_link
runpy.run_path(entry, run_name='__main__')
"""
        result = self.call(command=[sys.executable, "-c", script, str(ENTRY)],
                           path="race.md", content="ours")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("ws_write: error: PathExists ", result.stdout)
        self.assertEqual(result.stdout, result.stderr)
        self.assertEqual((self.ws / "race.md").read_bytes(), b"concurrent")
        self.assertEqual(sorted(p.name for p in self.ws.iterdir()), ["race.md"])

    def test_workspace_unset_or_empty_even_for_absolute_paths(self):
        for value in (None, ""):
            env = dict(self.env)
            if value is None:
                env.pop("AOS_WS")
            else:
                env["AOS_WS"] = value
            for path in ("x", str(self.ws / "x")):
                with self.subTest(value=value, path=path):
                    self.error("WsMissing", env=env, path=path, content="no")
        self.assertEqual(list(self.ws.iterdir()), [])

    def test_invalid_mode_and_arguments(self):
        self.error("ArgumentsBad", path="x", content="no", mode="overwrite")
        self.error("ArgumentsBad", path="x")
        self.error("ArgumentsBad", path="x", content=12)
        self.error("ArgumentsBad", path="", content="no")
        self.assertEqual(list(self.ws.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
