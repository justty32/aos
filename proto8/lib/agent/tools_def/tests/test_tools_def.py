"""Test tools_def new (copy the skeleton, description, PathExists, outside the workspace) and check (folder, JSON file, FILE#/POINTER, bad lines, sample call, stage)."""
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
        self.assertIn("self_tools add cannot take FILE#/POINTER yet", r.stdout)
        self.assertIn("_metainfo", json.loads((self.ws / "j" / "box.json").read_text())["tools"]["mul"])

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
