"""真的開一個 daemon 進程：起來就有第一顆 cpu 跑 kernel，stop 之後全收乾淨。"""
import json
import os
import shutil
import unittest

from _util import alive, kill_hard, mktmp, wait_until
import aos_daemon as d


class DaemonTest(unittest.TestCase):
    def setUp(self):
        self.tmp = mktmp("aos-proto4-2-daemon-")
        self.home = d.Home(self.tmp)

    def tearDown(self):
        try:
            st = self.home.state() or {}
            d.stop(self.home)
            for c in st.get("cpus", {}).values():      # 保險：state 裡看到的 pid 一律收掉
                kill_hard(c["pid"])
        finally:
            shutil.rmtree(self.tmp, ignore_errors=True)

    def test_start_brings_up_kernel_cpu_then_stop_cleans_up(self):
        h = self.home
        self.assertTrue(d.start(h))
        self.assertTrue(h.alive())
        self.assertFalse(d.start(h))                                     # 第二次：已經在跑

        # kernel 的 inst.json 是 daemon 自動生的
        with open(os.path.join(h.kernel, ".aos", "inst.json")) as f:
            inst = json.load(f)
        self.assertTrue(inst["argv"][1].endswith("aos_kernel.py"))
        self.assertEqual(inst["env"]["AOS_HOME"], h.dir)

        self.assertTrue(wait_until(lambda: "kernel" in (h.state() or {}).get("cpus", {})))
        k = h.state()["cpus"]["kernel"]
        self.assertTrue(k["alive"])
        self.assertEqual(k["dir"], h.kernel)
        self.assertTrue(alive(k["pid"]))
        self.assertIsNotNone(k["rss_kb"])                                # 佔用資源看得到
        t0 = k["tick"]
        self.assertTrue(wait_until(lambda: h.state()["cpus"]["kernel"]["tick"] > t0))   # 格數在長

        # 登記表落地了
        with open(h.cpusf) as f:
            self.assertEqual(list(json.load(f)), ["kernel"])
        # kernel 每格印的摘要進了它自己的 last.json
        with open(os.path.join(h.kernel, ".aos", "last.json")) as f:
            self.assertIn("cpu 1 顆", json.load(f)["stdout"])

        kpid = k["pid"]
        self.assertTrue(d.stop(h))
        self.assertFalse(h.alive())
        self.assertTrue(wait_until(lambda: not alive(kpid), 5.0))        # kernel 進程也不在了
        self.assertFalse(os.path.exists(h.statef))
        self.assertFalse(os.path.exists(h.pidf))


if __name__ == "__main__":
    unittest.main()
