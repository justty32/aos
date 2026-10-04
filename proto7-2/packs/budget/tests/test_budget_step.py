"""〔budget〕接 step：一個普通 run 步呼叫 `aos7-budget call`（reserve → run → settle），帳是 tick 起的 keep 任務。

兩種跑法都是真的回合、離線：
- **daemon**：範例走通、close 後重播不重扣、restart_on_end 新 request 才是新交易、工作失敗仍計 1、pause／daemon 重開時鐘。
- **手動 tick／tock**：包裝程式在各點被 SIGKILL（在任務裡殺整個程序群組＝step 拿不到結果）→ step unknown →
  同 request 新 attempt；槽已刪、結果未發布時結算恢復不依賴 step。
"""
import json
import os
import shutil
import subprocess
import sys
import time
import unittest

from budgetcase import BUDGET, EXAMPLES, PY, TOP, BudgetMixin, grant
from base import DaemonCase
from _matrix import MatrixCase
import aos7_budget as bg
from aos7_fs import read_json, write_json

STEP = os.path.join(TOP, "packs", "step", "bin", "aos7-step")
LEDGER_ITEM = {"name": "budget-demo", "mode": "keep", "argv": [PY, BUDGET, "ledger", "budget/demo"]}


class StepBudgetCase(BudgetMixin, MatrixCase, DaemonCase):

    def install(self, node, job="api", g=None, payload=None, **step_over):
        """裝預算（開帳）＋範例工作；回 tasks.json 的兩項（帳、直譯器）。"""
        self.bd = self.setup_budget(node, g, clock=None)
        jd = os.path.join(node, "jobs", job)
        shutil.copytree(os.path.join(EXAMPLES, "fakeapi"), jd)
        os.unlink(os.path.join(jd, "grant.json"))
        if payload:
            write_json(os.path.join(jd, "payload.json"), payload)
        t = read_json(os.path.join(jd, "steps.json"))
        t["steps"]["call"]["run"] = [BUDGET if x == "@BUDGET@" else x for x in t["steps"]["call"]["run"]]
        t["steps"]["call"].update(step_over)
        write_json(os.path.join(jd, "steps.json"), t)
        return [LEDGER_ITEM, {"name": "step-" + job, "mode": "keep", "argv": [PY, STEP, "run", "jobs/" + job]}]

    def jd(self, node, job, *a):
        return os.path.join(node, "jobs", job, *a)

    def frame(self, node, job="api"):
        return read_json(self.jd(node, job, "frame.json")) or {}

    def step_cli(self, node, *args):
        return subprocess.run([PY, STEP, *args], cwd=node, capture_output=True, text=True, timeout=30)

    def cycle(self, node, job="api"):
        """手動一回合：tick、等直譯器啟動圈（若剛起）、tock、等直譯器處理完這個 tock。"""
        out = self.tick()
        rnd = out["round"]
        if any(r.startswith("step-%s#" % job) for r in out["started"]):
            self.wait_for(lambda: (self.frame(node, job).get("seen") or 0) >= rnd
                          or self.frame(node, job).get("phase") == "ended", 10, "直譯器啟動圈沒跑完")
        self.tock()

        def done():
            fr = self.frame(node, job)
            return fr.get("phase") == "ended" or (fr.get("tock") or 0) >= rnd
        self.wait_for(done, 10, "直譯器沒處理第 %d 回合：%r" % (rnd, self.frame(node, job)))
        return rnd

    def run_until(self, node, pred, limit=15, msg="沒走到"):
        for _ in range(limit):
            if pred():
                return
            self.cycle(node)
        self.assertTrue(pred(), "%s：frame=%r" % (msg, self.frame(node)))

    def wait_job_end(self, node, job="api", timeout=30):
        self.wait_for(lambda: self.frame(node, job).get("phase") == "ended", timeout,
                      "工作沒結束：%r" % self.frame(node, job))
        return self.frame(node, job)


