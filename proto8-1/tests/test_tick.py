"""proto8-1 的 aos-tick 測試。只用標準庫：

    python3 -m unittest discover -s proto8-1/tests

每個測試在 mkdtemp 建的暫存資料夾裡跑，跑完刪掉。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TICK = os.path.join(HERE, "bin", "aos-tick")
sys.path.insert(0, os.path.join(HERE, "..", "proto8", "lib"))

from aos_loop import Loop  # noqa: E402


class Tick(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="aos-test-")
        self.addCleanup(shutil.rmtree, self.tmp)
        self.file = os.path.join(self.tmp, "clock")

    def run_tick(self, *args):
        return subprocess.run([TICK] + list(args), capture_output=True, text=True, cwd=self.tmp)

    def read(self):
        with open(self.file) as f:
            return f.read()

    def test_first_writes_1_then_2(self):
        r = self.run_tick("clock")                  # 相對路徑從 cwd 算
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(self.read(), "1\n")
        self.assertEqual(self.run_tick(self.file).returncode, 0)
        self.assertEqual(self.read(), "2\n")
        self.assertEqual(os.listdir(self.tmp), ["clock"])     # 不留 .clock.tmp

    def test_no_trailing_newline_ok(self):
        with open(self.file, "w") as f:
            f.write("41")
        self.assertEqual(self.run_tick(self.file).returncode, 0)
        self.assertEqual(self.read(), "42\n")

    def test_bad_content_untouched(self):
        for bad in ["", "abc\n", "3\n\n", " 3\n", "-1\n", "٣\n"]:
            with open(self.file, "w") as f:
                f.write(bad)
            r = self.run_tick(self.file)
            self.assertEqual(r.returncode, 1, bad)
            self.assertTrue(r.stderr.startswith("BadContent: "), r.stderr)
            self.assertEqual(r.stderr.count("\n"), 1)
            self.assertEqual(self.read(), bad)
        self.assertEqual(os.listdir(self.tmp), ["clock"])

    def test_read_failed(self):
        os.mkdir(self.file)                         # 是資料夾，讀不了
        r = self.run_tick(self.file)
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("ReadFailed: "), r.stderr)

    @unittest.skipIf(os.geteuid() == 0, "root 寫得進唯讀資料夾")
    def test_write_failed(self):
        d = os.path.join(self.tmp, "ro")
        os.mkdir(d)
        path = os.path.join(d, "clock")
        with open(path, "w") as f:
            f.write("5\n")
        os.chmod(d, 0o500)
        self.addCleanup(os.chmod, d, 0o700)
        r = self.run_tick(path)
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("WriteFailed: "), r.stderr)
        with open(path) as f:
            self.assertEqual(f.read(), "5\n")

    def test_usage(self):
        for args in [(), ("a", "b")]:
            r = self.run_tick(*args)
            self.assertEqual(r.returncode, 1)
            self.assertTrue(r.stderr.startswith("Usage: "), r.stderr)
        self.assertEqual(os.listdir(self.tmp), [])

    def test_loop_times_3(self):
        d = os.path.join(self.tmp, "tick")
        os.mkdir(d)
        with open(os.path.join(d, "inst.json"), "w") as f:
            json.dump({"argv": [TICK, self.file], "cwd": self.tmp}, f)
        loop = Loop(stop_poll_ms=10)
        self.addCleanup(loop.shutdown)
        ident = loop.add(d, {"times": 3, "interval_ms": 10})
        end = time.monotonic() + 5
        while loop.get(ident)["state"] != "done":
            self.assertLess(time.monotonic(), end, "等不到")
            time.sleep(0.02)
        self.assertEqual(loop.get(ident)["last_code"], 0)
        self.assertEqual(self.read(), "3\n")


if __name__ == "__main__":
    unittest.main()
