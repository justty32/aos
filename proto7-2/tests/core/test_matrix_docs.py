"""固定回歸矩陣（二）：狀態檔內容壞掉（A2-02 round.json、last-round.json、A2-03 birth.json；spec 第 3、5.4、7 節）。

**AOS7_TEST_* 環境變數只給測試用**（這裡用 `AOS7_TEST_CRASH=before-once-delete` 讓子程序 tick 在刪 once 項前 SIGKILL 自己）。

矩陣維度與判定：

1. **round.json 壞**：內容 ∈ {`{`（半寫）、`{"round": 2}`（缺 open）、`{"round": 2, "open": "yes"}`、`{"round": "2", "open": false}`、`[]`}
   → tick 退出碼 3、round.json 原樣、沒起任務；tock 退出碼 3；`Timeline.check_round()` 回 None（不知道）。
   人寫回 `{"round": 2, "open": false}` 後 tick 開第 3 回合。另外：round.json 還開著 → tick 3（訊息說回合還開著），
   寫回 open:false 才開下一回合；round.json 不存在＋last-round.json 壞 → tick 3；兩個都不存在 → 從 1 起。
2. **last-round.json 壞**（round.json 是開著的第 N 回合）：內容 ∈ {`{`、`{"round": N}`（缺欄）、`{"round": "N"}`}
   → tock 重新產生完整總結（round＝N、有 ended／alive／tock_at、不是 replayed）、回合關上、之後 tick 開 N+1。
   對照：last-round.json 是完整的第 N 回合總結 → replayed。
   T8-06：已結束 once 在 tock-summary／tock-after-finish／tock-seen-round 被殺 → 重播補收尾、保留本回合槽，下一回合不重報並刪槽。
3. **birth.json 壞** 內容 ∈ {`{`、`[]`、`{"run": "x"}`} → UNKNOWN（單槽保留）：tick 不起、tock errors 有說明；人刪掉 birth.json 後
   下一回合照常起。不從其他證據（活程序、exit.json、pid.json）推回 run（那是誤用，已刪）。
"""
import os, sys  # noqa: E401
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # tests/：base、_matrix
import os
import unittest

from _matrix import MatrixCase, alive, gen, rec_argv
import aos7_daemon_timeline
import aos7_task
from aos7_fs import write_json

BAD_ROUND = (("half", "{"), ("no_open", '{"round": 2}'), ("open_str", '{"round": 2, "open": "yes"}'),
             ("round_str", '{"round": "2", "open": false}'), ("list", "[]"))
BAD_BIRTH = (("half", "{"), ("list", "[]"), ("run_str", '{"run": "x"}'))


class _FakeDaemon:
    def __init__(self, root):
        self.root = root