class TestBudgetDaemon(StepBudgetCase):
    """〔budget〕真 daemon＋step：走通、close 後重播、新 inst 新交易、工作失敗計 1、pause 與 daemon 重開。"""

    def test_end_to_end_and_replay_after_close(self):
        node = self.mknode("a", interval_ms=50)
        self.set_tasks(node, self.install(node))
        self.start_daemon(register=["a"])
        fr = self.wait_job_end(node)
        self.assertEqual(fr["end"], "ok", fr)
        req = fr["accepted"]["call"]["request"]
        out = read_json(self.jd(node, "api", "out", "call.json"))
        self.assertEqual((out["outcome"], out["used"], out["key"]["request"]), ("accepted", 1, req))
        self.assertEqual(out["response"]["echo"], "hello")
        L = self.audit(self.bd, final=True)
        self.assertEqual((L["used"], L["available"]), (1, 2))
        # close 只清 step 的結果；帳與入口仍認得 K：同 K 重跑不重扣、不重做
        self.assertEqual(self.step_cli(node, "close", "jobs/api").returncode, 0)
        self.assertFalse(os.path.exists(self.jd(node, "api", "results")))
        rc, again = self.call(node, req, payload=self.jd(node, "api", "payload.json"))
        self.assertEqual((rc, again["outcome"], again["settle"]), (0, "accepted", out["settle"]))
        L = self.audit(self.bd, final=True)
        self.assertEqual((L["used"], len(L["log"]), self.backend(self.bd)["accepted"]), (1, 2, 1))

    def test_restart_on_end_new_request_new_transaction(self):
        """restart_on_end：每個新 inst 是新 request＝新交易；額度 3 用完後第四次 reserve 被拒，工作走 failed。"""
        node = self.mknode("a", interval_ms=30)
        items = self.install(node)
        t = read_json(self.jd(node, "api", "steps.json"))
        t["options"] = {"restart_on_end": True}
        write_json(self.jd(node, "api", "steps.json"), t)
        self.set_tasks(node, items)
        self.start_daemon(register=["a"])
        seen = {}

        def sample():
            fr = self.frame(node)
            if fr.get("phase") == "ended":
                seen[fr["inst"]] = fr["end"]
            return list(seen.values()).count("failed") >= 1 and len(seen) >= 4
        self.wait_for(sample, 60, "沒跑滿四次：%r" % seen)
        L = self.audit(self.bd)
        self.assertEqual((L["used"], L["available"], len(L["ops"])), (3, 0, 3))
        self.assertEqual(self.backend(self.bd)["accepted"], 3)

    def test_work_failure_still_counts(self):
        """後端已受理、處理失敗：step ok:false 走 failed，但帳照受理結算 1（不因 step 失敗退款）。"""
        node = self.mknode("a", interval_ms=50)
        self.set_tasks(node, self.install(node, payload={"mode": "fail"}))
        self.start_daemon(register=["a"])
        fr = self.wait_job_end(node)
        self.assertEqual((fr["end"], fr["accepted"]["call"]["ok"]), ("failed", False), fr)
        L = self.audit(self.bd, final=True)
        self.assertEqual((L["used"], self.backend(self.bd)["accepted"]), (1, 1))

    def test_pause_and_daemon_restart_clock(self):
        """completed_tock：pause 時不前進；daemon 重開接續原回合（不歸零）；之後 call 照常、帳的 clock_hw 不超過時鐘。"""
        node = self.mknode("a", interval_ms=50)
        self.set_tasks(node, self.install(node, g=grant(until=10 ** 6)))
        p = self.start_daemon(register=["a"])
        self.wait_job_end(node)
        self.wait_round(5)
        self.prog("aos7-ctl", "daemon", self.root, "pause", "a", "--owner", "t")
        self.wait_for(lambda: self.nstat().get("phase") == "paused", 10, "沒 pause")
        time.sleep(0.3)
        c0 = bg.completed_tock(node)
        time.sleep(1.0)
        self.assertEqual(bg.completed_tock(node), c0)
        self.stop_daemon(p)
        self.start_daemon()
        self.prog("aos7-ctl", "daemon", self.root, "resume", "a", "--owner", "t")
        self.wait_for(lambda: (bg.completed_tock(node) or 0) > c0, 15, "重開後回合沒接續")
        self.assertGreater(bg.completed_tock(node), c0)
        rc, out = self.call(node, "after-restart")
        self.assertEqual(rc, 0, out)
        L = self.audit(self.bd, final=True)
        self.assertLessEqual(L["clock_hw"], bg.completed_tock(node))
        self.assertEqual(L["used"], 2)


