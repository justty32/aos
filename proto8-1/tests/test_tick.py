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
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TICK = os.path.join(HERE, "bin", "aos-tick")
LOOP = os.path.join(HERE, "..", "proto8", "lib", "aos_loop.py")


class Tick(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="aos-test-")
        self.addCleanup(shutil.rmtree, self.tmp)
        self.file = os.path.join(self.tmp, "clock")

    def run_tick(self, *args):
        return subprocess.run([TICK] + list(args), capture_output=True, text=True, cwd=self.tmp)

    def err(self, r):
        """stderr 那份錯誤 JSON（N-12，同 aos_cli）的 code；要剛好一行。"""
        self.assertEqual(r.stderr.count("\n"), 1, r.stderr)
        return json.loads(r.stderr)["error"]["code"]

    def read(self):
        with open(self.file) as f:
            return f.read()

    def test_first_writes_1_then_2(self):
        r = self.run_tick("clock")                  # 相對路徑從 cwd 算
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))
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
            self.assertEqual(self.err(r), "ContentBad")
            self.assertEqual(self.read(), bad)
        self.assertEqual(os.listdir(self.tmp), ["clock"])

    def test_read_failed(self):
        os.mkdir(self.file)                         # 是資料夾，讀不了
        r = self.run_tick(self.file)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.err(r), "ReadFailed")

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
        self.assertEqual(self.err(r), "WriteFailed")
        with open(path) as f:
            self.assertEqual(f.read(), "5\n")

    def test_usage(self):
        for args in [(), ("a", "b")]:
            r = self.run_tick(*args)
            self.assertEqual(r.returncode, 1)
            self.assertEqual(self.err(r), "Usage")
        self.assertEqual(os.listdir(self.tmp), [])

    def test_loop_times_3(self):
        loop = os.path.join(self.tmp, "tick.loop.json")
        with open(loop, "w") as f:
            json.dump({"inst": {"argv": [TICK, self.file], "cwd": self.tmp, "exit": "tick.exit", "exit_append": True},
                       "times": 3, "interval_ms": 10, "ctl": "tick.ctl.json", "state": "tick.state.json"}, f)
        r = subprocess.run([sys.executable, LOOP, loop], cwd=self.tmp, timeout=10, stdout=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0)
        with open(os.path.join(self.tmp, "tick.exit")) as f:
            self.assertEqual(f.read(), "0\n0\n0\n")
        self.assertEqual(self.read(), "3\n")


if __name__ == "__main__":
    unittest.main()
