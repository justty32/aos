"""固定回歸矩陣（一）：讀不到＝不知道（A2-01 與檔案層的三態；spec 第 0 節、5.4、2.6）。

**AOS7_TEST_* 環境變數只給測試用**：這裡用 `AOS7_TEST_FAULT`（分號分隔的 `op:glob:ERRNO`，glob 用 fnmatch 比完整路徑）
在指定的讀取點丟 OSError，`AOS7_TEST_RUNNER_CRASH` 讓 aos7-run 在指定點 SIGKILL 自己。正常環境不設；tick 起任務時拿掉。

矩陣維度與判定：

1. **/proc 讀不到**：op ∈ {proc-list（`/proc`）、proc-stat、proc-environ、proc-cmdline（只打在這個任務／runner 的 pid 上）}
   × errno ∈ {EIO、ESTALE、EACCES} × 情境 ∈
   - `healthy`：keep 任務正常活著。判定：judge 是 LIVE（proc-stat 時帶 `unsure`）；tick 不起新 run（started＝[]、birth 的 run 不變）、
     不殺（pid 還活）、不寫 exit.json；tock 的 alive 列它，unsure 時 errors 有這個槽一筆（phase unsure／judge）。拿掉注入：
     同一個 pid 繼續活、tock 的 alive 列它、執行次數仍 1。
   - `orphan`：runner 在 pid.json 前被 SIGKILL、任務還活（疑似 lost，要身分掃描）。判定：注入時 UNKNOWN——不殺、不寫 lost、
     不起新 run、tock errors 有一筆；拿掉後才收掉孤兒、判 lost，而且 lost 只報一次，之後槽裡剛好一個活程序。
   - `deadboth`（只有 proc-list、proc-environ 全部 pid）：runner 與任務都被 SIGKILL、沒 exit.json。判定同 orphan。
   - **契約**：proc-environ／proc-cmdline 的 EACCES＝「身分讀不到＝不是可辨認的任務、略過」（同 uid 的桌面程序本來就這樣），
     不是不知道；所以 orphan／deadboth／brokenbirth 不跑 environ、cmdline × EACCES，改成 healthy 的「不雙開、不誤殺」，
     加上 `deadboth_skip`（environ 全部 EACCES、任務確實死了 → 照常判 lost 一次、重起一個）。
   - `brokenbirth`（只有 proc-environ × EIO、ESTALE）：birth.json 壞掉，只能靠身分掃描 → UNKNOWN、不雙開；拿掉後判活（同一個 pid）。
   另有 `kill_identity` 在掃描不完整時回 (False, 說明)、`env_procs` 丟 `aos7_proc.ProcUnknown`。
2. **檔案讀不到**（open 注入）：檔 ∈ {birth.json、exit.json、pid.json} × errno → 槽 UNKNOWN：不起、不判 lost、不刪槽（名字拿掉也不刪）、
   tock errors 一筆；拿掉後恢復（lost 只報一次、重新起一個），回合不跳號。
   檔 ∈ {round.json（tick 3、tock 3，round.json 原樣）、last-round.json（tock 3）}、listdir `.aos/tasks`（tick 3、tock 3）× errno：
   什麼都沒寫；拿掉後恢復、回合連續。
3. **daemon 看 node 的 stat 讀不到** × errno：時間線保留、不進 missing、不起 reaper，last_error 帶 errno 類型。
"""
import errno
import os
import unittest

from _matrix import ERRNOS, MatrixCase, alive, fault, gen, rec_argv
import aos7_daemon
import aos7_daemon_timeline
import aos7_proc
import aos7_task

PROC_OPS = ("proc-list", "proc-stat", "proc-environ", "proc-cmdline")


def proc_rules(op, pids, e):
    """只打在給的 pid 上（proc-list 打 `/proc` 本身）。"""
    if op == "proc-list":
        return "proc-list:/proc:%s" % e
    leaf = op.split("-", 1)[1]
    return ";".join("%s:/proc/%d/%s:%s" % (op, p, leaf, e) for p in pids if p)


def keep_item(name="k"):
    return {"name": name, "mode": "keep", "argv": rec_argv(name, keep=True)}


