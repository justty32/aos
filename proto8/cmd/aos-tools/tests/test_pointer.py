"""Test aos-tools with FILE.json#/POINTER locations: add (stored form, default name), ls -l, get, call through aos-exec, rm by path, and the errors."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[3]
BIN = PROTO / "cmd" / "aos-tools" / "bin" / "aos-tools"
MUL = 'import json, sys\na = json.load(sys.stdin)\nprint(a["a"] * a["b"])\n'
SCHEMA = {"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}}}


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    env["PATH"] = os.path.expanduser("~/.local/bin") + os.pathsep + env.get("PATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.update(extra)
    return env


class PointerLocations(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="aos-tools-ptr-"))
        (self.tmp / "box").mkdir()
        (self.tmp / "box" / "mul.py").write_text(MUL)
        box = {"tools": {"mul": {"_entry": ["python3", "mul.py"],
                                 "_tooldef": {"description": "Multiply two numbers.", "parameters": SCHEMA},
                                 "_metainfo": {"timeout_ms": 5000}},
                         "a~b": {"_entry": ["python3", "mul.py"], "_tooldef": {"description": "Same."}},
                         "nodef": {"_entry": ["python3", "mul.py"]}}}
        (self.tmp / "box" / "box.json").write_text(json.dumps(box))
        (self.tmp / "def").mkdir()
        self.reg = self.tmp / "def" / "tools.json"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_tools(self, *args):
        return subprocess.run([sys.executable, str(BIN), "--file", str(self.reg)] + [str(a) for a in args],
                              cwd=self.tmp, env=clean_env(), capture_output=True, text=True)

    def ok(self, *args):
        r = self.run_tools(*args)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_add_ls_get_call_rm(self):
        out = self.ok("add", "box/box.json#/tools/mul")
        self.assertIn("added mul -> %s#/tools/mul" % (self.tmp / "box" / "box.json"), out)
        self.assertEqual(json.loads(self.reg.read_text())["tools"]["mul"], {"path": "../box/box.json#/tools/mul"})
        self.assertIn("mul\tjson\t%s#/tools/mul" % (self.tmp / "box" / "box.json"), self.ok("ls", "-l"))
        got = json.loads(self.ok("get", "mul"))
        self.assertEqual((got["kind"], got["metainfo"]), ("json", {"timeout_ms": 5000}))
        self.assertEqual(got["tooldef"]["parameters"], SCHEMA)
        self.assertEqual(self.ok("call", "mul", '{"a": 6, "b": 7}').strip(), "42")
        self.assertIn("removed mul", self.ok("rm", "box/box.json#/tools/mul"))

    def test_name_is_last_pointer_part_and_absolute_stays(self):
        path = "%s#/tools/a~0b" % (self.tmp / "box" / "box.json")
        r = self.run_tools("add", path)
        self.assertNotEqual(r.returncode, 0)                 # a~b is not a valid tool name
        self.assertIn("NameBad", r.stderr)
        self.ok("add", "--name", "ab", path)
        self.assertEqual(json.loads(self.reg.read_text())["tools"]["ab"], {"path": path})

    def test_path_json_relative_to_registry(self):
        self.ok("add", "--name", "m", "--path-json", '"../box/box.json#/tools/mul"')
        self.assertEqual(self.ok("call", "m", '{"a": 2, "b": 3}').strip(), "6")

    def test_errors(self):
        r = self.run_tools("add", "box/box.json#/tools/nodef")
        self.assertIn("ToolDefMissing", r.stderr)
        r = self.run_tools("add", "box/box.json#/tools/zz")
        self.assertIn("PathMissing", r.stderr)
        r = self.run_tools("add", "box/none.json#/tools/mul")
        self.assertIn("PathMissing", r.stderr)


if __name__ == "__main__":
    unittest.main()
