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
        # 使用者 11-12「_metainfo.json 壞掉時，index_view 對那個資料夾不該直接報錯。」：只略過裡面、照用外面，標頭說一句
        self.write("mi/_metainfo.json", {"index": [1]})
        self.assertEqual(self.ok(path="mi")[0], "[index] mi/_index.json, 2 entries (_metainfo.json index is not an object, skipped)")
        (self.ws / "mi" / "_metainfo.json").write_text("not json")
        self.assertEqual(self.ok(path="mi")[0], "[index] mi/_index.json, 2 entries (_metainfo.json could not be read, skipped)")
        self.write("mi/_metainfo.json", [1])
        self.assertEqual(self.ok(path="mi")[0], "[index] mi/_index.json, 2 entries (_metainfo.json is not an object, skipped)")
        (self.ws / "empty" / "_metainfo.json").write_text("not json")                         # 全都沒有＝照舊 [no index]、退 0
        self.assertTrue(self.ok(path="empty")[0].startswith("[no index] empty/_index.json does not exist."))
        self.write("mi/_index.json", [1])                                                    # 獨立那份壞了照舊報錯
        self.err("IndexBad", path="mi")

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
        self.assertEqual(self.ok(path="mj.json#/odd"), ["[index] mj.json#/odd/_index, 1 entry (_metainfo is not an object, skipped)", "z"])
        self.assertTrue(self.ok(path="mj.json#/bad")[0].startswith("[no index] mj.json#/bad/_index does not exist."))   # 壞的裡面略過、外面沒有
        self.assertEqual(self.ok(path="mj.json#/bad", index="me.json#/views")[0],
                         "[index] me.json#/views, 2 entries (natural index: mj.json#/bad/_index does not exist) (_metainfo index is not an object, skipped)")

    # 11-12 晚 index-link（使用者「還可以放index，值必須是字串，必須是路徑，指向另一個_index或_index.json。」
    # 「json object內的_index這個key……我希望能支援字串」「不跟着往下走。路徑相對...以_index, _index.json的位置爲準。」）
    def test_entry_index_field(self):
        (self.ws / "lk" / "sub").mkdir(parents=True)
        self.write("lk/_index.json", {"sub": {"description": "Sub folder", "index": "sub/_index.json"},
                                      "data.json": {"description": "Data", "index": "data.json#/_index"},
                                      "up": {"index": "../me.json#/views"},                      # 沒有 description：空欄
                                      "abs": {"description": "A", "index": "/srv/kb/_index.json"},  # 絕對路徑照用
                                      "num": {"description": "N", "index": 3},                    # 壞的只標這一行
                                      "hash": {"description": "H", "index": "x.json#a"},
                                      "empty": {"description": "E", "index": ""},
                                      "plain": {"description": "P"}})
        self.assertEqual(self.ok(path="lk"), [
            "[index] lk/_index.json, 8 entries",
            "sub\tSub folder\tindex: lk/sub/_index.json",                                     # 從 _index.json 所在的資料夾算
            "data.json\tData\tindex: lk/data.json#/_index",
            "up\t\tindex: me.json#/views",
            "abs\tA\tindex: /srv/kb/_index.json",
            "num\tN\tindex: bad (number; must be a path string to another index, counted from what holds this index: e.g. sub/_index.json, or in a JSON object sub/_index, ../a.json#/_index)",
            "hash\tH\tindex: bad (not a path; must be a path string to another index, counted from what holds this index: e.g. sub/_index.json, or in a JSON object sub/_index, ../a.json#/_index)",
            "empty\tE\tindex: bad (not a path; must be a path string to another index, counted from what holds this index: e.g. sub/_index.json, or in a JSON object sub/_index, ../a.json#/_index)",
            "plain\tP"])
        self.assertEqual(self.ok(path="lk", key="sub")[1], "sub\tSub folder\tindex: lk/sub/_index.json")
        # 不跟著往下走：指到的那份不在也不查
        self.assertEqual(len(self.ok(path="lk")), 9)
        # 使用者 11-12 晚「如果是在json物件內的，某key的_index，那他就從這個json物件開始算(把這個json物件當成資料夾)。
        # 然後如果這個json物件是這個.json檔案的根，那他就等同於這個檔案。」
        self.write("lk/sub/v.json", {"_index": {"a": {"description": "A", "index": "a/_index"},          # 根物件＝這個檔：往下是 key
                                                "up": {"index": "../w.json#/_index"},                 # 根物件的 ..＝檔案所在的資料夾
                                                "far": {"index": "../../_index.json"},
                                                "old": {"index": "w.json#/_index"}},                  # 物件裡又寫 #：不是路徑
                                     "o": {"p": {"_index": {"q": {"index": "q/_index"},
                                                            "sib": {"index": "../r/_index"},          # .. ＝外層物件
                                                            "out": {"index": "../../../x.json#/_index"},
                                                            "self": {"index": ".."}}}},
                                     "views": {"b": {"index": "b/_index"}},
                                     "_metainfo": {"index": {"m": {"index": "m/_index"}}}})
        bad = "bad (not a path; must be a path string to another index, counted from what holds this index: e.g. sub/_index.json, or in a JSON object sub/_index, ../a.json#/_index)"
        self.assertEqual(self.ok(path="lk/sub/v.json")[1:], [
            "m\t\tindex: lk/sub/v.json#/m/_index",                                         # _metainfo 裡的 index：容器同 _index（描述的那個物件）
            "a\tA\tindex: lk/sub/v.json#/a/_index", "up\t\tindex: lk/sub/w.json#/_index",
            "far\t\tindex: lk/_index.json", "old\t\tindex: " + bad])
        self.assertEqual(self.ok(path="lk/sub/v.json#/o/p")[1:], [
            "q\t\tindex: lk/sub/v.json#/o/p/q/_index", "sib\t\tindex: lk/sub/v.json#/o/r/_index",
            "out\t\tindex: lk/sub/x.json#/_index", "self\t\tindex: lk/sub/v.json#/o"])
        self.assertEqual(self.ok(index="lk/sub/v.json#/views")[1], "b\t\tindex: lk/sub/v.json#/b/_index")   # 主觀 index：表所在的上一層
        self.assertEqual(self.ok(index="lk/sub/v.json#/o/p/_index")[1], "q\t\tindex: lk/sub/v.json#/o/p/q/_index")

    def test_index_key_as_link(self):
        (self.ws / "ln").mkdir()
        self.write("ln/doc.json", {"_index": "../../kb/_index.json", "a": {"_index": "../_index"},
                                   "n": {"_index": 5}, "s": {"_index": "x.json#a"},
                                   "m": {"_metainfo": {"index": {"q": {"description": "Q"}}}, "_index": "q/_index"},
                                   "w": {"_index": "x.json#/_index"}})
        line = '[index link] ln/doc.json#/_index points to kb/_index.json (not followed; to read it: {"index": "kb/_index.json"})'
        self.assertEqual(self.ok(path="ln/doc.json"), [line])                              # 只印路徑，不往下讀
        self.assertEqual(self.ok(path="ln/doc.json#/a")[0],
                         '[index link] ln/doc.json#/a/_index points to ln/doc.json#/_index (not followed; to read it: {"index": "ln/doc.json#/_index"})')
        self.assertEqual(self.ok(index="ln/doc.json#/_index"),                              # 明講的那份是字串：同樣只印路徑
                         ['[index link] ln/doc.json#/_index points to kb/_index.json (not followed; to read it: {"index": "kb/_index.json"})'])
        self.assertEqual(self.ok(path="ln/doc.json#/m"), [                                  # 有別層的表：照列，標頭說一句連結
            "[index] ln/doc.json#/m/_metainfo/index, 1 entry (ln/doc.json#/m/_index points to ln/doc.json#/m/q/_index, not followed)", "q\tQ"])
        self.assertEqual(self.ok(path="ln/doc.json", index="me.json#/views")[0],
                         "[index] me.json#/views, 2 entries (ln/doc.json#/_index points to kb/_index.json, not followed)")
        self.assertIn("is number", self.err("IndexBad", path="ln/doc.json#/n"))           # 不是物件也不是字串：照舊 IndexBad
        self.assertIn("a string that is not a path", self.err("IndexBad", path="ln/doc.json#/s"))
        self.assertIn("a string that is not a path", self.err("IndexBad", path="ln/doc.json#/w"))   # 物件裡直接寫檔名#：要先 .. 出檔
        self.write("ln/_index.json", "kb/_index.json")                                    # 資料夾的 _index.json 整份不收字串
        self.err("IndexBad", path="ln")


if __name__ == "__main__":
    unittest.main()
