"""固定回歸矩陣（六）：astra-2 第六節 A3-01～A3-09 與 P2-01 的反例（notes/play/2026-10-04-astra-2-infra.md 第二節「矩陣外組合」）。

**AOS7_TEST_* 環境變數只給測試用**（這裡用 `AOS7_TEST_CRASH=ctl-after-seen`／`tock-summary`、
`AOS7_TEST_RUNNER_CRASH=runner-before-pid`）；正常環境不設。

每一類對應的判定：

1. **A3-01** ctl.json 刪不掉（同程序 mock `os.remove` 對 ctl.json 丟 PermissionError）：restart 只執行一次，keep 換兩次 run 後
   同一份請求不再殺新 run；`ctl-after-seen` 崩潰後下一次 tock 照 ctl-seen.json 補寫回條（`replayed: true`），不再執行。
2. **A3-04** id 超過 200 字 → 回條 ok:false、不執行；200 字內前綴相同的兩個 id 各自生效。
3. **A3-05** 保留 mtime 的新 inode 複製（shutil.copy2）＝新請求；兩個槽同內容同 mtime 各自生效；`aos7-ctl task` 自動帶 id。
4. **A3-06** owner／by／node 的檔名編碼無損；daemon 起來前送兩份不同非 ASCII owner 的 pause，兩個 owner 都在 paused。
5. **A3-03** 生命週期檔（birth／pid／exit／round／last-round）被換成 FIFO＝不知道：不起第二份、tick／tock 退出碼 3、不重開同號回合；
   換回一般檔後恢復。
6. **A3-02／A3-09** 真不可 dumpable 任務（prctl PR_SET_DUMPABLE=0，同 uid 讀 environ 也 EACCES）：runner-before-pid 後不判 lost、
   不起第二份；kill 回 ok:false。測試結束用 PID（cmdline 帶著 root）自己收掉它。
7. **A3-07** 槽的 mount-req／mount-done 裡死寫者的暫存檔被 tock 清掉，活寫者的留著。
8. **A3-08** 重播（tock-summary 被殺）時通知失敗 → round.json 與回傳都有 notify_errors；之後 tick／再 tock 會補寫。
9. **P2-01** 真 daemon、early_tock:false、interval 2500ms：回合中送 wake 很快開下一回合（記事件 woke）；沒 wake 的照節拍。
"""
import os, sys  # noqa: E401
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # tests/：base、_matrix
import datetime
import json
import os
import shutil
import signal
import stat
import sys
import time
import unittest
from unittest import mock


def _kill_quiet(pid):
    """收尾保底：照 PID SIGKILL，已經不在就算了。"""
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass

from base import BIN, SLEEP, DaemonCase
from _matrix import MatrixCase, alive, dead_pid, env, gen, rec_argv
import aos7_ctl
import aos7_proc
import aos7_task
from aos7_fs import read_json, read_jsonl, write_json


def ts(s):
    return datetime.datetime.fromisoformat(s)


class A3Case(MatrixCase):
    def ctl_path(self, node, slot):
        return os.path.join(self.slot(node, slot), "ctl.json")

    def write_ctl(self, node, slot, **ctl):
        write_json(self.ctl_path(node, slot), dict({"by": "a3"}, **ctl))

    def done(self, node, slot):
        return read_json(os.path.join(self.slot(node, slot), "ctl-done.json"))

    def seen(self, node):
        return (read_json(os.path.join(node, ".aos", "ctl-seen.json"), {}) or {}).get("slots") or {}

    def once_done_round(self, node, slot):
        """起 once 的第一回合並收掉（任務很快結束）。"""
        self.itick()
        self.wait_ended(node, slot, 1)
        self.itock()

    def full_round(self, node, *slots):
        out = self.itick()
        for s in slots:
            self.settle(node, s)
        return out, self.itock()

    def ctl_recs(self, summaries, slot):
        return [c for s in summaries for c in (s.get("ctl") or []) if c.get("slot") == slot]


# ---------- A3-01 ----------

