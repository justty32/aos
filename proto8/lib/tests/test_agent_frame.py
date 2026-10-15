"""proto8/lib 的自動測試：frame（lookup／intake／done，C-46）與 agent 當函數／當工具（定義資料夾＋frame，C-46／C-50）。
只用標準庫（10-15 晚從 test_agent.py 拆出來）：

    python3 -m unittest discover -s proto8/lib/tests

agent 當函數＝在 frame 裡跑定義資料夾的 loop.json。PATH 照 helpers.ENV。
"""
import json
import os
import subprocess
import sys

from helpers import ENV, LIB, Tmp, tree_hash

AGENT = os.path.join(LIB, "aos_agent_lib.py")


class AgentFrameTest(Tmp):
    """10-15 收工後的 frame：lookup()（frame → env.json parent 鏈）、intake、done（C-46）。"""

    def run_cell(self, cmd, cwd, *extra):
        return subprocess.run([sys.executable, AGENT, cmd] + list(extra), cwd=cwd, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=10)

    def test_lookup_chain_and_dir_merge(self):
        import aos_agent_lib
        self.write("def/brain.json", {"argv": ["x"]})
        self.write("def/tools/clock.json", {"argv": ["c"]})
        self.write("def/tools/t.json", {"argv": ["t0"]})
        self.write("fr/env.json", {"parent": "../def"})
        self.write("fr/tools/t.json", {"argv": ["t1"]})                      # 同名蓋過
        self.write("fr/tools/extra.json", {"argv": ["e"]})                   # 追加
        fr = self.p("fr")
        self.assertEqual(aos_agent_lib.chain(fr), [os.path.realpath(fr), os.path.realpath(self.p("def"))])
        self.assertEqual(aos_agent_lib.lookup("brain.json", fr), os.path.join(os.path.realpath(self.p("def")), "brain.json"))
        self.assertIsNone(aos_agent_lib.lookup("nope", fr))
        tools = aos_agent_lib.lookup_dir("tools", fr)
        self.assertEqual(sorted(tools), ["clock.json", "extra.json", "t.json"])
        self.assertTrue(tools["t.json"].startswith(os.path.realpath(fr)))
        self.write("def/env.json", {"parent": "../fr"})                       # 繞圈：停
        self.assertEqual(len(aos_agent_lib.chain(fr)), 2)

    def test_intake_think_route_done_in_frame(self):
        self.write("def/brain.py", "import json, sys\nreq = json.load(sys.stdin)\n"
                   "print(json.dumps({'role': 'assistant', 'content': 'n=%d' % len(req['messages'])}))\n")
        self.write("def/brain.json", {"argv": [sys.executable, self.p("def", "brain.py")]})
        self.write("def/system.md", "簡短")
        self.write("fr/env.json", {"parent": "../def"})
        self.write("fr/args.json", {"question": "幾點"})
        fr = self.p("fr")
        r = self.run_cell("intake", fr)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(self.read("fr/history.json")), [{"role": "user", "content": "幾點"}])
        r = self.run_cell("think", fr)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(self.read("fr/history.json"))[-1]["content"], "n=2")   # system＋user
        r = self.run_cell("route", fr, "--done", "done")
        self.assertEqual(json.loads(r.stdout)["next"], "done")
        r = self.run_cell("done", fr)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(self.read("fr/ret.json")), {"reply": "n=2"})
        self.assertFalse(os.path.exists(self.p("fr", "ctl.json")))           # done 不碰 ctl
        self.write("fr/work/think-fails.json", {"n": 3, "error": {"code": "BrainFailed", "msg": "x"}})
        self.run_cell("done", fr)
        self.assertEqual(json.loads(self.read("fr/ret.json")), {"error": {"code": "BrainFailed", "msg": "x"}})

    def test_fsm_subcommand_looks_up_table(self):
        # aos agent fsm：照 env.json 的 parent 鏈找 fsm.json，格名字從它所在的資料夾算、state 窗從 frame 算
        self.write("def/fsm.json", {"start": "a", "state": "st.json", "states": {"a": "cells/a.json"}})
        self.write("def/cells/a.json", {"argv": ["sh", "-c", "echo '{\"data\": 1}'"]})
        self.write("fr/env.json", {"parent": "../def"})
        r = subprocess.run(["aos", "agent", "fsm"], cwd=self.p("fr"), env=ENV, capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(self.read("fr/st.json")), {"phase": "a"})
        r = subprocess.run(["aos", "agent", "fsm", "nope.json"], cwd=self.p("fr"), env=ENV, capture_output=True,
                           text=True, timeout=10)
        self.assertEqual((r.returncode, json.loads(r.stderr)["error"]["code"]), (125, "NoFsm"))

    def test_intake_continues_same_frame(self):
        # 同一個 frame 續聊：已經有 history、又來新的 args.json＝接在後面當新的 user 訊息；接完改名，不會接兩次
        self.write("fr/history.json", [{"role": "user", "content": "綁好的"}, {"role": "assistant", "content": "好"}])
        self.write("fr/args.json", {"question": "再問一句"})
        fr = self.p("fr")
        for _ in range(2):
            self.assertEqual(self.run_cell("intake", fr).returncode, 0)
        self.assertEqual([m["content"] for m in json.loads(self.read("fr/history.json"))], ["綁好的", "好", "再問一句"])
        self.assertFalse(os.path.exists(self.p("fr", "args.json")))
        self.assertEqual(json.loads(self.read("fr/args.taken.json")), {"question": "再問一句"})
        self.write("fr/ret.json", {"reply": "上一輪"})
        self.write("fr/args.json", {"question": "第三句"})                  # 接新問題時清掉上一輪的 ret.json
        self.run_cell("intake", fr)
        self.assertFalse(os.path.exists(self.p("fr", "ret.json")))
        self.write("fr/history.json", [{"role": "user", "content": "綁好的"}, {"role": "assistant", "content": "好"},
                                       {"role": "user", "content": "再問一句"}])
        self.write("fr/args.json", {"question": "再問一句"})            # 上一拍接好了、改名前被殺：不重複接
        self.run_cell("intake", fr)
        self.assertEqual(len(json.loads(self.read("fr/history.json"))), 3)
        self.write("fr/args.json", {"history": [{"role": "user", "content": "整段換掉"}]})
        self.run_cell("intake", fr)
        self.assertEqual(json.loads(self.read("fr/history.json")), [{"role": "user", "content": "整段換掉"}])
        os.makedirs(self.p("empty"))
        r = self.run_cell("intake", self.p("empty"))
        self.assertEqual((r.returncode, json.loads(r.stderr)["error"]["code"]), (1, "NoHistory"))


