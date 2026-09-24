"""proto5-2 daemon（按池、宣告式）的真父子行程測試：scale、補／收／重拉、退避、節流、fd 預算、kill、halt、重開。"""
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
import unittest
from unittest import mock

import aos_client
import aos_daemon
import aos_daemon_pools
import aos_home

from _daemon_util import CLI, PY, DaemonCase, read_json, wait_for, write_json


class ScaleTest(DaemonCase):
    def test_scale_fills_pool_kid_files_summary_one_pipe(self):
        self.start()
        target = self.targets(3)
        self.assertEqual(self.ok(self.scale(count=3, target=target, decl=[5, 0])),
                         {"pool": "p", "count": 3, "ver": 1})
        summary = self.running("p", 3)
        self.assertEqual({k: summary[k] for k in ("pool", "owner", "count", "ver", "pending", "dead",
                                                  "failed", "killing", "draining", "restarting")},
                         {"pool": "p", "owner": "/k", "count": 3, "ver": 1, "pending": 0, "dead": 0,
                          "failed": 0, "killing": 0, "draining": 0, "restarting": 0})
        decl = read_json(self.home / "pools/p/pool.json")
        self.assertEqual((decl["count"], decl["skip"], decl["ver"], decl["decl"], decl["target"]),
                         (3, [], 1, [5, 0], target))
        self.assertEqual(set(self.state()), {"pid", "stopping", "current"})
        for i in range(3):
            start = wait_for(lambda: self.starts("p", i))[0]
            kid = self.kid("p", i)
            self.assertEqual((kid["pid"], kid["gen"], kid["state"], kid["streak"], kid["next_at"]),
                             (start["pid"], 1, "running", 0, None))
            self.assertEqual(aos_daemon.pool_kid(self.home, "p", i), kid)
            self.assertEqual(start["pgid"], start["pid"])                    # 自己一個 process group
            self.assertEqual(start["sid"], os.getsid(self.proc.pid))         # 同一個 session
            self.assertEqual(start["fd1"], "/dev/null")                      # 只留 fd 0 一條 pipe
        self.assertEqual(aos_daemon.pool_summary(self.home, "p")["running"], 3)
        self.assertIsNone(aos_daemon.pool_summary(self.home, "nope"))
        self.assertIsNone(aos_daemon.pool_kid(self.home, "p", 9))
        self.halt()

    def test_ver_only_changes_when_members_change(self):
        self.start()
        target = self.targets(4)
        self.assertEqual(self.ok(self.scale(count=2, target=target))["ver"], 1)
        self.assertEqual(self.ok(self.scale(count=2, target=target))["ver"], 1)      # 重送：冪等
        self.assertEqual(self.ok(self.scale(count=2, skip=[5]))["ver"], 1)            # 成員沒變
        self.assertEqual(self.ok(self.scale(count=2, home="/h/{name}"))["ver"], 1)    # 只換樣板
        self.assertEqual(self.ok(self.scale(count=2, skip=[0]))["ver"], 2)            # 0 退休 → 1、2
        self.assertEqual(read_json(self.home / "pools/p/pool.json")["home"], "/h/{name}")
        wait_for(lambda: self.kid("p", 0) is None and (self.summary() or {}).get("running") == 2)
        self.assertEqual(self.kid("p", 2)["state"], "running")
        self.halt()

    def test_scale_errors(self):
        self.set_info(max_children=3)
        self.start()
        target = self.targets(3)
        bad = [{"pool": "../x", "owner": "/k", "count": 1, "target": target},
               {"pool": "p", "owner": "", "count": 1, "target": target},
               {"pool": "p", "owner": "/k", "count": -1, "target": target},
               {"pool": "p", "owner": "/k", "count": True, "target": target},
               {"pool": "p", "owner": "/k", "count": 1, "skip": [1, 1], "target": target},
               {"pool": "p", "owner": "/k", "count": 1, "skip": [-1], "target": target},
               {"pool": "p", "owner": "/k", "count": 1, "target": "rel/{name}.json"},
               {"pool": "p", "owner": "/k", "count": 1, "target": "/abs/x.json"},
               {"pool": "p", "owner": "/k", "count": 1, "target": "/{name}/{name}.json"},
               {"pool": "p", "owner": "/k", "count": 1, "target": target, "decl": [1]},
               {"pool": "p", "owner": "/k", "count": 1},                                   # 池不在要 target
               "not-an-object"]
        for params in bad:
            with self.subTest(params=params):
                self.assertEqual(self.call("scale", params)["error"]["code"], -32602)
        self.assertFalse((self.home / "pools/p").exists())
        # 池不在、count 0：什麼都不建，ver 0
        self.assertEqual(self.ok(self.scale(count=0)), {"pool": "p", "count": 0, "ver": 0})
        self.assertFalse((self.home / "pools/p").exists())
        self.ok(self.scale(count=2, target=target, decl=[5, 3]))
        self.assertEqual(self.code(self.scale(count=2, owner="/other")), "NameTaken")
        self.assertIn("/k", self.scale(count=2, owner="/other")["error"]["message"])
        self.assertEqual(self.code(self.scale(count=1, decl=[5, 2])), "Stale")
        self.assertEqual(self.code(self.scale(count=1, decl=[4, 9])), "Stale")
        self.assertEqual(read_json(self.home / "pools/p/pool.json")["count"], 2)      # 什麼都沒改
        self.assertEqual(self.ok(self.scale(count=2, decl=[5, 3]))["ver"], 1)          # 相等＝重送
        self.assertEqual(self.ok(self.scale(count=2))["ver"], 1)                       # 沒給 decl 不擋
        self.assertEqual(read_json(self.home / "pools/p/pool.json")["decl"], [5, 3])   # 舊 decl 留著
        self.assertEqual(self.code(self.scale("q", 2, target=self.targets(2, pool="q"))), "TooMany")
        self.assertFalse((self.home / "pools/q").exists())
        self.assertEqual(self.ok(self.scale("q", 1, target=self.targets(1, pool="q")))["ver"], 1)
        self.assertEqual(self.call("spawn", {"name": "x", "target": target})["error"]["code"], -32601)
        self.halt()

    def test_shrink_drains_and_count_zero_removes_pool(self):
        self.start()
        target = self.targets(3)
        self.ok(self.scale(count=3, target=target))
        self.running("p", 3)
        self.assertEqual(self.ok(self.scale(count=1))["ver"], 2)
        wait_for(lambda: self.summary()["running"] == 1 and self.summary()["draining"] == 0)
        self.assertEqual(sorted(os.listdir(self.home / "pools/p/kids")), ["0.json"])
        self.assertEqual(self.ok(self.scale(count=0))["ver"], 3)
        wait_for(lambda: not (self.home / "pools/p").exists())
        # 名字空出來：別的 owner 可以用，ver 從 1 算
        self.assertEqual(self.ok(self.scale(count=1, owner="/other", target=target))["ver"], 1)
        self.running("p", 1)
        self.assertEqual(self.kid("p", 0)["gen"], 1)
        self.halt()

    def test_readded_while_draining_comes_back(self):
        self.set_info(stop_wait_ms=150, kill_wait_ms=150)
        self.start()
        target = self.targets(2, "kill")
        self.ok(self.scale(count=2, target=target))
        self.running("p", 2)
        wait_for(lambda: self.starts("p", 1))
        self.ok(self.scale(count=1))
        wait_for(lambda: self.summary()["draining"] == 1)
        self.ok(self.scale(count=2))
        wait_for(lambda: self.summary()["killing"] == 1)          # 又是成員：draining → killing
        wait_for(lambda: len(self.starts("p", 1)) == 2)            # 死透後當 pending 拉回來
        self.assertEqual(self.kid("p", 1)["gen"], 2)
        self.assertEqual(self.kid("p", 1)["streak"], 0)
        self.halt()


