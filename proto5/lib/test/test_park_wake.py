"""09-24 閒置停車＋喚醒（kernel/echo.md 102 那列、syscall.md「叫醒一個行程」、aos-agent tick.md §12）。

kernel 這半用假 daemon（_kernel_fake）一格一格跑；agent 這半跟 test_agent_tick 一樣用假 K 家、直接呼叫函式。
「崩」＝在某一步丟出 Crash（BaseException），記憶體全丟、磁碟停在那一刻；真 SIGKILL 的在 test_park_crash。
"""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import aos_agent as agent
import aos_agent_say
import aos_agent_wake
import aos_home
import aos_kernel_boot
import aos_kernel_cli
import aos_kernel_engine
import aos_kernel_info
import aos_kernel_ledger
import aos_kernel_ls
import aos_kernel_store
from _kernel_fake import Crash, FakeCase

PARK = 102


class KernelPark(FakeCase):
    def setUp(self):
        super().setUp()
        self.init({"default": {"count": 2}, "slow": {"count": 0}})
        self.boot()
        self.settle()

    # ---- 小工具 ----
    def park(self, name="agent", **params):
        """登記一個反覆行程、派一次、讓它退 102 → 停著。"""
        self.add(name, **params)
        st = self.tick()
        self.respond(st["on"][name], code=PARK)
        st = self.tick()
        proc = st["procs"][name]
        self.assertEqual((proc["status"], proc.get("parked")), ("queued", True))
        self.assertNotIn(name, st["on"])
        return st

    def post_wake(self, name, rid=None):
        self.n += 1
        req = "cli-%d-%d.json" % (self.n, os.getpid())
        body = {"jsonrpc": "2.0", "method": "wake", "params": {"name": name}}
        if rid is not None:
            body["id"] = rid
        aos_home.post_request(self.K, req, body)
        return req

    def kernel(self, st=None):
        return aos_kernel_engine.Kernel(self.K, aos_kernel_info.load_info(self.K), st or self.state(), 999)

    def events(self, kind):
        return [e for e in self.log_events() if e["event"] == kind]

    # ---- 102 那列 ----
    def test_102_parks_for_park_ms(self):
        before = time.time()
        st = self.park()
        proc = st["procs"]["agent"]
        self.assertEqual((proc["runs"], proc["fails"], proc["park_ms"]), (1, 0, 300000))
        self.assertGreaterEqual(proc["not_before"], before + 299)
        st = self.ticks(3)
        self.assertNotIn("agent", st["on"])  # 停著：不派
        self.assertEqual(st["procs"]["agent"]["runs"], 1)

    def test_park_ms_from_add_and_info(self):
        st = self.park(park_ms=1500)
        proc = st["procs"]["agent"]
        self.assertEqual(proc["park_ms"], 1500)
        self.assertLess(proc["not_before"] - time.time(), 2)
        info = self.info()
        info["park_ms"] = 7000
        aos_home.write_json(self.K / "info.json", info)
        st = self.park("b")
        self.assertEqual(st["procs"]["b"]["park_ms"], 7000)
        info["park_ms"] = -1
        aos_home.write_json(self.K / "info.json", info)
        with self.assertRaises(aos_kernel_info.KernelError):
            aos_kernel_info.load_info(self.K)

    def test_park_ms_zero_is_like_101(self):
        self.add("agent", park_ms=0)
        st = self.tick()
        self.respond(st["on"]["agent"], code=PARK)
        st = self.tick()
        self.assertIn("agent", st["on"])  # 當格判完就到期、當格再派
        self.assertNotIn("parked", st["procs"]["agent"])  # 派出去就不算停著

    def test_done_exit_102_means_done(self):
        info = self.info()
        info["done_exit"] = PARK
        aos_home.write_json(self.K / "info.json", info)
        self.add("agent")
        st = self.tick()
        self.respond(st["on"]["agent"], code=PARK)
        st = self.tick()
        self.assertEqual(st["procs"]["agent"]["status"], "done")
        self.assertNotIn("parked", st["procs"]["agent"])

    def test_102_is_not_a_failure(self):
        self.add("agent", park_ms=0)
        for _ in range(4):  # bad_after 是 3（FakeCase）
            st = self.tick()
            self.respond(st["on"]["agent"], code=PARK)
        st = self.tick()
        self.assertEqual((st["procs"]["agent"]["fails"], st["procs"]["agent"]["status"] != "bad"), (0, True))

    # ---- 出貨叫醒 ----
    def test_once_reply_wakes_parked(self):
        self.park()
        q = self.add("q", once=True, wake="agent")
        st = self.tick()
        self.assertEqual(st["procs"]["q"]["pending"]["wake"], "agent")
        self.respond(st["on"]["q"])
        st = self.tick()  # 收 q → 第 10 步出貨放回音、叫醒 → 09-24 tick-gap 提交點 D：同一格就再派
        self.assertTrue((self.K / "responses" / q).exists())
        proc = st["procs"]["agent"]
        self.assertNotIn("parked", proc)
        self.assertLessEqual(proc["not_before"], time.time())
        self.assertEqual(proc["status"], "running")
        self.assertIn("agent", st["on"])                  # 有空的 cpu：不用等下一格
        self.assertEqual(st["ready"]["default"], [])       # 叫醒推進 ready、同格就派走了
        self.assertEqual(st["stale"].get("default"), 1)  # delayed 裡那格變舊格
        self.assertEqual(self.events("wake")[-1], {"event": "wake", "proc": "agent", "how": "ready"})
        self.assertEqual(self.events("dispatch")[-1]["proc"], "agent")  # 叫醒之後的派工
        st = self.tick()
        self.assertIn("agent", st["on"])
        self.assertEqual(st["replies"], [])

    def test_wake_while_running_then_102_uses_interval(self):
        self.add("agent", interval_ms=0)
        st = self.tick()
        agent_cpu = st["on"]["agent"]
        self.add("q", once=True, wake="agent")
        st = self.tick()
        self.respond(st["on"]["q"])
        st = self.tick()
        self.assertTrue(st["procs"]["agent"]["woken"])
        self.assertEqual(self.events("wake")[-1]["how"], "woken")
        self.respond(agent_cpu, code=PARK)
        st = self.tick()
        proc = st["procs"]["agent"]
        self.assertNotIn("woken", proc)
        self.assertNotIn("parked", proc)  # 跑的時候回音已出貨：當 101，下一格再看
        st = self.tick()
        self.assertIn("agent", st["on"])

    def test_woken_cleared_after_any_verdict(self):
        self.add("agent", interval_ms=0)
        st = self.tick()
        key = st["on"]["agent"]
        k = self.kernel()
        k.wake("agent")
        k.save()
        self.respond(key, code=0)
        st = self.tick()
        self.assertNotIn("woken", st["procs"]["agent"])
        st = self.tick()
        self.respond(st["on"]["agent"], code=PARK)
        st = self.tick()
        self.assertTrue(st["procs"]["agent"]["parked"])  # 上一格的 woken 不會漏到這一格

    def test_new_generation_is_woken_by_old_batch(self):
        """astra 必修 1：舊批沒回來就 stop／start，新一代接手舊批、停著；舊批回來要叫醒新一代（不比代數）。"""
        self.park()
        q = self.add("q", once=True, wake="agent", pool="slow")  # slow 池 0 顆：一直排隊
        self.tick()
        self.rm("agent")
        self.tick()
        self.park()  # 同名重登記＝新的一代，接手舊批後停著
        self.rm("q")  # 舊批的回音（這裡是 Removed）出貨
        st = self.tick()
        self.assertTrue((self.K / "responses" / q).exists())
        self.assertNotIn("parked", st["procs"]["agent"])
        self.assertEqual(self.events("wake")[-1]["proc"], "agent")

    def test_wake_skips_missing_once_bad_done_discard(self):
        self.park()
        k = self.kernel()
        self.assertIsNone(k.wake("nobody"))
        for status in ("bad", "done"):
            k.state["procs"]["agent"]["status"] = status
            self.assertIsNone(k.wake("agent"))
        k.state["procs"]["agent"]["status"] = "queued"
        k.state["procs"]["agent"]["once"] = True
        self.assertIsNone(k.wake("agent"))
        # discard：被 rm、那格還在跑
        self.add("r", interval_ms=0)
        st = self.tick()
        self.rm("r")
        st = self.tick()
        self.assertTrue(st["busy"][st["on"]["r"]]["discard"])
        k = self.kernel()
        self.assertIsNone(k.wake("r"))
        self.assertNotIn("woken", k.state["procs"]["r"])

    def test_wake_due_does_not_double_queue(self):
        self.add("agent", pool="slow")  # count 0 的池：排在 ready 裡、not_before 已到
        st = self.tick()
        self.assertEqual(len(st["ready"]["slow"]), 1)
        k = self.kernel()
        self.assertIsNone(k.wake("agent"))
        self.assertEqual(len(k.state["ready"]["slow"]), 1)

    def test_removed_reply_wakes(self):
        self.park()
        q = self.add("q", once=True, wake="agent", pool="slow")
        self.tick()
        self.rm("q")
        st = self.tick()
        self.assertEqual(aos_home.read_json(self.K / "responses" / q)["error"]["data"]["code"], "Removed")
        self.assertNotIn("parked", st["procs"]["agent"])
        st = self.tick()
        self.assertIn("agent", st["on"])

    def test_stopping_reply_wakes(self):
        self.park()
        q = self.add("q", once=True, wake="agent", pool="slow")
        self.tick()
        self.stop_kernel()
        st = self.tick()
        self.assertEqual(aos_home.read_json(self.K / "responses" / q)["error"]["data"]["code"], "Stopping")
        self.assertNotIn("parked", st["procs"]["agent"])
        self.assertEqual(self.events("wake")[-1]["proc"], "agent")

    def test_rejected_add_reply_wakes(self):
        self.park()
        q = self.add("q", once=True, wake="agent", pool="nope")
        st = self.tick()
        self.assertEqual(aos_home.read_json(self.K / "responses" / q)["error"]["code"], -32602)
        self.assertNotIn("parked", st["procs"]["agent"])
        self.add("agent", wake="agent")  # AlreadyExists 也帶 wake；它已在 ready，不疊第二格
        st = self.tick()
        self.assertIn("agent", st["on"])
        self.assertEqual(sum(e[0] == "agent" for e in st["ready"]["default"]), 0)

    def test_wake_unknown_target_is_noop(self):
        """wake 指的行程收單時還沒登記也照記（之後才 start 的也叫得到）；出貨時不在就什麼都不做。"""
        q = self.add("q", once=True, wake="nobody")
        st = self.tick()
        self.assertEqual(st["procs"]["q"]["pending"]["wake"], "nobody")
        self.respond(st["on"]["q"])
        st = self.tick()
        self.assertTrue((self.K / "responses" / q).exists())
        self.assertEqual((st["replies"], self.events("wake")), ([], []))

    def test_bad_wake_param_rejected(self):
        q = self.add("q", once=True, wake="a/b")
        self.tick()
        self.assertEqual(aos_home.read_json(self.K / "responses" / q)["error"]["code"], -32602)

    def test_woken_cleared_for_every_verdict(self):
        """astra 建議 4：判定表每一列之後 woken 都清掉（stopped、error、kind=aos、done_exit、非零、0、101、102）。"""
        info = aos_kernel_info.load_info(self.K)
        proc = {"status": "running", "runs": 0, "fails": 0, "interval_ms": 0, "park_ms": 1000, "not_before": 0,
                "woken": True, "parked": True}
        cases = [{"result": {"stopped": True}}, {"error": {"code": -32000}}, {"result": {"kind": "aos", "code": 1}},
                 {"result": {"code": info["done_exit"]}}, {"result": {"code": 3}}, {"result": {"code": 0}},
                 {"result": {"code": 101}}, {"result": {"code": PARK}}]
        for response in cases:
            out = aos_kernel_info.classify(proc, response, info)
            self.assertNotIn("woken", out, response)
            self.assertNotIn("parked", out, response)  # woken 的 102 也不算停著

    def test_same_tick_park_and_reply(self):
        """同一格收到 agent 的 102 和它等的回音：判定在第 6 步、出貨叫醒在第 10 步，agent 不會停住。"""
        self.add("agent", interval_ms=0)
        st = self.tick()
        agent_cpu = st["on"]["agent"]
        self.add("q", once=True, wake="agent")
        st = self.tick()
        q_cpu = st["on"]["q"]
        self.respond(q_cpu)
        self.respond(agent_cpu, code=PARK)
        st = self.tick()
        self.assertNotIn("parked", st["procs"]["agent"])
        st = self.tick()
        self.assertIn("agent", st["on"])

    def test_act_batch_pieces_each_wake(self):
        """act 批兩件分開回來：第一件叫醒、agent 看了還差一件又停；第二件再叫醒。"""
        self.park()
        self.add("t1", once=True, wake="agent")
        self.add("t2", once=True, wake="agent", pool="slow")
        st = self.tick()
        self.respond(st["on"]["t1"])
        st = self.tick()
        self.assertNotIn("parked", st["procs"]["agent"])
        st = self.tick()
        self.respond(st["on"]["agent"], code=PARK)  # 還差 t2
        st = self.tick()
        self.assertTrue(st["procs"]["agent"]["parked"])
        self.rm("t2")  # 第二件回來（這裡用 Removed 當它的最後一則回音）
        st = self.tick()
        self.assertNotIn("parked", st["procs"]["agent"])

    # ---- wake syscall ----
    def test_wake_syscall_dispatches_same_tick(self):
        self.park()
        req = self.post_wake("agent")
        st = self.tick()
        self.assertIn("agent", st["on"])  # 第 5 步叫醒、第 8 步就派
        self.assertFalse((self.K / "requests" / req).exists())
        self.assertFalse((self.K / "responses" / req).exists())  # notification 不回音

    def test_wake_syscall_with_id(self):
        self.park()
        req = self.post_wake("nobody", rid="w1")
        ok = self.post_wake("agent", rid="w2")
        bad = self.post_wake("", rid="w3")
        self.tick()
        self.assertEqual(self.reply(req)["error"]["data"]["code"], "NotFound")
        self.assertEqual(self.reply(ok)["result"], {"name": "agent"})
        self.assertEqual(self.reply(bad)["error"]["code"], -32602)

    def test_wake_cli(self):
        self.park()
        out, done = io.StringIO(), []
        def run():
            with contextlib.redirect_stdout(out):
                done.append(aos_kernel_cli.main(["wake", "agent", "--target", str(self.K)]))
        thread = threading.Thread(target=run)
        thread.start()
        deadline = time.monotonic() + 8
        while thread.is_alive() and time.monotonic() < deadline:
            self.tick()
            time.sleep(.02)
        thread.join(2)
        self.assertEqual(done, [0])
        self.assertEqual(out.getvalue().strip(), "agent")
        self.assertIn("agent", self.state()["on"])

    def test_cli_add_park_ms(self):
        args = aos_kernel_cli._parser().parse_args(["add", "/x.json", "--park-ms", "5"])
        self.assertEqual(args.park_ms, 5)
        self.assertEqual(aos_kernel_cli.main(["add", "/x.json", "--park-ms", "-1", "--target", str(self.K)]), 2)

    # ---- 能力標記、ls ----
    def test_features_in_new_and_upgraded_ledger(self):
        self.assertEqual(self.state()["features"], ["park", "again"])  # 09-24 tick-gap：認得 103
        st = self.state()
        del st["features"]
        self.put_state(st)  # one-boot：帳本是 K/ledger.sqlite
        self.assertEqual(self.tick()["features"], ["park", "again"])

    def test_ls_shows_parked(self):
        self.park()
        self.add("busy", interval_ms=600000)
        self.tick()
        data = aos_kernel_ls.ls_data(self.K, aos_kernel_boot.status(self.K))
        procs = {p["name"]: p for p in data["procs"]}
        self.assertEqual((procs["agent"]["parked"], procs["busy"]["parked"]), (True, False))
        self.assertEqual(data["counts"]["procs"]["parked"], 1)
        self.assertIn("；停車 1", aos_kernel_ls.render(data))

    # ---- 崩潰窗口（Crash＝記憶體全丟、磁碟停在那一刻） ----
    def wake_crash(self, after_real):
        """把 Kernel.wake 換成「做完（或做之前）就崩」。"""
        real = aos_kernel_ledger.KernelLedger.wake
        def wake(self_, name):
            if after_real:
                real(self_, name)
            raise Crash()
        return mock.patch.object(aos_kernel_ledger.KernelLedger, "wake", wake)

    def reply_ready(self):
        """停著的 agent＋一張做完、回音待出貨（帶 wake）的 once q；回 q 的檔名。"""
        self.park()
        q = self.add("q", once=True, wake="agent")
        st = self.tick()
        self.respond(st["on"]["q"])
        return q

    def test_crash_after_reply_placed_before_ledger(self):
        """放好回音檔、叫醒只在記憶體 → 崩：下一格第 4 步重做（EEXIST 當已放）、再叫一次。"""
        q = self.reply_ready()
        with self.wake_crash(after_real=True), self.assertRaises(Crash):
            self.tick()
        st = self.state()
        body = aos_home.read_json(self.K / "responses" / q)
        self.assertEqual([r["name"] for r in st["replies"]], [q])  # 帳本還記著要出貨
        self.assertEqual(st["replies"][0]["wake"], "agent")
        self.assertTrue(st["procs"]["agent"]["parked"])  # 叫醒沒存到
        st = self.tick()
        self.assertEqual(st["replies"], [])
        self.assertIn("agent", st["on"])  # 第 4 步叫醒、第 8 步就派
        self.assertEqual(aos_home.read_json(self.K / "responses" / q), body)

    def test_crash_after_reply_placed_agent_running(self):
        """同一個窗口，但 agent 正在跑：woken 沒存到，下一格重做仍會記上。"""
        self.add("agent", interval_ms=0)
        st = self.tick()
        agent_cpu = st["on"]["agent"]
        self.add("q", once=True, wake="agent")
        st = self.tick()
        self.respond(st["on"]["q"])
        with self.wake_crash(after_real=True), self.assertRaises(Crash):
            self.tick()
        self.assertNotIn("woken", self.state()["procs"]["agent"])
        self.respond(agent_cpu, code=PARK, notify=False)  # agent 在 kernel 死掉時退了 102
        st = self.tick()  # 第 4 步：重放回音（EEXIST）、叫醒（running → woken）；第 6 步收 agent：當 101
        self.assertNotIn("parked", st["procs"]["agent"])
        self.assertNotIn("woken", st["procs"]["agent"])

    def test_crash_after_verdict_before_reply_placed(self):
        """回音待辦（帶 wake）已存（提交點 3）、第 10 步出貨前崩：下一格第 4 步放、叫。"""
        q = self.reply_ready()
        real = aos_kernel_engine.Kernel.flush_outboxes
        calls = []
        def flush(self_):
            calls.append(1)
            if len(calls) == 2:
                raise Crash()
            return real(self_)
        with mock.patch.object(aos_kernel_engine.Kernel, "flush_outboxes", flush), self.assertRaises(Crash):
            self.tick()
        st = self.state()
        self.assertEqual([(r["name"], r["wake"]) for r in st["replies"]], [(q, "agent")])
        self.assertFalse((self.K / "responses" / q).exists())
        st = self.tick()
        self.assertTrue((self.K / "responses" / q).exists())
        self.assertIn("agent", st["on"])

    def test_crash_before_verdict_committed(self):
        """收到 agent 的 102、判完但提交點 3 之前崩：下一格重收同一則，只算一次、照樣停。"""
        self.add("agent")
        st = self.tick()
        self.respond(st["on"]["agent"], code=PARK)
        with mock.patch.object(aos_kernel_engine.Kernel, "pools_step", side_effect=Crash()), self.assertRaises(Crash):
            self.tick()
        self.assertEqual(self.state()["procs"]["agent"]["status"], "running")
        st = self.tick()
        self.assertEqual((st["procs"]["agent"]["runs"], st["procs"]["agent"]["parked"]), (1, True))

    def test_crash_in_wake_syscall_before_commit(self):
        """wake 單判到一半崩（提交點 3 之前）：下一格重讀原單再叫一次。"""
        self.park()
        req = self.post_wake("agent")
        with self.wake_crash(after_real=True), self.assertRaises(Crash):
            self.tick()
        self.assertTrue((self.K / "requests" / req).exists())
        self.assertTrue(self.state()["procs"]["agent"]["parked"])
        st = self.tick()
        self.assertIn("agent", st["on"])

    def test_crash_after_wake_syscall_committed_before_delete(self):
        """wake 單已記（在 deletes）、原單還沒刪就崩：下一格只補刪、不重判；agent 只排一次。"""
        self.park()
        req = self.post_wake("agent")
        real = aos_kernel_engine.Kernel.flush_outboxes
        calls = []
        def flush(self_):
            calls.append(1)
            if len(calls) == 2:
                raise Crash()
            return real(self_)
        with mock.patch.object(aos_kernel_engine.Kernel, "flush_outboxes", flush), self.assertRaises(Crash):
            self.tick()
        st = self.state()
        self.assertIn(req, st["deletes"])
        self.assertIn("agent", st["on"])  # 提交點 3 已派出去
        st = self.tick()
        self.assertFalse((self.K / "requests" / req).exists())
        self.assertEqual(sum(e[0] == "agent" for q in st["ready"].values() for e in q), 0)
        self.assertEqual(len(self.events("wake")), 0)  # 崩掉那格沒寫 log；補刪那格沒重判

    def test_crash_after_commit2_woken_before_commit3(self):
        """第 4 步出貨叫醒（running → woken）已存進提交點 2、提交點 3 前崩：woken 留在帳本，下一格的 102 仍當 101。"""
        self.add("agent", interval_ms=0)
        st = self.tick()
        agent_cpu = st["on"]["agent"]
        self.add("q", once=True, wake="agent")
        st = self.tick()
        self.respond(st["on"]["q"])
        real = aos_kernel_engine.Kernel.flush_outboxes
        calls = []
        def flush(self_):
            calls.append(1)
            if len(calls) == 2:
                raise Crash()
            return real(self_)
        with mock.patch.object(aos_kernel_engine.Kernel, "flush_outboxes", flush), self.assertRaises(Crash):
            self.tick()  # 回音待辦記好、第 10 步前崩
        self.respond(agent_cpu, code=PARK)
        with mock.patch.object(aos_kernel_engine.Kernel, "pools_step", side_effect=Crash()), self.assertRaises(Crash):
            self.tick()  # 第 4 步出貨＋叫醒、提交點 2 存了；第 6 步判了 agent 但提交點 3 前崩
        st = self.state()
        self.assertEqual((st["replies"], st["procs"]["agent"]["status"], st["procs"]["agent"].get("woken")), ([], "running", True))
        st = self.tick()
        self.assertNotIn("parked", st["procs"]["agent"])
        self.assertNotIn("woken", st["procs"]["agent"])

    def test_park_ms_fallback(self):
        """沒人叫（say 崩在投好、叫之前，或外人直接丟檔）：最晚 park_ms 自己醒（plan-b §4）。真的 say 崩那條在 AgentPark。"""
        self.park(park_ms=1000)
        st = self.tick()
        self.assertNotIn("agent", st["on"])
        time.sleep(1.05)
        st = self.tick()
        self.assertIn("agent", st["on"])


