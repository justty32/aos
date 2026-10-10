from _daemon import *  # noqa: F403


class TestNodeGone(DaemonCase):
    """〔core〕"""
    def test_rm_rf_kills_and_stays_registered(self):
        node = self.mknode("a", [{"name": "s", "mode": "keep", "argv": SLEEP}])
        self.start_daemon(register=["a"])
        pid = self.wait_pid(node, "s")["pid"]
        shutil.rmtree(node)
        self.wait_for(lambda: not aos7_proc.pid_alive(pid), 10, "node 被刪，任務沒被收")
        self.wait_for(lambda: self.nstat().get("phase") == "missing")
        self.assertIn("a", read_json(os.path.join(self.root, ".aosd", "nodes.json"))["nodes"])
        self.assertFalse(os.path.exists(node))                    # 不建鬼目錄
        self.mknode("a", [{"name": "s", "mode": "keep", "argv": SLEEP}])   # 回來就接著跑
        self.wait_round(2)
        self.wait_pid(node, "s")

    def test_move_kills_old_new_place_needs_register(self):
        node = self.mknode("a", [{"name": "s", "mode": "keep", "argv": SLEEP}])
        self.start_daemon(register=["a"])
        pid = self.wait_pid(node, "s")["pid"]
        os.rename(node, os.path.join(self.root, "b"))
        self.wait_for(lambda: not aos7_proc.pid_alive(pid), 10, "搬走了，舊任務沒被收")
        self.wait_for(lambda: self.nstat().get("phase") == "missing")
        time.sleep(0.5)
        self.assertNotIn("b", self.status()["nodes"])            # 沒有自動發現（W1）
        self.wait_receipt(self.ctl("register", "b"))
        nb = os.path.join(self.root, "b")
        self.wait_for(lambda: self.birth(nb, "s").get("run", 0) > 1, 10, "新位置 register 後 keep 沒重起")

    def test_replaced_by_other_dir_is_new_timeline(self):
        node = self.mknode("a", [{"name": "s", "mode": "keep", "argv": SLEEP}])
        self.start_daemon(register=["a"])
        pid = self.wait_pid(node, "s")["pid"]
        os.rename(node, os.path.join(self.root, "old"))
        os.makedirs(node)                                        # 同路徑換成別的資料夾（inode 不同）
        self.wait_for(lambda: not aos7_proc.pid_alive(pid), 10)
        self.wait_for(lambda: os.path.exists(os.path.join(node, ".aos", "round.json")), 10)

    @unittest.skipIf(os.geteuid() == 0, "root 不受權限限制")
    def test_unreadable_node_is_unknown_not_gone(self):
        node = self.mknode("p", [{"name": "s", "mode": "keep", "argv": SLEEP}])
        os.makedirs(os.path.join(self.root, "lock"))
        self.addCleanup(os.chmod, os.path.join(self.root, "lock"), 0o700)
        inner = self.mknode("lock/n", [{"name": "s", "mode": "keep", "argv": SLEEP}])
        self.start_daemon(register=["lock/n"])
        pid = self.wait_pid(inner, "s")["pid"]
        os.chmod(os.path.join(self.root, "lock"), 0)              # stat 得到 EACCES：看不到≠不存在
        time.sleep(0.5)
        self.assertTrue(aos7_proc.pid_alive(pid))
        self.assertNotEqual(self.nstat("lock/n").get("phase"), "missing")
        os.chmod(os.path.join(self.root, "lock"), 0o700)



