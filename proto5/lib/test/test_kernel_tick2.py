"""proto5-2 kernel 一格十步：池的長大／縮小、scale 回音、通知三路、排隊懶刪、提交點、搬池、停機縮池。

全部用假 daemon（_kernel_fake），直接呼叫 tick 一格一格跑；cpu 的回音由測試自己寫。
"""
from pathlib import Path
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import aos_home
import aos_kernel_pools
from _kernel_fake import FakeCase


def free(st, pool="default"):
    return sorted(st["pools"][pool]["free"])


class Grow(FakeCase):
    def test_grow_free_only_after_echo(self):
        self.init({"default": {"count": 2}})
        self.boot()
        st = self.settle()
        self.assertEqual(free(st), [0, 1])
        self.edit_info(default={"count": 4})
        st = self.tick(process=False)
        entry = st["pools"]["default"]
        self.assertEqual(entry["pending"]["count"], 4)
        self.assertEqual(free(st), [0, 1])  # 還沒回音：新號不進 free
        for i in (2, 3):
            self.assertTrue((self.K / "pools/default/cpus" / str(i) / "info.json").exists())
        st = self.tick(process=False)  # 單在 D/requests：等
        self.assertIsNotNone(st["pools"]["default"]["pending"])
        self.fake.process()
        st = self.tick()
        self.assertEqual(free(st), [0, 1, 2, 3])
        self.assertEqual(st["pools"]["default"]["sent"], {"count": 4, "skip": []})
        self.assertIsNone(st["pools"]["default"]["pending"])

    def test_first_declaration_and_redeclare_after_boot(self):
        self.init({"default": {"count": 2}})
        self.boot()
        self.settle()
        n = len(self.fake.seen)
        self.boot()
        self.settle()
        names = [name for name, _ in self.fake.seen[n:] if "scale-default" in name]
        self.assertEqual(len(names), 1)  # boot 後就算集合一樣也整份重送一次
        self.assertEqual(self.fake.pool("default")["decl"][1], 1)

    def test_scale_params(self):
        self.init({"default": {"count": 3, "skip": [1], "dpool": "k1-default"}})
        self.boot()
        self.settle()
        name, params = [x for x in self.fake.seen if "scale-default" in x[0]][-1]
        self.assertEqual(params["pool"], "k1-default")
        self.assertEqual(params["owner"], str(self.K))
        self.assertEqual((params["count"], params["skip"]), (3, [1]))
        self.assertEqual(params["target"], str(self.K / "pools/default/cpus") + "/{name}/inst.json")
        self.assertEqual(params["home"], str(self.K / "pools/default/cpus") + "/{name}")
        chain = self.state()["chain"]
        self.assertEqual(params["decl"], [int(chain.split("-")[0]), 1])
        self.assertEqual(name, "k-%s-1-scale-default.json" % chain)
        self.assertEqual(free(self.state()), [0, 2, 3])