class TestCtlSeen(A3Case):
    """〔control〕ctl-seen 完成證據（A3-01，F39）：隨 restart／重播保護移出到控制包。"""
    def test_undeletable_ctl_runs_once_across_runs(self):
        """A3-01：restart 完成後 ctl.json 刪不掉，keep 跨兩次換 run：同一份請求只執行一次，之後的新 run 不被它殺。"""
        argv = ["sh", "-c", 'echo $AOS7_RUN >> "$AOS7_NODE/ran-k.txt"; if [ "$AOS7_RUN" -ge 3 ]; then exec sleep 60; fi']
        node = self.mknode("a", [{"name": "k", "mode": "keep", "argv": argv}])
        self.itick()
        self.wait_ended(node, "k", 1)
        self.itock()
        cpath = self.ctl_path(node, "k")
        self.write_ctl(node, "k", op="restart", id="one-request")
        real_remove = os.remove
        denied = []

        def deny(path, *a, **kw):
            if str(path).endswith(os.sep + os.path.join("k", "ctl.json")):   # tock 經 fd 路徑存取，只比結尾
                denied.append(path)
                raise PermissionError(13, "Permission denied (A3-01 測試)", str(path))
            return real_remove(path, *a, **kw)
        sums, pids = [], set()
        with mock.patch.object(os, "remove", deny):
            for r in range(5):
                self.itick()
                self.settle(node, "k")
                b = self.birth(node, "k")
                if b.get("run", 0) >= 3:
                    pj = self.wait_pid(node, "k")
                    pids.add(pj["pid"])
                    # 收尾保底：全套測試跑過一次留下過 run 3 的 runner＋sleep（沒能重現），這裡照 PID 明確收掉
                    for x in (pj["pid"], (b.get("runner") or {}).get("pid")):
                        if x:
                            self.addCleanup(_kill_quiet, x)
                sums.append(self.itock())
        self.assertTrue(denied, "測試時序不成立：沒有試著刪 ctl.json")
        self.assertTrue(os.path.exists(cpath), "測試時序不成立：ctl.json 被刪掉了")
        self.assertEqual(self.ran(node, "k"), ["1", "2", "3"],
                         "同一份 restart 意圖被執行了不只一次（或少了）：%r" % self.ran(node, "k"))
        recs = self.ctl_recs(sums, "k")
        real = [c for c in recs if not c.get("dup")]
        self.assertEqual(len(real), 1, "restart 真的執行了 %d 次：%r" % (len(real), recs))
        self.assertTrue(real[0]["ok"], real)
        self.assertIn("err", real[0], "ctl.json 刪不掉卻沒在紀錄留 err：%r" % real[0])
        dups = [c for c in recs if c.get("dup")]
        self.assertGreaterEqual(len(dups), 3, recs)
        self.assertEqual(len(pids), 1, "run 3 被換掉了（被舊請求殺掉重起）：%r" % pids)
        self.assertTrue(alive(pids.pop()), "run 3 不在了")
        self.assertEqual(self.birth(node, "k")["run"], 3)
        self.assertEqual(self.seen(node).get("k", {}).get("ctl_id"), "id:one-request")

    def test_refused_ctl_not_seen_can_retry(self):
        """A3-01（隊長 6ed9a7a7）：沒動手的 ok:false（run 不符）不記進 ctl-seen.json；同一個 id 改對後重送照樣執行。"""
        node = self.mknode("a", [{"name": "k", "mode": "keep", "argv": SLEEP}])
        self.itick()
        pid = self.wait_pid(node, "k")["pid"]
        self.write_ctl(node, "k", op="kill", id="same", run=7)
        self.itock()
        d = self.done(node, "k")
        self.assertIs(d["result"]["ok"], False, d)
        self.assertNotIn("k", self.seen(node), "沒動手的 ok:false 進了 ctl-seen：%r" % self.seen(node))
        self.assertTrue(alive(pid))
        self.itick()
        self.write_ctl(node, "k", op="kill", id="same")
        lr = self.itock()
        d = self.done(node, "k")
        self.assertIs(d["result"]["ok"], True, d)
        self.assertNotIn("replayed", d["result"])
        self.assertFalse([c for c in self.ctl_recs([lr], "k") if c.get("dup")], lr.get("ctl"))
        self.wait_for(lambda: not alive(pid), 5, "同 id 重送的 kill 沒執行")
        self.assertEqual(self.seen(node).get("k", {}).get("ctl_id"), "id:same")

    def test_crash_after_seen_receipt_replayed(self):
        """A3-01：記完 ctl-seen.json 就被殺（ctl-after-seen）：下一次 tock 不再執行，只照 seen 補寫回條（replayed）、刪掉 ctl.json。"""
        node = self.mknode("a", [{"name": "k", "mode": "keep", "argv": rec_argv("k", keep=True)}])
        self.itick()
        self.wait_pid(node, "k")
        self.itock()
        self.itick()
        self.write_ctl(node, "k", op="restart")
        self.crash("aos7-tock", "ctl-after-seen")
        self.assertTrue(os.path.exists(self.ctl_path(node, "k")), "測試時序不成立：ctl.json 已刪")
        self.assertIsNone(self.done(node, "k"), "測試時序不成立：回條已寫")
        cid = self.seen(node).get("k", {}).get("ctl_id")
        self.assertTrue(cid, "ctl-seen.json 沒記：%r" % self.seen(node))
        lr = self.itock()
        recs = self.ctl_recs([lr], "k")
        self.assertEqual([c.get("dup") for c in recs], [True], recs)
        d = self.done(node, "k")
        self.assertIsNotNone(d, "回條沒補寫")
        self.assertIs(d["result"].get("replayed"), True, d)
        self.assertIs(d["result"]["ok"], True, d)
        self.assertEqual(d["result"]["ctl_id"], cid)
        self.assertFalse(os.path.exists(self.ctl_path(node, "k")), "ctl.json 沒刪")
        for _ in range(2):
            self.itick()
            self.itock()
        self.wait_pid(node, "k")
        self.wait_for(lambda: len(self.ran(node, "k")) >= 2, 5, "restart 沒做：%r" % self.ran(node, "k"))
        self.wait_for(lambda: len(self.live_procs(node, "k")) == 1, 5, "恢復後槽裡不是剛好一個活程序")
        self.assertEqual(len(self.ran(node, "k")), 2, "restart 被重做：%r" % self.ran(node, "k"))
        self.assertEqual(self.birth(node, "k")["restart_of"], "k#1")


