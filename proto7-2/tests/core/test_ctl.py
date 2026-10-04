"""任務控制（ctl.json：kill／restart／reload／run）、kill 範圍（Q1）、lost 前的身分掃描（NODE＋TID＋RUN）、掛載。"""
import os, sys  # noqa: E401
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # tests/：base、_matrix
import os
import signal
import time
import unittest

from base import SLEEP, CoreCase
import aos7_proc
import aos7_task
from aos7_fs import read_json, write_json

# 留一個 setsid 的孫程序（新 session、環境變數照樣是這個任務的），pid 寫進槽裡的 gc.pid
LEAVE_GC = 'setsid sleep 60 > /dev/null 2>&1 & echo $! > "$AOS7_TASK/gc.pid"; '


def gc_pid(node, slot, wait=None):
    p = os.path.join(aos7_task.slot_dir(node, slot), "gc.pid")
    end = time.monotonic() + (wait or 0)
    while True:
        try:
            with open(p) as f:
                v = f.read().strip()
            if v:
                return int(v)
        except OSError:
            pass
        if time.monotonic() >= end:
            return None
        time.sleep(0.02)


class TestCtl(CoreCase):
    """〔control〕任務控制：kill 的案例是核心（標〔core〕），restart／reload 是控制包，aos7-ctl task 是工具包（標〔tools〕）。"""
    def write_ctl(self, node, slot, **ctl):
        write_json(os.path.join(self.slot(node, slot), "ctl.json"), dict({"by": "test"}, **ctl))

    def done(self, node, slot):
        return read_json(os.path.join(self.slot(node, slot), "ctl-done.json"))

    def test_kill_at_tock_reported_by_ctl(self):
        """〔core〕"""
        node = self.mknode("a", [{"name": "s", "argv": SLEEP}])
        self.tick()
        self.wait_pid(node, "s")
        self.write_ctl(node, "s", op="kill")
        lr = self.tock()
        d = self.done(node, "s")
        self.assertTrue(d["result"]["ok"], d)
        self.assertEqual(d["result"]["run"], "s#1")
        self.assertEqual(lr["ended"], [{"run": "s#1", "code": -15, "by_ctl": {"op": "kill", "by": "test"}}])

    def test_kill_with_stale_run_refused(self):
        """〔core〕"""
        node = self.mknode("a", [{"name": "s", "mode": "keep", "argv": SLEEP}])
        self.tick()
        self.wait_pid(node, "s")
        self.write_ctl(node, "s", op="kill", run=7)
        self.tock()
        d = self.done(node, "s")
        self.assertFalse(d["result"]["ok"])
        self.assertIn("已經不是現在的", d["result"]["msg"])
        self.assertEqual(self.view(node, "s", 1).state, aos7_task.LIVE)

    def test_restart_same_slot_new_run_keeps_state(self):
        node = self.mknode("a", [{"name": "w", "argv": ["sh", "-c", 'echo $AOS7_RUN >> "$AOS7_TASK/runs.txt"; sleep 60'],
                                  "from_round": 1}])
        self.tick()
        self.wait_pid(node, "w")
        self.set_tasks(node, [])   # 名字拿掉也照樣 restart（照 birth.json 的定義）
        self.write_ctl(node, "w", op="restart", why="test")
        self.tock()
        once = self.tasks(node)
        self.assertEqual(len(once), 1)
        self.assertEqual((once[0]["mode"], once[0]["slot"], once[0]["restart_of"]), ("once", "w", "w#1"))
        out = self.tick()
        self.assertEqual(out["started"], ["w#2"])
        self.assertEqual(self.tasks(node), [])
        b = self.birth(node, "w")
        self.assertEqual((b["run"], b["restart_of"]), (2, "w#1"))
        def runs():
            with open(os.path.join(self.slot(node, "w"), "runs.txt")) as f:
                return f.read().split() == ["1", "2"]
        self.wait_for(runs)

    def test_restart_reload_takes_new_definition(self):
        node = self.mknode("a", [{"name": "w", "mode": "keep", "argv": SLEEP}])
        self.tick()
        self.wait_pid(node, "w")
        self.set_tasks(node, [{"name": "w", "mode": "keep", "argv": ["sleep", "59"]}])
        self.write_ctl(node, "w", op="restart", reload=True)
        self.tock()
        d = self.done(node, "w")
        self.assertTrue(d["result"]["ok"], d)
        self.assertEqual(d["result"]["diff"], {"argv": {"old": SLEEP, "new": ["sleep", "59"]}})
        self.tick()
        self.assertEqual(self.birth(node, "w")["argv"], ["sleep", "59"])

    def test_reload_refused_without_kill(self):
        node = self.mknode("a", [{"name": "w", "mode": "keep", "argv": SLEEP}])
        self.tick()
        self.wait_pid(node, "w")
        self.set_tasks(node, [{"name": "w", "mode": "keep", "argv": SLEEP, "max_live": "2"}])
        self.write_ctl(node, "w", op="restart", reload=True)
        self.tock()
        self.assertFalse(self.done(node, "w")["result"]["ok"])
        self.assertEqual(self.view(node, "w", 1).state, aos7_task.LIVE)   # 沒 kill
        self.assertEqual(len(self.tasks(node)), 1)

    def test_bad_ctl_gets_failed_receipt(self):
        """〔core〕"""
        node = self.mknode("a", [{"name": "s", "argv": SLEEP}])
        self.tick()
        with open(os.path.join(self.slot(node, "s"), "ctl.json"), "w") as f:
            f.write("[1, 2")
        self.tock()
        self.assertFalse(self.done(node, "s")["result"]["ok"])
        self.assertFalse(os.path.exists(os.path.join(self.slot(node, "s"), "ctl.json")))

    def test_restart_receipt_survives_new_run(self):
        node = self.mknode("a", [{"name": "s", "mode": "keep", "argv": SLEEP}])
        self.tick()
        self.wait_pid(node, "s")
        self.write_ctl(node, "s", op="restart")
        self.tock()
        self.tick()
        self.assertEqual(self.done(node, "s")["result"]["run"], "s#1")   # 換 run 不清回條（P2-04）

    def test_aos7_ctl_task(self):
        """〔tools〕"""
        node = self.mknode("a", [{"name": "s", "argv": SLEEP}])
        self.tick()
        self.wait_pid(node, "s")
        self.prog("aos7-ctl", "task", self.slot(node, "s"), "kill", "why", "--run", "1")
        self.tock()
        self.assertTrue(self.done(node, "s")["result"]["ok"])