class AgentPark(unittest.TestCase):
    """agent 這半：退出碼、送單帶 wake、start 驗相容、say／drop_new 投 wake。"""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.base, self.k = self.root / "bob", self.root / "K"
        self.base.mkdir()
        (self.k / "requests").mkdir(parents=True)
        (self.k / "responses").mkdir()
        self.env = {"AOS_KERNEL_HOME": str(self.k)}
        self.info = {"_metainfo": {"_type": "llm_agent", "_version": 1}, "llm": {"model": "small"}}
        self.put(self.base / "info.json", self.info)
        self.put(self.k / "info.json", {})
        aos_kernel_store.write(self.k, {"procs": {}, "replies": []})  # one-boot：K 帳本是 K/ledger.sqlite
        self.err = io.StringIO()
        self.addCleanup(mock.patch.stopall)
        mock.patch("sys.stderr", self.err).start()

    def put(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def tick(self):
        return agent.tick(self.base, self.env)

    def in_flight(self):
        name = "aw-bob-1-1-0"
        batch = {"kind": "think", "kernel": str(self.k), "base_len": 0, "sent": True,
                 "calls": [{"name": name, "done": None, "acked": False}]}
        self.put(self.base / "state.json", {"state": "think", "batch": batch, "errors": 0})
        return name

    def wakes(self):
        return [json.loads(p.read_text()) for p in sorted((self.k / "requests").glob("aa-bob-wake-*.json"))]

    def test_exit_codes(self):
        self.assertEqual(self.tick(), PARK)  # idle 沒輸入
        self.in_flight()
        self.assertEqual(self.tick(), PARK)  # 批在途、什麼都沒到
        st = json.loads((self.base / "state.json").read_text())
        st["waits"] = ["go.json"]
        self.put(self.base / "state.json", st)
        self.assertEqual(self.tick(), 101)  # 門關著：外人開的門 kernel 叫不到，照舊 101
        self.put(self.base / "go.json", {})
        self.assertEqual(self.tick(), PARK)

    def test_send_carries_wake(self):
        self.put(self.base / "state.json", {"state": "think"})
        self.assertEqual(self.tick(), 102)
        req = next((self.k / "requests").glob("aw-bob-*.json"))
        self.assertEqual(json.loads(req.read_text())["params"]["wake"], "agent-bob")

    def test_start_compatibility(self):
        self.put(self.k / "info.json", {"done_exit": PARK})
        with self.assertRaises(agent.AgentError) as ctx:
            agent._compatible(str(self.k), self.env)
        self.assertEqual(ctx.exception.code, "KernelIncompatible")
        self.put(self.k / "info.json", {})
        agent._compatible(str(self.k), self.env)  # 假帳本沒 chain＝還沒 boot 過，不擋
        aos_kernel_store.write(self.k, {"chain": "1-1", "procs": {}, "replies": []})
        with self.assertRaises(agent.AgentError) as ctx:
            agent._compatible(str(self.k), self.env)
        self.assertIn("102", ctx.exception.msg)
        aos_kernel_store.write(self.k, {"chain": "1-1", "features": ["park"], "procs": {}, "replies": []})
        with self.assertRaises(agent.AgentError) as ctx:  # 09-24 tick-gap：只有 park、不認得 103＝擋
            agent._compatible(str(self.k), self.env)
        self.assertEqual(ctx.exception.code, "KernelIncompatible")
        aos_kernel_store.write(self.k, {"chain": "1-1", "features": ["park", "again"], "procs": {}, "replies": []})
        agent._compatible(str(self.k), self.env)
        (self.k / "ledger.sqlite").unlink()  # 沒帳本＝沒 boot 過，不擋
        agent._compatible(str(self.k), self.env)

    def test_start_refuses_old_kernel_end_to_end(self):
        aos_kernel_store.write(self.k, {"chain": "1-1", "procs": {}, "replies": []})
        self.assertEqual(agent.start(self.base, self.env), 1)
        self.assertIn("KernelIncompatible", self.err.getvalue())
        self.assertEqual(list((self.k / "requests").iterdir()), [])  # 沒登記

    def test_say_posts_wake_after_input(self):
        self.put(self.base / "tick.json", {"envs": {"AOS_KERNEL_HOME": str(self.k)}})
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(aos_agent_say.say(self.base, "你好", env={}), 0)
        self.assertEqual(self.wakes(), [{"jsonrpc": "2.0", "method": "wake", "params": {"name": "agent-bob"}}])
        self.assertTrue((self.base / "input.json").exists())

    def test_say_wake_order_and_best_effort(self):
        order = []
        real_wake = aos_agent_wake.wake
        def spy(base, env=None):
            order.append((Path(base) / "input.json").exists())
            return real_wake(base, env)
        with mock.patch.object(aos_agent_say, "wake", spy), contextlib.redirect_stdout(io.StringIO()):
            aos_agent_say.say(self.base, "a", env=self.env)
        self.assertEqual(order, [True])  # 叫醒時輸入已在
        shutil_k = self.root / "K2"
        self.assertIsNone(aos_agent_wake.wake(self.base, {"AOS_KERNEL_HOME": str(shutil_k)}))  # K 不在：不算錯
        self.assertIsNone(aos_agent_wake.wake(self.base, {}))  # 找不到 K

    def test_say_crash_between_input_and_wake(self):
        """astra 建議 3：say 放好輸入、投 wake 前崩：輸入留著、沒有 wake 單；agent 下一次被派（park_ms 到）照收一次。"""
        self.put(self.base / "tick.json", {"envs": {"AOS_KERNEL_HOME": str(self.k)}})
        with mock.patch.object(aos_agent_say, "wake", side_effect=Crash()), self.assertRaises(Crash), \
                contextlib.redirect_stdout(io.StringIO()):
            aos_agent_say.say(self.base, "晚安", env=self.env)
        self.assertTrue((self.base / "input.json").exists())
        self.assertEqual(self.wakes(), [])
        self.assertEqual(self.tick(), 103)
        history = json.loads((self.base / "prompts/history.json").read_text())
        self.assertEqual(history[-1], {"role": "user", "content": "晚安"})
        self.assertFalse((self.base / "input.json").exists())

    def test_empty_intake_recovery_does_not_park(self):
        """astra 必修 2：恢復一個檔都不在的 intake＝寫了 state、退 0；新投的輸入下一格照收（不會被停車吃掉叫醒）。"""
        self.put(self.base / "state.json", {"intake": {"id": "x", "base_len": 0,
                 "files": [{"src": str(self.base / "gone"), "dst": str(self.base / "gone.x.done")}]}})
        self.put(self.base / "input.json", "新的一句")
        self.assertEqual(self.tick(), 0)
        self.assertEqual(self.tick(), 103)
        self.assertEqual(json.loads((self.base / "state.json").read_text())["state"], "think")

    def test_status_shows_parked(self):
        import aos_agent_status
        aos_kernel_store.write(self.k, {"chain": "1-1", "features": ["park"], "replies": [], "procs": {
            "agent-bob": {"status": "queued", "runs": 3, "fails": 0, "parked": True}}})
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            aos_agent_status.status(self.base, env=self.env)
        self.assertIn("queued（停車", out.getvalue())

    def test_drop_new_wakes_registered_agent_only(self):
        self.put(self.base / "tick.json", {"envs": {"AOS_KERNEL_HOME": str(self.k)}})
        self.assertTrue(aos_agent_say.drop_new(self.base / "input", "mail-1.json", "hi"))
        self.assertEqual(len(self.wakes()), 1)
        time.sleep(.001)
        self.assertFalse(aos_agent_say.drop_new(self.base / "input", "mail-1.json", "hi"))  # 同名已在：不投，但照叫
        self.assertEqual(len(self.wakes()), 2)  # 前一次可能崩在投好、叫之前
        other = self.root / "plain"
        self.assertTrue(aos_agent_say.drop_new(other / "in", "x.json", "hi"))
        self.assertEqual(len(self.wakes()), 2)  # 不是 agent 家（沒 tick.json）：不叫


if __name__ == "__main__":
    unittest.main()