# ---------- A3-04、A3-05 ----------

class TestCtlId(A3Case):
    """〔control〕ctl_id 識別（A3-04、A3-05，F39）：隨重播保護移出到控制包；CLI 自動 id 屬工具包。"""
    def test_too_long_id_refused(self):
        """A3-04：id 超過 200 字 → 回條 ok:false 說 id 太長，不執行（不截斷）。"""
        node = self.mknode("a", [{"name": "o", "mode": "once", "argv": rec_argv("o")}])
        self.once_done_round(node, "o")
        self.write_ctl(node, "o", op="restart", id="x" * 201)
        self.itick()
        d = self.done(node, "o")   # 先看回條：tock 會把不在表上、已報過的 once 槽連同回條刪掉
        self.assertIs(d["result"]["ok"], False, d)
        self.assertIn("太長", d["result"]["msg"])
        self.assertFalse(os.path.exists(self.ctl_path(node, "o")))
        self.settle(node, "o")
        self.itock()
        self.assertEqual(len(self.ran(node, "o")), 1, "id 太長的請求被執行了")
        self.assertEqual(self.tasks(node), [])

    def test_same_prefix_ids_distinct(self):
        """A3-04：兩個前 199 字相同、總長 200 的不同 id 各自生效（以前截 64 字會變成同一件）。"""
        node = self.mknode("a", [{"name": "o", "mode": "once", "argv": rec_argv("o")}])
        self.once_done_round(node, "o")
        for last in "01":
            self.write_ctl(node, "o", op="restart", id="x" * 199 + last)
            self.full_round(node, "o")
            d = self.done(node, "o")
            self.assertIs(d["result"]["ok"], True, d)
            self.assertNotIn("重播", d["result"]["msg"])
        self.assertEqual(len(self.ran(node, "o")), 3, "前綴相同的不同 id 被當同一件：%r" % self.ran(node, "o"))

    def test_copy_with_same_mtime_new_inode_is_new(self):
        """A3-05：同內容、保留 mtime（shutil.copy2）的新 inode 複製是新請求，兩次都生效。"""
        node = self.mknode("a", [{"name": "o", "mode": "once", "argv": rec_argv("o")}])
        self.once_done_round(node, "o")
        tmpl = os.path.join(node, "tmpl.json")
        write_json(tmpl, {"op": "restart", "by": "a3"})
        cpath = self.ctl_path(node, "o")
        stats = []
        for k in range(2):
            shutil.copy2(tmpl, cpath)
            st = os.stat(cpath)
            stats.append((st.st_ino, st.st_mtime_ns))
            os.link(cpath, os.path.join(node, "hold-%d" % k))   # 抓住 inode，下一份複製一定是新 inode
            self.full_round(node, "o")
            d = self.done(node, "o")
            self.assertIs(d["result"]["ok"], True, d)
        self.assertNotEqual(stats[0][0], stats[1][0], "測試前提不成立：inode 一樣")
        self.assertEqual(stats[0][1], stats[1][1], "測試前提不成立：mtime 不一樣")
        self.assertEqual(len(self.ran(node, "o")), 3, "保留 mtime 的新請求被當重播：%r" % self.ran(node, "o"))

    def test_two_slots_same_content_mtime(self):
        """A3-05：兩個槽同內容、同 mtime 的 restart 各自生效（作用域是槽，pending 查重比同槽＋同 ctl_id）。"""
        node = self.mknode("a", [{"name": n, "mode": "once", "argv": rec_argv(n)} for n in ("o", "p")])
        self.itick()
        for n in ("o", "p"):
            self.wait_ended(node, n, 1)
        self.itock()
        tmpl = os.path.join(node, "tmpl.json")
        write_json(tmpl, {"op": "restart", "by": "a3"})
        for n in ("o", "p"):
            shutil.copy2(tmpl, self.ctl_path(node, n))
        self.assertEqual(os.stat(self.ctl_path(node, "o")).st_mtime_ns, os.stat(self.ctl_path(node, "p")).st_mtime_ns)
        self.full_round(node, "o", "p")
        for n in ("o", "p"):
            d = self.done(node, n)
            self.assertIs(d["result"]["ok"], True, d)
            self.assertNotIn("上次已加過", d["result"]["msg"], d)
            self.assertEqual(len(self.ran(node, n)), 2, "槽 %s 的 restart 沒生效：%r" % (n, self.ran(node, n)))

    def test_cli_task_auto_id(self):
        """A3-05：`aos7-ctl task` 每次自動帶新的 id，兩次 restart 都生效；`--id` 超過 200 字被拒（A3-04）。"""
        node = self.mknode("a", [{"name": "o", "mode": "once", "argv": rec_argv("o")}])
        self.once_done_round(node, "o")
        ids = []
        for _ in range(2):
            self.prog("aos7-ctl", "task", self.slot(node, "o"), "restart")
            ids.append(read_json(self.ctl_path(node, "o"))["id"])
            self.full_round(node, "o")
        self.assertTrue(all(isinstance(i, str) and i for i in ids), ids)
        self.assertNotEqual(ids[0], ids[1])
        self.assertEqual(len(self.ran(node, "o")), 3, self.ran(node, "o"))
        self.prog("aos7-ctl", "task", self.slot(node, "o"), "restart", "--id", "y" * 201, rc=1)
        self.assertFalse(os.path.exists(self.ctl_path(node, "o")), "--id 太長還是寫了 ctl.json")
        self.prog("aos7-ctl", "task", self.slot(node, "o"), "restart", "--id", "y" * 200)
        self.assertEqual(read_json(self.ctl_path(node, "o"))["id"], "y" * 200)


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

