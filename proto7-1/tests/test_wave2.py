"""第二波探針（probes/llmkernel、llmops、selfprog、llmteam、chaos）逼出來的基礎設施修補。"""
import os
import signal
import subprocess
import sys
import time
import unittest

from test_core import BIN, SLEEPER
from test_core_daemon import DaemonCase
import aos7_task
from aos7_fs import read_json, read_jsonl, write_json


class TestFifoAndOddFiles(DaemonCase):
    """控制面的檔被換成 FIFO／資料夾：不卡、不每圈重處理（chaos B5、B10；llmops）。"""

    def test_daemon_ctl_fifo_dir_and_bad_name(self):
        self.mknode("a", interval_ms=50)
        cdir = os.path.join(self.root, ".aosd", "ctl")
        os.makedirs(cdir)
        os.mkfifo(os.path.join(cdir, "f.json"))
        os.makedirs(os.path.join(cdir, "d.json"))
        with open(os.path.join(cdir, "x.txt"), "w") as f:
            f.write('{"op": "pause", "node": "a"}')
        p = self.start_daemon()
        done = os.path.join(self.root, ".aosd", "ctl-done")
        for n in ("f.json", "d.json", "x.txt.json"):
            r = self.wait_for(lambda: read_json(os.path.join(done, n)), msg="沒有 %s 的回條" % n)
            self.assertFalse(r["result"]["ok"])
        self.assertEqual(os.listdir(cdir), [])
        self.ctl("pause", "a")
        self.wait_for(lambda: self.status().get("nodes", {}).get("a", {}).get("phase") == "paused")
        self.assertEqual(len([x for x in self.log() if x.get("file") == "d.json"]), 1)
        self.ctl("stop")
        self.assertEqual(p.wait(10), 0)

    def test_fifo_tasks_json_and_spawn_do_not_hang_tick(self):
        node = self.mknode("a")
        os.remove(os.path.join(node, ".aos", "tasks.json"))
        os.mkfifo(os.path.join(node, ".aos", "tasks.json"))
        os.makedirs(os.path.join(node, ".aos", "spawn"))
        os.mkfifo(os.path.join(node, ".aos", "spawn", "s.json"))
        t0 = time.monotonic()
        self.tick()
        self.assertLess(time.monotonic() - t0, 5)
        self.assertFalse(os.path.exists(os.path.join(node, ".aos", "spawn", "s.json")))
        errs = read_json(os.path.join(node, ".aos", "round.json"))["tasks_error"]
        self.assertTrue(any("不是一般檔" in e for e in errs), errs)


class TestBadInputsIsolated(DaemonCase):
    """一個壞輸入只影響它自己（chaos B1～B4、B6、B9）。"""

    def test_new_node_with_list_round_json(self):
        self.mknode("a", interval_ms=50)
        node = self.mknode("b", interval_ms=50)
        write_json(os.path.join(node, ".aos", "round.json"), [])
        p = self.start_daemon()
        self.wait_for(lambda: self.node_round("b") >= 2 and self.node_round("a") >= 2)
        self.assertIsNone(p.poll())
        self.ctl("stop")

    def test_bad_name_item_skipped(self):
        node = self.mknode("a", [{"name": 5, "argv": ["true"]}, {"name": "good", "argv": ["true"]}])
        self.assertEqual(self.tick()["started"], ["good-r1"])
        self.assertTrue(read_json(os.path.join(node, ".aos", "round.json"))["tasks_error"])

    def test_poison_spawn_removed_and_keep_still_starts(self):
        node = self.mknode("a", [{"name": "k", "mode": "keep", "argv": ["true"]}])
        write_json(os.path.join(node, ".aos", "spawn", "p.json"), {"name": ["x"], "argv": ["true"]})
        write_json(os.path.join(node, ".aos", "spawn", "q.json"), {"name": "q", "argv": ["sleep", 5]})
        self.assertEqual(self.tick()["started"], ["k-r1"])
        self.assertEqual(os.listdir(os.path.join(node, ".aos", "spawn")), [])
        self.assertEqual(len(read_json(os.path.join(node, ".aos", "round.json"))["tasks_error"]), 2)

    def test_runner_writes_exit_for_non_string_argv(self):
        node = self.mknode("a")
        tdir = self.tdir(node, "x-r1")
        write_json(os.path.join(tdir, "birth.json"), {"tid": "x-r1", "name": "x", "argv": ["sleep", 5]})
        subprocess.run([sys.executable, os.path.join(BIN, "aos7-run"), tdir], cwd=node, timeout=10,
                       env=dict(os.environ, AOS7_NODE=node))
        self.assertEqual(read_json(os.path.join(tdir, "exit.json"))["code"], 127)

    def test_broken_round_continues_from_rounds_jsonl(self):
        node = self.mknode("a")
        for _ in range(3):
            self.tick()
            self.tock()
        write_json(os.path.join(node, ".aos", "round.json"), {"round": "3", "open": False})
        self.assertEqual(self.tick()["round"], 4)

    def test_negative_interval_is_an_error(self):
        node = self.mknode("a")
        write_json(os.path.join(node, ".aos", "timeline.json"), {"interval_ms": -5})
        self.start_daemon()
        err = self.wait_for(lambda: self.status().get("nodes", {}).get("a", {}).get("last_error"))
        self.assertEqual(err["prog"], "timeline")
        self.wait_for(lambda: self.status()["nodes"]["a"]["interval_ms"] == 1000)
        self.ctl("stop")


