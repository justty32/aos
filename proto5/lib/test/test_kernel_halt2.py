"""proto5-2 kernel：搬池、池從 info 消失、停機縮池與 halt 等待（kernel-info §4、kernel-pools §2 第 5 步、kernel/tick.md 第 9 步）。

全部用假 daemon（_kernel_fake），直接呼叫 tick 一格一格跑；cpu 的回音由測試自己寫。
"""
import io
import contextlib
from pathlib import Path
import sys
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import aos_kernel_boot
from _kernel_fake import FakeCase


def free(st, pool="default"):
    return sorted(st["pools"][pool]["free"])


class MovePool(FakeCase):
    def test_move_waits_for_old_pool_gone(self):
        self.init({"default": {"count": 2}})
        self.boot()
        self.settle()
        self.add("a")
        st = self.tick()
        self.fake.linger.add("default")
        self.edit_info(default={"count": 2, "dpool": "k2-default"})
        st = self.tick()
        entry = st["pools"]["default"]
        self.assertEqual(entry["dpool"], "default")
        self.assertEqual(entry["free"], [])
        self.respond(st["on"]["a"])
        st = self.ticks(3)
        entry = st["pools"]["default"]
        self.assertEqual((entry["dpool"], entry["sent"]["count"]), ("default", 0))
        self.assertIsNotNone(self.fake.summary("default"))  # 還在收：不換位置
        self.assertIsNone(self.fake.pool("k2-default"))
        self.fake.gone("default")
        st = self.ticks(3)
        entry = st["pools"]["default"]
        self.assertEqual(entry["dpool"], "k2-default")
        self.assertEqual(self.fake.pool("k2-default")["count"], 2)
        self.assertEqual(free(st), [1])
        self.assertEqual(st["busy"]["default/0"]["proc"], "a")  # a 回 queue 後在新位置派

    def test_pool_removed_then_readded(self):
        self.init({"default": {"count": 1}, "gpu": {"count": 2}})
        self.boot()
        self.settle()
        self.edit_info(gpu=None)
        self.add("g", pool="default")
        st = self.ticks(3)
        self.assertNotIn("gpu", st["pools"])
        self.assertIsNone(self.fake.pool("gpu"))
        self.edit_info(gpu={"count": 1})
        st = self.ticks(3)
        self.assertEqual(st["pools"]["gpu"]["sent"]["count"], 1)

    def test_removed_pool_queue_keeps_waiting(self):
        self.init({"default": {"count": 1}, "gpu": {"count": 0}})
        self.boot()
        self.settle()
        self.add("g", pool="gpu")
        self.tick()
        self.edit_info(gpu=None)
        st = self.ticks(3)
        self.assertEqual(st["procs"]["g"]["status"], "queued")
        self.edit_info(gpu={"count": 1})
        st = self.ticks(3)
        self.assertEqual(st["busy"]["gpu/0"]["proc"], "g")


