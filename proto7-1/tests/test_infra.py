"""探針（probes/）與 astra-4 逼出來的基礎設施修補：tick／tock 的強健性、世代、spawn 批次、max_live、daemon 新 op 與 status 欄位。"""
import io
import json
import os
import subprocess
import sys
import time
import unittest
from contextlib import redirect_stderr

from test_core import BIN, SLEEPER
from test_core_daemon import DaemonCase
import aos7_daemon
import aos7_fs
import aos7_task
from aos7_fs import read_json, read_jsonl, write_json


class TestTickRobust(DaemonCase):
    def rounds(self, node):
        return read_jsonl(os.path.join(node, ".aos", "rounds.jsonl"))

    def test_keep_without_name_starts_once(self):
        node = self.mknode("a", [{"mode": "keep", "argv": SLEEPER}])
        self.tick()
        self.wait_for(lambda: self.state(node, "task-r1") == "live")
        self.tock()
        self.assertEqual(self.tick()["started"], [])

    def test_bad_item_skipped_and_recorded(self):
        node = self.mknode("a", [{"name": "bad", "argv": ["true"], "from_round": "5"},
                                 {"name": "good", "argv": ["true"]}])
        self.assertEqual(self.tick()["started"], ["good-r1"])
        self.tock()
        self.assertIn("bad", self.rounds(node)[-1]["tasks_error"][0])

    def test_unreadable_tasks_json_recorded(self):
        node = self.mknode("a")
        with open(os.path.join(node, ".aos", "tasks.json"), "w") as f:
            f.write('{"tasks": [')
        self.tick()
        self.tock()
        self.assertTrue(self.rounds(node)[-1]["tasks_error"])

    def test_spawn_batch_one_round_and_traceable(self):
        node = self.mknode("a")
        write_json(os.path.join(node, ".aos", "spawn", "b1.json"),
                   {"batch": [{"name": "m", "argv": ["true"]} for _ in range(3)]})
        self.assertEqual(self.tick()["started"], ["m-r1", "m-r1-2", "m-r1-3"])
        self.assertFalse(os.path.exists(os.path.join(node, ".aos", "spawn", "b1.json")))
        self.assertEqual(read_json(os.path.join(self.tdir(node, "m-r1-3"), "birth.json"))["spawn"], "b1.json")

    def test_max_live(self):
        node = self.mknode("a", [{"name": "s", "argv": SLEEPER, "max_live": 2}])
        self.assertEqual(len(self.tick()["started"]), 1)
        self.tock()
        self.assertEqual(len(self.tick()["started"]), 1)
        self.wait_for(lambda: len(aos7_task.live_tasks(node)) == 2)
        self.tock()
        self.assertEqual(self.tick()["started"], [])

    def test_gone_node_not_recreated(self):
        node = self.mknode("a")
        os.remove(os.path.join(node, ".aos", "timeline.json"))
        self.assertTrue(self.tick()["gone"])
        self.assertTrue(self.tock()["gone"])
        self.assertFalse(os.path.exists(os.path.join(node, ".aos", "round.json")))

    def test_second_tock_same_round_skipped(self):
        node = self.mknode("a")
        self.tick()
        self.tock()
        self.assertIn("skipped", self.tock())
        self.assertEqual(len(self.rounds(node)), 1)

    def test_stale_generation_writes_nothing(self):
        node = self.mknode("a")
        write_json(os.path.join(self.root, ".aosd", "gen.json"), {"gen": 2})
        env = aos7_fs.env_with_bin()
        env["AOS7_GEN"] = "1"
        p = subprocess.run([sys.executable, os.path.join(BIN, "aos7-tick"), self.root, "a"],
                           capture_output=True, text=True, env=env, timeout=20)
        self.assertTrue(json.loads(p.stdout)["stale"])
        self.assertFalse(os.path.exists(os.path.join(node, ".aos", "round.json")))
        env["AOS7_GEN"] = "2"
        p = subprocess.run([sys.executable, os.path.join(BIN, "aos7-tick"), self.root, "a"],
                           capture_output=True, text=True, env=env, timeout=20)
        self.assertEqual(json.loads(p.stdout)["round"], 1)

    def test_broken_task_does_not_block_others(self):
        node = self.mknode("a", [{"name": "x", "mode": "keep", "argv": SLEEPER},
                                 {"name": "y", "mode": "keep", "argv": SLEEPER}])
        self.tick()
        self.wait_for(lambda: self.state(node, "x-r1") == "live" and self.state(node, "y-r1") == "live")
        os.makedirs(os.path.join(self.tdir(node, "x-r1"), "tock.json"))      # 通知位置被改成資料夾
        write_json(os.path.join(self.tdir(node, "x-r1"), "birth.json"), [1])  # birth 改壞
        s = self.tock()
        self.assertEqual(s["errors"][0]["tid"], "x-r1")
        self.assertEqual(read_json(os.path.join(self.tdir(node, "y-r1"), "tock.json"))["round"], 1)
        self.assertEqual(self.tick()["started"], [])     # x 還活著：birth 壞了也從 tid 認得出名字，不再起一份

    def test_ended_has_name_and_ctl(self):
        node = self.mknode("a", [{"name": "s", "argv": SLEEPER}])
        self.tick()
        self.wait_for(lambda: self.state(node, "s-r1") == "live")
        self.prog("aos7-ctl", "task", self.tdir(node, "s-r1"), "kill")
        s = self.tock()
        self.assertEqual(s["ended"][0]["name"], "s")
        self.assertEqual(s["ended"][0]["by_ctl"]["op"], "kill")
        self.assertFalse(s["early"] is True)

    def test_kill_ended_task_reaps_leftover(self):
        node = self.mknode("a", [{"name": "f", "argv": ["sh", "-c", "(setsid sleep 60 &) ; exit 0"]}])
        self.tick()
        self.wait_for(lambda: self.state(node, "f-r1") == "ended")
        left = self.wait_for(lambda: aos7_task._escaped("f-r1", node, set()))
        ok, msg = aos7_task.kill_task(self.tdir(node, "f-r1"))
        self.assertTrue(ok, msg)
        self.assertIn("leftover", msg)
        self.assertFalse(any(aos7_task.pid_alive(p) for p in left))


