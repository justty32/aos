"""aos-daemon 的本體：一個 dict、七個動作、狀態機。直接叫 `Daemon` 的方法，不開 daemon
進程——主迴圈那一圈（`tick()`）測試自己來，愛跑多快就多快。

七個動作**都是立刻回**（送個訊號、標個狀態），真的等它退／等它睡著是 `tick()` 的事，
所以這裡的寫法都是「下指令 → 一直 tick 到看見結果」。
真的會開 aos-run 子進程（value 就是它），所以每條測試最後 `shutdown()` 收乾淨。
"""
import os
import time

from _util import ExecCase
import aos_daemon
from aos_home import Home

FAST = {"argv": ["sh", "-c", "exit 3"]}         # 一下就跑完，退出碼 3
SLOW = {"argv": ["sh", "-c", "sleep 1"]}        # 跑一秒，拿來測「跑完手上那次」
HALF = {"argv": ["sh", "-c", "sleep 0.5"]}      # 跑 0.5 秒，拿來測 pause 等它睡著
MS100 = ["--interval-ms", "100"]
MS300 = ["--interval-ms", "300"]


class DaemonTest(ExecCase):
    def setUp(self):
        super().setUp()
        self.home = Home(os.path.join(self.d, "home"))
        self.dmn = aos_daemon.Daemon(self.home)
        self.addCleanup(self.dmn.shutdown)      # 收工：全部 SIGTERM／SIGKILL，不留孤兒

    def pump(self, cond, secs=8.0):
        """主迴圈的替身：一直 tick 到 cond 成立（或超時）。"""
        t0 = time.monotonic()
        while time.monotonic() - t0 < secs:
            self.dmn.tick()
            if cond():
                return True
            time.sleep(0.02)
        self.dmn.tick()
        return cond()

    def work(self, obj=FAST, rel="work"):
        """做一個資料夾當目標，回它的路徑。"""
        self.inst(obj, os.path.join(rel, ".aos", "inst.json"))
        return os.path.join(self.d, rel)

    def entry(self, w):
        return self.dmn.table[os.path.realpath(w)]

    def log(self):
        with open(self.home.logf, encoding="utf-8") as f:
            return f.read()

    # ── key ────────────────────────────────────────────

    def test_key_is_realpath_and_second_add_is_refused(self):
        w = self.work(SLOW)
        link = os.path.join(self.d, "link")
        os.symlink(w, link)
        ok, res = self.dmn.add(link, MS100)
        self.assertTrue(ok)
        self.assertEqual(list(self.dmn.table), [os.path.realpath(w)])
        self.assertEqual(res["target"], link)                    # target 留原樣，key 才 realpath

        for other in (os.path.join(self.d, "work", "..", "work"), w + "/", w):
            ok2, res2 = self.dmn.add(other, MS100)               # 同一個資料夾＝第二次拒絕
            self.assertFalse(ok2, other)
            self.assertIn("已經有一個在跑", res2)
        self.assertEqual(len(self.dmn.table), 1)
        self.assertEqual(self.entry(w).proc.pid, res["pid"])      # 舊的不動

    def test_json_target_key_is_its_folder(self):
        p = self.inst(SLOW, os.path.join("work", "my.json"))
        ok, _ = self.dmn.add(p, MS100)
        self.assertTrue(ok)
        self.assertEqual(list(self.dmn.table), [os.path.realpath(os.path.join(self.d, "work"))])

    def test_add_missing_target_is_refused(self):
        ok, res = self.dmn.add(os.path.join(self.d, "nope"))
        self.assertFalse(ok)
        self.assertIn("找不到", res)
        self.assertEqual(self.dmn.table, {})

    # ── 查 ─────────────────────────────────────────────

    def test_ls_and_get_fields(self):
        w = self.work(SLOW)
        self.dmn.add(w, MS100)
        key = os.path.realpath(w)
        ok, one = self.dmn.get(w)
        self.assertTrue(ok)
        self.assertEqual(sorted(one), ["alive", "args", "last_exit", "last_kind",
                                       "last_line", "pid", "ready", "running", "runs",
                                       "started_at", "state", "target"])
        self.assertEqual((one["args"], one["state"], one["alive"]), (MS100, "running", True))
        self.assertTrue(one["started_at"] > 0)
        ok, table = self.dmn.ls()                       # ls＝全部的 get，key 是資料夾
        self.assertTrue(ok)
        self.assertEqual(list(table), [key])
        self.assertEqual(table[key]["pid"], one["pid"])
        self.assertEqual(self.dmn.get(os.path.join(self.d, "nope"))[0], False)

    def test_ready_shows_up_quickly(self):
        """aos-run 裝好訊號處理器就會說 `ready`——pause 等的就是這個。"""
        w = self.work(FAST)
        self.dmn.add(w, MS300)
        r = self.entry(w)
        self.assertTrue(self.pump(lambda: r.ready, 5.0))

    def test_status_fd_gives_runs_and_last_exit_and_kind(self):
        w = self.work(FAST)                                 # 每次都 exit 3、100 ms 一次
        self.dmn.add(w, MS100)
        r = self.entry(w)
        self.assertTrue(self.pump(lambda: r.runs >= 2))
        self.assertEqual((r.last_exit, r.last_kind), (3, "child"))
        self.assertRegex(r.last_line, r"^done #\d+ exit=3 kind=child ")
        self.assertFalse(r.running)                         # done 之後就是在睡覺
        # stderr 照舊原樣進 daemon.log（前面加 key），只是不再從那裡解近況
        self.assertIn("%s aos-run: #1 exit=3" % os.path.realpath(w), self.log())

    # ── 暫停／繼續 ───────────────────────────────────────

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
        self.assertTrue(self.dmn.add(w, MS100)[0])                  # 同一個資料夾可以再 add

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

    # ── 請求 ───────────────────────────────────────────

    def test_dispatch_rejects_unknown_op_and_missing_fields(self):
        self.assertEqual(self.dmn.dispatch({"op": "nope"}), (False, "不認得的 op：'nope'"))
        self.assertEqual(self.dmn.dispatch({}), (False, "不認得的 op：None"))
        self.assertEqual(self.dmn.dispatch({"op": "add"})[0], False)        # 缺 target
        self.assertEqual(self.dmn.dispatch({"op": "get"})[0], False)        # 缺 dir
        self.assertEqual(self.dmn.dispatch([1, 2])[0], False)
        self.assertEqual(self.dmn.dispatch({"op": "ls"}), (True, {}))