def to_fifo(path):
    """把 path 換成 FIFO，回原本的內容（bytes）。"""
    with open(path, "rb") as f:
        raw = f.read()
    os.unlink(path)
    os.mkfifo(path)
    return raw


def back_to_file(path, raw):
    os.unlink(path)
    with open(path, "wb") as f:
        f.write(raw)


class TestNonRegular(A3Case):
    """〔core〕"""
    def _slot_file(self, name):
        """槽的生命週期檔 name 被換成 FIFO＝不知道：槽 UNKNOWN、tick 不起第二份、tock errors 有它；換回一般檔後恢復。"""
        if name == "exit.json":
            node = self.mknode("a", [{"name": "k", "argv": rec_argv("k")}])   # each：跑完的槽才有 exit.json
            self.itick()
            self.wait_ended(node, "k", 1)
            self.itock()
        else:
            node = self.mknode("a", [{"name": "k", "mode": "keep", "argv": rec_argv("k", keep=True)}])
            self.itick()
            pid = self.wait_pid(node, "k")["pid"]
            self.itock()
        path = os.path.join(self.slot(node, "k"), name)
        raw = to_fifo(path)
        self.assertEqual(self.view(node, "k", 2).state, aos7_task.UNKNOWN, dict(self.view(node, "k", 2)))
        rc, out, err = self.run_prog("aos7-tick")
        self.assertEqual(rc, 0, err)
        self.assertEqual(out["started"], [], "%s 是 FIFO 時起了新的 run：%r" % (name, out))
        self.assertTrue(stat.S_ISFIFO(os.lstat(path).st_mode), "FIFO 被覆蓋了")
        rc, lr, err = self.run_prog("aos7-tock")
        self.assertEqual(rc, 0, err)
        self.assertTrue(self.errors_for(lr, "k"), "tock errors 沒有槽 k：%r" % lr.get("errors"))
        self.assertEqual(len(self.ran(node, "k")), 1, self.ran(node, "k"))
        if name != "exit.json":
            self.assertTrue(alive(pid))
            self.assert_le_one(node, "k", "FIFO 期間")
        back_to_file(path, raw)
        out = self.itick()
        if name == "exit.json":
            self.assertEqual(out["started"], ["k#3"], "換回一般檔後沒恢復：%r" % out)
        else:
            self.assertEqual(out["started"], [])
            self.assertEqual(self.view(node, "k").state, aos7_task.LIVE)
            self.assertEqual(self.wait_pid(node, "k")["pid"], pid)
        lr = self.itock()
        self.assertFalse(self.errors_for(lr, "k"), lr.get("errors"))

    def test_open_round_fifo(self):
        """A3-03：開著的 round.json 換成 FIFO → tick／tock 退出碼 3、不從 last-round 接號重開同號回合；換回後照常收、開下一回合。"""
        node = self.mknode("a")
        self.itick()
        self.itock()
        self.itick()
        rpath = os.path.join(node, ".aos", "round.json")
        raw = to_fifo(rpath)
        for prog in ("aos7-tick", "aos7-tock"):
            rc, out, err = self.run_prog(prog)
            self.assertEqual(rc, 3, "%s 遇到 FIFO 的 round.json 退出碼 %r：%r %s" % (prog, rc, out, err))
            self.assertTrue(stat.S_ISFIFO(os.lstat(rpath).st_mode), "%s 覆蓋了 FIFO 的 round.json" % prog)
        self.assertEqual(self.last_round(node).get("round"), 1)
        back_to_file(rpath, raw)
        self.assertEqual(self.itock()["round"], 2)
        self.assertEqual(self.itick()["round"], 3)

    def test_last_round_fifo(self):
        """A3-03：last-round.json 換成 FIFO → tock 退出碼 3、回合不關；round.json 不在時 tick 也退出碼 3（不從 1 重數）；換回後恢復。"""
        node = self.mknode("a")
        self.itick()
        self.itock()
        self.itick()
        lpath = os.path.join(node, ".aos", "last-round.json")
        raw = to_fifo(lpath)
        rc, out, err = self.run_prog("aos7-tock")
        self.assertEqual(rc, 3, "%r %s" % (out, err))
        self.assertIs(self.round_json(node).get("open"), True, "last-round.json 讀不出來還關了回合")
        back_to_file(lpath, raw)
        self.assertEqual(self.itock()["round"], 2)
        rpath = os.path.join(node, ".aos", "round.json")
        os.unlink(rpath)
        raw = to_fifo(lpath)
        rc, out, err = self.run_prog("aos7-tick")
        self.assertEqual(rc, 3, "round.json 不在、last-round.json 是 FIFO，tick 還是開了：%r %s" % (out, err))
        self.assertFalse(os.path.exists(rpath))
        back_to_file(lpath, raw)
        self.assertEqual(self.itick()["round"], 3)


