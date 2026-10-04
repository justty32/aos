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
3. **birth.json 壞** 內容 ∈ {`{`、`[]`、`{"run": "x"}`} × 其他證據 ∈
   - `live`：有相符活程序（NODE＋TID）→ LIVE，不起、不判 lost，槽裡仍只有那一個程序；
   - `exit`：沒活程序、有 exit.json（run R）→ ENDED、run＝R；once 項的 launch.run＝R 時 tick 刪掉這項、不重跑
     （重現 astra 的 once_corrupt_birth：tick 死在 before-once-delete、run 1 跑完、birth 寫壞 → 槽外副作用只有一次）；
   - `pid`：沒活程序、有 pid.json（run R）、任務已死、沒 exit → 疑似 lost → tock 寫 lost（run R）；
   - `none`：什麼證據都沒有 → UNKNOWN：tick 不起、tock errors 有說明；人刪掉 birth.json 後下一回合照常起。
"""
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


gen(TestLastRoundJson, "bad_last_round", [("half", ("{",)), ("no_fields", ('{"round": 2}',)),
                                          ("round_str", ('{"round": "2"}',))], TestLastRoundJson._bad_last)


class TestBrokenBirth(MatrixCase):
    def corrupt(self, node, slot, content):
        with open(os.path.join(self.slot(node, slot), "birth.json"), "w") as f:
            f.write(content)

    def _live(self, content):
        """birth 壞＋有相符活程序 → LIVE：不起、不判 lost，仍只有那一個程序。"""
        node = self.mknode("a", [{"name": "k", "mode": "keep", "argv": rec_argv("k", keep=True)}])
        self.itick()
        pid = self.wait_pid(node, "k")["pid"]
        self.itock()
        self.corrupt(node, "k", content)
        self.assertEqual(self.view(node, "k", 2).state, aos7_task.LIVE)
        self.assertEqual(self.itick()["started"], [], "birth 壞、任務還活時起了第二份")
        lr = self.itock()
        self.assertEqual(self.ends_of([lr], "k"), [])
        self.assertTrue(alive(pid))
        self.assertEqual(self.live_procs(node, "k"), [pid])
        self.assertEqual(self.ran(node, "k"), ["1"])

    def _exit(self, content):
        """birth 壞＋有 exit.json（run 1）→ ENDED、run＝1；once 項（launch.run＝1）刪掉、不重跑（astra once_corrupt_birth）。"""
        node = self.mknode("a", [{"name": "o", "mode": "once", "argv": rec_argv("o")}])
        self.crash("aos7-tick", "before-once-delete")
        self.wait_ended(node, "o", 1)
        self.wait_for(lambda: not self.live_procs(node, "o"), 5)
        self.assertEqual(len(self.tasks(node)), 1)     # once 項還在（帶 launch run 1）
        self.corrupt(node, "o", content)
        v = self.view(node, "o", 2)
        self.assertEqual((v.state, v.run), (aos7_task.ENDED, 1), v)
        sums = [self.itock()]
        for _ in range(2):
            self.itick()
            self.settle(node, "o")
            sums.append(self.itock())
        self.assertEqual(self.ran(node, "o"), ["1"], "birth 壞掉後 once 又跑了一次")
        self.assertEqual(self.tasks(node), [], "once 項沒刪掉")
        self.assertLessEqual(len(self.ends_of(sums, "o")), 1, self.ends_of(sums, "o"))

    def _pid(self, content):
        """birth 壞＋有 pid.json（run 1）、任務已死、沒 exit → 疑似 lost → tock 寫 lost（run 1）。"""
        node = self.mknode("a", [{"name": "k", "mode": "keep", "argv": rec_argv("k", keep=True)}])
        self.itick()
        self.wait_pid(node, "k")
        self.itock()
        self.kill_runner_and_task(node, "k")
        self.corrupt(node, "k", content)
        self.itick()
        lr = self.itock()
        ex = self.exit_raw(node, "k")
        lost = [x for x in self.ends_of([lr], "k") if x.get("lost")]
        self.assertEqual([x["run"] for x in lost], ["k#1"], "沒照 pid.json 的 run 判 lost：%r／exit=%r" % (lr["ended"], ex))
        self.wait_for(lambda: len(self.live_procs(node, "k")) <= 1, 2)
        self.assertLessEqual(len(self.live_procs(node, "k")), 1)

    def _none(self, content):
        """birth 壞、沒有任何其他證據 → UNKNOWN：不起、tock errors 有說明；人刪掉 birth.json 後照常起。"""
        node = self.mknode("a", [{"name": "k", "mode": "keep", "argv": rec_argv("k", keep=True)}])
        os.makedirs(self.slot(node, "k"))
        self.corrupt(node, "k", content)
        self.assertEqual(self.view(node, "k", 1).state, aos7_task.UNKNOWN)
        self.assertEqual(self.itick()["started"], [], "沒有證據時就在壞 birth 的槽起了任務")
        lr = self.itock()
        errs = self.errors_for(lr, "k")
        self.assertTrue(errs and all(x.get("err") for x in errs), "tock errors 沒說明：%r" % lr.get("errors"))
        self.assertEqual(self.itick()["started"], [])
        self.itock()
        os.remove(os.path.join(self.slot(node, "k"), "birth.json"))
        self.assertEqual(self.itick()["started"], ["k#3"])
        self.wait_for(lambda: len(self.live_procs(node, "k")) == 1, 5)


for _kind in ("live", "exit", "pid", "none"):
    gen(TestBrokenBirth, "birth_%s" % _kind, [(n, (c,)) for n, c in BAD_BIRTH], getattr(TestBrokenBirth, "_" + _kind))


if __name__ == "__main__":
    unittest.main()
