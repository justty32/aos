"""once 不重起、不漏起（4.4，N-86）：tick 在各點被 kill -9 後下一個 tick 結果正確；三態判定（第 0 節）：讀不到時不做破壞性動作。"""
import os, sys  # noqa: E401
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # tests/：base、_matrix
import os
import stat
import unittest
from unittest import mock

from base import SLEEP, CoreCase
import aos7_fs
import aos7_proc
import aos7_task
import aos7_tick
from aos7_fs import read_json, write_json

# 每跑一次往 node 的 ran-<name>.txt 加一行：數得出到底跑了幾次
def once_item(name):
    return {"name": name, "mode": "once", "argv": ["sh", "-c", 'echo $AOS7_RUN >> "$AOS7_NODE/ran-%s.txt"' % name]}


class TestOnceCrash(CoreCase):
    """〔core〕"""
    def ran(self, node, name):
        try:
            with open(os.path.join(node, "ran-%s.txt" % name)) as f:
                return f.read().split()
        except OSError:
            return []

    def crash_then_continue(self, point, names=("o",)):
        node = self.mknode("a", [once_item(n) for n in names])
        out = self.tick(env={"AOS7_TEST_CRASH": point}, rc=None)
        self.assertIsNone(out)                                  # 被 SIGKILL，沒印東西
        self.assertTrue(self.round_json(node)["open"])
        self.tock(env={"AOS7_INCOMPLETE": "tick"})               # daemon 會做的：收掉被打斷的回合
        for _ in range(4):                                      # 再跑幾回合（lost 判定要等兩回合）
            self.tick()
            for n in names:
                if os.path.isdir(self.slot(node, n)):
                    v = self.view(node, n)
                    if v.state == aos7_task.LIVE and not v.get("unsure"):
                        self.wait_ended(node, n, v.run)
            self.tock()
        self.assertEqual(self.tasks(node), [], "once 項沒刪掉")
        return node

    def test_crash_after_launch_marker(self):
        node = self.crash_then_continue("after-launch")
        self.assertEqual(len(self.ran(node, "o")), 1)

    def test_crash_after_birth(self):
        """birth.json 寫了、runner 沒起（或起了沒記到）：不重起，判 lost 報出來，不會無痕消失。"""
        node = self.mknode("a", [once_item("o")])
        self.tick(env={"AOS7_TEST_CRASH": "after-birth"}, rc=None)
        self.tock(env={"AOS7_INCOMPLETE": "tick"})
        reported = []
        for _ in range(4):
            self.tick()
            reported += self.tock()["ended"]
        self.assertEqual(self.tasks(node), [])
        self.assertEqual(self.ran(node, "o"), [])
        self.assertEqual(reported, [{"run": "o#1", "code": None, "lost": True}])

    def test_crash_after_popen(self):
        node = self.crash_then_continue("after-popen")
        self.assertEqual(len(self.ran(node, "o")), 1)

    def test_crash_before_item_delete(self):
        node = self.crash_then_continue("before-once-delete")
        self.assertEqual(len(self.ran(node, "o")), 1)

    def test_gang_crash_mid_batch(self):
        """五項 once 起到第一個就被殺（after-popen）：其他四項有標記沒 birth → 照常起；每項剛好一次（N-86）。"""
        names = ("g1", "g2", "g3", "g4", "g5")
        node = self.crash_then_continue("after-popen", names)
        for n in names:
            self.assertEqual(len(self.ran(node, n)), 1, n)

    def test_unreadable_birth_keeps_once_item(self):
        node = self.mknode("a", [once_item("o")])
        self.tick(env={"AOS7_TEST_CRASH": "before-once-delete"}, rc=None)
        self.tock(env={"AOS7_INCOMPLETE": "tick"})
        bp = os.path.join(self.slot(node, "o"), "birth.json")
        os.chmod(bp, 0)
        try:
            self.tick()
            self.assertEqual(len(self.tasks(node)), 1)        # 不知道 → 留著，下一回合再看
            self.tock()
        finally:
            os.chmod(bp, stat.S_IRUSR | stat.S_IWUSR)
        self.tick()
        self.assertEqual(self.tasks(node), [])