class TestKillRange(CoreCase):
    """〔core〕"""
    def test_kill_reaches_setsid_grandchild(self):
        node = self.mknode("a", [{"name": "g", "argv": ["sh", "-c", LEAVE_GC + "sleep 60"]}])
        self.tick()
        gc = gc_pid(node, "g", wait=5)
        self.assertTrue(aos7_proc.pid_alive(gc))
        write_json(os.path.join(self.slot(node, "g"), "ctl.json"), {"op": "kill"})
        self.tock()
        self.wait_for(lambda: not aos7_proc.pid_alive(gc), 3, "setsid 的孫程序沒收到")

    def test_forged_pgid_not_killed(self):
        node = self.mknode("a", [{"name": "s", "argv": SLEEP}])
        import subprocess
        victim = subprocess.Popen(["sleep", "60"], start_new_session=True)
        self.procs.append(victim)
        self.tick()
        pj = self.wait_pid(node, "s")
        pj["pgid"] = victim.pid
        write_json(os.path.join(self.slot(node, "s"), "pid.json"), pj)
        write_json(os.path.join(self.slot(node, "s"), "ctl.json"), {"op": "kill"})
        self.tock()
        self.assertIsNone(victim.poll())
        self.assertIn("不是這個任務的群組", read_json(os.path.join(self.slot(node, "s"), "ctl-done.json"))["result"]["msg"])

    def test_inst_kill_reaches_other_session(self):
        node = self.mknode("a", [{"name": "i", "inst": "s.inst.json"}])
        write_json(os.path.join(node, "s.inst.json"), {"argv": SLEEP})
        self.tick()
        pj = self.wait_pid(node, "i")
        self.wait_for(lambda: len(aos7_proc.groups_with_descendants(pj["pgid"])) >= 2)
        groups = aos7_proc.groups_with_descendants(pj["pgid"])
        write_json(os.path.join(self.slot(node, "i"), "ctl.json"), {"op": "kill"})
        self.tock()
        self.assertFalse(any(aos7_proc.group_alive(g) for g in groups))


