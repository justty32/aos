"""走 CLI 的整條路：start → register → ls → unregister → stop。
請求是 CLI 寫進 requests/、kernel 撿走翻成 daemon 請求、daemon 才真的開 cpu。"""
import os
import shutil
import time
import unittest

from _util import alive, cli, copy_fx, kill_hard, mktmp, wait_until
import aos_daemon as d


def count(dir_):
    try:
        with open(os.path.join(dir_, "count.txt")) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return 0


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = mktmp("aos-proto4-2-cli-")
        self.home = d.Home(os.path.join(self.tmp, "home"))
        self.d = copy_fx("counter", self.tmp)

    def tearDown(self):
        try:
            st = self.home.state() or {}
            cli(self.home.dir, "stop")
            for c in st.get("cpus", {}).values():
                kill_hard(c["pid"])
        finally:
            shutil.rmtree(self.tmp, ignore_errors=True)

    def test_register_then_unregister(self):
        h = self.home.dir
        self.assertIn("起來了", cli(h, "start").stdout)

        self.assertIn("送出", cli(h, "register", self.d, "cnt", "0.2").stdout)
        self.assertTrue(wait_until(lambda: count(self.d) >= 2, 15.0))     # count.txt 真的在長

        out = cli(h, "ls").stdout
        self.assertIn("cnt", out)                                          # ls 看得到
        self.assertIn("kernel", out)
        row = [l for l in out.splitlines() if l.startswith("cnt")][0].split()
        self.assertEqual(row[2], "yes")                                    # alive
        pid = int(row[1])
        self.assertTrue(alive(pid))

        cli(h, "unregister", "cnt")
        self.assertTrue(wait_until(lambda: not alive(pid), 15.0))          # cpu 進程收掉了
        self.assertTrue(wait_until(lambda: not os.path.exists("/proc/%d" % pid), 10.0))  # 也收了殭屍
        self.assertTrue(wait_until(lambda: "cnt" not in cli(h, "ls").stdout, 10.0))
        c = count(self.d)
        time.sleep(1.0)
        self.assertEqual(count(self.d), c)                                 # 不再長了

        self.assertIn("收工了", cli(h, "stop").stdout)
        self.assertFalse(self.home.alive())


if __name__ == "__main__":
    unittest.main()
