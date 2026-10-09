"""kernel 骨架（spec.md）：設定、state、快照、執行順序、送出與核對。驗收條號見 kernel-pack §9。"""
import os
import unittest

from kernelcase import BRAIN, CoreCase, KernelMixin  # noqa: F401


class KernelSmoke(KernelMixin, CoreCase):
    def setUp(self):
        super().setUp()
        self.setup_kernel()

    def test_kill_round_trip(self):
        """存意圖 → 送 ctl → 核心收掉 → 回條 ok → done；keep 重起新 run，不再 kill。"""
        self.cfg([self.kill_rule(until=1)])
        run = self.brain_run()
        p = self.tock_kernel(1)
        self.assertEqual(p.returncode, 0, self.show(p))
        st = self.state()
        self.assertEqual(len(st["pending"]), 1, self.show(p))
        self.assertEqual(self.ctl()["run"], run)
        self.assertEqual(self.ctl()["id"], st["pending"][0]["id"])
        self.core_round()
        self.assertEqual(self.receipt()["result"]["ok"], True, self.receipt())
        p = self.tock_kernel(2)
        st = self.state()
        self.assertEqual(st["pending"], [], self.show(p))
        self.assertEqual(st["done"][-1]["result"], "ok")
        self.core_round()
        self.assertNotEqual(self.brain_run(), run)
        p = self.tock_kernel(3)
        self.assertIsNone(self.ctl(), self.show(p))


if __name__ == "__main__":
    unittest.main()
