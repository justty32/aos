"""09-24 tick-gap（P2 隊）：縮短「工具結果落地 → 下一次問模型」的每一跳、壞了的反覆工作要有人知道。

- kernel：退 103＝馬上再排；跑時被叫醒過（woken）退 0／101／102 也馬上再排；出貨時叫醒的同一格就派（提交點 D）；派工後按 cpu 門鈴。
- cpu：門鈴（wake FIFO）、等子行程用 pidfd。
- 反覆工作 bad：`on_bad` 寄通知信、health 第一行不印 ok、aos-agent status 不把別人的 bad 當 kernel 壞、團隊郵差／心跳預設寄給人。
時序類的斷言只用「遠小於輪詢間隔」這種寬鬆比較（輪詢設 30 秒、斷言 10 秒內），不依賴機器不忙。
"""
import contextlib
import io
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import aos_agent_status
import aos_exec_run
import aos_home
import aos_kernel_engine
import aos_kernel_health
import aos_kernel_info
import aos_kernel_ledger
from _kernel_fake import Crash, FakeCase
import test_exec_cpu as _tec

PARK, AGAIN = 102, 103


class KernelBase(FakeCase):
    def setUp(self):
        super().setUp()
        self.init({"default": {"count": 2}})
        self.boot()
        self.settle()

    def events(self, kind):
        return [e for e in self.log_events() if e["event"] == kind]

    def post_wake(self, name):
        self.n += 1
        aos_home.post_request(self.K, "cli-w%d-%d.json" % (self.n, os.getpid()),
                              {"jsonrpc": "2.0", "method": "wake", "params": {"name": name}})

    def park(self, name="agent"):
        self.add(name, interval_ms=60000)
        st = self.tick()
        self.respond(st["on"][name], code=PARK)
        st = self.tick()
        self.assertEqual((st["procs"][name]["status"], st["procs"][name].get("parked")), ("queued", True))
        return st


class Again(KernelBase):
    def test_103_requeues_now_same_tick(self):
        self.add("a", interval_ms=60000)
        st = self.tick()
        self.respond(st["on"]["a"], code=AGAIN)
        st = self.tick()
        self.assertIn("a", st["on"])                      # 同一格第 8 步就再派
        proc = st["procs"]["a"]
        self.assertEqual((proc["runs"], proc["fails"]), (1, 0))

    def test_0_still_waits_interval(self):
        self.add("a", interval_ms=60000)
        st = self.tick()
        self.respond(st["on"]["a"], code=0)
        before = time.time()
        st = self.tick()
        self.assertNotIn("a", st["on"])
        self.assertGreaterEqual(st["procs"]["a"]["not_before"], before + 59)

    def test_woken_0_101_102_requeue_now(self):
        for code in (0, 101, PARK):
            name = "a%d" % code
            self.add(name, interval_ms=60000)
            st = self.tick()
            key = st["on"][name]
            self.post_wake(name)                           # 跑著的時候被叫醒 → woken
            st = self.tick()
            self.assertTrue(st["procs"][name].get("woken"))
            self.respond(key, code=code)
            st = self.tick()
            self.assertIn(name, st["on"], code)            # 馬上再派，不等 interval_ms、不停車
            self.assertNotIn("parked", st["procs"][name])
            self.assertNotIn("woken", st["procs"][name])
            self.respond(st["on"][name], code=100)         # done：把 cpu 讓給下一個
            self.tick()

    def test_woken_failure_still_waits(self):
        self.add("a", interval_ms=60000)
        st = self.tick()
        key = st["on"]["a"]
        self.post_wake("a")
        self.tick()
        self.respond(key, code=7)
        st = self.tick()
        self.assertNotIn("a", st["on"])                   # 失敗不因為被叫醒就連環重試
        self.assertEqual(st["procs"]["a"]["fails"], 1)

    def test_done_exit_103_means_done(self):
        info = self.info()
        info["done_exit"] = AGAIN
        aos_home.write_json(self.K / "info.json", info)
        self.add("a")
        st = self.tick()
        self.respond(st["on"]["a"], code=AGAIN)
        st = self.tick()
        self.assertEqual(st["procs"]["a"]["status"], "done")

    def test_features_has_again(self):
        self.assertEqual(self.state()["features"], ["park", "again"])

    def test_classify_table(self):
        info = {"done_exit": 100, "bad_after": 10, "park_ms": 300000}
        base = {"runs": 0, "fails": 2, "interval_ms": 5000, "status": "running"}
        now = 1000.0
        cases = [({"code": AGAIN}, False, now), ({"code": 0}, False, now + 5), ({"code": 0}, True, now),
                 ({"code": PARK}, False, now + 300), ({"code": PARK}, True, now), ({"code": 3}, True, now + 5)]
        for result, woken, want in cases:
            proc = dict(base, woken=True) if woken else dict(base)
            got = aos_kernel_info.classify(proc, {"result": dict(result, kind="exit")}, info, now)
            self.assertEqual(got["not_before"], want, (result, woken))
            self.assertNotIn("woken", got)


