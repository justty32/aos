"""index_view（lib/aos_index.py，thinking 2026-11/12/index-tools）的定向測試：實跑 _entry，驗三種給法（只 path、只 index、兩個疊著）、key、分頁、沒有 index、壞掉的 index。"""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

LIB = Path(__file__).resolve().parents[1]
IMPLS = LIB.parent / "impls"
TOOL = LIB / "base" / "index_view" / "_entry"


class IndexViewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)
        self.env = dict(os.environ, AOS_WS=str(self.ws))
        self.env.pop("AOS_JSON_MAX_ITEMS", None)
        self.env["PATH"] = "%s:%s" % (IMPLS / "aos-json/bin", self.env.get("PATH", ""))
        (self.ws / "kb").mkdir()
        (self.ws / "empty").mkdir()
        self.write("kb/_index.json", {"cli": {"description": "Command-line programs"},
                                      "tools": {"description": "Tools the brain can call"},
                                      "data.json#/items/0": {"description": "First job;\nthe scheduler\treads only this"},
                                      "notes.json": {}, "odd": "not an object"})
        self.write("cfg.json", {"_index": {"states": {"description": "One entry per fsm state"}},
                                "states": {"think": {}, "_index": {"think": {"description": "Asks the brain"}}},
                                "tags": ["a", "b"], "name": "bob", "bad": {"_index": [1]}})
        self.write("me.json", {"views": {"tools": {"description": "The only part I use"},
                                         "mine": {"description": "Only in my view"}},
                               "list": [1, 2]})
        self.write("list.json", [1, 2])

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, doc):
        (self.ws / name).write_text(json.dumps(doc))

    def run_tool(self, env=None, **args):
        return subprocess.run([str(TOOL)], input=json.dumps(args), text=True, capture_output=True,
                              env=dict(self.env, **(env or {})))

    def ok(self, env=None, **args):
        r = self.run_tool(env, **args)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stderr, "")
        return r.stdout.rstrip("\n").split("\n")

    def err(self, code, **args):
        r = self.run_tool(**args)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("index_view: error: %s " % code, r.stdout)
        return r.stdout

    def test_folder(self):
        self.assertEqual(self.ok(path="kb"), [
            "[index] kb/_index.json, 5 entries",
            "cli\tCommand-line programs", "tools\tTools the brain can call",
            "data.json#/items/0\tFirst job; the scheduler reads only this",     # 換行、TAB 印成空白；鍵照字面
            "notes.json", "odd"])                                                # 沒有 description、項目壞掉：只印鍵
        self.assertEqual(self.ok(path="kb/")[0], "[index] kb/_index.json, 5 entries")

    def test_json_nodes(self):
        self.assertEqual(self.ok(path="cfg.json"), ["[index] cfg.json#/_index, 1 entry", "states\tOne entry per fsm state"])
        self.assertEqual(self.ok(path="cfg.json#/states"), ["[index] cfg.json#/states/_index, 1 entry", "think\tAsks the brain"])

    def test_key(self):
        self.assertEqual(self.ok(path="kb", key="tools"), ["[index] kb/_index.json, 5 entries", "tools\tTools the brain can call"])
        self.assertEqual(self.ok(path="kb", key="data.json#/items/0")[1], "data.json#/items/0\tFirst job; the scheduler reads only this")
        self.assertEqual(self.ok(path="kb", key="nope"), ["[index] kb/_index.json, 5 entries", "[no entry] nope"])
        self.assertEqual(self.ok(path="kb", key="tool")[1], "[no entry] tool")                 # 整個相等，不是子字串

    def test_index_only(self):
        self.assertEqual(self.ok(index="me.json#/views"), ["[index] me.json#/views, 2 entries",
                                                          "tools\tThe only part I use", "mine\tOnly in my view"])

    def test_both(self):
        self.assertEqual(self.ok(path="kb", index="me.json#/views"), [
            "[index] kb/_index.json + me.json#/views (on the same key me.json#/views wins), 6 entries",
            "cli\tCommand-line programs", "tools\tThe only part I use",                  # 同名：整項以指定那份為準
            "data.json#/items/0\tFirst job; the scheduler reads only this", "notes.json", "odd",
            "mine\tOnly in my view"])                                                     # 只在指定那份的接在後面
        self.assertEqual(self.ok(path="kb", index="me.json#/views", key="cli")[1], "cli\tCommand-line programs")
        out = self.ok(path="empty", index="me.json#/views")                              # 天然那份不在＝只看指定那份
        self.assertEqual(out[0], "[index] me.json#/views, 2 entries (natural index: empty/_index.json does not exist)")
        self.assertEqual(len(out), 3)
        self.err("FileMissing", path="kb", index="nope.json")                            # 明講的那份不在＝錯
        self.err("PointerMissing", path="kb", index="me.json#/nope")
        self.err("IndexBad", path="kb", index="me.json#/list")

    def test_no_index(self):
        out = self.ok(path="empty")
        self.assertEqual(out, ['[no index] empty/_index.json does not exist. What the index of . says about it: {"path": ".", "key": "empty"}. '
                               "An index is a view, not a listing: use ls or json_ls to see what is really there."])
        self.assertTrue(self.ok(path="me.json")[0].startswith("[no index] me.json#/_index does not exist."))
        self.write("kb/app.json", {"retries": 3})
        self.assertIn('{"path": "kb", "key": "app.json"}', self.ok(path="kb/app.json")[0])     # 只是提示上一層，不自己往上找
        self.assertIn('{"path": "cfg.json#/states", "key": "think"}', self.ok(path="cfg.json#/states/think")[0])
        out = self.ok(path="cfg.json#/tags")[0]
        self.assertTrue(out.startswith("[no index] cfg.json#/tags is array, it cannot hold _index."), out)
        self.assertIn("keys like tags/0", out)
        self.assertIn("try index_view cfg.json.", out)
        self.assertIn("is string", self.ok(path="cfg.json#/name")[0])
        out = self.ok(path="list.json")[0]
        self.assertIn("keys like list.json#/0", out)
        self.assertIn("try index_view .", out)

    def test_paging(self):
        lines = self.ok(path="kb", limit=2)
        self.assertEqual(lines, ["[index] kb/_index.json, 5 entries", "cli\tCommand-line programs",
                                 "tools\tTools the brain can call", '[more] 0 to 1 of 5 shown; next: "offset": 2'])
        self.assertEqual(self.ok(path="kb", offset=4), ["[index] kb/_index.json, 5 entries", "odd"])
        self.assertEqual(len(self.ok({"AOS_JSON_MAX_ITEMS": "1"}, path="kb")), 3)

    def test_errors(self):
        self.err("ArgumentsBad")
        self.err("ArgumentsBad", path="")
        self.err("ArgumentsBad", path="kb", offset=-1)
        self.err("ArgumentsBad", path="kb", limit=0)
        self.err("ArgumentsBad", path="kb", key=3)
        self.err("PointerBad", path="cfg.json#states")
        self.err("FileMissing", path="nowhere")                                           # 節點本身不在：照轉
        self.assertNotIn("create it first", self.err("FileMissing", path="nowhere.json#/a"))
        self.err("PointerMissing", path="cfg.json#/nope")
        self.err("IndexBad", path="cfg.json#/bad")
        self.write("kb2.json", {})
        (self.ws / "k3").mkdir()
        self.write("k3/_index.json", [1])
        self.err("IndexBad", path="k3")
        (self.ws / "k4").mkdir()
        (self.ws / "k4" / "_index.json").write_text("not json")
        self.err("FileBad", path="k4")

    # 11-12 metainfo（使用者「index_view也要認_metainfo。」，N-69、M15、M21）：_metainfo 裡的 index 為底、疊上獨立的 _index
    def test_metainfo_folder(self):
        (self.ws / "mi").mkdir()
        self.write("mi/_metainfo.json", {"summary": "s", "index": {"a": {"description": "A inside"}, "b": {"description": "B inside"}}})
        self.assertEqual(self.ok(path="mi"), ["[index] mi/_metainfo.json#/index, 2 entries", "a\tA inside", "b\tB inside"])
        self.write("mi/_index.json", {"b": {"description": "B outside"}, "c": {"description": "C outside"}})
        self.assertEqual(self.ok(path="mi"), [
            "[index] mi/_metainfo.json#/index + mi/_index.json (on the same key mi/_index.json wins), 3 entries",
            "a\tA inside", "b\tB outside", "c\tC outside"])                                   # 同名外面贏、順序裡面在前
        self.assertEqual(self.ok(path="mi", index="me.json#/views"), [
            "[index] mi/_metainfo.json#/index + mi/_index.json + me.json#/views (on the same key the later one wins), 5 entries",
            "a\tA inside", "b\tB outside", "c\tC outside", "tools\tThe only part I use", "mine\tOnly in my view"])
        self.write("empty/_metainfo.json", {"summary": "no index here"})                    # 有 _metainfo.json 但沒有 index＝照舊沒有
        self.assertTrue(self.ok(path="empty")[0].startswith("[no index] empty/_index.json does not exist."))
        self.write("mi/_metainfo.json", {"index": [1]})
        self.assertIn("mi/_metainfo.json#/index is array", self.err("IndexBad", path="mi"))

    def test_metainfo_json_nodes(self):
        self.write("mj.json", {"_metainfo": {"index": {"x": {"description": "X inside"}, "states": {"description": "S inside"}}},
                               "_index": {"states": {"description": "S outside"}},
                               "sub": {"_metainfo": {"index": {"y": {"description": "Y"}}}},
                               "odd": {"_metainfo": "not an object", "_index": {"z": {}}},
                               "bad": {"_metainfo": {"index": "nope"}}})
        self.assertEqual(self.ok(path="mj.json"), [
            "[index] mj.json#/_metainfo/index + mj.json#/_index (on the same key mj.json#/_index wins), 2 entries",
            "x\tX inside", "states\tS outside"])
        self.assertEqual(self.ok(path="mj.json#/sub"), ["[index] mj.json#/sub/_metainfo/index, 1 entry", "y\tY"])
        self.assertEqual(self.ok(path="mj.json#/odd"), ["[index] mj.json#/odd/_index, 1 entry", "z"])      # _metainfo 不是物件＝裡面沒有
        self.assertIn("mj.json#/bad/_metainfo/index is string", self.err("IndexBad", path="mj.json#/bad"))


if __name__ == "__main__":
    unittest.main()