gen(TestNonRegular, "slot_fifo", [(n, (n,)) for n in ("birth.json", "pid.json", "exit.json")], TestNonRegular._slot_file)


# ---------- A3-02、A3-09 ----------

HIDDEN = ("import ctypes, os, time\n"
          "assert ctypes.CDLL(None).prctl(4, 0, 0, 0, 0) == 0\n"
          "open(os.environ['AOS7_NODE'] + '/pid-' + os.environ['AOS7_RUN'], 'w').write(str(os.getpid()))\n"
          "time.sleep(60)\n"
          "# %s\n")


def environ_hidden_supported():
    """同 uid 讀不可 dumpable 程序的 /proc/<pid>/environ 會不會 EACCES（A3-02 要的前提）。回 (bool, 說明)。"""
    import subprocess
    try:
        p = subprocess.Popen([sys.executable, "-c", "import ctypes,sys,time\n"
                              "ok = ctypes.CDLL(None).prctl(4, 0, 0, 0, 0) == 0\n"
                              "print(ok, flush=True); time.sleep(5)"], stdout=subprocess.PIPE, text=True)
    except OSError as e:
        return False, "起不了 python：%r" % (e,)
    try:
        if p.stdout.readline().strip() != "True":
            return False, "prctl(PR_SET_DUMPABLE, 0) 失敗"
        try:
            with open("/proc/%d/environ" % p.pid, "rb") as f:
                f.read()
            return False, "同 uid 讀得到不可 dumpable 程序的 environ（例如以 root 跑或核心設定不同），重現不了 EACCES"
        except PermissionError:
            return True, ""
        except OSError as e:
            return False, "讀 environ 得到 %r，不是 EACCES" % (e,)
    finally:
        p.kill()
        p.wait()
        p.stdout.close()