class TestProcUnknown(MatrixCase):
    def _healthy(self, op, e):
        """/proc 讀不到、任務其實健康地活著：不殺、不起、不判 lost；拿掉注入自動回正。"""
        node = self.mknode("a", [keep_item()])
        self.itick()
        pid = self.wait_pid(node, "k")["pid"]
        self.itock()
        runner = (self.birth(node, "k").get("runner") or {}).get("pid")
        with fault(proc_rules(op, [pid, runner], e)):
            v = self.view(node, "k", 2)
            self.assertEqual(v.state, aos7_task.LIVE, v)
            if op == "proc-stat":
                self.assertTrue(v.get("unsure"), "pid／starttime 讀不到要判 LIVE＋unsure：%r" % v)
            out = self.itick()
            lr = self.itock()
        self.assertEqual(out["started"], [], "讀不到 /proc 時起了新的 run（雙開）")
        self.assertTrue(alive(pid), "讀不到 /proc 時把活任務殺了")
        self.assertEqual(self.birth(node, "k")["run"], 1)
        self.assertIsNone(self.exit_raw(node, "k"), "讀不到 /proc 時寫了 exit.json")
        self.assertIn("k#1", lr["alive"])
        if v.get("unsure"):
            errs = self.errors_for(lr, "k")
            self.assertTrue(any(x.get("phase") in ("unsure", "judge") and x.get("err") for x in errs),
                            "unsure 的槽要在 tock 的 errors 留一筆：%r" % lr.get("errors"))
        # 拿掉注入：自動回正
        self.assertEqual(self.itick()["started"], [])
        lr2 = self.itock()
        self.assertIn("k#1", lr2["alive"])
        self.assertTrue(alive(pid))
        self.assertEqual(self.ran(node, "k"), ["1"])

    def _orphan(self, op, e):
        """runner 在 pid.json 前被殺、任務還活：要身分掃描才能判 lost；掃描讀不到＝UNKNOWN，拿掉後才判 lost，只報一次。"""
        node = self.mknode("a", [keep_item()])
        rc, _out, err = self.run_prog("aos7-tick", env={"AOS7_TEST_RUNNER_CRASH": "runner-before-pid"})
        self.assertEqual(rc, 0, err)
        runner = (self.birth(node, "k").get("runner") or {}).get("pid")
        pid = self.wait_for(lambda: self.live_procs(node, "k"), 5, "任務沒起來")[0]
        self.wait_for(lambda: not alive(runner), 5, "runner 沒在 runner-before-pid 被殺")
        self.assertFalse(os.path.exists(os.path.join(self.slot(node, "k"), "pid.json")))
        sums = []
        with fault(proc_rules(op, [pid], e)):
            lr = self.itock()
            sums.append(lr)
            self.assertTrue(alive(pid), "掃描讀不到時把孤兒任務殺了")
            self.assertTrue(any(x.get("phase") in ("unsure", "judge") and x.get("err")
                                for x in self.errors_for(lr, "k")), "tock errors 沒有這個槽：%r" % lr.get("errors"))
            self.assertEqual(self.itick()["started"], [], "掃描讀不到時起了新的 run")
            sums.append(self.itock())
        self.assertTrue(alive(pid))
        self.assertEqual(self.ends_of(sums, "k"), [], "掃描讀不到時就判了 lost：%r" % self.ends_of(sums, "k"))
        self.assertEqual(self.birth(node, "k")["run"], 1)
        # 拿掉注入：收掉孤兒、判 lost（一次）、重起一個
        for _ in range(2):
            self.itick()
            sums.append(self.itock())
        self.assertEqual([x for x in self.ends_of(sums, "k") if x["run"] == "k#1"],
                         [{"run": "k#1", "code": None, "lost": True}])
        self.wait_for(lambda: not alive(pid), 5, "孤兒任務拿掉注入後沒收")
        self.wait_for(lambda: len(self.live_procs(node, "k")) == 1, 5, "恢復後槽裡不是剛好一個活程序")
        self.assertEqual(len(self.ran(node, "k")), 2, self.ran(node, "k"))

    def _deadboth(self, op, e):
        """runner 與任務都死了、沒 exit.json：身分掃描讀不到＝UNKNOWN 不寫 lost；拿掉後判 lost 一次。"""
        node = self.mknode("a", [keep_item()])
        self.itick()
        self.wait_pid(node, "k")
        self.itock()
        self.kill_runner_and_task(node, "k")
        rule = "proc-list:/proc:%s" % e if op == "proc-list" else "proc-environ:/proc/*/environ:%s" % e
        sums = []
        with fault(rule):
            self.assertEqual(self.itick()["started"], [], "掃描讀不到時起了新的 run")
            lr = self.itock()
            sums.append(lr)
            self.assertTrue(any(x.get("phase") in ("unsure", "judge") and x.get("err")
                                for x in self.errors_for(lr, "k")), "tock errors 沒有這個槽：%r" % lr.get("errors"))
        self.assertIsNone(self.exit_raw(node, "k"), "掃描讀不到時寫了 lost")
        for _ in range(2):
            self.itick()
            sums.append(self.itock())
        self.assertEqual([x for x in self.ends_of(sums, "k") if x["run"] == "k#1"],
                         [{"run": "k#1", "code": None, "lost": True}])
        self.wait_for(lambda: len(self.live_procs(node, "k")) == 1, 5, "恢復後槽裡不是剛好一個活程序")

    def test_deadboth_skip_proc_environ_EACCES(self):
        """environ 全部 EACCES＝身分讀不到的程序略過（不是不知道）：任務確實死了 → 照常判 lost 一次、重起一個，不雙開。"""
        node = self.mknode("a", [keep_item()])
        self.itick()
        self.wait_pid(node, "k")
        self.itock()
        self.kill_runner_and_task(node, "k")
        sums = []
        with fault("proc-environ:/proc/*/environ:EACCES"):
            for _ in range(2):
                self.itick()
                sums.append(self.itock())
        self.assertEqual([x for x in self.ends_of(sums, "k") if x["run"] == "k#1"],
                         [{"run": "k#1", "code": None, "lost": True}])
        self.wait_for(lambda: len(self.live_procs(node, "k")) == 1, 5, "恢復後槽裡不是剛好一個活程序")

    def _brokenbirth(self, e):
        """birth.json 壞掉＋身分掃描讀不到（proc-environ）＝UNKNOWN：不雙開；拿掉後判活（同一個 pid）。"""
        node = self.mknode("a", [keep_item()])
        self.itick()
        pid = self.wait_pid(node, "k")["pid"]
        self.itock()
        runner = (self.birth(node, "k").get("runner") or {}).get("pid")
        with open(os.path.join(self.slot(node, "k"), "birth.json"), "w") as f:
            f.write("{")
        with fault(proc_rules("proc-environ", [pid, runner], e)):
            v = self.view(node, "k", 2)
            self.assertEqual(v.state, aos7_task.UNKNOWN, v)
            self.assertEqual(self.itick()["started"], [], "birth 壞＋掃描讀不到時起了新的 run（雙開）")
            lr = self.itock()
            self.assertTrue(self.errors_for(lr, "k"), "tock errors 沒有這個槽：%r" % lr.get("errors"))
        self.assertTrue(alive(pid))
        self.assertEqual(self.live_procs(node, "k"), [pid])
        self.assertEqual(self.itick()["started"], [])
        self.itock()
        self.assertEqual(self.live_procs(node, "k"), [pid])
        self.assertEqual(self.ran(node, "k"), ["1"])

    def test_kill_identity_incomplete_scan(self):
        """掃描不完整：env_procs 丟 ProcUnknown、kill_identity 回 (False, 說明)，不殺。"""
        node = self.mknode("a", [keep_item()])
        self.itick()
        pid = self.wait_pid(node, "k")["pid"]
        with fault("proc-list:/proc:EIO"):
            with self.assertRaises(aos7_proc.ProcUnknown):
                aos7_proc.env_procs(node, "k")
            ok, msg = aos7_proc.kill_identity(node, "k", 1)
        self.assertIs(ok, False)
        self.assertIsInstance(msg, str)
        self.assertTrue(msg)
        self.assertTrue(alive(pid))


