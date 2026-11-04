"""aos-daemon 的動作：暫停／繼續、刪、自己退了、restart、請求那一層——從 `test_daemon.py`
拆出來的（那一支超過 300 行了），基底 `DaemonTest` 在 `_daemon.py`。

寫法一樣：下指令是**立刻回**的，所以都是「下指令 → 一直 tick 到看見結果」。
（`_util.py` 的坑：TestCase 裡別放叫 `run()` 的方法，那是 unittest 自己的。）
"""
import os
import time
import unittest

from _daemon import FAST, HALF, MS100, MS300, SLOW, DaemonTest


class DaemonOpsTest(DaemonTest):

    def test_pause_waits_until_it_is_asleep(self):
        """inst 跑 0.5 秒：pause 先是 pause_pending，等它 done 了才 SIGSTOP＝paused。"""
        w = self.work(HALF)
        self.dmn.add(w, MS300)
        r = self.entry(w)
        self.assertTrue(self.pump(lambda: r.running))       # 正在跑那 0.5 秒
        ok, res = self.dmn.pause(w)
        self.assertEqual((ok, res), (True, "pause_pending"))
        self.assertEqual(r.state, "pause_pending")          # 立刻回，還沒真的停
        self.assertTrue(self.pump(lambda: r.state == "paused"))
        self.assertFalse(r.running)                         # 停在睡覺的時候，不腰斬
        self.assertEqual(self.dmn.pause(w), (True, "paused"))       # 再 pause＝冪等

    def test_paused_freezes_runs_and_resume_thaws(self):
        w = self.work(FAST)
        self.dmn.add(w, MS100)
        r = self.entry(w)
        self.assertTrue(self.pump(lambda: r.runs >= 1))
        self.assertTrue(self.dmn.pause(w)[0])
        self.assertTrue(self.pump(lambda: r.state == "paused"))
        stuck = r.runs
        time.sleep(0.6)
        self.dmn.tick()
        self.assertEqual(r.runs, stuck)                             # 暫停中不會多跑
        self.assertEqual(self.dmn.resume(w), (True, "running"))
        self.assertTrue(self.pump(lambda: r.runs > stuck))          # 又動起來了
        self.assertEqual(self.dmn.pause(os.path.join(self.d, "nope"))[0], False)

    def test_resume_cancels_a_pending_pause(self):
        w = self.work(SLOW)
        self.dmn.add(w, MS100)
        r = self.entry(w)
        self.assertTrue(self.pump(lambda: r.running))
        self.dmn.pause(w)
        self.assertEqual(r.state, "pause_pending")
        self.assertEqual(self.dmn.resume(w), (True, "running"))     # 還沒睡著就取消了
        self.dmn.tick()
        self.assertEqual(r.state, "running")

    # ── 刪 ─────────────────────────────────────────────

    def test_rm_returns_at_once_and_the_row_goes_away(self):
        """rm 立刻回 stopping，主迴圈幾圈之後才真的收屍（那次跑完＝退出碼 0）。"""
        w = self.work(SLOW)
        self.dmn.add(w, MS100)
        key = os.path.realpath(w)
        self.assertTrue(self.pump(lambda: self.entry(w).running))
        r = self.entry(w)
        t0 = time.monotonic()
        self.assertEqual(self.dmn.remove(w), (True, "stopping"))
        self.assertLess(time.monotonic() - t0, 0.3)         # 沒有在那裡等它退
        self.assertEqual(r.state, "stopping")
        self.assertTrue(self.pump(lambda: key not in self.dmn.table))
        self.assertEqual(r.code(), 0)                       # 第一次 SIGTERM＝乾淨地退
        self.assertEqual(r.last_line, "stop signal")
        self.assertIn("rm 掉了 %s" % key, self.log())
        self.assertEqual(self.dmn.remove(w)[0], False)      # 已經不在表上

    def test_rm_force_cuts_the_current_run(self):
        w = self.work(SLOW)
        self.dmn.add(w, MS100)
        key = os.path.realpath(w)
        self.assertTrue(self.pump(lambda: self.entry(w).running))
        r = self.entry(w)
        self.assertEqual(self.dmn.remove(w, force=True), (True, "stopping"))
        self.assertTrue(self.pump(lambda: key not in self.dmn.table))
        self.assertEqual(r.code(), 143)                     # 第二發 SIGTERM＝腰斬，128+15
        self.assertEqual(r.last_line, "stop signal_forced")

    def test_rm_a_paused_one_wakes_it_first(self):
        w = self.work(FAST)
        self.dmn.add(w, MS100)
        key = os.path.realpath(w)
        r = self.entry(w)
        self.assertTrue(self.pump(lambda: r.ready))         # 等它裝好訊號處理器再暫停
        self.assertTrue(self.dmn.pause(w)[0])
        self.assertTrue(self.pump(lambda: r.state == "paused"))
        self.assertEqual(self.dmn.remove(w), (True, "stopping"))    # 沒 SIGCONT 就收不到
        self.assertTrue(self.pump(lambda: key not in self.dmn.table, 5.0))
        self.assertEqual(r.code(), 0)

    def test_rm_again_while_stopping_is_idempotent(self):
        w = self.work(SLOW)
        self.dmn.add(w, MS100)
        self.assertEqual(self.dmn.remove(w), (True, "stopping"))
        self.assertEqual(self.dmn.remove(w), (True, "stopping"))
        self.assertTrue(self.pump(lambda: not self.dmn.table))

    def test_the_loop_stays_fast_while_something_is_stopping(self):
        """證明主迴圈不卡：rm 一個手上那次要跑一秒的，每一圈還是 0.3 秒以內。"""
        w = self.work(SLOW)
        self.dmn.add(w, MS100)
        self.assertTrue(self.pump(lambda: self.entry(w).running))
        self.dmn.remove(w)
        for _ in range(5):
            t0 = time.monotonic()
            self.dmn.tick()
            self.assertLess(time.monotonic() - t0, 0.3)
            time.sleep(0.05)

    # ── 自己退了、改 ──────────────────────────────────────

    def test_self_exit_is_reaped_and_logged(self):
        w = self.work(FAST)
        ok, res = self.dmn.add(w, MS100 + ["--max-runs", "2"])
        self.assertTrue(ok)
        key = os.path.realpath(w)
        self.assertTrue(self.pump(lambda: key not in self.dmn.table))
        self.assertEqual(self.dmn.table, {})                        # 表上消失
        self.assertIn("自己退了 %s pid=%d exit=0 last=stop max_runs"
                      % (key, res["pid"]), self.log())
        self.assertTrue(self.dmn.add(w, MS100)[0])                  # 同一份 .json 可以再 add

    def test_restart_swaps_the_process_without_leaving_the_table(self):
        w = self.work(FAST)
        old = self.dmn.add(w, MS100)[1]
        key = os.path.realpath(w)
        self.assertEqual(self.dmn.restart(w, MS300), (True, "restarting"))
        self.assertEqual(self.dmn.table[key].state, "restarting")   # 空窗期也還在表上
        self.assertTrue(self.pump(lambda: key in self.dmn.table
                                  and self.dmn.table[key].proc.pid != old["pid"]))
        new = self.dmn.table[key]
        self.assertEqual(new.state, "running")
        self.assertEqual(new.args, MS300)                           # 用新旗標開的
        self.assertEqual(list(self.dmn.table), [key])               # 表上只有一筆
        self.assertEqual(self.dmn.restart(os.path.join(self.d, "nope"))[0], False)

    def test_restart_returns_at_once_and_the_loop_stays_fast(self):
        """restart 也不卡：手上那次要跑一秒，指令立刻回，主迴圈每圈照樣很快。"""
        w = self.work(SLOW)
        self.dmn.add(w, MS100)
        key = os.path.realpath(w)
        self.assertTrue(self.pump(lambda: self.entry(w).running))
        old = self.entry(w).proc.pid
        t0 = time.monotonic()
        self.assertEqual(self.dmn.restart(w, MS300), (True, "restarting"))
        self.assertLess(time.monotonic() - t0, 0.3)             # 沒有在那裡等舊的退
        for _ in range(3):
            t1 = time.monotonic()
            self.dmn.tick()
            self.assertLess(time.monotonic() - t1, 0.3)
            time.sleep(0.05)
        self.assertTrue(self.pump(lambda: self.dmn.table[key].proc.pid != old))
        self.assertEqual(self.dmn.table[key].args, MS300)

    def test_restart_only_takes_json_targets(self):
        w = self.work(FAST)
        self.dmn.add(w, MS100)
        ok, res = self.dmn.restart(os.path.dirname(w), MS300)   # 資料夾＝拒絕
        self.assertEqual((ok, "只收 .json" in res), (False, True), res)
        self.assertEqual(self.entry(w).state, "running")        # 舊的不動

    # ── 請求 ───────────────────────────────────────────

    def test_dispatch_rejects_unknown_op_and_missing_fields(self):
        self.assertEqual(self.dmn.dispatch({"op": "nope"}), (False, "不認得的 op：'nope'"))
        self.assertEqual(self.dmn.dispatch({}), (False, "不認得的 op：None"))
        self.assertEqual(self.dmn.dispatch({"op": "add"})[0], False)        # 缺 target
        self.assertEqual(self.dmn.dispatch({"op": "get"})[0], False)        # 缺 target
        self.assertEqual(self.dmn.dispatch([1, 2])[0], False)
        self.assertEqual(self.dmn.dispatch({"op": "ls"}), (True, {}))

    def test_every_op_takes_the_target_field(self):
        """七個動作的目標欄位一律叫 `target`，值是那份 inst.json 的路徑（§15）。"""
        w = self.work(FAST)
        self.assertTrue(self.dmn.dispatch({"op": "add", "target": w, "args": MS100})[0])
        for op in ("get", "pause", "resume"):
            self.assertTrue(self.dmn.dispatch({"op": op, "target": w})[0], op)
            self.assertEqual(self.dmn.dispatch({"op": op, "dir": w})[0], False, op)
        self.assertTrue(self.dmn.dispatch({"op": "remove", "target": w})[0])
        self.assertTrue(self.pump(lambda: not self.dmn.table))


if __name__ == "__main__":
    unittest.main()