class TestDaemonOps(DaemonCase):
    def test_wake_starts_next_round_early(self):
        self.mknode("a", interval_ms=3000)
        self.start_daemon()
        self.wait_for(lambda: self.node_round() >= 1 and self.status()["nodes"]["a"]["phase"] == "idle")
        t0 = time.monotonic()
        self.ctl("wake", "a")
        self.wait_for(lambda: self.node_round() >= 2, timeout=2.5)
        self.assertLess(time.monotonic() - t0, 2.5)
        self.assertEqual(self.status()["nodes"]["a"]["interval_ms"], 3000)
        self.ctl("stop")

    def test_resume_rounds_steps_then_pauses(self):
        node = self.mknode("a", interval_ms=30)
        write_json(os.path.join(self.root, ".aosd", "paused.json"), {"paused": ["a"]})
        self.start_daemon()
        self.wait_for(lambda: self.status().get("nodes", {}).get("a", {}).get("phase") == "paused")
        write_json(os.path.join(self.root, ".aosd", "ctl", "s.json"), {"op": "resume", "node": "a", "rounds": 3})
        self.wait_for(lambda: self.status()["nodes"]["a"]["paused"] and self.node_round() == 3, timeout=5)
        time.sleep(0.3)
        self.assertEqual(len(read_jsonl(os.path.join(node, ".aos", "rounds.jsonl"))), 3)
        self.ctl("stop")

    def test_pause_node_of_child_daemon_refused(self):
        os.makedirs(os.path.join(self.root, "sub", ".aosd"))
        self.mknode("a")
        self.start_daemon()
        write_json(os.path.join(self.root, ".aosd", "ctl", "p.json"), {"op": "pause", "node": "sub/x"})
        done = self.wait_for(lambda: read_json(os.path.join(self.root, ".aosd", "ctl-done", "p.json")))
        self.assertFalse(done["result"]["ok"])
        self.assertIn("queued_at", done["result"])
        self.ctl("stop")

    def test_bad_interval_does_not_kill_timeline(self):
        node = self.mknode("a", interval_ms=30)
        write_json(os.path.join(node, ".aos", "timeline.json"), {"interval_ms": "fast"})
        self.start_daemon()
        self.wait_for(lambda: self.status().get("nodes", {}).get("a", {}).get("last_error"))
        self.assertEqual(self.status()["nodes"]["a"]["last_error"]["prog"], "timeline")
        write_json(os.path.join(node, ".aos", "timeline.json"), {"interval_ms": 30})
        r = self.node_round()
        self.wait_for(lambda: self.node_round() >= r + 3, timeout=5)
        self.ctl("stop")

    def test_status_has_gen_and_stopped(self):
        self.mknode("a")
        p = self.start_daemon()
        self.wait_for(lambda: self.status().get("gen") == 1)
        self.ctl("stop")
        self.assertEqual(p.wait(10), 0)
        self.assertTrue(self.status()["stopped"])
        self.assertEqual(read_json(os.path.join(self.root, ".aosd", "gen.json"))["gen"], 1)

    def test_guard_keeps_daemon_alive_on_oserror(self):
        d = aos7_daemon.Daemon(self.root)
        os.makedirs(d.aosd, exist_ok=True)

        def boom():
            raise OSError(28, "No space left on device")
        with redirect_stderr(io.StringIO()) as err:
            d.guard(boom)
        self.assertEqual(d.io_errors, 1)
        self.assertIn("No space", err.getvalue())
        self.assertEqual(read_jsonl(os.path.join(d.aosd, "log.jsonl"))[-1]["ev"], "io-error")


class TestHelpers(DaemonCase):
    def test_edit_json_no_lost_update(self):
        path = os.path.join(self.root, "t.json")
        code = ("import sys; sys.path.insert(0, %r)\nimport aos7_fs\nfor i in range(50):\n"
                "    aos7_fs.edit_json(%r, lambda t: dict(t, n=t.get('n', 0) + 1), {})\n"
                % (os.path.join(os.path.dirname(BIN), "lib"), path))
        ps = [subprocess.Popen([sys.executable, "-c", code]) for _ in range(2)]
        for p in ps:
            p.wait(20)
        self.assertEqual(read_json(path)["n"], 100)

    def test_wait_tock_cli(self):
        tdir = os.path.join(self.root, "t")
        write_json(os.path.join(tdir, "tock.json"), {"round": 4})
        p = subprocess.run([sys.executable, os.path.join(BIN, "aos7-wait-tock"), "--task", tdir, "--after", "3"],
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(p.stdout.strip(), "4")
        p = subprocess.run([sys.executable, os.path.join(BIN, "aos7-wait-tock"), "--task", tdir, "--after", "4",
                            "--timeout", "0.1"], capture_output=True, text=True, timeout=10)
        self.assertEqual(p.returncode, 1)


if __name__ == "__main__":
    unittest.main()