class Shrink(FakeCase):
    def setUp(self):
        super().setUp()
        self.init({"default": {"count": 3}})
        self.boot()
        self.settle()

    def busy_on(self, *names):
        for name in names:
            self.add(name)
        st = self.tick()
        return {v["proc"]: k for k, v in st["busy"].items()}

    def test_drain_then_shrink_recompute_once(self):
        where = self.busy_on("a", "b", "c")
        self.assertEqual(sorted(where.values()), ["default/0", "default/1", "default/2"])
        calls = []
        real = aos_kernel_pools.PoolsMixin.recompute
        def spy(self_, pool, entry):
            calls.append(pool)
            return real(self_, pool, entry)
        with mock.patch.object(aos_kernel_pools.PoolsMixin, "recompute", spy):
            self.edit_info(default={"count": 1})
            st = self.tick()
            entry = st["pools"]["default"]
            self.assertEqual(entry["draining"], 2)
            self.assertIsNone(entry["pending"])  # T＝W ∪ busy 的 S＝{0,1,2}＝S：不送單
            self.assertEqual(calls, ["default"])
            self.respond("default/2")
            st = self.tick()
            self.assertEqual(st["pools"]["default"]["draining"], 1)
            self.assertEqual(calls, ["default"])  # 做完一顆不重算
            self.assertNotIn("default/2", st["busy"])
            self.assertEqual(free(st), [])  # 2 號不回 free
            self.respond("default/1")
            st = self.tick()
            self.assertEqual(calls, ["default", "default"])  # 最後一顆做完才重算一次
            self.assertEqual(st["pools"]["default"]["pending"]["count"], 1)
            st = self.tick()
        self.assertEqual(st["pools"]["default"]["sent"], {"count": 1, "skip": []})
        self.assertEqual(self.fake.pool("default")["count"], 1)
        # a、b、c 都照常回 queue；只有 0 號可派
        for key in list(st["busy"]):
            self.assertEqual(key, "default/0")

    def test_r4_shrink_in_flight_then_restored(self):
        self.edit_info(default={"count": 2})
        st = self.tick(process=False)
        self.assertEqual(st["pools"]["default"]["pending"]["count"], 2)
        self.edit_info(default={"count": 3})
        st = self.tick(process=False)
        self.assertEqual(free(st), [0, 1])  # 2 號在 Q 之外：等下一張單確認
        self.fake.process()
        st = self.tick(process=False)
        self.assertEqual(st["pools"]["default"]["sent"]["count"], 2)
        self.assertEqual(st["pools"]["default"]["pending"]["count"], 3)
        self.assertEqual(free(st), [0, 1])
        self.fake.process()
        st = self.tick()
        self.assertEqual(free(st), [0, 1, 2])

    def test_busy_shrunk_number_not_in_w_stays_out(self):
        where = self.busy_on("a")
        self.assertEqual(where["a"], "default/0")
        self.edit_info(default={"count": 3, "skip": [0]})  # 0 號退休、補 3 號
        st = self.tick()
        self.assertEqual(st["pools"]["default"]["draining"], 1)
        self.assertEqual(st["pools"]["default"]["pending"]["count"], 4)  # T＝{1,2,3}∪{0}
        st = self.tick()
        self.assertEqual(free(st), [1, 2, 3])
        # 被派到的只有 1、2、3
        self.respond("default/0")
        st = self.tick()
        st = self.tick()
        self.assertEqual(st["pools"]["default"]["sent"], {"count": 3, "skip": [0]})
        self.assertNotIn("default/0", st["busy"])


class Errors(FakeCase):
    def setUp(self):
        super().setUp()
        self.init({"default": {"count": 1}})
        self.boot()
        self.settle()

    def grow_with(self, *codes):
        self.fake.errors["default"] = list(codes)
        self.edit_info(default={"count": 2})
        return self.tick()

    def scale_names(self):
        return [n for n, _ in self.fake.seen if "scale-default" in n]

    def test_name_taken_no_auto_retry(self):
        self.grow_with("NameTaken")
        st = self.tick()
        entry = st["pools"]["default"]
        self.assertEqual(entry["error"]["code"], "NameTaken")
        self.assertIsNone(entry["pending"])
        n = len(self.fake.seen)
        self.ticks(5)
        self.assertEqual(len(self.fake.seen), n)  # 不自動重試
        self.assertEqual(free(self.state()), [0])
        self.edit_info(default={"count": 3})  # info 再變才再試
        st = self.ticks(2)
        self.assertIsNone(st["pools"]["default"]["error"])
        self.assertEqual(free(st), [0, 1, 2])

    def test_stopping_retries_every_10_ticks(self):
        self.grow_with("Stopping")
        st = self.tick()
        self.assertEqual(st["pools"]["default"]["error"]["code"], "Stopping")
        at = st["pools"]["default"]["retry_at"]
        self.assertEqual(at, self.seq + 10)
        n = len(self.scale_names())
        while self.seq < at - 1:
            self.tick()
        self.assertEqual(len(self.scale_names()), n)
        st = self.ticks(2)
        self.assertEqual(len(self.scale_names()), n + 1)
        self.assertIsNone(st["pools"]["default"]["error"])
        self.assertEqual(free(st), [0, 1])

    def test_stale_and_interrupted_redeclare(self):
        for code in ("Stale", "Interrupted"):
            with self.subTest(code=code):
                self.fake.errors["default"] = [code]
                count = self.state()["pools"]["default"]["want"]["count"] + 1
                self.edit_info(default={"count": count})
                n = len(self.scale_names())
                st = self.tick()
                st = self.tick()  # 收到錯 → redeclare → 同一格重送
                self.assertIsNone(st["pools"]["default"]["error"])
                self.assertEqual(len(self.scale_names()), n + 2)
                st = self.tick()
                self.assertEqual(st["pools"]["default"]["sent"]["count"], count)

    def test_both_files_missing_is_interrupted(self):
        self.edit_info(default={"count": 2})
        st = self.tick(process=False)
        name = st["pools"]["default"]["pending"]["name"]
        self.fake.swallow.add(name)
        self.fake.process()
        st = self.tick()
        self.assertIn({"event": "scale_echo", "pool": "default", "request": name, "result": "Interrupted"},
                      self.log_events())
        st = self.tick()
        self.assertEqual(free(st), [0, 1])

    def test_echo_acked(self):
        self.edit_info(default={"count": 2})
        st = self.ticks(3)
        self.assertEqual(list((Path(self.D) / "responses").glob("*scale-default*")), [])


