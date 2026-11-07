"""Verify knowledge locks use a fixed wall-clock lease regardless of caller ticks."""
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HERE), str(HERE.parents[1])]
import locking


@unittest.skipUnless(shutil.which("aos-lock"), "aos-lock must be on PATH")
class LockingTest(unittest.TestCase):
    def test_fast_and_frozen_ticks_do_not_change_wall_clock_lease(self):
        with tempfile.TemporaryDirectory() as base:
            folder = Path(base) / "node"
            folder.mkdir()
            tick = Path(base) / "tick"
            tick.write_text("0\n")
            with patch.dict(os.environ, AOS_TICK=str(tick), AOS_TICK_INTERVAL="1"):
                with locking.with_lock(str(folder), "wall-clock test"):
                    value = locking.holder(str(folder))
                    self.assertEqual(value["lease_ticks"], 10)
                    self.assertNotIn("acquired_at_ticks", value)
                    tick.write_text("1000000000\n")
                    self.assertTrue(locking.live(str(folder), value))
                    code, _ = locking.run_lock(["acquire", str(folder) + "/"])
                    self.assertEqual(code, 10, "fast tick must not reap a live lock")
                    # Freeze the tick and wait until the actual ten-second lease ends.
                    deadline = time.monotonic() + 12
                    while locking.live(str(folder), value) and time.monotonic() < deadline:
                        time.sleep(0.05)
                    self.assertFalse(locking.live(str(folder), value))
                    code, _ = locking.run_lock(["acquire", str(folder) + "/"])
                    self.assertEqual(code, 0, "frozen tick must not prevent wall-clock expiry")
                self.assertFalse((folder / ".lock").exists())

    def test_invalid_caller_clock_is_not_read(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, AOS_TICK="/missing/tick", AOS_TICK_INTERVAL="bad"):
                with locking.with_lock(folder, "invalid caller clock"):
                    self.assertTrue(locking.live(folder, locking.holder(folder)))


if __name__ == "__main__":
    unittest.main()
