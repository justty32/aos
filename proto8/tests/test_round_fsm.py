"""test_round_fsm - agent-round 一輪：lib/agent/round 的 fsm 表＋五格（10-31 自 test_round.py 拆出，行為不變）。

一輪（10-30 起 aos-round：lib/agent/round 的 fsm 表＋五格；舊骨架 round/_entry 與它的 Round 類、--step、hook/pause 第 6 步刪了）：
  題目經 queue push 進 $AOS_STACK/queue/，答案看 history 最新那則 assistant。
RoundFsm（第 2 步）：aos-fsm 一次一格、驗 state.txt 與 trace 的 (state, code, next)；system.txt 與 tools 帶進請求、
  第一題答完後 claim 死在搬進 cur/ 之後的補認領（這兩案第 6 步從舊 Round 類搬來）。
設計：proto8/thinking/2026-10-28-agent-round.md § 3、§ 4、文末「實作時代定」；2026-10-30-agent-lifecycle 結論 A、B-11。"""
import subprocess, unittest
from pathlib import Path

from aos_bins import tool  # noqa: E402
from round_common import AgentCase, ROUND, FAKE, OPENAI, err_code, EXEC  # noqa: E402
from dead_brain import DEAD  # noqa: E402

TWO_CLOCKS = """#!/usr/bin/env python3
# 測試用 endpoint：只有一題、最後一則是 user＝一次叫兩個 clock；否則把每一題的題文串起來答
import json, sys
m = json.loads(sys.stdin.read())["messages"]
users = [x["content"].strip() for x in m if x["role"] == "user"]
if m[-1]["role"] == "user" and len(users) == 1:
    calls = [{"id": "c%d" % i, "type": "function", "function": {"name": "clock", "arguments": "{}"}} for i in (1, 2)]
    print(json.dumps({"role": "assistant", "content": None, "tool_calls": calls}))
else:
    print(json.dumps({"role": "assistant", "content": "答：" + "／".join(users)}, ensure_ascii=False))
"""