class TestEarlyTock(DaemonCase):
    """〔core〕"""
    def test_default_fixed_interval(self):
        node = self.mknode("a", [{"name": "q", "argv": ["true"]}], interval_ms=1200)
        self.start_daemon(register=["a"])
        self.wait_for(lambda: self.last_round(node).get("round"), 10)
        lr = self.last_round(node)
        self.assertIs(lr["early"], False)
        import datetime
        dt = (datetime.datetime.fromisoformat(lr["tock_at"]) - datetime.datetime.fromisoformat(lr["tick_at"]))
        self.assertGreater(dt.total_seconds(), 1.0)

    def test_early_tock_when_all_ended(self):
        node = self.mknode("a", [{"name": "q", "argv": ["true"]}], interval_ms=3000, early=True)
        self.start_daemon(register=["a"])
        self.wait_for(lambda: self.last_round(node).get("round"), 3, "early_tock 沒提前")
        self.assertIs(self.last_round(node)["early"], True)



class TestPause(DaemonCase):
    """〔core〕"""
    def test_owner_pause_not_released_by_other(self):
        self.mknode("a", interval_ms=50)
        self.start_daemon(register=["a"])
        self.wait_round(2)
        self.wait_receipt(self.ctl("pause", "a", "--owner", "A"))
        self.wait_receipt(self.ctl("pause", "a", "--owner", "B"))
        self.wait_for(lambda: self.nstat().get("phase") == "paused")
        r = self.wait_receipt(self.ctl("resume", "a", "--owner", "B"))
        self.assertIn("還有", r["result"]["msg"])
        n = self.node_round()
        time.sleep(0.4)
        self.assertEqual(self.node_round(), n)                       # A 的 pause 還在
        self.assertEqual(self.nstat()["paused_by"], ["A"])
        self.assertEqual(read_json(os.path.join(self.root, ".aosd", "paused.json"))["paused"], {"a": ["A"]})
        self.wait_receipt(self.ctl("resume", "a", "--owner", "A"))
        self.wait_round(n + 2)

    def test_resume_all_and_no_owner_slot(self):
        self.mknode("a", interval_ms=50)
        self.start_daemon(register=["a"])
        self.wait_receipt(self.ctl("pause", "a"))
        self.wait_receipt(self.ctl("pause", "a", "--owner", "X"))
        self.wait_for(lambda: self.nstat().get("phase") == "paused")
        self.assertEqual(sorted(self.nstat()["paused_by"]), ["", "X"])
        self.wait_receipt(self.ctl("resume", "a", "--all"))
        n = self.node_round()
        self.wait_round(n + 2)

    def test_resume_wakes_immediately(self):
        self.mknode("a", interval_ms=4000)
        self.start_daemon(register=["a"])
        self.wait_round(1)
        self.wait_receipt(self.ctl("pause", "a"))
        self.wait_for(lambda: self.nstat().get("phase") in ("paused",), 10)
        n = self.node_round()
        t0 = time.monotonic()
        self.ctl("resume", "a")
        self.wait_round(n + 1, timeout=3)
        self.assertLess(time.monotonic() - t0, 2.5)

    def test_resume_rounds_then_pauses_with_same_owner(self):
        self.mknode("a", interval_ms=50)
        self.start_daemon(register=["a"])
        self.wait_receipt(self.ctl("pause", "a", "--owner", "k"))
        self.wait_for(lambda: self.nstat().get("phase") == "paused")
        n = self.node_round()
        self.wait_receipt(self.ctl("resume", "a", "--owner", "k", "--rounds", "3"))
        self.wait_for(lambda: self.nstat().get("phase") == "paused" and self.node_round() >= n + 3, 10)
        time.sleep(0.3)
        self.assertEqual(self.node_round(), n + 3)
        self.assertEqual(self.nstat()["paused_by"], ["k"])

    def test_wake(self):
        # 固定 interval 時整段 interval 都在回合中（wake 照舊不打斷）；提前 tock 才有「等下一回合」的空檔（P2-01）
        self.mknode("a", interval_ms=5000, early=True)
        self.start_daemon(register=["a"])
        self.wait_round(1)
        self.wait_for(lambda: self.nstat().get("phase") == "idle", 8)
        n = self.node_round()
        self.ctl("wake", "a")
        self.wait_round(n + 1, timeout=3)



