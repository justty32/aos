"""以本地假資料驗證 memory 的 JSON Pointer 與既有節點路徑行為。"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import sys
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[2]),
                str(Path(__file__).resolve().parents[3])]
import memory_fs

ENTRY = Path(__file__).resolve().parents[1] / "_entry"


class PointerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "data.json").write_text(json.dumps({
            "a/b": {"~key": [None, False, {"": "text"}]}, "": 42, "~1": "escaped",
        }))
        (self.root / "note.md").write_text("# Note\nSummary\n")
        (self.root / "folder").mkdir()
        (self.root / "bad.json").write_text("{")
        (self.root / "scalar.json").write_text("null")

    def run_tool(self, path, op="read", **args):
        env = dict(os.environ, AOS_MEMORY=str(self.root), AOS_CD=str(ENTRY.parent))
        return subprocess.run([str(ENTRY)], input=json.dumps(dict(op=op, path=path, **args)),
                              text=True, capture_output=True, env=env)

    def test_values_and_escapes(self):
        for path, value in [("data#/a~1b/~0key/0", None),
                            ("data#/a~1b/~0key/1", False),
                            ("data#/~01", "escaped"),
                            ("data#/a~1b/~0key/2/", "text"), ("data#/", 42),
                            ("data#/a~1b", {"~key": [None, False, {"": "text"}]})]:
            with self.subTest(path=path):
                result = self.run_tool(path)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout.split("\n\n", 1)[1]), value)

    def test_errors(self):
        for path, code in [("data#/missing", "PointerMissing"),
                           ("scalar#/x", "PointerMissing"),
                           ("data#/a~1b/~0key/0/x", "PointerMissing"),
                           ("data#/a~1b/~0key/01", "PointerMissing"),
                           ("data#/a~1b/~0key/-", "PointerMissing"),
                           ("data#/a~1b/~0key/" + "9" * 5000, "PointerMissing"),
                           ("data#/bad~2", "PathBad"), ("data#", "PathBad"),
                           ("data#bad", "PathBad"), ("note#/x", "TargetBad"),
                           ("folder#/x", "TargetBad"), ("bad#/x", "FileBad"),
                           ("absent#/x", "NodeMissing")]:
            with self.subTest(path=path[:60]):
                result = self.run_tool(path)
                self.assertEqual(result.returncode, 1)
                self.assertIn("error: " + code + " ", result.stderr)
                self.assertEqual(result.stdout, result.stderr)
        for op in ("ls", "find"):
            result = self.run_tool("data#/x", op, query="text")
            self.assertEqual(result.returncode, 1)
            self.assertIn("error: PathBad ", result.stderr)

    def test_non_string_paths(self):
        for path in (1, 1.5, True, [], {}, ["#"], {"#": 1}):
            with self.subTest(path=path):
                for op in ("read", "ls", "find"):
                    result = self.run_tool(path, op, query="text")
                    self.assertEqual(result.returncode, 1)
                    self.assertIn("error: ArgumentsBad ", result.stderr)
                    self.assertEqual(result.stdout, result.stderr)
                for parse in (memory_fs.parse_path, memory_fs.parse_read_path):
                    with patch.object(memory_fs, "die", side_effect=RuntimeError) as fail:
                        with self.assertRaises(RuntimeError):
                            parse(path)
                        self.assertEqual(fail.call_args.args[0], "PathBad")
        self.assertEqual(memory_fs.parse_path(None), [])
        self.assertEqual(memory_fs.parse_read_path(None), ([], None))

    def test_plain_reads_and_priority(self):
        result = self.run_tool("data")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"a/b"', result.stdout)
        (self.root / "data.md").write_text("# Shadow\n")
        result = self.run_tool("data#/a~1b")
        self.assertIn("error: TargetBad ", result.stderr)
        result = self.run_tool("note/")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("# Note", result.stdout)


if __name__ == "__main__":
    unittest.main()