class TestIdentityScan(CoreCase):
    """〔core〕"""
    def test_lost_kills_leftover_before_keep_restarts(self):
        """runner 與任務主程序都被 kill -9，setsid 的孫程序還在：lost 判定前先身分掃描收掉它，keep 不雙開。"""
        node = self.mknode("a", [{"name": "k", "mode": "keep", "argv": ["sh", "-c", LEAVE_GC + "sleep 60"]}])
        self.tick()
        pj = self.wait_pid(node, "k")
        gc = gc_pid(node, "k", wait=5)
        runner = self.birth(node, "k")["runner"]["pid"]
        os.kill(runner, signal.SIGKILL)
        os.kill(pj["pid"], signal.SIGKILL)
        self.wait_for(lambda: not aos7_proc.pid_alive(pj["pid"]) and not aos7_proc.pid_alive(runner))
        self.assertTrue(aos7_proc.pid_alive(gc))
        lr = self.tock()
        self.assertEqual(lr["ended"], [{"run": "k#1", "code": None, "lost": True}])
        self.assertFalse(aos7_proc.pid_alive(gc), "lost 前沒收掉舊 run 的殘留")
        self.assertIn("note", self.exit_of(node, "k"))
        self.assertEqual(self.tick()["started"], ["k#2"])
        self.assertEqual(aos7_proc.env_procs(node, "k", 1, runners=True), [])

    def test_old_run_leftover_not_taken_as_new_run(self):
        """同一個槽上一個 run 留下的孫程序：不算這次的活任務、kill 這次也不打到它。"""
        node = self.mknode("a", [{"name": "e", "argv": ["sh", "-c",
                                                        'if [ "$AOS7_RUN" = 1 ]; then ' + LEAVE_GC + 'exit 0; fi; sleep 60']}])
        self.tick()
        self.wait_ended(node, "e", 1)
        gc = gc_pid(node, "e", wait=5)
        self.assertTrue(aos7_proc.pid_alive(gc))
        self.tock()
        self.tick()
        pj = self.wait_pid(node, "e")
        self.assertEqual(pj["run"], 2)
        self.assertEqual(aos7_proc.env_procs(node, "e", 2), [pj["pid"]])
        # run 2 的主程序與 runner 死掉：身分掃描比 RUN，找不到這次的 → lost；run 1 的殘留不動
        os.kill(self.birth(node, "e")["runner"]["pid"], signal.SIGKILL)
        os.kill(pj["pid"], signal.SIGKILL)
        self.wait_for(lambda: not aos7_proc.pid_alive(pj["pid"]))
        time.sleep(0.1)
        lr = self.tock()
        self.assertIn({"run": "e#2", "code": None, "lost": True}, lr["ended"])
        self.assertNotIn("note", self.exit_of(node, "e"))
        self.assertTrue(aos7_proc.pid_alive(gc), "run 2 的 lost 判定打到了 run 1 的殘留")
        # 對 run 1 下的 kill（指定 run）不執行
        write_json(os.path.join(self.slot(node, "e"), "ctl.json"), {"op": "kill", "run": 1})
        self.tick()
        self.assertFalse(read_json(os.path.join(self.slot(node, "e"), "ctl-done.json"))["result"]["ok"])

    def test_runner_died_without_pid_json_is_lost(self):
        node = self.mknode("a")
        sd = self.slot(node, "x")
        dead = os.getpid() + 100000   # 不存在的 pid
        write_json(os.path.join(sd, "birth.json"), {"name": "x", "slot": "x", "run": 1, "round": 1,
                                                    "runner": {"pid": dead, "starttime": 1}})
        self.set_tasks(node, [{"name": "x", "argv": ["true"]}])
        write_json(os.path.join(node, ".aos", "round.json"), {"round": 1, "open": True})
        lr = self.tock()
        self.assertEqual(lr["ended"], [{"run": "x#1", "code": None, "lost": True}])

    def test_no_runner_young_birth_is_live_old_is_lost(self):
        node = self.mknode("a", [{"name": "x", "argv": ["true"]}])
        sd = self.slot(node, "x")
        write_json(os.path.join(sd, "birth.json"), {"name": "x", "slot": "x", "run": 1, "round": 1, "runner": None})
        self.assertEqual(aos7_task.judge(sd, node, "x", 2).state, aos7_task.LIVE)
        self.assertEqual(aos7_task.judge(sd, node, "x", 3).state, aos7_task.SUSPECT)

    def test_broken_birth_uses_node_tid_scan(self):
        """〔misuse M-2.3〕壞 birth 靠 NODE＋TID 掃描判活（A2-03，F31）"""
        node = self.mknode("a", [{"name": "k", "mode": "keep", "argv": SLEEP}])
        self.tick()
        self.wait_pid(node, "k")
        with open(os.path.join(self.slot(node, "k"), "birth.json"), "w") as f:
            f.write("{broken")
        self.assertEqual(self.view(node, "k", 1).state, aos7_task.LIVE)   # 有相符活程序＝活（run 不明）
        self.tock()
        self.assertEqual(self.tick()["started"], [])                        # keep 不雙開