class RestartTest(DaemonCase):
    def gaps(self, pool, i, n):
        starts = wait_for(lambda: len(self.starts(pool, i)) >= n and self.starts(pool, i), timeout=10)
        return [b["at"] - a["at"] for a, b in zip(starts, starts[1:])][:n - 1]

    def test_backoff_doubles_up_to_max_any_exit_code(self):
        self.set_info(restart_delay_ms=100, restart_max_ms=400)
        self.start()
        self.ok(self.scale(count=1, target=self.targets(1, "exit0")))    # 退 0 也重拉
        gaps = self.gaps("p", 0, 5)
        for gap, want in zip(gaps, (0.1, 0.2, 0.4, 0.4)):
            self.assertGreaterEqual(gap, want - 0.01, gaps)
            self.assertLess(gap, want + 0.25, gaps)
        kid = self.kid("p", 0)
        self.assertEqual(kid["last_exit"], 0)
        self.assertGreaterEqual(kid["exits"], 4)
        self.halt()

    def test_stable_resets_streak_and_restarting(self):
        mode = self.root / "mode"
        mode.write_text("exit1")
        self.set_info(restart_delay_ms=60, restart_max_ms=5000, stable_ms=150)
        self.start()
        self.ok(self.scale(count=1, target=self.targets(1, "@%s" % mode)))
        wait_for(lambda: (self.kid("p", 0) or {}).get("streak") == 2 and self.kid("p", 0)["state"] == "dead")
        mode.write_text("after400:1")
        wait_for(lambda: self.summary()["restarting"] == 1)       # 重拉了、還沒穩
        wait_for(lambda: self.summary()["restarting"] == 0 and self.summary()["running"] == 1)
        # 活過 stable_ms 才死：streak 先歸 0 再加 1，等待回到起點
        dead = wait_for(lambda: self.kid("p", 0)["state"] == "dead" and self.kid("p", 0)["gen"] >= 4
                        and self.kid("p", 0))
        self.assertEqual(dead["streak"], 1)
        self.assertLess(dead["next_at"] - time.time(), 0.07)
        self.halt()

    def test_spawn_failed_backoff_and_new_target_clears_wait(self):
        self.set_info(restart_delay_ms=5000)
        self.start()
        target = self.targets(1)
        self.ok(self.scale(count=1, target=str(self.root / "missing/{name}.json")))
        failed = wait_for(lambda: (self.kid("p", 0) or {}).get("state") == "failed" and self.kid("p", 0))
        self.assertEqual((failed["pid"], failed["gen"], failed["streak"]), (None, 0, 1))
        self.assertGreater(failed["next_at"] - time.time(), 3)
        self.assertEqual(self.summary()["failed"], 1)
        self.assertIn("SpawnFailed", self.log())
        self.assertEqual(self.ok(self.scale(count=1, target=target))["ver"], 1)
        self.running("p", 1)
        self.assertEqual(self.kid("p", 0)["gen"], 1)
        self.halt()

    def test_token_bucket_throttles_spawns(self):
        self.set_info(spawn_per_sec=5)
        self.start()
        self.ok(self.scale(count=8, target=self.targets(8)))
        self.running("p", 8)
        wait_for(lambda: all(self.starts("p", i) for i in range(8)))
        starts = sorted(self.starts("p", i)[0]["at"] for i in range(8))
        self.assertLess(starts[4] - starts[0], 0.15)               # 桶是滿的：前 5 顆一起
        self.assertGreaterEqual(starts[5] - starts[0], 0.15)       # 之後一秒 5 顆
        self.assertGreaterEqual(starts[7] - starts[0], 0.5)
        self.halt()

    def test_pools_take_turns(self):
        self.set_info(spawn_per_sec=4)
        for pool, count in (("a", 8), ("b", 2)):
            (self.home / "pools" / pool / "kids").mkdir(parents=True)
            write_json(self.home / "pools" / pool / "pool.json",
                       {"pool": pool, "owner": "/k", "count": count, "skip": [], "ver": 1,
                        "target": self.targets(count, pool=pool)})
        self.start()
        self.running("b", 2)
        wait_for(lambda: all(self.starts("b", i) for i in range(2)))
        first_a = sorted(self.starts("a", i)[0]["at"] for i in range(8) if self.starts("a", i))
        last_b = max(self.starts("b", i)[0]["at"] for i in range(2))
        self.assertLess(last_b, first_a[2] if len(first_a) > 2 else float("inf"), first_a)
        self.halt()

    def test_fd_budget_waits_for_draining_pool(self):
        self.set_info(max_children=2, stop_wait_ms=200, kill_wait_ms=200)
        self.start()
        self.ok(self.scale("a", 2, target=self.targets(2, "kill", pool="a")))
        self.running("a", 2)
        wait_for(lambda: self.starts("a", 1))
        self.ok(self.scale("a", 0))
        self.ok(self.scale("b", 2, target=self.targets(2, pool="b")))    # 宣告合計 2：合法
        time.sleep(.2)
        self.assertEqual((self.summary("b") or {}).get("running", 0), 0)  # a 還在 killing：先不拉
        self.assertEqual(self.summary("a")["draining"], 2)
        self.running("b", 2)
        wait_for(lambda: not (self.home / "pools/a").exists())
        self.halt()


