"""走 CLI 的整條路：start → register → ls → unregister → stop。
請求是 CLI 寫進 requests/、kernel 撿走翻成 daemon 請求、daemon 才真的開 cpu。

一個資料夾的本體就是它的路徑（realpath 過），不再用 name 認。"""
import os
import shutil
import time
import unittest

from _util import alive, cli, copy_fx, find_done, kill_hard, mktmp, wait_until
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
        self.rd = os.path.realpath(self.d)          # 真正會被拿來當 key 的路徑

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

        self.assertIn("送出", cli(h, "register", self.d, "0.2").stdout)
        self.assertTrue(wait_until(lambda: count(self.d) >= 2, 15.0))     # count.txt 真的在長

        out = cli(h, "ls").stdout
        self.assertIn(self.rd, out)                                        # ls 直接列路徑
        self.assertIn("(kernel)", out)
        row = [l for l in out.splitlines() if l.startswith(self.rd)][0].split()
        pid = int(row[1])
        self.assertEqual(row[2], "yes")                                    # alive
        self.assertTrue(alive(pid))

        cli(h, "unregister", self.d)
        self.assertTrue(wait_until(lambda: not alive(pid), 15.0))          # cpu 進程收掉了
        self.assertTrue(wait_until(lambda: not os.path.exists("/proc/%d" % pid), 10.0))  # 也收了殭屍
        self.assertTrue(wait_until(lambda: self.rd not in cli(h, "ls").stdout, 10.0))
        c = count(self.d)
        time.sleep(1.0)
        self.assertEqual(count(self.d), c)                                 # 不再長了

        self.assertIn("收工了", cli(h, "stop").stdout)
        self.assertFalse(self.home.alive())

    def test_register_same_dir_twice_second_rejected(self):
        """同一個資料夾兩種寫法（一個絕對、一個帶 ..）register 兩次：只有一顆 cpu，
        第二次那筆在 daemon 的 done 檔裡是 ok:false。"""
        h = self.home.dir
        self.assertIn("起來了", cli(h, "start").stdout)

        self.assertIn("送出", cli(h, "register", self.d, "0.2").stdout)
        self.assertTrue(wait_until(lambda: count(self.d) >= 1, 15.0))      # 先讓第一顆真的跑起來

        alt = os.path.join(self.tmp, "counter", "..", "counter")          # 帶 .. 的另一種寫法
        self.assertNotEqual(alt, self.d)
        self.assertEqual(os.path.realpath(alt), self.rd)
        self.assertIn("送出", cli(h, "register", alt, "0.2").stdout)

        rec = find_done(self.home.ddone, lambda r: r.get("req", {}).get("op") == "spawn"
                         and r.get("req", {}).get("dir") == self.rd
                         and r.get("ok") is False)
        self.assertIsNotNone(rec, "沒等到第二次 spawn 被拒的 done 檔")
        self.assertIn("already running", rec["result"])
        self.assertIn(self.rd, rec["result"])

        st = self.home.state() or {}
        dirs = [c["dir"] for c in st.get("cpus", {}).values()]
        self.assertEqual(dirs.count(self.rd), 1)                          # 只有一顆

    def test_unregister_not_running_dir_rejected(self):
        h = self.home.dir
        self.assertIn("起來了", cli(h, "start").stdout)

        self.assertIn("送出", cli(h, "unregister", self.d).stdout)         # 這資料夾根本沒 register 過

        rec = find_done(self.home.ddone, lambda r: r.get("req", {}).get("op") == "kill"
                         and r.get("req", {}).get("dir") == self.rd
                         and r.get("ok") is False)
        self.assertIsNotNone(rec, "沒等到 unregister 被拒的 done 檔")
        self.assertIn("not running", rec["result"])


if __name__ == "__main__":
    unittest.main()
