"""json 工具一族（lib/aos_json.py；簡單組 json_*、複雜組 aos_json_*，thinking 2026-11/12/json-tools）的定向測試：每支實跑 _entry，驗輸出與檔案內容。"""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

LIB = Path(__file__).resolve().parents[1]
IMPLS = LIB.parent / "impls"


class JsonToolsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)
        self.env = dict(os.environ, AOS_WS=str(self.ws))
        self.env.pop("AOS_JSON_MAX_BYTES", None)
        self.env.pop("AOS_JSON_MAX_ITEMS", None)
        self.env["PATH"] = "%s:%s:%s" % (IMPLS / "aos-json/bin", IMPLS / "aos-directive/bin", self.env.get("PATH", ""))
        self.write("cfg.json", {"name": "bob", "max": 20,
                                "states": {"think": {"exec": "think.py", "next": "act"}, "act": {"exec": "act.py", "next": "idle"}},
                                "tags": ["a", "b"], "r": {"$ref": "o.json#/x"}})
        self.write("o.json", {"x": {"y": 1}})

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, doc):
        (self.ws / name).write_text(json.dumps(doc))

    def doc(self, name="cfg.json"):
        return json.loads((self.ws / name).read_text())

    def run_tool(self, tool, env=None, **args):
        layer = "aos" if tool.startswith("aos_json_") else "base"
        return subprocess.run([str(LIB / layer / tool / "_entry")], input=json.dumps(args), text=True,
                              capture_output=True, env=dict(self.env, **(env or {})))

    def ok(self, tool, env=None, **args):
        r = self.run_tool(tool, env, **args)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout.rstrip("\n")

    def err(self, tool, code, **args):
        r = self.run_tool(tool, **args)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("%s: error: %s " % (tool, code), r.stdout)
        return r.stdout

    # 簡單組：讀
    def test_get(self):
        self.assertEqual(json.loads(self.ok("json_get", path="cfg.json#/states/think")), {"exec": "think.py", "next": "act"})
        self.assertEqual(self.ok("json_get", path="cfg.json#/max"), "20")
        self.assertEqual(json.loads(self.ok("json_get", path="cfg.json#/")), self.doc())     # #/ ＝整份
        self.assertEqual(json.loads(self.ok("json_get", path="cfg.json#/r")), {"$ref": "o.json#/x"})   # 指示詞照原文
        self.err("json_get", "PointerMissing", path="cfg.json#/nope")
        self.err("json_get", "PointerBad", path="cfg.json#nope")
        self.err("json_get", "FileMissing", path="none.json")

    def test_get_too_big_and_limits(self):
        out = self.ok("json_get", path="cfg.json", max_bytes=20)
        self.assertTrue(out.startswith("[too big] object, 5 keys, "), out)
        self.assertIn("json_ls cfg.json", out)
        self.assertEqual(json.loads(self.ok("json_get", path="cfg.json", max_bytes=20, full=True)), self.doc())
        self.assertTrue(self.ok("json_get", {"AOS_JSON_MAX_BYTES": "20"}, path="cfg.json").startswith("[too big]"))
        self.assertTrue(self.ok("json_get", {"AOS_JSON_MAX_BYTES": "20"}, path="cfg.json", max_bytes=9999).startswith("{"))   # 參數蓋環境變數
        r = self.run_tool("json_get", {"AOS_JSON_MAX_BYTES": "lots"}, path="cfg.json")
        self.assertEqual(r.returncode, 0)
        self.assertIn("json_get: warning: AOS_JSON_MAX_BYTES=lots", r.stderr)

    def test_ls(self):
        self.assertEqual(self.ok("json_ls", path="cfg.json").split("\n"), ["object, 5 keys", "name", "max", "states", "tags", "r"])
        lines = self.ok("json_ls", path="cfg.json", long=True, limit=2).split("\n")
        self.assertEqual(lines, ["object, 5 keys", "name\tstring\t3 chars\t5 bytes", "max\tnumber\t20",
                                 '[more] 0 to 1 of 5 shown; next: "offset": 2'])
        self.assertEqual(self.ok("json_ls", path="cfg.json", offset=4).split("\n"), ["object, 5 keys", "r"])
        self.assertEqual(self.ok("json_ls", path="cfg.json#/tags").split("\n")[0], "array, 2 items (index 0..1)")
        self.assertEqual(self.ok("json_ls", path="cfg.json#/name"), "string, 3 chars")
        self.write("k.json", {"a/b": 1})
        self.assertEqual(self.ok("json_ls", path="k.json").split("\n")[1], "a~1b")       # 可以直接接在路徑後面

    def test_search(self):
        self.assertEqual(self.ok("json_search", path="cfg.json", key="next").split("\n"),
                         ["cfg.json#/states/think/next\tstring\t3 chars\t5 bytes", "cfg.json#/states/act/next\tstring\t4 chars\t6 bytes"])
        self.assertEqual(self.ok("json_search", path="cfg.json#/states/act/exec", key="max", up=True), "cfg.json#/max\tnumber\t20")
        self.assertEqual(self.ok("json_search", path="cfg.json", value="b"), "cfg.json#/tags/1\tstring\t1 chars\t3 bytes")
        self.assertEqual(self.ok("json_search", path="cfg.json", value="20"), "[no match]")      # 型別要一樣
        self.assertEqual(self.ok("json_search", path="cfg.json", value=".py", contains=True).count("\n"), 1)
        self.assertEqual(self.ok("json_search", path="cfg.json", key="next", value="act"), "cfg.json#/states/think/next\tstring\t3 chars\t5 bytes")
        self.assertIn("[more]", self.ok("json_search", path="cfg.json", key="next", limit=1))
        self.err("json_search", "ArgumentsBad", path="cfg.json")

    # 簡單組：寫
    def test_set(self):
        self.assertEqual(self.ok("json_set", path="cfg.json#/states/act/next", value="think"), "ok cfg.json#/states/act/next")
        self.assertEqual(self.ok("json_set", path="cfg.json#/tags/-", value="c"), "ok cfg.json#/tags/2")
        self.assertIn('"parents": true', self.err("json_set", "PointerMissing", path="cfg.json#/a/b", value=1))
        self.ok("json_set", path="cfg.json#/a/b", value='{"x":1}', parents=True)
        self.ok("json_set", path="cfg.json#/n", value=None)
        self.ok("json_set", path="cfg.json#/r/z", value=2)                                # 指示詞物件當普通物件（--raw）
        d = self.doc()
        self.assertEqual((d["states"]["act"]["next"], d["tags"], d["a"], d["n"], d["r"]),
                         ("think", ["a", "b", "c"], {"b": '{"x":1}'}, None, {"$ref": "o.json#/x", "z": 2}))   # 值照字面
        self.err("json_set", "ArgumentsBad", path="cfg.json#/x")
        self.assertIn("create it first", self.err("json_set", "FileMissing", path="new.json#/a", value=1))
        self.assertEqual(self.ok("json_set", path="new.json", value={"k": 1}), "ok new.json")
        self.assertEqual(self.doc("new.json"), {"k": 1})

    def test_add(self):
        self.assertEqual(self.ok("json_add", path="cfg.json#/tags/1", value="ins"), "ok cfg.json#/tags/1")
        self.assertEqual(self.ok("json_add", path="cfg.json#/tags/0", value="first"), "ok cfg.json#/tags/0")
        self.assertEqual(self.ok("json_add", path="cfg.json#/tags/4", value="end"), "ok cfg.json#/tags/4")
        self.assertEqual(self.ok("json_add", path="cfg.json#/tags/-", value="last"), "ok cfg.json#/tags/5")
        self.assertEqual(self.doc()["tags"], ["first", "a", "ins", "b", "end", "last"])
        self.assertIn("cfg.json#/tags/-", self.err("json_add", "KeyExists", path="cfg.json#/tags", value="x"))
        self.err("json_add", "KeyExists", path="cfg.json#/max", value=1)
        self.err("json_add", "PointerMissing", path="cfg.json#/tags/99", value=1)
        self.ok("json_add", path="cfg.json#/new", value=None)
        self.ok("json_add", path="cfg.json#/p/q", value=1, parents=True)
        self.assertEqual((self.doc()["new"], self.doc()["p"]), (None, {"q": 1}))
        self.err("json_add", "KeyExists", path="cfg.json", value={})

    def test_del(self):
        self.assertEqual(self.ok("json_del", path="cfg.json#/tags/0"), "ok cfg.json#/tags/0")
        self.ok("json_del", path="cfg.json#/name")
        self.assertEqual((self.doc()["tags"], "name" in self.doc()), (["b"], False))
        self.err("json_del", "PointerMissing", path="cfg.json#/name")
        self.err("json_del", "TargetBad", path="cfg.json#/")

    # 複雜組
    def test_aos_get(self):
        self.assertEqual(json.loads(self.ok("aos_json_get", path="cfg.json#/r/y", follow=True)), 1)
        self.assertEqual(json.loads(self.ok("aos_json_get", path="cfg.json#/r", resolve=True)), {"y": 1})
        self.assertEqual(json.loads(self.ok("aos_json_get", path="cfg.json#/r")), {"$ref": "o.json#/x"})

    def test_aos_set_add(self):
        self.err("aos_json_set", "FollowMissing", path="cfg.json#/r/y", value=5)
        self.ok("aos_json_set", path="cfg.json#/r/y", value=5, follow=True)
        self.assertEqual(self.doc("o.json"), {"x": {"y": 5}})
        self.ok("aos_json_set", path="cfg.json#/t", text='{"aaa": true}')
        self.err("aos_json_set", "TextBad", path="cfg.json#/t", text="nope")
        self.ok("aos_json_set", path="cfg.json#/f", **{"from": "o.json#/x"})
        self.ok("aos_json_set", path="cfg.json#/kept", value={"$ref": "o.json#/x"})
        self.ok("aos_json_set", path="cfg.json#/solved", value={"$ref": "o.json#/x"}, resolve=True)
        self.err("aos_json_set", "ArgumentsBad", path="cfg.json#/t", value=1, text="1")
        d = self.doc()
        self.assertEqual((d["t"], d["f"], d["kept"], d["solved"]), ({"aaa": True}, {"y": 5}, {"$ref": "o.json#/x"}, {"y": 5}))
        self.ok("aos_json_add", path="cfg.json#/tags/0", text='"z"')
        self.assertEqual(self.doc()["tags"], ["z", "a", "b"])
        self.err("aos_json_add", "KeyExists", path="cfg.json#/t", value=1)

    def test_aos_set_check(self):
        self.write("fsm.json", {"start": "a", "states": {"a": {"exec": ["true"], "next": "a"}}})
        self.err("aos_json_set", "CheckFailed", path="fsm.json#/states/a/exec", value=[], check=True)
        self.ok("aos_json_set", path="fsm.json#/states/a/exec", value=["false"], check=True)


if __name__ == "__main__":
    unittest.main()
