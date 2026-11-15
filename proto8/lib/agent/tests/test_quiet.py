"""驗 11-15 逾時改 0：cli.json 沒寫 timeout_ms＝不限時（比舊上限久的假輪不會被殺、不會 CliFailed），寫了正整數才有上限；
quiet.json（「很久沒動靜」標記）只標記：沒動靜滿門檻才寫、有動靜或結束就收掉、寫的行程不在了讀者當沒有。"""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
LIB = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(LIB))
from agent import cli_base, cli_print, quiet  # noqa: E402


class Died(Exception):
    def __init__(self, code, reason):
        super().__init__("%s %s" % (code, reason))
        self.code = code


def die(code, reason):
    raise Died(code, reason)


class TurnTimeout(unittest.TestCase):
    def test_omitted_null_zero_and_bad_mean_no_limit(self):
        for cfg in ({}, {"timeout_ms": None}, {"timeout_ms": 0}, {"timeout_ms": -5}, {"timeout_ms": True}, {"timeout_ms": "600000"}):
            with self.subTest(cfg=cfg):
                self.assertEqual(cli_base.turn_timeout_ms(cfg), 0)
                self.assertIsNone(cli_print.timeout_seconds(cli_base.turn_timeout_ms(cfg)))

    def test_written_positive_number_is_the_limit(self):
        self.assertEqual(cli_base.turn_timeout_ms({"timeout_ms": 1500}), 1500)

    def test_a_turn_longer_than_the_old_limit_is_not_killed(self):
        # 舊上限縮成 0.3 秒來比：寫了 300 ms 的照舊被殺（CliFailed）；沒寫的同一支 1.2 秒假輪做完、拿到輸出。
        with tempfile.TemporaryDirectory() as ws, patch.object(cli_base, "die", die):
            argv = [sys.executable, "-c", "import time; time.sleep(1.2); print('done')"]
            with self.assertRaises(Died) as got:
                cli_print.run_cli(argv, "", ws, cli_base.turn_timeout_ms({"timeout_ms": 300}))
            self.assertEqual(got.exception.code, "CliFailed")
            started = time.monotonic()
            r = cli_print.run_cli(argv, "", ws, cli_base.turn_timeout_ms({}))
            self.assertGreaterEqual(time.monotonic() - started, 1.2)
            self.assertEqual((r.returncode, r.stdout.strip()), (0, "done"))

    def test_stream_turn_longer_than_the_old_limit_is_not_killed(self):
        with tempfile.TemporaryDirectory() as ws, patch.object(cli_base, "die", die):
            argv = [sys.executable, "-c", "import time, sys; sys.stdin.read(); time.sleep(1.2); print('{\"type\": \"result\"}')"]
            live = os.path.join(ws, "live.jsonl")
            code, lines = cli_print.run_claude_stream(argv, "hi", ws, cli_base.turn_timeout_ms({}), live)
            self.assertEqual(code, 0)
            self.assertEqual(lines, ['{"type": "result"}\n'])


class QuietMark(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stack = self.tmp.name

    def test_mark_read_clear(self):
        rec = quiet.mark(self.stack, "cli_turn", since=time.time() - 700)
        self.assertEqual(rec["what"], "cli_turn")
        self.assertTrue(rec["quiet"])
        self.assertGreaterEqual(rec["quiet_s"], 700)
        self.assertEqual(rec["pid"], os.getpid())
        self.assertEqual(quiet.read(self.stack), rec)
        quiet.clear(self.stack)
        self.assertFalse(os.path.exists(quiet.path(self.stack)))
        quiet.clear(self.stack)                                  # 本來就不在不算錯

    def test_dead_writer_reads_as_none_and_null_pid_is_kept(self):
        quiet.mark(self.stack, "cli_turn", since=time.time(), pid=2 ** 22 + 12345)   # 不會有這個 pid
        self.assertIsNone(quiet.read(self.stack))
        quiet.mark(self.stack, "brain_reply", since=time.time(), pid=0)
        self.assertIsNone(json.loads(Path(quiet.path(self.stack)).read_text())["pid"])
        self.assertEqual(quiet.read(self.stack)["what"], "brain_reply")

    def test_watch_marks_after_silence_clears_on_activity_and_on_stop(self):
        log = os.path.join(self.stack, "live.jsonl")
        Path(log).write_text("")
        w = quiet.Watch(self.stack, "cli_turn", [log, os.path.join(self.stack, "transcripts")], after_s=0.3, poll_s=0.05, refresh_s=0.1)
        with w:
            time.sleep(0.15)
            self.assertFalse(os.path.exists(quiet.path(self.stack)))     # 還沒滿門檻
            deadline = time.time() + 3
            while not os.path.exists(quiet.path(self.stack)) and time.time() < deadline:
                time.sleep(0.02)
            rec = quiet.read(self.stack)
            self.assertEqual((rec["what"], rec["pid"]), ("cli_turn", os.getpid()))
            with open(log, "a") as f:                               # 有動靜了：標記收掉
                f.write("{}\n")
            deadline = time.time() + 3
            while os.path.exists(quiet.path(self.stack)) and time.time() < deadline:
                time.sleep(0.02)
            self.assertFalse(os.path.exists(quiet.path(self.stack)))
            deadline = time.time() + 3                              # 又安靜下來：再標
            while not os.path.exists(quiet.path(self.stack)) and time.time() < deadline:
                time.sleep(0.02)
            self.assertTrue(os.path.exists(quiet.path(self.stack)))
        self.assertFalse(os.path.exists(quiet.path(self.stack)))         # 這輪結束：收掉

    def test_watch_start_removes_a_leftover(self):
        quiet.mark(self.stack, "cli_turn", since=time.time() - 900)
        with quiet.Watch(self.stack, "cli_turn", [], after_s=60, poll_s=0.05):
            self.assertFalse(os.path.exists(quiet.path(self.stack)))


if __name__ == "__main__":
    unittest.main()