BRAIN_PY = """import json, sys, time
req = json.load(sys.stdin)
msgs = [m for m in req["messages"] if m["role"] != "system"]
last = msgs[-1]
names = sorted(t["function"]["name"] for t in req.get("tools", []))
first = msgs[0].get("content")
if first == "fail":
    print(json.dumps({"error": {"code": "Boom", "msg": "壞了"}}), file=sys.stderr)
    sys.exit(1)
if first == "slow":
    time.sleep(0.5)
looping = "loop" in [m.get("content") for m in msgs if m["role"] == "user"]
if (looping or last.get("content") == "use t") and last["role"] != "assistant":
    out = {"role": "assistant", "content": "還在想", "tool_calls": [
        {"id": "c%d" % len(msgs), "type": "function", "function": {"name": "t", "arguments": "{}"}}]}
else:
    out = {"role": "assistant", "content": json.dumps({"argv": sys.argv[1:], "tools": names, "n": len(msgs)})}
print(json.dumps(out))
"""


class AgentCallTest(Tmp):
    """agent 當函數（C-46／C-50）：定義資料夾 bob/ 不動；frame＝被叫者的 cwd（env.json 指回 bob/、args.json、ret.json）；
    在 frame 放同名檔＝綁定（腦、追加工具）；agent 當工具＝工具 inst 用 sh 三步叫另一個 agent。"""

    def setUp(self):
        super().setUp()
        self.write("bob/brain.py", BRAIN_PY)
        self.write("bob/brain.json", {"argv": [sys.executable, self.p("bob", "brain.py")]})
        self.write("bob/tools/t.json", {"argv": ["sh", "-c", "cat; echo"], "_tool": {"description": "回聲"}})
        self.write("bob/fsm.json", {"start": "intake", "state": "fsm-state.json", "end": ["done", "halted"], "states": {
            "intake": {"target": "cells/intake.json", "next": "thinking"},
            "thinking": {"target": "cells/think.json", "next": "route"},
            "route": "cells/route.json", "tool": {"target": "cells/tool.json", "next": "thinking"},
            "done": "cells/done.json", "halted": "cells/done.json"}})
        for k, argv in (("intake", ["intake"]), ("think", ["think"]), ("route", ["route", "--done", "done"]),
                        ("tool", ["tool"]), ("done", ["done"])):
            self.write("bob/cells/%s.json" % k, {"argv": ["aos", "agent"] + argv})
        self.write("bob/loop.json", {"inst": {"argv": ["aos", "agent", "fsm"]}, "times": 20, "stop_on_end": True,
                                     "ctl": "ctl.json", "state": "loop-state.json"})

    def start(self, frame, q, times=None):
        """呼叫：在 frame 寫 env.json、args.json，cd 過去跑 bob 的 loop.json（不等）。"""
        self.write(frame + "/env.json", {"parent": self.p("bob")})
        self.write(frame + "/args.json", {"question": q})
        flags = ["--times", str(times)] if times else []
        return subprocess.Popen(["aos", "loop"] + flags + [self.p("bob", "loop.json")], cwd=self.p(frame), env=ENV,
                                stdout=subprocess.DEVNULL)

    def ret(self, frame):
        return json.loads(self.read(frame + "/ret.json"))

    def call(self, frame, q, **kw):
        p = self.start(frame, q, **kw)
        self.assertEqual(p.wait(30), 0)
        r = self.ret(frame)
        return r, json.loads(r["reply"]) if isinstance(r.get("reply"), str) else None

    def test_bob_untouched_frames_hold_history(self):
        before = tree_hash(self.p("bob"))
        r, out = self.call("f1", "use t")
        self.call("f2", "hi")
        self.assertEqual(tree_hash(self.p("bob")), before)
        self.assertEqual([m["role"] for m in json.loads(self.read("f1/history.json"))],
                         ["user", "assistant", "tool", "assistant"])
        self.assertEqual(len(json.loads(self.read("f2/history.json"))), 2)
        self.assertEqual((out["tools"], out["n"]), (["t"], 3))
        st = json.loads(self.read("f1/loop-state.json"))
        self.assertEqual((st["state"], st["runs"]), ("done", 7))           # fsm 結束＝loop 正常結束（stop_on_end）         # intake think route tool think route done
        self.assertEqual(json.loads(self.read("f1/fsm-state.json")), {"phase": "intake"})    # 走完 end 歸位
        self.assertEqual(json.loads(self.read("f1/work/1/args.json")), {})   # 工具 t 在 work/1/ 跑

    def test_same_frame_continues(self):
        # 同一個 frame 再叫一次＝接著那裡的 history；呼叫方不用刪東西（intake 清上一輪的 ret.json，loop 不靠 ctl 停）
        self.call("f", "hi")
        _, out = self.call("f", "再一句")
        self.assertEqual(out["n"], 3)
        self.assertEqual([m["content"] for m in json.loads(self.read("f/history.json"))][2], "再一句")

    def test_bindings_in_frame(self):
        # frame 裡放同名檔＝綁定：tools/ 逐項合併（追加）、brain.json 蓋過 bob 的
        self.write("f/tools/u.json", {"argv": ["true"]})
        self.write("f/brain.json", {"argv": [sys.executable, self.p("bob", "brain.py"), "--model", "m2"]})
        _, out = self.call("f", "hi")
        self.assertEqual((out["tools"], out["argv"]), (["t", "u"], ["--model", "m2"]))

    def test_halted_writes_error_ret(self):
        _, out = self.call("f", "fail")
        r = self.ret("f")
        self.assertEqual(r["error"]["code"], "BrainFailed")                  # N-29 形狀
        self.assertIn("Boom", r["error"]["msg"])
        self.assertEqual(len(json.loads(self.read("f/history.json"))), 1)
        self.assertEqual(json.loads(self.read("f/loop-state.json"))["runs"], 5)   # intake、think×3（第 3 次回 halted）、halted

    def test_times_used_up_no_ret(self):
        # 一直叫工具：loop 的 times 用完還沒走到 done＝沒有 ret.json（沒跑完）
        self.call("f", "hi")
        p = self.start("f", "loop", times=6)                                   # 上一輪的 ret.json 由 intake 清掉
        self.assertEqual(p.wait(30), 0)
        self.assertFalse(os.path.exists(self.p("f", "ret.json")))

    def test_two_frames_concurrently(self):
        a, b = self.start("f1", "slow"), self.start("f2", "slow")
        self.assertEqual((a.wait(30), b.wait(30)), (0, 0))
        self.assertEqual((self.ret("f1")["reply"] is not None, self.ret("f2")["reply"] is not None), (True, True))

    def test_agent_as_tool(self):
        # boss 的工具 bob.json＝sh 三步（寫 env.json → 跑 bob 的 loop → 讀 ret.json），frame＝boss 的 work/<n>/
        import shutil
        shutil.copytree(self.p("bob"), self.p("boss"), ignore=shutil.ignore_patterns("tools"))
        self.write("boss/tools/bob.json", {"argv": ["sh", "-c",
            "printf '{\"parent\": \"%s\"}' \"$BOB\" > env.json && aos loop \"$BOB/loop.json\" >/dev/null; cat ret.json"],
            "envs": {"BOB": self.p("bob")}, "timeout_ms": 30000,
            "_tool": {"description": "問 bob", "parameters": {"type": "object", "properties": {"question": {"type": "string"}}}}})
        self.write("boss/brain.py", BRAIN_PY.replace('"t"', '"bob"').replace(
            '"arguments": "{}"', '"arguments": json.dumps({"question": "hi"})'))
        self.write("boss/brain.json", {"argv": [sys.executable, self.p("boss", "brain.py")]})
        self.write("f/env.json", {"parent": self.p("boss")})
        self.write("f/args.json", {"question": "use t"})
        self.assertEqual(subprocess.run(["aos", "loop", self.p("boss", "loop.json")], cwd=self.p("f"), env=ENV,
                                        stdout=subprocess.DEVNULL, timeout=60).returncode, 0)
        sub = json.loads(self.read("f/work/1/ret.json"))                     # bob 在 boss 的 work/1/ 跑
        self.assertEqual(json.loads(sub["reply"])["n"], 1)
        tool_msg = json.loads(json.loads(self.read("f/history.json"))[2]["content"])
        self.assertEqual(tool_msg["result"], sub)


