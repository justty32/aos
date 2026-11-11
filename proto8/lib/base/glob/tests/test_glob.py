"""glob 工具：** 零層與多層、不含 / 的樣式任何深度、type、sort mtime、翻頁、隱藏與明寫 . 段、資料夾捷徑列出不進、gitignore、PatternBad、FileBad、工作區外。"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ENTRY = Path(__file__).resolve().parents[1] / "_entry"


class GlobTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ws, self.out = self.root / "ws", self.root / "out"
        self.ws.mkdir()
        self.out.mkdir()
        self.env = dict(os.environ, AOS_WS=str(self.ws))
        for rel in ("a.py", "src/b.py", "src/deep/c.py", "src/deep/d.json", "docs/e.md", ".hid/f.py", "src/.g.py"):
            p = self.ws / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x\n")

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, **args):
        r = subprocess.run([str(ENTRY)], input=json.dumps(args).encode(), capture_output=True, env=self.env)
        return r.returncode, r.stdout.decode(), r.stderr.decode()

    def ok(self, **args):
        code, out, err = self.call(**args)
        self.assertEqual(code, 0, out + err)
        return out.splitlines()

    def test_any_depth_and_double_star(self):
        self.assertEqual(self.ok(pattern="*.py"), ["a.py", "src/b.py", "src/deep/c.py"])
        self.assertEqual(self.ok(pattern="src/**/*.py"), ["src/b.py", "src/deep/c.py"])      # ** 零層也算
        self.assertEqual(self.ok(pattern="src/*.py"), ["src/b.py"])
        self.assertEqual(self.ok(pattern="**/deep/*"), ["src/deep/c.py", "src/deep/d.json"])
        self.assertEqual(self.ok(pattern="?.py"), ["a.py", "src/b.py", "src/deep/c.py"])
        self.assertEqual(self.ok(pattern="[ab].*"), ["a.py", "src/b.py"])
        self.assertEqual(self.ok(pattern="[!ab].py"), ["src/deep/c.py"])
        self.assertEqual(self.ok(pattern="nothing*"), ["... no matches"])

    def test_type_and_folders(self):
        self.assertEqual(self.ok(pattern="src/**", type="dir"), ["src/", "src/deep/"])
        self.assertEqual(self.ok(pattern="*", type="any", path="src"), ["src/b.py", "src/deep/", "src/deep/c.py", "src/deep/d.json"])
        code, out, _ = self.call(pattern="*", type="link")
        self.assertEqual((code, out), (1, "glob: error: ArgumentsBad type must be one of: file, dir, any\n"))

    def test_hidden(self):
        self.assertEqual(self.ok(pattern="*.py", hidden=True), [".hid/f.py", "a.py", "src/.g.py", "src/b.py", "src/deep/c.py"])
        self.assertEqual(self.ok(pattern=".hid/*"), [".hid/f.py"])                         # 明寫 . 段＝明指
        self.assertEqual(self.ok(pattern="**/.g.py"), ["src/.g.py"])

    def test_sort_mtime_and_paging(self):
        for i, rel in enumerate(("src/deep/c.py", "a.py", "src/b.py")):
            os.utime(self.ws / rel, (1000 + i, 1000 + i))
        self.assertEqual(self.ok(pattern="*.py", sort="mtime"), ["src/b.py", "a.py", "src/deep/c.py"])
        self.assertEqual(self.ok(pattern="*.py", max_items=2), ["a.py", "src/b.py", "... next_offset 2 (3 paths in all)"])
        self.assertEqual(self.ok(pattern="*.py", offset=2), ["src/deep/c.py"])
        self.assertEqual(self.ok(pattern="*.py", offset=5), ["... no matches from offset 5 (3 paths in all)"])

    def test_folder_links_listed_not_entered(self):
        os.symlink(self.ws / "src", self.ws / "src" / "loop")
        os.symlink(self.ws / "src", self.ws / "slink")
        self.assertEqual(self.ok(pattern="*.py"), ["a.py", "src/b.py", "src/deep/c.py"])
        self.assertEqual(self.ok(pattern="*", type="dir"), ["docs/", "slink/", "src/", "src/deep/", "src/loop/"])
        self.assertEqual(self.ok(pattern="*.py", path="slink"), ["slink/b.py", "slink/deep/c.py"])   # path 本身是捷徑＝跟過去

    @unittest.skipUnless(shutil.which("git"), "needs git")
    def test_gitignore(self):
        subprocess.run(["git", "-C", str(self.ws), "init", "-q"], check=True)
        (self.ws / ".gitignore").write_text("deep/\n")
        self.assertEqual(self.ok(pattern="*.py"), ["a.py", "src/b.py"])
        self.assertEqual(self.ok(pattern="*.py", gitignore=False), ["a.py", "src/b.py", "src/deep/c.py"])
        self.assertEqual(self.ok(pattern="*", type="dir", hidden=True), [".hid/", "docs/", "src/"])      # .git 不列

    def test_errors_and_outside(self):
        self.assertEqual(self.call(pattern="[ab")[:2], (1, "glob: error: PatternBad unclosed [ in '[ab'\n"))
        self.assertEqual(self.call(pattern="/abs/*")[:2],
                         (1, "glob: error: PatternBad the pattern is relative to path; put the folder in path instead\n"))
        self.assertEqual(self.call(pattern="*", path="a.py")[:2],
                         (1, "glob: error: FileBad a.py is not a folder; glob searches under a folder (put the folder in path)\n"))
        self.assertEqual(self.call(pattern="*", path="nope")[:2], (1, "glob: error: FileMissing nope\n"))
        (self.out / "o.txt").write_text("x")
        self.assertEqual(self.ok(pattern="*.txt", path=str(self.out)), [str(self.out / "o.txt")])
        self.assertEqual(self.ok(pattern="*.txt", path="../out"), [str(self.out / "o.txt")])


if __name__ == "__main__":
    unittest.main()
