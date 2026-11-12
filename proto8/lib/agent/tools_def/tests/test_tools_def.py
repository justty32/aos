"""Test tools_def new (copy the skeleton, description, PathExists, outside the workspace, into JSON objects), check (folder, JSON file, FILE#/POINTER, bad lines, sample call, stage) and the step-by-step ops add_entry, add_metainfo, add_tooldef."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
TOOL = Path(__file__).resolve().parents[1] / "_entry"
PROTO = Path(__file__).resolve().parents[4]


class ToolsDef(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tools-def-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(os.path.realpath(self.temp.name))
        self.ws = self.root / "ws"
        self.ws.mkdir()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        self.env.update(AOS_WS=str(self.ws), AOS_HOME=str(PROTO), PYTHONDONTWRITEBYTECODE="1")

    def run_tool(self, args):
        return subprocess.run([sys.executable, str(TOOL)], input=json.dumps(args), text=True,
                              capture_output=True, env=self.env, timeout=120)

    def make_mul(self, path="t/mul"):
        r = self.run_tool({"op": "new", "path": path, "description": 'Multiply. Example: {"a": 6, "b": 7} -> 42'})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        script = (self.ws / path / "tool.py") if not os.path.isabs(path) else Path(path) / "tool.py"
        script.write_text(script.read_text().replace('return args["a"] + args["b"]', 'return args["a"] * args["b"]'))
        return script

    def test_new_copies_and_fills_description(self):
        self.make_mul()
        d = self.ws / "t" / "mul"
        self.assertEqual(sorted(p.name for p in d.iterdir()), ["README.md", "_entry.json", "_metainfo.json", "_tooldef.json", "tool.py"])
        self.assertTrue(json.loads((d / "_tooldef.json").read_text())["description"].startswith("Multiply."))
        self.assertEqual([p.name for p in (self.ws / "t").iterdir()], ["mul"])           # 沒留暫存夾
        r = self.run_tool({"op": "new", "path": "t/mul"})
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stdout.startswith("tools_def: error: PathExists"))

    def test_check_ok_with_sample_outside_workspace(self):
        out = self.root / "elsewhere" / "mul"
        self.make_mul(str(out))
        r = self.run_tool({"op": "check", "path": str(out), "sample": {"a": 6, "b": 7}})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("made  _tooldef and _metainfo from tool.py", r.stdout)
        self.assertIn('ok    try: {"a": 6, "b": 7} -> exit 0: 42', r.stdout)
        self.assertTrue(r.stdout.splitlines()[-1].startswith("stage 3 of 3"), r.stdout)

    def test_check_bad_lines(self):
        script = self.make_mul()
        good = script.read_text()
        for broken, want in ((good.replace('args["b"]\n', '\n'), "bad   entry: tool.py line"),
                             (good.replace('"number", "the first number"', '"num", "the first number"'), "SpecBad param a: type 'num'"),
                             (good.replace('return args["a"] * args["b"]', 'return args["a"] / 0'), "RunFailed run() raised ZeroDivisionError")):
            with self.subTest(want=want):
                script.write_text(broken)
                r = self.run_tool({"op": "check", "path": "t/mul", "sample": {"a": 1, "b": 2}})
                self.assertEqual(r.returncode, 1)
                self.assertIn(want, r.stdout)
                self.assertIn("fix the lines marked bad", r.stdout)
                self.assertRegex(r.stdout, r"tools_def: error: ToolBad \d problem\(s\) above; fix the lines marked bad and check again\n\Z")

    def test_check_catches_overwritten_or_unchanged_skeleton(self):
        r = self.run_tool({"op": "new", "path": "t/plain"})
        self.assertIn("---- t/plain/tool.py, the part to change ----\nDESCRIPTION = ", r.stdout)       # new 直接給要改的那段
        self.assertTrue(r.stdout.rstrip().endswith("ts.main(run, DESCRIPTION, PARAMS, META)"), r.stdout)
        r = self.run_tool({"op": "check", "path": "t/plain"})
        self.assertIn("description is still the skeleton's", r.stdout)
        (self.ws / "t" / "plain" / "tool.py").write_text("def multiply(a, b):\n    return a * b\n")   # gemma 第 1 輪的寫法
        r = self.run_tool({"op": "check", "path": "t/plain", "sample": {"a": 6, "b": 7}})
        self.assertEqual(r.returncode, 1)
        self.assertIn("bad   defs: tool.py does not use tool_spec any more", r.stdout)
        self.assertIn("skip  try: not tried", r.stdout)

    def test_example_in_description_is_tried(self):
        script = self.make_mul()
        r = self.run_tool({"op": "check", "path": "t/mul"})
        self.assertIn('ok    example: {"a": 6, "b": 7} -> 42 (as the description says)', r.stdout)
        script.write_text(script.read_text().replace('args["a"] * args["b"]', 'args["a"] + args["b"]'))   # gemma 第 3 輪：只改了說明
        r = self.run_tool({"op": "check", "path": "t/mul"})
        self.assertEqual(r.returncode, 1)
        self.assertIn('bad   example: the description says {"a": 6, "b": 7} -> 42, but the tool gave 13', r.stdout)

    def test_check_json_file_and_pointer(self):
        script = self.make_mul()
        (self.ws / "j").mkdir()
        (self.ws / "j" / "tool.py").write_text(script.read_text())
        (self.ws / "j" / "one.json").write_text('{"_entry": ["python3", "tool.py"]}')
        (self.ws / "j" / "box.json").write_text('{"tools": {"mul": {"_entry": ["python3", "tool.py"]}}}')
        r = self.run_tool({"op": "check", "path": "j/one.json", "sample": {"a": 2, "b": 4}})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("exit 0: 8", r.stdout)
        self.assertIn("_tooldef", json.loads((self.ws / "j" / "one.json").read_text()))
        r = self.run_tool({"op": "check", "path": "j/box.json#/tools/mul", "sample": {"a": 3, "b": 4}})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("exit 0: 12", r.stdout)
        self.assertIn('self_tools {"op": "add", "path": "j/box.json#/tools/mul"}; it works at once: in your next reply', r.stdout)
        self.assertIn('like any other tool: mul {"a": 3, "b": 4}', r.stdout)
        self.assertIn("_metainfo", json.loads((self.ws / "j" / "box.json").read_text())["tools"]["mul"])

    def test_new_into_json_objects(self):
        for name in ("mul", "twice"):
            r = self.run_tool({"op": "new", "path": "k/box.json#/tools/" + name})
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("---- k/%s.py, the part to change ----" % name, r.stdout)
        box = json.loads((self.ws / "k" / "box.json").read_text())["tools"]
        self.assertEqual(box["mul"]["_entry"], ["python3", "mul.py"])
        self.assertEqual(sorted(box["twice"]), ["_entry", "_metainfo", "_tooldef"])
        script = self.ws / "k" / "mul.py"
        script.write_text(script.read_text().replace("Add two numbers and return the sum. Example: {\"a\": 2, \"b\": 3} -> 5",
                                                     "Multiply. Example: {\"a\": 6, \"b\": 7} -> 42")
                          .replace('return args["a"] + args["b"]', 'return args["a"] * args["b"]'))
        r = self.run_tool({"op": "check", "path": "k/box.json#/tools/mul", "sample": {"a": 6, "b": 7}})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("exit 0: 42", r.stdout)
        self.assertIn("ok    tooldef: valid", r.stdout)                 # aos-tools add + get took the pointer
        r = self.run_tool({"op": "new", "path": "k/box.json#/tools/mul"})
        self.assertTrue(r.stdout.startswith("tools_def: error: PathExists"), r.stdout)

    def test_step_by_step_folder_with_tool_spec_script(self):
        r = self.run_tool({"op": "add_entry", "path": "fn"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("stage 1 of 3", r.stdout)
        self.assertEqual(json.loads((self.ws / "fn" / "_entry.json").read_text()), {"argv": ["python3", "tool.py"]})
        r = self.run_tool({"op": "add_metainfo", "path": "fn"})
        self.assertIn("(from tool.py)", r.stdout)
        self.assertIn("stage 2 of 3", r.stdout)
        r = self.run_tool({"op": "add_tooldef", "path": "fn"})
        self.assertIn("stage 3 of 3", r.stdout)
        self.assertEqual(json.loads((self.ws / "fn" / "_tooldef.json").read_text())["parameters"]["required"], ["a", "b"])
        r = self.run_tool({"op": "add_entry", "path": "fn"})
        self.assertTrue(r.stdout.startswith("tools_def: error: PathExists"), r.stdout)

    def test_step_by_step_json_object_with_plain_script(self):
        (self.ws / "h").mkdir()
        (self.ws / "h" / "f.py").write_text('import json, sys\na = json.load(sys.stdin)\nprint(a["a"] * a["b"])\n')
        (self.ws / "h" / "fs.json").write_text('{"note": "kept"}')
        r = self.run_tool({"op": "add_entry", "path": "h/fs.json#/f"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("kept the script f.py", r.stdout)
        r = self.run_tool({"op": "add_metainfo", "path": "h/fs.json#/f"})
        self.assertTrue(r.stdout.startswith("tools_def: error: ArgumentsBad description is needed"), r.stdout)
        desc = 'Multiply two numbers. Example: {"a": 6, "b": 7} -> 42'
        r = self.run_tool({"op": "add_metainfo", "path": "h/fs.json#/f", "description": desc})
        self.assertIn("stage 2 of 3", r.stdout)
        r = self.run_tool({"op": "add_tooldef", "path": "h/fs.json#/f", "description": desc,
                           "params": [{"name": "a", "type": "number", "description": "first"},
                                      {"name": "b", "type": "number", "description": "second"}]})
        self.assertIn("stage 3 of 3", r.stdout)
        r = self.run_tool({"op": "check", "path": "h/fs.json#/f", "sample": {"a": 2, "b": 5}})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("note  defs: f.py does not use tool_spec", r.stdout)
        self.assertIn("ok    example:", r.stdout)
        self.assertIn("exit 0: 10", r.stdout)
        self.assertEqual(json.loads((self.ws / "h" / "fs.json").read_text())["note"], "kept")
        r = self.run_tool({"op": "add_tooldef", "path": "h/fs.json#/f", "description": desc})
        self.assertTrue(r.stdout.startswith("tools_def: error: PathExists"), r.stdout)

    def test_check_runnable_function_only_and_handwritten_tool(self):
        (self.ws / "f").mkdir()
        (self.ws / "f" / "_entry.json").write_text('["python3", "-c", "print(1)"]')
        r = self.run_tool({"op": "check", "path": "f"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("stage 1 of 3 (entry, _metainfo, _tooldef); missing: _metainfo, _tooldef", r.stdout)
        r = self.run_tool({"op": "check", "path": str(PROTO / "lib" / "base" / "math"), "sample": {"expr": "6*7"}})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("made", r.stdout)                                               # 手寫的工具不重產
        self.assertIn("exit 0: 42", r.stdout)

    def test_tooldef_inside_metainfo_counts(self):
        # 11-12 metainfo（N-69、M20、M22）：只有 _metainfo.json 的 tooldef 也算「有」；兩處都有多一行 note
        d = self.ws / "m"
        d.mkdir()
        (d / "_entry.json").write_text('["python3", "-c", "import json,sys; a=json.load(sys.stdin); print(a[\\"a\\"]*a[\\"b\\"])"]')
        td = {"description": "Multiply a by b.", "parameters": {"type": "object", "properties": {
            "a": {"type": "number", "description": "a"}, "b": {"type": "number", "description": "b"}}}}
        (d / "_metainfo.json").write_text(json.dumps({"summary": "Multiply", "tooldef": td}))
        r = self.run_tool({"op": "check", "path": "m", "sample": {"a": 6, "b": 7}})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("stage 3 of 3", r.stdout)
        self.assertIn("exit 0: 42", r.stdout)
        self.assertNotIn("both", r.stdout)
        r = self.run_tool({"op": "add_tooldef", "path": "m", "description": "x"})
        self.assertTrue(r.stdout.startswith("tools_def: error: PathExists"), r.stdout)
        (d / "_tooldef.json").write_text(json.dumps({"description": "Multiply two numbers."}))
        r = self.run_tool({"op": "check", "path": "m"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("note  tooldef: both _metainfo.json#/tooldef and _tooldef.json; _tooldef.json wins on the same key", r.stdout)
        self.assertIn("valid, parameters: a, b", r.stdout)
        # 壞的裡面不擋好的外面（比照使用者 11-12 對 index_view 的裁定）
        (d / "_metainfo.json").write_text(json.dumps({"summary": "Multiply", "tooldef": "nope"}))
        (d / "_tooldef.json").write_text(json.dumps(td))
        r = self.run_tool({"op": "check", "path": "m"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("note  tooldef: _metainfo.json#/tooldef is not an object, skipped; using _tooldef.json", r.stdout)
        self.assertIn("stage 3 of 3", r.stdout)

    def test_arguments(self):
        for args, want in (({}, "ArgumentsBad"), ({"op": "x"}, "OpUnknown"), ({"op": "check", "path": "a", "sample": {}, "zz": 1}, "ArgumentsBad"),
                           ({"op": "new", "path": "a", "sample": {}}, "ArgumentsBad op new does not take sample"),
                           ({"op": "check", "path": "nope"}, "PathMissing")):
            with self.subTest(args=args):
                r = self.run_tool(args)
                self.assertEqual(r.returncode, 1)
                self.assertTrue(r.stdout.startswith("tools_def: error: " + want), r.stdout)


if __name__ == "__main__":
    unittest.main()