class KillTest(DaemonCase):
    def test_kill_restarts_without_backoff(self):
        self.set_info(restart_delay_ms=5000)
        mode = self.root / "mode"
        mode.write_text("normal")
        self.start()
        self.ok(self.scale(count=2, target=self.targets(2, "@%s" % mode)))
        self.running("p", 2)
        self.assertEqual(self.ok(self.call("kill", {"pool": "p", "names": ["0", "7"]})),
                         {"killed": ["0"], "skipped": {"7": "not-member"}})
        wait_for(lambda: len(self.starts("p", 0)) == 2)
        kid = self.kid("p", 0)
        self.assertEqual((kid["gen"], kid["streak"], kid["exits"]), (2, 0, 1))
        # dead 的：清掉等待，馬上重拉
        mode.write_text("exit3")
        self.ok(self.call("kill", {"pool": "p", "names": ["1"]}))
        dead = wait_for(lambda: self.kid("p", 1)["state"] == "dead" and self.kid("p", 1))
        self.assertGreater(dead["next_at"] - time.time(), 3)
        mode.write_text("normal")
        self.assertEqual(self.ok(self.call("kill", {"pool": "p", "all": True}))["killed"], ["0", "1"])
        wait_for(lambda: len(self.starts("p", 1)) == 3)
        self.assertEqual(self.code(self.call("kill", {"pool": "zz", "all": True})), "NotFound")
        for params in ({"pool": "p"}, {"pool": "p", "all": True, "names": ["1"]},
                       {"pool": "p", "names": ["01"]}, {"pool": "p", "names": "1"},
                       {"pool": "p", "all": 1}):
            self.assertEqual(self.call("kill", params)["error"]["code"], -32602, params)
        self.halt()

    def test_kill_skips_pending_and_killing(self):
        self.set_info(spawn_per_sec=1, stop_wait_ms=300, kill_wait_ms=300)
        self.start()
        self.ok(self.scale(count=2, target=self.targets(2, "kill")))
        self.running("p", 1)
        wait_for(lambda: self.starts("p", 0))
        self.assertEqual(self.ok(self.call("kill", {"pool": "p", "all": True})),
                         {"killed": ["0"], "skipped": {"1": "pending"}})
        self.assertEqual(self.ok(self.call("kill", {"pool": "p", "names": ["0"]}))["skipped"], {"0": "killing"})
        self.halt()


