"""aos.gdb 的三個小加強（使用者 11-20 選項框三個都選，線 aos-gdb-small-1120；不起 daemon）：Pending.cancel()（只是不等、不收回，之後 is_done() 真、wait() 回 cancelled）、a.bp.set 回斷點物件、磁碟上的名字號碼補零到 4 位（gdb_0012，12 個以上照號碼排；.id 照舊是 int）。假的 aos-agent 借 test_gdb_trigger 的 AddFails（setUp 那幾支）。"""
import json
import os
import sys
import threading
import time
import unittest
from pathlib import Path

PROTO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROTO / "py"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from aos.gdb import trigger  # noqa: E402
from aos.gdb.handles import Breakpoint, Pending  # noqa: E402
from aos.gdb.look import Why, Failed, bp_id, bp_name  # noqa: E402
from aos.gdb import watcher  # noqa: E402
import test_gdb_trigger as _t  # noqa: E402（只借假的 aos-agent；不把它的類別拉進這個模組，免得測兩次）

FAKE = (_t.AddFails.setUp, _t.AddFails.tearDown, _t.AddFails.mode)
del _t


def result(outcome, head):
    w = Why("ann", True, True, [])
    w.outcome, w.head = outcome, head
    return w


class Cancel(unittest.TestCase):
    """使用者 11-20 選「Pending 加 cancel()」；紀錄沒寫細節，選最小做法：只是不再等、不收回送出的東西。"""

    def test_cancel_stops_the_wait_and_wait_says_cancelled(self):
        seen = []

        def run(cancel):                                   # 像 Breakpoints._wait：沒停就一直等，cancel 設了就回 cancelled
            while not cancel.wait(0.05):
                pass
            seen.append("asked")
            return result("cancelled", "stopped waiting (cancel()); nothing is taken back: what a.bp.step() sent stays sent")
        p = Pending("a.bp.step(wait=False)", "ann", run=run)
        self.assertFalse(p.is_done())
        self.assertIn(".cancel() stops waiting", repr(p))
        t = time.monotonic()
        self.assertTrue(p.cancel())                        # True＝是這次 cancel 讓它好的
        self.assertLess(time.monotonic() - t, 2)
        self.assertEqual(seen, ["asked"])
        self.assertTrue(p.is_done())
        self.assertEqual(p.wait().outcome, "cancelled")
        self.assertIn("done: stopped waiting (cancel())", repr(p))
        self.assertFalse(p.cancel())                       # 再叫一次：早就好了，什麼都不變
        self.assertEqual(p.wait().outcome, "cancelled")

    def test_cancel_after_it_is_done_changes_nothing(self):
        w = result("stopped", "stopped after one step, before think")
        ready = Pending("a.bp.pause(wait=False)", "ann", value=w)      # 已經停著時 pause(wait=False) 回的
        self.assertFalse(ready.cancel())
        self.assertIs(ready.wait(), w)
        go = threading.Event()
        p = Pending("a.bp.resume(wait=False)", "ann", run=lambda cancel: (go.wait(5), w)[1])
        go.set()
        p.wait()
        self.assertFalse(p.cancel())
        self.assertIs(p.wait(), w)                         # 照原本的結果

    def test_cancel_when_the_wait_had_failed(self):
        def boom(cancel):
            raise Failed("a.bp.resume", "it broke")
        p = Pending("a.bp.resume(wait=False)", "ann", run=boom)
        while not p.is_done():
            time.sleep(0.01)
        self.assertFalse(p.cancel())
        with self.assertRaises(Failed):
            p.wait()

    def test_the_real_wait_loop_sees_cancel(self):
        """Breakpoints._wait 本身：cancel 設了＝回 cancelled，不叫 _take_back（不收回 step 的 pause）。"""
        import aos.gdb as g
        bp = g.Breakpoints.__new__(g.Breakpoints)
        bp._a = type("T", (), {"name": "ann", "stack": "/nonexistent"})()
        bp._s, bp._mine = {}, set()
        bp.stopped = lambda: False
        bp._body = lambda: "busy"
        bp.why = lambda: Why("ann", False, False, [])
        took = []
        bp._take_back = lambda what: took.append(what)
        cancel = threading.Event()
        cancel.set()
        r = bp._wait((None, False, None), "step", False, own=7, report=False, cancel=cancel)
        self.assertEqual((r.outcome, r.head), ("cancelled", "stopped waiting (cancel()); nothing is taken back: what a.bp.step() sent stays sent"))
        self.assertEqual(took, [])


