"""aos-daemon 的 key 與查：key＝那份 inst.json 的 realpath（§15）、只收 `.json`、
`ls`／`get` 的欄位、近況是讀 status-fd 來的。

直接叫 `Daemon` 的方法，不開 daemon 進程——主迴圈那一圈（`tick()`）測試自己來。基底與
三份 inst.json 的內容在 `_daemon.py`，其餘動作在 `test_daemon_ops.py`。
（`_util.py` 的坑：TestCase 裡別放叫 `run()` 的方法，那是 unittest 自己的。）
"""
import os
import unittest

from _daemon import FAST, MS100, MS300, SLOW, DaemonTest


class DaemonKeyTest(DaemonTest):

    def test_key_is_the_json_realpath_and_second_add_is_refused(self):
        """key＝那份 .json 的 realpath：symlink／`..`／相對路徑都算同一筆。"""
        w = self.work(SLOW)
        link = os.path.join(self.d, "link.json")
        os.symlink(w, link)
        ok, res = self.dmn.add(link, MS100)
        self.assertTrue(ok)
        self.assertEqual(list(self.dmn.table), [os.path.realpath(w)])
        self.assertEqual(res["target"], link)                    # target 留原樣，key 才 realpath

        for other in (os.path.join(self.d, "work", "..", "work", "inst.json"), link, w):
            ok2, res2 = self.dmn.add(other, MS100)               # 同一份 .json＝第二次拒絕
            self.assertFalse(ok2, other)
            self.assertIn("已經有一個在跑", res2)
        self.assertEqual(len(self.dmn.table), 1)
        self.assertEqual(self.entry(w).proc.pid, res["pid"])      # 舊的不動

    def test_two_jsons_in_one_folder_are_two_rows(self):
        """同一個資料夾掛兩份不同的 inst.json＝兩筆，各一支 aos-run。"""
        a = self.work(SLOW, "work/a.json")
        b = self.work(SLOW, "work/b.json")
        self.assertTrue(self.dmn.add(a, MS100)[0])
        self.assertTrue(self.dmn.add(b, MS100)[0])
        self.assertEqual(sorted(self.dmn.table),
                         sorted([os.path.realpath(a), os.path.realpath(b)]))
        self.assertNotEqual(self.entry(a).proc.pid, self.entry(b).proc.pid)

    def test_add_a_folder_is_refused(self):
        self.work(FAST, "work/inst.json")
        for d in (os.path.join(self.d, "work"), self.d):
            ok, res = self.dmn.add(d, MS100)
            self.assertFalse(ok, d)
            self.assertIn("只收 .json", res)
        os.makedirs(os.path.join(self.d, "trap.json"))          # 叫 .json 的資料夾也是資料夾
        ok, res = self.dmn.add(os.path.join(self.d, "trap.json"), MS100)
        self.assertEqual((ok, "資料夾" in res), (False, True), res)
        self.assertEqual(self.dmn.table, {})

    def test_add_a_plain_file_is_refused(self):
        p = self.write("hello.sh", "#!/bin/sh\necho hi\n", executable=True)
        ok, res = self.dmn.add(p, MS100)
        self.assertEqual((ok, "只收 .json" in res), (False, True), res)
        self.assertEqual(self.dmn.table, {})

    def test_add_a_json_that_is_not_there_yet(self):
        """檔案不存在照收：每次跑回 125（kind=aos），檔案出現了就跑起來。"""
        p = os.path.join(self.d, "later", "inst.json")
        os.makedirs(os.path.dirname(p))
        ok, res = self.dmn.add(p, MS100)
        self.assertTrue(ok, res)
        r = self.entry(p)
        self.assertTrue(self.pump(lambda: r.runs >= 2))
        self.assertEqual((r.last_exit, r.last_kind), (125, "aos"))
        self.inst(FAST, os.path.join("later", "inst.json"))     # 檔案出現了
        self.assertTrue(self.pump(lambda: r.last_kind == "child"))
        self.assertEqual(r.last_exit, 3)                        # FAST＝exit 3

    # ── 查 ─────────────────────────────────────────────
    def test_ls_and_get_fields(self):
        w = self.work(SLOW)
        self.dmn.add(w, MS100)
        key = os.path.realpath(w)
        ok, one = self.dmn.get(w)
        self.assertTrue(ok)
        self.assertEqual(sorted(one), ["alive", "args", "last_exit", "last_kind",
                                       "last_line", "pid", "ready", "running", "runs",
                                       "started_at", "state", "target"])
        self.assertEqual((one["args"], one["state"], one["alive"]), (MS100, "running", True))
        self.assertTrue(one["started_at"] > 0)
        ok, table = self.dmn.ls()                       # ls＝全部的 get，key 是那份 .json
        self.assertTrue(ok)
        self.assertEqual(list(table), [key])
        self.assertEqual(table[key]["pid"], one["pid"])
        self.assertEqual(self.dmn.get(os.path.join(self.d, "nope"))[0], False)

    def test_ready_shows_up_quickly(self):
        """aos-run 裝好訊號處理器就會說 `ready`——pause 等的就是這個。"""
        w = self.work(FAST)
        self.dmn.add(w, MS300)
        r = self.entry(w)
        self.assertTrue(self.pump(lambda: r.ready, 5.0))

    def test_status_fd_gives_runs_and_last_exit_and_kind(self):
        w = self.work(FAST)                                 # 每次都 exit 3、100 ms 一次
        self.dmn.add(w, MS100)
        r = self.entry(w)
        self.assertTrue(self.pump(lambda: r.runs >= 2))
        self.assertEqual((r.last_exit, r.last_kind), (3, "child"))
        self.assertRegex(r.last_line, r"^done #\d+ exit=3 kind=child ")
        self.assertFalse(r.running)                         # done 之後就是在睡覺
        # stderr 照舊原樣進 daemon.log（前面加 key），只是不再從那裡解近況
        self.assertIn("%s aos-run: #1 exit=3" % os.path.realpath(w), self.log())


if __name__ == "__main__":
    unittest.main()