class HaltBootTest(DaemonCase):
    def test_halt_keeps_pool_json_and_boot_brings_kids_back(self):
        self.start()
        self.ok(self.scale(count=2, target=self.targets(2), home=str(self.root / "h/{name}")))
        self.running("p", 2)
        self.halt()
        self.assertTrue((self.home / "pools/p/pool.json").exists())
        for i in range(2):
            kid = self.kid("p", i)
            self.assertEqual((kid["state"], kid["pid"], kid["gen"], kid["exits"]), ("pending", None, 1, 1))
        self.start()
        self.running("p", 2)
        self.assertEqual([self.kid("p", i)["gen"] for i in range(2)], [2, 2])
        self.assertEqual(self.ok(self.scale(count=2))["ver"], 1)
        self.halt()

    def test_stopping_rejects_scale_kill_still_answers(self):
        self.set_info(stop_wait_ms=300, kill_wait_ms=300)
        self.start()
        self.ok(self.scale(count=1, target=self.targets(1, "kill")))
        wait_for(lambda: self.starts("p", 0))
        aos_home.post_request(self.home, aos_client.new_name("stop"), {"jsonrpc": "2.0", "method": "stop"})
        wait_for(lambda: self.state().get("stopping"))
        self.assertEqual(self.code(self.scale(count=2)), "Stopping")
        self.assertEqual(self.ok(self.call("kill", {"pool": "p", "all": True}))["skipped"], {"0": "killing"})
        self.assertEqual(self.proc.wait(timeout=6), 0)
        self.assertEqual(read_json(self.home / "pools/p/pool.json")["count"], 1)

    def test_batch_ladder_stop_then_term_then_kill(self):
        self.set_info(stop_wait_ms=200, kill_wait_ms=200)
        self.start()
        self.ok(self.scale("t", 2, target=self.targets(2, "term", pool="t")))
        self.ok(self.scale("k", 2, target=self.targets(2, "kill", pool="k")))
        self.ok(self.scale("n", 1, target=self.targets(1, pool="n")))
        for pool, n in (("t", 2), ("k", 2), ("n", 1)):
            wait_for(lambda: all(self.starts(pool, i) for i in range(n)))
        began = time.monotonic()
        aos_home.post_request(self.home, aos_client.new_name("stop"), {"jsonrpc": "2.0", "method": "stop"})
        self.assertEqual(self.proc.wait(timeout=6), 0)
        took = time.monotonic() - began
        self.assertGreaterEqual(took, 0.39)                         # kill 模式要走到最後一階
        terms = [float(Path(str(self.ready("t", i)) + ".term").read_text()) for i in range(2)]
        self.assertLess(abs(terms[0] - terms[1]), 0.05)             # 同一批一起 TERM
        self.assertGreaterEqual(min(terms) - began, 0.19)
        self.assertFalse(Path(str(self.ready("n", 0)) + ".term").exists())   # 聽 stop 的不用 TERM
        self.assertEqual(self.kid("n", 0)["last_exit"], 0)
        self.assertEqual(self.kid("k", 0)["last_exit"], 137)

    def test_epipe_skips_stop_wait(self):
        self.set_info(stop_wait_ms=3000, kill_wait_ms=60)
        self.start()
        self.ok(self.scale(count=1, target=self.targets(1, "epipe")))
        wait_for(lambda: self.starts("p", 0))
        began = time.monotonic()
        aos_home.post_request(self.home, aos_client.new_name("stop"), {"jsonrpc": "2.0", "method": "stop"})
        self.assertEqual(self.proc.wait(timeout=6), 0)
        self.assertLess(time.monotonic() - began, 1.5)

    def test_signal_stops_daemon(self):
        self.start()
        self.ok(self.scale(count=1, target=self.targets(1)))
        wait_for(lambda: self.starts("p", 0))
        self.proc.send_signal(signal.SIGINT)
        self.assertEqual(self.proc.wait(timeout=4), 0)
        self.assertTrue((self.home / "pools/p/pool.json").exists())

    def test_v1_home_children_are_killed_and_dropped(self):
        write_json(self.home / "info.json", {"_metainfo": {"_type": "daemon", "_version": 1},
                                             "poll_ms": 5, "stop_wait_ms": 50, "kill_wait_ms": 50})
        ready = self.root / "old.ready"
        old = subprocess.Popen([PY, str(self.child), "kill", str(ready)], stdin=subprocess.PIPE,
                               stdout=subprocess.DEVNULL, start_new_session=True)
        old.stdin.write(b'{"method": "go"}\n')
        old.stdin.flush()
        wait_for(ready.exists)
        threading.Thread(target=old.wait, daemon=True).start()     # 替它收屍，kill(pid,0) 才看得到消失
        write_json(self.home / "state.json", {"pid": 0, "stopping": False, "current": None,
                                              "children": {"k": {"pid": old.pid, "state": "running"}}})
        self.start()
        self.assertIsNotNone(old.returncode if old.poll() is not None else wait_for(lambda: old.poll() is not None))
        self.assertEqual(old.returncode, -signal.SIGKILL)
        self.assertNotIn("children", read_json(self.home / "state.json"))
        old.stdin.close()
        self.halt()

    def test_lock_refuses_second_daemon_and_shared_probe(self):
        self.assertFalse(aos_daemon.is_alive(self.home))
        self.start()
        self.assertTrue(aos_daemon.is_alive(self.home))
        second = subprocess.run([PY, str(CLI / "aos-daemon"), "boot", "--target", str(self.home)],
                                stdin=subprocess.DEVNULL, capture_output=True, timeout=4)
        self.assertEqual(second.returncode, 1)
        self.assertIn(b"AlreadyRunning", second.stderr)
        self.halt()
        self.assertFalse(aos_daemon.is_alive(self.home))


