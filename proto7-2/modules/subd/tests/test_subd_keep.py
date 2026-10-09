"""〔subd〕被允許的 stop 留下的任務不被誤收（A8-09、MC-01），與回收記錄不無界巢狀（R8-18）。

- A8-09：合法 no-kill stop 已生效（status stopped），但子根 `ctl-done/` 寫不進去、回條沒留下（核心 §2.3：處理例外刪請求、記
  `last_ctl_error`）。以前判定只認回條，重開就把應保留的任務收掉；現在「本代有 last_ctl_error」＝可能就是那件 stop＝不知道，
  不轉成可回收：照被允許的 stop 提交（stopped.json 帶 unconfirmed），刪掉再起照核心接回。
- MC-01：刪 stopped.json 重接時，新 running 已寫、argv 還沒起就被殺；再起時舊 stop 回條早於新 since。現在 running 帶 `kept`，
  本代還沒有 daemon 起來過（gen.json 早於 since）就仍算「保留中」，不回收。
- R8-18：回收一再被打斷，recovering 的 `prev` 只留最初那份前代記錄，不一層包一層。"""
import os
import signal
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # 同資料夾的 test_subd_recover（RecoverCase）

import unittest  # noqa: E402

from test_subd_recover import RecoverCase  # noqa: E402（先 import：它把 tests/、lib/ 放上 sys.path）
import aos7_proc  # noqa: E402
from aos7_fs import read_json, write_json  # noqa: E402


class TestReceiptLost(RecoverCase):
    """A8-09：合法 no-kill stop 的回條寫失敗。"""
    def stop_receipt_fails(self, env=None):
        sub, n1 = self.child_space(n=1)
        p = self.run_subd(run=1, allow_stop=True, env=env)
        pid = self.ready_pids(n1, n=1)[0]
        start = aos7_proc.proc(pid)[1]
        daemon = self.wait_for(lambda: self.status(sub).get("pid"), 10, "子 daemon 沒起")
        done = os.path.join(sub, ".aosd", "ctl-done")
        os.chmod(done, 0o555)
        self.addCleanup(os.chmod, done, 0o755)
        self.ctl("stop", root=sub)
        rc = p.wait(15)
        os.chmod(done, 0o755)
        st = self.status(sub)
        self.assertTrue(st.get("stopped"), "前提不成立：stop 沒生效")
        self.assertTrue(st.get("last_ctl_error"), "前提不成立：回條寫成了")
        self.assertFalse([n for n in os.listdir(done) if n.endswith(".json") and
                          (read_json(os.path.join(done, n)) or {}).get("op") == "stop"], "前提不成立：有 stop 回條")
        self.assertTrue(self.same(pid, start), "前提不成立：no-kill stop 收了任務")
        return sub, n1, pid, start, daemon, p, rc

    def reattach(self, sub, n1, pid, start, daemon):
        stopped = os.path.join(sub, ".aosd", "stopped.json")
        self.assertTrue(read_json(stopped).get("unconfirmed"), "stopped.json 沒註明回條沒寫成")
        os.remove(stopped)
        self.run_subd(run=3, allow_stop=True)
        self.new_daemon(sub, daemon)
        self.wait_for(lambda: "s0#1" in self.nstat("n1", sub).get("live", []), 10, "新代沒接回原任務")
        self.assertTrue(self.same(pid, start), "接回時原任務不是同一個程序")
        self.assertEqual(self.birth(n1, "s0")["run"], 1, "起了 run 2")

    def test_receipt_lost_keeps_tasks(self):
        """包活著看到收尾：照被允許的 stop 提交；再起被擋、任務不收；刪掉 stopped.json 再起照核心接回。"""
        sub, n1, pid, start, daemon, p, rc = self.stop_receipt_fails()
        self.assertEqual(rc, 0, self.err(p))
        self.assertEqual(self.life(sub)["state"], "stopped")
        p2 = self.run_subd(run=2, allow_stop=True)
        self.assertEqual(p2.wait(15), 1, self.err(p2))
        self.assertTrue(self.same(pid, start), "回條沒寫成的合法 stop 留下的任務被收了")
        self.assert_no_daemon(sub, daemon)
        self.reattach(sub, n1, pid, start, daemon)

    def test_receipt_lost_and_commit_killed(self):
        """收尾提交前包被 SIGKILL（記錄還是 running）：下一次起包用同一個判定補完、不回收。"""
        sub, n1, pid, start, daemon, p, rc = self.stop_receipt_fails(env={"AOS7_TEST_CRASH": "subd-stop-seen"})
        self.assertEqual(rc, -signal.SIGKILL, self.err(p))
        self.assertEqual(self.life(sub)["state"], "running")
        p2 = self.run_subd(run=2, allow_stop=True)
        self.assertEqual(p2.wait(15), 1, self.err(p2))
        self.assertEqual(self.life(sub)["state"], "stopped")
        self.assertTrue(self.same(pid, start), "回條沒寫成的合法 stop 留下的任務被收了")
        self.assert_no_daemon(sub, daemon)
        self.reattach(sub, n1, pid, start, daemon)

    def test_ctl_error_without_allow_stop_still_reaps(self):
        """沒 --allow-stop 的代不可能有被允許的 stop：本代有 last_ctl_error、status stopped（父 kill 收完）也照收。"""
        sub, n1, old, daemon = self.leftover_gen()
        path = os.path.join(sub, ".aosd", "status.json")
        st = read_json(path)
        write_json(path, dict(st, stopped=True, last_ctl_error={"file": "x.json", "at": self.life(sub)["since"] + "9",
                                                               "err": "RuntimeError()"}))
        self.run_subd(run=2)
        self.new_daemon(sub, daemon)
        self.assertEqual([], self.alive_old(old), "沒 --allow-stop 的前代沒收")


