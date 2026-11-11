"""Test that aos-tools call does not create the tool cell beforehand (11-11 tool-cells-lazy): a read-only tool leaves no folder, a writing tool makes its own."""
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

LOOK = """#!/usr/bin/env python3
import json, os, sys
if sys.argv[1:] == ["--tooldef"]:
    print(json.dumps({"description": "look only"}))
    sys.exit(0)
sys.stdin.read()
cell = os.environ["AOS_STACK"]
print(json.dumps({"stack": cell, "exists": os.path.isdir(cell)}))
"""

WRITE = """#!/usr/bin/env python3
import json, os, sys
if sys.argv[1:] == ["--tooldef"]:
    print(json.dumps({"description": "write a note"}))
    sys.exit(0)
sys.stdin.read()
cell = os.environ["AOS_STACK"]
os.makedirs(cell, exist_ok=True)
with open(os.path.join(cell, "note.txt"), "w") as f:
    f.write("hi")
print("wrote")
"""


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    env["PATH"] = os.path.expanduser("~/.local/bin") + os.pathsep + env.get("PATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.update(extra)
    return env


class CellLazy(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="aos-tools-lazy-"))
        self.stack = self.tmp / "stack"
        self.stack.mkdir()
        self.reg = self.tmp / "tools.json"
        tools = {}
        for name, body in (("look", LOOK), ("write", WRITE)):
            p = self.tmp / "bin" / name
            p.parent.mkdir(exist_ok=True)
            p.write_text(body)
            p.chmod(0o755)
            tools[name] = {"path": str(p)}
        self.reg.write_text(json.dumps({"tools": tools}))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def call(self, name):
        r = subprocess.run([sys.executable, str(BIN), "--file", str(self.reg), "call", name, "{}"], cwd=self.tmp,
                           env=clean_env(AOS_STACK=str(self.stack), AOS_WS=str(self.tmp)), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_read_only_tool_leaves_nothing(self):
        out = json.loads(self.call("look"))
        self.assertEqual(out["stack"], str(self.stack / "tools" / "look") + "/")
        self.assertFalse(out["exists"])
        self.assertEqual(list(self.stack.iterdir()), [])

    def test_writing_tool_makes_its_own_cell(self):
        self.assertEqual(self.call("write"), "wrote\n")
        self.assertEqual((self.stack / "tools" / "write" / "note.txt").read_text(), "hi")
        self.assertEqual(sorted(p.name for p in (self.stack / "tools").iterdir()), ["write"])


if __name__ == "__main__":
    unittest.main()