class HomeTest(DaemonCase):
    def boot_fails(self, needle):
        bad = subprocess.run([PY, str(CLI / "aos-daemon"), "boot", "--target", str(self.home)],
                             stdin=subprocess.DEVNULL, capture_output=True, timeout=4)
        self.assertEqual(bad.returncode, 1)
        self.assertIn(needle, bad.stderr.decode())

    def test_info_defaults_versions_and_validation(self):
        os.unlink(self.home / "info.json")
        self.start()
        info = read_json(self.home / "info.json")
        self.assertEqual(info["_metainfo"], {"_type": "daemon", "_version": 2})
        self.assertEqual((info["spawn_per_sec"], info["max_children"], info["restart_max_ms"]), (50, 20000, 60000))
        self.halt()
        loaded = aos_daemon.load_info(self.home)
        self.assertEqual(loaded["stable_ms"], 10000)
        write_json(self.home / "info.json", {"_metainfo": {"_type": "daemon", "_version": 1},
                                             "restart_delay_ms": 90000})
        self.assertEqual(aos_daemon.load_info(self.home)["restart_max_ms"], 90000)
        for bad in ({"spawn_per_sec": 0}, {"max_children": True}, {"poll_ms": 0}, {"stable_ms": -1},
                    {"restart_delay_ms": 10, "restart_max_ms": 5}):
            with self.subTest(bad=bad):
                write_json(self.home / "info.json", dict({"_metainfo": {"_type": "daemon", "_version": 2}}, **bad))
                self.boot_fails("FieldTypeMismatch")
        write_json(self.home / "info.json", {"_metainfo": {"_type": "daemon", "_version": 3}})
        self.boot_fails("NotAHome")

    def test_broken_pool_json_refuses_to_start(self):
        (self.home / "pools/p").mkdir(parents=True)
        write_json(self.home / "pools/p/pool.json", {"pool": "other", "owner": "/k", "count": 1})
        self.boot_fails("ReadFailed")

    def test_requests_ack_and_reconciliation(self):
        aos_home.ensure_queue(self.home)
        original = "interrupted.json"
        aos_home.post_request(self.home, original, {"jsonrpc": "2.0", "id": "saved", "method": "scale"})
        write_json(self.home / "state.json", {"pid": 0, "current": {
            "name": original, "id": "saved", "notify": False}})
        self.start()
        response = aos_client.wait_response(self.home, original, timeout_ms=3000, poll_ms=5)
        self.assertEqual(response["error"]["data"]["code"], "Interrupted")
        ack = aos_client.ack(self.home, original)
        wait_for(lambda: not (self.home / "requests" / ack).exists())
        self.assertFalse((self.home / "responses" / original).exists())
        self.assertEqual(self.call("unknown")["error"]["code"], -32601)
        name = aos_client.new_name("notification")
        aos_home.post_request(self.home, name, {"jsonrpc": "2.0", "method": "unknown"})
        wait_for(lambda: not (self.home / "requests" / name).exists())
        self.assertFalse((self.home / "responses" / name).exists())
        self.assertEqual(self.ok(self.call("ls")), {"pools": {}})
        self.halt()

    def test_ls_rpc(self):
        self.start()
        self.ok(self.scale(count=2, target=self.targets(2), home=str(self.root / "h/{name}")))
        self.running("p", 2)
        (self.root / "h/1").mkdir(parents=True)
        write_json(self.root / "h/1/state.json", {"current": {"name": "x"}})
        everything = self.ok(self.call("ls", {}))
        self.assertEqual(everything["pools"]["p"]["running"], 2)
        one = self.ok(self.call("ls", {"pool": "p"}))
        self.assertEqual((one["children"]["0"]["busy"], one["children"]["1"]["busy"]), (False, True))
        self.assertEqual(self.code(self.call("ls", {"pool": "zz"})), "NotFound")
        self.halt()

    def test_home_resolution_precedence(self):
        with mock.patch.dict(os.environ, {"AOS_DAEMON_HOME": str(self.home), "HOME": str(self.root)}):
            self.assertEqual(aos_daemon.daemon_home(), str(self.home))
            self.assertEqual(aos_daemon.daemon_home(str(self.root / "explicit")), str(self.root / "explicit"))
        cwd = os.getcwd()
        try:
            os.chdir(self.root)
            with mock.patch.dict(os.environ, {"HOME": str(self.root)}, clear=True):
                self.assertEqual(aos_daemon.daemon_home(), str(Path(self.root).resolve()))
        finally:
            os.chdir(cwd)