class TestReattachInterrupted(RecoverCase):
    """MC-01：合法 no-kill stop → 刪 stopped.json 重接 → 新 running 寫了、argv 前被殺 → 再起不收保留的任務。"""
    def test_killed_before_argv_while_reattaching(self):
        sub, n1, pid, start, daemon, p = self.stopped_by_ctl()
        self.assertEqual(p.wait(15), 0, self.err(p))
        self.assertEqual(self.life(sub)["state"], "stopped")
        os.remove(os.path.join(sub, ".aosd", "stopped.json"))
        p2 = self.run_subd(run=2, allow_stop=True, env={"AOS7_TEST_CRASH": "subd-before-argv"})
        self.assertEqual(p2.wait(15), -signal.SIGKILL, self.err(p2))
        self.assertEqual(self.life(sub)["state"], "running")
        self.assertTrue(self.same(pid, start))
        p3 = self.run_subd(run=3, allow_stop=True)
        self.new_daemon(sub, daemon)
        self.assertIsNone(p3.poll())
        self.wait_for(lambda: "s0#1" in self.nstat("n1", sub).get("live", []), 10, "新代沒接回原任務")
        self.assertTrue(self.same(pid, start), "重接中斷後保留的任務被收了")
        self.assertEqual(self.birth(n1, "s0")["run"], 1, "起了 run 2")


class TestRecoveringRecord(RecoverCase):
    """R8-18：回收被打斷幾次，recovering 的 prev 都是最初那份前代記錄（固定大小），不巢狀。"""
    def test_prev_not_nested(self):
        sub, n1, old, daemon = self.leftover_gen()
        first = self.life(sub)
        for run in (2, 3):
            p = self.run_subd(run=run, env={"AOS7_TEST_CRASH": "subd-reaping"})
            self.assertEqual(p.wait(15), -signal.SIGKILL, self.err(p))
            life = self.life(sub)
            self.assertEqual(life["state"], "recovering")
            self.assertEqual(life["prev"], first, "prev 不是最初的前代記錄")
        self.assertEqual(life["attempt"], 2)
        self.run_subd(run=4)
        self.new_daemon(sub, daemon)
        self.assertEqual([], self.alive_old(old))


if __name__ == "__main__":
    unittest.main()
