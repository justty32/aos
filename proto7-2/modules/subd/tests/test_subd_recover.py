"""〔subd〕重開前回收（A5-01）：父 kill 只給 1 秒寬限，子 daemon 收不完忽略 SIGTERM 的任務；下一個 aos7-subd 起 argv 前
自己收前代（launcher、runner、任務），確定乾淨才起新代。起 argv 前／回收中／回收完未起新代時被殺都能接續；paused node 也收；
不知道就不起；不碰 sibling 子根與新代；被允許的 stop 之後不回收——提交（stopped.json、生命週期）中途被殺也一樣（A6-01）。

兩種起法：經父 daemon（真的父 kill，同 astra-4 壓力探針的負載）；或測試直接當任務起 aos7-subd（才能帶 AOS7_TEST_CRASH／FAULT：
經 tick 起的任務環境會拿掉 AOS7_TEST_*），「父 kill」照核心 kill 的樣子打它的群組：SIGTERM、等 1 秒、SIGKILL。"""
import os
import signal
import subprocess
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tests"))  # tests/：base

import unittest  # noqa: E402

import _proc  # noqa: E402
from base import BIN, MODULES, DaemonCase  # noqa: E402
import aos7_proc  # noqa: E402
from aos7_fs import read_json, write_json  # noqa: E402

SUBD = os.path.join(MODULES, "subd", "aos7-subd")
BOOT = ["sh", "-c", 'aos7-ctl daemon "$AOS7_SUBROOT" register n1 --by boot > /dev/null && exec aos7-daemon "$AOS7_SUBROOT"']
# 忽略 SIGTERM、保留身分的任務（astra-4 G3 的負載）：起來寫 ready.json
IGNORE = ("import json, os, signal, time\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
          "t = os.environ['AOS7_TASK']\nwith open(os.path.join(t, '.ready.tmp'), 'w') as f:\n"
          "    json.dump({'pid': os.getpid(), 'run': int(os.environ['AOS7_RUN'])}, f)\n"
          "os.replace(os.path.join(t, '.ready.tmp'), os.path.join(t, 'ready.json'))\n"
          "while True:\n    time.sleep(0.05)\n")
N_TASKS = 3


