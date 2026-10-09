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
from aos7_fs import write_json  # noqa: E402
from _matrix import MatrixCase, env, gen, rec_argv  # noqa: E402

RETRY = os.path.join(MODULES, "once_retry", "retry_lost.py")
_spec = importlib.util.spec_from_file_location("aos7_retry_lost", RETRY)
retry_lost = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(retry_lost)


class TestRetryLost(MatrixCase):
    """〔once_retry〕retry_lost（P2-02，F26）：同程序呼叫模組的 scan（每個 tock 之後一次，等於任務收到 tock）。"""

    def lost_once(self, x=None, scan=True, rounds=4):
        """once 項（帶 x）在 after-birth 被打斷，之後恢復 tock＋指定回合數（預設四回合）；scan＝每次 tock 後跑一次模組。回 (node, 各回合總結)。"""
        item = {"name": "o", "mode": "once", "argv": rec_argv("o")}
        if x is not None:
            item["x"] = x
        node = self.mknode("a", [item])
        self.crash("aos7-tick", "after-birth")
        sums = []
        with env(AOS7_INCOMPLETE="tick"):
            sums.append(self.itock())
        for _ in range(rounds):
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

    def test_pending_dropped_when_slot_reused_by_keep(self):
        """R8-26：表壞掉留下 pending 後，同名 keep 真的重用槽，不能拿舊 birth 加回 once。"""
        node, sums = self.lost_once(x={"retry_lost": True}, scan=False, rounds=2)
        self.assertEqual(self.ends_of(sums, "o"), [{"run": "o#1", "code": None, "lost": True, "never_started": True}])
        self.assertEqual(len(retry_lost.candidates(node)), 1)
        with open(os.path.join(node, ".aos", "tasks.json"), "w") as f:
            f.write("{")
        pending = retry_lost.scan(node)
        self.assertIn("o#1", pending)
        keep = {"name": "o", "mode": "keep", "argv": rec_argv("keep", keep=True)}
        self.set_tasks(node, [keep])
        self.itick()
        self.wait_pid(node, "o")
        self.assertNotEqual(str(self.birth(node, "o")["run"]), "1")
        self.assertIs(self.birth(node, "o")["once"], False)
        self.assertEqual(retry_lost.scan(node, pending), {})
        self.assertEqual(self.tasks(node), [keep])
        self.assertEqual(self.ran(node, "o"), [])

    def test_pending_retained_when_birth_unreadable(self):
        """R8-26：表鎖內讀到 birth 壞掉時保留 pending，修回後仍能加回。"""
        node, _ = self.lost_once(x={"retry_lost": True}, scan=False, rounds=2)
        rid, slot, birth = retry_lost.candidates(node)[0]
        pending = {rid: (slot, birth)}
        path = os.path.join(self.slot(node, slot), "birth.json")
        with open(path, "w") as f:
            f.write("{")
        self.assertEqual(retry_lost.scan(node, pending), pending)
        self.assertEqual(self.tasks(node), [])
        write_json(path, [])   # 讀得到但不是物件：一樣不知道，留著
        self.assertEqual(retry_lost.scan(node, pending), pending)
        self.assertEqual(self.tasks(node), [])
        write_json(path, birth)
        self.assertEqual(retry_lost.scan(node, pending), {})
        self.assertEqual(self.tasks(node)[0]["x"]["retry_of"], rid)

    def test_pending_dropped_when_birth_missing(self):
        """R8-26：槽證據確定已消失，不再加回或留下 pending。"""
        node, _ = self.lost_once(x={"retry_lost": True}, scan=False, rounds=2)
        rid, slot, birth = retry_lost.candidates(node)[0]
        os.unlink(os.path.join(self.slot(node, slot), "birth.json"))
        self.assertEqual(retry_lost.scan(node, {rid: (slot, birth)}), {})
        self.assertEqual(self.tasks(node), [])

    def test_pending_dropped_when_retry_lost_withdrawn(self):
        """R8-26：同 run 的 retry_lost 已撤回，舊候選不能加回。"""
        node, _ = self.lost_once(x={"retry_lost": True}, scan=False, rounds=2)
        rid, slot, birth = retry_lost.candidates(node)[0]
        write_json(os.path.join(self.slot(node, slot), "birth.json"), dict(birth, x={"retry_lost": False}))
        self.assertEqual(retry_lost.scan(node, {rid: (slot, birth)}), {})
        self.assertEqual(self.tasks(node), [])

    def check_retry_lost_value(self, value):
        """T8-08：先有真正的 lost，再驗證只有布林 true 才產生候選並執行一次。"""
        node, sums = self.lost_once(x={"retry_lost": value}, scan=False, rounds=2)
        lost = {"run": "o#1", "code": None, "lost": True, "never_started": True}
        self.assertEqual(self.ends_of(sums, "o"), [lost])
        self.assertIn(lost, self.last_round(node)["ended"])
        candidates = retry_lost.candidates(node)
        self.assertEqual([c[0] for c in candidates], ["o#1"] if value is True else [])
        self.assertEqual(retry_lost.scan(node), {})
        self.assertEqual(len(self.tasks(node)), 1 if value is True else 0)
        for _ in range(4):
            self.itick()
            self.settle(node, "o")
            self.itock()
        self.assertEqual(len(self.ran(node, "o")), 1 if value is True else 0)
        self.assertEqual(self.tasks(node), [])

    def test_old_field_rejected(self):
        """舊的頂層 `retry_lost` 欄：核心跳過該項、tasks_error 指到這個包。"""
        node = self.mknode("a", [{"name": "o", "mode": "once", "argv": ["true"], "retry_lost": True},
                                 {"name": "g", "mode": "once", "argv": ["true"], "x": {"retry_lost": "yes"}}])
        out = self.itick()
        self.assertEqual(out["started"], ["g#1"], out)
        errs = self.round_json(node).get("tasks_error") or []
        self.assertTrue([e for e in errs if e.startswith("o：") and "once 保證包" in e], errs)


gen(TestRetryLost, "retry_lost_value", [("true", (True,)), ("false", (False,)),
                                       ("string", ("yes",)), ("integer", (1,)), ("null", (None,))],
    TestRetryLost.check_retry_lost_value)


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