class TestStop(DaemonCase):
    """〔core〕"""
    def test_stop_kill_and_sigterm(self):
        node = self.mknode("a", [{"name": "s", "mode": "keep", "argv": SLEEP}])
        p = self.start_daemon(register=["a"])
        pid = self.wait_pid(node, "s")["pid"]
        r = self.ctl("stop", "a")
        self.assertFalse(self.wait_receipt(r)["result"]["ok"])      # stop 不收 node
        self.stop_daemon(p)
        self.assertFalse(aos7_proc.pid_alive(pid))
        st = self.status()
        self.assertTrue(st["stopped"])
        self.assertFalse(self.round_json(node)["open"])
        p = self.start_daemon()
        pid = self.wait_pid(node, "s") and self.wait_for(
            lambda: (read_json(os.path.join(self.slot(node, "s"), "pid.json")) or {}).get("run", 0) > 1 and
            read_json(os.path.join(self.slot(node, "s"), "pid.json"))["pid"])
        p.terminate()
        self.assertEqual(p.wait(15), 0)
        self.assertFalse(aos7_proc.pid_alive(pid))

    def test_stop_without_kill_leaves_tasks(self):
        node = self.mknode("a", [{"name": "s", "mode": "keep", "argv": SLEEP}])
        p = self.start_daemon(register=["a"])
        pid = self.wait_pid(node, "s")["pid"]
        self.stop_daemon(p, kill=False)
        self.assertTrue(aos7_proc.pid_alive(pid))

    def test_second_daemon_refused(self):
        self.start_daemon()
        self.wait_for(lambda: self.status().get("pid"))
        p = subprocess.run([sys.executable, os.path.join(BIN, "aos7-daemon"), self.root], capture_output=True,
                           text=True, timeout=10)
        self.assertEqual(p.returncode, 1)

    def test_root_moved_stops_with_kill(self):
        node = self.mknode("a", [{"name": "s", "mode": "keep", "argv": SLEEP}])
        p = self.start_daemon(register=["a"])
        pid = self.wait_pid(node, "s")["pid"]
        moved = self.root + "-moved"
        os.rename(self.root, moved)
        self.addCleanup(shutil.rmtree, moved, True)
        self.addCleanup(kill_space_procs, moved)
        self.assertEqual(p.wait(15), 0)
        self.assertFalse(aos7_proc.pid_alive(pid))
        self.assertTrue(read_json(os.path.join(moved, ".aosd", "status.json"))["root_gone"])
        os.makedirs(self.root)



class TestStuckActions(DaemonCase):
    """〔core〕"""
    def test_stuck_tick_cut_and_round_marked(self):
        node = self.mknode("a", interval_ms=50, action_timeout_s=0.5)
        self.start_daemon(env={"AOS7_TEST_HANG": "tick-opened"}, register=["a"])
        self.wait_for(lambda: self.last_round(node).get("incomplete") == "tick" and
                      self.last_round(node)["round"] >= 2, 15, "沒有 incomplete=tick 的回合")
        self.assertEqual(self.nstat()["last_error"]["where"], "tick")

    def test_stop_not_blocked_by_stuck_tick(self):
        self.mknode("a", interval_ms=50, action_timeout_s=1000)
        p = self.start_daemon(env={"AOS7_TEST_HANG": "tick-opened"}, register=["a"])
        self.wait_for(lambda: self.nstat().get("phase") == "tick")
        t0 = time.monotonic()
        p.terminate()
        self.assertEqual(p.wait(15), 0)
        self.assertLess(time.monotonic() - t0, 10)

    def test_tock_killed_after_summary_is_replayed_once(self):
        node = self.mknode("a", interval_ms=50, action_timeout_s=0.5)
        self.start_daemon(env={"AOS7_TEST_HANG": "tock-summary"}, register=["a"])
        self.wait_for(lambda: self.round_json(node).get("replayed") and self.round_json(node).get("open") is False,
                      15, "被打斷的 tock 沒有補做")
        self.assertEqual(self.round_json(node)["round"], self.last_round(node)["round"])

    @unittest.skipIf(os.geteuid() == 0, "root 讀得到 chmod 000 的檔")
    def test_unreadable_round_json_holds_timeline(self):
        node = self.mknode("a", interval_ms=50)
        self.start_daemon(register=["a"])
        self.wait_round(2)
        rp = os.path.join(node, ".aos", "round.json")
        os.chmod(rp, 0)
        try:
            self.wait_for(lambda: self.nstat().get("phase") == "error" and self.nstat().get("round_open") is None, 10)
            r = self.node_round()
            time.sleep(0.5)
            self.assertEqual(self.node_round(), r)               # 不知道 → 不 tick
        finally:
            os.chmod(rp, 0o600)
        self.wait_round(r + 2)



