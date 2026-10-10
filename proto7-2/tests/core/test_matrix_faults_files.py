from _matrix_faults import *  # noqa: F403


class TestFileUnknown(MatrixCase):
    """〔core〕"""
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

    def _last_round_readback(self, status):
        """T8-05：第 2 次讀才注入，避開讀舊總結，證明寫後整份讀回失敗時不關回合、不收尾，解除後重播。"""
        node = self.mknode("a", [{"name": "j", "argv": ["true"]}])
        self.itick()
        self.settle(node, "j")
        self.itock()
        self.assertEqual(self.itick()["round"], 2)
        self.settle(node, "j")
        lpath = os.path.join(node, ".aos", "last-round.json")
        orig = aos7_tock.fact
        reads = 0

        def fact(path, *args, **kwargs):
            nonlocal reads
            if str(path).endswith("/.aos/last-round.json"):
                reads += 1
                if reads == 2:
                    st, back = orig(path, *args, **kwargs)
                    self.assertEqual(st, aos7_fs.OK)
                    self.assertEqual(back["round"], 2)
                    if status == aos7_fs.OK:
                        changed = dict(back, tock_at=back["tock_at"] + "（注入）")
                        self.assertEqual(changed["round"], back["round"])
                        self.assertNotEqual(changed, back)
                        return status, changed
                    return status, "注入"
            return orig(path, *args, **kwargs)

        with mock.patch.object(aos7_tock, "fact", side_effect=fact):
            with self.assertRaises(aos7_tock.Unknown) as raised:
                self.itock()
            self.assertEqual(raised.exception.kind, "readback")
            self.assertEqual(reads, 2, "沒有命中寫後讀回點")
        self.assertIs(self.round_json(node)["open"], True)
        notice = read_json(os.path.join(self.slot(node, "j"), "tock.json"))
        self.assertNotEqual((notice or {}).get("round"), 2, "讀回失敗仍通知了第 2 回合")
        ex = self.exit_raw(node, "j")
        self.assertIsNotNone(ex, "已結束任務的結果被刪了")
        self.assertNotEqual(ex.get("seen_round"), 2, "讀回失敗仍做了收尾")
        committed = read_json(lpath)
        self.assertEqual(committed["round"], 2)
        self.assertTrue(aos7_fs.summary_ok(committed), "第 2 回合總結沒有完整落地")
        lr = self.itock()
        self.assertTrue(lr.get("replayed"))
        self.assertEqual(lr["round"], 2)
        self.assertIs(self.round_json(node)["open"], False)
        self.assertEqual(self.exit_raw(node, "j")["seen_round"], 2)
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
gen(TestFileUnknown, "last_round_readback", [(name, (status,)) for name, status in
    (("U", aos7_fs.U), ("BAD", aos7_fs.BAD), ("OK_same_round", aos7_fs.OK))],
    TestFileUnknown._last_round_readback)
gen(TestFileUnknown, "listdir_tasks", [(e, (e,)) for e in ERRNOS], TestFileUnknown._listdir)


if __name__ == "__main__":
    unittest.main()
