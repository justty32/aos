"""Test that aos-tools call tells the tool where its cell sits in the caller's stack (AOS_STACK_IN_CALLER=tools/NAME), and drops a stale one when there is no parent stack."""
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

SEE = """#!/usr/bin/env python3
import json, os, sys
if sys.argv[1:] == ["--tooldef"]:
    print(json.dumps({"description": "print what the call gave"}))
    sys.exit(0)
sys.stdin.read()
print(json.dumps({"stack": os.environ.get("AOS_STACK"), "in_caller": os.environ.get("AOS_STACK_IN_CALLER")}))
"""


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    env["PATH"] = os.path.expanduser("~/.local/bin") + os.pathsep + env.get("PATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.update(extra)
    return env


class StackInCaller(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="aos-tools-in-caller-"))
        self.stack = self.tmp / "stack"
        self.stack.mkdir()
        self.reg = self.tmp / "tools.json"
        p = self.tmp / "bin" / "see"
        p.parent.mkdir()
        p.write_text(SEE)
        p.chmod(0o755)
        self.reg.write_text(json.dumps({"tools": {
            "see": {"path": str(p)},
            "see_env": {"path": str(p), "env": {"AOS_STACK_IN_CALLER": "tools/from-the-registry"}}}}))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def call(self, name, **env):
        r = subprocess.run([sys.executable, str(BIN), "--file", str(self.reg), "call", name, "{}"], cwd=self.tmp,
                           env=clean_env(AOS_WS=str(self.tmp), **env), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_the_tool_is_told_where_its_cell_sits_in_the_callers_stack(self):
        out = self.call("see", AOS_STACK=str(self.stack))
        self.assertEqual(out["in_caller"], "tools/see")
        self.assertEqual(os.path.join(str(self.stack), out["in_caller"], ""), out["stack"])   # 叫方的 stack＋這個值＝工具的小格

    def test_each_call_sets_its_own_over_an_inherited_or_registered_one(self):
        out = self.call("see", AOS_STACK=str(self.stack), AOS_STACK_IN_CALLER="tools/outer")   # 工具再叫工具：外層那個不往下傳
        self.assertEqual(out["in_caller"], "tools/see")
        out = self.call("see_env", AOS_STACK=str(self.stack))                                  # 登記格 env 蓋不掉（同小格）
        self.assertEqual(out["in_caller"], "tools/see_env")

    def test_no_parent_stack_means_no_variable(self):
        out = self.call("see", AOS_STACK_IN_CALLER="tools/stale")
        self.assertIsNone(out["in_caller"])
        out = self.call("see_env")
        self.assertIsNone(out["in_caller"])
        shutil.rmtree(self.tmp / ".stack", ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