class RoundFsm(AgentCase):
    """lib/agent/round 的表＋五格（thinking 2026-10-30-aos-round § B、實作步驟第 2 步）：aos-fsm 一次一格（cwd＝round 資料夾），
    驗 state.txt、history 與 fsm trace 的 (state, code, next) 序列；格對 state 與資料對不上要自保（crash 接續）。"""

    def step(self, table="fsm-stop.json", env=None):
        """aos-fsm 跑一格；回 (碼, stderr)。"""
        r = subprocess.run([tool("aos-fsm"), table], capture_output=True, text=True, cwd=ROUND, timeout=120,
                           env=self.env(dict({"AOS_ROUND_AGENT": str(self.agent)}, **(env or {}))))
        return r.returncode, r.stderr

    def steps(self, n, **kw):
        return [self.step(**kw)[0] for _ in range(n)]

    def states(self):
        return [(t["state"], t["code"], t["next"]) for t in self.lines((self.stack / "trace.jsonl").read_text())]

    def state(self):
        """state.txt 的狀態；沒有＝""（fsm 當 start）。"""
        p = self.stack / "state.txt"
        return p.read_text().strip() if p.exists() else ""

    def test_no_tools(self):
        (self.agent / "tools.json").write_text('{"tools": {}}')
        self.assertEqual(self.steps(4), [0, 0, 0, 10])
        self.assertEqual(self.states(), [("idle", 0, "think"), ("think", 10, "finish"), ("finish", 0, "idle"), ("idle", 10, None)])
        self.assertEqual(self.state(), "idle")
        self.assertEqual([m["role"] for m in self.history()], ["user", "assistant"])
        self.assertEqual(self.answer(), "FAKE ANSWER to: 幾點？")
        self.assertEqual((self.ls("new"), self.ls("cur")), ([], []))

    def test_clock(self):
        self.assertEqual(self.steps(6), [0, 0, 0, 0, 0, 10])
        self.assertEqual([s for s, _, _ in self.states()], ["idle", "think", "act", "think", "finish", "idle"])
        self.assertEqual([n for _, _, n in self.states()], ["think", "act", "think", "finish", "idle", None])
        self.assertEqual(self.state(), "idle")
        self.assertEqual([m["role"] for m in self.history()], ["user", "assistant", "tool", "assistant"])
        self.assertRegex(self.answer(), r"^FAKE ANSWER to: 幾點？（clock said: \d{4}-.*Z）$")
        self.assertEqual((self.ls("new"), self.ls("cur")), ([], []))
        self.assertEqual(set(self.lines((self.stack / "trace.jsonl").read_text())[0]),
                         {"started_at", "state", "code", "signal", "elapsed_ms", "next"})        # 格不寫自己的 unit 行

    def test_interrupt(self):
        self.parts["endpoint/default"] = {"path": self.script("two", TWO_CLOCKS, sh=False)}
        q2 = self.put("插話")
        self.hook("on_interrupt", 'read n; [ "$n" = %s ] && echo interrupt\n' % q2)
        self.assertEqual(self.steps(8), [0, 0, 0, 0, 0, 0, 0, 10])
        self.assertEqual(self.states(), [("idle", 0, "think"), ("think", 0, "act"), ("act", 10, "more"), ("more", 0, "act"),
                                         ("act", 0, "think"), ("think", 10, "finish"), ("finish", 0, "idle"), ("idle", 10, None)])
        h = self.history()
        self.assertEqual([m["role"] for m in h], ["user", "assistant", "tool", "tool", "user", "assistant"])
        self.assertTrue(h[3]["content"].startswith("act: Interrupted 有新題（%s）" % q2), h[3])
        self.assertEqual(self.answer(), "答：幾點？／插話")
        self.assertEqual((self.ls("new"), self.ls("cur")), ([], []))

    def test_endpoint_broken_then_on_error_switch(self):
        self.parts["endpoint/default"] = {"path": OPENAI, "env": {"AOS_BRAIN_URL": DEAD, "AOS_BRAIN_MODEL": "m"}}
        self.save()
        self.assertEqual(self.step()[0], 0)
        code, err = self.step()
        self.assertEqual(code, 1)
        self.assertEqual(err_code("endpoint", err), "BrainFailed")                             # 格自己說、think 不轉述
        self.assertEqual((self.state(), self.states()[-1]), ("think", ("think", 1, None)))
        self.assertEqual([m["role"] for m in self.history()], ["user"])
        self.parts["endpoint/fake"] = {"path": FAKE}
        self.hook("on_error", 'read line; case "$line" in "endpoint: BrainFailed "*) echo switch;; esac\n')
        self.assertEqual(self.steps(5), [0, 0, 0, 0, 10])
        self.assertEqual((self.stack / "endpoint.txt").read_text(), "fake\n")
        self.assertTrue(self.answer().startswith("FAKE ANSWER to: 幾點？"))
        self.assertEqual(self.ls("cur"), [])

    def test_retry_has_a_limit(self):
        self.parts["endpoint/default"] = {"path": OPENAI, "env": {"AOS_BRAIN_URL": DEAD, "AOS_BRAIN_MODEL": "m"}}
        self.hook("on_error", "cat > /dev/null; echo retry\n")
        self.step()
        code, err = self.step(env={"AOS_ROUND_MAX_RETRIES": "2"})
        self.assertEqual((code, err_code("round/think", err)), (1, "EndpointFailed"))
        self.assertEqual(err.count("endpoint: BrainFailed"), 3)                                  # 1 次＋重來 2 次
        self.assertEqual(self.state(), "think")
        self.assertFalse((self.stack / "endpoint.txt").exists())

    def test_crash_resume_act_with_nothing_to_run(self):
        """state 說 act、history 卻沒有待回的 tool_calls（交卷前、或工具都回了）＝act 退 0 去 think。"""
        (self.agent / "tools.json").write_text('{"tools": {}}')
        self.steps(2)                                                                          # idle、think（答了）→ finish
        (self.stack / "state.txt").write_text("act\n")
        self.assertEqual(self.step()[0], 0)
        self.assertEqual((self.state(), self.states()[-1]), ("think", ("act", 0, "think")))
        self.assertEqual(self.steps(3), [0, 0, 10])                                             # think 不再問腦、退 10 → finish → idle
        self.assertEqual([m["role"] for m in self.history()], ["user", "assistant"])
        self.assertEqual(self.ls("cur"), [])

    def test_crash_resume_act_after_tools_answered(self):
        self.steps(3)                                                                          # idle、think、act（clock 回了）→ think
        (self.stack / "state.txt").write_text("act\n")
        self.assertEqual(self.step()[0], 0)
        self.assertEqual(self.state(), "think")
        self.assertEqual([m["role"] for m in self.history()], ["user", "assistant", "tool"])     # 工具沒再跑一次
        self.assertEqual(self.steps(3), [0, 0, 10])
        self.assertTrue(self.answer().startswith("FAKE ANSWER to: 幾點？（clock said:"))

    def test_idle_table_catches_10(self):
        (self.agent / "tools.json").write_text('{"tools": {}}')
        self.assertEqual(self.steps(3), [0, 0, 0])
        before = (self.stack / "history.jsonl").read_text()
        self.assertEqual(self.step(table="fsm-idle.json"), (0, ""))
        self.assertEqual((self.state(), self.states()[-1]), ("idle", ("idle", 10, "idle")))
        self.assertEqual((self.stack / "history.jsonl").read_text(), before)
        q2 = self.put("第二題")
        self.assertEqual(self.steps(3, table="fsm-idle.json"), [0, 0, 0])
        self.assertEqual(self.answer(), "FAKE ANSWER to: 第二題")
        self.assertNotIn(q2, self.ls("new") + self.ls("cur"))

    def test_system_and_tools_in_request(self):
        """system.txt 每次帶進請求、不進 history；tools.json → OpenAI tools（從舊 Round 類搬來）。"""
        (self.agent / "system.txt").write_text("你是測試")
        log = self.tmp / "req.log"
        self.parts["endpoint/default"] = {"path": self.script("rec", 'tee -a "%s" | exec aos-exec "%s" "$1"\n' % (log, FAKE))}
        self.save()
        self.assertEqual(self.steps(6), [0, 0, 0, 0, 0, 10])
        first = self.lines(log.read_text())[0]
        self.assertEqual(first["messages"][0], {"role": "system", "content": "你是測試"})
        self.assertEqual(first["tools"][0]["function"]["name"], "clock")
        self.assertEqual([m["role"] for m in self.history()], ["user", "assistant", "tool", "assistant"])

    def test_resume_claim_does_not_answer_with_old_answer(self):
        """第一題答完後，claim 死在搬進 cur/ 之後：idle 補認領（不叫 pre_round），不拿 history 裡上一題的答案交卷（從舊 Round 類搬來）。"""
        self.assertEqual(self.steps(6)[-1], 10)
        q2 = self.put("第二題")
        subprocess.run([tool("aos-post"), "claim", str(self.stack / "queue")], capture_output=True, env=self.env(), check=True)
        self.hook("pre_round", "exit 3\n")
        self.assertEqual(self.steps(6), [0, 0, 0, 0, 0, 10])
        self.assertTrue(self.answer().startswith("FAKE ANSWER to: 第二題"), self.answer())
        self.assertEqual([m["content"] for m in self.history() if m["role"] == "user"], ["幾點？", "第二題"])
        self.assertEqual(self.ls("cur"), [])
        self.assertNotIn(q2, self.ls("new"))

    def test_resume_claim_does_not_call_pre_round(self):
        subprocess.run([tool("aos-post"), "claim", str(self.stack / "queue")], capture_output=True, env=self.env(), check=True)
        self.hook("pre_round", "exit 3\n")
        self.assertEqual(self.step(), (0, ""))                                                  # 補認領
        self.assertEqual([m["content"] for m in self.history()], ["幾點？"])
        self.assertEqual(self.ls("cur"), [self.q1])

    def test_pre_round_fails(self):
        self.hook("pre_round", "exit 3\n")
        self.assertEqual(self.step()[0], 3)
        self.assertEqual((self.state(), self.ls("new"), self.history()), ("", [self.q1], []))     # state 沒寫過

    def test_own_errors(self):
        del self.parts["act"]
        self.save()
        self.steps(2)
        code, err = self.step()
        self.assertEqual((code, err_code("round/act", err), self.state()), (1, "PartMissing", "act"))
        (self.stack / "state.txt").write_text("think\n")
        code, err = self.step(env={"AOS_ROUND_MAX_RETRIES": "-1"})
        self.assertEqual((code, err_code("round/think", err), self.state()), (1, "SettingBad", "think"))
        r = subprocess.run([EXEC, str(Path(ROUND) / "more"), "agent"], capture_output=True, text=True, env=self.env(),
                           cwd=self.tmp, timeout=60)
        self.assertEqual((r.returncode, err_code("round/more", r.stderr)), (1, "AgentBad"))


if __name__ == "__main__":
    unittest.main()
