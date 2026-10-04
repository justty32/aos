"""固定回歸矩陣（三）：SIGKILL 中斷點（once／keep 起任務的交接、A2-05 restart 冪等；spec 4.4、5.3、6 節，N-86、K-03、K-04）。

**AOS7_TEST_* 環境變數只給測試用**：`AOS7_TEST_CRASH=<點>` 讓 tick／tock 在那一點 SIGKILL 自己（子程序退出碼 -9），
`AOS7_TEST_RUNNER_CRASH=<點>` 由 tick 傳給 aos7-run、aos7-run 起任務前從任務環境拿掉。正常環境不設。

矩陣維度與判定：

1. **起任務被打斷** 模式 ∈ {once、keep} × 點 ∈ tick 的 {before-launch、after-launch、after-birth、after-popen、after-runner、
   before-once-delete、after-once-delete}、runner 的 {runner-before-pid、runner-before-exit}。恢復＝tock（被殺在 tick 時帶
   `AOS7_INCOMPLETE=tick`）再 tick／tock 四回合。
   - once（任務把 `$AOS7_RUN` 記到槽外）：執行次數 ≤ 1；除了 after-birth（P2-02：0 次、報一次 lost）都剛好 1 次；
     ended 裡這個 once 的結束只報一次（lost 或 code）；tasks.json 最後沒有這項。
   - keep（launch／刪 once 項那四點另放一個不相干的 once 項當伴，tick 才會走到）：每個檢查點（被殺後、每次 tick／tock 後）同槽活程序 ≤ 1（`env_procs(node, slot, runners=False)`）；恢復後剛好一個活的。
2. **restart 被打斷**（A2-05）點 ∈ {restart-after-append、restart-after-kill、ctl-after-done}（子程序 tock 被殺）× 任務 ∈
   - once（跑完的 once 寫 ctl.json restart）：恢復後執行紀錄剛好兩次（原本＋一次重起），tasks.json 任何時候都不會有兩個
     `restart_of` 的 once 項，最後沒有殘項；
   - keep（活著的 keep restart）：任何檢查點同槽活程序 ≤ 1；重起只發生一次（birth 的 run 只前進一次、執行紀錄兩次），
     新 birth 帶 `ctl_id`。
"""
import os, sys  # noqa: E401
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # tests/：base、_matrix
import os
import unittest

from _matrix import MatrixCase, env, gen, rec_argv
import aos7_task
from aos7_fs import write_json

TICK_POINTS = ("before-launch", "after-launch", "after-birth", "after-popen", "after-runner",
               "before-once-delete", "after-once-delete")
RUNNER_POINTS = ("runner-before-pid", "runner-before-exit")
ONCE_ONLY_POINTS = ("before-launch", "after-launch", "before-once-delete", "after-once-delete")
RESTART_POINTS = ("restart-after-append", "restart-after-kill", "ctl-after-done")


class TestLaunchCrash(MatrixCase):
    """〔core〕"""
    def interrupt_tick(self, point):
        """在 point 打斷第 1 回合的 tick（或 runner）；回恢復用的第一個 tock 要帶的環境。"""
        if point in RUNNER_POINTS:
            rc, _out, err = self.run_prog("aos7-tick", env={"AOS7_TEST_RUNNER_CRASH": point})
            self.assertEqual(rc, 0, err)
            return {}
        self.crash("aos7-tick", point)
        return {"AOS7_INCOMPLETE": "tick"}

    def _once(self, point):
        """once 任務的起動交接在 point 被 SIGKILL：不重起、不漏起（after-birth 例外：0 次、報一次 lost）。"""
        node = self.mknode("a", [{"name": "o", "mode": "once", "argv": rec_argv("o")}])
        extra = self.interrupt_tick(point)
        if point == "runner-before-exit":
            self.wait_for(lambda: self.ran(node, "o"), 5, "任務沒跑")
        sums = []
        with env(**extra):
            self.settle(node, "o")
            sums.append(self.itock())
        for _ in range(4):
            self.itick()
            self.settle(node, "o")
            sums.append(self.itock())
        n = len(self.ran(node, "o"))
        ends = self.ends_of(sums, "o")
        if point == "after-birth":
            self.assertEqual(n, 0, self.ran(node, "o"))
            self.assertEqual(ends, [{"run": "o#1", "code": None, "lost": True, "never_started": True}])
        else:
            self.assertEqual(n, 1, "once 在 %s 被打斷後執行了 %d 次：%r" % (point, n, self.ran(node, "o")))
            self.assertEqual(len(ends), 1, "once 的結束報了 %d 次：%r" % (len(ends), ends))
        self.assertEqual(self.tasks(node), [], "once 項沒刪掉")

    def _keep(self, point):
        """keep 任務的起動交接在 point 被 SIGKILL：任何檢查點同槽活程序 ≤ 1，恢復後剛好一個活的。"""
        items = [{"name": "k", "mode": "keep", "argv": rec_argv("k", keep=True, short_first=point == "runner-before-exit")}]
        if point in ONCE_ONLY_POINTS:
            # launch 標記與刪 once 項只在有 once 項時才走到：放一個不相干的 once 當伴（它排在 keep 前面起）
            items.append({"name": "c", "mode": "once", "argv": ["true"]})
        node = self.mknode("a", items)
        extra = self.interrupt_tick(point)
        self.assert_le_one(node, "k", "被殺後")
        with env(**extra):
            self.itock()
        self.assert_le_one(node, "k", "恢復 tock 後")
        for r in range(4):
            self.itick()
            self.assert_le_one(node, "k", "第 %d 次恢復 tick 後" % r)
            self.itock()
            self.assert_le_one(node, "k", "第 %d 次恢復 tock 後" % r)
        self.wait_for(lambda: len(self.live_procs(node, "k")) == 1, 5, "恢復後槽裡不是剛好一個活程序：%r" % self.live_procs(node, "k"))
        self.assertEqual(self.view(node, "k").state, aos7_task.LIVE)