gen(TestProcUnknown, "healthy", [("%s_%s" % (op, e), (op, e)) for op in PROC_OPS for e in ERRNOS],
    TestProcUnknown._healthy)
# 契約（隊長 10-04）：proc-environ／proc-cmdline 的 EACCES＝「讀不到身分＝不是可辨認的任務、略過」（桌面上同 uid 的
# systemd --user、kwin 等本來就是 EACCES），不是「不知道」。所以「掃描不完整＝UNKNOWN」只用下面這些組合；
# environ／cmdline × EACCES 的判定是 healthy 情境的「不雙開、不誤殺」與 deadboth_skip 的「照常判 lost 一次」。
UNSURE_SCAN = [(op, e) for op in PROC_OPS for e in ERRNOS
               if not (op in ("proc-environ", "proc-cmdline") and e == "EACCES")]
gen(TestProcUnknown, "orphan", [("%s_%s" % (op, e), (op, e)) for op, e in UNSURE_SCAN], TestProcUnknown._orphan)
gen(TestProcUnknown, "deadboth", [("%s_%s" % (op, e), (op, e)) for op, e in UNSURE_SCAN
                                  if op in ("proc-list", "proc-environ")], TestProcUnknown._deadboth)
gen(TestProcUnknown, "brokenbirth_environ", [(e, (e,)) for e in ("EIO", "ESTALE")], TestProcUnknown._brokenbirth)