class TestDaemonDeath(DaemonCase):
    """〔core〕"""
    def test_kill9_daemon_new_daemon_recovers_round_no_double(self):
        node = self.mknode("a", [{"name": "s", "mode": "keep", "argv": SLEEP}], interval_ms=2000)
        p = self.start_daemon(register=["a"])
        pid = self.wait_pid(node, "s")["pid"]
        self.wait_for(lambda: self.round_json(node).get("open") is True)
        os.kill(p.pid, signal.SIGKILL)                          # 只殺 daemon 本身（回合開著、任務在）
        p.wait()
        self.assertTrue(aos7_proc.pid_alive(pid))
        gen = read_json(os.path.join(self.root, ".aosd", "gen.json"))["gen"]
        self.start_daemon()
        self.wait_for(lambda: self.last_round(node).get("incomplete") == "unclosed", 10, "沒收掉沒關的回合")
        self.assertEqual(read_json(os.path.join(self.root, ".aosd", "gen.json"))["gen"], gen + 1)
        self.wait_round(self.last_round(node)["round"] + 1)
        self.assertEqual(self.birth(node, "s")["run"], 1)        # keep 沒雙開
        self.assertTrue(aos7_proc.pid_alive(pid))

    HOLD = ("import os,sys,time\nsys.path.insert(0,%r)\nimport aos7_fs\n"
            "with aos7_fs.action_lock(%r, %r) as ok:\n    open(%r,'w').write('held')\n    time.sleep(60)\n")

    def test_new_daemon_reaps_old_holder(self):
        node = self.mknode("a", action_timeout_s=0.3)
        write_json(os.path.join(self.root, ".aosd", "gen.json"), {"gen": 5})
        mark = os.path.join(self.root, "held")
        import _proc
        holder = _proc.track(self, subprocess.Popen([sys.executable, "-c", self.HOLD % (LIB, self.root, node, mark)],
                                                    env=dict(os.environ, AOS7_GEN="5")))
        self.wait_for(lambda: os.path.exists(mark))
        open(os.path.join(self.root, ".aosd", "log.on"), "w").close()
        self.start_daemon(register=["a"])
        self.wait_round(2, timeout=15)
        self.assertEqual(holder.wait(timeout=5), -signal.SIGKILL)
        self.assertTrue(any(e["ev"] == "stale-holder-kill" for e in read_jsonl(os.path.join(self.root, ".aosd",
                                                                                            "log.jsonl"))))

    def test_unverified_holder_not_killed(self):
        node = self.mknode("a", action_timeout_s=0.3)
        mark = os.path.join(self.root, "held")
        import _proc
        holder = _proc.track(self, subprocess.Popen([sys.executable, "-c", self.HOLD % (LIB, self.root, node, mark)]))
        self.wait_for(lambda: os.path.exists(mark))   # 沒有 AOS7_GEN：action.owner.json 的 gen 是 null → 認不出
        self.start_daemon(register=["a"])
        self.wait_for(lambda: "stale-holder-unverified" in (self.nstat().get("last_error") or {}).get("why", ""), 10)
        self.assertIsNone(holder.poll())



if __name__ == "__main__":
    unittest.main()