class TestRoundJson(MatrixCase):
    """〔core〕"""
    def _bad_round(self, content):
        """round.json 內容壞掉＝不知道回合關了沒：tick／tock 退出碼 3、什麼都不寫；人寫回 open:false 後照常。"""
        node = self.mknode("a", [{"name": "j", "argv": ["true"]}])
        self.itick()
        self.settle(node, "j")
        self.itock()
        rp = os.path.join(node, ".aos", "round.json")
        with open(rp, "w") as f:
            f.write(content)
        rc, out, err = self.run_prog("aos7-tick")
        self.assertEqual(rc, 3, "round.json＝%r 時 tick 沒拒絕（rc=%r, out=%r）" % (content, rc, out))
        self.assertIn("unknown", out or {})
        rc, out, err = self.run_prog("aos7-tock")
        self.assertEqual(rc, 3, "round.json＝%r 時 tock 沒拒絕（rc=%r, out=%r）" % (content, rc, out))
        with open(rp) as f:
            self.assertEqual(f.read(), content, "round.json 被改了")
        self.assertEqual(self.birth(node, "j")["run"], 1, "起了任務")
        self.assertIsNone(aos7_daemon_timeline.Timeline(_FakeDaemon(self.root), "a", None).check_round(),
                          "check_round 要回 None（不知道）")
        write_json(rp, {"round": 2, "open": False})   # 人工恢復
        self.assertEqual(self.itick()["round"], 3)

    def test_open_round_tick_refuses(self):
        """round.json 還開著：tick 退出碼 3（說回合還開著）；人寫回 open:false 後開下一回合。"""
        node = self.mknode("a")
        self.itick()
        self.itock()
        self.itick()                                   # 第 2 回合開著
        rp = os.path.join(node, ".aos", "round.json")
        before = self.raw(rp)
        rc, out, err = self.run_prog("aos7-tick")
        self.assertEqual(rc, 3, "回合還開著時 tick 又開了一回合（out=%r）" % (out,))
        msg = (out or {}).get("unknown", "") + err
        self.assertTrue("開著" in msg or "open" in msg, msg)
        self.assertEqual(self.raw(rp), before)
        write_json(rp, {"round": 2, "open": False})
        self.assertEqual(self.itick()["round"], 3)

    def test_missing_round_bad_last_round(self):
        """round.json 不存在、last-round.json 壞：推定不了回合數 → tick 3，什麼都不寫。"""
        node = self.mknode("a")
        lp = os.path.join(node, ".aos", "last-round.json")
        with open(lp, "w") as f:
            f.write("{")
        rc, out, err = self.run_prog("aos7-tick")
        self.assertEqual(rc, 3, out)
        self.assertFalse(os.path.exists(os.path.join(node, ".aos", "round.json")))

    def test_both_missing_starts_at_one(self):
        node = self.mknode("a")
        self.assertEqual(self.itick()["round"], 1)
        self.assertEqual(self.itock()["round"], 1)


gen(TestRoundJson, "bad_round", [(n, (c,)) for n, c in BAD_ROUND], TestRoundJson._bad_round)


class TestLastRoundJson(MatrixCase):
    """〔core〕"""
    def _bad_last(self, content):
        """last-round.json 壞（round.json 是開著的第 2 回合）：tock 重新產生完整總結，不是 replayed；之後開第 3 回合。"""
        node = self.mknode("a", [{"name": "j", "argv": ["true"]}])
        self.itick()
        self.settle(node, "j")
        self.itock()
        self.itick()                                   # 第 2 回合開著
        self.settle(node, "j")
        with open(os.path.join(node, ".aos", "last-round.json"), "w") as f:
            f.write(content)
        lr = self.itock()
        self.assertFalse(lr.get("replayed"), "壞的 last-round.json 被當成這回合的總結重播：%r" % lr)
        self.assertEqual(lr["round"], 2)
        for k in ("ended", "alive", "tock_at"):
            self.assertIn(k, lr)
        disk = self.last_round(node)
        self.assertEqual(disk.get("round"), 2)
        for k in ("ended", "alive", "tock_at"):
            self.assertIn(k, disk, "last-round.json 沒重新產生完整總結：%r" % disk)
        self.assertIn({"run": "j#2", "code": 0}, disk["ended"])
        self.assertIs(self.round_json(node)["open"], False)
        self.assertEqual(self.itick()["round"], 3)

    def test_complete_summary_is_replayed(self):
        """對照：last-round.json 已是完整的第 N 回合總結（tock 寫完總結就被殺）→ replayed，不重寫。"""
        node = self.mknode("a")
        self.itick()
        self.itock()
        self.itick()
        self.crash("aos7-tock", "tock-summary")
        lp = os.path.join(node, ".aos", "last-round.json")
        before = self.raw(lp)
        lr = self.itock()
        self.assertTrue(lr.get("replayed"))
        self.assertEqual(self.raw(lp), before)
        self.assertEqual(self.itick()["round"], 3)

    def _ended_once_replay_finish(self, point):
        """T8-06：已結束 once 重播必須收尾；tock-summary＝總結寫完、尚未補 seen_round；
        tock-after-finish＝收尾完成、尚未關回合；tock-seen-round＝seen_round 寫完、收尾尚未完成。
        once 表項在首次 tick 起動成功就刪；結果槽保留完整一回合，下一回合 tock 才刪。
        """
        node = self.mknode("a", [{"name": "j", "mode": "once", "argv": ["true"]}])
        self.itick()
        self.settle(node, "j")
        self.crash("aos7-tock", point)
        lp = os.path.join(node, ".aos", "last-round.json")
        before = self.raw(lp)
        ex0 = self.exit_raw(node, "j")
        self.assertIsInstance(ex0, dict)
        if point == "tock-summary":
            self.assertNotIn("seen_round", ex0)
        else:
            self.assertEqual(ex0["seen_round"], 1)
        self.assertIs(self.round_json(node)["open"], True)
        self.assertEqual(self.tasks(node), [], "once 起動成功後應已刪除表項")

        lr = self.itock()
        self.assertTrue(lr.get("replayed"))
        self.assertEqual(self.raw(lp), before, "重播不應改寫總結")
        ended = self.ends_of([lr], "j")
        self.assertEqual(len(ended), 1)
        self.assertEqual(ended[0]["run"], "j#1")
        self.assertEqual(ended[0]["code"], 0)
        self.assertIs(self.round_json(node)["open"], False)
        self.assertEqual(self.exit_raw(node, "j")["seen_round"], 1)
        self.assertTrue(os.path.isdir(self.slot(node, "j")), "本回合才報過的結果槽必須保留")

        self.assertEqual(self.itick()["round"], 2)
        self.assertEqual(self.tasks(node), [])
        lr2 = self.itock()
        self.assertEqual(self.ends_of([lr2], "j"), [], "已報過的 once 不應重報")
        self.assertFalse(os.path.isdir(self.slot(node, "j")), "下一回合應刪除已報過的 once 槽")