class UnitTest(unittest.TestCase):
    def test_members_and_backoff(self):
        self.assertEqual(aos_daemon_pools.members(3, [1]), [0, 2, 3])
        self.assertEqual(aos_daemon_pools.members(0, [5]), [])
        owner = aos_daemon.Daemon("/nonexistent", dict(aos_daemon.INFO_DEFAULTS), budget=10)
        self.assertEqual([owner.backoff_ms(s) for s in (1, 2, 3, 7, 8)], [1000, 2000, 4000, 60000, 60000])

    def test_remove_pool_deletes_summary_first(self):
        import tempfile
        with tempfile.TemporaryDirectory(prefix="aos-daemon-test-") as tmp:
            pool = Path(tmp) / "pools" / "p"
            (pool / "kids").mkdir(parents=True)
            for leaf in ("summary.json", "pool.json"):
                (pool / leaf).write_text("{}")
            order = []
            real = os.unlink
            def unlink(path, *a, **k):
                order.append(Path(path).name)
                return real(path, *a, **k)
            with mock.patch("aos_daemon_pools.os.unlink", unlink):
                aos_daemon_pools.remove_pool(tmp, "p")
            self.assertEqual(order[:2], ["summary.json", "pool.json"])
            self.assertFalse(pool.exists())

    def test_fd_budget_takes_open_file_limit(self):
        info = dict(aos_daemon.INFO_DEFAULTS, max_children=10 ** 9)
        with mock.patch("aos_daemon.resource.getrlimit", return_value=(1000, 1000)):
            self.assertEqual(aos_daemon.fd_budget(info), 936)
        info["max_children"] = 5
        with mock.patch("aos_daemon.resource.getrlimit", return_value=(1000, 1000)):
            self.assertEqual(aos_daemon.fd_budget(info), 5)


if __name__ == "__main__":
    unittest.main()
