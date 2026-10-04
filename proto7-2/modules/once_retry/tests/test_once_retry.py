"""〔once_retry〕once 保證包：retry_lost 任務把「從沒起來過就 lost」、`x.retry_lost: true` 的 once 加回（至少一次）。

從 tests/core/test_options_a3.py 的 TestRetryLost（P2-02）搬來改寫：以前是核心選項，現在核心只給事實欄 `never_started`，
加回由這個包做。**AOS7_TEST_CRASH=after-birth**：tick 寫完 birth.json、起 runner 之前 SIGKILL（只給測試用）。
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tests"))  # tests/：base

import importlib.util  # noqa: E402
import unittest  # noqa: E402

from base import MODULES  # noqa: E402
from _matrix import MatrixCase, env, rec_argv  # noqa: E402

RETRY = os.path.join(MODULES, "once_retry", "retry_lost.py")
_spec = importlib.util.spec_from_file_location("aos7_retry_lost", RETRY)
retry_lost = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(retry_lost)


class TestRetryLost(MatrixCase):
    """〔once_retry〕retry_lost（P2-02，F26）：同程序呼叫模組的 scan（每個 tock 之後一次，等於任務收到 tock）。"""

    def lost_once(self, x=None, scan=True):
        """once 項（帶 x）在 after-birth 被打斷，之後恢復 tock＋四回合；scan＝每次 tock 後跑一次模組。回 (node, 各回合總結)。"""
        item = {"name": "o", "mode": "once", "argv": rec_argv("o")}
        if x is not None:
            item["x"] = x
        node = self.mknode("a", [item])
        self.crash("aos7-tick", "after-birth")
        sums = []
        with env(AOS7_INCOMPLETE="tick"):
            sums.append(self.itock())
        for _ in range(4):
            if scan:
                self.assertEqual(retry_lost.scan(node), {})
            self.itick()
            self.settle(node, "o")
            sums.append(self.itock())
        return node, sums

    def test_retry_lost_true_runs_once(self):
        """x.retry_lost:true 的 once 從沒起來過 → 模組加回、同槽新 run 跑一次（副作用 1 次）；ended 的 lost 帶 never_started。"""
        node, sums = self.lost_once(x={"retry_lost": True})
        self.wait_for(lambda: self.ran(node, "o"), 5, "加回的 once 沒跑")
        self.assertEqual(len(self.ran(node, "o")), 1, "retry_lost 的 once 執行了 %r" % self.ran(node, "o"))
        ends = self.ends_of(sums, "o")
        first = [e for e in ends if e["run"] == "o#1"]
        self.assertEqual(first, [{"run": "o#1", "code": None, "lost": True, "never_started": True}], ends)
        again = [e for e in ends if e["run"] != "o#1"]
        self.assertEqual(len(again), 1, ends)
        self.assertEqual(again[0]["code"], 0, again)
        self.assertNotIn("lost", again[0])
        self.assertEqual(self.tasks(node), [], "加回的 once 項沒刪掉：%r" % self.tasks(node))

    def test_retry_lost_default_at_most_once(self):
        """不帶 x.retry_lost：模組照跑也不加回，維持最多一次：0 次、報一次 lost。"""
        node, sums = self.lost_once()
        self.assertEqual(self.ran(node, "o"), [])
        self.assertEqual(self.ends_of(sums, "o"), [{"run": "o#1", "code": None, "lost": True, "never_started": True}])
        self.assertEqual(self.tasks(node), [])

    def test_old_field_rejected_and_non_true_ignored(self):
        """舊的頂層 `retry_lost` 欄：核心跳過該項、tasks_error 指到這個包；`x.retry_lost` 不是 true（字串）：核心照起，模組不理。"""
        node = self.mknode("a", [{"name": "o", "mode": "once", "argv": ["true"], "retry_lost": True},
                                 {"name": "g", "mode": "once", "argv": ["true"], "x": {"retry_lost": "yes"}}])
        out = self.itick()
        self.assertEqual(out["started"], ["g#1"], out)
        errs = self.round_json(node).get("tasks_error") or []
        self.assertTrue([e for e in errs if e.startswith("o：") and "once 保證包" in e], errs)
        self.assertEqual(retry_lost.candidates(node), [])


class TestRetryLostTask(MatrixCase):
    """〔once_retry〕模組當普通 keep 任務跑：收到 tock 就看 last-round.json，把 lost 的 once 加回（取樣，見 README）。"""

    def test_module_as_keep_task(self):
        import sys as _sys
        node = self.mknode("a", [{"name": "o", "mode": "once", "argv": rec_argv("o"), "x": {"retry_lost": True}},
                                 {"name": "retry", "mode": "keep", "argv": [_sys.executable, RETRY]}])
        self.crash("aos7-tick", "after-birth")       # o 先排：寫完它的 birth 就被殺，retry 還沒起
        with env(AOS7_INCOMPLETE="tick"):
            self.itock()
        reported = False
        for _ in range(6):
            self.itick()
            self.settle(node, "o")
            lr = self.itock()
            if any(e.get("run") == "o#1" and e.get("lost") for e in lr.get("ended", [])):
                reported = True
                self.wait_for(lambda: any((i.get("x") or {}).get("retry_of") == "o#1" for i in self.tasks(node) or [])
                              or self.ran(node, "o"), 10, "retry_lost 任務沒把 once 加回")
            if self.ran(node, "o"):
                break
        self.assertTrue(reported, "o#1 沒報 lost")
        self.wait_for(lambda: self.ran(node, "o"), 5, "加回的 once 沒跑")
        self.assertEqual(len(self.ran(node, "o")), 1, self.ran(node, "o"))


if __name__ == "__main__":
    unittest.main()