class Halt(FakeCase):
    def setUp(self):
        super().setUp()
        self.init({"default": {"count": 2}, "llm": {"count": 1}})
        self.boot()
        self.settle()

    def test_halt_order(self):
        self.add("r")
        once = self.add("o", once=True, pool="llm")
        waiting = self.add("w", once=True)
        st = self.tick()
        self.assertEqual(st["procs"]["w"]["status"], "running")
        self.edit_info(llm={"count": 0})
        self.add("late", pool="llm", once=True)
        self.tick()
        st = self.state()
        self.stop_kernel()
        n = len(self.fake.seen)
        late = self.add("late2", once=True)
        st = self.tick()
        self.assertEqual(st["phase"], "stopping")
        self.assertEqual(self.reply(late)["error"]["data"]["code"], "Stopping")
        self.assertFalse(st["halting"])  # 還有忙的
        for key in list(st["busy"]):
            self.respond(key)
        for _ in range(8):
            st = self.tick()
            if st["phase"] == "stopped":
                break
        self.assertEqual(st["phase"], "stopped")
        self.assertIn("result", self.reply(waiting))
        scales = [(name, p["pool"], p["count"]) for name, p in self.fake.seen[n:] if "pool" in (p or {})]
        pools = [p for _, p, _ in scales]
        self.assertEqual(sorted(pools), ["default", "llm"])
        self.assertTrue(all(c == 0 for _, _, c in scales))
        self.assertIsNone(self.fake.summary("default"))
        # one-boot：沒有 kernel 池可縮；停好那格最後寄撤登記（tick off）給開 tick 的 daemon
        name, last = self.fake.seen[-1]
        self.assertTrue(name.endswith("-untick.json"), name)
        self.assertEqual(last, {"home": str(self.K.absolute()), "off": True})
        import aos_daemon_ticks
        self.assertIsNone(aos_daemon_ticks.peek(self.D, self.K.absolute()))
        self.assertNotIn("kernel", st["pools"])
        n = len(self.fake.seen)
        st = self.tick()  # stopped 之後的格：只出貨，什麼都不寄
        self.assertEqual(st["phase"], "stopped")
        self.assertEqual(self.fake.seen[n:], [])

    def test_halt_blocked_by_daemon_error(self):
        self.fake.stopping = True
        self.stop_kernel()
        st = self.ticks(4)
        self.assertTrue(st["halting"])
        self.assertEqual(st["phase"], "stopping")
        self.assertEqual(st["pools"]["default"]["error"]["code"], "Stopping")
        self.fake.stopping = False
        for _ in range(15):
            st = self.tick()
            if st["phase"] == "stopped":
                break
        self.assertEqual(st["phase"], "stopped")

    def drive(self, stop_event):
        while not stop_event.is_set():
            try:
                self.tick()
            except Exception:
                pass
            time.sleep(.005)

    def test_halt_cli_waits_for_pools(self):
        out = io.StringIO()
        done = threading.Event()
        worker = threading.Thread(target=self.drive, args=(done,), daemon=True)
        worker.start()
        try:
            with contextlib.redirect_stdout(out):
                code = aos_kernel_boot.stop(self.K, wait_ms=5000)
        finally:
            done.set()
            worker.join(5)
        self.assertEqual(code, 0)
        self.assertEqual(out.getvalue().strip(), "stopped")
        with contextlib.redirect_stdout(out):
            aos_kernel_boot.stop(self.K)
        self.assertEqual(out.getvalue().split(), ["stopped", "stopped"])

    def test_halt_timeout_message_and_not_running(self):
        self.fake.linger.add("default")
        done = threading.Event()
        worker = threading.Thread(target=self.drive, args=(done,), daemon=True)
        worker.start()
        try:
            with self.assertRaises(aos_kernel_boot.KernelError) as cm:
                with contextlib.redirect_stdout(io.StringIO()):
                    aos_kernel_boot.stop(self.K, wait_ms=300)
        finally:
            done.set()
            worker.join(5)
        self.assertEqual(cm.exception.code, "Timeout")
        self.assertIn("拉回來", cm.exception.msg)
        self.fake.gone("default")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            aos_kernel_boot.stop(self.K, wait_ms=1000)
        self.assertEqual(out.getvalue().strip(), "stopped")


class NotRunning(FakeCase):
    def test_not_running_when_tick_not_registered(self):
        """one-boot：daemon 沒登記替這個 kernel 開 tick（或 daemon 不在）＝沒在跑；halt 印 not running、不放 stop。"""
        import aos_daemon_ticks
        self.init({"default": {"count": 1}})
        self.boot()
        self.assertIsNotNone(aos_daemon_ticks.peek(self.D, self.K.absolute()))
        aos_daemon_ticks.reg_path(self.D, self.K.absolute()).unlink()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            aos_kernel_boot.stop(self.K)
        self.assertEqual(out.getvalue().strip(), "not running")
        self.assertEqual(list((self.K / "requests").glob("stop-*")), [])

    def test_not_running_when_daemon_dead(self):
        self.init({"default": {"count": 1}})
        self.boot()
        self.fake.set_alive(False)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            aos_kernel_boot.stop(self.K)
        self.assertEqual(out.getvalue().strip(), "not running")
        self.assertEqual(list((self.K / "requests").glob("stop-*")), [])


if __name__ == "__main__":
    unittest.main()