class Notify(FakeCase):
    def setUp(self):
        super().setUp()
        self.init({"default": {"count": 3}}, sweep=1)
        self.boot()
        self.settle()

    def test_resp_notification(self):
        self.add("a")
        st = self.tick()
        key = st["on"]["a"]
        self.tick()  # recent 查過一次（在途）
        self.respond(key)
        st = self.tick()
        self.assertEqual(st["procs"]["a"]["runs"], 1)
        self.assertEqual(list((self.K / "requests").glob("resp-*")), [])

    def test_recent_catches_without_notification(self):
        self.add("a")
        st = self.tick()
        key = st["on"]["a"]
        self.respond(key, notify=False)
        st = self.tick()
        self.assertEqual(st["procs"]["a"]["runs"], 1)

    def test_sweep_rotates(self):
        for name in "abc":
            self.add(name)
        st = self.tick()
        self.assertEqual(len(st["busy"]), 3)
        self.tick()
        st = self.state()
        order = list(st["busy"])
        for key in order:
            self.respond(key, notify=False)
        seen = []
        for _ in range(3):
            st = self.tick()
            seen.append(sum(p["runs"] for p in st["procs"].values()))
        self.assertEqual(seen, [1, 2, 3])  # sweep=1：一格收一顆，輪著查

    def test_bad_and_old_notifications(self):
        self.add("a")
        st = self.tick()
        key = st["on"]["a"]
        home = self.cpu(key)
        self.notify(home, "x.json", raw="{not json")
        aos_home.write_json(self.K / "requests" / "resp-2.json", {"jsonrpc": "2.0", "id": 1, "method": "responded",
                                                                   "params": {"home": str(home), "name": "x"}})
        aos_home.write_json(self.K / "requests" / "resp-3.json", {"jsonrpc": "2.0", "method": "nope", "params": {}})
        aos_home.write_json(self.K / "requests" / "resp-4.json", {"jsonrpc": "2.0", "method": "responded",
                                                                   "params": {"home": "/elsewhere/cpus/1", "name": "x"}})
        aos_home.write_json(self.K / "requests" / "resp-5.json", {"jsonrpc": "2.0", "method": "responded",
                                                                   "params": {"home": str(self.cpu("default/2")), "name": "x"}})
        old = self.notify(home, "k-old.json")  # busy 有那格、name 對不上＝舊通知
        (self.K / "requests" / "resp-6.json.tmp").write_text("{")
        st = self.tick()
        self.assertEqual(sorted(p.name for p in (self.K / "requests").glob("resp-*")), ["resp-6.json.tmp"])
        bad = [e for e in self.log_events() if e["event"] == "bad_notify"]
        self.assertEqual(len(bad), 5)
        self.assertNotIn(old, [e["file"] for e in bad])
        self.assertIn(key, st["busy"])  # 舊通知不收

    def test_rm_running_discard_and_cancel(self):
        self.add("a")
        self.add("b")
        st = self.tick()
        self.rm("a")
        st = self.tick()
        self.assertTrue(st["busy"][st["on"]["a"]]["discard"])
        self.respond(st["on"]["a"])
        st = self.tick()
        self.assertNotIn("a", st["procs"])
        self.assertNotIn("a", st["on"])
        # b：記了派工、原單與回音都不在（像是沒放出去）→ rm 直接取消
        key = st["on"]["b"]
        (self.cpu(key) / "requests" / st["busy"][key]["req"]).unlink()
        self.rm("b")
        st = self.tick(process=False)
        self.assertNotIn("b", st["procs"])
        self.assertNotIn(key, st["busy"])
        self.assertIn(int(key.split("/")[1]), st["pools"]["default"]["free"])