class RecoverCase(DaemonCase):
    def child_space(self, sub="a/sub", n=N_TASKS):
        """子根 sub 底下的 n1：n 個忽略 SIGTERM 的 keep 任務。回 (子根, n1)。"""
        os.makedirs(os.path.join(self.root, "a", ".aos"), exist_ok=True)
        worker = os.path.join(self.root, "ignore_term.py")
        with open(worker, "w") as f:
            f.write(IGNORE)
        n1 = self.mknode(sub + "/n1", [{"name": "s%d" % i, "mode": "keep", "argv": [sys.executable, worker]}
                                       for i in range(n)], interval_ms=100)
        return os.path.join(self.root, sub), n1

    def ready_pids(self, n1, n=N_TASKS, timeout=20, not_in=()):
        """n 個任務都起好（ready.json 是現在這個 run 的、pid 不在 not_in：ready.json 是任務自己的檔，換 run 不清）→ pid。"""
        def ok():
            rs = [read_json(os.path.join(self.slot(n1, "s%d" % i), "ready.json")) for i in range(n)]
            bs = [self.birth(n1, "s%d" % i) for i in range(n)]
            if all(isinstance(r, dict) and r.get("run") == b.get("run") and r.get("pid") not in not_in
                   for r, b in zip(rs, bs)):
                return [r["pid"] for r in rs]
            return None
        return self.wait_for(ok, timeout, "子任務沒起好")

    def life(self, sub):
        return read_json(os.path.join(sub, ".aosd", "subd-life.json"))

    # ---------- 直接起 aos7-subd（當作父 node a 的任務 sub） ----------

    def run_subd(self, sub_id="a/sub", run=1, env=None, allow_stop=False):
        """像 tick 起任務那樣起 aos7-subd（PATH 前面加 bin/、帶任務身分）；stderr 進 root 底下的檔（err(p) 讀）。"""
        e = dict(os.environ, AOS7_ROOT=self.root, AOS7_NODE=os.path.join(self.root, "a"), AOS7_NODE_ID="a",
                 AOS7_TID=sub_id.rsplit("/", 1)[1], AOS7_RUN=str(run), PATH=BIN + os.pathsep + os.environ.get("PATH", ""),
                 **(env or {}))
        log = os.path.join(self.root, "subd-%s-%d.err" % (sub_id.replace("/", "_"), run))
        with open(log, "w") as f:
            p = subprocess.Popen([sys.executable, SUBD, sub_id] + (["--allow-stop"] if allow_stop else []) + ["--"] + BOOT,
                                 env=e, stdout=subprocess.DEVNULL, stderr=f, start_new_session=True)
        p.log = log
        self.procs.append(p)
        _proc.track(self, p, grace=6, group=True)
        return p

    def err(self, p):
        with open(p.log, encoding="utf-8") as f:
            return f.read()

    def parent_kill(self, p):
        """照核心 kill 打 p 的群組：SIGTERM、最多等 1 秒、SIGKILL（aos7_proc.kill_groups 的寬限）。"""
        os.killpg(p.pid, signal.SIGTERM)
        try:
            p.wait(aos7_proc.KILL_GRACE)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        p.wait(5)

    def leftover_gen(self, sub_id="a/sub"):
        """起第一代、等任務起好、父 kill：回 (子根, n1, 原任務 pid, 第一代子 daemon pid)；確認原任務真的留下來了（A5-01 前提）。"""
        sub, n1 = self.child_space(sub_id)
        p = self.run_subd(sub_id, run=1)
        old = self.ready_pids(n1)
        daemon = self.wait_for(lambda: self.status(sub).get("pid"), 10, "子 daemon 沒起")
        self.parent_kill(p)
        self.wait_for(lambda: not aos7_proc.pid_alive(daemon), 5, "第一代子 daemon 沒死")
        self.assertTrue(all(aos7_proc.pid_alive(x) for x in old), "前提不成立：父 kill 後原任務已經沒了")
        return sub, n1, old, daemon

    def new_daemon(self, sub, old_daemon, timeout=20):
        return self.wait_for(lambda: (lambda d: d if d and d != old_daemon and aos7_proc.pid_alive(d) else None)(
            self.status(sub).get("pid")), timeout, "新代子 daemon 沒起")

    def stopped_by_ctl(self, run=1, env=None):
        """起包（--allow-stop）、等任務起好、控制檔 stop（不帶 kill）：回 (子根, n1, 任務 pid, starttime, 子 daemon pid, 包)。"""
        sub, n1 = self.child_space(n=1)
        p = self.run_subd(run=run, allow_stop=True, env=env)
        pid = self.ready_pids(n1, n=1)[0]
        start = aos7_proc.proc(pid)[1]
        daemon = self.wait_for(lambda: self.status(sub).get("pid"), 10, "子 daemon 沒起")
        self.assertTrue(self.wait_receipt(self.ctl("stop", root=sub))["result"]["ok"])
        return sub, n1, pid, start, daemon, p

    def same(self, pid, start):
        return aos7_proc.same_process(pid, start) == aos7_proc.ALIVE

    def assert_no_daemon(self, sub, old_daemon):
        self.assertIn(self.status(sub).get("pid"), (None, old_daemon), "不該起新代子 daemon")
        self.assertFalse(aos7_proc.pid_alive(self.status(sub).get("pid") or 0))


