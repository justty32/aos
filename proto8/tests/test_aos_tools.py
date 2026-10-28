"""test_aos_tools - proto8/bin/aos-tools：一個 agent 資料夾一份工具註冊檔（tools.json），add／rm／ls／get／call。

三種登記對象（資料夾＋_tooldef、JSON＋_tooldef、可執行檔＋--tooldef／--tool-call）、不合就報錯、撞名與 --override、
存絕對路徑（相對從 cwd 算）、手寫相對路徑從 tools.json 的資料夾算、--tooldef 快取、指示詞拆檔（$ref 陣列）。
設計：proto8/thinking/2026-10-28-aos-tools.md。"""
import json, os, subprocess, tempfile, unittest
from pathlib import Path

from aos_bins import ROOT, path_with  # noqa: E402

TOOLS = str(ROOT / "bin" / "aos-tools")
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_CF", "AOS_CD", "AOS_CO")
ADD_PY = """#!/usr/bin/env python3
import json, sys
if sys.argv[1:] == ["--tooldef"]:
    open(sys.argv[0] + ".count", "a").write("x")      # 數 --tooldef 被跑了幾次（看快取）
    print(json.dumps({"description": "加法", "parameters": {"type": "object", "properties": {"x": {}, "y": {}}}}))
    sys.exit()
assert sys.argv[1] == "--tool-call", sys.argv
a = json.load(open(sys.argv[2]))
print(a["x"] + a["y"])
sys.exit(a.get("code", 0))
"""