class Queue(FakeCase):
    def setUp(self):
        super().setUp()
        self.init({"default": {"count": 0}})
        self.boot()
        self.settle()

    def test_lazy_delete_and_same_name_readd(self):
        first = self.add("x")
        self.tick()
        self.rm("x")
        self.tick()
        second = self.add("x")
        st = self.tick()
        self.assertEqual(st["procs"]["x"]["request"], second)
        self.edit_info(default={"count": 1})
        st = self.ticks(3)
        self.assertEqual(st["procs"]["x"]["status"], "running")
        self.assertEqual(st["busy"]["default/0"]["proc"], "x")
        self.assertEqual(st["ready"]["default"], [])
        dispatched = [e for e in self.log_events() if e["event"] == "dispatch"]
        self.assertEqual(len(dispatched), 1)
        self.assertNotEqual(first, second)

    def test_compaction(self):
        for i in range(10):
            self.add("p%d" % i)
        st = self.tick()
        self.assertEqual(len(st["ready"]["default"]), 10)
        for i in range(6):
            self.rm("p%d" % i)
        st = self.tick()
        self.assertLessEqual(len(st["ready"]["default"]), 6)
        self.assertEqual({n for n, _ in st["ready"]["default"]} >= {"p6", "p7", "p8", "p9"}, True)

    def test_delayed_heap(self):
        self.edit_info(default={"count": 1})
        self.settle()
        self.add("slow", interval_ms=300)
        st = self.tick()
        self.respond("default/0")
        st = self.tick()
        self.assertEqual(st["procs"]["slow"]["status"], "queued")
        self.assertEqual(len(st["delayed"]), 1)
        self.assertEqual(st["delayed"][0][1:], ["slow", st["procs"]["slow"]["request"]])
        st = self.tick()
        self.assertEqual(st["busy"], {})
        time.sleep(.35)
        st = self.tick()
        self.assertEqual(st["busy"]["default/0"]["proc"], "slow")
        self.assertEqual(st["delayed"], [])

    def test_pool_count_zero_keeps_queueing(self):
        self.add("q")
        st = self.ticks(3)
        self.assertEqual(st["procs"]["q"]["status"], "queued")


class Commits(FakeCase):
    def test_at_most_three_writes(self):
        """one-boot：一格最多三筆交易（提交點 A 出貨完、B 決定完、C 出貨完）；沒事做的提交點不寫。"""
        import aos_kernel_store
        self.init({"default": {"count": 2}})
        self.boot()
        self.settle()
        writes = []
        real = aos_kernel_store.Store.save
        def spy(store, state):
            if store.home == self.K.absolute():
                writes.append({k: state[k] for k in ("last_seq", "acks", "sends", "busy")})
            return real(store, state)
        with mock.patch.object(aos_kernel_store.Store, "save", spy):
            self.tick()
            self.assertEqual(len(writes), 1)  # 閒格：只有提交點 B
            writes.clear()
            self.add("a")
            self.add("b")
            self.edit_info(default={"count": 3})
            st = self.tick(process=False)
            self.assertEqual(len(writes), 2)  # 上一格出貨完了：B、C
            self.assertEqual(writes[0]["last_seq"], st["last_seq"])
            self.assertTrue(writes[0]["sends"])  # 提交點 B 帶著新單
            self.assertEqual(writes[-1]["sends"], [])  # 提交點 C 出貨完拿掉
            writes.clear()
            for key in list(st["busy"]):
                self.respond(key)
            self.fake.process()
            self.tick()
            # 上一格第 10 步已出貨完，這格第 4 步沒事做就不寫：B（帶 acks）、C
            self.assertEqual(len(writes), 2)
            self.assertTrue(writes[0]["acks"])
            self.assertEqual(writes[1]["acks"], [])

    def test_commit_a_when_outbox_left(self):
        """上一格崩在 B 之後、C 之前（出貨箱還有東西）：這格第 4 步先出貨、存提交點 A（帶 last_seq）。"""
        import aos_kernel_store
        self.init({"default": {"count": 2}})
        self.boot()
        self.settle()
        st = self.state()
        st["acks"] = [{"home": str(self.cpu("default/0")), "name": "gone.json"}]
        self.put_state(st)
        writes = []
        real = aos_kernel_store.Store.save
        def spy(store, state):
            if store.home == self.K.absolute():
                writes.append({k: state[k] for k in ("last_seq", "acks")})
            return real(store, state)
        with mock.patch.object(aos_kernel_store.Store, "save", spy):
            st = self.tick()
        self.assertEqual(len(writes), 2)  # A、B
        self.assertEqual(writes[0]["acks"], [])
        self.assertEqual(writes[0]["last_seq"], st["last_seq"])


if __name__ == "__main__":
    unittest.main()