class TestParentKill(RecoverCase):
    """經父 daemon：真的父 kill，下一個 aos7-subd 起新代之前就把原任務收掉（A5-01 驗收：替代 daemon 出現時原任務已全消失）。"""
    def setup_parent(self, pause_child=False):
        sub, n1 = self.child_space()
        a = self.mknode("a", [{"name": "sub", "mode": "keep", "argv": [sys.executable, SUBD, "a/sub", "--"] + BOOT}],
                        interval_ms=100)
        self.start_daemon(register=["a"])
        old = self.ready_pids(n1)
        old_daemon = self.wait_for(lambda: self.status(sub).get("pid"), 10)
        if pause_child:
            self.wait_receipt(self.ctl("pause", "n1", root=sub))
            self.wait_for(lambda: self.nstat("n1", sub).get("phase") == "paused", 10, "n1 沒停下")
        return a, sub, n1, old, old_daemon

    def kill_parent_task(self, a):
        run = self.birth(a, "sub")["run"]
        write_json(os.path.join(self.slot(a, "sub"), "ctl.json"), {"op": "kill", "run": run, "by": "t"})
        return run

    def test_reaped_before_new_daemon(self):
        a, sub, n1, old, old_daemon = self.setup_parent()
        run = self.kill_parent_task(a)
        self.new_daemon(sub, old_daemon)
        self.assertEqual([x for x in old if aos7_proc.pid_alive(x)], [], "新代子 daemon 起來時原任務還活著")
        life = self.life(sub)
        self.assertEqual(life["state"], "running")
        # 新 run＝起它的回合數（核心 next_run），不一定是 run+1：比現役槽的 run、且晚於被 kill 的那個
        self.assertEqual(life["owner"]["run"], str(self.birth(a, "sub")["run"]))
        self.assertGreater(int(life["owner"]["run"]), run)
        self.ready_pids(n1, not_in=old)   # 新代照常起任務

    def test_paused_node_reaped_and_stays_paused(self):
        """子空間的 n1 被 pause：照環境身分收，不必 resume；pause 留著（包不改 pause）。"""
        a, sub, n1, old, old_daemon = self.setup_parent(pause_child=True)
        self.kill_parent_task(a)
        self.new_daemon(sub, old_daemon)
        self.assertEqual([x for x in old if aos7_proc.pid_alive(x)], [])
        self.wait_for(lambda: self.nstat("n1", sub).get("phase") == "paused", 10, "新代的 n1 沒維持 paused")
        self.assertTrue(self.nstat("n1", sub).get("paused_by"))


class TestInterrupted(RecoverCase):
    """回收的每個窗口被殺（AOS7_TEST_CRASH＝SIGKILL 自己），記錄都留著、不起新代；下一次照常接續收完再起。"""
    def crash_then_resume(self, point, old_alive_after_crash):
        sub, n1, old, old_daemon = self.leftover_gen()
        p2 = self.run_subd(run=2, env={"AOS7_TEST_CRASH": point})
        self.assertEqual(p2.wait(15), -signal.SIGKILL, self.err(p2))
        self.assert_no_daemon(sub, old_daemon)
        self.assertEqual(self.life(sub)["state"], "running" if point == "subd-before-argv" else "recovering")
        self.assertEqual(all(aos7_proc.pid_alive(x) for x in old), old_alive_after_crash)
        p3 = self.run_subd(run=3)
        self.new_daemon(sub, old_daemon)
        self.assertIsNone(p3.poll())
        self.assertEqual([x for x in old if aos7_proc.pid_alive(x)], [])
        self.assertEqual(self.life(sub)["state"], "running")
        self.assertEqual(self.life(sub)["owner"]["run"], "3")
        self.ready_pids(n1, not_in=old)

    def test_killed_while_reaping(self):
        self.crash_then_resume("subd-reaping", True)

    def test_killed_after_reaped_before_new_gen(self):
        self.crash_then_resume("subd-reaped", False)

    def test_killed_before_argv(self):
        self.crash_then_resume("subd-before-argv", False)


