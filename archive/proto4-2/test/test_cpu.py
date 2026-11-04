"""一顆 cpu ＝ 一個 Linux process：反覆執行，三種停法（跑滿次數／SIGTERM／整體時限）。"""
import json
import os
import shutil
import signal
import subprocess
import time
import unittest

from _util import PY, CPU, alive, copy_fx, kill_hard, last, mkinst, mktmp, wait_until


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
        self.assertEqual(cpu["time_limit"], 0)              # 沒給＝不限
        self.assertEqual(cpu["stopped"], "max_runs")        # 退之前補的
        self.assertIsNotNone(cpu["ended_at"])

    def test_time_limit_exits_while_sleeping(self):
        """睡覺中時限到＝醒來直接退（interval 5 秒，但時限 0.6 秒）。"""
        t0 = time.time()
        p = subprocess.run([PY, CPU, self.d, "--interval", "5", "--time-limit", "0.6"],
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0)
        self.assertLess(time.time() - t0, 4.0)              # 沒等完那 5 秒
        self.assertEqual(count(self.d), 1)                  # 只跑得完第一次
        with open(os.path.join(self.d, ".aos", "cpu.json")) as f:
            cpu = json.load(f)
        self.assertEqual(cpu["stopped"], "time_limit")
        self.assertEqual(cpu["time_limit"], 0.6)
        self.assertIsNotNone(cpu["ended_at"])

    def test_time_limit_kills_the_run_in_progress(self):
        """硬時限：正在跑的那次直接當逾時砍掉，不等它跑完。"""
        d = mkinst(self.tmp, {"argv": ["sh", "-c", "sleep 30"]})
        t0 = time.time()
        p = subprocess.run([PY, CPU, d, "--interval", "0.1", "--time-limit", "1"],
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0)
        self.assertLess(time.time() - t0, 5.0)              # 沒等那 30 秒
        r = last(d)
        self.assertTrue(r["timed_out"])
        self.assertEqual(r["signal"], 15)                   # SIGTERM 砍中的
        with open(os.path.join(d, ".aos", "cpu.json")) as f:
            self.assertEqual(json.load(f)["stopped"], "time_limit")

    def test_sigterm_exits(self):
        self.p = subprocess.Popen([PY, CPU, self.d, "--interval", "0.2"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.assertTrue(wait_until(lambda: count(self.d) >= 2))     # 真的在反覆跑
        self.p.send_signal(signal.SIGTERM)
        self.assertEqual(self.p.wait(timeout=10), 0)                # 跑完這次就退，退出碼 0
        self.assertFalse(alive(self.p.pid))
        with open(os.path.join(self.d, ".aos", "cpu.json")) as f:
            self.assertEqual(json.load(f)["stopped"], "sigterm")


if __name__ == "__main__":
    unittest.main()