class TestHiddenEnviron(A3Case):
    """〔misuse M-2.8〕不可 dumpable／environ 讀不到權限的任務在已知 session／群組裡＝不知道（A3-02，F33）：任務違反前置「同 uid、environ 可讀」。"""
    def setUp(self):
        super().setUp()
        ok, why = environ_hidden_supported()
        if not ok:
            self.skipTest("這個環境做不出 environ EACCES：%s" % why)
        self.addCleanup(self.kill_hidden)

    def kill_hidden(self):
        """收掉 cmdline 帶著這個測試 root 的程序（不可 dumpable 的任務 environ 讀不到，base 的保底掃不到它）。"""
        mark = self.root.encode()
        for _ in range(3):
            left = []
            for p in os.listdir("/proc"):
                if not p.isdigit() or int(p) == os.getpid():
                    continue
                try:
                    with open("/proc/%s/cmdline" % p, "rb") as f:
                        cmd = f.read()
                except OSError:
                    continue
                if mark in cmd:
                    left.append(int(p))
                    try:
                        os.kill(int(p), signal.SIGKILL)
                    except OSError:
                        pass
            if not left:
                return
            time.sleep(0.05)

    def hidden_node(self):
        return self.mknode("a", [{"name": "k", "mode": "keep", "argv": [sys.executable, "-c", HIDDEN % self.root]}])

    def hidden_pid(self, node, run):
        p = os.path.join(node, "pid-%d" % run)

        def get():
            try:
                with open(p) as f:
                    v = f.read().strip()
                return int(v) if v else None
            except OSError:
                return None
        return self.wait_for(get, 10, "不可 dumpable 的任務沒起來")

    def test_runner_dead_before_pid_not_lost(self):
        """A3-02：不可 dumpable 任務、runner 在寫 pid.json 前死：tock 不判 lost、tick 不起第二份；kill 回 ok:false（A3-09）、任務還活著。"""
        node = self.hidden_node()
        rc, _out, err = self.run_prog("aos7-tick", env={"AOS7_TEST_RUNNER_CRASH": "runner-before-pid"})
        self.assertEqual(rc, 0, err)
        pid = self.hidden_pid(node, 1)
        runner = (self.birth(node, "k").get("runner") or {}).get("pid")
        self.assertTrue(runner, self.birth(node, "k"))
        self.wait_for(lambda: not alive(runner), 5, "runner 沒死")
        self.assertIsNone(read_json(os.path.join(self.slot(node, "k"), "pid.json")), "測試時序不成立：有 pid.json")
        with self.assertRaises(PermissionError):
            open("/proc/%d/environ" % pid, "rb").read()
        sums = [self.itock()]
        for _ in range(2):
            out = self.itick()
            self.assertEqual(out["started"], [], "不可讀身分的任務還活著就起了第二份：%r" % out)
            sums.append(self.itock())
        self.assertEqual(self.ends_of(sums, "k"), [], "判了 lost：%r" % self.ends_of(sums, "k"))
        self.assertIsNone(self.exit_raw(node, "k"), "寫了 exit.json：%r" % self.exit_raw(node, "k"))
        self.assertTrue(all(self.errors_for(s, "k") for s in sums), "沒在 errors 說明不知道：%r" % [s.get("errors") for s in sums])
        self.assertFalse(os.path.exists(os.path.join(node, "pid-2")), "起了第二份")
        self.assertEqual(self.birth(node, "k")["run"], 1)
        self.assertTrue(alive(pid))
        # A3-09：送 kill——判不出來，不能回成功
        self.write_ctl(node, "k", op="kill")
        lr = self.itock() if self.round_json(node).get("open") else (self.itick(), self.itock())[1]
        recs = self.ctl_recs([lr], "k")
        self.assertTrue(recs, lr.get("ctl"))
        self.assertTrue(all(c.get("ok") is False for c in recs), "kill 回了成功：%r" % recs)
        d = self.done(node, "k")
        self.assertTrue(d is None or d["result"]["ok"] is False, "回條說成功：%r" % d)
        self.assertTrue(alive(pid), "測試時序不成立：任務被收掉了")
        os.kill(pid, signal.SIGKILL)
        self.wait_for(lambda: not alive(pid), 5, "任務收不掉")

    def test_kill_live_hidden_task_not_ok(self):
        """A3-09：pid.json 記著的不可 dumpable 任務、runner 已死，送 kill：任務仍活 → 回條 ok:false（unknown），不說收乾淨。"""
        node = self.hidden_node()
        self.itick()
        pid = self.hidden_pid(node, 1)
        pj = self.wait_pid(node, "k")
        self.assertEqual(pj["pid"], pid)
        runner = (self.birth(node, "k").get("runner") or {}).get("pid")
        os.kill(runner, signal.SIGKILL)
        self.wait_for(lambda: not alive(runner), 5, "runner 沒死")
        self.itock()
        self.itick()
        self.write_ctl(node, "k", op="kill")
        lr = self.itock()
        d = self.done(node, "k")
        self.assertIsNotNone(d, "沒有回條：%r" % lr.get("ctl"))
        self.assertIs(d["result"]["ok"], False, "任務還活著，kill 卻回成功：%r" % d)
        self.assertIn("unknown", d["result"]["msg"])
        self.assertTrue(alive(pid))
        self.assertIn("k#1", lr["alive"])
        os.kill(pid, signal.SIGKILL)
        self.wait_for(lambda: not alive(pid), 5, "任務收不掉")


