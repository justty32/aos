"""kernel 的崩潰窗口（kernel-ledger §3 四個提交點、kernel-tick、handoff §1）：直接準備持久帳本／檔案，再跑一格補齊。

proto5 版搬過來時改了什麼：
- 出貨箱 `stops` 拿掉，換成 `sends`（往 daemon 家放 scale 單，kernel-ledger §2）；「送出後、清帳前」改成在提交點 2 崩。
- boot 不再 spawn 每顆 cpu：重宣告工作池；用 _kernel_fake 的假 daemon 回 scale 音。
- 2026-09-24 one-boot：帳本是 K/ledger.sqlite（aos_kernel_store 讀寫）；提交點改 A（出貨完）、B（決定完）、C（出貨完）；
  沒有 kernel cpu 與「放下一格」，boot 改成向 daemon 登記開 tick。
- 刪掉 proto5 的「已知邊界 B-10：已出貨的舊 stop 活過 boot、讓新 kernel cpu 退出」：proto5-2 的 kernel 不再往 cpu 放
  stop-（handoff §3、proto5-diffs cpu/stop.md §5.4），這個邊界不存在了。
"""
import copy
import json
from pathlib import Path
from unittest.mock import patch

import aos_home as home
import aos_kernel as kernel
import aos_kernel_store
from _kernel_fake import FakeDaemon
from test_kernel import CLI, KernelCase
from _kernel_util import KernelCase as LiveKernelCase


class Crash(Exception):
    pass


