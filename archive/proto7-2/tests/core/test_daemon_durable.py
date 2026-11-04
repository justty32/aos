from _daemon import *  # noqa: F403


class TestDaemonDurableRecovery(DaemonCase):
    """〔core〕"""
    KEEP = {"name": "s", "mode": "keep", "argv": [sys.executable, "-c",
            "import os,signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);"
            "open(os.path.join(os.environ['AOS7_TASK'],'ready'),'w').close();time.sleep(600)"]}

    def nodes_state(self):
        return read_json(os.path.join(self.root, ".aosd", "nodes.json"), {}) or {}

    def ready_task(self, node):
        self.wait_for(lambda: os.path.exists(os.path.join(self.slot(node, "s"), "ready")),
                      msg="任務沒有裝好忽略 SIGTERM 的 handler")
        identity = self.wait_pid(node, "s")
        self.assertIsNotNone(identity.get("starttime"))
        self.assertEqual(self.task_state(identity), aos7_proc.ALIVE)
        return identity

    def task_state(self, identity):
        return aos7_proc.same_process(identity["pid"], identity["starttime"])

    def wait_reaped(self, identity):
        self.wait_for(lambda: self.task_state(identity) == aos7_proc.GONE, 15, "舊 pid＋starttime 仍活著")
        self.wait_for(lambda: "reaping" not in self.nodes_state(), 10, "收乾淨後 reaping 沒清掉")

    def nodes_write_fault(self):
        """nodes.json 寫檔失敗（D3 的 inject("write")）：回 (Fault, 規則檔)；寫規則檔＝開、刪掉＝關。"""
        rules = os.path.join(self.root, "fault-rules.txt")
        fault = Fault("@" + rules, ops={"write"})
        self.addCleanup(fault.close)
        return fault, rules

    def test_unregister_write_failure_is_retryable(self):
        node = self.mknode("a", [self.KEEP])
        fault, rules = self.nodes_write_fault()
        self.start_daemon(env=fault.env, register=["a"])
        identity = self.ready_task(node)
        self.wait_for(lambda: self.nstat().get("round"))
        with open(rules, "w") as fh:
            fh.write("write:*/.aosd/nodes.json:EIO\n")
        result = self.wait_receipt(self.ctl("unregister", "a"))["result"]
        fault.check_rules(where="（unregister 寫 nodes.json）")
        self.assertFalse(result["ok"])
        self.assertIn("nodes.json", result["msg"])
        self.assertIn("a", self.nodes_state()["nodes"])
        self.assertNotIn("reaping", self.nodes_state())
        self.assertTrue(self.nstat().get("round"), "寫檔失敗後時間線丟了")
        self.assertNotEqual(self.nstat().get("phase"), "unregistering")
        os.remove(rules)
        time.sleep(0.3)
        self.assertEqual(self.task_state(identity), aos7_proc.ALIVE)
        self.assertTrue(self.wait_receipt(self.ctl("unregister", "a"))["result"]["ok"])   # 重送：不被記憶體短路
        self.wait_reaped(identity)
        self.assertNotIn("a", self.nodes_state()["nodes"])

    def test_register_write_failure_is_retryable(self):
        node = self.mknode("a")
        fault, rules = self.nodes_write_fault()
        self.start_daemon(env=fault.env)
        self.wait_for(lambda: self.status().get("pid"))
        with open(rules, "w") as fh:
            fh.write("write:*/.aosd/nodes.json:EIO\n")
        result = self.wait_receipt(self.ctl("register", "a"))["result"]
        fault.check_rules(where="（register 寫 nodes.json）")
        self.assertFalse(result["ok"])
        self.assertIn("nodes.json", result["msg"])
        self.assertNotIn("a", self.nodes_state().get("nodes", {}))
        os.remove(rules)
        time.sleep(0.3)
        self.assertNotIn("a", self.status()["nodes"])
        self.assertFalse(os.path.exists(os.path.join(node, ".aos", "round.json")))
        self.assertTrue(self.wait_receipt(self.ctl("register", "a"))["result"]["ok"])
        self.wait_round(2)
        self.assertIn("a", self.nodes_state()["nodes"])

    def test_unregister_crash_before_kill_resumes(self):
        node = self.mknode("a", [self.KEEP])
        p = self.start_daemon(env={"AOS7_TEST_CRASH": "reap-before-kill"}, register=["a"])
        identity = self.ready_task(node)
        self.ctl("unregister", "a")
        self.assertEqual(p.wait(10), -signal.SIGKILL, "回收測試點沒打中")
        self.assertIn("a", self.nodes_state()["reaping"])
        self.assertNotIn("a", self.nodes_state()["nodes"])
        self.assertEqual(self.task_state(identity), aos7_proc.ALIVE)
        self.start_daemon()
        self.wait_reaped(identity)

    def test_unregister_external_sigkill_resumes(self):
        node = self.mknode("a", [self.KEEP])
        p = self.start_daemon(register=["a"])
        identity = self.ready_task(node)
        self.assertTrue(self.wait_receipt(self.ctl("unregister", "a"))["result"]["ok"])
        self.wait_for(lambda: "a" in self.nodes_state().get("reaping", {}))
        os.kill(p.pid, signal.SIGKILL)
        self.assertEqual(p.wait(10), -signal.SIGKILL)
        self.assertEqual(self.task_state(identity), aos7_proc.ALIVE, "沒打在 TERM 寬限內")
        self.assertIn("a", self.nodes_state()["reaping"])
        self.start_daemon()
        self.wait_reaped(identity)

    def test_replaced_node_crash_reaps_before_new_birth(self):
        node = self.mknode("a", [self.KEEP])
        p = self.start_daemon(env={"AOS7_TEST_CRASH": "reap-before-kill"}, register=["a"])
        identity = self.ready_task(node)
        os.rename(node, os.path.join(self.root, "old"))
        self.mknode("a", [self.KEEP])
        self.assertEqual(p.wait(10), -signal.SIGKILL, "node 替換沒打中回收測試點")
        self.assertIn("a", self.nodes_state()["reaping"])
        self.assertEqual(self.task_state(identity), aos7_proc.ALIVE)
        self.assertFalse(self.birth(node, "s"))
        self.start_daemon()

        def new_birth_after_old_died():
            birth = self.birth(node, "s")
            if birth:
                self.assertEqual(self.task_state(identity), aos7_proc.GONE, "新 birth 出現時舊任務還活著")
            return birth

        self.wait_for(new_birth_after_old_died, 15, "舊任務收完後沒有新 birth")
        fresh = self.ready_task(node)
        self.assertNotEqual((fresh["pid"], fresh["starttime"]), (identity["pid"], identity["starttime"]))
        self.wait_reaped(identity)
        self.assertEqual(self.task_state(fresh), aos7_proc.ALIVE)

    def test_incomplete_reap_holds_missing_until_scan_recovers(self):
        node = self.mknode("a", [self.KEEP])
        rules = os.path.join(self.root, "fault-rules.txt")
        fault = Fault("@" + rules, ops={"proc-list"})
        self.addCleanup(fault.close)
        self.start_daemon(env=fault.env, register=["a"])
        identity = self.ready_task(node)
        self.assertEqual(fault.hits(), 0)
        # 必須先開故障，再換 inode，否則第一次回收可能已經判乾淨。
        with open(rules, "w") as fh:
            fh.write("proc-list:/proc:EIO\n")
        os.rename(node, os.path.join(self.root, "old"))
        self.mknode("a", [self.KEEP])
        self.wait_for(lambda: fault.hits("proc-list") > 0)
        self.wait_for(lambda: self.nstat().get("phase") == "missing")
        self.wait_for(lambda: "a" in self.nodes_state().get("reaping", {}))
        end = time.monotonic() + 2.2
        while time.monotonic() < end:
            self.assertEqual(self.nstat().get("phase"), "missing")
            self.assertFalse(os.path.exists(os.path.join(node, ".aos", "round.json")))
            self.assertIn("a", self.nodes_state()["reaping"])
            time.sleep(0.05)
        fault.check(where="（收不乾淨不得重開時間線）")
        os.remove(rules)
        self.wait_reaped(identity)
        fresh = self.ready_task(node)
        self.assertEqual(self.task_state(fresh), aos7_proc.ALIVE)
        self.wait_round(1)

    def test_live_pid_read_failure_retains_known_pgid(self):
        node = self.mknode("a", [self.KEEP])
        self.tick()
        identity = self.ready_task(node)
        d = aos7_daemon.Daemon(self.root)
        self.addCleanup(os.close, d.rfd)
        timeline = SimpleNamespace(node=node, round=1)
        self.assertEqual(aos7_task.judge(self.slot(node, "s"), node, "s", 1).state, aos7_task.LIVE)
        d.live_of("a", timeline)
        self.assertIn(identity["pgid"], d._pgids["a"])
        d._live.clear()
        original = aos7_daemon.read_json
        reads = []

        def unreadable_pid(path, *args, **kwargs):
            if path == os.path.join(self.slot(node, "s"), "pid.json"):
                reads.append(path)
                return None
            return original(path, *args, **kwargs)

        with mock.patch.object(aos7_daemon, "read_json", side_effect=unreadable_pid):
            self.assertIn("s#1", d.live_of("a", timeline))
        self.assertTrue(reads, "LIVE 之後的 pid.json 讀取故障沒有打中")
        self.assertIn(identity["pgid"], d._pgids["a"])

    def test_steps_resume_remaining_rounds_after_sigkill(self):
        node = self.mknode("a", interval_ms=1500, early=True)
        p = self.start_daemon(register=["a"])
        self.wait_receipt(self.ctl("pause", "a", "--owner", "k"))
        self.wait_for(lambda: self.nstat().get("phase") == "paused")
        before = self.node_round()
        self.assertTrue(self.wait_receipt(self.ctl("resume", "a", "--owner", "k", "--rounds", "3"))["result"]["ok"])
        paused_path = os.path.join(self.root, ".aosd", "paused.json")

        def remaining():
            return ((read_json(paused_path) or {}).get("steps", {}).get("a") or {}).get("k")

        self.wait_for(lambda: remaining() == 2, 10, "關上一回合後 steps=2 沒落盤")
        self.assertFalse(self.round_json(node)["open"])
        os.kill(p.pid, signal.SIGKILL)
        self.assertEqual(p.wait(10), -signal.SIGKILL)
        self.assertEqual(remaining(), 2)
        self.assertEqual(self.last_round(node)["round"], before + 1)
        self.start_daemon()
        self.wait_for(lambda: self.nstat().get("phase") == "paused" and self.node_round() == before + 3,
                      15, "重起後沒有只跑剩餘兩回合")
        self.assertEqual(self.nstat()["paused_by"], ["k"])
        self.assertNotIn("steps_left", self.nstat())
        self.assertNotIn("a", (read_json(paused_path) or {}).get("steps", {}))
        time.sleep(0.2)
        self.assertEqual(self.node_round(), before + 3)

    def test_steps_closed_before_save_three_crashes(self):
        node = self.mknode("a", interval_ms=50, early=True)
        self.round_trip()
        before = self.round_json(node)["round"]
        path = os.path.join(self.root, ".aosd", "paused.json")
        write_json(path, {"paused": {"a": ["k"]}, "steps": {}})
        p = self.start_daemon(env={"AOS7_TEST_CRASH": "round-closed-before-steps"}, register=["a"])
        self.wait_for(lambda: self.nstat().get("phase") == "paused")
        self.wait_receipt(self.ctl("resume", "a", "--owner", "k", "--rounds", "3"))
        for i in range(3):
            with self.subTest(crash=i + 1):
                self.assertEqual(p.wait(10), -signal.SIGKILL)
                self.assertFalse(self.round_json(node)["open"])
                self.assertEqual(self.round_json(node)["round"], before + i + 1)
                state = read_json(path)
                self.assertEqual(state["steps"], {"a": {"k": 3 - i}})
                self.assertEqual(state["owe"], {"a": before + i})
                p = self.start_daemon(env={"AOS7_TEST_CRASH": "round-closed-before-steps"} if i < 2 else {})
        self.wait_for(lambda: self.nstat().get("phase") == "paused", 10)
        self.assertEqual(self.nstat()["paused_by"], ["k"])
        self.assertEqual(read_json(path), {"paused": {"a": ["k"]}, "steps": {}})
        time.sleep(0.2)
        self.assertEqual(self.round_json(node)["round"], before + 3)

    def test_steps_open_round_recovery_debits_once(self):
        node = self.mknode("a", interval_ms=50)
        self.tick()   # 模擬 daemon 在 tick 開回合後死亡的磁碟狀態
        path = os.path.join(self.root, ".aosd", "paused.json")
        write_json(path, {"paused": {}, "steps": {"a": {"k": 1}}, "owe": {"a": 0}})
        self.start_daemon(register=["a"])
        self.wait_for(lambda: self.nstat().get("phase") == "paused", 10)
        self.assertFalse(self.round_json(node)["open"])
        self.assertEqual(self.nstat()["paused_by"], ["k"])
        self.assertEqual(read_json(path), {"paused": {"a": ["k"]}, "steps": {}})
        time.sleep(0.2)
        self.assertEqual(self.round_json(node)["round"], 1)

    def test_mark_owe_save_failure_retries_same_base(self):
        d = aos7_daemon.Daemon(self.root)
        self.addCleanup(os.close, d.rfd)
        d.steps = {"a": {"k": 2}}
        with mock.patch.object(d, "save_paused", side_effect=[OSError("disk unavailable"), None]) as save:
            self.assertFalse(d.mark_owe("a", 4))
            self.assertEqual(d.owe, {})
            self.assertTrue(d.mark_owe("a", 4))
        self.assertEqual(save.call_count, 2)

    def test_mark_owe_without_pending_write_succeeds(self):
        d = aos7_daemon.Daemon(self.root)
        self.addCleanup(os.close, d.rfd)
        for steps, owe in (({}, {}), ({"a": {"k": 2}}, {"a": 4})):
            with self.subTest(steps=steps, owe=owe):
                d.steps, d.owe = steps, owe
                with mock.patch.object(d, "save_paused") as save:
                    self.assertTrue(d.mark_owe("a", 4))
                    save.assert_not_called()

    def test_steps_owe_write_failure_holds_round_until_recovery(self):
        """待結算寫不進去不 tick；恢復後只跑原額度，沒有倒數的 node 照跑。"""
        node = self.mknode("a", interval_ms=50, early=True)
        self.mknode("b", interval_ms=50, early=True)
        os.makedirs(os.path.join(self.root, ".aosd"))
        path = os.path.join(self.root, ".aosd", "paused.json")
        initial = {"paused": {}, "steps": {"a": {"k": 2}}}
        write_json(path, initial)
        with open(os.path.join(self.root, ".aosd", "log.on"), "w"):
            pass
        rules = os.path.join(self.root, "fault-rules.txt")
        fault = Fault("@" + rules, ops={"write"})
        self.addCleanup(fault.close)
        self.start_daemon(env=fault.env)
        self.wait_for(lambda: self.status().get("pid"))   # 啟動的首份 paused.json 先成功落盤
        with open(rules, "w") as fh:
            fh.write("write:*/.aosd/paused.json:EIO\n")
        self.assertTrue(self.wait_receipt(self.ctl("register", "a"))["result"]["ok"])
        self.assertTrue(self.wait_receipt(self.ctl("register", "b"))["result"]["ok"])
        self.wait_for(lambda: fault.hits("write") >= 3, msg="沒有重試保存 owe")
        fault.check_rules(where="（開回合前保存 owe）")
        end = time.monotonic() + 0.2
        while time.monotonic() < end:
            self.assertEqual(self.round_json(node).get("round", 0), 0, "owe 沒落盤卻開了回合")
            self.assertEqual(read_json(path), initial, "保存失敗改了磁碟上的倒數")
            time.sleep(0.02)
        self.wait_round(2, "b")   # steps 空的 node 不受 paused.json 故障擋住
        events = read_jsonl(os.path.join(self.root, ".aosd", "log.jsonl"))
        self.assertTrue(any(e.get("ev") == "paused-save-error" and e.get("node") == "a" for e in events))
        os.remove(rules)
        self.wait_for(lambda: self.nstat().get("phase") == "paused", 10, "寫入恢復後倒數沒有跑完")
        self.assertEqual(self.round_json(node)["round"], 2)
        self.assertFalse(self.round_json(node)["open"])
        self.assertEqual(read_json(path), {"paused": {"a": ["k"]}, "steps": {}})
        time.sleep(0.1)
        self.assertEqual(self.round_json(node)["round"], 2)

    def test_reaping_node_stat_eio_is_missing(self):
        d = aos7_daemon.Daemon(self.root)
        self.addCleanup(os.close, d.rfd)
        d.registry, d.reaping = {"a": {}}, {"a": {"since": "saved"}}
        with mock.patch.object(d, "reap"), mock.patch.object(aos7_daemon, "inject", side_effect=OSError(5, "EIO")) as fault:
            d.check_nodes()
        fault.assert_called_once_with("stat", os.path.join(self.root, "a"))
        self.assertEqual(d.missing.get("a", {}).get("since"), "saved")

    def test_load_filters_owe_entries(self):
        path = os.path.join(self.root, ".aosd", "paused.json")
        d = aos7_daemon.Daemon(self.root)
        self.addCleanup(os.close, d.rfd)
        for owe in ({"a": 0, "b": 2, "../bad": 1, "a/": 1, "bool": True,
                     "neg": -1, "float": 1.5, "str": "2"}, None, [], "bad"):
            with self.subTest(owe=owe):
                write_json(path, {"paused": {}, "owe": owe})
                d.load_state()
                self.assertEqual(d.owe, {"a": 0, "b": 2} if isinstance(owe, dict) else {})

    def test_reaping_restart_stays_missing_with_proc_stat_eio(self):
        node = self.mknode("a", [self.KEEP])
        rules = os.path.join(self.root, "fault-rules.txt")
        fault = Fault("@" + rules, ops={"proc-stat"})
        self.addCleanup(fault.close)
        p = self.start_daemon(env=fault.env, register=["a"])
        identity = self.ready_task(node)
        with open(rules, "w") as fh:
            fh.write("proc-stat:/proc/%d/stat:EIO\n" % identity["pid"])
        os.rename(node, os.path.join(self.root, "old"))
        self.mknode("a", [self.KEEP])
        self.wait_for(lambda: self.nstat().get("phase") == "missing")
        self.wait_for(lambda: "a" in self.nodes_state().get("reaping", {}))
        self.wait_for(lambda: fault.hits("proc-stat") > 0)
        os.kill(p.pid, signal.SIGKILL)
        self.assertEqual(p.wait(10), -signal.SIGKILL)
        old_gen = self.status()["gen"]
        self.start_daemon(env=fault.env)
        self.wait_for(lambda: self.status().get("gen", old_gen) > old_gen)
        end = time.monotonic() + 2.2
        while time.monotonic() < end:
            self.assertEqual(self.nstat().get("phase"), "missing")
            self.assertFalse(os.path.exists(os.path.join(node, ".aos", "round.json")))
            self.assertIn("a", self.nodes_state()["reaping"])
            self.assertEqual(self.task_state(identity), aos7_proc.ALIVE)
            time.sleep(0.05)
        fault.check(where="（重起後回收未知保留 missing）")
        os.remove(rules)
        self.wait_reaped(identity)
        fresh = self.ready_task(node)
        self.assertEqual(self.task_state(fresh), aos7_proc.ALIVE)
        self.wait_round(1)

    def test_invalid_reaping_state_refuses_start(self):
        for invalid in ([], None, "a", 1):
            with self.subTest(reaping=invalid):
                state = {"nodes": {}, "reaping": invalid}
                path = os.path.join(self.root, ".aosd", "nodes.json")
                write_json(path, state)
                p = self.start_daemon()
                self.assertEqual(p.wait(10), 3)
                self.assertEqual(read_json(path), state)

    def test_load_filters_reaping_and_steps_entries(self):
        write_json(os.path.join(self.root, ".aosd", "nodes.json"),
                   {"nodes": {}, "reaping": {"a": None, "b": {"why": "kept"}, "../bad": {}, "a/": {}}})
        write_json(os.path.join(self.root, ".aosd", "paused.json"),
                   {"paused": {}, "steps": {"a": {"ok": 2, "zero": 0, "negative": -1, "bool": True,
                                                     "float": 1.5, "string": "2"}, "bad": []}})
        d = aos7_daemon.Daemon(self.root)
        self.addCleanup(os.close, d.rfd)
        d.load_state()
        self.assertEqual(d.reaping, {"a": {}, "b": {"why": "kept"}})
        self.assertEqual(d.steps, {"a": {"ok": 2}})
        for steps in (None, [], "bad"):
            write_json(os.path.join(self.root, ".aosd", "paused.json"), {"paused": {}, "steps": steps})
            d.load_state()
            self.assertEqual(d.steps, {})

    def test_reap_dirty_write_retries_and_preserves_known_groups(self):
        d = aos7_daemon.Daemon(self.root)
        self.addCleanup(os.close, d.rfd)
        node = self.mknode("a")
        d.registry = {"a": {}}
        d._pgids["a"] = {43210}
        d.save_nodes()
        with mock.patch.object(aos7_proc, "kill_node", side_effect=[(1, False), (1, True)]) as kill, \
                mock.patch.object(aos7_daemon, "Timeline") as timeline:
            with mock.patch.object(d, "save_nodes", side_effect=OSError("disk unavailable")):
                d.reap("a", node, "node-gone-kill")
                d.check_nodes()
                kill.assert_not_called()
                timeline.assert_not_called()
                self.assertTrue(d._nodes_dirty)
                self.assertEqual(d._reap_mem["a"]["known"], {43210})
                self.assertNotIn("a", self.nodes_state().get("reaping", {}))
                d.write_status()
                self.assertEqual(self.nstat()["phase"], "missing")
            d.check_nodes()
            d.reapers["a"].join(2)
            self.assertFalse(d._nodes_dirty)
            self.assertIn("a", self.nodes_state()["reaping"])
            self.assertEqual(kill.call_count, 1)
            d.check_nodes()
            self.assertEqual(kill.call_count, 1, "未到重試間隔就又收一次")
            d._reap_mem["a"]["at"] -= aos7_daemon.REAP_RETRY_S
            d.check_nodes()
            d.reapers["a"].join(2)
            self.assertEqual(kill.call_count, 2)
            kill.assert_called_with(node, {43210})
            d.check_nodes()
            timeline.return_value.start.assert_called_once()
        self.assertNotIn("reaping", self.nodes_state())
        self.assertNotIn("a", d._reap_mem)

    def test_deferred_reap_starts_after_recovery_while_gone_timeline_alive(self):
        """node 消失的首次回收落盤失敗：恢復後立即起收，不等舊時間線結束。"""
        node = self.mknode("a")
        d = aos7_daemon.Daemon(self.root)
        self.addCleanup(os.close, d.rfd)
        d.registry = {"a": {}}
        old = SimpleNamespace(is_alive=mock.Mock(return_value=True), wake=threading.Event())
        d.timelines["a"] = old
        d._pgids["a"] = {43210}
        d.save_nodes()
        os.rename(node, os.path.join(self.root, "old"))
        with mock.patch.object(aos7_proc, "kill_node", return_value=(0, True)) as kill:
            with mock.patch.object(d, "save_nodes", side_effect=OSError("disk unavailable")):
                d.check_nodes()
                self.assertIs(d.gone_tls["a"], old)
                self.assertTrue(old.gone)
                self.assertTrue(old.wake.is_set())
                self.assertTrue(d._nodes_dirty)
                self.assertNotIn("a", self.nodes_state().get("reaping", {}))
                kill.assert_not_called()
            d.check_nodes()
            self.assertIn("a", d.reapers, "意圖落盤後仍等待舊時間線結束才起收")
            d.reapers["a"].join(2)
            self.assertFalse(d.reapers["a"].is_alive())
            self.assertTrue(old.is_alive())
            self.assertIs(d.gone_tls["a"], old)
            self.assertFalse(d._nodes_dirty)
            self.assertIn("a", self.nodes_state()["reaping"])
            self.assertNotIn("deferred", d._reap_mem["a"])
            kill.assert_called_once_with(node, {43210})
            d.check_nodes()
            self.assertEqual(kill.call_count, 1)
            self.assertIn("a", d.reaping, "舊線還活著就清掉回收意圖")
            old.is_alive.return_value = False
            d.check_nodes()
            d.reapers["a"].join(2)
            self.assertEqual(kill.call_count, 2, "舊線結束後沒有再掃一次")
            d.check_nodes()
            self.assertNotIn("a", d.reaping)
        self.assertNotIn("reaping", self.nodes_state())

    def test_clean_reap_waits_for_intent_removal_write(self):
        self.mknode("a")
        d = aos7_daemon.Daemon(self.root)
        self.addCleanup(os.close, d.rfd)
        d.registry = {"a": {}}
        d.reaping = {"a": {"why": "node-gone-kill"}}
        d._reap_mem["a"] = {"clean": True}
        d.reapers["a"] = mock.Mock(is_alive=mock.Mock(return_value=False))
        d.missing["a"] = {"why": "inode 換了"}
        d.save_nodes()
        with mock.patch.object(aos7_daemon, "Timeline") as timeline:
            with mock.patch.object(d, "save_nodes", side_effect=OSError("disk unavailable")) as save:
                d.check_nodes()
                save.assert_called_once_with(reaping={})
            timeline.assert_not_called()
            self.assertIn("a", d.reaping)
            self.assertIn("a", d.missing)
            self.assertIn("a", self.nodes_state()["reaping"])
            d.check_nodes()
            timeline.return_value.start.assert_called_once()
        self.assertNotIn("reaping", self.nodes_state())
        self.assertNotIn("a", d.reaping)

    def test_gone_timeline_must_end_before_final_clean_scan(self):
        """舊時間線在 node 消失後還活著：reaper 判乾淨也不清意圖、不開新線；舊線結束後再掃一次才清（sol 第二眼 2）。"""
        self.mknode("a")
        d = aos7_daemon.Daemon(self.root)
        self.addCleanup(os.close, d.rfd)
        d.registry = {"a": {}}
        old = mock.Mock(is_alive=mock.Mock(return_value=True))
        d.gone_tls["a"] = old
        with mock.patch.object(aos7_proc, "kill_node", return_value=(0, True)) as kill, \
                mock.patch.object(aos7_daemon, "Timeline") as timeline:
            d.reap("a", os.path.join(self.root, "a"), "node-gone-kill")
            d.reapers["a"].join(5)
            d.check_nodes()
            self.assertIn("a", self.nodes_state()["reaping"], "舊線還活著就清掉回收意圖")
            timeline.assert_not_called()
            old.is_alive.return_value = False
            d.check_nodes()                          # 看到舊線結束 → 起一次重掃
            d.reapers["a"].join(5)
            self.assertEqual(kill.call_count, 2, "舊線結束後沒有再掃一次")
            timeline.assert_not_called()
            d.check_nodes()                          # 重掃乾淨 → 清意圖、開線
            timeline.return_value.start.assert_called_once()
        self.assertNotIn("reaping", self.nodes_state())

    def test_round_done_save_failure_does_not_raise_or_double_count(self):
        """同一結算寫失敗不動記憶體；重試只扣一次，到零的 owner 再 pause。"""
        d = aos7_daemon.Daemon(self.root)
        self.addCleanup(os.close, d.rfd)
        d.steps = {"a": {"k": 1, "other": 3}, "b": {"k": 2}}
        d.owe = {"a": 4, "b": 1}
        d.paused = {"a": ["already"]}
        d.save_paused()
        before = copy.deepcopy((d.owe, d.steps, d.paused))
        path = os.path.join(self.root, ".aosd", "paused.json")
        disk = read_json(path)
        with mock.patch.object(d, "save_paused", side_effect=OSError("disk unavailable")), \
                mock.patch.object(d, "log") as log:
            self.assertFalse(d.round_done("a"))
            self.assertEqual((d.owe, d.steps, d.paused), before)
            self.assertEqual(read_json(path), disk)
            self.assertFalse(any(c.kwargs.get("ev") == "steps-done" for c in log.call_args_list))
        self.assertTrue(d.round_done("a"))
        self.assertEqual(d.owe, {"b": 1})
        self.assertEqual(d.steps, {"a": {"other": 2}, "b": {"k": 2}})
        self.assertEqual(d.paused, {"a": ["already", "k"]})
        self.assertTrue(d.round_done("unused"))
        d.owe["a"] = 5
        self.assertTrue(d.round_done("a", debit=False))
        self.assertEqual(d.steps["a"], {"other": 2})
        self.assertNotIn("a", d.owe)

    def test_slot_kill_unknown_is_not_clean(self):
        """逐槽 kill 回 unknown（K1：runner 還在啟動、任務還沒起）＝未確認乾淨：unregister 的意圖留著、隔一陣再逐槽收，
        確定了才清；stop 收尾時仍不確定的寫進 reaping（stop-kill）留給重開。"""
        node = self.mknode("a", [self.KEEP])
        self.tick()
        self.ready_task(node)
        d = aos7_daemon.Daemon(self.root)
        self.addCleanup(os.close, d.rfd)
        d.reaping = {"a": {"why": "unregister-kill"}}
        d.save_nodes()
        unknown = (False, "unknown：runner 仍在啟動、還沒寫 pid.json，請求留著下次再試")
        with mock.patch.object(aos7_proc, "kill_node", return_value=(0, True)), \
                mock.patch.object(aos7_task, "kill_run", side_effect=[unknown, (True, "killed 1 group(s)")]) as kr:
            d.check_nodes()
            d.reapers["a"].join(10)
            self.assertEqual(kr.call_count, 1)
            self.assertIn("a", d._kill_unsure)
            d.check_nodes()
            self.assertIn("a", self.nodes_state()["reaping"], "槽級 unknown 就當收乾淨")
            d._reap_mem["a"]["at"] -= aos7_daemon.REAP_RETRY_S
            d.check_nodes()
            d.reapers["a"].join(10)
            self.assertEqual(kr.call_count, 2)
            d.check_nodes()
        self.assertNotIn("reaping", self.nodes_state())
        self.assertNotIn("a", d._kill_unsure)
        d2 = aos7_daemon.Daemon(self.root)
        self.addCleanup(os.close, d2.rfd)
        d2.registry = {"a": {}}
        d2._kill_unsure = {"a"}
        with mock.patch.object(aos7_proc, "kill_node", return_value=(0, True)), \
                mock.patch.object(aos7_task, "kill_run", return_value=unknown):
            d2.sweep_leftovers()
        self.assertEqual(self.nodes_state()["reaping"]["a"]["why"], "stop-kill")

    def test_stop_sweep_includes_unregistered_reaping_intents(self):
        d = aos7_daemon.Daemon(self.root)
        self.addCleanup(os.close, d.rfd)
        d.registry = {"b": {}}
        d.reaping = {"a": {}}
        d.save_nodes()
        with mock.patch.object(aos7_proc, "kill_node", return_value=(1, False)) as kill:
            d.sweep_leftovers()
            self.assertEqual(set(kill.call_args.args[0]), {os.path.join(self.root, "a"), os.path.join(self.root, "b")})
            self.assertIn("a", self.nodes_state()["reaping"])
            kill.return_value = (1, True)
            with mock.patch.object(d, "save_nodes", side_effect=OSError("disk unavailable")) as save:
                d.sweep_leftovers()
                save.assert_called_once_with(reaping={})
            self.assertIn("a", self.nodes_state()["reaping"])
            d.sweep_leftovers()
        self.assertNotIn("reaping", self.nodes_state())

    def test_stop_without_kill_keeps_intent_for_restart(self):
        node = self.mknode("a", [self.KEEP])
        self.tick()
        identity = self.ready_task(node)
        state = {"nodes": {}, "reaping": {"a": {"why": "unregister-kill"}}}
        write_json(os.path.join(self.root, ".aosd", "nodes.json"), state)
        request = self.ctl("stop")  # 先排 stop，主迴圈不會先啟動回收
        p = self.start_daemon()
        self.assertEqual(p.wait(10), 0)
        self.assertTrue(self.wait_receipt(request)["result"]["ok"])
        self.assertEqual(self.nodes_state(), state)
        self.assertEqual(self.task_state(identity), aos7_proc.ALIVE)
        self.start_daemon()
        self.wait_reaped(identity)



if __name__ == "__main__":
    unittest.main()