# ---------- A3-07 ----------

class TestMountTmpSweep(A3Case):
    """〔core〕"""
    def test_mount_dirs_dead_tmp_swept(self):
        """A3-07：槽的 mount-req／mount-done 裡寫者已死的 `.<名>.tmp.<pid>` 被 tock 清掉，活寫者的不動。"""
        node = self.mknode("a", [{"name": "k", "mode": "keep", "argv": SLEEP}])
        self.itick()
        self.wait_pid(node, "k")
        self.itock()
        dead = dead_pid()
        files = {}
        for sub in ("mount-req", "mount-done"):
            d = os.path.join(self.slot(node, "k"), sub)
            os.makedirs(d, exist_ok=True)
            files[os.path.join(d, ".x.json.tmp.%d" % dead)] = False
            files[os.path.join(d, ".y.json.tmp.%d" % os.getpid())] = True
        for p in files:
            with open(p, "w") as f:
                f.write("{")
        self.itick()
        self.itock()
        for p, keep in files.items():
            self.assertEqual(os.path.exists(p), keep, "%s：%s" % ("活寫者的暫存被刪了" if keep else "死寫者的暫存沒清", p))


# ---------- A3-08 ----------

class TestReplayNotify(A3Case):
    """〔core〕"""
    def replay_with_blocked_tock(self):
        """keep 任務活著，第 1 回合 tock 寫完總結就被殺，再把 tock.json 佔成資料夾，重播 tock。回 (node, 重播結果)。"""
        node = self.mknode("a", [{"name": "k", "mode": "keep", "argv": SLEEP}])
        self.itick()
        self.wait_pid(node, "k")
        self.crash("aos7-tock", "tock-summary")
        tp = os.path.join(self.slot(node, "k"), "tock.json")
        self.assertFalse(os.path.exists(tp), "測試時序不成立：tock.json 已寫")
        os.mkdir(tp)
        out = self.itock()
        self.assertIs(out.get("replayed"), True, out)
        return node, out

    def assert_owed(self, errs, rnd=1):
        self.assertTrue(errs, "沒有 notify_errors")
        self.assertEqual([(e["slot"], e["run"], e["round"]) for e in errs], [("k", 1, rnd)], errs)
        self.assertTrue(all(e.get("err") for e in errs), errs)

    def test_replay_notify_error_then_tick_retries(self):
        """A3-08：重播時 tock.json 寫不進去 → round.json 與回傳都有 notify_errors；恢復後下一個 tick 補寫上一回合的 tock.json。"""
        node, out = self.replay_with_blocked_tock()
        self.assert_owed(out.get("notify_errors"))
        rj = self.round_json(node)
        self.assertIs(rj["open"], False)
        self.assert_owed(rj.get("notify_errors"))
        tp = os.path.join(self.slot(node, "k"), "tock.json")
        os.rmdir(tp)
        r = self.itick()
        self.assertEqual(r["round"], 2)
        t = read_json(tp)
        self.assertEqual((t or {}).get("round"), 1, "沒補寫第 1 回合的 tock.json：%r" % t)
        self.assertEqual(t["run"], 1)
        self.assertFalse(self.round_json(node).get("tasks_error"), self.round_json(node).get("tasks_error"))

    def test_replay_notify_still_failing_goes_to_tasks_error(self):
        """A3-08：補寫時 tock.json 還寫不進去 → 新回合的 tasks_error 記著欠的通知。"""
        node, _out = self.replay_with_blocked_tock()
        self.itick()
        errs = self.round_json(node).get("tasks_error") or []
        self.assertTrue([e for e in errs if "tock.json" in e and "1" in e], "補不上的通知沒進 tasks_error：%r" % errs)

    def test_closed_round_tock_retries(self):
        """A3-08：對已關的回合再跑 tock：還寫不進去 → notify_retried＋留著；恢復後再跑 → 補寫、notify_errors 清掉。"""
        node, _out = self.replay_with_blocked_tock()
        r = self.itock()
        self.assertIs(r.get("notify_retried"), True, r)
        self.assert_owed(r.get("notify_errors"))
        self.assert_owed(self.round_json(node).get("notify_errors"))
        tp = os.path.join(self.slot(node, "k"), "tock.json")
        os.rmdir(tp)
        r = self.itock()
        self.assertIs(r.get("notify_retried"), True, r)
        self.assertEqual(r.get("notify_errors"), [], r)
        self.assertNotIn("notify_errors", self.round_json(node))
        self.assertEqual((read_json(tp) or {}).get("round"), 1)

    def test_replay_unjudgeable_slot_recorded(self):
        """A3-08：重播時槽判不出（birth.json 換成 FIFO）→ notify_errors 記著（phase judge），不默默關回合。"""
        node = self.mknode("a", [{"name": "k", "mode": "keep", "argv": SLEEP}])
        self.itick()
        self.wait_pid(node, "k")
        self.crash("aos7-tock", "tock-summary")
        bpath = os.path.join(self.slot(node, "k"), "birth.json")
        raw = to_fifo(bpath)
        out = self.itock()
        self.assertIs(out.get("replayed"), True, out)
        self.assert_owed(out.get("notify_errors"))
        self.assertEqual(out["notify_errors"][0].get("phase"), "judge")
        back_to_file(bpath, raw)
        self.itick()
        self.assertEqual((read_json(os.path.join(self.slot(node, "k"), "tock.json")) or {}).get("round"), 1)


