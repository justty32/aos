"""Test the todo tool: the four ops, its errors and limits, where it keeps the list, and that ls never makes the cell (also through aos-tools call)."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
TOOL = Path(__file__).resolve().parents[1] / "_entry"


class TodoTool(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="todo-tool-"))
        self.cell = self.tmp / "agent" / "tools" / "todo"
        self.file = self.cell / "todo.json"
        self.env = dict(os.environ, AOS_STACK=str(self.cell), PYTHONDONTWRITEBYTECODE="1")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_tool(self, args, env=None, argv=()):
        return subprocess.run([sys.executable, str(TOOL)] + list(argv), input=json.dumps(args), capture_output=True,
                              text=True, env=env or self.env, timeout=30)

    def ok(self, args):
        r = self.run_tool(args)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stderr, "")
        return r.stdout

    def fails(self, args, code, env=None):
        r = self.run_tool(args, env)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        line = r.stderr.strip()
        self.assertTrue(line.startswith("todo: error: %s " % code), line)
        self.assertEqual(r.stdout.strip(), line)   # 給腦用的工具兩邊印同一行
        return line

    def saved(self):
        return json.loads(self.file.read_text())

    def test_ls_empty_makes_no_cell(self):
        self.assertEqual(self.ok({"op": "ls"}), "... empty (use set or add)\n")
        self.assertFalse((self.tmp / "agent").exists())
        got = json.loads(self.ok({"op": "ls", "json": True}))
        self.assertEqual(got, {"items": [], "counter_completed": 0, "updated_at": None})
        self.assertFalse((self.tmp / "agent").exists())

    def test_first_add_makes_the_cell(self):
        out = self.ok({"op": "add", "text": "read the config"})
        self.assertEqual(out, "1 [ ] read the config\n... 0 of 1 completed\n")
        data = self.saved()
        self.assertEqual(data["items"], [{"text": "read the config", "status": "pending"}])
        self.assertRegex(data["updated_at"], r"\A\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z\Z")
        self.assertEqual(sorted(os.listdir(self.cell)), ["todo.json"])   # 暫存檔改名後不留

    def test_four_ops(self):
        out = self.ok({"op": "set", "items": ["read the config format", "write the parser", "add tests"]})
        self.assertEqual(out, "1 [ ] read the config format\n2 [ ] write the parser\n3 [ ] add tests\n... 0 of 3 completed\n")
        self.ok({"op": "mark", "n": 1, "status": "completed"})
        out = self.ok({"op": "mark", "n": 2, "status": "in_progress"})
        self.assertEqual(out, "1 [x] read the config format\n2 [>] write the parser\n3 [ ] add tests\n... 1 of 3 completed\n")
        out = self.ok({"op": "add", "text": "update the docs", "after": 2})
        self.assertEqual(out.splitlines()[2:4], ["3 [ ] update the docs", "4 [ ] add tests"])
        out = self.ok({"op": "add", "text": "plan", "after": 0})
        self.assertEqual(out.splitlines()[0], "1 [ ] plan")
        self.assertEqual(self.ok({"op": "ls"}), out)
        got = json.loads(self.ok({"op": "ls", "json": True}))
        self.assertEqual([(x["n"], x["text"], x["status"]) for x in got["items"]][:3],
                         [(1, "plan", "pending"), (2, "read the config format", "completed"), (3, "write the parser", "in_progress")])
        self.assertEqual(got["counter_completed"], 1)
        self.assertEqual(got["updated_at"], self.saved()["updated_at"])
        self.assertEqual(self.ok({"op": "set", "items": []}), "... empty (use set or add)\n")
        self.assertEqual(self.saved()["items"], [])

    def test_set_mixes_strings_and_objects(self):
        out = self.ok({"op": "set", "items": ["  a  ", {"text": "b", "status": "completed"}, {"text": "c"}]})
        self.assertEqual(out, "1 [ ] a\n2 [x] b\n3 [ ] c\n... 1 of 3 completed\n")

    def test_flags(self):
        r = self.run_tool({}, argv=["--op", "set", "--items", "x", "--items", "y"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([x["text"] for x in self.saved()["items"]], ["x", "y"])

    def test_two_in_progress_note(self):
        out = self.ok({"op": "set", "items": [{"text": "a", "status": "in_progress"}, {"text": "b", "status": "in_progress"}]})
        self.assertEqual(out.splitlines()[-1], "... note: 2 items are in_progress (keep at most one)")
        self.assertNotIn("note", self.ok({"op": "mark", "n": 2, "status": "pending"}))

    def test_item_missing(self):
        self.assertIn("the list is empty", self.fails({"op": "mark", "n": 1, "status": "completed"}, "ItemMissing"))
        self.ok({"op": "set", "items": ["a", "b"]})
        self.assertIn("the list has 2 items (1 to 2)", self.fails({"op": "mark", "n": 3, "status": "completed"}, "ItemMissing"))
        self.fails({"op": "mark", "n": 0, "status": "completed"}, "ItemMissing")
        self.fails({"op": "add", "text": "c", "after": 3}, "ItemMissing")
        self.fails({"op": "add", "text": "c", "after": -1}, "ItemMissing")
        self.assertEqual(len(self.saved()["items"]), 2)

    def test_status_unknown(self):
        self.ok({"op": "set", "items": ["a"]})
        self.assertIn('(got "done")', self.fails({"op": "mark", "n": 1, "status": "done"}, "StatusUnknown"))
        self.fails({"op": "set", "items": [{"text": "a", "status": "doing"}]}, "StatusUnknown")
        self.assertEqual(self.saved()["items"], [{"text": "a", "status": "pending"}])

    def test_arguments_bad(self):
        self.fails({}, "ArgumentsBad")
        self.fails({"op": "rm"}, "OpUnknown")
        self.fails({"op": "ls", "text": "x"}, "ArgumentsBad")
        self.fails({"op": "add"}, "ArgumentsBad")
        self.fails({"op": "add", "text": "  "}, "ArgumentsBad")
        self.fails({"op": "add", "text": "two\nlines"}, "ArgumentsBad")
        self.fails({"op": "add", "text": "x" * 301}, "ArgumentsBad")
        self.fails({"op": "mark", "n": 1}, "ArgumentsBad")
        self.fails({"op": "mark", "status": "completed"}, "ArgumentsBad")
        self.fails({"op": "set"}, "ArgumentsBad")
        self.fails({"op": "set", "items": [{"text": "a", "why": "b"}]}, "ArgumentsBad")
        self.fails({"op": "set", "items": [{"status": "pending"}]}, "ArgumentsBad")
        self.fails({"op": "set", "items": ["x"] * 51}, "ArgumentsBad")
        self.assertFalse((self.tmp / "agent").exists())   # 錯了什麼都不寫
        self.ok({"op": "set", "items": ["x" * 300] * 50})
        self.assertIn("50 items", self.fails({"op": "add", "text": "one more"}, "ArgumentsBad"))

    def test_list_bad(self):
        self.cell.mkdir(parents=True)
        for broken in ("{not json", '{"items": [{"text": "a", "status": "done"}]}', "[]"):
            self.file.write_text(broken)
            line = self.fails({"op": "ls"}, "ListBad")
            self.assertIn("the saved list $AOS_STACK/todo.json ", line)
            self.assertIn("set writes a new whole list", line)
            self.assertNotIn(str(self.tmp), line)
            self.fails({"op": "add", "text": "b"}, "ListBad")
            self.fails({"op": "mark", "n": 1, "status": "completed"}, "ListBad")
            self.assertEqual(self.file.read_text(), broken)
        self.assertEqual(self.ok({"op": "set", "items": ["fixed"]}), "1 [ ] fixed\n... 0 of 1 completed\n")

    def test_keeps_file_mode(self):
        self.ok({"op": "set", "items": ["a"]})
        self.file.chmod(0o600)
        self.ok({"op": "add", "text": "b"})
        self.assertEqual(self.file.stat().st_mode & 0o777, 0o600)

    def test_write_failed(self):
        if os.geteuid() == 0:
            self.skipTest("root can write anywhere")
        (self.tmp / "agent").mkdir()
        (self.tmp / "agent").chmod(0o500)
        try:
            line = self.fails({"op": "add", "text": "a"}, "WriteFailed")
        finally:
            (self.tmp / "agent").chmod(0o700)
        # 11-12 線 errpath：錯誤行會接進 history（進 git），檔名相對 $AOS_STACK、不帶 OSError 的絕對檔名
        self.assertEqual(line, "todo: error: WriteFailed cannot write $AOS_STACK/todo.json: Permission denied")

    def test_stack_missing(self):
        env = dict(self.env)
        env.pop("AOS_STACK")
        self.fails({"op": "ls"}, "StackMissing", env)
        self.fails({"op": "add", "text": "a"}, "StackMissing", env)

    def test_through_aos_tools_call(self):
        if not (shutil.which("aos-tools") and shutil.which("aos-exec")):
            self.skipTest("aos-tools / aos-exec not on PATH (put them there with proto8/install.sh)")
        reg = self.tmp / "tools.json"
        reg.write_text(json.dumps({"tools": {"todo": {"path": str(TOOL.parent)}}}))
        stack = self.tmp / "agent"
        env = dict(os.environ, AOS_STACK=str(stack), PYTHONDONTWRITEBYTECODE="1")

        def call(args):
            r = subprocess.run(["aos-tools", "--file", str(reg), "call", "todo", json.dumps(args)], capture_output=True,
                               text=True, env=env, cwd=str(self.tmp), timeout=60)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            return r.stdout

        self.assertEqual(call({"op": "ls"}), "... empty (use set or add)\n")
        self.assertFalse((stack / "tools").exists())
        call({"op": "add", "text": "first"})
        out = call({"op": "add", "text": "second"})
        self.assertEqual(out, "1 [ ] first\n2 [ ] second\n... 0 of 2 completed\n")
        self.assertEqual([x["text"] for x in json.loads((stack / "tools" / "todo" / "todo.json").read_text())["items"]],
                         ["first", "second"])

    def test_error_through_aos_tools_names_a_path_the_caller_can_open(self):
        """11-13 fx-2：經 aos-tools 叫時錯誤行裡的存檔路徑要從叫方（腦）的 stack 算——照字面把 $AOS_STACK 換成叫方的 stack 找得到那個檔；
        原本印小格裡的 $AOS_STACK/todo.json，腦在自己的 stack 找不到。不印絕對路徑。"""
        if not (shutil.which("aos-tools") and shutil.which("aos-exec")):
            self.skipTest("aos-tools / aos-exec not on PATH (put them there with proto8/install.sh)")
        reg = self.tmp / "tools.json"
        reg.write_text(json.dumps({"tools": {"todo": {"path": str(TOOL.parent)}}}))
        stack = self.tmp / "agent"
        self.cell.mkdir(parents=True)
        self.file.write_text("{not json")
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        env.update(AOS_STACK=str(stack), PYTHONDONTWRITEBYTECODE="1")
        r = subprocess.run(["aos-tools", "--file", str(reg), "call", "todo", json.dumps({"op": "ls"})], capture_output=True,
                           text=True, env=env, cwd=str(self.tmp), timeout=60)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        line = r.stdout.strip()
        self.assertTrue(line.startswith("todo: error: ListBad the saved list $AOS_STACK/tools/todo/todo.json is not JSON"), line)
        shown = line.split("the saved list ", 1)[1].split(" ", 1)[0]
        self.assertTrue(Path(shown.replace("$AOS_STACK", str(stack), 1)).is_file(), shown)   # 叫方照字面找得到
        self.assertNotIn(str(self.tmp), r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
