"""memory_write（純 JSON 樹）：add／set／rm 同時維護內容與表裡那格、寫到庫外也行、自己的簡介當普通路徑寫、各錯誤代號；寫完用 memory 讀回來對。"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ENTRY = Path(__file__).resolve().parents[1] / "_entry"
READER = Path(__file__).resolve().parents[2] / "memory" / "_entry"


@unittest.skipUnless(shutil.which("aos-json"), "aos-json not on PATH")
class WritingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(os.path.realpath(self.tmp.name))
        self.root = self.base / "kb"
        (self.root / "notes").mkdir(parents=True)
        self.put("_description.json", "Root.")
        self.put("_index.json", {"notes/": {"_description": "Notes."}})
        self.put("notes/_index.json", {})
        self.env = {k: v for k, v in os.environ.items() if k != "AOS_CD"}
        self.env.update(AOS_MEMORY=str(self.root), AOS_CD=str(ENTRY.parent))

    def put(self, rel, value):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(value))

    def load(self, rel):
        return json.loads((self.root / rel).read_text())

    def run_tool(self, entry=ENTRY, env=None, **args):
        return subprocess.run([sys.executable, str(entry)], input=json.dumps(args), text=True,
                              capture_output=True, env=dict(self.env, **(env or {})), timeout=30)

    def ok(self, **args):
        r = self.run_tool(**args)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stderr, "")
        return r.stdout

    def fails(self, code, env=None, **args):
        r = self.run_tool(env=env, **args)
        self.assertEqual(r.returncode, 1, r.stdout)
        line = r.stderr.strip().splitlines()[-1]
        self.assertTrue(line.startswith("memory_write: error: %s " % code), line)
        self.assertEqual(r.stdout.strip(), line)
        return line

    def read(self, **args):
        r = self.run_tool(entry=READER, **args)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def test_add_file_writes_value_and_index(self):
        out = self.ok(op="add", path="notes/amy.json", value="Amy likes tea.", description="Who Amy is")
        self.assertEqual(out, "node: notes/amy.json\nadded\n")
        self.assertEqual(self.load("notes/amy.json"), "Amy likes tea.")
        self.assertEqual(self.load("notes/_index.json"), {"amy.json": {"_description": "Who Amy is"}})
        self.assertIn("  notes/amy.json  Who Amy is", self.read(op="ls", path="notes/"))

    def test_add_text_file_and_index_created_when_missing(self):
        (self.root / "notes" / "_index.json").unlink()
        self.ok(op="add", path="notes/trip.md", value="# Trip\nnice", description="A trip")
        self.assertEqual((self.root / "notes" / "trip.md").read_text(), "# Trip\nnice")
        self.assertEqual(self.load("notes/_index.json"), {"trip.md": {"_description": "A trip"}})
        self.assertNotEqual(os.stat(self.root / "notes" / "trip.md").st_mode & 0o044, 0)

    def test_add_key_in_object_writes_index_in_same_object(self):
        self.put("notes/amy.json", {"name": "Amy", "deep": {"a": 1}})
        self.ok(op="add", path="notes/amy.json#/phone", value="0912", description="Amy's phone")
        self.ok(op="add", path="notes/amy.json#/deep/b~1c", value=2, description="Slash key")
        data = self.load("notes/amy.json")
        self.assertEqual(data["phone"], "0912")
        self.assertEqual(data["_index"], {"phone": {"_description": "Amy's phone"}})
        self.assertEqual(data["deep"], {"a": 1, "b/c": 2, "_index": {"b~1c": {"_description": "Slash key"}}})
        self.assertIn("  notes/amy.json#/deep/b~1c  Slash key", self.read(op="ls", path="notes/amy.json#/deep"))
        self.ok(op="rm", path="notes/amy.json#/deep/b~1c")
        self.assertEqual(self.load("notes/amy.json")["deep"], {"a": 1, "_index": {}})

    def test_add_folder(self):
        self.ok(op="add", path="notes/trips/", description="Trips")
        self.assertEqual(self.load("notes/trips/_index.json"), {})
        self.assertEqual(self.load("notes/_index.json"), {"trips/": {"_description": "Trips"}})
        self.assertIn("  notes/trips/  Trips", self.read(op="read", path="notes/"))

    def test_set_value_and_description_keeps_tags(self):
        self.put("notes/amy.json", {"phone": "1", "_index": {"phone": {"_description": "old", "tags": ["people"]}}})
        self.put("notes/_index.json", {"amy.json": {"_description": "old", "tags": ["people"]}})
        self.ok(op="set", path="notes/amy.json#/phone", value="2", description="Phone")
        self.assertEqual(self.load("notes/amy.json"),
                         {"phone": "2", "_index": {"phone": {"_description": "Phone", "tags": ["people"]}}})
        self.ok(op="set", path="notes/amy.json", description="About Amy")
        self.assertEqual(self.load("notes/_index.json"), {"amy.json": {"_description": "About Amy", "tags": ["people"]}})
        self.ok(op="set", path="notes/amy.json", value="whole new")
        self.assertEqual(self.load("notes/amy.json"), "whole new")
        self.ok(op="set", path="notes/", description="All notes")
        self.assertEqual(self.load("_index.json")["notes/"], {"_description": "All notes"})

    def test_set_description_adds_missing_cell(self):
        self.put("notes/x.json", {"k": 1})
        self.ok(op="set", path="notes/x.json#/k", description="K")
        self.assertEqual(self.load("notes/x.json"), {"k": 1, "_index": {"k": {"_description": "K"}}})

    def test_rm_file_key_and_folder_pull_index(self):
        self.ok(op="add", path="notes/amy.json", value={"phone": "1"}, description="Amy")
        self.ok(op="set", path="notes/amy.json#/phone", value="1", description="Phone")
        self.assertEqual(self.ok(op="rm", path="notes/amy.json#/phone"), "node: notes/amy.json#/phone\nremoved\n")
        self.assertEqual(self.load("notes/amy.json"), {"_index": {}})
        self.ok(op="rm", path="notes/amy.json")
        self.assertFalse((self.root / "notes" / "amy.json").exists())
        self.assertEqual(self.load("notes/_index.json"), {})
        self.ok(op="add", path="notes/trips/", description="Trips")
        self.ok(op="rm", path="notes/trips/")                       # 只有 _index.json＝空
        self.assertEqual(self.load("notes/_index.json"), {})
        self.ok(op="add", path="notes/trips/", description="Trips")
        self.ok(op="add", path="notes/trips/a.json", value=1, description="A")
        self.fails("ChildrenExist", op="rm", path="notes/trips/")
        self.ok(op="rm", path="notes/trips", recursive=True)
        self.assertFalse((self.root / "notes" / "trips").exists())
        self.assertEqual(self.load("notes/_index.json"), {})

    def test_rm_finds_cell_written_another_way(self):
        self.put("_index.json", {"notes": {"_description": "no slash"}, "./x.json": {}})
        self.put("x.json", 1)
        self.ok(op="rm", path="x.json")
        self.ok(op="rm", path="notes/", recursive=True)
        self.assertEqual(self.load("_index.json"), {})

    def test_writes_outside_root_are_allowed(self):
        self.ok(op="add", path="../out.json", value=1, description="x")
        self.assertEqual(json.loads((self.base / "out.json").read_text()), 1)
        self.assertEqual(json.loads((self.base / "_index.json").read_text()), {"out.json": {"_description": "x"}})
        (self.base / "out").mkdir()
        os.symlink(self.base / "out", self.root / "link")
        self.ok(op="add", path="link/x.json", value=2, description="through a link")
        self.assertEqual(json.loads((self.base / "out" / "x.json").read_text()), 2)
        self.ok(op="set", path=str(self.base / "out" / "x.json"), value=3)
        self.assertEqual(json.loads((self.base / "out" / "x.json").read_text()), 3)
        self.ok(op="rm", path="link/x.json")
        self.assertFalse((self.base / "out" / "x.json").exists())
        self.ok(op="add", path=str(self.root / "notes" / "abs.json"), value=1, description="absolute inside")
        if os.geteuid() != 0:                    # 作業系統不讓寫＝WriteFailed
            (self.base / "ro").mkdir()
            os.chmod(self.base / "ro", 0o555)
            self.addCleanup(os.chmod, self.base / "ro", 0o755)
            self.fails("WriteFailed", op="add", path="../ro/x.json", value=1, description="x")
            self.fails("WriteFailed", op="add", path="../ro/x.md", value="t", description="x")
            self.fails("WriteFailed", op="add", path="../ro/d/", description="x")
        self.fails("PathBad", op="rm", path="/")
        self.fails("PathBad", op="rm", path="")
        self.fails("PathBad", op="add", path="notes/_x.json", value=1, description="x")
        self.assertIn("_description.json", self.fails("PathBad", op="set", path="/", description="x"))

    def test_own_descriptions_are_plain_paths(self):
        self.ok(op="set", path="_description.json", value="New root.")
        self.assertEqual(self.load("_description.json"), "New root.")
        self.ok(op="add", path="notes/_description.json", value="All the notes.")
        self.assertEqual(self.load("notes/_index.json"), {})       # 不進表
        self.assertTrue(self.read(op="read", path="notes/").startswith("node: notes/\nAll the notes.\n\nchildren:"))
        self.put("notes/amy.json", {"_index": {}, "phone": "1"})
        self.ok(op="add", path="notes/amy.json#/_description", value="About Amy.")
        self.assertEqual(self.load("notes/amy.json"), {"_index": {}, "phone": "1", "_description": "About Amy."})
        self.ok(op="set", path="notes/amy.json#/_description", value="Amy.")
        self.assertTrue(self.read(op="read", path="notes/amy.json").startswith("node: notes/amy.json\nAmy.\n\nchildren:"))
        self.fails("ValueBad", op="set", path="notes/_description.json", value={"a": 1})
        self.fails("ValueBad", op="add", path="notes/amy.json#/_description", value=1)
        self.fails("ArgumentsBad", op="set", path="notes/_description.json", value="x", description="x")
        self.fails("NodeExists", op="add", path="notes/_description.json", value="again")
        self.ok(op="rm", path="notes/_description.json")
        self.ok(op="rm", path="notes/amy.json#/_description")
        self.assertFalse((self.root / "notes" / "_description.json").exists())
        self.assertEqual(self.load("notes/amy.json"), {"_index": {}, "phone": "1"})
        self.assertEqual(self.load("notes/_index.json"), {})
        self.fails("PathBad", op="add", path="notes/_description.json/", description="x")

    def test_errors(self):
        self.put("notes/a.json", {"list": [1, 2], "r": {"$ref": "b.json"}})
        self.put("notes/b.json", {"k": 1})
        self.fails("ArgumentsBad", op="add")
        self.assertIn('call again like {"op": "add", "path": "notes/n.json", "description": "<one line saying what this is>", "value": 1}',
                      self.fails("ArgumentsBad", op="add", path="notes/n.json", value=1))
        self.fails("ArgumentsBad", op="add", path="notes/n.json", value=1, description="")
        self.fails("OpUnknown", op="edit", path="notes/a.json")
        self.fails("NodeExists", op="add", path="notes/a.json", value=1, description="x")
        self.fails("NodeExists", op="add", path="notes/a.json#/list", value=1, description="x")
        missing = self.fails("NodeMissing", op="add", path="nope/deep/x.json", value=1, description="x")
        self.assertIn("/ has: notes/", missing)
        self.assertIn('first call {"op": "add", "path": "nope/", "description": ', missing)   # 教先開最上面那層資料夾
        self.assertIn('first call {"op": "add", "path": "notes/new.json", "value": {}, ',
                      self.fails("NodeMissing", op="add", path="notes/new.json#/k", value=1, description="x"))
        self.assertNotIn("first call", self.fails("NodeMissing", op="add", path="notes/a.json/x.json", value=1, description="x"))
        self.fails("NodeMissing", op="add", path="notes/a.json#/no/x", value=1, description="x")
        self.fails("NodeMissing", op="set", path="notes/zz.json", value=1)
        self.fails("NodeMissing", op="set", path="notes/a.json#/zz", value=1)
        self.fails("NodeMissing", op="rm", path="notes/a.json#/zz")
        self.fails("ValueBad", op="add", path="notes/n.json", description="x")
        self.fails("ValueBad", op="add", path="notes/n.md", value=5, description="x")
        self.fails("ValueBad", op="add", path="notes/n.json", value="x" * 8001, description="x")
        self.fails("ValueBad", op="set", path="notes/a.json")
        self.fails("ValueBad", op="add", path="notes/dir/", value=1, description="x")
        self.ok(op="add", path="notes/dir0/", value=None, description="null value = no value")   # 小模型常帶 "value": null
        self.ok(op="add", path="notes/dir1/", value="", description="empty value = no value")
        self.assertNotIn('"value"', self.fails("ArgumentsBad", op="add", path="notes/dir2/", value=""))
        self.fails("TargetBad", op="add", path="notes/a.json#/list/2", value=1, description="x")
        self.fails("TargetBad", op="rm", path="notes/a.json#/list/0")
        self.fails("TargetBad", op="add", path="notes/a.json#/r/z", value=1, description="x")
        self.fails("TargetBad", op="set", path="notes/", value=1)
        self.fails("PathBad", op="add", path="notes/a.json#bad", value=1, description="x")
        (self.root / "notes" / "bad.json").write_text("{nope")
        self.fails("FileBad", op="add", path="notes/bad.json#/k", value=1, description="x")
        self.fails("MemoryMissing", env={"AOS_MEMORY": ""}, op="rm", path="notes/a.json")
        empty = self.base / "emptybin"
        empty.mkdir()
        self.fails("LaunchFailed", env={"PATH": str(empty)}, op="add", path="notes/n.json", value=1, description="x")
        self.assertEqual(self.load("notes/a.json"), {"list": [1, 2], "r": {"$ref": "b.json"}})
        self.assertEqual(self.load("notes/b.json"), {"k": 1})

    def test_help_is_english(self):
        r = subprocess.run([sys.executable, str(ENTRY), "--help"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertIn("usage: memory_write", r.stdout)
        self.assertTrue(r.stdout.isascii(), r.stdout)


if __name__ == "__main__":
    unittest.main()
