"""daemon 的測試：登記／取消登記、node 消失搬走 → missing、early_tock 兩種、pause owner、resume 順便 wake、stop／SIGTERM、
控制檔洪水與壞檔、回條只留上一次、卡住的 tick／tock、kill -9 daemon 後接手、舊動作接管、root 消失、log.on。"""
import os, sys  # noqa: E401
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # tests/：base、_matrix
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import unittest
from types import SimpleNamespace
from unittest import mock

from base import BIN, LIB, SLEEP, DaemonCase, kill_space_procs
from _matrix import Fault
import aos7_daemon
import aos7_fs
import aos7_proc
import aos7_task
from aos7_fs import read_json, write_json
from aos7_taskside import read_jsonl


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

    def readonly_aosd(self):
        path = os.path.join(self.root, ".aosd")
        self.addCleanup(os.chmod, path, 0o700)
        os.chmod(path, 0o500)
        # 先證明同一個目錄真的不能原子寫檔，避免故障沒有打中卻通過。
        with self.assertRaises(PermissionError):
            write_json(os.path.join(path, "write-probe.json"), {})
        return path

    @unittest.skipIf(os.geteuid() == 0, "root 不受 chmod 寫入限制")
    def test_unregister_write_failure_is_retryable(self):
        node = self.mknode("a", [self.KEEP])
        self.start_daemon(register=["a"])
        identity = self.ready_task(node)
        self.wait_for(lambda: self.nstat().get("round"))
        path = self.readonly_aosd()
        result = self.wait_receipt(self.ctl("unregister", "a"))["result"]
        self.assertFalse(result["ok"])
        self.assertIn("nodes.json", result["msg"])
        self.assertIn("a", self.nodes_state()["nodes"])
        self.assertTrue(self.nstat().get("round"))
        self.assertEqual(self.task_state(identity), aos7_proc.ALIVE)
        before = self.status()["at"]
        os.chmod(path, 0o700)
        self.wait_for(lambda: self.status().get("at") != before)
        self.assertTrue(self.nstat().get("round"), "恢復 status 寫入後時間線丟了")
        self.assertNotEqual(self.nstat().get("phase"), "unregistering")
        self.assertEqual(self.task_state(identity), aos7_proc.ALIVE)
        self.assertTrue(self.wait_receipt(self.ctl("unregister", "a"))["result"]["ok"])
        self.wait_reaped(identity)
        self.assertNotIn("a", self.nodes_state()["nodes"])

    @unittest.skipIf(os.geteuid() == 0, "root 不受 chmod 寫入限制")
    def test_register_write_failure_is_retryable(self):
        node = self.mknode("a")
        self.start_daemon()
        self.wait_for(lambda: self.status().get("pid"))
        self.wait_receipt(self.ctl("wake", "a"))  # 先建好 ctl-done，chmod 只擋狀態檔覆寫
        path = self.readonly_aosd()
        result = self.wait_receipt(self.ctl("register", "a"))["result"]
        self.assertFalse(result["ok"])
        self.assertIn("nodes.json", result["msg"])
        self.assertNotIn("a", self.nodes_state().get("nodes", {}))
        self.assertNotIn("a", self.status()["nodes"])
        before = self.status()["at"]
        os.chmod(path, 0o700)
        self.wait_for(lambda: self.status().get("at") != before)
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
        node = os.path.join(self.root, "a")
        d._pgids["a"] = {43210}
        with mock.patch.object(aos7_proc, "kill_node", side_effect=[(1, False), (1, True)]) as kill:
            with mock.patch.object(d, "save_nodes", side_effect=OSError("disk unavailable")) as save:
                d.reap("a", node, "node-gone-kill")
                d.reapers["a"].join(5)
                save.assert_called_once()
            self.assertFalse(d.reapers["a"].is_alive())
            self.assertTrue(d._nodes_dirty)
            self.assertFalse(d._reap_mem["a"]["clean"])
            self.assertEqual(d._reap_mem["a"]["known"], {43210})
            d.check_nodes()
            self.assertFalse(d._nodes_dirty)
            self.assertIn("a", self.nodes_state()["reaping"])
            self.assertEqual(kill.call_count, 1, "未到重試間隔就又收一次")
            d._reap_mem["a"]["at"] -= aos7_daemon.REAP_RETRY_S
            d.check_nodes()
            d.reapers["a"].join(5)
            self.assertEqual(kill.call_count, 2)
            kill.assert_called_with(node, {43210})
            d.check_nodes()
        self.assertNotIn("reaping", self.nodes_state())
        self.assertNotIn("a", d._reap_mem)

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