class RecoveryTests(KernelCase):
    def step(self):
        self.engine.step()

    def load_engine(self, seq=7):
        self.close_store()
        self.state = aos_kernel_store.read(self.k)
        self.engine = kernel.Kernel(self.k, self.info, self.state, seq)

    def ledger(self, where=None):
        return aos_kernel_store.read(where or self.k)

    def test_recorded_but_not_placed_is_replayed_without_redispatch(self):
        proc, cpu, req = self.assign()
        self.engine.save()
        self.step()                                                     # 巡檢查到：兩個檔都不在＝再放一次
        placed = home.read_json(cpu / "requests" / req)
        self.assertEqual(placed["method"], "aos-exec")
        self.assertEqual(placed["params"]["target"], proc["target"])
        self.assertEqual(self.state["busy"]["default/0"]["req"], req)
        self.assertEqual(sum(slot["proc"] == "p" for slot in self.state["busy"].values()), 1)
        self.load_engine(seq=8)
        self.step()
        self.assertEqual([p.name for p in (cpu / "requests").glob("k-*.json")], [req])
        self.assertEqual(self.state["procs"]["p"]["runs"], 0)

    def test_dispatch_records_before_put_then_next_tick_recovers(self):
        self.proc()
        original = home.post_request
        def crash_on_work(destination, name, obj):
            if Path(destination) == self.cpu("default/0"):
                raise Crash()
            return original(destination, name, obj)
        with patch.object(home, "post_request", side_effect=crash_on_work):
            with self.assertRaises(Crash):
                self.step()
        recorded = self.ledger()                                        # 提交點 B 已寫
        req = recorded["busy"]["default/0"]["req"]
        self.assertEqual(recorded["procs"]["p"]["status"], "running")
        self.assertEqual(recorded["recent"], ["default/0"])
        self.assertEqual(recorded["ready"]["default"], [])
        self.assertFalse((self.cpu("default/0") / "requests" / req).exists())
        self.load_engine(seq=8)
        self.step()                                                     # recent 一定查：補放
        self.assertTrue((self.cpu("default/0") / "requests" / req).exists())
        self.assertEqual(sum(slot["proc"] == "p" for slot in self.state["busy"].values()), 1)

    SCALE = "k-1000-1-6-scale-default.json"

    def populate_outboxes(self):
        cpu = self.cpu("default/0")
        self.state["acks"] = [{"home": str(cpu), "name": "finished-work.json"}]
        self.state["replies"] = [{"name": "client.json", "id": "client-id",
                                 "body": {"result": {"name": "p"}}}]
        self.state["deletes"] = ["old-syscall.json"]
        self.state["sends"] = [{"home": str(self.d), "name": self.SCALE,
                                "body": {"jsonrpc": "2.0", "id": self.SCALE[:-5], "method": "scale",
                                         "params": {"pool": "default", "owner": str(self.k), "count": 2}}}]
        home.post_request(self.k, "old-syscall.json", {"jsonrpc": "2.0", "method": "add", "id": 1})
        self.engine.save()
        return cpu

    def assert_delivered(self, cpu):
        values = [home.read_json(path) for path in (cpu / "requests").glob("*.json")]
        self.assertTrue(any(v.get("method") == "ack" and
                            v.get("params", {}).get("name") == "finished-work.json" for v in values))
        self.assertEqual(home.read_json(self.d / "requests" / self.SCALE)["method"], "scale")
        self.assertEqual(home.read_json(self.k / "responses" / "client.json"),
                         {"jsonrpc": "2.0", "id": "client-id", "result": {"name": "p"}})
        self.assertFalse((self.k / "requests" / "old-syscall.json").exists())
        self.assertTrue(all(not self.state[key] for key in ("acks", "replies", "sends", "deletes")))

    def test_all_four_outboxes_replay_from_recorded_state(self):
        cpu = self.populate_outboxes()
        self.engine.flush_outboxes()
        self.assert_delivered(cpu)

    def test_delivered_outboxes_still_recorded_replay_idempotently(self):
        cpu = self.populate_outboxes()
        pending = copy.deepcopy(self.state)
        self.engine.flush_outboxes()
        aos_kernel_store.write(self.k, pending)
        self.load_engine()
        self.engine.flush_outboxes()
        self.assert_delivered(cpu)
        self.assertEqual(len(list((cpu / "requests").glob("ack-*.json"))), 1)
        self.assertEqual(len(list((self.d / "requests").glob("k-*.json"))), 1)

    def test_scale_already_answered_is_not_posted_again(self):
        """D-25：崩在「放完、清帳前」而 daemon 已處理完、回了音：重放時看到回音就不再放同名單。"""
        self.populate_outboxes()
        home.write_json(self.d / "responses" / self.SCALE, {"jsonrpc": "2.0", "id": self.SCALE[:-5],
                                                            "result": {"pool": "default", "count": 2, "ver": 1}})
        self.engine.flush_outboxes()
        self.assertFalse((self.d / "requests" / self.SCALE).exists())
        self.assertEqual(self.state["sends"], [])

    def test_crash_after_delivery_before_outbox_clear_is_safe(self):
        """第 4 步出貨完、提交點 A 寫帳本前崩：下一格照帳本重放，對方收到的效果一樣。"""
        cpu = self.populate_outboxes()
        real, calls = self.engine.save, []
        def save():
            calls.append(1)
            if len(calls) == 1:
                raise Crash()
            return real()
        with patch.object(self.engine, "save", side_effect=save):
            with self.assertRaises(Crash):
                self.step()
        self.assertEqual(self.ledger()["deletes"], ["old-syscall.json"])   # 帳上還在
        self.load_engine(seq=8)
        self.step()
        self.assert_delivered(cpu)
        self.assertEqual(len(list((self.d / "requests").glob("k-*.json"))), 1)

    def test_multiple_acks_to_same_home_in_one_tick_are_not_lost(self):
        cpu = self.cpu("default/0")
        names = ["old-work.json", "new-work.json"]
        self.state["acks"] = [{"home": str(cpu), "name": name} for name in names]
        self.engine.save()
        self.engine.flush_outboxes()
        requests = [home.read_json(path) for path in (cpu / "requests").glob("ack-*.json")]
        self.assertEqual({r["params"]["name"] for r in requests}, set(names))

    def test_response_recorded_before_ack_is_not_counted_twice(self):
        proc, cpu, req = self.assign()
        home.write_json(cpu / "responses" / req, self.result())
        self.engine.collect(["default/0"])
        self.engine.save()                                              # 提交點 3；ack 還沒出貨就崩
        self.assertEqual(self.state["procs"]["p"]["runs"], 1)
        self.load_engine(seq=8)
        self.engine.collect(["default/0"])
        self.assertEqual(self.state["procs"]["p"]["runs"], 1)
        self.assertEqual(self.state["acks"], [{"home": str(cpu), "name": req}])

    def test_deletes_survives_removed_proc_and_tick_does_not_recreate(self):
        env = self.syscall("add", {"target": "/future.json", "name": "gone"})
        self.engine.apply_syscall(env)
        self.state["procs"].clear()
        self.state["ready"].clear()
        self.engine.save()
        self.load_engine(seq=8)
        self.step()
        self.assertNotIn("gone", self.state["procs"])
        self.assertFalse((self.k / "requests" / env.name).exists())

    def test_old_chain_tick_changes_nothing(self):
        """舊 kernel cpu 裡還排著的舊格（帶 --chain／--seq）：退 0、什麼都不碰（連 .tick.lock 都不建）。"""
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
        self.state["last_seq"] = 8
        self.engine.save()
        with patch.object(kernel.Kernel, "pools_step", side_effect=AssertionError("停機後不能動池")):
            self.assertEqual(kernel.tick(self.k), 0)
        self.load_engine()
        self.assert_delivered(cpu)
        self.assertTrue((self.k / "requests" / "later.json").exists())
        self.assertNotIn("later", self.state["procs"])
        self.assertEqual(self.state["last_seq"], 8)                       # stopped 的格不算數、不記序號
        self.assertEqual(sorted(p.name for p in (self.d / "requests").glob("*.json")), [self.SCALE])  # 沒再寄撤登記

    def test_first_boot_initializes_missing_ledger_and_writes_raw_envs(self):
        fake = FakeDaemon(self.root / "FD")
        self.addCleanup(fake.close)
        fresh = self.root / "fresh-kernel"
        envs = {"$opt": "clear", "$val": {"PATH": {"$env": "UNSET_UNTIL_DAEMON_SPAWN"}}}
        kernel.init(fresh, {"daemon": str(fake.home), "pools": {"default": {"count": 3}, "llm": {"count": 1, "envs": envs}}})
        fake.start()
        try:
            self.assertEqual(kernel.boot(fresh, 5000), 0)
        finally:
            fake.stop()
        state = self.ledger(fresh)
        self.assertEqual(state["phase"], "running")
        self.assertEqual((state["last_seq"], state["ticker"]), (0, str(fake.home)))
        self.assertEqual(set(state["pools"]), {"default", "llm"})               # one-boot：沒有 kernel 池
        self.assertTrue(all(state["pools"][p]["redeclare"] for p in ("default", "llm")))
        self.assertFalse(state["procs"])
        self.assertEqual(state["ready"], {})
        self.assertEqual(home.read_json(fresh / "pools" / "llm" / "envs.json"), envs)   # 原樣、不解
        for i in range(3):
            self.assertTrue((fresh / "pools" / "default" / "cpus" / str(i) / "inst.json").is_file())
        self.assertIsNone(fake.pool("kernel"))
        self.assertIsNone(fake.pool("default"))                             # 工作池第一格才宣告
        self.assertFalse((fresh / "pools" / "kernel").exists())
        # 向 daemon 登記開 tick（不再放第 1 格進 kernel cpu）
        import aos_daemon_ticks
        reg = aos_daemon_ticks.peek(fake.home, fresh)
        self.assertEqual(reg, {"home": str(fresh), "cli": str(kernel.CLI.resolve()), "every_ms": 1000, "timeout_ms": 60000})
        answered = [p.name for p in (fake.home / "responses").glob("*.json")]
        self.assertEqual(len(answered), 1)                                  # 登記的回音已 ack（假 daemon 還沒處理）
        acks = [home.read_json(p)["params"]["name"] for p in (fake.home / "requests").glob("ack-*.json")]
        self.assertEqual(acks, answered)

    def test_boot_preserves_inflight_and_outboxes_but_discards_scale_sends(self):
        fake = FakeDaemon(self.d)
        self.addCleanup(fake.close)
        self.assign(once=True, pending={"name": "waiting-once.json", "id": 1})
        self.proc("waiting")
        self.state["phase"] = "stopped"
        self.state["acks"] = [{"home": str(self.d), "name": "previous-scale.json"}]
        self.state["replies"] = [{"name": "reply.json", "id": 7, "body": {"result": {"name": "x"}}}]
        self.state["deletes"] = ["handled.json"]
        self.state["sends"] = [{"home": str(self.d), "name": "k-1000-1-5-scale-default.json",
                                "body": {"jsonrpc": "2.0", "id": "x", "method": "scale", "params": {}}},
                               {"home": str(self.d), "name": "k-1000-1-5-untick.json",
                                "body": {"jsonrpc": "2.0", "method": "tick", "params": {"home": str(self.k), "off": True}}}]
        self.engine.save()
        before = self.ledger()
        old_inst = self.cpu("default/0") / "inst.json"
        home.write_json(old_inst, {"argv": ["my-custom-cpu"], "envs": {"CUSTOM": "keep"}})
        old_bytes = old_inst.read_bytes()
        fake.start()
        try:
            self.assertEqual(kernel.boot(self.k, 5000), 0)
        finally:
            fake.stop()
        after = self.ledger()
        self.assertNotEqual(after["chain"], before["chain"])
        self.assertEqual(after["phase"], "running")
        self.assertEqual(after["sends"], [])                                # 舊 chain 的 scale、撤登記單丟掉
        for key in ("busy", "on", "ready", "delayed", "procs", "replies", "deletes"):
            self.assertEqual(after[key], before[key], key)
        self.assertEqual(after["acks"][:1], before["acks"])
        self.assertEqual(after["recent"], ["default/0"])                   # boot 後第一格把忙的都查一次
        self.assertTrue(after["pools"]["default"]["redeclare"])
        self.assertEqual(old_inst.read_bytes(), old_bytes)

    def test_empty_ticks_do_not_log_but_dispatch_does(self):
        for seq in range(7, 11):
            self.load_engine(seq)
            self.step()
        log = self.k / "kernel.log"
        self.assertFalse(log.exists())
        self.proc()
        self.step()
        rows = [json.loads(line) for line in log.read_text().splitlines()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["events"][0]["event"], "dispatch")
        self.assertEqual(rows[0]["events"][0]["cpu"], "default/0")

    def test_init_recovers_partial_home_without_overwriting(self):
        fresh = self.root / "partial"
        fresh.mkdir()
        (fresh / "requests").mkdir()
        sentinel = fresh / "requests" / "keep.txt"
        sentinel.write_text("keep")
        kernel.init(fresh)
        self.assertEqual(kernel.load_info(fresh)["pools"], {})                   # one-boot：init 不再補 kernel 池
        for name in ("requests", "responses", "pools"):
            self.assertTrue((fresh / name).is_dir())
        self.assertEqual(sentinel.read_text(), "keep")
        with self.assertRaises(kernel.KernelError) as caught:
            kernel.init(fresh)
        self.assertEqual(caught.exception.code, "AlreadyExists")