gen(TestLastRoundJson, "bad_last_round", [("half", ("{",)), ("no_fields", ('{"round": 2}',)),
                                          ("round_str", ('{"round": "2"}',))], TestLastRoundJson._bad_last)
gen(TestLastRoundJson, "ended_once_replay_finish", [(p, (p,)) for p in
                                                 ("tock-summary", "tock-after-finish", "tock-seen-round")],
    TestLastRoundJson._ended_once_replay_finish)


class TestBrokenBirth(MatrixCase):
    """〔core〕birth.json 壞掉＝不知道（單槽保留）。以前從其他證據推回 run 的 live／exit／pid 三種已刪（誤用 M-2.3，見 problems.md）。"""
    def corrupt(self, node, slot, content):
        with open(os.path.join(self.slot(node, slot), "birth.json"), "w") as f:
            f.write(content)

    def _none(self, content):
        """birth 壞 → UNKNOWN：不起、tock errors 有說明；人刪掉 birth.json 後照常起。"""
        node = self.mknode("a", [{"name": "k", "mode": "keep", "argv": rec_argv("k", keep=True)}])
        os.makedirs(self.slot(node, "k"))
        self.corrupt(node, "k", content)
        self.assertEqual(self.view(node, "k", 1).state, aos7_task.UNKNOWN)
        self.assertEqual(self.itick()["started"], [], "沒有證據時就在壞 birth 的槽起了任務")
        lr = self.itock()
        errs = self.errors_for(lr, "k")
        self.assertTrue(errs and all(x.get("why") for x in errs), "tock errors 沒說明：%r" % lr.get("errors"))
        self.assertEqual(self.itick()["started"], [])
        self.itock()
        os.remove(os.path.join(self.slot(node, "k"), "birth.json"))
        self.assertEqual(self.itick()["started"], ["k#3"])
        self.wait_for(lambda: len(self.live_procs(node, "k")) == 1, 5)


gen(TestBrokenBirth, "birth_none", [(n, (c,)) for n, c in BAD_BIRTH], TestBrokenBirth._none)


if __name__ == "__main__":
    unittest.main()
