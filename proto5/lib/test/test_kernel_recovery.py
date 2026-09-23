"""kernel.md §2、§3、§6 的崩潰窗口：直接準備持久帳本／檔案，再跑一格補齊。"""
import copy
from pathlib import Path
from unittest.mock import patch

import aos_home as home
import aos_kernel as kernel
from test_kernel import CLI, KernelCase


class Crash(Exception):
    pass


class RecoveryTests(KernelCase):
    def step(self):
        with patch.object(self.engine, "ensure_cpus"):
            self.engine.step()

    def load_engine(self, seq=7):
        self.state = home.read_state(self.k)
        self.engine = kernel.Kernel(self.k, self.info, self.state, seq)

    def test_recorded_but_not_placed_is_replayed_without_redispatch(self):
        proc, cpu, req = self.assign()
        self.engine.save()
        self.step()
        placed = home.read_json(cpu / "requests" / req)
        self.assertEqual(placed["method"], "aos-exec")
        self.assertEqual(placed["params"]["target"], proc["target"])
        self.assertEqual(self.state["cpus"]["0"]["req"], req)
        self.assertEqual(sum(c["proc"] == "p" for c in self.state["cpus"].values()), 1)
        self.load_engine(seq=8)
        self.step()
        self.assertEqual([p.name for p in (cpu / "requests").glob("k-*.json")], [req])
        self.assertEqual(self.state["procs"]["p"]["runs"], 0)

    def test_dispatch_records_before_put_then_next_tick_recovers(self):
        self.proc()
        original = home.post_request
        def crash_on_work(destination, name, obj):
            if Path(destination) == self.k / "cpus" / "0":
                raise Crash()
            return original(destination, name, obj)
        with patch.object(home, "post_request", side_effect=crash_on_work):
            with self.assertRaises(Crash):
                self.engine.dispatch()
        recorded = home.read_state(self.k)
        req = recorded["cpus"]["0"]["req"]
        self.assertIsNotNone(req)
        self.assertEqual(recorded["procs"]["p"]["status"], "running")
        self.assertNotIn("p", recorded["queue"])
        self.assertFalse((self.k / "cpus" / "0" / "requests" / req).exists())
        self.load_engine(seq=8)
        self.step()
        self.assertTrue((self.k / "cpus" / "0" / "requests" / req).exists())
        self.assertEqual(sum(c["proc"] == "p" for c in self.state["cpus"].values()), 1)

    def test_next_tick_placed_before_last_seq_record_is_idempotent(self):
        name = "k-test-chain-8.json"
        request = {"jsonrpc": "2.0", "id": "next-id", "method": "aos-exec",
                   "params": {"target": str(CLI), "args": ["tick", str(self.k), "--chain",
                              "test-chain", "--seq", "8"], "timeout_ms": 0}}
        cpu = self.k / "cpus" / "k"
        home.post_request(cpu, name, request)
        inode = (cpu / "requests" / name).stat().st_ino
        self.state["last_seq"] = 6
        self.engine.save()
        self.step()
        self.assertEqual(self.state["last_seq"], 7)
        self.assertEqual((cpu / "requests" / name).stat().st_ino, inode)
        self.assertEqual(home.read_json(cpu / "requests" / name), request)

    def test_tick_request_uses_plain_cli_args_and_no_timeout(self):
        self.step()
        request = home.read_json(self.k / "cpus" / "k" / "requests" / "k-test-chain-8.json")
        self.assertEqual(request["params"], {"target": str(CLI), "args": ["tick", str(self.k),
                          "--chain", "test-chain", "--seq", "8"], "timeout_ms": 0})

    def populate_outboxes(self):
        cpu = self.k / "cpus" / "0"
        self.state["acks"] = [{"home": str(cpu), "name": "finished-work.json"}]
        self.state["replies"] = [{"name": "client.json", "id": "client-id",
                                 "body": {"result": {"name": "p"}}}]
        self.state["stops"] = ["0"]
        self.state["deletes"] = ["old-syscall.json"]
        home.post_request(self.k, "old-syscall.json", {"jsonrpc": "2.0", "method": "add", "id": 1})
        self.engine.save()
        return cpu

    def assert_delivered(self, cpu):
        values = [home.read_json(path) for path in (cpu / "requests").glob("*.json")]
        self.assertTrue(any(v.get("method") == "ack" and
                            v.get("params", {}).get("name") == "finished-work.json" for v in values))
        self.assertTrue(any(v.get("method") == "stop" for v in values))
        self.assertEqual(home.read_json(self.k / "responses" / "client.json"),
                         {"jsonrpc": "2.0", "id": "client-id", "result": {"name": "p"}})
        self.assertFalse((self.k / "requests" / "old-syscall.json").exists())
        self.assertTrue(all(not self.state[key] for key in ("acks", "replies", "stops", "deletes")))

    def test_all_four_outboxes_replay_from_recorded_state(self):
        cpu = self.populate_outboxes()
        self.engine.flush_outboxes()
        self.assert_delivered(cpu)

    def test_delivered_outboxes_still_recorded_replay_idempotently(self):
        cpu = self.populate_outboxes()
        pending = copy.deepcopy(self.state)
        self.engine.flush_outboxes()
        home.write_state(self.k, pending)
        self.load_engine()
        self.engine.flush_outboxes()
        self.assert_delivered(cpu)
        self.assertEqual(len(list((cpu / "requests").glob("ack-*.json"))), 1)
        self.assertEqual(len(list((cpu / "requests").glob("stop-*.json"))), 1)

    def test_crash_after_delivery_before_outbox_clear_is_safe(self):
        cpu = self.populate_outboxes()
        with patch.object(self.engine, "save", side_effect=Crash):
            with self.assertRaises(Crash):
                self.engine.flush_outboxes()
        self.load_engine()
        self.engine.flush_outboxes()
        self.assert_delivered(cpu)

    def test_multiple_acks_to_same_home_in_one_tick_are_not_lost(self):
        cpu = self.k / "cpus" / "0"
        names = ["old-work.json", "new-work.json"]
        self.state["acks"] = [{"home": str(cpu), "name": name} for name in names]
        self.engine.save()
        self.engine.flush_outboxes()
        requests = [home.read_json(path) for path in (cpu / "requests").glob("ack-*.json")]
        self.assertEqual({r["params"]["name"] for r in requests}, set(names))

    def test_response_recorded_before_ack_is_not_counted_twice(self):
        proc, cpu, req = self.assign()
        home.write_json(cpu / "responses" / req, self.result())
        self.engine.collect()
        self.assertEqual(self.state["procs"]["p"]["runs"], 1)
        self.load_engine(seq=8)
        self.engine.collect()
        self.assertEqual(self.state["procs"]["p"]["runs"], 1)
        self.assertEqual(self.state["acks"], [{"home": str(cpu), "name": req}])

    def test_deletes_survives_removed_proc_and_tick_does_not_recreate(self):
        env = self.syscall("add", {"target": "/future.json", "name": "gone"})
        self.engine.apply_syscall(env)
        self.state["procs"].clear()
        self.state["queue"].clear()
        self.engine.save()
        self.load_engine(seq=8)
        self.step()
        self.assertNotIn("gone", self.state["procs"])
        self.assertFalse((self.k / "requests" / env.name).exists())

    def test_old_chain_tick_changes_nothing(self):
        self.proc()
        self.engine.save()
        before = {str(p.relative_to(self.k)): p.read_bytes() for p in self.k.rglob("*") if p.is_file()}
        self.assertEqual(kernel.tick(self.k, "obsolete-chain", 100), 0)
        after = {str(p.relative_to(self.k)): p.read_bytes() for p in self.k.rglob("*") if p.is_file()}
        self.assertEqual(after, before)

    def test_stopped_tick_only_flushes_outboxes(self):
        cpu = self.populate_outboxes()
        self.state["phase"] = "stopped"
        home.post_request(self.k, "later.json", {"jsonrpc": "2.0", "method": "add", "id": 2,
                                                 "params": {"target": "/future.json", "name": "later"}})
        self.engine.save()
        with patch.object(kernel.Kernel, "ensure_cpus", side_effect=AssertionError("不能啟動cpu")):
            self.assertEqual(kernel.tick(self.k, "test-chain", 9), 0)
        self.load_engine()
        self.assert_delivered(cpu)
        self.assertTrue((self.k / "requests" / "later.json").exists())
        self.assertEqual(list((self.k / "cpus" / "k" / "requests").glob("k-*.json")), [])
        self.assertNotIn("later", self.state["procs"])

    def test_first_boot_initializes_missing_ledger_and_copies_envs(self):
        fresh = self.root / "fresh-kernel"
        kernel.init(fresh)
        raw = home.read_json(fresh / "info.json")
        envs = {"$opt": "clear", "$val": {"PATH": {"$env": "UNSET_UNTIL_DAEMON_SPAWN"}}}
        raw["cpus"]["llm"] = {"pool": "llm", "envs": envs}
        home.write_json(fresh / "info.json", raw)
        home.write_json(self.d / "info.json", {"_metainfo": {"_type": "daemon", "_version": 1}})
        with patch.object(kernel.aos_daemon, "is_alive", return_value=True), \
             patch.object(kernel.aos_daemon, "read_state", return_value={"children": {}}), \
             patch.object(kernel.Kernel, "_daemon_call", return_value={"result": {"pid": 1}}) as spawn:
            self.assertEqual(kernel.boot(fresh, daemon=self.d), 0)
        state = home.read_state(fresh)
        self.assertEqual(state["phase"], "running")
        self.assertEqual(set(state["cpus"]), {"0", "1", "2", "llm"})
        self.assertFalse(state["procs"])
        self.assertFalse(state["queue"])
        self.assertEqual(spawn.call_count, 5)
        inst = home.read_json(fresh / "cpus" / "llm" / "inst.json")
        self.assertEqual(inst["envs"], envs)
        next_path = fresh / "cpus" / "k" / "requests" / ("k-%s-1.json" % state["chain"])
        self.assertTrue(next_path.exists())

    def test_boot_preserves_inflight_and_outboxes_but_discards_old_stops(self):
        self.assign(once=True, pending={"name": "waiting-once.json", "id": 1})
        self.state["phase"] = "stopped"
        self.state["stops"] = ["0", "k"]
        self.state["acks"] = [{"home": str(self.d), "name": "previous-spawn.json"}]
        self.state["replies"] = [{"name": "reply.json", "id": 7, "body": {"result": {"name": "x"}}}]
        self.state["deletes"] = ["handled.json"]
        self.engine.save()
        before = copy.deepcopy(self.state)
        old_inst = self.k / "cpus" / "0" / "inst.json"
        home.write_json(old_inst, {"argv": ["my-custom-cpu"], "envs": {"CUSTOM": "keep"}})
        old_bytes = old_inst.read_bytes()
        home.write_json(self.d / "info.json", {"_metainfo": {"_type": "daemon", "_version": 1}})
        with patch.object(kernel.aos_daemon, "is_alive", return_value=True), \
             patch.object(kernel.aos_daemon, "read_state", return_value={"children": {}}), \
             patch.object(kernel.Kernel, "_daemon_call", return_value={"result": {"pid": 1}}):
            self.assertEqual(kernel.boot(self.k, daemon=self.d), 0)
        after = home.read_state(self.k)
        self.assertNotEqual(after["chain"], before["chain"])
        self.assertEqual(after["phase"], "running")
        self.assertEqual(after["stops"], [])
        for key in ("cpus", "queue", "procs", "acks", "replies", "deletes"):
            self.assertEqual(after[key], before[key])
        self.assertEqual(old_inst.read_bytes(), old_bytes)
