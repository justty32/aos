"""tick-gap P2 的 astra 唯讀審查（2026-09-25）必修修補：

- M2：AOS_HOPS 指到 FIFO（沒人讀）也不能卡住主程式；不是普通檔就不寫。
- M3：量測遇到怪字（落單的 \\ud800）不能讓程式拋例外。
- M4：判 bad 那格填 {look} 時讀 target，target 被換成 FIFO 也不能卡住 kernel。
- S2：on_bad 的 body 上限算 UTF-8 位元組。
"""
import contextlib
import json
import os
import signal
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import aos_hops  # noqa: E402
import aos_kernel_ledger  # noqa: E402
import aos_kernel_ls  # noqa: E402
import test_tick_gap as _ttg  # noqa: E402


@contextlib.contextmanager
def deadline(seconds):
    """卡住就讓測試失敗，而不是整套測試掛著。"""
    def boom(*_):
        raise AssertionError("卡住超過 %d 秒" % seconds)
    old = signal.signal(signal.SIGALRM, boom)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


class HopsNeverBlocks(unittest.TestCase):
    def test_fifo_without_reader_does_not_block(self):
        with tempfile.TemporaryDirectory() as d:
            fifo = os.path.join(d, "hops")
            os.mkfifo(fifo)
            with mock.patch.dict(os.environ, {aos_hops.ENV: fifo}), deadline(5):
                aos_hops.mark("kernel", "begin")

    def test_fifo_with_reader_is_not_written(self):
        with tempfile.TemporaryDirectory() as d:
            fifo = os.path.join(d, "hops")
            os.mkfifo(fifo)
            reader = os.open(fifo, os.O_RDONLY | os.O_NONBLOCK)
            try:
                with mock.patch.dict(os.environ, {aos_hops.ENV: fifo}), deadline(5):
                    aos_hops.mark("kernel", "begin")
                self.assertEqual(os.read(reader, 100), b"")  # 管道裡什麼都沒有（寫端從沒開過）
            finally:
                os.close(reader)

    def test_lone_surrogate_does_not_raise(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "hops.jsonl")
            with mock.patch.dict(os.environ, {aos_hops.ENV: path}):
                aos_hops.mark("kernel", "req", method="\ud800", name="中文")
            with open(path, encoding="ascii") as f:
                line = json.loads(f.read())
            self.assertEqual((line["method"], line["name"]), ("\ud800", "中文"))


class LookNeverBlocks(unittest.TestCase):
    def test_fifo_target_is_pointed_at_directly(self):
        with tempfile.TemporaryDirectory() as d:
            fifo = os.path.join(d, "work.json")
            os.mkfifo(fifo)
            with deadline(5):
                self.assertEqual(aos_kernel_ls.stderr_hint(fifo), fifo)

    def test_big_target_is_not_read(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "work.json")
            with open(path, "w") as f:
                f.write('{"stderr": "e.err", "pad": "%s"}' % ("x" * (aos_kernel_ls.HINT_MAX + 10)))
            self.assertEqual(aos_kernel_ls.stderr_hint(path), path)

    def test_normal_target_still_finds_stderr(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "work.json")
            with open(path, "w") as f:
                json.dump({"argv": ["true"], "stderr": {"$opt": ["append"], "$val": "e.err"}}, f)
            self.assertEqual(aos_kernel_ls.stderr_hint(path), os.path.join(d, "e.err"))


class BadTickWithFifoTarget(_ttg.KernelBase):
    def test_tick_that_judges_bad_is_not_blocked_by_fifo_target(self):
        inbox = self.root / "inbox"
        inbox.mkdir()
        self.add("w", on_bad={"dir": str(inbox)})
        target = self.root / "work.json"
        for _ in range(3):                                 # FakeCase 的 bad_after 是 3
            st = self.tick()
            self.respond(st["on"]["w"], code=1)
        target.unlink(missing_ok=True)
        os.mkfifo(target)                                  # 判 bad 之前 target 被換成 FIFO
        with deadline(10):
            st = self.tick()
        self.assertEqual(st["procs"]["w"]["status"], "bad")
        (only,) = inbox.iterdir()
        self.assertIn(str(target), json.loads(only.read_text()))


class BodyLimitInBytes(unittest.TestCase):
    def test_chinese_body_over_64kb_is_refused(self):
        ok = {"dir": "/x", "body": "字" * 20000}          # 2 萬字 ≈ 6 萬位元組：收
        too_big = {"dir": "/x", "body": "字" * 30000}     # 3 萬字 ≈ 9 萬位元組：以前算字數會收
        self.assertTrue(aos_kernel_ledger._on_bad(ok))
        self.assertFalse(aos_kernel_ledger._on_bad(too_big))


if __name__ == "__main__":
    unittest.main()
