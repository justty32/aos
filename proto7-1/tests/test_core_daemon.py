"""daemon 的測試：提前 tock、ctl pause/resume/stop、SIGTERM、同 root 第二個 daemon、路一（任務開子 daemon）。"""
import os
import signal
import subprocess
import sys
import time
import unittest

from test_core import BIN, SLEEPER, CoreCase
import aos7_daemon_timeline
import aos7_task
from aos7_fs import read_jsonl, read_json, write_json


class DaemonCase(CoreCase):
    def start_daemon(self, root=None):
        p = subprocess.Popen([sys.executable, os.path.join(BIN, "aos7-daemon"), root or self.root],
                             stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, start_new_session=True)
        self.procs.append(p)
        return p

    def status(self, root=None):
        return read_json(os.path.join(root or self.root, ".aosd", "status.json"), {})

    def node_round(self, nid="a"):
        return self.status().get("nodes", {}).get(nid, {}).get("round", 0)

    def log(self, root=None):
        return read_jsonl(os.path.join(root or self.root, ".aosd", "log.jsonl"))

    def ctl(self, *args):
        return self.prog("aos7-ctl", "daemon", self.root, *args)


class TestDaemon(DaemonCase):
    def test_early_tock(self):
        self.mknode("a", [{"name": "q", "argv": ["true"]}], interval_ms=3000)
        self.start_daemon()
        tock = self.wait_for(lambda: [x for x in self.log() if x.get("ev") == "tock"], msg="沒有 tock")[0]
        self.assertTrue(tock["early"])
        self.assertEqual(tock["ended"], [{"tid": "q-r1", "code": 0}])
        self.ctl("stop")

    def test_pause_resume_stop_kill(self):
        node = self.mknode("a", [{"name": "s", "mode": "keep", "argv": SLEEPER}], interval_ms=50)
        p = self.start_daemon()
        self.wait_for(lambda: self.node_round() >= 2)
        self.ctl("pause", "a")
        self.wait_for(lambda: self.status()["nodes"]["a"]["phase"] == "paused")
        r = self.node_round()
        time.sleep(0.3)
        self.assertEqual(self.node_round(), r)
        self.assertEqual(read_json(os.path.join(self.root, ".aosd", "paused.json")), {"paused": ["a"]})
        self.ctl("resume", "a")
        self.wait_for(lambda: self.node_round() >= r + 2)
        live = self.status()["nodes"]["a"]["live"]
        self.assertEqual(len(live), 1)
        self.ctl("stop", "--kill")
        self.assertEqual(p.wait(10), 0)
        self.assertEqual(aos7_task.live_tasks(node), [])
        done = os.listdir(os.path.join(self.root, ".aosd", "ctl-done"))
        self.assertEqual(len(done), 3)
        self.assertTrue(self.status()["stopping"])

    def test_stop_without_kill_leaves_tasks(self):
        node = self.mknode("a", [{"name": "s", "mode": "keep", "argv": SLEEPER}], interval_ms=50)
        p = self.start_daemon()
        self.wait_for(lambda: aos7_task.live_tasks(node))
        self.ctl("stop")
        self.assertEqual(p.wait(10), 0)
        self.assertEqual(len(aos7_task.live_tasks(node)), 1)   # 沒 kill：任務照跑（tearDown 收）

    def test_sigterm_is_stop_kill(self):
        node = self.mknode("a", [{"name": "s", "mode": "keep", "argv": SLEEPER}], interval_ms=50)
        p = self.start_daemon()
        self.wait_for(lambda: self.status().get("nodes", {}).get("a", {}).get("live"))
        p.send_signal(signal.SIGTERM)
        self.assertEqual(p.wait(10), 0)
        self.assertEqual(aos7_task.live_tasks(node), [])

    def test_second_daemon_refused(self):
        self.mknode("a", interval_ms=50)
        self.start_daemon()
        self.wait_for(lambda: self.status().get("pid"))
        p2 = self.start_daemon()
        self.assertEqual(p2.wait(10), 1)
        self.ctl("stop")

    def test_bad_ctl_moved_with_error(self):
        self.mknode("a", interval_ms=50)
        self.start_daemon()
        self.wait_for(lambda: self.status().get("pid"))
        with open(os.path.join(self.root, ".aosd", "ctl", "x.json"), "w") as f:
            f.write("{壞掉")
        write_json(os.path.join(self.root, ".aosd", "ctl", "y.json"), {"op": "fly"})
        done = os.path.join(self.root, ".aosd", "ctl-done")
        self.wait_for(lambda: os.path.exists(os.path.join(done, "y.json")))
        self.assertFalse(read_json(os.path.join(done, "x.json"))["result"]["ok"])
        self.assertFalse(read_json(os.path.join(done, "y.json"))["result"]["ok"])
        self.ctl("stop")

    def test_node_appears_and_round_continues(self):
        node = self.mknode("a", interval_ms=50)
        write_json(os.path.join(node, ".aos", "round.json"), {"round": 41, "open": False})
        p = self.start_daemon()
        self.wait_for(lambda: self.node_round() >= 42)
        self.mknode("b", interval_ms=50)
        self.wait_for(lambda: self.node_round("b") >= 1)
        self.ctl("stop")
        p.wait(10)
        rounds = [r["round"] for r in read_jsonl(os.path.join(node, ".aos", "rounds.jsonl"))]
        self.assertEqual(rounds[0], 42)
        self.assertEqual(rounds, list(range(42, 42 + len(rounds))))
        self.assertFalse(os.path.exists(os.path.join(node, ".aos", "rounds")))


