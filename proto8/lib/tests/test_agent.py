"""proto8/lib 的自動測試：agent 的現成格庫（aos_agent_lib）、agent 當函數／當工具（定義資料夾＋frame，C-46／C-50），
與真的腦（aos_brain_openai、aos_brain_ollama）。只用標準庫：

    python3 -m unittest discover -s proto8/lib/tests

整圈用 demo/fsm 那套（假的腦）：在暫存 frame（env.json 指回 demo/fsm）一拍一拍敲 `aos agent fsm`；
agent 當函數＝在 frame 裡跑定義資料夾的 loop.json；真的腦對一個本機假伺服器（http.server）。PATH 照 helpers.ENV。
"""
import http.server
import json
import os
import socket
import subprocess
import sys
import threading

from helpers import ENV, FSM, LIB, Tmp, tree_hash

AGENT = os.path.join(LIB, "aos_agent_lib.py")
BRAIN = os.path.join(LIB, "aos_brain_openai.py")
OLLAMA = os.path.join(LIB, "aos_brain_ollama.py")
DEMO = os.path.realpath(os.path.join(LIB, "..", "demo", "fsm"))


class AgentRoundTest(Tmp):
    """demo/fsm 這個定義資料夾：idle → thinking（ask → review）→ tool → thinking → idle；frame＝暫存資料夾。"""

    def setUp(self):
        super().setUp()
        os.makedirs(self.p("inbox"))
        self.write("env.json", {"parent": DEMO})

    def round(self, text, ticks=8):
        self.write("inbox/01.txt", text)
        steps = []
        for _ in range(ticks):
            r = subprocess.run(["aos", "agent", "fsm"], cwd=self.tmp, env=ENV, capture_output=True, text=True, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
            steps.append(json.loads(r.stdout.splitlines()[0]))
            if os.path.exists(self.p("outbox.txt")):
                break
        return steps, json.loads(self.read("history.json"))

    def test_full_round_with_tool(self):
        # 外層的工具只有 clerk（報時員＝另一個 agent）：外層叫 clerk，clerk 在 work/1/（工具呼叫的 frame）裡叫 clock
        steps, hist = self.round("現在幾點？")
        self.assertEqual([(s["from"], s["to"]) for s in steps],
                         [("idle", "thinking"), ("thinking", "thinking"), ("thinking", "tool"),
                          ("tool", "thinking"), ("thinking", "thinking"), ("thinking", "idle")])
        self.assertEqual([m["role"] for m in hist], ["user", "assistant", "tool", "assistant"])
        call = hist[1]["tool_calls"][0]
        self.assertEqual((call["type"], call["function"]["name"]), ("function", "clerk"))
        self.assertEqual(json.loads(call["function"]["arguments"]), {"question": "現在幾點？"})
        self.assertEqual(hist[2]["tool_call_id"], call["id"])
        res = json.loads(hist[2]["content"])                                   # N-30 結果＋result（＝clerk 的 ret.json）
        self.assertEqual((res["code"], res["signal"], res["timed_out"]), (0, None, False))
        self.assertTrue(res["result"]["reply"].startswith("現在是 "))
        self.assertTrue(self.read("outbox.txt").startswith("報時員說：" + res["result"]["reply"]))
        self.assertEqual(json.loads(self.read("work/1/args.taken.json")), {"question": "現在幾點？"})   # 引數→clerk 接走
        self.assertEqual(json.loads(self.read("work/1/env.json")), {"parent": os.path.join(DEMO, "clerk")})
        sub = json.loads(self.read("work/1/history.json"))                    # clerk 的 frame
        self.assertEqual([m["role"] for m in sub], ["user", "assistant", "tool", "assistant"])
        self.assertEqual(sub[1]["tool_calls"][0]["function"]["name"], "clock")
        self.assertEqual(json.loads(self.read("work/1/ret.json")), res["result"])
        self.assertEqual(json.loads(self.read("work/1/loop-state.json"))["state"], "done")   # fsm 結束＝clerk 的 loop 停
        self.assertFalse(os.path.exists(self.p("work", "1", "ctl.json")))     # 不靠 ctl

    def test_clerk_reused_definition_untouched(self):
        clerk = os.path.join(DEMO, "clerk")
        before = tree_hash(clerk)
        self.round("現在幾點？")
        os.remove(self.p("outbox.txt"))
        self.round("幾點了？")
        self.assertEqual(sorted(n for n in os.listdir(self.p("work")) if n.isdigit()), ["1", "2"])
        self.assertEqual(json.loads(self.read("work/2/history.json"))[0]["content"], "幾點了？")
        self.assertEqual(tree_hash(clerk), before)

    def test_unknown_tool_goes_back_to_model(self):
        steps, hist = self.round("亂叫一個")
        self.assertEqual(steps[-1]["to"], "idle")
        self.assertTrue(all("error" not in s for s in steps))                # 不是 fsm 的錯
        self.assertEqual(json.loads(hist[2]["content"])["error"]["code"], "UnknownTool")   # N-29 形狀

    def test_empty_inbox_done_stops(self):
        # inbox 空了＝idle 回 next done：done 格寫 ret.json，fsm 結束（那行帶 end、phase 歸位 idle）
        r = subprocess.run(["aos", "agent", "fsm"], cwd=self.tmp, env=ENV, capture_output=True, text=True, timeout=30)
        self.assertEqual(json.loads(r.stdout.splitlines()[0])["to"], "done")
        r = subprocess.run(["aos", "agent", "fsm"], cwd=self.tmp, env=ENV, capture_output=True, text=True, timeout=30)
        out = [json.loads(x) for x in r.stdout.splitlines()]
        self.assertEqual((out[0]["end"], out[-1]), (True, {"data": {"reply": None}}))
        self.assertEqual(json.loads(self.read("fsm-state.json")), {"phase": "idle"})


class AgentSystemTest(Tmp):
    """system 提示檔：第一則 system 訊息、不進 history、檔不存在＝格出錯。"""

    def setUp(self):
        super().setUp()
        self.write("brain.py", "import json, sys\nreq = json.load(sys.stdin)\n"
                   "open('seen.json', 'w').write(json.dumps(req))\n"
                   "print(json.dumps({'role': 'assistant', 'content': 'ok'}))\n")
        self.write("brain.json", {"argv": ["python3", "brain.py"]})
        self.write("h.json", [{"role": "user", "content": "hi"}])
        self.cfg = {"brain": "brain.json", "tools": {}, "history": "h.json", "work": "work"}

    def think(self, cfg):
        return subprocess.run([sys.executable, AGENT, "think"], cwd=self.tmp, input=json.dumps(cfg),
                              capture_output=True, text=True, timeout=30)

    def test_system_first_and_not_in_history(self):
        self.write("system.md", "用繁體中文")
        r = self.think(dict(self.cfg, system="system.md"))
        self.assertEqual(r.returncode, 0, r.stderr)
        seen = json.loads(self.read("seen.json"))["messages"]
        self.assertEqual(seen[0], {"role": "system", "content": "用繁體中文"})
        self.assertEqual(seen[1]["role"], "user")
        self.assertEqual([m["role"] for m in json.loads(self.read("h.json"))], ["user", "assistant"])

    def test_no_system_key_no_system_message(self):
        r = self.think(self.cfg)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([m["role"] for m in json.loads(self.read("seen.json"))["messages"]], ["user"])

    def test_missing_system_file_is_cell_error(self):
        r = self.think(dict(self.cfg, system="nope.md"))
        self.assertEqual(r.returncode, 1)
        self.assertEqual(json.loads(r.stderr.strip().splitlines()[-1])["error"]["code"], "SystemUnreadable")
        self.assertEqual(len(json.loads(self.read("h.json"))), 1)


class AgentCellTest(Tmp):
    """直接敲 aos_agent_lib.py tool（stdin＝設定）：一次多個 tool_calls、被中斷、沒設定。"""

    def setUp(self):
        super().setUp()
        self.write("tools/echo.json", {"argv": ["sh", "-c", "cat; pwd > where.txt"], "_tool": {"description": "回聲"}})
        self.cfg = {"brain": "brain.json", "tools": {"echo": "tools/echo.json"}, "history": "h.json", "work": "work"}

    def calls(self, *names):
        tc = [{"id": "c%d" % i, "type": "function", "function": {"name": n, "arguments": '{"x": %d}' % i}}
              for i, n in enumerate(names)]
        self.write("h.json", [{"role": "user", "content": "hi"}, {"role": "assistant", "content": None, "tool_calls": tc}])

    def tool(self, cfg=True):
        arg = self.cfg if cfg else []
        return subprocess.run([sys.executable, AGENT, "tool"], cwd=self.tmp, capture_output=True,
                              text=True, input=json.dumps(arg), timeout=10)

    def test_no_cfg_is_cell_error(self):
        self.calls("echo")
        r = self.tool(cfg=False)
        self.assertEqual((r.returncode, json.loads(r.stderr)["error"]["code"]), (1, "NoConfig"))

    def test_multiple_tool_calls_runs_first_only(self):
        self.calls("echo", "echo", "nope")
        r = self.tool()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stderr.splitlines()[0])["warning"]["code"], "ToolCallsSkipped")
        hist = json.loads(self.read("h.json"))
        self.assertEqual([m.get("tool_call_id") for m in hist[2:]], ["c0", "c1", "c2"])   # 每個 id 都有回
        res = json.loads(hist[2]["content"])                                          # N-30 結果＋result
        self.assertEqual((res["code"], res["result"], res["id"]), (0, {"x": 0}, self.p("tools", "echo.json")))
        self.assertEqual([json.loads(m["content"])["error"]["code"] for m in hist[3:]], ["Skipped"] * 2)
        self.assertEqual(self.tool().stdout.strip(), '{"data": {"tool": null}}')    # 都回過了＝什麼都不跑

    def test_each_call_in_new_numbered_folder(self):
        # 工具每次在 work/<n>/ 新資料夾跑（C-46 工具呼叫的 frame 預設），引數寫成那裡的 args.json
        for i in range(2):
            self.calls("echo")
            self.assertEqual(self.tool().returncode, 0)
        for n in ("1", "2"):
            self.assertEqual(json.loads(self.read("work/%s/args.json" % n)), {"x": 0})
            self.assertEqual(self.read("work/%s/where.txt" % n).strip(), os.path.realpath(self.p("work", n)))
        self.write("tools/echo.json", {"argv": ["sh", "-c", "cat; pwd > where.txt"], "cwd": self.tmp})   # inst 自己寫了 cwd＝照它
        self.calls("echo")
        self.tool()
        self.assertTrue(os.path.exists(self.p("where.txt")))
        self.assertTrue(os.path.exists(self.p("work", "3", "args.json")))

    def test_interrupted_tool_not_rerun(self):
        self.calls("echo")
        self.write("work/.tool-running.json", {"id": "c0"})                  # 上一拍跑到一半被殺
        r = self.tool()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(json.loads(self.read("h.json"))[-1]["content"])["error"]["code"], "Interrupted")
        self.assertEqual(os.listdir(self.p("work")), [])                    # 沒跑工具、記號刪了

    def test_tool_specs_from_inst(self):
        import aos_agent_lib
        cwd = os.getcwd()
        os.chdir(self.tmp)
        try:
            specs = aos_agent_lib.tool_specs({"echo": "tools/echo.json"})
        finally:
            os.chdir(cwd)
        self.assertEqual(specs, [{"type": "function", "function": {
            "name": "echo", "description": "回聲", "parameters": {"type": "object", "properties": {}}}}])


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


