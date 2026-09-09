"""aos-run：連續執行、兩種間隔算法、四種停止條件、訊號、用法錯。

時間相關的界都放得很鬆（開一個 python 進程本身就要一點時間），只驗「差得出來」的量級。
**注意**：TestCase 裡不能有叫 `run()` 的方法，會蓋掉 `TestCase.run()`，結果 Ran 0 tests。
"""
import os
import re
import signal
import subprocess
import time
import unittest

from _util import PY, ROOT, ExecCase

RUN = os.path.join(ROOT, "aos-run")
SLEEP_INST = {"argv": ["sh", "-c", "sleep 0.3; echo x >> count.txt"]}
COUNTER = """n=$(cat n.txt 2>/dev/null || echo 0)
n=$((n+1))
echo $n > n.txt
[ "$n" -ge 3 ] && exit 7
exit 0
"""


def _reap(p):
    """測試收尾：還活著就砍掉，不留孤兒在機器上。"""
    if p.poll() is None:
        p.kill()
        p.wait()


class RunCase(ExecCase):
    """跟 ExecCase 一樣有一個暫存資料夾 self.d，只是開的是 aos-run。"""

    def start(self, *args):
        """開一個 aos-run 進程但不等它（要送訊號的測試用）。"""
        p = subprocess.Popen([PY, RUN] + [str(a) for a in args],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(_reap, p)
        return p

    def aos_run(self, *args, timeout=60):
        """開一個 aos-run 進程並等它跑完，回 CompletedProcess。"""
        return subprocess.run([PY, RUN] + [str(a) for a in args],
                              capture_output=True, text=True, timeout=timeout)

    def timed(self, *args, **kw):
        """跑完順便回花了幾秒。"""
        t0 = time.monotonic()
        r = self.aos_run(*args, **kw)
        return r, time.monotonic() - t0

    def logs(self, err):
        """stderr 裡「跑完一次」的那些行。"""
        return [l for l in err.splitlines() if l.startswith("aos-run: #")]


class TestMaxRuns(RunCase):

    def test_max_runs_runs_exactly_n_times(self):
        """--max-runs 3＝真的跑三次（每次往同一個檔 append 一行來數）。"""
        self.inst({"argv": ["sh", "-c", "echo x >> count.txt"]})
        r = self.aos_run(self.d, "--max-runs", 3, "--interval-ms", 50)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.read("count.txt"), "x\nx\nx\n")
        self.assertEqual(len(self.logs(r.stderr)), 3)
        self.assertIn("aos-run: stop max_runs", r.stderr)

    def test_log_line_format(self):
        """每跑完一次印 `aos-run: #<n> exit=<碼> <秒數>s`，秒數一位小數。"""
        self.inst({"argv": ["sh", "-c", "exit 3"]})
        r = self.aos_run(self.d, "--max-runs", 1)
        self.assertRegex(self.logs(r.stderr)[0], r"^aos-run: #1 exit=3 \d+\.\ds$")

    def test_dir_target_is_passed_through(self):
        """aos-exec 有的旗標 aos-run 都有：--dir-target 原樣傳給 run_target()。"""
        self.inst({"argv": ["sh", "-c", "echo x >> count.txt"]}, "other/place.json")
        r = self.aos_run(self.d, "--dir-target", "other/place.json",
                         "--max-runs", 2, "--interval-ms", 50)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.read("count.txt"), "x\nx\n")   # cwd 還是 xxx，不是 other/

    def test_timeout_ms_is_per_run(self):
        """--timeout-ms 是**每一次**的上限：兩次都被砍，然後照 max_runs 停。"""
        self.inst({"argv": ["sh", "-c", "sleep 10"]})
        r, sec = self.timed(self.d, "--timeout-ms", 300, "--max-runs", 2,
                            "--interval-ms", 50)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(len(self.logs(r.stderr)), 2)
        for line in self.logs(r.stderr):
            self.assertIn("exit=143", line)
        self.assertIn("aos-run: stop max_runs", r.stderr)
        self.assertLess(sec, 8)


class TestStopExit(RunCase):

    def test_stops_when_exit_code_matches(self):
        """第三次才回 7（用計數檔），--stop-exit 7 就在那一次停。"""
        self.inst({"argv": ["sh", "-c", COUNTER]})
        r = self.aos_run(self.d, "--stop-exit", 7, "--max-runs", 10, "--interval-ms", 50)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.read("n.txt"), "3\n")
        self.assertEqual(len(self.logs(r.stderr)), 3)
        self.assertIn("exit=7", self.logs(r.stderr)[2])
        self.assertIn("aos-run: stop stop_exit", r.stderr)

    def test_stop_exit_can_be_repeated(self):
        """--stop-exit 給很多次＝一組碼，中了任何一個就停。"""
        self.inst({"argv": ["sh", "-c", COUNTER]})
        r = self.aos_run(self.d, "--stop-exit", 5, "--stop-exit", 7,
                         "--max-runs", 10, "--interval-ms", 50)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(len(self.logs(r.stderr)), 3)
        self.assertIn("aos-run: stop stop_exit", r.stderr)

    def test_broken_inst_does_not_stop(self):
        """inst.json 壞掉＝run_target 回 1，**不停**，照 interval 一直試。"""
        self.inst("{ 這不是 JSON")
        r = self.aos_run(self.d, "--max-runs", 2, "--interval-ms", 50)
        self.assertEqual(r.returncode, 0)
        lines = self.logs(r.stderr)
        self.assertEqual(len(lines), 2)
        for line in lines:
            self.assertIn("exit=1", line)
        self.assertIn("aos-run: stop max_runs", r.stderr)


