"""aos-daemon 的本體：一個 dict、七個動作。直接叫 `Daemon` 的方法，不開 daemon 進程。

真的會開 aos-run 子進程（value 就是它），所以每條測試最後把表清乾淨。
"""
import os
import time

from _util import ExecCase
import aos_daemon
from aos_home import Home

FAST = {"argv": ["sh", "-c", "exit 3"]}         # 一下就跑完，退出碼 3
SLOW = {"argv": ["sh", "-c", "sleep 1"]}        # 跑一秒，拿來測「跑完手上那次」
MS100 = ["--interval-ms", "100"]


def wait_until(cond, secs=5.0):
    t0 = time.monotonic()
    while time.monotonic() - t0 < secs:
        if cond():
            return True
        time.sleep(0.02)
    return cond()


class DaemonTest(ExecCase):
    def setUp(self):
        super().setUp()
        self.home = Home(os.path.join(self.d, "home"))
        self.dmn = aos_daemon.Daemon(self.home)
        self.addCleanup(self.clear)

    def clear(self):
        for key in list(self.dmn.table):
            self.dmn.remove(key, force=True)

    def work(self, obj=FAST, rel="work"):
        """做一個資料夾當目標，回它的路徑。"""
        self.inst(obj, os.path.join(rel, ".aos", "inst.json"))
        return os.path.join(self.d, rel)

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
        self.assertEqual(self.dmn.table[os.path.realpath(w)].proc.pid, res["pid"])   # 舊的不動

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
        self.assertEqual(sorted(one), ["alive", "args", "last_exit", "last_line", "paused",
                                       "pid", "runs", "started_at", "target"])
        self.assertEqual((one["args"], one["paused"], one["alive"]), (MS100, False, True))
        self.assertTrue(one["started_at"] > 0)
        ok, table = self.dmn.ls()                       # ls＝全部的 get，key 是資料夾
        self.assertTrue(ok)
        self.assertEqual(list(table), [key])
        self.assertEqual(table[key]["pid"], one["pid"])
        self.assertEqual(self.dmn.get(os.path.join(self.d, "nope"))[0], False)

    def test_stderr_gives_runs_and_last_exit(self):
        w = self.work(FAST)                                 # 每次都 exit 3、100 ms 一次
        self.dmn.add(w, MS100)
        r = self.dmn.table[os.path.realpath(w)]
        self.assertTrue(wait_until(lambda: r.runs >= 2))
        self.assertEqual(r.last_exit, 3)
        self.assertRegex(r.last_line, r"^aos-run: #\d+ exit=3 ")
        self.assertIn("%s aos-run: #1 exit=3" % os.path.realpath(w), self.log())

    # ── 暫停／繼續 ───────────────────────────────────────

    def test_pause_freezes_runs_and_resume_thaws(self):
        w = self.work(FAST)
        self.dmn.add(w, MS100)
        r = self.dmn.table[os.path.realpath(w)]
        self.assertTrue(wait_until(lambda: r.runs >= 1))
        ok, e = self.dmn.pause(w)
        self.assertTrue(ok)
        self.assertTrue(e["paused"])
        time.sleep(0.2)                     # 讓還在管子裡的那幾行讀完
        stuck = r.runs
        time.sleep(0.6)
        self.assertEqual(r.runs, stuck)                             # 暫停中不會多跑
        self.assertTrue(self.dmn.resume(w)[0])
        self.assertFalse(self.dmn.table[os.path.realpath(w)].paused)
        self.assertTrue(wait_until(lambda: r.runs > stuck))         # 又動起來了
        self.assertEqual(self.dmn.pause(os.path.join(self.d, "nope"))[0], False)

    # ── 刪 ─────────────────────────────────────────────

    def test_remove_waits_for_the_current_run(self):
        w = self.work(SLOW)
        self.dmn.add(w, MS100)
        time.sleep(0.3)                                     # 正在跑第一次（睡 1 秒）
        t0 = time.monotonic()
        ok, res = self.dmn.remove(w)
        self.assertTrue(ok)
        self.assertEqual(res["exit"], 0)                    # 第一次 SIGTERM＝乾淨地退
        self.assertEqual(res["last_line"], "aos-run: stop signal")
        self.assertGreater(time.monotonic() - t0, 0.3)      # 真的等它跑完手上那次
        self.assertEqual(self.dmn.table, {})
        self.assertEqual(self.dmn.remove(w)[0], False)      # 已經不在表上

    def test_remove_force_cuts_the_current_run(self):
        w = self.work(SLOW)
        self.dmn.add(w, MS100)
        time.sleep(0.3)
        ok, res = self.dmn.remove(w, force=True)
        self.assertTrue(ok)
        self.assertEqual(res["exit"], 143)                  # 第二次 SIGTERM＝腰斬，128+15
        self.assertEqual(res["last_line"], "aos-run: stop signal_forced")

    def test_remove_a_paused_one_wakes_it_first(self):
        w = self.work(FAST)
        self.dmn.add(w, MS100)
        r = self.dmn.table[os.path.realpath(w)]
        self.assertTrue(wait_until(lambda: r.runs >= 1))     # 等它裝好訊號處理器再暫停
        self.assertTrue(self.dmn.pause(w)[0])
        ok, res = self.dmn.remove(w)                        # 沒先 SIGCONT 的話會卡到 5 秒
        self.assertTrue(ok)
        self.assertEqual(res["exit"], 0)
        self.assertEqual(self.dmn.table, {})

    # ── 自己退了、改 ──────────────────────────────────────

    def test_self_exit_is_reaped_and_logged(self):
        w = self.work(FAST)
        ok, res = self.dmn.add(w, MS100 + ["--max-runs", "2"])
        self.assertTrue(ok)
        key = os.path.realpath(w)
        self.assertTrue(wait_until(lambda: self.dmn.reap() or key not in self.dmn.table))
        self.assertEqual(self.dmn.table, {})                        # 表上消失
        self.assertIn("自己退了 %s pid=%d exit=0 last=aos-run: stop max_runs"
                      % (key, res["pid"]), self.log())
        self.assertTrue(self.dmn.add(w, MS100)[0])                  # 同一個資料夾可以再 add

    def test_restart_swaps_the_process(self):
        w = self.work(FAST)
        old = self.dmn.add(w, MS100)[1]
        ok, new = self.dmn.restart(w, ["--interval-ms", "300"])
        self.assertTrue(ok)
        self.assertNotEqual(new["pid"], old["pid"])
        self.assertEqual(new["args"], ["--interval-ms", "300"])
        self.assertEqual(list(self.dmn.table), [os.path.realpath(w)])    # 表上只有一筆
        self.assertEqual(self.dmn.restart(os.path.join(self.d, "nope"))[0], False)

    # ── 請求 ───────────────────────────────────────────

    def test_dispatch_rejects_unknown_op_and_missing_fields(self):
        self.assertEqual(self.dmn.dispatch({"op": "nope"}), (False, "不認得的 op：'nope'"))
        self.assertEqual(self.dmn.dispatch({}), (False, "不認得的 op：None"))
        self.assertEqual(self.dmn.dispatch({"op": "add"})[0], False)        # 缺 target
        self.assertEqual(self.dmn.dispatch({"op": "get"})[0], False)        # 缺 dir
        self.assertEqual(self.dmn.dispatch([1, 2])[0], False)
        self.assertEqual(self.dmn.dispatch({"op": "ls"}), (True, {}))
