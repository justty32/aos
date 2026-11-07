"""以本地知識庫驗證 memory 單一標籤與關鍵字交集搜尋。"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ENTRY = Path(__file__).resolve().parents[1] / "_entry"


class FindTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name, value in {
            "alpha.json": {"title": "Alpha", "body": "Needle", "tags": ["Exact", ""]},
            "beta.json": {"title": "Beta", "body": "Needle", "tags": ["other"]},
            "gamma.json": {"title": "Gamma", "body": "hay", "tags": ["Exact"]},
        }.items():
            (self.root / name).write_text(json.dumps(value))
        (self.root / "folder").mkdir()
        (self.root / "folder" / "_tags.json").write_text('{"tags": ["Exact"]}')
        (self.root / "folder" / "child.json").write_text('{"body": "Needle"}')
        (self.root / "note.md").write_text('# Note\nNeedle\n')

    def run_tool(self, **args):
        env = dict(os.environ, AOS_MEMORY=str(self.root), AOS_CD=str(ENTRY.parent))
        return subprocess.run([str(ENTRY)], input=json.dumps(dict(op="find", **args)),
                              text=True, capture_output=True, env=env)

    def paths(self, **args):
        result = self.run_tool(**args)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        return [line.split()[0] for line in result.stdout.splitlines() if line.startswith("  ")]

    def test_tag_only_and_exact(self):
        self.assertEqual(self.paths(tag="Exact"), ["alpha", "folder", "gamma"])
        self.assertEqual(self.paths(tag="exact"), [])
        self.assertEqual(self.paths(tag="Ex"), [])
        self.assertEqual(self.paths(tag=""), ["alpha"])
        self.assertEqual(self.paths(tag="other"), ["beta"])

    def test_query_and_tag_intersection(self):
        self.assertEqual(self.paths(query="needle", tag="Exact"), ["alpha"])
        self.assertEqual(self.paths(query="NEEDLE"), ["alpha", "beta", "folder/child", "note"])
        (self.root / "folder" / "README.md").write_text('# Folder\nNeedle\n')
        self.assertEqual(self.paths(query="needle", tag="Exact"), ["alpha", "folder"])

    def test_scope_and_no_inheritance(self):
        self.assertEqual(self.paths(path="folder", tag="Exact"), ["folder"])
        self.assertEqual(self.paths(path="folder", tag="Exact", query="Needle"), [])
        self.assertEqual(self.paths(path="alpha", tag="Exact"), ["alpha"])
        self.assertEqual(self.paths(path="note", tag="Exact"), [])

    def test_bad_metadata_and_hidden_nodes(self):
        for value in ('{', 'null', '[]', '{"tags":"Exact"}', '{"tags":["Exact",1]}',
                      '{"tags":["Exact",null]}', '{}'):
            with self.subTest(value=value):
                (self.root / "folder" / "_tags.json").write_text(value)
                (self.root / "bad.json").write_text(value)
                self.assertEqual(self.paths(tag="Exact"), ["alpha", "gamma"])
        self.assertFalse(any("_tags" in p for p in self.paths(query="tags")))
        for name in ("_hidden", ".hidden"):
            (self.root / name).mkdir()
            (self.root / name / "_tags.json").write_text('{"tags":["Exact"]}')
        self.assertEqual(self.paths(tag="Exact"), ["alpha", "gamma"])

    def test_priority_and_root(self):
        (self.root / "alpha.md").write_text('# Shadow\nNeedle\n')
        self.assertEqual(self.paths(tag="Exact"), ["folder", "gamma"])
        (self.root / "gamma").mkdir()
        self.assertEqual(self.paths(tag="Exact"), ["folder"])
        (self.root / "_tags.json").write_text('{"tags":["Exact"]}')
        self.assertEqual(self.paths(tag="Exact"), ["/", "folder"])
        (self.root / "README.md").write_text('# Root\nNeedle\n')
        self.assertEqual(self.paths(query="needle", tag="Exact"), ["/"])

    def test_arguments(self):
        for args in ({}, {"query": ""}, {"tag": []}, {"tag": 1}, {"tag": None},
                     {"tag": ["Exact", "other"]},
                     {"query": False, "tag": "Exact"}):
            with self.subTest(args=args):
                result = self.run_tool(**args)
                self.assertEqual(result.returncode, 1)
                self.assertIn('error: ArgumentsBad ', result.stderr)
                self.assertEqual(result.stdout, result.stderr)

    def test_null_optional_and_symlink_cycle(self):
        self.assertEqual(self.paths(query=None, tag="Exact"), ["alpha", "folder", "gamma"])
        (self.root / "folder" / "loop").symlink_to(self.root / "folder", target_is_directory=True)
        self.assertEqual(self.paths(path="folder", tag="Exact"), ["folder", "folder/loop"])

    def test_output_limit(self):
        for i in range(25):
            (self.root / ('item%d.json' % i)).write_text('{"tags":["many"]}')
        result = self.run_tool(tag="many")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len([l for l in result.stdout.splitlines() if l.startswith('  item')]), 20)
        self.assertIn('5 more', result.stdout)


if __name__ == "__main__":
    unittest.main()