class TestInterval(RunCase):

    def test_interval_from_end_waits_the_full_gap(self):
        """預設從**結束**算：跑 0.3 睡 0.5，三次≥0.3+0.5+0.3+0.5+0.3。"""
        self.inst(SLEEP_INST)
        r, sec = self.timed(self.d, "--max-runs", 3, "--interval-ms", 500)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.read("count.txt"), "x\nx\nx\n")
        self.assertGreaterEqual(sec, 1.85)

    def test_interval_from_start_is_shorter(self):
        """--from-start 從**開始**算：三次≈0.5+0.5+0.3，比從結束算短一大截。"""
        self.inst(SLEEP_INST)
        r, sec = self.timed(self.d, "--max-runs", 3, "--interval-ms", 500, "--from-start")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.read("count.txt"), "x\nx\nx\n")
        self.assertGreaterEqual(sec, 1.25)
        self.assertLess(sec, 1.8)               # 從結束算的那條是 ≥1.85

    def test_from_start_overrun_starts_next_immediately(self):
        """--from-start 一次跑超過 interval：下一次立刻開始，也不補跑錯過的格。"""
        self.inst({"argv": ["sh", "-c", "sleep 0.4; echo x >> count.txt"]})
        r, sec = self.timed(self.d, "--max-runs", 3, "--interval-ms", 200, "--from-start")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.read("count.txt"), "x\nx\nx\n")   # 三次就是三次，沒補跑
        self.assertGreaterEqual(sec, 1.15)      # 3×0.4，中間沒有多睡
        self.assertLess(sec, 1.9)


class TestTimeLimit(RunCase):

    def test_time_limit_wakes_up_from_sleep(self):
        """睡覺中撞到整體時限＝醒來就退，不會把 5 秒的 interval 睡完。"""
        self.inst({"argv": ["true"]})
        r, sec = self.timed(self.d, "--interval-ms", 5000, "--time-limit-ms", 500)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(len(self.logs(r.stderr)), 1)
        self.assertIn("aos-run: stop time_limit", r.stderr)
        self.assertLess(sec, 3)

    def test_time_limit_kills_the_running_one(self):
        """硬時限：正在跑的那次被砍（timeout_ms 換成剩下的毫秒），碼是 143 或 137。"""
        self.inst({"argv": ["sh", "-c", "sleep 10"]})
        r, sec = self.timed(self.d, "--time-limit-ms", 500)
        self.assertEqual(r.returncode, 0)
        lines = self.logs(r.stderr)
        self.assertEqual(len(lines), 1)
        self.assertTrue("exit=143" in lines[0] or "exit=137" in lines[0], lines[0])
        self.assertIn("aos-run: stop time_limit", r.stderr)
        self.assertLess(sec, 6)


class TestSignals(RunCase):

    def test_sigterm_lets_the_current_run_finish(self):
        """第一次 SIGTERM＝跑完這次再退，退出碼 0，印 stop signal。"""
        self.inst({"argv": ["sh", "-c", "sleep 0.5; echo x >> count.txt"]})
        p = self.start(self.d, "--interval-ms", 50)
        time.sleep(0.2)                          # 讓它正在跑
        p.send_signal(signal.SIGTERM)
        _out, err = p.communicate(timeout=20)
        self.assertEqual(p.returncode, 0)
        self.assertIn("aos-run: stop signal", err)
        self.assertIn("exit=0", self.logs(err)[-1])          # 那次是好好跑完的
        self.assertTrue(self.read("count.txt").endswith("x\n"))

    def test_second_sigterm_kills_the_running_one(self):
        """第二次同一個訊號＝直接砍正在跑的（SIGKILL 整個 process group）。"""
        self.inst({"argv": ["sh", "-c", "sleep 10"]})
        p = self.start(self.d, "--interval-ms", 50)
        time.sleep(0.3)
        p.send_signal(signal.SIGTERM)
        time.sleep(0.3)
        p.send_signal(signal.SIGTERM)
        _out, err = p.communicate(timeout=20)
        self.assertEqual(p.returncode, 0)
        self.assertIn("exit=137", self.logs(err)[-1])
        self.assertIn("aos-run: stop signal", err)

    def test_sigint_while_sleeping_exits_at_once(self):
        """睡覺中收到訊號也叫得醒（小步睡），不用等 interval 睡完。"""
        self.inst({"argv": ["true"]})
        p = self.start(self.d, "--interval-ms", 5000)
        time.sleep(0.5)                          # 第一次早就跑完了，現在在睡
        t0 = time.monotonic()
        p.send_signal(signal.SIGINT)
        _out, err = p.communicate(timeout=20)
        self.assertEqual(p.returncode, 0)
        self.assertLess(time.monotonic() - t0, 2)
        self.assertIn("aos-run: stop signal", err)


class TestUsage(RunCase):

    def test_missing_xxx_is_2(self):
        r = self.aos_run(os.path.join(self.d, "nope"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("找不到", r.stderr)

    def test_no_args_is_2(self):
        self.assertEqual(self.aos_run().returncode, 2)

    def test_unknown_flag_is_2(self):
        self.assertEqual(self.aos_run(self.d, "--nope").returncode, 2)

    def test_negative_numbers_are_2(self):
        for flag in ("--interval-ms", "--time-limit-ms", "--max-runs",
                     "--timeout-ms", "--stop-exit"):
            with self.subTest(flag=flag):
                r = self.aos_run(self.d, flag, -1)
                self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
