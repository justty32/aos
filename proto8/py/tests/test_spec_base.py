"""Test py/aos/spec_base.py: the shared base of agent_spec and tool_spec - one SpecBad / DefBad, prog_name, the --compile [LOCATION] / --dry-run shell, and write_files (text, JSON, program 755, link; temp files then rename, nothing left behind on failure)."""
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
import unittest.mock

sys.dont_write_bytecode = True
LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
from aos import spec_base as sb  # noqa: E402
from aos import tool_spec, agent_spec, agent_spec_parts, agent_spec_load  # noqa: E402


def mode(p):
    return stat.S_IMODE(os.lstat(p).st_mode)


class Names(unittest.TestCase):
    def test_one_exception_class_each(self):
        for m in (tool_spec, agent_spec, agent_spec_parts, agent_spec_load):
            self.assertIs(m.SpecBad, sb.SpecBad)
        for m in (agent_spec, agent_spec_parts, agent_spec_load):
            self.assertIs(m.DefBad, sb.DefBad)
        self.assertTrue(issubclass(sb.DefBad, ValueError))

    def test_prog_name(self):
        self.assertEqual(sb.prog_name("/x/weather/agent.py", "agent.py"), "weather")
        self.assertEqual(sb.prog_name("/x/weather/other.py", "agent.py"), "other")
        self.assertEqual(sb.prog_name("/x/add/tool.py", "tool.py"), "add")
        self.assertEqual(sb.prog_name("/x/add/mul.py", "tool.py"), "mul")

    def test_location(self):
        said = []

        def die(code, msg):
            said.append((code, msg))
            raise SystemExit(1)
        self.assertEqual(sb.location("--compile", [], ["--compile"], "/x/a/agent.py", "usage: u", die), "/x/a")
        self.assertEqual(sb.location("--compile", ["out"], ["--compile", "out"], "/x/a/agent.py", "usage: u", die), "out")
        self.assertEqual(sb.location("--dry-run", [], ["--dry-run", "--static"], "/x/a/agent.py", "usage: u", die), "/x/a")
        for mode_, rest in (("--compile", ["a", "b"]), ("--dry-run", ["a"])):
            self.assertRaises(SystemExit, sb.location, mode_, rest, [mode_] + rest, "/x/a/tool.py", "usage: u", die)
        self.assertEqual(said[-1], ("ArgumentsBad", "too many arguments: --dry-run a (usage: u)"))


