from _daemon import *  # noqa: F403


class TestDaemonSaveFailures(DaemonCase):
    """〔core〕存檔失敗保守暫停，故障解除後主迴圈自動補寫。"""

    def daemon(self):
        d = aos7_daemon.Daemon(self.root)
        self.addCleanup(os.close, d.rfd)
        return d

    def test_mark_owe_save_failure_restores_previous_zero_base(self):
        d = self.daemon()
        d.steps, d.owe = {"a": {"k": 2}}, {"a": 0}
        with mock.patch.object(d, "save_paused", side_effect=OSError("disk unavailable")):
            self.assertFalse(d.mark_owe("a", 1))
        self.assertEqual(d.owe, {"a": 0})

    def test_stop_repairs_dirty_paused_before_final_status(self):
        d = self.daemon()
        path = os.path.join(self.root, ".aosd", "paused.json")
        write_json(path, {"paused": {}, "steps": {"a": {"k": 2}}, "owe": {"a": 0}})

        def stop_with_dirty_removal():
            d.steps.clear()
            d.owe.clear()
            d._paused_dirty = True
            d.stop(False)

        with warnings.catch_warnings(), mock.patch.object(aos7_daemon.signal, "signal"), \
                mock.patch.object(d, "handle_ctl", side_effect=stop_with_dirty_removal):
            warnings.simplefilter("ignore", ResourceWarning)
            self.assertEqual(d.run(), 0)
        self.assertFalse(d._paused_dirty)
        self.assertEqual(read_json(path), {"paused": {}, "steps": {}})
        self.assertTrue(self.status()["stopped"])

    def test_closed_round_save_failure_holds_owe_until_recovery(self):
        node = self.mknode("a", interval_ms=2000)
        path = os.path.join(self.root, ".aosd", "paused.json")
        write_json(path, {"paused": {}, "steps": {"a": {"k": 2}}})
        rules = os.path.join(self.root, "fault-rules.txt")
        fault = Fault("@" + rules, ops={"write"})
        self.addCleanup(fault.close)
        self.start_daemon(env=fault.env, register=["a"])
        self.wait_for(lambda: self.round_json(node).get("open") and
                      (read_json(path) or {}).get("owe") == {"a": 0}, 3)
        initial = read_json(path)
        with open(rules, "w") as fh:
            fh.write("write:*/.aosd/paused.json:EIO\n")
        self.wait_for(lambda: fault.hits("write") >= 1, 3)
        self.wait_for(lambda: not self.round_json(node).get("open"), 2)
        time.sleep(0.1)  # 留一圈 status 更新，故障期間倒數仍是原值
        fault.check_rules(where="（關回合後結算）")
        self.assertFalse(self.round_json(node)["open"])
        self.assertEqual(self.round_json(node)["round"], 1)
        self.assertEqual(read_json(path), initial)
        self.assertEqual(self.nstat().get("steps_left"), {"k": 2})
        self.wait_for(lambda: fault.hits("write") >= 3, 2, "結算存檔失敗沒有重試")
        time.sleep(0.15)
        self.assertEqual(self.round_json(node)["round"], 1, "結算沒存進去卻 mark_owe/tick 下一回合")
        self.assertEqual(read_json(path)["owe"], {"a": 0}, "舊 owe 被下一回合蓋掉")
        os.remove(rules)
        self.wait_for(lambda: self.nstat().get("phase") == "paused", 3)
        self.assertEqual(self.round_json(node)["round"], 2)
        self.assertEqual(read_json(path), {"paused": {"a": ["k"]}, "steps": {}})
        time.sleep(0.1)
        self.assertEqual(self.round_json(node)["round"], 2)

    def test_pause_resume_pending_settlement_refuses_without_mutation_or_wake(self):
        d = self.daemon()
        path = os.path.join(self.root, ".aosd", "paused.json")
        for pending in (True, False):
            for op in ("pause", "resume"):
                with self.subTest(op=op, settle_pending=pending):
                    d.timelines["a"] = SimpleNamespace(settle_pending=pending)
                    d.paused, d.steps, d.owe = {"a": ["k"]}, {"a": {"k": 3}}, {"a": 0}
                    d.save_paused()
                    before = copy.deepcopy((d.paused, d.steps, d.owe))
                    with open(path, "rb") as fh:
                        disk = fh.read()
                    ctl = {"owner": "k", **({"rounds": 1} if op == "resume" else {})}
                    with mock.patch.object(d, "save_paused") as save, mock.patch.object(d, "_kick") as kick:
                        ok, msg = getattr(d, "op_" + op)("a", ctl)
                        self.assertFalse(ok)
                        self.assertEqual(msg, "a 上一回合的倒數結算還沒寫進 paused.json，%s 沒有改；稍後重送" % op)
                        self.assertEqual((d.paused, d.steps, d.owe), before)
                        with open(path, "rb") as fh:
                            self.assertEqual(fh.read(), disk)
                        save.assert_not_called()
                        kick.assert_not_called()

    def test_pause_resume_save_failure_returns_false_without_mutation_or_wake(self):
        d = self.daemon()
        path = os.path.join(self.root, ".aosd", "paused.json")
        cases = (("pause", {}, {"owner": "k"}),
                 ("resume", {"a": ["k", "other"]}, {"owner": "k", "all": True, "rounds": 2}))
        for error, (op, paused, ctl) in ((e, c) for e in (OSError("disk unavailable"), aos7_daemon.Unknown("unknown")) for c in cases):
            with self.subTest(op=op, error=type(error).__name__):
                d.paused = copy.deepcopy(paused)
                d.steps, d.owe = {"a": {"k": 3}}, {"a": 4}
                d.save_paused()
                before = copy.deepcopy((d.paused, d.steps, d.owe))
                disk = read_json(path)
                with mock.patch.object(d, "save_paused", side_effect=error), \
                        mock.patch.object(d, "_kick") as kick:
                    ok, msg = d.apply(dict(op=op, node="a", **ctl))
                    self.assertFalse(ok)
                    self.assertIn("請重送", msg)
                    self.assertEqual((d.paused, d.steps, d.owe), before)
                    self.assertEqual(read_json(path), disk)
                    kick.assert_not_called()
                with mock.patch.object(d, "_kick") as kick:
                    self.assertTrue(d.apply(dict(op=op, node="a", **ctl))[0])
                    self.assertNotEqual(read_json(path), disk)
                    if op == "resume":
                        kick.assert_called_once_with("a")

    def test_pause_resume_save_failure_receipts_are_ok_false(self):
        path = os.path.join(self.root, ".aosd", "paused.json")
        write_json(path, {"paused": {"a": ["k"]}, "steps": {}})
        rules = os.path.join(self.root, "fault-rules.txt")
        fault = Fault("@" + rules, ops={"write"})
        self.addCleanup(fault.close)
        self.start_daemon(env=fault.env)
        self.wait_for(lambda: self.status().get("pid"), 3)
        initial = read_json(path)
        with open(rules, "w") as fh:
            fh.write("write:*/.aosd/paused.json:EIO\n")
        for op in ("pause", "resume"):
            receipt = self.wait_receipt(self.ctl(op, "a", "--owner", "k"), 2)
            self.assertFalse(receipt["result"]["ok"])
            self.assertIn("請重送", receipt["result"]["msg"])
            self.assertEqual(read_json(path), initial)
        fault.check_rules()
        os.remove(rules)
        self.assertTrue(self.wait_receipt(self.ctl("resume", "a", "--owner", "k"), 2)["result"]["ok"])
        self.assertEqual(read_json(path)["paused"], {})

    def test_removed_steps_save_failure_is_repaired_without_control_request(self):
        for gone in (False, True):
            with self.subTest(node_gone=gone):
                d = self.daemon()
                d.registry = {"a": {}}
                d.steps, d.owe = {"a": {"k": 2}}, {"a": 0}
                d.save_nodes()
                d.save_paused()
                path = os.path.join(self.root, ".aosd", "paused.json")
                with mock.patch.object(d, "save_paused", side_effect=OSError("disk unavailable")), \
                        mock.patch.object(d, "reap"):
                    if gone:
                        d.timelines["a"] = SimpleNamespace(is_alive=lambda: False, wake=threading.Event())
                        d.check_nodes()
                    else:
                        self.assertTrue(d.op_unregister("a", {"kill": False})[0])
                self.assertEqual(d.steps, {})
                self.assertEqual(d.owe, {})
                self.assertEqual(read_json(path)["steps"], {"a": {"k": 2}})
                self.assertTrue(d._paused_dirty)
                d.check_nodes()
                self.assertFalse(d._paused_dirty)
                self.assertEqual(read_json(path), {"paused": {}, "steps": {}})

    def test_stop_held_intent_save_failure_retries_and_warns_with_bounded_wait(self):
        d = self.daemon()
        d.registry, d._kill_unsure = {"a": {}}, {"a"}
        stderr = io.StringIO()
        with mock.patch.object(d, "kill_live", return_value=False), \
                mock.patch.object(aos7_proc, "kill_node", return_value=(0, True)), \
                mock.patch.object(d, "save_nodes", side_effect=OSError("disk unavailable")) as save, \
                mock.patch.object(sys, "stderr", stderr), mock.patch.object(d, "log") as log:
            start = time.monotonic()
            d.sweep_leftovers()
            elapsed = time.monotonic() - start
        self.assertGreater(save.call_count, 1, "held 回收意圖沒有重試落盤")
        self.assertLess(elapsed, 3)
        self.assertIn("回收意圖寫不進 nodes.json", stderr.getvalue())
        self.assertIn("重開後不會續收：a", stderr.getvalue())
        self.assertTrue(any(c.kwargs.get("ev") == "nodes-save-error" for c in log.call_args_list))
        self.assertIn("a", d.reaping)



if __name__ == "__main__":
    unittest.main()