gen(TestLaunchCrash, "once", [(p, (p,)) for p in TICK_POINTS + RUNNER_POINTS], TestLaunchCrash._once)
gen(TestLaunchCrash, "keep", [(p, (p,)) for p in TICK_POINTS + RUNNER_POINTS], TestLaunchCrash._keep)


class TestRestartCrash(MatrixCase):
    """〔control〕restart 在三個交接點被殺只重起一次（A2-05，F39）。"""
    def restart_items(self, node):
        return [i for i in self.tasks(node) or [] if isinstance(i, dict) and i.get("restart_of")]

    def assert_one_restart_item(self, node, when):
        items = self.restart_items(node)
        self.assertLessEqual(len(items), 1, "%s：tasks.json 同時有 %d 個 restart 的 once 項：%r" % (when, len(items), items))

    def _once(self, point):
        """跑完的 once 寫 restart，tock 在 point 被殺：恢復後只重起一次（執行紀錄兩次）。"""
        node = self.mknode("a", [{"name": "x", "mode": "once", "argv": rec_argv("x")}])
        self.itick()
        self.wait_ended(node, "x", 1)
        write_json(os.path.join(self.slot(node, "x"), "ctl.json"), {"op": "restart", "by": "matrix"})
        self.crash("aos7-tock", point)
        self.assert_one_restart_item(node, "tock 在 %s 被殺後" % point)
        self.itock()
        self.assert_one_restart_item(node, "恢復 tock 後")
        for r in range(3):
            self.itick()
            self.assert_one_restart_item(node, "第 %d 次恢復 tick 後" % r)
            self.settle(node, "x")
            self.itock()
            self.assert_one_restart_item(node, "第 %d 次恢復 tock 後" % r)
        self.assertEqual(len(self.ran(node, "x")), 2, "restart 在 %s 被打斷後執行紀錄：%r（要原本＋一次重起）"
                         % (point, self.ran(node, "x")))
        self.assertEqual(self.restart_items(node), [])

    def _keep(self, point):
        """活著的 keep 寫 restart，tock 在 point 被殺：不雙開、重起只發生一次、新 birth 帶 ctl_id。"""
        node = self.mknode("a", [{"name": "k", "mode": "keep", "argv": rec_argv("k", keep=True)}])
        self.itick()
        self.wait_pid(node, "k")
        self.itock()
        self.itick()                                   # 第 2 回合開著，k 還活著（run 1）
        self.assertEqual(self.birth(node, "k")["run"], 1)
        write_json(os.path.join(self.slot(node, "k"), "ctl.json"), {"op": "restart", "by": "matrix"})
        self.crash("aos7-tock", point)
        self.assert_le_one(node, "k", "tock 在 %s 被殺後" % point)
        self.assert_one_restart_item(node, "tock 在 %s 被殺後" % point)
        runs = {1}
        self.itock()
        self.assert_le_one(node, "k", "恢復 tock 後")
        for r in range(3):
            self.itick()
            self.assert_le_one(node, "k", "第 %d 次恢復 tick 後" % r)
            self.assert_one_restart_item(node, "第 %d 次恢復 tick 後" % r)
            runs.add(self.birth(node, "k").get("run"))
            self.itock()
            self.assert_le_one(node, "k", "第 %d 次恢復 tock 後" % r)
        self.wait_for(lambda: len(self.live_procs(node, "k")) == 1, 5, "恢復後槽裡不是剛好一個活程序")
        self.assertEqual(len(runs), 2, "birth 的 run 前進了 %d 次：%r" % (len(runs) - 1, sorted(runs)))
        self.assertEqual(len(self.ran(node, "k")), 2, self.ran(node, "k"))
        b = self.birth(node, "k")
        self.assertTrue(b.get("ctl_id"), "重起的 birth 沒帶 ctl_id：%r" % b)
        self.assertEqual(b.get("restart_of"), "k#1")
        self.assertEqual(self.restart_items(node), [])


gen(TestRestartCrash, "restart_once", [(p, (p,)) for p in RESTART_POINTS], TestRestartCrash._once)
gen(TestRestartCrash, "restart_keep", [(p, (p,)) for p in RESTART_POINTS], TestRestartCrash._keep)


if __name__ == "__main__":
    unittest.main()
