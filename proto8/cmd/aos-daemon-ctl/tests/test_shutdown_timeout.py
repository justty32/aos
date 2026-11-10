"""test_shutdown_timeout - shutdown 等不到 daemon 退出＝StillRunning 錯誤（11-10 two-machines：退 0 會讓人以為可以 commit／push）。"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROTO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(PROTO / "py"), str(PROTO / "lib")]
import daemon_ctl as dc  # noqa: E402
from daemon_ctl import ctl  # noqa: E402


class ShutdownTimeout(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="sd-timeout-")
        Path(self.d, "daemon.json").write_text('{"procs": {}}\n')

    def tearDown(self):
        import shutil
        shutil.rmtree(self.d, ignore_errors=True)

    def run_shutdown(self, alive_forever):
        def alive(d, state, *a, **k):
            if alive_forever:
                return 4242, None
            raise dc.Fail("DaemonMissing", "gone")
        calls = {"n": 0}

        def first_alive_then(d, state, *a, **k):
            calls["n"] += 1
            if calls["n"] == 1 or alive_forever:
                return 4242, None
            raise dc.Fail("DaemonMissing", "gone")
        with mock.patch.object(ctl, "read_state", return_value={"pid": 4242}), \
                mock.patch.object(ctl, "check_alive", side_effect=first_alive_then), \
                mock.patch.object(ctl, "poke", return_value=None):
            return ctl.shutdown(self.d, timeout_s=0.2)

    def test_still_running_is_an_error(self):
        with self.assertRaises(dc.Fail) as cm:
            self.run_shutdown(alive_forever=True)
        self.assertEqual(cm.exception.code, "StillRunning")
        self.assertIn("not safe to commit", str(cm.exception))
        self.assertTrue(os.path.exists(os.path.join(self.d, "ctl.json")))     # the stop stays for its next round

    def test_exits_in_time_returns_seq(self):
        self.assertEqual(self.run_shutdown(alive_forever=False), 1)


if __name__ == "__main__":
    unittest.main()