class DispatchWoken(KernelBase):
    def test_reply_wake_dispatches_in_same_tick(self):
        self.park()
        q = self.add("q", once=True, wake="agent")
        st = self.tick()
        qkey = st["on"]["q"]
        self.respond(qkey)
        st = self.tick()                                   # 收 q → C 出貨放回音、叫醒 → D 同一格派 agent
        self.assertTrue((self.K / "responses" / q).exists())
        self.assertIn("agent", st["on"])
        self.assertEqual(st["procs"]["agent"]["status"], "running")
        req = st["busy"][st["on"]["agent"]]["req"]
        self.assertTrue((self.cpu(st["on"]["agent"]) / "requests" / req).exists())
        seq = st["last_seq"]
        line = [json.loads(x) for x in (self.K / "kernel.log").read_text().splitlines()][-1]
        self.assertEqual(line["seq"], seq)
        kinds = [e["event"] for e in line["events"]]
        self.assertLess(kinds.index("wake"), [i for i, k in enumerate(kinds) if k == "dispatch"][-1])

    def test_first_pass_requests_are_not_reposted(self):
        """D 只放這一輪新派的：同一格第 8 步派出去、cpu 已經撿走（刪掉）的單不能被 D 再放一次。"""
        self.park()
        self.add("other", interval_ms=60000)
        q = self.add("q", once=True, wake="agent")
        st = self.tick()
        self.respond(st["on"]["q"])
        orig = aos_kernel_engine.Kernel.post_dispatched
        taken = []

        def spy(kernel, keys=None):
            orig(kernel, keys)
            if keys is None:                               # 第 8 步放完：假裝 cpu 立刻撿走（刪原單）
                for key in list(kernel.state["recent"]):
                    slot = kernel.state["busy"].get(key)
                    if slot is not None:
                        (self.cpu(key) / "requests" / slot["req"]).unlink(missing_ok=True)
                        taken.append((key, slot["req"]))
        with mock.patch.object(aos_kernel_engine.Kernel, "post_dispatched", spy):
            st = self.tick()
        self.assertTrue((self.K / "responses" / q).exists())
        for key, req in taken:
            if st["busy"].get(key, {}).get("proc") != "agent":
                self.assertFalse((self.cpu(key) / "requests" / req).exists(), key)

    def test_crash_after_D_before_post_is_resent_next_tick(self):
        self.park()
        self.add("q", once=True, wake="agent")
        st = self.tick()
        self.respond(st["on"]["q"])
        orig = aos_kernel_engine.Kernel.post_dispatched

        def crash_in_D(kernel, keys=None):
            if keys is not None:
                raise Crash()
            return orig(kernel, keys)
        with mock.patch.object(aos_kernel_engine.Kernel, "post_dispatched", crash_in_D), self.assertRaises(Crash):
            aos_kernel_engine.tick(self.K)
        st = self.state()
        key = st["on"]["agent"]                            # D 已存：記了派給誰
        req = st["busy"][key]["req"]
        self.assertFalse((self.cpu(key) / "requests" / req).exists())
        st = self.tick()                                   # 下一格靠 recent 補放
        self.assertTrue((self.cpu(key) / "requests" / req).exists())
        self.assertEqual(st["on"]["agent"], key)

    def test_dispatch_rings_the_cpu_doorbell(self):
        bells = {}
        for i in (0, 1):
            home = self.K / "pools" / "default" / "cpus" / str(i)
            bells[str(i)] = aos_home.Doorbell(str(home))
            self.addCleanup(bells[str(i)].close)
        self.add("a")
        st = self.tick()
        i = st["on"]["a"].split("/")[1]
        ready, _, _ = select.select([bells[i].fds[0]], [], [], 0)
        self.assertTrue(ready)