class TestFileUnknown(MatrixCase):
    def _slot_file(self, fname, e):
        """槽裡的 birth／exit／pid.json 讀不到：UNKNOWN——不起、不判 lost、不刪槽；拿掉後恢復，回合不跳號。"""
        node = self.mknode("a", [keep_item()])
        self.itick()
        self.wait_pid(node, "k")
        sums = [self.itock()]
        self.kill_runner_and_task(node, "k")       # 平常下一回合會判 lost、重起
        with fault("open:*/.aos/tasks/k/%s:%s" % (fname, e)):
            v = self.view(node, "k", 2)
            self.assertEqual(v.state, aos7_task.UNKNOWN, v)
            self.assertEqual(self.itick()["started"], [], "%s 讀不到時起了新的 run" % fname)
            lr = self.itock()
            sums.append(lr)
            self.assertTrue(self.errors_for(lr, "k"), "tock errors 沒有這個槽：%r" % lr.get("errors"))
            self.set_tasks(node, [])               # 名字拿掉：平常報完就刪槽；不知道時不能刪
            self.itick()
            sums.append(self.itock())
        self.assertTrue(os.path.isdir(self.slot(node, "k")), "%s 讀不到時把槽刪了" % fname)
        self.assertIsNone(self.exit_raw(node, "k"), "%s 讀不到時寫了 lost" % fname)
        self.assertEqual(self.ends_of(sums, "k"), [])
        self.set_tasks(node, [keep_item()])
        for _ in range(2):
            self.itick()
            sums.append(self.itock())
        self.assertEqual([x for x in self.ends_of(sums, "k") if x["run"] == "k#1"],
                         [{"run": "k#1", "code": None, "lost": True}])
        self.wait_for(lambda: len(self.live_procs(node, "k")) == 1, 5, "恢復後槽裡不是剛好一個活程序")
        rounds = [s["round"] for s in sums]
        self.assertEqual(rounds, list(range(1, len(sums) + 1)), "回合跳號：%r" % rounds)

    def _round_json(self, e):
        """round.json 讀不到：tick 3、tock 3，什麼都沒寫；拿掉後回合連續。"""
        node = self.mknode("a", [{"name": "j", "argv": ["true"]}])
        self.itick()
        self.settle(node, "j")
        self.itock()
        rp = os.path.join(node, ".aos", "round.json")
        before = self.raw(rp)
        rc, out, err = self.run_prog("aos7-tick", env={"AOS7_TEST_FAULT": "open:*/.aos/round.json:%s" % e})
        self.assertEqual(rc, 3, err)
        self.assertIn("unknown", out or {})
        self.assertEqual(self.raw(rp), before, "round.json 讀不到時 tick 還是寫了")
        self.assertEqual(self.birth(node, "j")["run"], 1)
        self.itick()
        before = self.raw(rp)
        rc, out, err = self.run_prog("aos7-tock", env={"AOS7_TEST_FAULT": "open:*/.aos/round.json:%s" % e})
        self.assertEqual(rc, 3, err)
        self.assertEqual(self.raw(rp), before, "round.json 讀不到時 tock 還是寫了")
        self.assertEqual(self.last_round(node)["round"], 1)
        self.assertEqual(self.itock()["round"], 2)
        self.assertEqual(self.itick()["round"], 3)

    def _last_round(self, e):
        """last-round.json 讀不到：tock 3（判斷不了這回合總結寫過沒），回合不關；拿掉後關上第 N 回合。"""
        node = self.mknode("a")
        self.itick()
        self.itock()
        self.itick()
        lp = os.path.join(node, ".aos", "last-round.json")
        before = self.raw(lp)
        rc, _out, err = self.run_prog("aos7-tock", env={"AOS7_TEST_FAULT": "open:*/.aos/last-round.json:%s" % e})
        self.assertEqual(rc, 3, err)
        self.assertEqual(self.raw(lp), before)
        self.assertIs(self.round_json(node)["open"], True)
        lr = self.itock()
        self.assertEqual(lr["round"], 2)
        self.assertFalse(lr.get("replayed"))
        self.assertEqual(self.itick()["round"], 3)

    def _listdir(self, e):
        """`.aos/tasks` 列不出來：tick 3、tock 3，什麼都沒寫；拿掉後恢復。"""
        node = self.mknode("a", [{"name": "j", "argv": ["true"]}])
        self.itick()
        self.settle(node, "j")
        self.itock()
        rp = os.path.join(node, ".aos", "round.json")
        before = self.raw(rp)
        rule = {"AOS7_TEST_FAULT": "listdir:*/.aos/tasks:%s" % e}
        rc, _out, err = self.run_prog("aos7-tick", env=rule)
        self.assertEqual(rc, 3, err)
        self.assertEqual(self.raw(rp), before)
        self.itick()
        before = self.raw(rp)
        rc, _out, err = self.run_prog("aos7-tock", env=rule)
        self.assertEqual(rc, 3, err)
        self.assertEqual(self.raw(rp), before)
        self.assertEqual(self.itock()["round"], 2)
        self.assertEqual(self.itick()["round"], 3)


