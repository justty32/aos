"""Test aos-tools reading the tool definition from _metainfo's tooldef as well as the separate _tooldef (11-12 metainfo, N-69): merged one level deep, outside wins."""
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
SCHEMA_IN = {"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}}}
SCHEMA_OUT = {"type": "object", "properties": {"a": {"type": "number"}}}
INSIDE = {"description": "inside", "parameters": SCHEMA_IN, "errors": ["InsideOnly"]}
OUTSIDE = {"description": "outside", "parameters": SCHEMA_OUT}


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    env["PATH"] = os.path.expanduser("~/.local/bin") + os.pathsep + env.get("PATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.update(extra)
    return env


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="aos-tools-meta-"))
        self.reg = self.tmp / "tools.json"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_tools(self, *args):
        return subprocess.run([sys.executable, str(BIN), "--file", str(self.reg)] + [str(a) for a in args],
                              cwd=self.tmp, env=clean_env(), capture_output=True, text=True)

    def get(self, loc):
        r = self.run_tools("add", "--name", "t", loc)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.run_tools("get", "t")
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)["tooldef"]

    def fails(self, loc, code):
        r = self.run_tools("add", "--name", "t", loc)
        self.assertEqual(r.returncode, 1)
        self.assertIn(code, r.stderr)
        return r.stderr


class DirTool(Base):
    def make(self, inside=None, outside=None, meta=True):
        d = self.tmp / "mul"
        d.mkdir()
        (d / "_entry").write_text("#!/usr/bin/env python3\n" + MUL)
        (d / "_entry").chmod(0o755)
        if meta:
            m = {"summary": "Multiply", "timeout_ms": 5000}
            if inside is not None:
                m["tooldef"] = inside
            (d / "_metainfo.json").write_text(json.dumps(m))
        if outside is not None:
            (d / "_tooldef.json").write_text(json.dumps(outside))
        return "mul"

    def test_outside_only(self):
        self.assertEqual(self.get(self.make(outside=OUTSIDE)), OUTSIDE)

    def test_inside_only_add_get_call(self):
        self.assertEqual(self.get(self.make(inside=INSIDE)), INSIDE)
        r = self.run_tools("call", "t", '{"a": 6, "b": 7}')
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "42"), r.stderr)

    def test_both_outside_wins_per_top_key(self):
        td = self.get(self.make(inside=INSIDE, outside=OUTSIDE))
        self.assertEqual(td, {"description": "outside", "parameters": SCHEMA_OUT, "errors": ["InsideOnly"]})

    def test_neither_is_missing(self):
        self.assertIn("tooldef key in _metainfo.json", self.fails(self.make(), "ToolDefMissing"))

    def test_inside_not_object_is_bad(self):
        err = self.fails(self.make(inside="nope", outside=OUTSIDE), "ToolDefBad")
        self.assertIn("_metainfo.json#/tooldef", err)


class PointerTool(Base):
    def make(self, inside=None, outside=None):
        obj = {"_entry": ["python3", "mul.py"], "_metainfo": {"timeout_ms": 5000}}
        if inside is not None:
            obj["_metainfo"]["tooldef"] = inside
        if outside is not None:
            obj["_tooldef"] = outside
        (self.tmp / "mul.py").write_text(MUL)
        (self.tmp / "box.json").write_text(json.dumps({"tools": {"mul": obj}}))
        return "box.json#/tools/mul"

    def test_outside_only(self):
        self.assertEqual(self.get(self.make(outside=OUTSIDE)), OUTSIDE)

    def test_inside_only(self):
        self.assertEqual(self.get(self.make(inside=INSIDE)), INSIDE)
        r = self.run_tools("call", "t", '{"a": 2, "b": 3}')
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "6"), r.stderr)

    def test_both_outside_wins_per_top_key(self):
        td = self.get(self.make(inside=INSIDE, outside=OUTSIDE))
        self.assertEqual(td, {"description": "outside", "parameters": SCHEMA_OUT, "errors": ["InsideOnly"]})

    def test_neither_is_missing(self):
        self.fails(self.make(), "ToolDefMissing")


if __name__ == "__main__":
    unittest.main()
