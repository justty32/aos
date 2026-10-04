"""〔tools〕工具包：aos7-ctl（固定檔名無損編碼、task 子命令）。

從 tests/core/test_matrix_a3.py 的 TestOwnerNames（A2-13、A3-06）與 tests/core/test_ctl.py 的 test_aos7_ctl_task 搬來，內容未改。
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tests"))  # tests/：base

import unittest  # noqa: E402

from base import SLEEP, CoreCase, DaemonCase  # noqa: E402
import aos7_ctl  # noqa: E402
from aos7_fs import read_json, write_json  # noqa: E402,F401


# ---------- A3-06 ----------

class TestOwnerNames(DaemonCase):
    """〔tools〕aos7-ctl 的固定檔名無損編碼（A2-13、A3-06，F57）。"""
    def test_fixed_name_lossless(self):
        """A3-06：甲／乙、A/B 與 A+B、x? 與 x!（owner、by、node 各段）都編成不同檔名；很長的也不同、不超過 255 bytes。"""
        pairs = [("甲", "乙"), ("A/B", "A+B"), ("x?", "x!"), ("a.b", "a@b"), ("%41", "A"),
                 ("l" * 300 + "1", "l" * 300 + "2")]
        for a, b in pairs:
            self.assertNotEqual(aos7_ctl.fixed_name("cli", "pause", "a", a), aos7_ctl.fixed_name("cli", "pause", "a", b),
                                "owner %r 與 %r 撞名" % (a, b))
            self.assertNotEqual(aos7_ctl.fixed_name(a, "pause", "n"), aos7_ctl.fixed_name(b, "pause", "n"),
                                "by %r 與 %r 撞名" % (a, b))
            self.assertNotEqual(aos7_ctl.fixed_name("cli", "pause", a), aos7_ctl.fixed_name("cli", "pause", b),
                                "node %r 與 %r 撞名" % (a, b))
            for x in (a, b):
                self.assertLessEqual(len(aos7_ctl.fixed_name(x, "pause", x, x).encode()), 255)
        self.assertNotEqual(aos7_ctl.fixed_name("cli", "pause", "a", ""), aos7_ctl.fixed_name("cli", "pause", "a"))

    def test_non_ascii_owner_pauses_both_kept(self):
        """A3-06：daemon 沒起前送兩份 pause（owner 甲、乙），起來後兩個 owner 都在 paused.json。"""
        self.mknode("a", interval_ms=120)
        a = self.ctl("pause", "a", "--owner", "甲")
        b = self.ctl("pause", "a", "--owner", "乙")
        self.assertNotEqual(a, b, "不同 owner 的 pause 寫成同一個檔")
        self.start_daemon(register=["a"])
        self.wait_receipt(a)
        self.wait_receipt(b)
        owners = ((read_json(os.path.join(self.root, ".aosd", "paused.json"), {}) or {}).get("paused") or {}).get("a")
        self.assertEqual(sorted(owners or []), sorted(["甲", "乙"]))


# ---------- A3-03 ----------


class TestCtlTask(CoreCase):
    """〔tools〕aos7-ctl task 寫 ctl.json（F57）。"""
    def done(self, node, slot):
        return read_json(os.path.join(self.slot(node, slot), "ctl-done.json"))

    def test_aos7_ctl_task(self):
        """〔tools〕"""
        node = self.mknode("a", [{"name": "s", "argv": SLEEP}])
        self.tick()
        self.wait_pid(node, "s")
        self.prog("aos7-ctl", "task", self.slot(node, "s"), "kill", "why", "--run", "1")
        self.tock()
        self.assertTrue(self.done(node, "s")["result"]["ok"])


if __name__ == "__main__":
    unittest.main()