class TestRouteOne(DaemonCase):
    """S-21 路一：父時間線的任務就是 `aos7-daemon sub`；用 ctl.json kill 它，子 daemon 的任務也被收掉。"""

    def test_child_daemon_as_task(self):
        sub = os.path.join(self.root, "sub")
        os.makedirs(os.path.join(sub, ".aosd"))      # 先建好，免得父 daemon 把 sub 當自己的 node（P-11）
        child = self.mknode(".", [{"name": "s", "mode": "keep", "argv": SLEEPER}], interval_ms=50, root=sub)
        parent = self.mknode(".", [{"name": "subd", "mode": "keep", "argv": ["aos7-daemon", "$AOS7_TASK/mnt/sub"],
                                         "mounts": {"sub": "sub"}}],
                             interval_ms=50)
        p = self.start_daemon()
        self.wait_for(lambda: aos7_task.live_tasks(child), msg="子 daemon 沒起任務")
        self.assertEqual(list(self.status()["nodes"]), ["."])        # sub 不是父的 node
        grand = self.wait_for(lambda: read_json(os.path.join(aos7_task.task_dir(child, "s-r1"), "pid.json")))
        self.prog("aos7-ctl", "task", aos7_task.task_dir(parent, "subd-r1"), "kill", "路一測試")
        self.wait_for(lambda: os.path.exists(os.path.join(aos7_task.task_dir(parent, "subd-r1"), "ctl-done.json")))
        self.wait_for(lambda: aos7_task.task_state(aos7_task.task_dir(parent, "subd-r1")) == "ended")
        self.assertEqual(read_json(os.path.join(aos7_task.task_dir(parent, "subd-r1"), "exit.json"))["code"], 0)
        self.assertFalse(aos7_task.group_alive(grand["pgid"]))      # 孫任務被子 daemon 帶走
        # keep 會在下個 tick 把子 daemon 起回來（P-09）；最後父 daemon stop --kill，整串都要收乾淨
        self.ctl("stop", "--kill")
        self.assertEqual(p.wait(10), 0)
        self.assertEqual(aos7_task.live_tasks(parent), [])
        self.assertEqual(aos7_task.live_tasks(child), [])



class TestTickFailure(CoreCase):
    """tick 寫了新回合卻失敗（rc≠0、沒印 stdout）：回合數以 round.json 為準，status 帶 last_error（astra 試玩二-1）。"""

    def test_round_from_disk_and_last_error(self):
        node = self.mknode("a")

        class FakeDaemon:
            root, stopping, kill_on_stop = self.root, False, False
            logs = []

            def is_paused(self, nid):
                return False

            def log(self, **kw):
                self.logs.append(kw)

        d = FakeDaemon()

        def fake_run(name, root, nid):
            if name == "aos7-tick":
                write_json(os.path.join(node, ".aos", "round.json"), {"round": 3, "open": True})
                return 1, None, "Traceback: boom"
            d.stopping = True
            return 0, {}, ""
        tl = aos7_daemon_timeline.Timeline(d, "a")
        orig = aos7_daemon_timeline.run_prog
        aos7_daemon_timeline.run_prog = fake_run
        try:
            tl._loop()
        finally:
            aos7_daemon_timeline.run_prog = orig
        self.assertEqual(tl.round, 3)
        self.assertEqual((tl.last_error["prog"], tl.last_error["rc"], tl.last_error["round"]), ("tick", 1, 3))
        self.assertIn("boom", tl.last_error["err"])


if __name__ == "__main__":
    unittest.main()
