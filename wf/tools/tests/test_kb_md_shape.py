"""Tests for wf/tools/kb_md_shape.py: a data-shaped json page becomes markdown and every leaf value reads back through aos.mdpath."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

TOOLS = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS.parent.parent / "proto8" / "py"))
import kb_md_shape  # noqa: E402
from aos import mdpath  # noqa: E402

PAGE = {"_description": "What this page is.",
        "when": "When to use it.",
        "steps": ["first: do a", "second"],
        "text": ["line one", "", "- a list line"],
        "fields": {"date": "the day", "note": ""},
        "records": [{"who": "ann", "tags": ["x", "y"]}, {"who": "bob", "tags": ["z"]}],
        "link": {"$ref": "other.json#/k"},
        "count": 3, "empty": [],
        "skeleton": {"a": {"b": 1}}}


class Shape(unittest.TestCase):
    def test_every_leaf_reads_back(self):
        page, forced = kb_md_shape.convert_page(PAGE, "lib/sub")
        self.assertEqual(forced, set())
        text = "\n".join(page.lines) + "\n"
        get = lambda *t: mdpath.get(text, list(t))  # noqa: E731
        self.assertEqual(get("_"), "What this page is.\n")
        self.assertEqual(get("when", "_"), "When to use it.\n")
        self.assertEqual(get("steps", "1"), "second")
        self.assertEqual(get("text", "_"), "line one\n\n- a list line\n")
        self.assertEqual(get("fields", "date"), "the day")
        self.assertEqual(get("fields", "note"), "")
        self.assertEqual(get("records", "1", "who", "_"), "bob\n")       # a record with a list in it: every field is a sub-heading
        self.assertEqual(get("records", "0", "tags", "1"), "y")
        self.assertEqual(get("link", "_"), "→ `lib/sub/other.json#/k`\n")
        self.assertEqual(get("count"), 3)
        self.assertEqual(get("empty"), [])
        self.assertEqual(get("skeleton", "a", "b"), 1)
        self.assertFalse(any(l.startswith("<!--") for l in page.lines))

    def test_a_key_that_cannot_be_read_back_stays_a_json_block(self):
        doc = {"outer": [{"n": 1, "inner": [{"k": "a"}, {"k": "b"}]}, {"n": 2, "inner": []}]}
        page, forced = kb_md_shape.convert_page(doc, "lib")
        self.assertEqual(forced, {"outer"})             # outer/1 would find the nested heading "1" first
        self.assertEqual(mdpath.get("\n".join(page.lines) + "\n", ["outer", "1", "n"]), 2)

    def test_convert_writes_md_removes_json_and_renames_index_keys(self):
        with tempfile.TemporaryDirectory() as t:
            lib = pathlib.Path(t) / "lib"
            (lib / "sub").mkdir(parents=True)
            (lib / "sub" / "p.json").write_text(json.dumps(PAGE, ensure_ascii=False), encoding="utf-8")
            (lib / "sub" / "_index.json").write_text(json.dumps({"p.json": {"description": "d"}, "p.json#/when": "w"}), encoding="utf-8")
            r = subprocess.run([sys.executable, str(TOOLS / "kb_md_shape.py"), "convert", str(lib), "--write", "--map", str(lib / "m.json")],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("1 pages to md, 0 kept as json", r.stdout)
            self.assertTrue((lib / "sub" / "p.md").is_file())
            self.assertFalse((lib / "sub" / "p.json").exists())
            self.assertEqual(list(json.loads((lib / "sub" / "_index.json").read_text(encoding="utf-8"))), ["p.md", "p.md#/when"])
            m = json.loads((lib / "m.json").read_text(encoding="utf-8"))
            self.assertEqual(m["lib/sub/p.json"], "lib/sub/p.md")
            self.assertEqual(m["lib/sub/p.json#/_description"], "lib/sub/p.md#/_")
            self.assertEqual(m["lib/sub/p.json#/when"], "lib/sub/p.md#/when")
            self.assertEqual(m["lib/sub/p.json#/records/1/who"], "lib/sub/p.md#/records/1/who")


if __name__ == "__main__":
    unittest.main()
