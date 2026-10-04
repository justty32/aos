"""任務項目的選項（astra-2 之後加的）：P2-02 `retry_lost`（once 至少一次）與 `until_round`（使用者 10-04：回合數超過就不再起新 run）。

**AOS7_TEST_* 環境變數只給測試用**（這裡用 `AOS7_TEST_CRASH=after-birth`：tick 寫完 birth.json、起 runner 之前 SIGKILL）。

判定：

1. **P2-02** once 在 after-birth 被打斷（birth 沒 runner、沒 pid.json、沒 out.log）：
   - `retry_lost: true` → 判 lost 時加回 once 項、同槽新 run 起一次（槽外副作用剛好 1 次），ended 那筆有 `lost`＋`retried`，最後表上沒殘項；
   - 預設（false）→ 0 次、報一次 lost、沒有 retried；
   - 型別錯（字串、給 keep）→ 跳過該項、記 tasks_error，同表其他項照起。
2. **until_round** each 任務 until_round=2 → 第 3 回合起不再起；keep 在跑的 run 過了 until_round 不被殺、結束後不再起；
   型別錯（負數、字串、bool）→ 跳過該項記 tasks_error，同表其他項照起。
"""
import os, sys  # noqa: E401
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # tests/：base、_matrix
import os
import signal
import unittest

from _matrix import MatrixCase, alive, env, rec_argv


class TestRetryLost(MatrixCase):
    """〔once_retry〕retry_lost 選項（P2-02，F26）：移成 once 保證包。"""
    def lost_once(self, **opt):
        """once 項（帶 opt）在 after-birth 被打斷，之後恢復 tock＋四回合。回 (node, 各回合總結)。"""
        node = self.mknode("a", [dict({"name": "o", "mode": "once", "argv": rec_argv("o")}, **opt)])
        self.crash("aos7-tick", "after-birth")
        sums = []
        with env(AOS7_INCOMPLETE="tick"):
            sums.append(self.itock())
        for _ in range(4):
            self.itick()
            self.settle(node, "o")
            sums.append(self.itock())
        return node, sums

    def test_retry_lost_true_runs_once(self):
        """P2-02：retry_lost:true 的 once 從沒起來過 → 加回、同槽新 run 跑一次（副作用 1 次），ended 有 lost＋retried。"""
        node, sums = self.lost_once(retry_lost=True)
        self.wait_for(lambda: self.ran(node, "o"), 5, "加回的 once 沒跑")
        self.assertEqual(len(self.ran(node, "o")), 1, "retry_lost 的 once 執行了 %r" % self.ran(node, "o"))
        ends = self.ends_of(sums, "o")
        first = [e for e in ends if e["run"] == "o#1"]
        self.assertEqual(first, [{"run": "o#1", "code": None, "lost": True, "retried": True}], ends)
        again = [e for e in ends if e["run"] != "o#1"]
        self.assertEqual(len(again), 1, ends)
        self.assertEqual(again[0]["code"], 0, again)
        self.assertNotIn("lost", again[0])
        self.assertEqual(self.tasks(node), [], "加回的 once 項沒刪掉：%r" % self.tasks(node))

    def test_retry_lost_default_at_most_once(self):
        """P2-02：預設（不帶 retry_lost）維持最多一次：0 次、報一次 lost、沒有 retried。"""
        node, sums = self.lost_once()
        self.assertEqual(self.ran(node, "o"), [])
        self.assertEqual(self.ends_of(sums, "o"), [{"run": "o#1", "code": None, "lost": True}])
        self.assertEqual(self.tasks(node), [])

    def test_retry_lost_bad_type_skipped(self):
        """P2-02：retry_lost 型別錯（字串）或給 keep → 跳過該項、記 tasks_error；同表的好項照起。"""
        node = self.mknode("a", [{"name": "o", "mode": "once", "argv": ["true"], "retry_lost": "yes"},
                                 {"name": "k", "mode": "keep", "argv": ["true"], "retry_lost": True},
                                 {"name": "g", "mode": "once", "argv": ["true"], "retry_lost": False}])
        out = self.itick()
        self.assertEqual(out["started"], ["g#1"], out)
        errs = self.round_json(node).get("tasks_error") or []
        for n in ("o", "k"):
            self.assertTrue([e for e in errs if e.startswith(n + "：") and "retry_lost" in e], "%s 沒記 tasks_error：%r" % (n, errs))


class TestUntilRound(MatrixCase):
    """〔core〕"""
    def test_each_stops_after_until_round(self):
        """until_round：each 任務 until_round=2 → 第 1、2 回合起，第 3 回合起不再起；項目留在表上。"""
        node = self.mknode("a", [{"name": "e", "argv": rec_argv("e"), "until_round": 2}])
        started = []
        for _ in range(4):
            started += self.itick()["started"]
            self.settle(node, "e")
            self.itock()
        self.assertEqual(started, ["e#1", "e#2"])
        self.assertEqual(self.ran(node, "e"), ["1", "2"])
        self.assertEqual(len(self.tasks(node)), 1)

    def test_keep_running_not_killed(self):
        """until_round：keep 的 run 過了 until_round 不被殺；它自己結束後不再起新 run。"""
        node = self.mknode("a", [{"name": "k", "mode": "keep", "argv": rec_argv("k", keep=True), "until_round": 1}])
        self.itick()
        pj = self.wait_pid(node, "k")
        self.itock()
        for _ in range(2):
            self.assertEqual(self.itick()["started"], [])
            self.assertTrue(alive(pj["pid"]), "過了 until_round 的 keep 被殺了")
            self.assertIn("k#1", self.itock()["alive"])
        os.killpg(pj["pgid"], signal.SIGKILL)
        self.wait_ended(node, "k", 1)
        if self.round_json(node).get("open"):
            self.itock()
        for _ in range(2):
            self.assertEqual(self.itick()["started"], [], "過了 until_round 還重起 keep")
            self.itock()
        self.assertEqual(self.ran(node, "k"), ["1"])

    def test_until_round_bad_type_skipped(self):
        """until_round 型別錯（負數、字串、bool）→ 只跳過該項、記 tasks_error；until_round=0 合法（一次都不起）；好項照起。"""
        node = self.mknode("a", [{"name": "n", "argv": ["true"], "until_round": -1},
                                 {"name": "s", "argv": ["true"], "until_round": "3"},
                                 {"name": "b", "argv": ["true"], "until_round": True},
                                 {"name": "z", "argv": ["true"], "until_round": 0},
                                 {"name": "g", "argv": ["true"], "until_round": 5}])
        out = self.itick()
        self.assertEqual(out["started"], ["g#1"], out)
        errs = self.round_json(node).get("tasks_error") or []
        for n in ("n", "s", "b"):
            self.assertTrue([e for e in errs if e.startswith(n + "：") and "until_round" in e], "%s 沒記 tasks_error：%r" % (n, errs))
        self.assertFalse([e for e in errs if e.startswith(("z：", "g："))], errs)


if __name__ == "__main__":
    unittest.main()
