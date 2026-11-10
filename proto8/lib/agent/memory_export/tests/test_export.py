"""memory_export（純 JSON 樹）：node 行、簡介、字串原樣、其他 JSON 包 ```json、表的順序與 not in index、防繞圈、截斷、錯誤。"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ENTRY = Path(__file__).resolve().parents[1] / "_entry"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


@unittest.skipUnless(shutil.which("aos-json"), "aos-json not on PATH")
class ExportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(os.path.realpath(self.tmp.name)) / "kb"
        write(self.root / "_description.json", "# Root\n\nThe root page.")
        write(self.root / "_index.json", {"rules.json": {"_description": "Rules."},
                                          "errors.json": {"_description": "Errors."}})
        write(self.root / "rules.json", "# Rules\n\nNever.\n")
        write(self.root / "errors.json", {
            "_description": "How to read errors.",
            "_index": {"codes": {"_description": "Codes."},
                       "../rules.json": {"_description": "Back to rules."}},
            "codes": "Code text",
            "plain": {"a": [1, "two"]},
            "about": {"_description": "Only a description.", "x": 1}})
        write(self.root / "cli" / "_index.json", {"flags.json": {"_description": "Flags."}})
        write(self.root / "cli" / "flags.json", "--help")
        os.symlink(self.root, self.root / "cli" / "loop")
        self.env = {k: v for k, v in os.environ.items() if k != "AOS_CD"}
        self.env.update(AOS_MEMORY=str(self.root), AOS_CD=str(ENTRY.parent))

    def run_tool(self, **args):
        return subprocess.run([sys.executable, str(ENTRY)], input=json.dumps(args), text=True,
                              capture_output=True, env=self.env, timeout=30)

    def nodes(self, out):
        return [l[len("<!-- node: "):-len(" -->")] for l in out.splitlines() if l.startswith("<!-- node: ")]

    def test_root_order_and_shapes(self):
        r = self.run_tool()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.nodes(r.stdout), ["/", "rules.json", "errors.json", "errors.json#/codes",
                                                "rules.json", "errors.json#/plain", "errors.json#/about", "cli/", "cli/flags.json",
                                                "cli/loop/"])
        self.assertTrue(r.stdout.startswith("<!-- node: / -->\n# Root\n\nThe root page.\n\n<!-- node: rules.json -->\n# Rules\n\nNever.\n\n"))
        self.assertIn("<!-- node: errors.json -->\nHow to read errors.\n\n", r.stdout)
        self.assertIn("<!-- node: errors.json#/codes -->\nCode text\n", r.stdout)
        self.assertIn('<!-- node: errors.json#/plain -->\n```json\n{\n  "a": [\n    1,\n    "two"\n  ]\n}\n```', r.stdout)
        self.assertIn('<!-- node: errors.json#/about -->\nOnly a description.\n\n```json\n{\n  "x": 1\n}\n```', r.stdout)
        self.assertNotIn("_description", r.stdout)
        self.assertEqual(r.stdout.count("(already exported above; not followed)"), 2)   # ../rules.json 與 cli/loop 捷徑

    def test_subpath(self):
        r = self.run_tool(path="errors.json#/codes")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "<!-- node: errors.json#/codes -->\nCode text\n")
        r = self.run_tool(path="cli/")
        self.assertEqual(self.nodes(r.stdout)[:2], ["cli/", "cli/flags.json"])

    def test_truncate(self):
        r = self.run_tool(max_bytes=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout.splitlines()[-1], r"^\[truncated: \d+ more bytes; export a child path\]$")

    def test_errors(self):
        r = self.run_tool(path="nope.json")
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stdout.startswith("memory_export: error: NodeMissing nope.json not found; / has: "), r.stdout)
        self.assertIn("memory_export: error: ArgumentsBad", self.run_tool(max_bytes=0).stdout)
        self.assertIn("memory_export: error: PathBad", self.run_tool(path="errors.json#bad").stdout)


if __name__ == "__main__":
    unittest.main()
