"""peek_clock：讀 $AOS_CLOCK 回 cycle 與 interval_ms；沒設或缺檔＝ClockMissing（不當 0）、壞檔＝ClockBad（11-10 深夜 tool-packs）。"""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ENTRY = Path(__file__).resolve().parents[1] / "_entry"


class PeekClockTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = Path(self.tmp.name) / "clock"

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, args="{}", **env):
        e = {k: v for k, v in os.environ.items() if k not in ("AOS_CLOCK", "AOS_CLOCK_INTERVAL")}
        e.update(env)
        r = subprocess.run([str(ENTRY)], input=args, text=True, capture_output=True, env=e)
        return r.returncode, r.stdout.strip()

    def test_reads_cycle_and_interval(self):
        self.clock.write_text("42\n")
        self.assertEqual(self.call(AOS_CLOCK=str(self.clock)), (0, '{"cycle": 42, "interval_ms": 1000}'))
        code, out = self.call(AOS_CLOCK=str(self.clock), AOS_CLOCK_INTERVAL="250")
        self.assertEqual(json.loads(out), {"cycle": 42, "interval_ms": 250})

    def test_empty_file_is_zero(self):
        self.clock.write_text("")
        self.assertEqual(json.loads(self.call(AOS_CLOCK=str(self.clock))[1])["cycle"], 0)

    def test_missing(self):
        code, out = self.call()
        self.assertEqual(code, 1)
        self.assertTrue(out.startswith("peek_clock: error: ClockMissing AOS_CLOCK is not set"), out)
        code, out = self.call(AOS_CLOCK=str(self.clock))
        self.assertEqual(code, 1)
        self.assertTrue(out.startswith("peek_clock: error: ClockMissing clock file"), out)

    def test_bad(self):
        self.clock.write_text("x")
        self.assertTrue(self.call(AOS_CLOCK=str(self.clock))[1].startswith("peek_clock: error: ClockBad"))
        self.clock.write_text("3")
        self.assertTrue(self.call(AOS_CLOCK=str(self.clock), AOS_CLOCK_INTERVAL="0")[1].startswith("peek_clock: error: ClockBad"))
        self.assertTrue(self.call('{"a": 1}', AOS_CLOCK=str(self.clock))[1].startswith("peek_clock: error: ArgumentsBad"))


if __name__ == "__main__":
    unittest.main()
