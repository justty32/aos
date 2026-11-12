"""Test agent_def tools / llm / system (change a definition directly; args shaped like self_*) in a temp folder, with this repo's aos-tools and aos-json."""
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
PROTO = Path(__file__).resolve().parents[4]
NAME = TOOL.parent.name
BINS = [PROTO / "cmd" / "aos-tools" / "bin", PROTO / "impls" / "aos-json" / "bin", PROTO / "impls" / "aos-directive" / "bin"]


def make_def(d):
    d.mkdir(parents=True)
    (d / "README.md").write_text("A test definition.\n")
    (d / "_metainfo.json").write_text('{"summary": "test"}')
    (d / "interfaces.json").write_text('{"aos-agent": {"tools": "tools.json", "llm": "llm.json", "system": "system.txt", "llm_keys": ["model"]}}')
    (d / "tools.json").write_text('{"tools": {}}')
    (d / "llm.json").write_text('{"model": "fake"}')
    (d / "system.txt").write_text("You are a test.\n")
    return d


@unittest.skipUnless((BINS[0] / "aos-tools").is_file() and (BINS[1] / "aos-json").is_file(), "aos-tools / aos-json not built")
class DefEdit(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="agent-def-edit-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(os.path.realpath(self.temp.name))
        self.ws = self.root / "ws"
        self.ws.mkdir()
        self.d = make_def(self.ws / "defs" / "helper")
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        self.env.update(AOS_WS=str(self.ws), AOS_HOME=str(PROTO), PYTHONDONTWRITEBYTECODE="1",
                        PATH=os.pathsep.join([str(b) for b in BINS] + [os.environ.get("PATH", "")]))

    def run_tool(self, op, args, path="defs/helper"):
        return subprocess.run([sys.executable, str(TOOL)], input=json.dumps({"op": op, "path": path, "args": args}), text=True,
                              capture_output=True, env=self.env, timeout=60)

    def ok(self, op, args, **kw):
        r = self.run_tool(op, args, **kw)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        return r

    def fails(self, op, args, code, **kw):
        r = self.run_tool(op, args, **kw)
        self.assertEqual(r.returncode, 1, r.stderr + r.stdout)
        self.assertTrue(r.stdout.startswith("%s: error: %s" % (NAME, code)), r.stdout)
        return r

    def reg(self):
        return json.loads((self.d / "tools.json").read_text())

    # ---- tools ----
    def test_tools_add_ls_get_rm(self):
        tool = PROTO / "lib" / "base" / "math"
        r = self.ok("tools", {"op": "add", "path": str(tool)})
        self.assertIn("added math", r.stdout)
        self.assertIn("unless they changed that tool for themselves", r.stdout)
        self.assertEqual(self.reg()["tools"]["math"]["path"], str(tool))          # 絕對存絕對（aos-tools 照寫法）
        self.assertTrue(self.ok("tools", {"op": "ls"}).stdout.startswith("math\t"))
        self.assertIn("math\tdir\t", self.ok("tools", {"op": "ls", "long": True}).stdout)
        self.assertEqual(json.loads(self.ok("tools", {"op": "get", "name": "math"}).stdout.splitlines()[0])["name"], "math")
        r = self.fails("tools", {"op": "add", "path": str(tool)}, "ToolExists")
        self.assertIn('"replace": true', r.stdout)                                 # 教工具參數，不教 CLI 旗標
        self.assertIn("aos-tools: error: ToolExists", r.stderr)                      # 下層 stderr 原樣透出
        self.ok("tools", {"op": "add", "path": str(tool), "replace": True, "envs": {"K": "v"}})
        self.assertEqual(self.reg()["tools"]["math"]["env"], {"K": "v"})
        self.ok("tools", {"op": "rm", "name": "math"})
        self.assertEqual(self.reg()["tools"], {})
        self.fails("tools", {"op": "rm", "name": "math"}, "ToolMissing")

    def test_tools_relative_path_from_workspace(self):
        shutil.copytree(PROTO / "lib" / "base" / "math", self.ws / "mytools" / "calc")
        self.ok("tools", {"op": "add", "path": "mytools/calc"})
        stored = self.reg()["tools"]["calc"]["path"]
        self.assertEqual(os.path.normpath(os.path.join(self.d, stored)), str(self.ws / "mytools" / "calc"))   # 存成相對登記檔

    def test_tools_path_json_and_override_base(self):
        self.ok("tools", {"op": "add", "name": "m", "path_json": {"$env": "AOS_HOME", "$path": "/lib/base/math"}})
        self.assertEqual(self.reg()["tools"]["m"]["path"], {"$env": "AOS_HOME", "$path": "/lib/base/math"})
        # 定義的登記檔疊在別份上：rm 底下那份的工具＝寫 null、底下那份不動（aos-tools 的規則）
        base = self.ws / "base.json"
        base.write_text(json.dumps({"tools": {"calc": {"path": str(PROTO / "lib" / "base" / "math")}}}))
        (self.d / "tools.json").write_text(json.dumps({"$override": "../../base.json", "tools": {}}))
        self.ok("tools", {"op": "rm", "name": "calc"})
        self.assertEqual(self.reg()["tools"], {"calc": None})
        self.assertIn("calc", json.loads(base.read_text())["tools"])

    # ---- llm ----
    def test_llm_set_ls_rm(self):
        r = self.ok("llm", {"op": "set", "settings": {"model": "smart", "temperature": "0.2"}})
        self.assertIn("(temperature is not a setting the body reads (it reads: model); stored anyway)", r.stdout)
        self.assertIn("model=smart\ntemperature=0.2\n", r.stdout)
        self.assertEqual(json.loads((self.d / "llm.json").read_text()), {"model": "smart", "temperature": "0.2"})
        self.assertEqual(self.ok("llm", {"op": "ls"}).stdout, "model=smart\ntemperature=0.2\n")
        r = self.fails("llm", {"op": "rm", "keys": ["temperature", "nope"]}, "KeyMissing")
        self.assertIn("nothing removed", r.stdout)
        self.ok("llm", {"op": "rm", "keys": ["temperature"]})
        self.assertEqual(json.loads((self.d / "llm.json").read_text()), {"model": "smart"})

    def test_llm_odd_key_and_missing_file(self):
        (self.d / "llm.json").unlink()
        self.assertIn("(no settings: the body uses its defaults)", self.ok("llm", {"op": "ls"}).stdout)
        self.ok("llm", {"op": "set", "settings": {"a/b~c": "1"}})                 # 指標跳脫：鍵照字面
        self.assertEqual(json.loads((self.d / "llm.json").read_text()), {"a/b~c": "1"})
        self.ok("llm", {"op": "rm", "keys": ["a/b~c"]})
        self.assertEqual(json.loads((self.d / "llm.json").read_text()), {})

    def test_llm_system_key_points_to_system(self):
        r = self.fails("llm", {"op": "set", "settings": {"system": "x"}}, "ArgumentsBad")
        self.assertIn('"op": "system"', r.stdout)
        self.assertEqual(json.loads((self.d / "llm.json").read_text()), {"model": "fake"})

    # ---- system ----
    def test_system_get_set(self):
        self.assertEqual(self.ok("system", {"op": "get"}).stdout, "You are a test.\n")
        os.chmod(self.d / "system.txt", 0o640)
        r = self.ok("system", {"op": "set", "text": "New text."})
        self.assertIn("(9 bytes)", r.stdout)
        self.assertIn("unless they have their own system text", r.stdout)
        self.assertEqual((self.d / "system.txt").read_text(), "New text.")
        self.assertEqual(os.stat(self.d / "system.txt").st_mode & 0o777, 0o640)  # 權限照舊
        self.ok("system", {"op": "set", "text": ""})
        self.assertIn("is empty", self.ok("system", {"op": "get"}).stdout)
        (self.d / "system.txt").unlink()
        self.assertIn("does not exist", self.ok("system", {"op": "get"}).stdout)
        self.assertEqual(sorted(p.name for p in self.d.iterdir() if p.name.startswith(".")), [])   # 沒留暫存檔

    # ---- 錯 ----
    def test_not_declared(self):
        (self.d / "interfaces.json").write_text('{"aos-agent": {}}')
        for op, args, code in (("tools", {"op": "ls"}, "ToolsMissing"), ("llm", {"op": "ls"}, "LlmMissing"),
                               ("system", {"op": "get"}, "SystemMissing")):
            with self.subTest(op=op):
                self.fails(op, args, code)

    def test_bad_arguments(self):
        for op, args, code, word in (("tools", {"op": "reset"}, "OpUnknown", "no own copy to reset"),
                                     ("llm", {"op": "reset"}, "OpUnknown", "ls, set, rm"),
                                     ("system", {"op": "reset"}, "OpUnknown", "get, set"),
                                     ("llm", {"op": "ls", "long": True}, "ArgumentsBad", "does not take long"),
                                     ("tools", {}, "ArgumentsBad", "args needs op"),
                                     ("tools", {"op": "add"}, "ArgumentsBad", "add needs path"),
                                     ("llm", {"op": "set", "settings": {"model": 3}}, "ArgumentsBad", "object of strings"),
                                     ("system", {"op": "set"}, "ArgumentsBad", "set needs text")):
            with self.subTest(op=op, args=args):
                self.assertIn(word, self.fails(op, args, code).stdout)
        self.assertIn("needs args", self.fails("tools", None, "ArgumentsBad").stdout)
        self.fails("tools", {"op": "ls"}, "DefMissing", path="nope")

    def test_lineage_untouched_by_edits(self):
        (self.d / "_metainfo.json").write_text('{"summary": "test", "lineage": {"from": "x"}}')
        self.ok("llm", {"op": "set", "settings": {"model": "y"}})
        self.ok("system", {"op": "set", "text": "y"})
        self.assertEqual(json.loads((self.d / "_metainfo.json").read_text())["lineage"], {"from": "x"})


if __name__ == "__main__":
    unittest.main()