# ---------- P2-01 ----------

class TestWakeFixedInterval(DaemonCase):
    """〔core〕"""
    INTERVAL = 2500

    def setup_node(self):
        node = self.mknode("a", interval_ms=self.INTERVAL, early=False)
        os.makedirs(os.path.join(self.root, ".aosd"), exist_ok=True)
        open(os.path.join(self.root, ".aosd", "log.on"), "w").close()
        self.start_daemon(register=["a"])
        self.wait_for(lambda: self.round_json(node).get("round") == 1 and self.round_json(node).get("open") is True, 10,
                      "第 1 回合沒開")
        return node

    def test_wake_mid_round_starts_next_soon(self):
        """P2-01：early_tock:false 的 node 回合中送 wake → 馬上 tock（early）、下一回合遠早於 interval 開始，記事件 woke。"""
        node = self.setup_node()
        t1 = ts(self.round_json(node)["tick_at"])
        self.ctl("wake", "a")
        self.wait_for(lambda: self.round_json(node).get("round") == 2, 5, "wake 後沒開第 2 回合")
        gap = (ts(self.round_json(node)["tick_at"]) - t1).total_seconds()
        self.assertLess(gap, 1.5, "回合中 wake 沒提前結束回合（間隔 %.3f 秒，interval %.1f 秒）" % (gap, self.INTERVAL / 1000))
        self.assertIs(self.last_round(node).get("early"), True, self.last_round(node))
        rows = read_jsonl(os.path.join(self.root, ".aosd", "log.jsonl"))
        self.assertTrue([e for e in rows if e.get("ev") == "woke" and e.get("node") == "a" and e.get("round") == 1],
                        "沒記事件 woke：%r" % rows[-10:])

    def test_no_wake_keeps_interval(self):
        """P2-01 對照組：沒送 wake 的回合照 interval 節拍（第 2 回合不早於第 1 回合 tick 後約 interval）。"""
        node = self.setup_node()
        t1 = ts(self.round_json(node)["tick_at"])
        self.wait_for(lambda: self.round_json(node).get("round") == 2, 8, "沒開第 2 回合")
        gap = (ts(self.round_json(node)["tick_at"]) - t1).total_seconds()
        self.assertGreaterEqual(gap, self.INTERVAL / 1000 - 0.2, "沒 wake 也提早開了下一回合（%.3f 秒）" % gap)
        self.assertIs(self.last_round(node).get("early"), False, self.last_round(node))
        rows = read_jsonl(os.path.join(self.root, ".aosd", "log.jsonl"))
        self.assertFalse([e for e in rows if e.get("ev") == "woke"], rows)


if __name__ == "__main__":
    unittest.main()
