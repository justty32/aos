"""一顆 cpu ＝ 一個 Linux process：反覆執行、跑滿次數退出、收 SIGTERM 退出。"""
import json
import os
import shutil
import signal
import subprocess
import unittest

from _util import PY, CPU, alive, copy_fx, kill_hard, mktmp, wait_until


def count(d):
    try:
        with open(os.path.join(d, "count.txt")) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return 0


class CpuTest(unittest.TestCase):
    def setUp(self):
        self.tmp = mktmp("aos-proto4-2-cpu-")
        self.d = copy_fx("counter", self.tmp)
        self.p = None

    def tearDown(self):
        if self.p and self.p.poll() is None:
            kill_hard(self.p.pid)
            self.p.wait()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_max_runs_then_exit(self):
        p = subprocess.run([PY, CPU, self.d, "--interval", "0.05", "--max-runs", "3"],
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0)
        self.assertEqual(count(self.d), 3)
        with open(os.path.join(self.d, ".aos", "runs.jsonl")) as f:
            self.assertEqual(len([x for x in f if x.strip()]), 3)
        with open(os.path.join(self.d, ".aos", "cpu.json")) as f:
            cpu = json.load(f)
        self.assertEqual(cpu["tick"], 3)
        self.assertEqual(cpu["dir"], self.d)
        self.assertEqual(cpu["interval"], 0.05)

    def test_sigterm_exits(self):
        self.p = subprocess.Popen([PY, CPU, self.d, "--interval", "0.2"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.assertTrue(wait_until(lambda: count(self.d) >= 2))     # 真的在反覆跑
        self.p.send_signal(signal.SIGTERM)
        self.assertEqual(self.p.wait(timeout=10), 0)                # 跑完這次就退，退出碼 0
        self.assertFalse(alive(self.p.pid))


if __name__ == "__main__":
    unittest.main()