class TestUnknown(RecoverCase):
    """不知道前代收乾淨沒有＝退出碼 1、不起新代、記錄留著；修好之後照常收。"""
    def test_scan_incomplete_does_not_start(self):
        sub, n1, old, old_daemon = self.leftover_gen()
        p2 = self.run_subd(run=2, env={"AOS7_TEST_FAULT": "proc-list:*:EIO"})
        self.assertEqual(p2.wait(15), 1)
        self.assertIn("讀不完整", self.err(p2))
        self.assert_no_daemon(sub, old_daemon)
        self.assertEqual(self.life(sub)["state"], "recovering")
        self.assertTrue(all(aos7_proc.pid_alive(x) for x in old))
        self.run_subd(run=3)
        self.new_daemon(sub, old_daemon)
        self.assertEqual([x for x in old if aos7_proc.pid_alive(x)], [])

    def test_bad_record_does_not_start(self):
        sub, n1, old, old_daemon = self.leftover_gen()
        with open(os.path.join(sub, ".aosd", "subd-life.json"), "w") as f:
            f.write("{半份")
        p2 = self.run_subd(run=2)
        self.assertEqual(p2.wait(15), 1)
        self.assertIn("subd-life.json", self.err(p2))
        self.assert_no_daemon(sub, old_daemon)
        self.assertTrue(all(aos7_proc.pid_alive(x) for x in old))

    def test_no_record_with_old_slots_is_not_fresh(self):
        """沒有記錄（例如舊版包起的）但子根已有前代：不當全新空間，照樣先收。"""
        sub, n1, old, old_daemon = self.leftover_gen()
        os.remove(os.path.join(sub, ".aosd", "subd-life.json"))
        self.run_subd(run=2)
        self.new_daemon(sub, old_daemon)
        self.assertEqual([x for x in old if aos7_proc.pid_alive(x)], [])


class TestBoundary(RecoverCase):
    """只收自己子根裡的前代：sibling 子根（名字是前綴也一樣）與現役新代不碰；被允許的 stop 之後不回收。"""
    def test_sibling_and_current_gen_untouched(self):
        sub2, n1b = self.child_space("a/sub2", n=1)
        q = self.run_subd("a/sub2", run=1)
        sib = self.ready_pids(n1b, n=1)
        sub, n1, old, old_daemon = self.leftover_gen("a/sub")
        self.run_subd(run=2)
        cur_daemon = self.new_daemon(sub, old_daemon)
        self.assertEqual([x for x in old if aos7_proc.pid_alive(x)], [])
        self.assertTrue(aos7_proc.pid_alive(sib[0]), "收到 sibling 子根 a/sub2 的任務了")
        self.assertIsNone(q.poll())
        cur = self.ready_pids(n1, not_in=old)
        # 同一子根再起一個包：拿不到 subd.lock，退出碼 1，不掃、不收現役新代
        p3 = self.run_subd(run=3)
        self.assertEqual(p3.wait(15), 1)
        self.assertIn("認領", self.err(p3))
        self.assertTrue(all(aos7_proc.pid_alive(x) for x in cur), "收到現役新代的任務了")
        self.assertEqual(self.status(sub).get("pid"), cur_daemon)

    def test_allowed_stop_without_kill_keeps_tasks(self):
        """被允許的 stop（不帶 kill）留下的任務是擁有者要留的：刪掉 stopped.json 再起時不回收，照核心接回。"""
        sub, n1 = self.child_space(n=1)
        p = self.run_subd(run=1, allow_stop=True)
        pid = self.ready_pids(n1, n=1)[0]
        old_daemon = self.wait_for(lambda: self.status(sub).get("pid"), 10)
        self.assertTrue(self.wait_receipt(self.ctl("stop", root=sub))["result"]["ok"])
        self.assertEqual(p.wait(15), 0)
        self.assertEqual(self.life(sub)["state"], "stopped")
        self.assertTrue(os.path.exists(os.path.join(sub, ".aosd", "stopped.json")))
        self.assertTrue(aos7_proc.pid_alive(pid))
        os.remove(os.path.join(sub, ".aosd", "stopped.json"))
        self.run_subd(run=2, allow_stop=True)
        self.new_daemon(sub, old_daemon)
        self.wait_for(lambda: "s0#1" in self.nstat("n1", sub).get("live", []), 10, "新代沒接回原任務")
        self.assertTrue(aos7_proc.pid_alive(pid))


