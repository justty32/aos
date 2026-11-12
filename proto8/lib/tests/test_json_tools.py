"""json 工具一族（lib/aos_json.py；簡單組 json_*、複雜組 jsonx_*，thinking 2026-11/12/json-tools）的定向測試：每支實跑 _entry，驗輸出與檔案內容。"""

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
        layer = "aos" if tool.startswith("jsonx_") else "base"
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
        self.assertEqual(json.loads(self.ok("json_get", path="cfg.json")), self.doc())       # 只寫檔＝整份
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
        self.assertEqual(self.ok("json_search", path="cfg.json", value="b"), "cfg.json#/tags/1\tstring\t1 char\t3 bytes")
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
        out = self.err("json_set", "WriteFailed", path="nodir/_index.json", value={})   # 資料夾不在：照腦給的字面說是哪個夾（J2）
        self.assertIn("folder nodir does not exist, create it first", out)
        self.assertEqual(self.ok("json_set", path="cfg.json#/sub~1b.json", value=1), "ok cfg.json#/sub~1b.json")
        self.assertEqual(self.doc()["sub/b.json"], 1)                                     # 鍵裡的 / 寫 ~1（J3）

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
        self.err("json_del", "TargetBad", path="cfg.json")

    def test_root_is_standard(self):
        """照 RFC 6901（同 aos-json／$ref，使用者 11-12「按照標準寫法」）：x.json 是整份，x.json#/ 是空字串 key；x.json# 不收（照 aos-json 報 SpecBad，11-12 代定）。"""
        self.write("e.json", {"": {"in": 1}, "a": 2})
        whole = {"": {"in": 1}, "a": 2}
        self.assertEqual(json.loads(self.ok("json_get", path="e.json")), whole)
        for tool in ("json_get", "json_ls", "json_search", "json_set", "json_add", "json_del", "jsonx_get", "jsonx_set", "jsonx_add"):
            extra = {"key": "a"} if tool == "json_search" else {"value": 1} if tool[-3:] in ("set", "add") else {}
            out = self.err(tool, "SpecBad", path="e.json#", **extra)
            self.assertIn("e.json#: # must be followed by /; use FILE alone for the whole document: e.json", out)
        self.assertEqual(self.doc("e.json"), whole)
        self.assertEqual(json.loads(self.ok("json_get", path="e.json#/")), {"in": 1})
        self.assertEqual(json.loads(self.ok("json_get", path="e.json#//in")), 1)
        self.assertEqual(self.ok("json_ls", path="e.json#/").split("\n"), ["object, 1 key", "in"])
        self.assertEqual(self.ok("json_search", path="e.json#/", key="in"), "e.json#//in\tnumber\t1")
        self.assertEqual(self.ok("json_set", path="e.json#/", value=5), "ok e.json#/")
        self.assertEqual(self.doc("e.json"), {"": 5, "a": 2})
        self.assertEqual(self.ok("json_del", path="e.json#/"), "ok e.json#/")
        self.assertEqual(self.doc("e.json"), {"a": 2})
        self.err("json_get", "PointerMissing", path="e.json#/")
        self.assertEqual(self.ok("json_add", path="e.json#/", value=[]), "ok e.json#/")
        self.assertEqual(self.doc("e.json"), {"a": 2, "": []})
        self.assertEqual(self.ok("json_set", path="e.json", value={"b": 3}), "ok e.json")
        self.assertEqual(self.doc("e.json"), {"b": 3})
        self.assertEqual(json.loads(self.ok("jsonx_get", path="e.json")), {"b": 3})

    # 複雜組
    def test_aos_get(self):
        self.assertEqual(json.loads(self.ok("jsonx_get", path="cfg.json#/r/y", follow=True)), 1)
        self.assertEqual(json.loads(self.ok("jsonx_get", path="cfg.json#/r", resolve=True)), {"y": 1})
        self.assertEqual(json.loads(self.ok("jsonx_get", path="cfg.json#/r")), {"$ref": "o.json#/x"})

    def test_aos_set_add(self):
        self.err("jsonx_set", "FollowMissing", path="cfg.json#/r/y", value=5)
        self.ok("jsonx_set", path="cfg.json#/r/y", value=5, follow=True)
        self.assertEqual(self.doc("o.json"), {"x": {"y": 5}})
        self.ok("jsonx_set", path="cfg.json#/t", text='{"aaa": true}')
        self.err("jsonx_set", "TextBad", path="cfg.json#/t", text="nope")
        self.ok("jsonx_set", path="cfg.json#/f", **{"from": "o.json#/x"})
        self.ok("jsonx_set", path="cfg.json#/kept", value={"$ref": "o.json#/x"})
        self.ok("jsonx_set", path="cfg.json#/solved", value={"$ref": "o.json#/x"}, resolve=True)
        self.err("jsonx_set", "ArgumentsBad", path="cfg.json#/t", value=1, text="1")
        d = self.doc()
        self.assertEqual((d["t"], d["f"], d["kept"], d["solved"]), ({"aaa": True}, {"y": 5}, {"$ref": "o.json#/x"}, {"y": 5}))
        self.ok("jsonx_add", path="cfg.json#/tags/0", text='"z"')
        self.assertEqual(self.doc()["tags"], ["z", "a", "b"])
        self.err("jsonx_add", "KeyExists", path="cfg.json#/t", value=1)

    def test_aos_set_check(self):
        self.write("fsm.json", {"start": "a", "states": {"a": {"exec": ["true"], "next": "a"}}})
        self.err("jsonx_set", "CheckFailed", path="fsm.json#/states/a/exec", value=[], check=True)
        self.ok("jsonx_set", path="fsm.json#/states/a/exec", value=["false"], check=True)

    def test_aos_ls_search_del(self):
        self.write("o.json", {"x": {"y": 1, "k": {"next": 2}}})
        self.err("jsonx_ls", "PointerMissing", path="cfg.json#/r/k")             # 不給 follow＝照原文，$ref 物件裡沒有 k
        self.assertEqual(self.ok("jsonx_ls", path="cfg.json#/r/k", follow=True).split("\n"), ["object, 1 key", "next"])
        self.assertEqual(self.ok("jsonx_ls", path="cfg.json#/r", resolve=True).split("\n"), ["object, 2 keys", "y", "k"])
        self.assertEqual(self.ok("json_search", path="cfg.json", key="next").count("\n"), 1)       # 簡單組看不到 o.json 裡的
        hits = self.ok("jsonx_search", path="cfg.json", key="next", resolve=True).split("\n")
        self.assertIn("cfg.json#/r/k/next\tnumber\t2", hits)
        self.assertEqual(self.ok("jsonx_search", path="cfg.json#/r/k", key="next", follow=True), "cfg.json#/r/k/next\tnumber\t2")
        self.err("jsonx_search", "ArgumentsBad", path="cfg.json#/r/k", key="next", follow=True, up=True)
        self.err("jsonx_del", "FollowMissing", path="cfg.json#/r/y")
        self.assertEqual(self.ok("jsonx_del", path="cfg.json#/r/y", follow=True), "ok cfg.json#/r/y")
        self.assertEqual(self.doc("o.json"), {"x": {"k": {"next": 2}}})
        self.assertEqual(self.ok("json_del", path="cfg.json#/r/$ref"), "ok cfg.json#/r/$ref")       # 簡單組＝普通物件
        self.assertEqual(self.doc()["r"], {})

    # 一次多格
    def test_multi_get(self):
        self.assertEqual(self.ok("json_multi_get", paths=["cfg.json#/name", "o.json#/x/y"]), 'cfg.json#/name\t"bob"\no.json#/x/y\t1')
        r = self.run_tool("json_multi_get", paths=["cfg.json#/max", "cfg.json#/nope", "cfg.json#"], max_bytes=5)
        lines = r.stdout.rstrip("\n").split("\n")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(lines[0], "cfg.json#/max\t20")
        self.assertTrue(lines[1].startswith("cfg.json#/nope\t[error] PointerMissing "), lines[1])
        self.assertTrue(lines[2].startswith("cfg.json#\t[error] SpecBad "), lines[2])
        self.assertTrue(lines[3].startswith("json_multi_get: error: PlacesFailed 2 of 3 places failed"), lines[3])
        self.assertTrue(self.ok("json_multi_get", paths=["cfg.json"], max_bytes=5).startswith("cfg.json\t[too big] object"))
        self.err("json_multi_get", "ArgumentsBad", paths=[])
        self.err("json_multi_get", "ArgumentsBad", paths=["cfg.json"], max_bytes=0)

    def test_multi_set(self):
        out = self.ok("json_multi_set", items=[{"path": "cfg.json#/max", "value": 30}, {"path": "cfg.json#/tags/-", "value": None},
                                               {"path": "new.json", "value": {"a": "1"}}])
        self.assertEqual(out, "cfg.json#/max\tok cfg.json#/max\ncfg.json#/tags/-\tok cfg.json#/tags/2\nnew.json\tok new.json")
        self.assertEqual((self.doc()["max"], self.doc()["tags"], self.doc("new.json")), (30, ["a", "b", None], {"a": "1"}))
        r = self.run_tool("json_multi_set", items=[{"path": "cfg.json#/q/z", "value": 1}, {"path": "cfg.json#/name", "value": "amy"},
                                                    {"path": "cfg.json#/x"}, {"path": "cfg.json#/y", "value": 1, "parents": True}])
        lines = r.stdout.rstrip("\n").split("\n")
        self.assertEqual(r.returncode, 1)
        self.assertTrue(lines[0].startswith("cfg.json#/q/z\t[error] PointerMissing "), lines[0])
        self.assertEqual(lines[1], "cfg.json#/name\tok cfg.json#/name")              # 前一格錯不擋後一格、不回滾
        self.assertEqual(lines[2], "cfg.json#/x\t[error] ArgumentsBad missing value (any JSON)")
        self.assertTrue(lines[3].startswith("cfg.json#/y\t[error] ArgumentsBad unknown key in item: parents"), lines[3])
        self.assertTrue(lines[4].startswith("json_multi_set: error: PlacesFailed 3 of 4 places failed"), lines[4])
        self.assertEqual(self.doc()["name"], "amy")
        self.ok("json_multi_set", items=[{"path": "cfg.json#/q/z", "value": 1}], parents=True)
        self.assertEqual(self.doc()["q"], {"z": 1})


if __name__ == "__main__":
    unittest.main()
