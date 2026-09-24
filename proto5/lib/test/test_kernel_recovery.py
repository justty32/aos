"""kernel.md §2、§3、§6 的崩潰窗口：直接準備持久帳本／檔案，再跑一格補齊。"""
import copy
import json
import os
import signal

from pathlib import Path
from unittest.mock import patch

import aos_client
import aos_home as home
import aos_kernel as kernel
from test_kernel import CLI, KernelCase
from _kernel_util import KernelCase as LiveKernelCase, wait_for


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
                   "params": {"target": str(CLI), "args": ["tick", "--target", str(self.k), "--chain",
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
        self.assertEqual(request["params"], {"target": str(CLI), "args": ["tick", "--target", str(self.k),
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

    def test_empty_ticks_do_not_log_but_dispatch_does(self):
        for seq in range(7, 11):
            self.load_engine(seq)
            self.step()
        log = self.k / 'kernel.log'
        self.assertFalse(log.exists())
        self.proc()
        self.step()
        rows = [json.loads(line) for line in log.read_text().splitlines()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['events'][0]['event'], 'dispatch')

    def test_reloaded_tick_ms_controls_sleep(self):
        self.raw['tick_ms'] = 120
        home.write_json(self.k / 'info.json', self.raw)
        with patch.object(kernel.time, 'sleep') as sleep, patch.object(kernel.Kernel, 'ensure_cpus'):
            kernel.tick(self.k, self.state['chain'], 7)
        sleep.assert_called_once_with(.12)

    def test_init_recovers_partial_home_without_overwriting(self):
        fresh = self.root / 'partial'
        fresh.mkdir()
        (fresh / 'requests').mkdir()
        sentinel = fresh / 'requests' / 'keep.txt'
        sentinel.write_text('keep')
        kernel.init(fresh)
        self.assertEqual(kernel.load_info(fresh)['cpus']['k']['pool'], 'kernel')
        for name in ('requests', 'responses', 'cpus'):
            self.assertTrue((fresh / name).is_dir())
        self.assertEqual(sentinel.read_text(), 'keep')
        with self.assertRaises(kernel.KernelError) as caught:
            kernel.init(fresh)
        self.assertEqual(caught.exception.code, 'AlreadyExists')



class LiveRecoveryTests(LiveKernelCase):
    def recover_creation(self, failed_file):
        self.initialize(cpus={'k': {'pool': 'kernel'}, '0': {}})
        self.start_daemon()
        original = home.write_json
        cpu = self.home / 'cpus' / '0'
        def fail(path, obj):
            if Path(path) == cpu / failed_file:
                raise Crash()
            return original(path, obj)
        with patch.object(home, 'write_json', side_effect=fail):
            with self.assertRaises(Crash):
                kernel.boot(self.home, self.daemon)
        self.assertTrue(cpu.is_dir())
        self.assertEqual((cpu / 'info.json').exists(), failed_file == 'inst.json')
        self.assertFalse((cpu / 'inst.json').exists())
        before = (cpu / 'info.json').read_bytes() if failed_file == 'inst.json' else None
        self.boot()
        if before is not None:
            self.assertEqual((cpu / 'info.json').read_bytes(), before)
        for name in ('requests', 'responses'):
            self.assertTrue((cpu / name).is_dir())
        self.assertTrue((cpu / 'inst.json').is_file())
        self.assertTrue(self.dstate()['children']['0']['alive'])
        response = self.call('add', {'target': self.job(), 'once': True})
        self.assertEqual(response['result']['code'], 0)
        self.kernel_stop()

    def test_boot_recovers_crash_after_cpu_mkdir(self):
        self.recover_creation('info.json')

    def test_boot_recovers_crash_after_cpu_info(self):
        self.recover_creation('inst.json')

    def test_boot_preserves_complete_cpu_custom_inst_and_info(self):
        self.initialize()
        info = kernel.load_info(self.home)
        engine = kernel.Kernel(self.home, info, kernel.new_state(info, 'prepare', 'k', kernel.CLI), 0)
        engine._create_cpu('0', {})
        cpu = self.home / 'cpus' / '0'
        inst = home.read_json(cpu / 'inst.json')
        inst['envs'] = {'CUSTOM': 'human-edit'}
        self.write(cpu / 'inst.json', inst)
        settings = home.read_json(cpu / 'info.json')
        settings['poll_ms'] = 7
        self.write(cpu / 'info.json', settings)
        before = {name: (cpu / name).read_bytes() for name in ('info.json', 'inst.json')}
        self.start_daemon()
        self.boot()
        self.boot()
        self.assertEqual({name: (cpu / name).read_bytes() for name in before}, before)
        self.kernel_stop()

    def test_known_boundary_b10_shipped_stop_survives_boot_and_stalls_chain(self):
        """已知邊界 B-10：boot 清 stops 帳本，已出貨的舊 stop 仍使新 kcpu 退出。"""
        self.initialize(cpus={'k': {'pool': 'kernel'}, '0': {}})
        self.start_daemon()
        info = kernel.load_info(self.home)
        state = kernel.new_state(info, 'old-chain', 'k', kernel.CLI)
        engine = kernel.Kernel(self.home, info, state, 0)
        engine._create_cpu('k', {})
        cpu = self.home / 'cpus' / 'k'
        spawned = aos_client.call(self.daemon, 'spawn',
                                  {'name': 'k', 'target': str(cpu / 'inst.json'), 'restart': True},
                                  timeout_ms=5000, poll_ms=5)
        pid = spawned['result']['pid']
        os.kill(pid, signal.SIGSTOP)
        wait_for(lambda: '\nState:\tT' in Path('/proc/%d/status' % pid).read_text())
        state['stops'] = ['k']
        engine.save()
        engine.flush_outboxes()
        stop = cpu / 'requests' / 'stop-old-chain.json'
        self.assertTrue(stop.exists())
        aos_client.call(self.daemon, 'kill', {'name': 'k'}, timeout_ms=5000, poll_ms=5)
        wait_for(lambda: 'k' not in self.dstate()['children'])
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)
        self.assertTrue(stop.exists())
        state['stops'] = ['k']  # 另有尚未出貨的帳本待辦；boot 只清掉這一層。
        engine.save()
        self.good_cli('boot', self.home, '--daemon-target', self.daemon)
        wait_for(lambda: 'k' not in self.dstate()['children'])
        self.assertFalse(stop.exists())
        current = self.state()
        self.assertEqual(current['stops'], [])
        self.assertEqual(current['last_seq'], 0)
        self.assertEqual(current['phase'], 'running')
        self.assertTrue((cpu / 'requests' / ('k-%s-1.json' % current['chain'])).exists())
