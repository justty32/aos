"""aos-tick（時鐘，C-44、N-01；計畫 10-21 第 4 段）。只用標準庫：python3 -m unittest discover -s proto8/tests"""
import os, subprocess, tempfile, unittest
from pathlib import Path
import own_error  # noqa: E402
own_error.install()   # 錯誤一行的代號（照 10-23 命名統合）：檢查對得上原因開頭再拿掉；raw_stderr 留原樣

from aos_bins import ROOT, tool, path_with  # noqa: E402  四支 C++ 在 impls/<名>/bin/、aos-tick 在 proto8/bin/（10-23）
TICK = tool("aos-tick")   # 唯一還是 Python 的一支（proto8/bin）


def run(*args, cwd, **kw):
    e = {k: v for k, v in os.environ.items() if k not in ("AOS_WS", "AOS_ENTRY", "AOS_STACK")}
    e["PATH"] = path_with(e["PATH"])
    return subprocess.run(args, capture_output=True, text=True, env=e, cwd=cwd, **kw)


class T(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)
        self.addCleanup(self._t.cleanup)
        self.clock = self.tmp / "clock"

    def tick(self, *args):
        return run(TICK, *args, cwd=str(self.tmp))

    def one_line_err(self, r, code, head):
        # 10-23 命名統合起 aos-tick 也帶代號：原樣是「aos-tick: 代號 原因」（統合前不帶）
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout, "")
        self.assertEqual(r.raw_stderr.count("\n"), 1, r.raw_stderr)
        self.assertTrue(r.raw_stderr.startswith("aos-tick: %s %s" % (code, head)), r.raw_stderr)
        self.assertTrue(r.stderr.startswith("aos-tick: " + head), r.stderr)

    def test_first_writes_1_then_2(self):
        r = self.tick("clock")                      # 相對路徑從 cwd 算
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))
        self.assertEqual(self.clock.read_text(), "1\n")
        self.assertEqual(self.tick(str(self.clock)).returncode, 0)
        self.assertEqual(self.clock.read_text(), "2\n")
        self.assertEqual(os.listdir(self.tmp), ["clock"])     # 不留 .clock

    def test_no_trailing_newline_ok(self):
        self.clock.write_text("41")
        self.assertEqual(self.tick("clock").returncode, 0)
        self.assertEqual(self.clock.read_text(), "42\n")

    def test_written_by_rename_not_in_place(self):
        # N-05：先寫 .clock 再改名蓋過去——舊的 inode 被換掉，讀的人拿著舊檔也讀不到半份
        self.clock.write_text("7\n")
        before = self.clock.stat().st_ino
        self.assertEqual(self.tick("clock").returncode, 0)
        self.assertNotEqual(self.clock.stat().st_ino, before)
        self.assertEqual(self.clock.read_text(), "8\n")

    def test_bad_content_untouched(self):
        for bad in ["", "abc\n", "3\n\n", " 3\n", "-1\n", "٣\n", "3\r\n"]:
            self.clock.write_text(bad, encoding="utf-8", newline="")
            r = self.tick("clock")
            self.one_line_err(r, "ClockBad", "時鐘檔壞：")
            self.assertEqual(self.clock.read_bytes().decode("utf-8"), bad)   # read_text 的 newline 要 3.13，這台 3.12（10-22）
        self.assertEqual(os.listdir(self.tmp), ["clock"])

    def test_read_failed(self):
        self.clock.mkdir()                          # 是資料夾，讀不了
        self.one_line_err(self.tick("clock"), "ClockBad", "時鐘檔讀不到：")

    @unittest.skipIf(os.geteuid() == 0, "root 寫得進唯讀資料夾")
    def test_write_failed_untouched(self):
        d = self.tmp / "ro"
        d.mkdir()
        (d / "clock").write_text("5\n")
        d.chmod(0o500)
        self.addCleanup(d.chmod, 0o700)
        self.one_line_err(self.tick("ro/clock"), "WriteFailed", "時鐘檔寫不了：")
        self.assertEqual((d / "clock").read_text(), "5\n")
        self.assertEqual(os.listdir(d), ["clock"])

    def test_missing_dir_is_write_error(self):
        self.one_line_err(self.tick("nope/clock"), "WriteFailed", "時鐘檔寫不了：")
        self.assertFalse((self.tmp / "nope").exists())   # 不替人建資料夾

    def test_usage(self):
        for args, code in [((), "ArgumentsBad"), (("a", "b"), "ArgumentsBad"), (("--cfg", "x", "a"), "FlagUnknown"),
                           (("--x=1", "a"), "FlagUnknown")]:
            self.one_line_err(self.tick(*args), code, "usage: aos-tick [旗標] FILE（")
        self.assertEqual(os.listdir(self.tmp), [])

    def test_double_dash_and_hash_literal(self):
        # `--` 結束旗標，FILE 可以 - 開頭；# 照字面（時鐘檔不是設定檔，不切指標）
        self.assertEqual(self.tick("--", "-c").returncode, 0)
        self.assertEqual((self.tmp / "-c").read_text(), "1\n")
        self.assertEqual(self.tick("a#b").returncode, 0)
        self.assertEqual((self.tmp / "a#b").read_text(), "1\n")
        (self.tmp / "c.json").write_text('{"k": 3}')
        self.one_line_err(self.tick("c.json#/k"), "WriteFailed", "時鐘檔寫不了：")   # 當成資料夾 c.json# 底下的 k
        self.assertEqual((self.tmp / "c.json").read_text(), '{"k": 3}')

    def test_demo_tick_loop_5(self):
        # demo/tick：aos-loop 每次行程內跑一次內嵌單子 aos-tick $AOS_STACK/tick.txt（10-24 起直接寫在 exec，原 loop.json#/body），max 5
        r = run("aos-exec", str(ROOT / "demo" / "tick"), cwd=str(self.tmp), timeout=30)
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual((self.tmp / ".stack" / "tick.txt").read_text(), "5\n")


if __name__ == "__main__":
    unittest.main()