class Doorbell(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = self.tmp.name

    def test_ring_without_cpu_is_harmless(self):
        self.assertFalse(aos_home.ring(self.home))         # 沒有 wake
        os.mkfifo(os.path.join(self.home, "wake"))
        self.assertFalse(aos_home.ring(self.home))         # 有 FIFO、沒有讀端（cpu 沒在跑）

    def test_ring_wakes_and_wait_drains(self):
        bell = aos_home.Doorbell(self.home)
        self.addCleanup(bell.close)
        self.assertIsNotNone(bell.fds)
        for _ in range(3):
            self.assertTrue(aos_home.ring(self.home))
        start = time.monotonic()
        bell.wait(30)
        self.assertLess(time.monotonic() - start, 10)      # 響了就醒，不睡滿 30 秒
        with self.assertRaises(BlockingIOError):
            os.read(bell.fds[0], 1)                        # 幾聲都一次讀乾淨

    def test_wait_without_ring_sleeps(self):
        bell = aos_home.Doorbell(self.home)
        self.addCleanup(bell.close)
        start = time.monotonic()
        bell.wait(0.05)
        self.assertGreaterEqual(time.monotonic() - start, 0.04)   # 沒人寫也不會因為 EOF 空轉就醒

    def test_existing_fifo_is_reused(self):
        os.mkfifo(os.path.join(self.home, "wake"))
        bell = aos_home.Doorbell(self.home)
        self.addCleanup(bell.close)
        self.assertTrue(aos_home.ring(self.home))

    def test_regular_file_or_symlink_is_not_written(self):
        path = os.path.join(self.home, "wake")
        with open(path, "w") as f:
            f.write("keep")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            bell = aos_home.Doorbell(self.home)
        self.assertIsNone(bell.fds)
        self.assertIn("NoDoorbell", err.getvalue())
        self.assertFalse(aos_home.ring(self.home))
        with open(path) as f:
            self.assertEqual(f.read(), "keep")
        bell.wait(0.001)                                   # 沒門鈴＝照舊睡
        os.unlink(path)
        other = os.path.join(self.home, "elsewhere")
        os.mkfifo(other)
        os.symlink(other, path)
        keep = os.open(other, os.O_RDONLY | os.O_NONBLOCK)
        self.addCleanup(os.close, keep)
        self.assertFalse(aos_home.ring(self.home))         # O_NOFOLLOW：不跟著 symlink 寫


class PidfdWait(unittest.TestCase):
    def details(self, poll):
        return {"timed_out": False, "stopped": False, "on_poll": None, "poll": poll}

    def test_child_exit_wakes_waiter(self):
        p = subprocess.Popen(["sleep", "0.1"])
        start = time.monotonic()
        aos_exec_run._wait_full(p, 0, self.details(30.0))
        self.assertLess(time.monotonic() - start, 10)      # 不睡滿 30 秒的 poll
        self.assertEqual(p.returncode, 0)

    def test_without_pidfd_still_works(self):
        p = subprocess.Popen(["sleep", "0.05"])
        with mock.patch.object(os, "pidfd_open", side_effect=OSError("no pidfd"), create=True):
            aos_exec_run._wait_full(p, 0, self.details(0.02))
        self.assertEqual(p.returncode, 0)

    def test_timeout_still_kills(self):
        p = subprocess.Popen(["sleep", "30"], start_new_session=True)
        details = self.details(0.05)
        aos_exec_run._wait_full(p, 200, details)
        self.assertTrue(details["timed_out"])
        self.assertIsNotNone(p.returncode)


class CpuDoorbell(_tec.CpuCase):
    def test_ring_beats_a_long_poll(self):
        self.inst({"_metainfo": {"_type": "exec_cpu", "_version": 1}, "poll_ms": 30000}, "info.json")
        self.start()
        self.wait(lambda: os.path.exists(os.path.join(self.d, "wake")))
        time.sleep(0.2)                                    # 讓它進入 30 秒的睡
        start = time.monotonic()
        self.post(params={"target": self.job()})
        aos_home.ring(self.d)
        self.response()                                    # response() 最多等 6 秒
        self.assertLess(time.monotonic() - start, 10)
        self.stop()                                        # stop 走控制 pipe：也不用等滿 30 秒的睡


class BadNotice(KernelBase):
    def fail_until_bad(self, name):
        for _ in range(3):                                 # FakeCase 的 bad_after 是 3
            st = self.tick()
            self.respond(st["on"][name], code=1)
        return self.tick()

    def inbox(self):
        path = self.root / "inbox"
        path.mkdir(exist_ok=True)
        return path

    def test_letter_with_body_and_wake(self):
        self.park("agent")
        inbox = self.inbox()
        body = {"id": "{id}", "text": "{proc} 連錯 {fails} 次，看 {look}", "at": "{at}", "n": 1, "deep": {"x": "{proc}"}}
        self.add("w", on_bad={"dir": str(inbox), "body": body, "wake": "agent"})
        st = self.fail_until_bad("w")
        self.assertEqual(st["procs"]["w"]["status"], "bad")
        files = sorted(inbox.iterdir())
        self.assertEqual(len(files), 1)
        got = json.loads(files[0].read_text())
        self.assertEqual(got["id"], files[0].name[:-5])
        self.assertTrue(files[0].name.startswith("bad-w-"))
        self.assertEqual(got["text"], "w 連錯 3 次，看 %s" % (self.root / "work.json"))
        self.assertRegex(got["at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d{4}$")
        self.assertEqual((got["n"], got["deep"]), (1, {"x": "{proc}"}))  # 只換第一層字串
        self.assertIn("agent", st["on"])                   # 放完叫醒收件的 agent（同一格 D 就派）
        self.assertEqual(st["letters"], [])
        self.assertEqual(len(self.events("bad_letter")), 1)
        self.ticks(2)
        self.assertEqual(len(list(inbox.iterdir())), 1)   # 不重寄

    def test_default_body_is_a_plain_sentence(self):
        inbox = self.inbox()
        self.add("w", on_bad={"dir": str(inbox)})
        self.fail_until_bad("w")
        (only,) = inbox.iterdir()
        text = json.loads(only.read_text())
        self.assertIsInstance(text, str)
        self.assertIn("w", text)
        self.assertIn("bad", text)

    def test_undeliverable_letter_does_not_break_the_tick(self):
        self.add("w", on_bad={"dir": str(self.root / "no-such-dir")})
        st = self.fail_until_bad("w")                      # tick() 斷言退 0
        self.assertEqual(st["letters"], [])
        self.assertEqual(len(self.events("bad_letter_failed")), 1)

    def test_crash_before_delivery_resends_once(self):
        inbox = self.inbox()
        self.add("w", on_bad={"dir": str(inbox)})
        for _ in range(3):
            st = self.tick()
            self.respond(st["on"]["w"], code=1)
        orig = aos_kernel_ledger.KernelLedger.flush_letters

        def crash(kernel):
            if kernel.state["letters"]:
                raise Crash()
            return orig(kernel)
        with mock.patch.object(aos_kernel_ledger.KernelLedger, "flush_letters", crash), self.assertRaises(Crash):
            aos_kernel_engine.tick(self.K)
        self.assertEqual(len(self.state()["letters"]), 1)  # 判 bad 跟排信同一次存（提交點 B）
        self.assertEqual(list(inbox.iterdir()), [])
        st = self.tick()
        self.assertEqual(len(list(inbox.iterdir())), 1)
        self.assertEqual(st["letters"], [])

    def test_bad_shapes_are_refused(self):
        inbox = str(self.inbox())
        for on_bad, once in (({"dir": "relative"}, False), ({"dir": inbox, "x": 1}, False),
                             ({"dir": inbox, "wake": 123}, False), ("str", False),
                             ({"dir": inbox, "body": "x" * 70000}, False), ({"dir": inbox}, True)):
            name = "n%d" % self.n
            req = self.add(name, once=once, on_bad=on_bad)
            st = self.tick()
            self.assertNotIn(name, st["procs"], on_bad)
            reply = self.reply(req)
            self.assertEqual(reply["error"]["data"]["code"], "FieldTypeMismatch", on_bad)


class HealthBad(KernelBase):
    def test_first_line_is_not_ok_when_a_proc_is_bad(self):
        self.add("w")
        for _ in range(3):
            st = self.tick()
            self.respond(st["on"]["w"], code=1)
        st = self.tick()
        self.assertEqual(st["procs"]["w"]["status"], "bad")
        code, message = aos_kernel_health.health(self.K, now=st["last_tick_at"])
        self.assertEqual(code, "bad")
        self.assertIn("反覆工作 1 個 bad：w", message)

    def test_many_names_are_cut(self):
        snap = {"procs": {"p%d" % i: {"status": "bad"} for i in range(7)}}
        snap["procs"]["ok"] = {"status": "queued"}
        self.assertEqual(aos_kernel_health.bad_procs(snap), ["p%d" % i for i in range(7)])

    def test_agent_status_does_not_blame_kernel_for_others_bad(self):
        data = {"kernel": {"home": str(self.K), "proc": {"status": "queued"}, "note": ""}, "dir": "/x",
                "manual_paused": False, "paused": False, "streak": 0, "state_error": None, "resumed": False,
                "info_error": None}
        with mock.patch.object(aos_kernel_health, "health", return_value=("bad", "反覆工作 1 個 bad：w")):
            got = aos_agent_status.agent_health(data)
        self.assertNotEqual(got["code"], "kernel")


class TeamBadNotice(unittest.TestCase):
    def test_register_sends_on_bad_to_human(self):
        import aos_team_post
        from aos_team_format import Layout
        with tempfile.TemporaryDirectory() as d:
            team = Path(d) / "t"
            team.mkdir()
            seen = {}

            def call(kernel, method, params, **kw):
                seen.update(params)
                return {"result": {"name": params["name"]}}
            with mock.patch("aos_client.call", call), mock.patch.object(aos_team_post.fmt, "write_json"), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(aos_team_post.register(team, "post", ["post"], 5000, env={"AOS_KERNEL_HOME": d}), 0)
            on_bad = seen["on_bad"]
            self.assertEqual(on_bad["dir"], str(Layout(team).human_inbox))
            self.assertTrue(Path(on_bad["dir"]).is_dir())
            body = on_bad["body"]
            self.assertEqual((body["to"], body["status"], body["id"], body["at"]), ("human", "FAILED", "{id}", "{at}"))
            self.assertIn("郵差", body["text"])
            self.assertTrue(aos_kernel_ledger._on_bad(on_bad))


if __name__ == "__main__":
    unittest.main()