class _Stub(http.server.BaseHTTPRequestHandler):
    seen, reply, status = [], None, 200

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).seen.append((self.path, dict(self.headers), body))
        raw = json.dumps(type(self).reply).encode()
        self.send_response(type(self).status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *a):
        pass


class BrainOpenaiTest(Tmp):
    def setUp(self):
        super().setUp()
        _Stub.seen, _Stub.status = [], 200
        _Stub.reply = {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
            {"id": "call_x", "type": "function", "function": {"name": "clock", "arguments": "{}"}}]}}]}
        self.srv = http.server.HTTPServer(("127.0.0.1", 0), _Stub)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)
        self.url = "http://127.0.0.1:%d/v1" % self.srv.server_port

    def brain(self, req, *flags, env=None):
        return subprocess.run([sys.executable, BRAIN, "--base-url", self.url, "--model", "m1"] + list(flags),
                              input=json.dumps(req), capture_output=True, text=True, timeout=10,
                              env=dict(os.environ, **(env or {})))

    def test_request_has_tools_and_reply_parsed(self):
        tools = [{"type": "function", "function": {"name": "clock", "description": "", "parameters": {}}}]
        r = self.brain({"messages": [{"role": "user", "content": "幾點"}], "tools": tools})
        self.assertEqual(r.returncode, 0, r.stderr)
        path, headers, body = _Stub.seen[0]
        self.assertEqual(path, "/v1/chat/completions")
        self.assertEqual((body["model"], body["tools"]), ("m1", tools))
        self.assertNotIn("Authorization", headers)
        out = json.loads(r.stdout)
        self.assertEqual(out["role"], "assistant")
        self.assertEqual(out["tool_calls"][0]["function"], {"name": "clock", "arguments": "{}"})

    def test_api_key_from_env(self):
        r = self.brain({"messages": []}, "--api-key-env", "AOS_TEST_KEY", env={"AOS_TEST_KEY": "sk-1"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(_Stub.seen[0][1]["Authorization"], "Bearer sk-1")

    def test_http_and_connect_errors(self):
        _Stub.status = 500
        r = self.brain({"messages": []})
        self.assertEqual((r.returncode, json.loads(r.stderr)["error"]["code"]), (1, "HttpError"))
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        self.url = "http://127.0.0.1:%d/v1" % s.getsockname()[1]          # 綁了又關＝沒人聽
        s.close()
        r = self.brain({"messages": []}, "--timeout-ms", "3000")
        self.assertEqual((r.returncode, json.loads(r.stderr)["error"]["code"]), (1, "ConnectFailed"))

    def test_usage_passed_through(self):
        _Stub.reply = dict(_Stub.reply, usage={"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7})
        out = json.loads(self.brain({"messages": []}).stdout)
        self.assertEqual((out["role"], out["usage"]["total_tokens"]), ("assistant", 7))

    def test_think_cell_through_real_brain(self):
        _Stub.reply = {"choices": [{"message": {"role": "assistant", "content": "好"}}], "usage": {"total_tokens": 3}}
        self.write("brain.json", {"argv": [sys.executable, BRAIN, "--base-url", self.url, "--model", "m1"]})
        self.write("tools/clock.json", {"argv": ["true"], "_tool": {"description": "時間"}})
        cfg = {"brain": "brain.json", "tools": {"clock": "tools/clock.json"}, "history": "h.json", "work": "work"}
        self.write("h.json", [{"role": "user", "content": "hi"}])
        r = subprocess.run([sys.executable, AGENT, "think"], cwd=self.tmp, input=json.dumps(cfg),
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(_Stub.seen[0][2]["tools"][0]["function"]["description"], "時間")
        self.assertEqual(json.loads(self.read("h.json"))[-1], {"role": "assistant", "content": "好"})   # usage 沒進 history
        self.assertEqual(json.loads(r.stdout), {"data": {"content": "好", "tool_calls": []}})


class BrainOllamaTest(BrainOpenaiTest):
    """ollama 原生 /api/chat：num_ctx、keep_alive、兩邊形狀的翻譯。沿用上面的假伺服器。"""

    def setUp(self):
        super().setUp()
        _Stub.reply = {"model": "m1", "done": True, "message": {"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "clock", "arguments": {"tz": "UTC"}}}]}}
        self.url = self.url[:-3]                                             # ollama 的 base_url 不含 /v1

    def ollama(self, req, *flags):
        return subprocess.run([sys.executable, OLLAMA, "--base-url", self.url, "--model", "m1"] + list(flags),
                              input=json.dumps(req), capture_output=True, text=True, timeout=10)

    def test_request_shape_and_reply_translated(self):
        tools = [{"type": "function", "function": {"name": "clock", "description": "", "parameters": {}}}]
        r = self.ollama({"messages": [{"role": "user", "content": "幾點"}], "tools": tools})
        self.assertEqual(r.returncode, 0, r.stderr)
        path, _, body = _Stub.seen[0]
        self.assertEqual(path, "/api/chat")
        self.assertEqual((body["model"], body["stream"], body["options"], body["keep_alive"], body["tools"]),
                         ("m1", False, {"num_ctx": 4096}, "30s", tools))
        out = json.loads(r.stdout)
        self.assertEqual((out["role"], out["content"]), ("assistant", None))      # 空字串 → null
        call = out["tool_calls"][0]
        self.assertTrue(call["id"].startswith("call_"))
        self.assertEqual((call["type"], call["function"]), ("function", {"name": "clock", "arguments": '{"tz": "UTC"}'}))

    def test_usage_from_eval_counts(self):
        _Stub.reply = dict(_Stub.reply, prompt_eval_count=10, eval_count=4)
        out = json.loads(self.ollama({"messages": []}).stdout)
        self.assertEqual(out["usage"], {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14})

    def test_usage_passed_through(self):
        pass                                    # openai 專屬；ollama 的在 test_usage_from_eval_counts

    def test_flags_and_history_translated(self):
        _Stub.reply = {"message": {"role": "assistant", "content": "現在 10 點"}}
        hist = [{"role": "user", "content": "幾點"},
                {"role": "assistant", "content": None, "tool_calls": [
                    {"id": "c9", "type": "function", "function": {"name": "clock", "arguments": '{"tz": "UTC"}'}}]},
                {"role": "tool", "tool_call_id": "c9", "content": "{\"time\": \"10:00\"}"}]
        r = self.ollama({"messages": hist}, "--num-ctx", "8192", "--keep-alive", "0")
        self.assertEqual(r.returncode, 0, r.stderr)
        body = _Stub.seen[0][2]
        self.assertEqual((body["options"]["num_ctx"], body["keep_alive"]), (8192, 0))
        self.assertNotIn("tools", body)
        a, t = body["messages"][1], body["messages"][2]
        self.assertEqual((a["content"], a["tool_calls"]), ("", [{"function": {"name": "clock", "arguments": {"tz": "UTC"}}}]))
        self.assertEqual((t["role"], t["tool_name"], t["tool_call_id"]), ("tool", "clock", "c9"))
        self.assertEqual(json.loads(r.stdout), {"role": "assistant", "content": "現在 10 點"})

    def test_http_and_bad_response(self):
        _Stub.status, _Stub.reply = 400, {"error": "m1 does not support tools"}
        r = self.ollama({"messages": []})
        err = json.loads(r.stderr)["error"]
        self.assertEqual((r.returncode, err["code"]), (1, "HttpError"))
        self.assertIn("does not support tools", err["msg"])
        _Stub.status, _Stub.reply = 200, {"nope": 1}
        r = self.ollama({"messages": []})
        self.assertEqual((r.returncode, json.loads(r.stderr)["error"]["code"]), (1, "BadResponse"))

    def test_no_tools_400_surfaces_and_stops(self):
        # 146 試跑的情形：腦回 400 → think 格 BrainFailed 帶原因 → fsm 那行的 error 看得到；
        # 10-15 收工後連錯停住是格自己的事（N-38）：think 錯第 3 次改回 next halted，之後不再打
        _Stub.status, _Stub.reply = 400, {"error": "m1 does not support tools"}
        self.write("brain.json", {"argv": [sys.executable, OLLAMA, "--base-url", self.url, "--model", "m1"]})
        self.write("tools/clock.json", {"argv": ["true"], "_tool": {"description": "時間"}})
        self.write("h.json", [{"role": "user", "content": "幾點"}])
        self.write("cfg.json", {"brain": "brain.json", "tools": {"clock": "tools/clock.json"},
                                "history": "h.json", "work": "work"})
        self.write("f.json", {"start": "ask", "state": "f.state.json", "states": {
            "ask": {"argv": [sys.executable, AGENT, "think"], "stdin": "cfg.json"},
            "halted": {"argv": ["sh", "-c", "echo '{}'"]}}})
        codes = []
        for _ in range(5):
            r = subprocess.run([sys.executable, FSM, "f.json"], cwd=self.tmp, capture_output=True, text=True, timeout=10)
            codes.append(r.returncode)
            if r.returncode:
                err = json.loads(r.stdout.splitlines()[-1])["error"]
                self.assertTrue(err["msg"].startswith("BrainFailed: HttpError: "), err)
                self.assertIn("does not support tools", err["msg"])
        self.assertEqual(codes, [1, 1, 0, 0, 0])
        self.assertEqual((json.loads(self.read("f.state.json"))["phase"], len(_Stub.seen)), ("halted", 3))
        self.assertEqual(json.loads(self.read("work/think-fails.json"))["n"], 3)

    def test_bad_num_ctx(self):
        r = self.ollama({"messages": []}, "--num-ctx", "big")
        self.assertEqual((r.returncode, json.loads(r.stderr)["error"]["code"]), (1, "FieldType"))

    # 父類別的 openai 專屬測試不重跑
    test_request_has_tools_and_reply_parsed = test_api_key_from_env = None
    test_http_and_connect_errors = test_think_cell_through_real_brain = None
