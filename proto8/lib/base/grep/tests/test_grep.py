"""grep 工具：正規式與 fixed、大小寫、context 與 --、files、翻頁、二進位／超大／非 UTF-8、隱藏、資料夾捷徑不跟進、gitignore（有 git、不在 git、git 不在 PATH）、單一檔、工作區外、預算、長行截斷。"""

import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True                        # 不在 lib/base 留 __pycache__
ENTRY = Path(__file__).resolve().parents[1] / "_entry"
sys.path.insert(0, str(ENTRY.parents[1]))           # lib/base：file_walk
sys.path.insert(1, str(ENTRY.parents[2]))           # lib：tool_io
import file_walk  # noqa: E402


class GrepTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ws, self.out = self.root / "ws", self.root / "out"
        self.ws.mkdir()
        self.out.mkdir()
        self.env = dict(os.environ, AOS_WS=str(self.ws))

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, rel, text):
        p = self.ws / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(text, bytes):
            p.write_bytes(text)
        else:
            p.write_text(text)
        return p

    def call(self, env=None, **args):
        r = subprocess.run([str(ENTRY)], input=json.dumps(args).encode(), capture_output=True, env=env or self.env)
        return r.returncode, r.stdout.decode("utf-8"), r.stderr.decode("utf-8")

    def ok(self, **args):
        code, out, err = self.call(**args)
        self.assertEqual(code, 0, out + err)
        return out.splitlines()

    def test_regex_fixed_and_case(self):
        self.put("a.txt", "one\nTwo 2\nthree a.c\n")
        self.put("b/c.txt", "two\n")
        self.assertEqual(self.ok(pattern=r"[Tt]wo \d"), ["a.txt:2:Two 2"])
        self.assertEqual(self.ok(pattern="a.c", fixed=True), ["a.txt:3:three a.c"])
        self.assertEqual(self.ok(pattern="two"), ["b/c.txt:1:two"])
        self.assertEqual(self.ok(pattern="two", ignore_case=True), ["a.txt:2:Two 2", "b/c.txt:1:two"])
        self.assertEqual(self.ok(pattern="nothing"), ["... no matches"])

    def test_context_and_groups(self):
        self.put("a.txt", "".join("l%d\n" % i for i in range(1, 11)).replace("l2\n", "hit\n").replace("l9\n", "hit\n"))
        self.put("b.txt", "hit\n")
        self.assertEqual(self.ok(pattern="hit", context=1),
                         ["a.txt-1-l1", "a.txt:2:hit", "a.txt-3-l3", "--", "a.txt-8-l8", "a.txt:9:hit", "a.txt-10-l10",
                          "--", "b.txt:1:hit"])
        self.assertEqual(self.ok(pattern="hit", context=4)[:9], ["a.txt-1-l1", "a.txt:2:hit"] + ["a.txt-%d-l%d" % (i, i) for i in range(3, 9)] + ["a.txt:9:hit"])
        code, out, _ = self.call(pattern="hit", context=6)
        self.assertEqual((code, out), (1, "grep: error: ArgumentsBad context must be an integer from 0 to 5\n"))

    def test_files_mode_and_paging(self):
        for i in range(5):
            self.put("f%d.txt" % i, "x\n" * (i + 1))
        self.assertEqual(self.ok(pattern="x", files=True, max_matches=2),
                         ["f0.txt\t1", "f1.txt\t2", "... next_offset 2 (5 files in all)"])
        self.assertEqual(self.ok(pattern="x", files=True, offset=4), ["f4.txt\t5"])
        self.assertEqual(self.ok(pattern="x", max_matches=2), ["f0.txt:1:x", "f1.txt:1:x", "... next_offset 2 (15 matches in 5 files in all)"])
        self.assertEqual(self.ok(pattern="x", offset=2, max_matches=2), ["f1.txt:2:x", "f2.txt:1:x", "... next_offset 4 (15 matches in 5 files in all)"])
        self.assertEqual(self.ok(pattern="x", offset=99), ["... no matches from offset 99 (15 matches in 5 files in all)"])

    def test_skips_binary_big_and_non_utf8(self):
        self.put("bin.dat", b"needle\0rest")
        big = self.put("big.txt", "needle\n")
        with open(big, "r+b") as f:
            f.truncate(9 * 1024 * 1024)                # sparse：不佔空間
        self.put("latin.txt", b"caf\xe9 needle\r\n")
        self.assertEqual(self.ok(pattern="needle"),
                         ["latin.txt:1:caf� needle", "... skipped 1 binary file, 1 file over 8MB"])
        self.assertEqual(self.ok(pattern="needle$"), ["latin.txt:1:caf� needle", "... skipped 1 binary file, 1 file over 8MB"])
        self.assertEqual(self.ok(pattern="needle", path="bin.dat"), ["... no matches", "... skipped 1 binary file"])

    def test_long_line_cut(self):
        self.put("long.txt", "needle" + "x" * 400 + "\n")
        line, = self.ok(pattern="needle")
        self.assertEqual(line, "long.txt:1:" + ("needle" + "x" * 400)[:300] + "…[cut]")

    def test_hidden_and_folder_links(self):
        self.put(".secret", "needle\n")
        self.put(".dot/in.txt", "needle\n")
        self.put("d/a.txt", "needle\n")
        os.symlink(self.ws / "d", self.ws / "d" / "loop")           # 指回自己的環
        os.symlink(self.ws / "d", self.ws / "dlink")
        os.symlink(self.ws / "d" / "a.txt", self.ws / "flink")
        os.symlink(self.ws / "gone", self.ws / "broken")
        self.assertEqual(self.ok(pattern="needle"), ["d/a.txt:1:needle", "flink:1:needle"])
        self.assertEqual(self.ok(pattern="needle", hidden=True),
                         [".dot/in.txt:1:needle", ".secret:1:needle", "d/a.txt:1:needle", "flink:1:needle"])
        self.assertEqual(self.ok(pattern="needle", path="dlink"), ["dlink/a.txt:1:needle"])   # path 本身是捷徑＝跟過去
        self.assertEqual(self.ok(pattern="needle", glob=".dot/*"), [".dot/in.txt:1:needle"])  # 明寫 . 段＝明指

    def test_glob_filter(self):
        self.put("a.py", "needle\n")
        self.put("src/b.py", "needle\n")
        self.put("src/c.json", "needle\n")
        self.assertEqual(self.ok(pattern="needle", glob="*.py"), ["a.py:1:needle", "src/b.py:1:needle"])
        self.assertEqual(self.ok(pattern="needle", glob="src/**/*.json"), ["src/c.json:1:needle"])
        code, out, _ = self.call(pattern="x", glob="[ab")
        self.assertEqual((code, out), (1, "grep: error: PatternBad glob: unclosed [ in '[ab'\n"))

    def test_pattern_bad_and_missing(self):
        code, out, err = self.call(pattern="(a")
        self.assertEqual(code, 1)
        self.assertTrue(out.startswith("grep: error: PatternBad missing ), unterminated subpattern"), out)
        self.assertIn('"fixed": true', out)
        self.assertEqual(out, err)
        self.assertEqual(self.call(pattern="x", path="nope")[:2], (1, "grep: error: FileMissing nope\n"))
        self.assertEqual(self.call(path="a")[:2], (1, "grep: error: ArgumentsBad missing pattern (required)\n"))

    def test_single_file_and_outside(self):
        self.put(".hidden.txt", "needle\n")
        self.assertEqual(self.ok(pattern="needle", path=".hidden.txt"), [".hidden.txt:1:needle"])
        (self.out / "o.txt").write_text("a\nneedle\n")
        self.assertEqual(self.ok(pattern="needle", path=str(self.out)), ["%s:2:needle" % (self.out / "o.txt")])
        self.assertEqual(self.ok(pattern="needle", path="../out/o.txt"), ["%s:2:needle" % (self.out / "o.txt")])

    def git(self, *a):
        subprocess.run(["git", "-C", str(self.ws)] + list(a), check=True, capture_output=True)

    @unittest.skipUnless(shutil.which("git"), "needs git")
    def test_gitignore(self):
        self.git("init", "-q")
        self.put(".gitignore", "build/\n*.log\n")
        self.put("src/a.txt", "needle\n")
        self.put("build/out.txt", "needle\n")
        self.put("x.log", "needle\n")
        self.put("tracked.log", "needle\n")
        self.git("add", "-f", "tracked.log")             # 已追蹤的不算被擋
        self.assertEqual(self.ok(pattern="needle"), ["src/a.txt:1:needle", "tracked.log:1:needle"])
        self.assertEqual(self.ok(pattern="needle", gitignore=False),
                         ["build/out.txt:1:needle", "src/a.txt:1:needle", "tracked.log:1:needle", "x.log:1:needle"])
        self.assertEqual(self.ok(pattern="needle", path="src"), ["src/a.txt:1:needle"])     # 從子資料夾起也照擋
        self.assertEqual(self.ok(pattern="needle", hidden=True), ["src/a.txt:1:needle", "tracked.log:1:needle"])  # .git 不搜
        bare = self.root / "bin"                          # PATH 裡只有 python3、沒有 git
        bare.mkdir()
        os.symlink(sys.executable, bare / "python3")
        code, out, err = self.call(env=dict(self.env, PATH=str(bare)), pattern="needle")
        self.assertEqual(code, 0, err)
        self.assertEqual(err, "grep: warning: git is not on PATH; .gitignore is not applied\n")
        self.assertIn("build/out.txt:1:needle", out)

    def test_not_in_git(self):
        self.put("build/out.txt", "needle\n")
        self.put(".gitignore", "build/\n")              # 不在 git 工作樹裡＝不擋、不出聲
        code, out, err = self.call(pattern="needle")
        self.assertEqual((code, out, err), (0, "build/out.txt:1:needle\n", ""))

    def test_budget(self):
        for i in range(10):
            self.put("f%02d.txt" % i, "needle\n")
        walk = file_walk.Walk(str(self.ws), max_entries=3)
        self.assertEqual([r for r, _, _ in walk], ["f00.txt", "f01.txt", "f02.txt"])
        self.assertEqual(walk.stopped, "3 entries")
        self.assertEqual(list(file_walk.Walk(str(self.ws), max_seconds=0)), [])
        out = io.StringIO()
        with mock.patch.object(file_walk, "MAX_ENTRIES", 4), mock.patch.dict(os.environ, AOS_WS=str(self.ws)), \
                mock.patch.object(sys, "argv", [str(ENTRY)]), mock.patch.object(sys, "stdin", io.StringIO('{"pattern": "needle", "max_matches": 2}')), \
                contextlib.redirect_stdout(out):
            runpy.run_path(str(ENTRY), run_name="__main__")
        self.assertEqual(out.getvalue().splitlines(),
                         ["f00.txt:1:needle", "f01.txt:1:needle", "... next_offset 2 (at least 4 matches in 4 files)",
                          "... stopped after 4 entries (scan budget); narrow path or glob"])


if __name__ == "__main__":
    unittest.main()