class TestMounts(CoreCase):
    """〔core〕"""
    def test_mounts_made_and_rebuilt_per_run(self):
        node = self.mknode("a", [{"name": "m", "argv": ["true"], "mounts": {"bob": "b/inbox", "bad/": "x"}}])
        self.tick()
        sd = self.slot(node, "m")
        self.assertTrue(os.path.islink(os.path.join(sd, "mnt", "bob")))
        self.assertTrue(os.path.isdir(os.path.join(self.root, "b", "inbox")))
        b = self.birth(node, "m")
        self.assertIn("at", b["mounts"]["bob"])
        self.wait_ended(node, "m", 1)
        self.tock()
        self.set_tasks(node, [{"name": "m", "argv": ["true"], "mounts": {"c": "c"}}])
        self.tick()
        self.assertEqual(sorted(os.listdir(os.path.join(sd, "mnt"))), ["c"])

    def test_mount_request_served_and_restart_carries_dyn(self):
        node = self.mknode("a", [{"name": "m", "mode": "keep", "argv": SLEEP}])
        os.makedirs(os.path.join(self.root, "z"))
        self.tick()
        sd = self.slot(node, "m")
        self.wait_pid(node, "m")
        write_json(os.path.join(sd, "mount-req", "z.json"), {"name": "z", "path": "z", "why": "t"})
        self.tock()
        self.tick()
        self.assertTrue(read_json(os.path.join(sd, "mount-done", "z.json"))["result"]["ok"])
        self.assertFalse(os.path.exists(os.path.join(sd, "mount-req", "z.json")))
        self.assertTrue(self.birth(node, "m")["mounts"]["z"].get("dyn"))
        write_json(os.path.join(sd, "ctl.json"), {"op": "restart"})
        self.tock()
        self.tick()
        b = self.birth(node, "m")
        self.assertEqual(b["run"], 3)
        self.assertTrue(b["mounts"]["z"].get("dyn"))
        self.assertFalse(os.path.exists(os.path.join(sd, "mount-done")))   # 新 run 清掉


if __name__ == "__main__":
    unittest.main()