class LiveRecoveryTests(LiveKernelCase):
    def recover_creation(self, failed_file):
        """boot 第 4 步建 cpu 家建到一半崩：再 boot 缺的補齊、已在的不動，cpu 照樣拉得起來。"""
        self.initialize({"default": {"count": 1}})
        self.start_daemon()
        original = home.write_json
        cpu = self.cpu_home("default", 0)
        def fail(path, obj):
            if Path(path) == cpu / failed_file:
                raise Crash()
            return original(path, obj)
        with patch.object(home, "write_json", side_effect=fail):
            with self.assertRaises(Crash):
                kernel.boot(self.home, 8000)
        self.assertTrue(cpu.is_dir())
        self.assertEqual((cpu / "info.json").exists(), failed_file == "inst.json")
        self.assertFalse((cpu / "inst.json").exists())
        before = (cpu / "info.json").read_bytes() if failed_file == "inst.json" else None
        self.boot()
        if before is not None:
            self.assertEqual((cpu / "info.json").read_bytes(), before)
        for name in ("requests", "responses"):
            self.assertTrue((cpu / name).is_dir())
        self.assertTrue((cpu / "inst.json").is_file())
        response = self.call("add", {"target": self.job(), "once": True})
        self.assertEqual(response["result"]["code"], 0, response)
        self.assertEqual(self.kid("default", 0)["state"], "running")
        self.kernel_stop()

    def test_boot_recovers_crash_after_cpu_mkdir(self):
        self.recover_creation("info.json")

    def test_boot_recovers_crash_after_cpu_info(self):
        self.recover_creation("inst.json")

    def test_boot_preserves_complete_cpu_custom_inst_and_info(self):
        self.initialize({"default": {"count": 1}})
        info = kernel.load_info(self.home)
        engine = kernel.Kernel(self.home, info, kernel.new_state("prepare", kernel.CLI), 0)
        engine.ensure_cpu_home("default", 0)   # 只建 cpu 家，不存帳本
        cpu = self.cpu_home("default", 0)
        inst = home.read_json(cpu / "inst.json")
        inst["envs"] = {"CUSTOM": "human-edit"}
        self.write(cpu / "inst.json", inst)
        settings = home.read_json(cpu / "info.json")
        settings["poll_ms"] = 7
        self.write(cpu / "info.json", settings)
        before = {name: (cpu / name).read_bytes() for name in ("info.json", "inst.json")}
        self.start_daemon()
        self.boot()
        self.boot()
        self.assertEqual({name: (cpu / name).read_bytes() for name in before}, before)
        response = self.call("add", {"target": self.job(), "once": True})
        self.assertEqual(response["result"]["code"], 0, response)
        self.kernel_stop()