class WriteFiles(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="spec-base-")
        self.d = self._tmp.name
        self.target = os.path.join(self.d, "target.txt")      # the link target: never touched
        Path(self.target).write_text("shared\n")

    def tearDown(self):
        self._tmp.cleanup()

    def leftovers(self, folder=None):
        return [n for n in os.listdir(folder or self.d) if ".tmp-" in n]

    def test_four_kinds_written_and_read_back(self):
        sb.write_files(self.d, {"a.txt": "plain text\n", "b.json": {"k": ["v", 1], "u": "é"},
                                "run.py": sb.Program("#!/bin/sh\necho hi\n"), "c": sb.Link("target.txt")})
        self.assertEqual(Path(self.d, "a.txt").read_text(), "plain text\n")
        self.assertEqual(Path(self.d, "b.json").read_text(encoding="utf-8"), '{\n  "k": [\n    "v",\n    1\n  ],\n  "u": "é"\n}\n')
        self.assertEqual(Path(self.d, "run.py").read_text(), "#!/bin/sh\necho hi\n")
        self.assertEqual(mode(os.path.join(self.d, "run.py")), 0o755)
        self.assertEqual(os.readlink(os.path.join(self.d, "c")), "target.txt")
        self.assertEqual(Path(self.d, "c").read_text(), "shared\n")
        self.assertEqual(self.leftovers(), [])

    def test_program_is_755_over_an_old_file(self):
        p = os.path.join(self.d, "run.py")
        Path(p).write_text("old\n")
        os.chmod(p, 0o600)
        sb.write_files(self.d, {"run.py": sb.Program("new\n")})
        self.assertEqual(mode(p), 0o755)

    def test_text_keeps_the_old_mode(self):
        p = os.path.join(self.d, "a.txt")
        Path(p).write_text("old\n")
        os.chmod(p, 0o640)
        sb.write_files(self.d, {"a.txt": "new\n"})
        self.assertEqual((Path(p).read_text(), mode(p)), ("new\n", 0o640))

    def test_link_and_file_replace_each_other_target_untouched(self):
        p = os.path.join(self.d, "system.txt")
        Path(p).write_text("hand\n")
        sb.write_files(self.d, {"system.txt": sb.Link(self.target)})        # file -> link
        self.assertEqual(os.readlink(p), self.target)
        sb.write_files(self.d, {"system.txt": sb.Link("elsewhere.txt")})    # link -> link (a broken one is fine)
        self.assertEqual(os.readlink(p), "elsewhere.txt")
        sb.write_files(self.d, {"system.txt": sb.Link(self.target)})
        sb.write_files(self.d, {"system.txt": "compiled\n"})               # link -> file: the link is replaced, not written through
        self.assertFalse(os.path.islink(p))
        self.assertEqual(Path(p).read_text(), "compiled\n")
        self.assertEqual(Path(self.target).read_text(), "shared\n")
        self.assertEqual(self.leftovers(), [])

    def test_failure_midway_leaves_the_folder_as_it_was(self):
        Path(self.d, "a.txt").write_text("old\n")
        before = sorted(os.listdir(self.d))
        self.assertRaises(TypeError, sb.write_files, self.d, {"a.txt": "new\n", "b.json": {"x": object()}})
        self.assertEqual(sorted(os.listdir(self.d)), before)
        self.assertEqual(Path(self.d, "a.txt").read_text(), "old\n")

    def test_link_then_failure_no_temp_link_no_empty_subfolder(self):
        before = sorted(os.listdir(self.d))
        self.assertRaises(TypeError, sb.write_files, self.d, {"fn/add.py": sb.Link("/no/such/place"), "b.json": {1, 2}})
        self.assertEqual(sorted(os.listdir(self.d)), before)                 # the broken temp link and fn/ are gone
        os.mkdir(os.path.join(self.d, "fn"))                                 # a sub-folder that was there stays
        self.assertRaises(TypeError, sb.write_files, self.d, {"fn/add.py": sb.Link("/no/such/place"), "b.json": {1, 2}})
        self.assertEqual(os.listdir(os.path.join(self.d, "fn")), [])

    def test_subfolder_made_and_kept_on_success(self):
        sb.write_files(self.d, {"fn/add.py": sb.Program("x\n"), "fn/hook.py": sb.Link("../target.txt")})
        self.assertEqual(sorted(os.listdir(os.path.join(self.d, "fn"))), ["add.py", "hook.py"])
        self.assertEqual(Path(self.d, "fn", "hook.py").read_text(), "shared\n")

    def test_left_over_temp_of_the_same_name_is_cleared(self):
        sentinel = os.path.join(self.d, "sentinel.txt")
        Path(sentinel).write_text("keep\n")
        for name in ("a.txt", "b"):
            os.symlink(sentinel, os.path.join(self.d, ".%s.tmp-%d" % (name, os.getpid())))   # a temp link left by a crash
        sb.write_files(self.d, {"a.txt": "new\n", "b": sb.Link(self.target)})
        self.assertEqual(Path(sentinel).read_text(), "keep\n")
        self.assertEqual((Path(self.d, "a.txt").read_text(), os.readlink(os.path.join(self.d, "b"))), ("new\n", self.target))
        self.assertEqual(self.leftovers(), [])

    def test_rename_order_follows_last(self):
        order, replace = [], os.replace
        with unittest.mock.patch("os.replace", lambda a, b: (order.append(os.path.basename(b)), replace(a, b))):
            sb.write_files(self.d, {"index.json": {}, "a": "a", "b": sb.Link("x"), "c": {}}, last={"index.json": 2, "b": 1})
        self.assertEqual(order, ["a", "c", "b", "index.json"])

    def test_rename_failure_cleans_temp_files(self):
        def fail(a, b):
            raise OSError("replace fails")
        with unittest.mock.patch("os.replace", fail):
            self.assertRaisesRegex(OSError, "replace fails", sb.write_files, self.d, {"a": "a", "fn/b": sb.Link("x")})
        self.assertEqual(sorted(os.listdir(self.d)), ["target.txt"])

    def test_bad_names_and_not_a_folder(self):
        for name in ("", "/abs", "../up", "a/b/c", "a//b", "./a", "fn/.."):
            with self.subTest(name=name):
                self.assertRaises(ValueError, sb.write_files, self.d, {name: "x"})
        self.assertRaisesRegex(OSError, "is not a folder", sb.write_files, self.target, {"a": "x"})
        self.assertEqual(sorted(os.listdir(self.d)), ["target.txt"])


if __name__ == "__main__":
    unittest.main()