class Padding(unittest.TestCase):
    """使用者 11-20 選「斷點號碼檔名補零」：hook 名、小格夾、觀察者 proc 名的號碼補零到 4 位；.id 照舊是 int。"""

    def test_names(self):
        self.assertEqual([bp_name(i) for i in (1, 12, 9999, 10000, "mine")], ["0001", "0012", "9999", "10000", "mine"])
        self.assertEqual((bp_id("gdb_0012"), bp_id("gdbw_0003"), bp_id("gdb_0001")), (12, 3, 1))
        self.assertEqual(watcher.proc_of(2), "gdbw_0002")
        self.assertEqual(watcher.proc_of("mine"), "gdbw_mine")

    setUp, tearDown, mode = FAKE

    def test_twelve_breakpoints_list_in_number_order(self):
        self.mode("ok")
        got = [self.bp.add.after_tool().id for _ in range(12)]
        self.assertEqual(got, list(range(1, 13)))
        cells = sorted(os.listdir(self.tmp / "stack" / "hookeds"))                 # 照名字排＝照號碼排
        self.assertEqual(cells, ["gdb_%04d" % i for i in range(1, 13)])
        self.assertEqual(json.loads((self.tmp / "hooks.json").read_text()), cells)   # hook 名同一個（假的 aos-agent 照名字排）
        self.assertEqual([r["id"] for r in self.bp.ls()], list(range(1, 13)))
        self.assertEqual(self.bp.get("12")["id"], 12)
        self.bp.rm(10)
        self.assertEqual(self.bp.add.before_tool().id, 13)                       # 不重用
        m = self.bp.add.after_tool(id="mine")
        self.assertEqual(sorted(os.listdir(self.tmp / "stack" / "hookeds"))[-1], "gdb_mine")   # 名字原樣、排在號碼後面
        self.assertEqual(m.id, "mine")


class SetReturnsTheBreakpoint(unittest.TestCase):
    """使用者 11-20 選「a.bp.set 也回物件」：跟 add 回的同一種（.id、.kind，屬性每次重查）。"""

    setUp, tearDown, mode = FAKE

    def test_set_returns_a_live_breakpoint(self):
        self.mode("ok")
        b = self.bp.add.after_tool("write")
        s = self.bp.set(b, times=3)
        self.assertIsInstance(s, Breakpoint)
        self.assertTrue(s == b and s.id == 1 and type(s.id) is int)
        self.assertEqual((s.kind, s.times, s.enabled), ("after_tool", 3, True))
        off = self.bp.set("1", enabled=False)                                    # 給數字字串：回的 .id 是 int
        self.assertEqual((off.id, off.enabled), (1, False))
        trigger.write_json(str(self.tmp / "stack" / "hookeds" / "gdb_0001" / trigger.COUNT), {"fired": 5})
        self.assertEqual(s.fired, 5)                                             # 每次讀都重新查
        self.assertIn("breakpoint 1 of ann: after_tool", repr(s))
        n = self.bp.set(self.bp.add.before_tool(id="mine"), once=True)
        self.assertEqual((n.id, n.once), ("mine", True))
        self.bp.rm(b)
        with self.assertRaises(Failed) as e:
            s.times
        self.assertEqual(e.exception.code, "BreakpointGone")


if __name__ == "__main__":
    unittest.main()