class TestUnclosedRound(DaemonCase):
    def test_reappearing_node_closes_open_round_first(self):
        """回合中拿掉 timeline.json、node 消失後放回：那回合補一行 incomplete: unclosed，rounds.jsonl 不缺號（chaos B8）。"""
        node = self.mknode("a", [{"name": "s", "argv": SLEEPER}], interval_ms=2000)
        self.start_daemon()
        self.wait_for(lambda: self.status().get("nodes", {}).get("a", {}).get("phase") == "running")
        tl = os.path.join(node, ".aos", "timeline.json")
        os.rename(tl, tl + ".off")
        self.wait_for(lambda: [x for x in self.log() if x.get("ev") == "node-"])
        os.rename(tl + ".off", tl)
        rows = self.wait_for(lambda: (lambda r: r if len(r) >= 2 else None)(
            read_jsonl(os.path.join(node, ".aos", "rounds.jsonl"))), timeout=10)
        self.assertEqual([x["round"] for x in rows[:2]], [1, 2])
        self.assertEqual(rows[0].get("incomplete"), "unclosed")
        self.ctl("stop", "--kill")


class TestKillTrust(DaemonCase):
    def test_forged_pgid_is_not_killed(self):
        """任務把 pid.json 的 pgid 改成別人的群組：kill 不打那個群組（chaos B7）。"""
        victim = subprocess.Popen(["sleep", "30"], start_new_session=True)
        self.procs.append(victim)
        node = self.mknode("a", [{"name": "s", "argv": SLEEPER}])
        self.tick()
        tdir = self.tdir(node, "s-r1")
        pid = self.wait_for(lambda: read_json(os.path.join(tdir, "pid.json")))
        write_json(os.path.join(tdir, "pid.json"), dict(pid, pgid=victim.pid))
        ok, msg = aos7_task.kill_task(tdir)
        self.assertFalse(ok)
        self.assertIsNone(victim.poll())
        self.wait_for(lambda: not aos7_task.pid_alive(pid["pid"]), msg="環境變數相符的任務本身沒收掉")
        victim.kill()


class TestDaemonSmallFixes(DaemonCase):
    def test_paused_json_written_at_start_and_stop_rejects_node(self):
        self.mknode("a", interval_ms=50)
        p = self.start_daemon()
        self.wait_for(lambda: self.status().get("nodes"))
        self.assertEqual(read_json(os.path.join(self.root, ".aosd", "paused.json")), {"paused": []})
        write_json(os.path.join(self.root, ".aosd", "ctl", "s.json"), {"op": "stop", "node": "a"})
        r = self.wait_for(lambda: read_json(os.path.join(self.root, ".aosd", "ctl-done", "s.json")))
        self.assertFalse(r["result"]["ok"])
        self.assertIsNone(p.poll())
        self.ctl("stop")

    def test_spawn_keep_respects_live(self):
        """spawn 一個 keep 項目、同名已有活的：不起第二份（llmops：補起一份變兩份）。"""
        node = self.mknode("a", [{"name": "w", "mode": "keep", "argv": SLEEPER}])
        self.tick()
        self.wait_for(lambda: self.state(node, "w-r1") == "live")
        self.tock()
        write_json(os.path.join(node, ".aos", "spawn", "w.json"), {"name": "w", "mode": "keep", "argv": SLEEPER})
        self.assertEqual(self.tick()["started"], [])
        self.assertFalse(os.path.exists(os.path.join(node, ".aos", "spawn", "w.json")))


class TestSubroot(DaemonCase):
    def test_subroot_must_be_inside_node(self):
        node = self.mknode("lab", [{"name": "d", "argv": ["true"], "subroot": "sub"}])
        self.tick("lab")
        b = read_json(os.path.join(self.tdir(node, "d-r1"), "birth.json"))
        self.assertIn("subroot_error", b)
        self.assertFalse(os.path.exists(os.path.join(self.root, "sub", ".aosd")))

    def test_subroot_env_and_child_daemon(self):
        """argv 寫 $AOS7_SUBROOT 就指到子根（llmteam 誤解 1：寫成相對空間根的路徑，cwd 是 node 時跑錯地方）。"""
        node = self.mknode("lab", [{"name": "d", "mode": "keep", "argv": ["aos7-daemon", "$AOS7_SUBROOT"],
                                    "subroot": "lab/sub"}], interval_ms=100)
        self.mknode("lab/sub/w", interval_ms=50)
        self.start_daemon(env={"AOS7_AUDIT": "1"})
        st = self.wait_for(lambda: read_json(os.path.join(node, "sub", ".aosd", "status.json")), msg="子 daemon 沒起來")
        self.assertEqual(os.path.realpath(st["root"]), os.path.realpath(os.path.join(node, "sub")))
        self.wait_for(lambda: (read_json(os.path.join(node, "sub", ".aosd", "status.json")) or {})
                      .get("nodes", {}).get("w", {}).get("round", 0) >= 2)
        self.ctl("stop", "--kill")
        time.sleep(0.3)
        bad = [x for x in read_jsonl(os.path.join(self.tdir(node, "d-r1"), "writes.jsonl")) if not x.get("ok")]
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
