"""index_view 讀 md 與 $ref 的定向測試（11-21 晚，thinking 2026-11/21/知識庫-骨架加md-規劃-1121 的 01、10）：純字串一項、$ref 一項、夾的 _index.md、md 頁自己的 _index／index 標題、index 參數指進 md。"""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

LIB = Path(__file__).resolve().parents[1]
BIN = LIB.parent / "bin"
TOOL = LIB / "tools" / "base" / "index_view" / "_entry"

PAGE = """Lead line of the page.

# Who am I

Finding your own name.

# _index

- Who am I: finding your own name
- What is in your stack: the files in your stack
- a line without a key

# index

- Who am I: loses to _index

# Deep

## index

- inner: an index in a section

# Data

```json
{"a": {"description": "from a json block"}, "b": "plain string"}
```

# Prose

Just words, no list.
"""


class IndexViewMdTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ws = Path(self.tmp.name)
        self.env = dict(os.environ, AOS_WS=str(self.ws))
        self.env.pop("AOS_JSON_MAX_ITEMS", None)
        self.env["PATH"] = "%s:%s" % (BIN, self.env.get("PATH", ""))
        self.put("me.md", PAGE)
        self.put("plain.md", "# One\n\ntext\n\n# Two\n\nmore\n")
        self.put("only_index.md", "# index\n\n- x.md: the x page\n")
        self.put("facts.json", {"who": "a sentence from json", "entry": {"description": "a whole entry", "index": "sub/_index.json"},
                                "num": 3})

    def put(self, name, doc):
        p = self.ws / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(doc if isinstance(doc, str) else json.dumps(doc), encoding="utf-8")

    def run_tool(self, **args):
        return subprocess.run([str(TOOL)], input=json.dumps(args), text=True, capture_output=True, env=self.env)

    def ok(self, **args):
        r = self.run_tool(**args)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stderr, "")
        return r.stdout.rstrip("\n").split("\n")

    def err(self, code, **args):
        r = self.run_tool(**args)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("index_view: error: %s " % code, r.stdout)
        return r.stdout

    def test_plain_string_entry(self):
        # 11-21 第 18 句「也可以是純字串，但這個字串就是等同於description了」
        self.put("kb/_index.json", {"me.md": "Finding your own name", "x": {"description": "obj"}, "multi": "a\nb\tc"})
        self.assertEqual(self.ok(path="kb"), ["[index] kb/_index.json, 3 entries", "me.md\tFinding your own name", "x\tobj", "multi\ta b c"])

    def test_ref_entries(self):
        self.put("kb/_index.json", {
            "s": {"$ref": "../facts.json#/who"},                         # 拿到字串＝description
            "e": {"$ref": "../facts.json#/entry"},                       # 拿到物件＝那一項（index 欄從它所在的位置算）
            "d": {"description": {"$ref": "../facts.json#/who"}},       # description 是 $ref
            "m": {"$ref": "../me.md#/Who am I/_"},                        # 指到 md 用 mdpath
            "mk": {"description": {"$ref": "../me.md#/_index/Who am I"}},
            "gone": {"$ref": "../nope.json"},
            "miss": {"$ref": "../me.md#/Nope"},
            "word": {"$ref": "#abc"},
            "num": {"$ref": "../facts.json#/num"},
            "ok": {"description": "still fine"}})
        out = self.ok(path="kb")
        self.assertEqual(out[0], "[index] kb/_index.json, 10 entries")
        self.assertEqual(out[1:4], ["s\ta sentence from json", "e\ta whole entry\tindex: sub/_index.json", "d\ta sentence from json"])
        self.assertEqual(out[4:6], ["m\tFinding your own name.", "mk\tfinding your own name"])
        self.assertTrue(out[6].startswith("gone\tbad $ref (") and "nope.json" in out[6], out[6])   # 解不開只標這一行
        self.assertTrue(out[7].startswith("miss\tbad $ref (") and "Nope" in out[7], out[7])
        self.assertTrue(out[8].startswith("word\tbad $ref ("), out[8])
        self.assertTrue(out[9].startswith("num\tbad $ref (it points to number"), out[9])
        self.assertEqual(out[10], "ok\tstill fine")
        self.assertEqual(self.ok(path="kb", key="s")[1], "s\ta sentence from json")

    def test_folder_index_md(self):
        # 夾沒有 _index.json 才讀 _index.md（第 18 句）：整份當字典式清單
        self.put("mdkb/_index.md", "- me.md: Finding your own name\n- **rules.json**: the rules\n- no key here\n")
        self.assertEqual(self.ok(path="mdkb"), ["[index] mdkb/_index.md, 2 entries", "me.md\tFinding your own name", "rules.json\tthe rules"])
        self.put("mdkb/_index.json", {"only.json": {"description": "json wins"}})          # 有 _index.json 就完全不看 _index.md
        self.assertEqual(self.ok(path="mdkb"), ["[index] mdkb/_index.json, 1 entry", "only.json\tjson wins"])
        self.put("bad/_index.md", "Just a sentence, no list.\n")
        self.err("IndexBad", path="bad")
        (self.ws / "none").mkdir()
        self.assertTrue(self.ok(path="none")[0].startswith("[no index] none/_index.json does not exist."))   # 都沒有：照舊

    def test_md_page_index(self):
        self.assertEqual(self.ok(path="me.md"), ["[index] me.md#/_index, 2 entries",           # _index 贏 index；沒鍵的項不算
                                                 "Who am I\tfinding your own name", "What is in your stack\tthe files in your stack"])
        self.assertEqual(self.ok(path="only_index.md"), ["[index] only_index.md#/index, 1 entry", "x.md\tthe x page"])
        self.assertEqual(self.ok(path="me.md#/Deep"), ["[index] me.md#/Deep/index, 1 entry", "inner\tan index in a section"])
        out = self.ok(path="plain.md")
        self.assertEqual(out, ["[no index] plain.md has no heading _index or index (to see its headings: json_ls plain.md). "
                               "An index is a view, not a listing: use ls or json_ls to see what is really there."])
        self.assertTrue(self.ok(path="me.md#/Prose")[0].startswith("[no index] me.md#/Prose has no heading"))
        self.err("PointerMissing", path="me.md#/Nope")
        self.err("FileMissing", path="nope.md")

    def test_index_param_into_md(self):
        self.assertEqual(self.ok(index="me.md#/Data"), ["[index] me.md#/Data, 2 entries", "a\tfrom a json block", "b\tplain string"])
        self.assertEqual(self.ok(index="me.md#/_index")[0], "[index] me.md#/_index, 2 entries")
        self.assertEqual(self.ok(path="plain.md", index="only_index.md#/index"),
                         ["[index] only_index.md#/index, 1 entry (natural index: plain.md has no heading _index or index (to see its headings: json_ls plain.md))",
                          "x.md\tthe x page"])
        self.assertIn("not an index", self.err("IndexBad", index="me.md#/Prose"))
        self.err("PointerMissing", index="me.md#/Nope")


if __name__ == "__main__":
    unittest.main()
