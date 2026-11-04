from _daemon import *  # noqa: F403


class TestRegister(DaemonCase):
    """〔core〕"""
    def test_register_runs_only_registered(self):
        a = self.mknode("a", [{"name": "j", "argv": ["true"]}])
        b = self.mknode("b", [{"name": "j", "argv": ["true"]}])
        self.start_daemon(register=["a"])
        self.wait_round(3)
        self.assertFalse(os.path.exists(os.path.join(b, ".aos", "round.json")))   # 沒登記的不跑（不掃描）
        self.assertEqual(list(read_json(os.path.join(self.root, ".aosd", "nodes.json"))["nodes"]), ["a"])
        r = self.wait_receipt(self.ctl("register", "b"))
        self.assertTrue(r["result"]["ok"])
        self.wait_round(2, "b")
        r = self.wait_receipt(self.ctl("register", "b", by="again"))
        self.assertIn("已登記", r["result"]["msg"])

    def test_register_absent_dir_then_appears(self):
        self.start_daemon()
        r = self.wait_receipt(self.ctl("register", "later"))
        self.assertTrue(r["result"]["ok"])
        self.assertIn("出現時才開回合", r["result"]["msg"])
        self.wait_for(lambda: self.nstat("later").get("phase") == "missing")
        self.mknode("later")
        self.wait_round(2, "later")

    def test_register_checks(self):
        os.makedirs(os.path.join(self.root, "sub", ".aosd"))
        os.makedirs(os.path.join(self.root, "sub", "n"))
        outside = os.path.join(self.root + "-outside")
        os.makedirs(outside, exist_ok=True)
        self.addCleanup(shutil.rmtree, outside, True)
        os.symlink(outside, os.path.join(self.root, "esc"))
        self.start_daemon()
        for node, word in (("/abs", "絕對"), ("../x", ".."), ("sub/n", "daemon sub"), ("esc", "跑出空間根"),
                           ("a/.aos", ". 開頭")):
            path = os.path.join(self.root, ".aosd", "ctl", "t-%d.json" % abs(hash(node)))
            write_json(path, {"op": "register", "node": node, "by": "t"})
            r = self.wait_receipt(path)
            self.assertFalse(r["result"]["ok"], node)
        self.assertEqual(read_json(os.path.join(self.root, ".aosd", "nodes.json"))["nodes"], {})

    def test_registered_before_daemon_starts(self):
        """寫給停著的 daemon 的控制檔留在 ctl/，起來才做（子 daemon 起來前先登記就靠這個）。"""
        self.mknode("a")
        self.ctl("register", "a")
        self.start_daemon()
        self.wait_round(2)

    def test_restart_daemon_follows_nodes_json(self):
        self.mknode("a")
        p = self.start_daemon(register=["a"])
        self.wait_round(2)
        self.stop_daemon(p)
        r = self.node_round()
        self.start_daemon()
        self.wait_round(r + 2)

    def test_unregister_kills_by_default(self):
        node = self.mknode("a", [{"name": "s", "mode": "keep", "argv": SLEEP}])
        self.start_daemon(register=["a"])
        pid = self.wait_pid(node, "s")["pid"]
        r = self.wait_receipt(self.ctl("unregister", "a"))
        self.assertTrue(r["result"]["ok"])
        self.wait_for(lambda: not aos7_proc.pid_alive(pid), 10, "unregister 沒收任務")
        self.wait_for(lambda: "a" not in self.status().get("nodes", {}))
        self.assertFalse(self.round_json(node)["open"])        # 本回合收完才走
        self.assertEqual(read_json(os.path.join(self.root, ".aosd", "nodes.json"))["nodes"], {})

    def test_unregister_no_kill_leaves_task(self):
        node = self.mknode("a", [{"name": "s", "mode": "keep", "argv": SLEEP}])
        self.start_daemon(register=["a"])
        pid = self.wait_pid(node, "s")["pid"]
        self.wait_receipt(self.ctl("unregister", "a", "--no-kill"))
        self.wait_for(lambda: "a" not in self.status().get("nodes", {}))
        time.sleep(0.3)
        self.assertTrue(aos7_proc.pid_alive(pid))