class TestBudgetStepProbes(StepBudgetCase):
    """〔budget〕手動回合：包裝程式在各點被殺 → step unknown → 同 request 新 attempt，不重扣、不重做。"""

    def test_crash_points_resend_same_request(self):
        for point in ("call-after-reserve", "gateway-after-intent", "backend-after-effect", "gateway-after-receipt",
                      "call-after-settle"):
            with self.subTest(point=point):
                node = self.mknode("a")
                self.set_tasks(node, self.install(node))
                self.crash_at(self.bd, point)
                self.run_until(node, lambda: self.frame(node).get("phase") == "ended", msg=point)
                fr = self.frame(node)
                self.assertFalse(os.path.exists(os.path.join(self.bd, ".crash")), "%s 沒打中" % point)
                acc = fr["accepted"]["call"]
                self.assertEqual((fr["end"], acc["attempt"]), ("ok", acc["request"] + "-a2"), fr)
                L = self.audit(self.bd, final=True)
                self.assertEqual((L["used"], len(L["log"]), self.backend(self.bd)["accepted"]), (1, 2, 1), point)
                self.assertEqual(list(L["ops"].values())[0]["key"]["request"], acc["request"])
                from base import kill_space_procs
                kill_space_procs(self.root)
                shutil.rmtree(node)

    def test_slot_gone_settle_without_step(self):
        """入口回條寫了、結算前被殺，step 停在 unknown（不自動重送）；once 槽刪掉後直接 settle 照入口證據結算 1；
        之後 resume --resend 只重播（結果未發布那段也不重扣）。"""
        node = self.mknode("a")
        self.set_tasks(node, self.install(node, on_unknown="stop"))
        self.crash_at(self.bd, "gateway-after-receipt")
        self.run_until(node, lambda: self.frame(node).get("phase") == "halted", msg="沒停在 unknown")
        self.assertEqual(self.frame(node)["halt"]["kind"], "unknown")
        req = self.frame(node)["pending"]["request"]
        for _ in range(3):
            self.cycle(node)
        self.assertFalse(os.path.exists(self.slot(node, "step-api-call")), "once 槽還在，測不到")
        self.assertEqual(self.audit(self.bd)["inflight"], 1)
        r = self.cli(node, "settle", "budget/demo", "--holder", "api", "--request", req)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.loads(r.stdout.strip().splitlines()[-1])["settle"]["used"], 1)
        self.audit(self.bd, final=True)
        self.assertEqual(self.step_cli(node, "resume", "jobs/api", "--resend").returncode, 0)
        self.run_until(node, lambda: self.frame(node).get("phase") == "ended")
        self.assertEqual(self.frame(node)["end"], "ok")
        L = self.audit(self.bd, final=True)
        self.assertEqual((L["used"], len(L["log"]), self.backend(self.bd)["accepted"]), (1, 2, 1))

    def test_expired_between_rounds(self):
        """reserve 後被殺、step 停在 unknown；回合走過 until 後 resume --resend：首次准入被擋 → 結算 0、step 走 failed。"""
        node = self.mknode("a")
        self.set_tasks(node, self.install(node, g=grant(until=5), on_unknown="stop"))
        self.crash_at(self.bd, "call-after-reserve")
        self.run_until(node, lambda: self.frame(node).get("phase") == "halted", msg="沒停在 unknown")
        L = self.audit(self.bd)
        self.assertEqual((len(L["ops"]), L["inflight"]), (1, 1))
        self.assertLess(L["clock_hw"], 5)
        self.run_until(node, lambda: (bg.completed_tock(node) or 0) >= 5, msg="時鐘沒走到 until")
        self.assertEqual(self.step_cli(node, "resume", "jobs/api", "--resend").returncode, 0)
        self.run_until(node, lambda: self.frame(node).get("phase") == "ended", msg="沒結束")
        fr = self.frame(node)
        self.assertEqual(fr["end"], "failed", fr)
        L = self.audit(self.bd, final=True)
        g = self.gw(self.bd, list(L["ops"])[0])
        self.assertEqual((g["outcome"], L["used"], L["available"]), ("denied", 0, 3), g)
        self.assertEqual(self.backend(self.bd)["effects"], {})

if __name__ == "__main__":
    unittest.main()
