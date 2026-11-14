"""test_limits_keys - ctl add --limits 的鍵：daemon 認得的 cgroup 鍵 mem_total_mb、procs_total（B5）Python 這邊也要認；nofile 照舊報錯（ok-limits 11-14）。"""
import sys
import unittest
from pathlib import Path

PROTO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(PROTO / "py"), str(PROTO / "lib")]
import daemon_ctl as dc  # noqa: E402


class LimitsKeys(unittest.TestCase):
    def test_cgroup_keys_pass(self):
        v = {"mem_mb": 512, "files": 256, "mem_total_mb": 2048, "procs_total": 64}
        self.assertEqual(dc.check_limits(dict(v), "--limits", "ArgumentsBad"), v)

    def test_nofile_is_still_unknown(self):
        with self.assertRaises(dc.Fail) as cm:
            dc.check_limits({"nofile": 256}, "--limits", "ArgumentsBad")
        self.assertEqual(cm.exception.code, "ArgumentsBad")
        self.assertIn("unknown key nofile in --limits (keys: mem_mb, cpu_s, procs, file_mb, files, mem_total_mb, procs_total, user)", str(cm.exception))

    def test_total_keys_need_positive_ints(self):
        for bad in (0, -1, "64", 1.5, True):
            with self.assertRaises(dc.Fail):
                dc.check_limits({"procs_total": bad}, "--limits", "ArgumentsBad")


if __name__ == "__main__":
    unittest.main()