JUDGE_BRAIN_PY = r"""
import json, sys
req = json.load(sys.stdin)
print(json.dumps({"role": "assistant", "content": "好的：" + json.dumps({"run": ["L1"], "defer": [], "reject": []})}))
"""


class AskJudgeTest(Tmp):
    """demo/kernel2/judge/ask_judge.py 收定義資料夾當引數（10-15「都按照推薦」：不再寫死 judge/）：
    另開一個資料夾放 brain.json＋env.json 指回 judge/＝換腦，judge/ 一個字不動。"""

    def test_overlay_definition_swaps_brain(self):
        judge = os.path.join(LIB, "..", "demo", "kernel2", "judge")
        before = tree_hash(judge)
        self.write("over/brain.py", JUDGE_BRAIN_PY)
        self.write("over/brain.json", {"argv": [sys.executable, self.p("over", "brain.py")]})
        self.write("over/env.json", {"parent": os.path.abspath(judge)})
        r = subprocess.run(["aos-demo", "kernel2/judge/ask_judge.py", "over"], cwd=self.tmp, env=ENV, input="{}",
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout), {"run": ["L1"], "defer": [], "reject": []})
        self.assertEqual(tree_hash(judge), before)
        r = subprocess.run(["aos-demo", "kernel2/judge/ask_judge.py", "nope"], cwd=self.tmp, env=ENV, input="{}",
                           capture_output=True, text=True, timeout=10)
        self.assertEqual((r.returncode, json.loads(r.stderr)["error"]["code"]), (1, "NoDefinition"))