class TestCtlFiles(DaemonCase):
    """〔core〕"""
    def test_receipt_overwritten_same_name(self):
        self.mknode("a", interval_ms=50)
        self.start_daemon(register=["a"])
        for _ in range(20):
            self.wait_receipt(self.ctl("wake", "a"))
        done = os.listdir(os.path.join(self.root, ".aosd", "ctl-done"))
        self.assertEqual(sorted(done), ["cli.register.a.json", "cli.wake.a.json"])

    def test_flood_budget_and_status_moves(self):
        self.mknode("a", interval_ms=50)
        cdir = os.path.join(self.root, ".aosd", "ctl")
        for k in range(3000):
            write_json(os.path.join(cdir, "f%05d.json" % k), {"op": "wake", "node": "a"})
        self.start_daemon(register=["a"])
        self.wait_for(lambda: self.status().get("at"), 10)
        a1 = self.status()["at"]
        time.sleep(0.3)
        self.assertNotEqual(self.status()["at"], a1)   # 洪水中 status 照常寫
        self.wait_for(lambda: not [n for n in os.listdir(cdir) if not n.startswith(".")], 30, "洪水沒消化完")
        self.wait_round(2)

    def test_bad_files_get_receipts(self):
        self.start_daemon()
        self.wait_for(lambda: self.status().get("pid"))
        cdir = os.path.join(self.root, ".aosd", "ctl")
        os.mkfifo(os.path.join(cdir, "fifo.json"))
        os.makedirs(os.path.join(cdir, "dir.json"))
        with open(os.path.join(cdir, "x.txt"), "w") as f:
            f.write("{}")
        with open(os.path.join(cdir, "bad.json"), "w") as f:
            f.write("{nope")
        write_json(os.path.join(cdir, "unk.json"), {"op": "dance"})
        done = os.path.join(self.root, ".aosd", "ctl-done")
        self.wait_for(lambda: not [n for n in os.listdir(cdir) if not n.startswith(".")], 10)
        for n in ("fifo.json", "dir.json", "x.txt.json", "bad.json", "unk.json"):
            self.assertFalse(read_json(os.path.join(done, n))["result"]["ok"], n)
        self.assertTrue(os.path.exists(os.path.join(done, "fifo.json.bad")))
        self.assertTrue(self.status()["pid"])

    def test_receipt_failure_drops_request_and_stop_still_works(self):
        """回條寫不進去（處理丟例外）：效果可能已生效，不重做——請求刪掉、記 last_ctl_error；同圈的 stop 照樣生效。"""
        self.start_daemon()
        self.wait_for(lambda: self.status().get("pid"))
        aosd = os.path.join(self.root, ".aosd")
        shutil.rmtree(os.path.join(aosd, "ctl-done"), ignore_errors=True)
        with open(os.path.join(aosd, "ctl-done"), "w") as f:   # ctl-done 變成一般檔：回條寫不進去
            f.write("x")
        write_json(os.path.join(aosd, "ctl", "a-wake.json"), {"op": "wake", "node": "zz"})
        write_json(os.path.join(aosd, "ctl", "b-stop.json"), {"op": "stop"})
        p = self.procs[-1]
        self.assertEqual(p.wait(15), 0)
        self.assertEqual([n for n in os.listdir(os.path.join(aosd, "ctl")) if not n.startswith(".")], [])
        self.assertFalse(os.path.exists(os.path.join(aosd, "ctl-failed")))
        self.assertIn("last_ctl_error", self.status())

    def test_log_on_switch(self):
        self.mknode("a", interval_ms=50)
        self.start_daemon(register=["a"])
        self.wait_round(2)
        lp = os.path.join(self.root, ".aosd", "log.jsonl")
        self.assertFalse(os.path.exists(lp))                     # 預設沒有流水帳
        self.assertTrue(self.status()["last_event"])
        open(os.path.join(self.root, ".aosd", "log.on"), "w").close()
        self.wait_receipt(self.ctl("wake", "a"))
        self.wait_for(lambda: any(e.get("ev") == "ctl" for e in read_jsonl(lp)))



if __name__ == "__main__":
    unittest.main()
