from _matrix_faults import *  # noqa: F403


class TestProcUnknown(MatrixCase):
    """〔core〕"""
    def _healthy(self, op, e):
        """/proc 讀不到、任務其實健康地活著：不殺、不起、不判 lost；同樣故障下的 kill 控制回 unknown、不殺；拿掉注入自動回正。"""
        node = self.mknode("a", [keep_item()])
        self.itick()
        pid = self.wait_pid(node, "k")["pid"]
        self.itock()
        runner = (self.birth(node, "k").get("runner") or {}).get("pid")
        ctl_path = os.path.join(self.slot(node, "k"), "ctl.json")
        with fault(proc_rules(op, [pid, runner], e)) as f:
            v = self.view(node, "k", 2)
            self.assertEqual(v.state, aos7_task.LIVE, v)
            if op == "proc-stat":
                self.assertTrue(v.get("unsure"), "pid／starttime 讀不到要判 LIVE＋unsure：%r" % v)
            out = self.itick()
            lr = self.itock()
            # 已知 pid／runner 活著的判定走捷徑，proc-list／environ／cmdline 不一定會讀到（astra-2：命中 0 次）。
            # kill 一定要身分掃描（Q1 範圍、A3-09 再看一次 pid.json 的任務）→ 在同樣的故障下送一份 kill 控制，證明讀取失敗＝不知道
            with open(ctl_path, "w") as fh:
                json.dump({"op": "kill", "run": 1, "by": "t"}, fh)
            before = f.hits(op)
            out2 = self.itick()
            self.assertGreater(f.hits(op), before, "kill 控制沒有打中 %s 的注入（命中 %r）" % (op, f.records()))
            lr2 = self.itock()
        self.assertEqual(out["started"], [], "讀不到 /proc 時起了新的 run（雙開）")
        self.assertEqual(out2["started"], [], "讀不到 /proc 時（kill 控制那回合）起了新的 run")
        self.assertTrue(alive(pid), "讀不到 /proc 時把活任務殺了（kill 控制在掃描不完整時不能動手）")
        self.assertEqual(self.birth(node, "k")["run"], 1)
        self.assertIsNone(self.exit_raw(node, "k"), "讀不到 /proc 時寫了 exit.json")
        self.assertIn("k#1", lr["alive"])
        self.assertIn("k#1", lr2["alive"])
        if v.get("unsure"):
            errs = self.errors_for(lr, "k")
            self.assertTrue(any(x.get("where") == "judge" and x.get("why") for x in errs),
                            "unsure 的槽要在 tock 的 errors 留一筆：%r" % lr.get("errors"))
        # kill 控制：回合總結的 ctl 紀錄 ok:false；回條 ctl-done.json 的 result.ok false、訊息帶 unknown；請求已消費
        recs = [c for c in (lr2.get("ctl") or []) if c.get("slot") == "k"]
        self.assertEqual([(c.get("op"), c.get("ok")) for c in recs], [("kill", False)], "回合總結的 ctl：%r" % lr2.get("ctl"))
        done = self.raw(os.path.join(self.slot(node, "k"), "ctl-done.json"))
        self.assertIsNotNone(done, "kill 控制沒有回條")
        res = json.loads(done).get("result") or {}
        self.assertIs(res.get("ok"), False, res)
        self.assertIn("unknown", res.get("msg", ""), "掃描不完整的 kill 回條要說 unknown：%r" % res)
        self.assertFalse(os.path.exists(ctl_path), "處理過的 ctl.json 沒有消費掉")
        # 拿掉注入：自動回正（同一個 pid、執行一次；ok:false 的那件已記在 ctl-seen，不會再被執行）
        self.assertEqual(self.itick()["started"], [])
        lr3 = self.itock()
        self.assertEqual([c for c in (lr3.get("ctl") or []) if c.get("slot") == "k"], [], "kill 控制被重做了")
        self.assertIn("k#1", lr3["alive"])
        self.assertTrue(alive(pid))
        self.assertEqual(self.wait_pid(node, "k")["pid"], pid)
        self.assertEqual(self.birth(node, "k")["run"], 1)
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
            self.assertTrue(any(x.get("where") == "judge" and x.get("why")
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
            self.assertTrue(any(x.get("where") == "judge" and x.get("why")
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

    def test_kill_identity_incomplete_scan(self):
        """掃描不完整：env_procs 丟 Unknown、kill_identity 回 (False, 說明)，不殺。"""
        node = self.mknode("a", [keep_item()])
        self.itick()
        pid = self.wait_pid(node, "k")["pid"]
        with fault("proc-list:/proc:EIO"):
            with self.assertRaises(aos7_fs.Unknown):
                aos7_proc.env_procs(node, "k")
            ok, msg = aos7_proc.kill_identity(node, "k", 1)
        self.assertIs(ok, False)
        self.assertIsInstance(msg, str)
        self.assertTrue(msg)
        self.assertTrue(alive(pid))


gen(TestProcUnknown, "healthy", [("%s_%s" % (op, e), (op, e)) for op in PROC_OPS for e in ERRNOS],
    TestProcUnknown._healthy)
# environ 的 EACCES＝不是可辨認的任務（略過）；cmdline 的 EACCES 一律不知道。orphan 的 environ × EACCES 是任務自己變得不可讀
#（誤用 M-2.8，已刪）；其餘 11 組照跑。deadboth 的 environ × EACCES 另外是 deadboth_skip：任務真的死了 → 照常判 lost 一次。
UNSURE_SCAN = [(op, e) for op in PROC_OPS for e in ERRNOS]
gen(TestProcUnknown, "orphan", [("%s_%s" % (op, e), (op, e)) for op, e in UNSURE_SCAN
                                if (op, e) != ("proc-environ", "EACCES")], TestProcUnknown._orphan)
gen(TestProcUnknown, "deadboth", [("%s_%s" % (op, e), (op, e)) for op, e in UNSURE_SCAN
                                  if op in ("proc-list", "proc-environ")
                                  and not (op == "proc-environ" and e == "EACCES")], TestProcUnknown._deadboth)


if __name__ == "__main__":
    unittest.main()