gen(TestFileUnknown, "slotfile", [("%s_%s" % (f.split(".")[0], e), (f, e))
                                  for f in ("birth.json", "exit.json", "pid.json") for e in ERRNOS],
    TestFileUnknown._slot_file)
gen(TestFileUnknown, "round_json", [(e, (e,)) for e in ERRNOS], TestFileUnknown._round_json)
gen(TestFileUnknown, "last_round_json", [(e, (e,)) for e in ERRNOS], TestFileUnknown._last_round)
gen(TestFileUnknown, "listdir_tasks", [(e, (e,)) for e in ERRNOS], TestFileUnknown._listdir)


class TestDaemonStatUnknown(MatrixCase):
    def _stat(self, e):
        """daemon 看已登記 node 的 stat 讀不到：時間線保留、不進 missing、不起 reaper，last_error 帶 errno 類型。"""
        node = self.mknode("a")
        d = aos7_daemon.Daemon(self.root)
        self.addCleanup(os.close, d.rfd)
        d.registry = {"a": {}}
        st = os.lstat(node)
        tl = aos7_daemon_timeline.Timeline(d, "a", (st.st_dev, st.st_ino))   # 不 start：只看 check_nodes 怎麼對待它
        d.timelines["a"] = tl
        with fault("stat:%s:%s" % (node, e)):
            d.check_nodes()
        self.assertIs(d.timelines.get("a"), tl, "看不到 node 就丟掉時間線")
        self.assertNotIn("a", d.missing)
        self.assertNotIn("a", d.reapers)
        self.assertFalse(tl.gone)
        le = tl.last_error or {}
        err = le.get("err", "")
        # 契約（隊長 10-04）：errno 類型放在 last_error 的 kind（errno 名）；err 文字裡帶也算
        self.assertTrue(le.get("kind") == e or e in err or "Errno %d" % getattr(errno, e) in err,
                        "last_error 沒有 errno 類型：%r" % tl.last_error)


gen(TestDaemonStatUnknown, "node_stat", [(e, (e,)) for e in ERRNOS], TestDaemonStatUnknown._stat)


if __name__ == "__main__":
    unittest.main()