@unittest.skipIf(os.geteuid() == 0, "root 讀得到 chmod 000 的檔")
class TestThreeState(CoreCase):
    """〔core〕"""
    def test_round_json_unreadable_tick_tock_do_nothing(self):
        node = self.mknode("a", [{"name": "j", "argv": ["true"]}])
        self.round_trip()
        rp = os.path.join(node, ".aos", "round.json")
        before = read_json(rp)
        os.chmod(rp, 0)
        try:
            out = self.tick(rc=3)
            self.assertIn("unknown", out)
            self.tock(rc=3)
        finally:
            os.chmod(rp, stat.S_IRUSR | stat.S_IWUSR)
        self.assertEqual(read_json(rp), before)
        self.assertEqual(self.birth(node, "j")["run"], 1)   # 沒起新的

    def test_broken_round_json_is_unknown_even_with_last_round(self):
        """A2-02：round.json 壞了＝不知道上一回合關了沒，即使 last-round.json 能用也不接著數（會覆蓋還開著的同號回合）。"""
        node = self.mknode("a")
        for _ in range(3):
            self.round_trip()
        write_json(os.path.join(node, ".aos", "round.json"), ["broken"])
        self.assertIn("unknown", self.tick(rc=3))
        self.assertEqual(read_json(os.path.join(node, ".aos", "round.json")), ["broken"])
        write_json(os.path.join(node, ".aos", "round.json"), {"round": 3, "open": False})   # 人確認後寫回
        self.assertEqual(self.tick()["round"], 4)

    def test_broken_round_and_no_last_round_is_unknown(self):
        node = self.mknode("a")
        write_json(os.path.join(node, ".aos", "round.json"), "x")
        self.assertIn("unknown", self.tick(rc=3))
        self.assertEqual(read_json(os.path.join(node, ".aos", "round.json")), "x")

    def test_birth_unreadable_no_start_no_lost_no_delete(self):
        node = self.mknode("a", [{"name": "k", "mode": "keep", "argv": SLEEP}])
        self.tick()
        self.wait_pid(node, "k")
        self.tock()
        self.set_tasks(node, [])   # 名字拿掉：平常報完就刪槽；不知道時不能刪
        bp = os.path.join(self.slot(node, "k"), "birth.json")
        os.chmod(bp, 0)
        try:
            self.set_tasks(node, [{"name": "k", "mode": "keep", "argv": SLEEP}])
            out = self.tick()
            self.assertEqual(out["started"], [])
            lr = self.tock()
            self.assertEqual(lr["ended"], [])
            self.assertTrue(lr["errors"])
            self.set_tasks(node, [])
            self.tick()
            self.tock()
            self.assertTrue(os.path.isdir(self.slot(node, "k")))
            self.assertFalse(os.path.exists(os.path.join(self.slot(node, "k"), "exit.json")))
        finally:
            os.chmod(bp, stat.S_IRUSR | stat.S_IWUSR)

    def test_starttime_unreadable_counts_as_alive(self):
        """starttime 讀不到＝不知道 → 當活：不判 lost、keep 不雙開（K-05）。用同程序的 tick／tock mock 掉 starttime。"""
        node = self.mknode("a", [{"name": "k", "mode": "keep", "argv": SLEEP}])
        self.itick()
        self.wait_pid(node, "k")
        self.itock()
        with mock.patch.object(aos7_proc, "proc_starttime", lambda pid: None):
            v = self.view(node, "k", 2)
            self.assertEqual(v.state, aos7_task.LIVE)
            self.assertTrue(v.get("unsure"))
            self.assertEqual(self.itick()["started"], [])
            lr = self.itock()
        self.assertEqual(lr["alive"], ["k#1"])
        self.assertIsNone(self.exit_of(node, "k"))

    def test_pid_reused_is_gone(self):
        """starttime 對不上（pid 被重用）＝確定不在。"""
        self.assertEqual(aos7_proc.same_process(os.getpid(), aos7_fs.proc_starttime(os.getpid()) + 1), aos7_proc.GONE)
        self.assertEqual(aos7_proc.same_process(os.getpid(), None), aos7_proc.UNKNOWN)

    def test_fact_states(self):
        """單一讀檔入口 fact：不存在＝N、壞 JSON＝BAD、讀不到＝U；存在但不是一般檔（FIFO、資料夾）一律＝U（頂層定案 3）。"""
        d = self.root
        p = os.path.join(d, "x.json")
        self.assertEqual(aos7_fs.fact(p)[0], aos7_fs.N)
        with open(p, "w") as f:
            f.write("{")
        self.assertEqual(aos7_fs.fact(p)[0], aos7_fs.BAD)
        os.chmod(p, 0)
        self.assertEqual(aos7_fs.fact(p)[0], aos7_fs.U)
        os.chmod(p, 0o600)
        os.remove(p)
        os.mkfifo(p)
        self.assertEqual(aos7_fs.fact(p)[0], aos7_fs.U)
        os.remove(p)
        os.mkdir(p)
        self.assertEqual(aos7_fs.fact(p)[0], aos7_fs.U)

    def test_tasks_dir_unlistable_no_start(self):
        node = self.mknode("a", [{"name": "j", "argv": ["true"]}])
        os.makedirs(os.path.join(node, ".aos", "tasks"))
        os.chmod(os.path.join(node, ".aos", "tasks"), 0)
        try:
            self.assertIn("unknown", self.tick(rc=3))
        finally:
            os.chmod(os.path.join(node, ".aos", "tasks"), 0o700)


if __name__ == "__main__":
    unittest.main()
