"""remove（rm 的包裝）：檔、捷徑本身、資料夾要 recursive、. ／.. ／/ 拒絕、工作區外照刪（11-10 tool-packs）。"""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ENTRY = Path(__file__).resolve().parents[1] / "_entry"


class RemoveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ws, self.out = self.root / "ws", self.root / "out"
        self.ws.mkdir()
        self.out.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, **args):
        r = subprocess.run([str(ENTRY)], input=json.dumps(args), text=True, capture_output=True,
                           env=dict(os.environ, AOS_WS=str(self.ws)))
        return r.returncode, r.stdout.strip()

    def test_file_and_outside(self):
        (self.ws / "a.txt").write_text("x")
        (self.out / "b.txt").write_text("y")
        self.assertEqual(self.call(path="a.txt"), (0, '{"path":"a.txt","type":"file"}'))
        code, out = self.call(path="../out/b.txt")
        self.assertEqual(code, 0, out)
        self.assertFalse((self.out / "b.txt").exists())
        self.assertEqual(json.loads(out)["path"], str(self.out / "b.txt"))

    def test_folder_needs_recursive(self):
        (self.ws / "d" / "e").mkdir(parents=True)
        (self.ws / "d" / "e" / "f").write_text("z")
        code, out = self.call(path="d")
        self.assertEqual(code, 1)
        self.assertIn("error: FileBad", out)
        self.assertTrue((self.ws / "d").exists())
        self.assertEqual(self.call(path="d", recursive=True), (0, '{"path":"d","type":"dir","counter_files":1}'))
        self.assertFalse((self.ws / "d").exists())

    def test_link_itself(self):
        (self.out / "keep").mkdir()
        (self.ws / "l").symlink_to(self.out / "keep")
        self.assertEqual(self.call(path="l"), (0, '{"path":"l","type":"link"}'))
        self.assertTrue((self.out / "keep").is_dir())

    def test_refusals(self):
        for path in (".", "..", "d/..", "/"):
            code, out = self.call(path=path, recursive=True)
            self.assertEqual(code, 1, path)
            self.assertIn("error: PathBad", out)
        code, out = self.call(path="nope")
        self.assertIn("error: FileMissing", out)


if __name__ == "__main__":
    unittest.main()