class TestAllowedStopInterrupted(RecoverCase):
    """A6-01：被允許的 stop（不帶 kill）的提交在三個窗口被真 SIGKILL：status 已 stopped 還沒寫 stopped.json、stopped.json 的暫存檔
    還沒 rename、stopped.json 寫了生命週期還沒寫。生命週期都還是 running；下一次起包要用核心停止事實（status＋stop 回條）判出
    「被允許的 stop 停過」：補完提交、退出碼 1、不回收；刪掉 stopped.json 再起＝核心 §5.4 接回原任務（同 PID／starttime、沒有 run 2）。
    反例：父 kill（SIGTERM，不留回條）照收；上一代留下的舊 stop 回條＋本代父 kill 也照收（兩者都把 status 補成 stopped，見 status_stopped）。"""

    def status_stopped(self, sub):
        """父 kill 時子 daemon 常在收任務途中就被 SIGKILL、status 還沒寫 stopped；這裡補成 stopped: true，模擬「寬限內收完、
        寫好 stopped」——最容易被誤判成被允許的 stop 的情況（判定要靠回條分辨，不能只看 status）。"""
        path = os.path.join(sub, ".aosd", "status.json")
        st = read_json(path)
        if st.get("stopped") is not True:
            write_json(path, dict(st, stopped=True))

    def crash_window(self, point, marker_written):
        sub, n1, pid, start, daemon, p = self.stopped_by_ctl(env={"AOS7_TEST_CRASH": point})
        self.assertEqual(p.wait(15), -signal.SIGKILL, self.err(p))
        stopped = os.path.join(sub, ".aosd", "stopped.json")
        self.assertEqual(self.life(sub)["state"], "running", "前提不成立：生命週期已經提交了")
        self.assertEqual(os.path.exists(stopped), marker_written)
        self.assertTrue(self.same(pid, start))
        p2 = self.run_subd(run=2, allow_stop=True)
        self.assertEqual(p2.wait(15), 1, self.err(p2))
        self.assertIn("stop", self.err(p2))
        self.assertTrue(os.path.exists(stopped), "沒補寫 stopped.json")
        self.assertIsInstance(read_json(stopped).get("at"), str, "stopped.json 沒取那份 stop 回條")
        self.assertEqual(self.life(sub)["state"], "stopped", "沒補完生命週期")
        self.assertTrue(self.same(pid, start), "被允許的 stop 留下的任務被收了")
        self.assert_no_daemon(sub, daemon)
        os.remove(stopped)
        self.run_subd(run=3, allow_stop=True)
        self.new_daemon(sub, daemon)
        self.wait_for(lambda: "s0#1" in self.nstat("n1", sub).get("live", []), 10, "新代沒接回原任務")
        self.assertTrue(self.same(pid, start), "接回時原任務不是同一個程序")
        self.assertEqual(self.birth(n1, "s0")["run"], 1, "起了 run 2")
        self.assertEqual(self.life(sub)["state"], "running")

    def test_killed_before_marker(self):
        """status 已 stopped、stopped.json 還沒寫。"""
        self.crash_window("subd-stop-seen", False)

    def test_killed_before_marker_rename(self):
        """stopped.json 的暫存檔寫了、還沒 rename。"""
        self.crash_window("tmp:stopped.json", False)

    def test_killed_after_marker_before_life(self):
        """stopped.json 寫了、生命週期還沒寫：先被 stopped.json 擋（順手補完生命週期），刪掉再起就接回。"""
        self.crash_window("subd-stop-marked", True)

    def test_unknown_status_neither_reaps_nor_starts(self):
        """窗口中斷後子根 status.json 讀不到＝不知道是不是被允許的 stop：退出碼 1、不收、不起、記錄不動；讀得到了照常補完。"""
        sub, n1, pid, start, daemon, p = self.stopped_by_ctl(env={"AOS7_TEST_CRASH": "subd-stop-seen"})
        self.assertEqual(p.wait(15), -signal.SIGKILL, self.err(p))
        p2 = self.run_subd(run=2, allow_stop=True, env={"AOS7_TEST_FAULT": "open:*/a/sub/.aosd/status.json:EIO"})
        self.assertEqual(p2.wait(15), 1, self.err(p2))
        self.assertIn("不知道", self.err(p2))
        self.assertTrue(self.same(pid, start))
        self.assertEqual(self.life(sub)["state"], "running")
        self.assertFalse(os.path.exists(os.path.join(sub, ".aosd", "stopped.json")))
        self.assert_no_daemon(sub, daemon)
        p3 = self.run_subd(run=3, allow_stop=True)
        self.assertEqual(p3.wait(15), 1, self.err(p3))
        self.assertEqual(self.life(sub)["state"], "stopped")
        self.assertTrue(self.same(pid, start))

    def test_parent_kill_with_allow_stop_reaps(self):
        """父 kill（SIGTERM＝stop＋kill，不留回條）：子根 status 也是 stopped，但不是被允許的 stop——照收、不寫 stopped.json。"""
        sub, n1 = self.child_space()
        p = self.run_subd(run=1, allow_stop=True)
        old = self.ready_pids(n1)
        daemon = self.wait_for(lambda: self.status(sub).get("pid"), 10, "子 daemon 沒起")
        self.parent_kill(p)
        self.wait_for(lambda: not aos7_proc.pid_alive(daemon), 5, "子 daemon 沒死")
        self.status_stopped(sub)
        self.assertTrue(all(aos7_proc.pid_alive(x) for x in old), "前提不成立：父 kill 後原任務已經沒了")
        self.assertFalse(os.path.exists(os.path.join(sub, ".aosd", "stopped.json")))
        self.assertEqual(self.life(sub)["state"], "running")
        self.run_subd(run=2, allow_stop=True)
        self.new_daemon(sub, daemon)
        self.assertEqual([x for x in old if aos7_proc.pid_alive(x)], [], "父 kill 留下的前代沒收")

    def test_old_stop_receipt_then_parent_kill_reaps(self):
        """上一代被允許的 stop 留下的回條（早於本代 since）不算：本代被父 kill 照收。"""
        sub, n1 = self.child_space()
        p = self.run_subd(run=1, allow_stop=True)
        gen1 = self.ready_pids(n1)
        d1 = self.wait_for(lambda: self.status(sub).get("pid"), 10, "子 daemon 沒起")
        self.assertTrue(self.wait_receipt(self.ctl("stop", "--kill", root=sub))["result"]["ok"])
        self.assertEqual(p.wait(15), 0)
        self.assertEqual(self.life(sub)["state"], "stopped")
        os.remove(os.path.join(sub, ".aosd", "stopped.json"))
        p2 = self.run_subd(run=2, allow_stop=True)
        d2 = self.new_daemon(sub, d1)
        old = self.ready_pids(n1, not_in=gen1)
        self.parent_kill(p2)
        self.wait_for(lambda: not aos7_proc.pid_alive(d2), 5, "第二代子 daemon 沒死")
        self.status_stopped(sub)
        self.assertTrue(all(aos7_proc.pid_alive(x) for x in old), "前提不成立：父 kill 後原任務已經沒了")
        self.assertEqual(self.life(sub)["state"], "running")
        p3 = self.run_subd(run=3, allow_stop=True)
        self.new_daemon(sub, d2)
        self.assertIsNone(p3.poll())
        self.assertFalse(os.path.exists(os.path.join(sub, ".aosd", "stopped.json")), "拿上一代的回條判成被允許的 stop")
        self.assertEqual([x for x in old if aos7_proc.pid_alive(x)], [], "父 kill 留下的前代沒收")


if __name__ == "__main__":
    unittest.main()
