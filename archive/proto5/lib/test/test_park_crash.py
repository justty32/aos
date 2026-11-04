"""09-24 停車＋喚醒的真 SIGKILL 崩潰窗口（借 test_kernel_crash 的閘門 tick、真 daemon、真 aos-cpu）。

「agent」是一份每跑一次記一行、然後退 102 的工作（停車，park_ms 拉到 10 分鐘＝不叫就不會再跑）；
「q」是一張帶 `wake: agent` 的 once。只看兩件事：kernel 在出貨窗口被砍之後，下一格有沒有把 agent 叫起來；回音檔是不是只放成功一次。
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import aos_client
from _kernel_util import read_json, wait_for
import test_kernel_crash


class ParkKillTest(test_kernel_crash.KernelCrashWindowTest):
    def parked_agent(self):
        self.setup_running()
        target, _ = self.job("agent", code=102)
        self.add(target, "agent", interval_ms=0, park_ms=600000)
        wait_for(lambda: self.state()["procs"]["agent"].get("parked") is True, timeout=10)
        self.assertEqual(self.runs("agent"), 1)
        q_target, _ = self.job("q")
        return q_target

    def finish(self, name, hit):
        self.release("next")
        wait_for(lambda: self.runs("agent") == 2, timeout=10)      # 被叫醒、再跑了一次（又停下）
        wait_for(lambda: self.state()["procs"]["agent"].get("parked") is True, timeout=10)
        self.settle()
        self.assertEqual(self.runs("agent"), 2)
        self.assertEqual(self.runs("q"), 1)
        self.assertEqual(self.state()["replies"], [])
        self.assertEqual(len(self.trace(op="reply", outcome="ok", name=name)), 1)
        self.assertEqual(read_json(self.home / "responses" / name)["result"]["code"], 0)
        self.assert_no_same_name_twice()

    def test_kill_after_reply_placed_before_ledger(self):
        """放好回音檔（第 10 步）、還沒存帳本就 SIGKILL：下一格第 4 步 EEXIST 當已放、再叫一次。"""
        q_target = self.parked_agent()
        name = aos_client.new_name("cli")
        self.gate("reply", "after_put", box="reply", name=name)
        aos_client.submit(self.home, "add", {"name": "q", "target": q_target, "once": True, "wake": "agent"}, name=name)
        hit, held = self.kill_tick("reply", hold="next")
        st = self.state()
        self.assertEqual([(r["name"], r["wake"]) for r in st["replies"]], [(name, "agent")])
        self.assertTrue(st["procs"]["agent"]["parked"])               # 叫醒沒存到
        self.assertTrue((self.home / "responses" / name).exists())
        self.finish(name, hit)
        self.assertEqual([e["seq"] for e in self.trace(op="reply", outcome="exists", name=name)], [hit["seq"] + 1])

    def test_kill_after_verdict_before_reply_placed(self):
        """回音待辦（帶 wake）已存、放檔前 SIGKILL：下一格第 4 步放檔、叫醒。"""
        q_target = self.parked_agent()
        name = aos_client.new_name("cli")
        self.gate("reply", "before_put", box="reply", name=name)
        aos_client.submit(self.home, "add", {"name": "q", "target": q_target, "once": True, "wake": "agent"}, name=name)
        hit, held = self.kill_tick("reply", hold="next")
        st = self.state()
        self.assertEqual([r["name"] for r in st["replies"]], [name])
        self.assertFalse((self.home / "responses" / name).exists())
        self.assertTrue(st["procs"]["agent"]["parked"])
        self.finish(name, hit)
        self.assertEqual([e["seq"] for e in self.trace(op="reply", outcome="ok", name=name)], [hit["seq"] + 1])


# 只跑這裡的兩條：借來的 KernelCrashWindowTest 自己的測試在 test_kernel_crash 已經跑過。
for _name in dir(test_kernel_crash.KernelCrashWindowTest):
    if _name.startswith("test_"):
        setattr(ParkKillTest, _name, None)