class AosTools(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.t = Path(self.tmp.name)
        self.agent = t / "agent"
        self.agent.mkdir()
        lib = self.lib = t / "lib"
        (lib / "clock").mkdir(parents=True)
        (lib / "clock" / "_entry").write_text("#!/bin/sh\necho tick\n")
        (lib / "clock" / "_entry").chmod(0o755)
        (lib / "clock" / "_tooldef").write_text('{"description": "時間", "parameters": {"type": "object", "properties": {}}}')
        (lib / "clock" / "_metainfo").write_text('{"side_effect": false}')
        (lib / "echo.json").write_text('{"_entry": {"argv": ["cat"]}, "_tooldef": {"description": "回聲"}, "_metainfo": {"idempotent": true}}')
        (lib / "add.py").write_text(ADD_PY)
        (lib / "add.py").chmod(0o755)
        self.env = {k: v for k, v in os.environ.items() if k not in CLEAR}
        self.env["PATH"] = path_with(self.env.get("PATH", ""))

    def tearDown(self):
        self.tmp.cleanup()

    def run_tools(self, *args, stdin="", cwd=None, env=None):
        return subprocess.run([TOOLS] + list(args), input=stdin, capture_output=True, text=True,
                              cwd=cwd or self.agent, env=env or self.env, timeout=60)

    def ok(self, *args, **kw):
        r = self.run_tools(*args, **kw)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def bad(self, code, *args, **kw):
        r = self.run_tools(*args, **kw)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertTrue(r.stderr.splitlines()[-1].startswith("aos-tools: " + code), r.stderr)   # aos-json 的那行可能在前面
        return r.stderr

    def reg(self):
        return json.loads((self.agent / "tools.json").read_text())["tools"]

    def add3(self):
        for p in ("../lib/clock", "../lib/echo.json", "../lib/add.py"):
            self.ok("add", p)

    def test_add_three_kinds_absolute(self):
        self.add3()
        r = self.reg()
        self.assertEqual(sorted(r), ["add", "clock", "echo"])
        self.assertEqual(r["clock"]["path"], str(self.lib / "clock"))           # 相對從 cwd 算、存絕對
        self.assertEqual(r["echo"]["path"], str(self.lib / "echo.json"))
        self.assertEqual(r["add"]["cache"]["tooldef"]["description"], "加法")
        rows = [l.split("\t") for l in self.ok("ls").splitlines()]
        self.assertEqual(rows, [["add", "exe", str(self.lib / "add.py")], ["clock", "dir", str(self.lib / "clock")],
                                ["echo", "json", str(self.lib / "echo.json")]])
        got = json.loads(self.ok("get", "clock"))
        self.assertEqual((got["kind"], got["tooldef"]["description"], got["metainfo"]), ("dir", "時間", {"side_effect": False}))
        self.assertEqual(json.loads(self.ok("get", "echo"))["metainfo"], {"idempotent": True})
        self.assertNotIn("metainfo", json.loads(self.ok("get", "add")))
        self.assertEqual(json.loads(self.ok("get", "../lib/echo.json"))["name"], "echo")   # get 也收路徑

    def test_not_qualified_is_error(self):
        (self.lib / "plain.txt").write_text("hello")
        (self.lib / "nodef.json").write_text('{"_entry": {"argv": ["true"]}}')
        (self.lib / "empty").mkdir()
        (self.lib / "badexe").write_text("#!/bin/sh\nexit 3\n")
        (self.lib / "badexe").chmod(0o755)
        (self.lib / "baddef").mkdir()
        (self.lib / "baddef" / "_tooldef.json").write_text('{"parameters": "x"}')
        self.bad("ToolDefBad", "add", "../lib/plain.txt")
        self.bad("ToolDefMissing", "add", "../lib/nodef.json")
        self.bad("ToolDefMissing", "add", "../lib/empty")
        self.bad("ToolDefBad", "add", "../lib/badexe")
        self.bad("ToolDefBad", "add", "../lib/baddef")
        self.bad("PathMissing", "add", "../lib/nope")
        self.assertFalse((self.agent / "tools.json").exists())               # 錯了什麼都不寫

    def test_name_clash_and_override(self):
        self.ok("add", "../lib/clock")
        (self.t / "other").mkdir()
        (self.t / "other" / "clock").mkdir()
        (self.t / "other" / "clock" / "_tooldef.json").write_text("{}")      # 只有 _tooldef.json 也行
        self.bad("ToolExists", "add", "../other/clock")
        self.ok("add", "--override", "../other/clock")
        self.assertEqual(self.reg()["clock"]["path"], str(self.t / "other" / "clock"))
        self.ok("add", "--name", "clock2", "../lib/clock")
        self.bad("NameBad", "add", "--name", "a b", "../lib/clock")

    def test_rm_by_name_or_path(self):
        self.add3()
        self.assertEqual(json.loads(self.ok("rm", "echo")), {"removed": ["echo"]})
        self.assertEqual(json.loads(self.ok("rm", "../lib/add.py")), {"removed": ["add"]})
        self.assertEqual(sorted(self.reg()), ["clock"])
        self.bad("ToolMissing", "rm", "echo")

    def test_call_three_kinds(self):
        self.add3()
        self.assertEqual(self.ok("call", "clock"), "tick\n")
        self.assertEqual(json.loads(self.ok("call", "echo", stdin='{"a": 1}')), {"a": 1})   # stdin 原樣進
        stack = self.t / "st"
        env = dict(self.env, AOS_STACK=str(stack) + "/")
        self.assertEqual(self.ok("call", "add", stdin='{"x": 2, "y": 3}', env=env), "5\n")
        self.assertEqual(json.loads((stack / "tool_call.json").read_text()), {"x": 2, "y": 3})
        r = self.run_tools("call", "add", stdin='{"x": 1, "y": 1, "code": 7}')   # 沒 AOS_STACK：暫存檔
        self.assertEqual((r.returncode, r.stdout), (7, "2\n"))                     # 結束碼是工具的
        self.bad("ToolMissing", "call", "nope")

    def test_tooldef_cache(self):
        self.ok("add", "../lib/add.py")
        count = self.lib / "add.py.count"
        self.assertEqual(count.read_text(), "x")
        self.ok("ls", "--json")
        self.ok("get", "add")
        self.assertEqual(count.read_text(), "x")                             # 沒變：用快取
        before = (self.agent / "tools.json").read_text()
        (self.lib / "add.py").write_text(ADD_PY + "\n")                       # 變了：重跑、不寫回（P-15）
        self.ok("ls")
        self.assertEqual(count.read_text(), "xx")
        self.assertEqual((self.agent / "tools.json").read_text(), before)

    def test_ls_json_and_broken_entry(self):
        self.assertEqual(json.loads(self.ok("ls", "--json")), [])           # 沒有 tools.json＝沒有工具
        self.add3()
        names = [t["name"] for t in json.loads(self.ok("ls", "--json"))]
        self.assertEqual(names, ["add", "clock", "echo"])
        (self.lib / "echo.json").unlink()
        err = self.bad("PathMissing", "ls")
        self.assertIn("工具 echo", err)
        (self.agent / "tools.json").write_text('{"tools": []}')
        self.bad("RegistryBad", "ls")

    def test_hand_written_relative_and_directive_split(self):
        """手寫的相對路徑從 tools.json 的資料夾算；$ref 陣列拆成兩份，add 寫進最後一份、rm 從它所在那份拿掉。"""
        (self.agent / "tools.json").write_text('{"tools": {"$ref": ["base.json", "mine.json"]}}')
        (self.agent / "base.json").write_text('{"clock": {"path": "../lib/clock"}}')
        (self.agent / "mine.json").write_text("{}")
        other = self.t / "elsewhere"
        other.mkdir()
        self.assertEqual(self.ok("--file", str(self.agent / "tools.json"), "ls", cwd=other).split("\t")[2].strip(),
                         str(self.lib / "clock"))
        self.ok("add", "../lib/echo.json")
        self.assertIn("echo", json.loads((self.agent / "mine.json").read_text()))
        self.ok("rm", "clock")
        self.assertEqual(json.loads((self.agent / "base.json").read_text()), {})
        self.assertEqual([l.split("\t")[0] for l in self.ok("ls").splitlines()], ["echo"])
        (self.agent / "tools.json").write_text('{"tools": {"$ref": "nope.json"}}')
        self.bad("DirectiveBad", "ls")

    def test_usage_errors(self):
        self.bad("ArgumentsBad")
        self.bad("CommandUnknown", "list")
        self.bad("FlagUnknown", "--nope", "ls")
        self.bad("ArgumentsBad", "add")
        self.bad("FlagUnknown", "ls", "--nope")


if __name__ == "__main__":
    unittest.main()
