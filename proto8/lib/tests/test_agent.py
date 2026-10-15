"""proto8/lib 的自動測試：agent 的現成格庫（aos_agent_lib）與真的腦（aos_brain_openai、aos_brain_ollama）。只用標準庫：

    python3 -m unittest discover -s proto8/lib/tests

整圈用 demo/fsm 那套（假的腦），在暫存資料夾一拍一拍敲 aos_fsm；真的腦對一個本機假伺服器（http.server）。
"""
import http.server
import json
import os
import runpy
import socket
import subprocess
import sys
import threading

from helpers import FSM, LIB, Tmp, tree_hash

AGENT = os.path.join(LIB, "aos_agent_lib.py")
BRAIN = os.path.join(LIB, "aos_brain_openai.py")
OLLAMA = os.path.join(LIB, "aos_brain_ollama.py")
DEMO = os.path.join(LIB, "..", "demo", "fsm")


class AgentRoundTest(Tmp):
    """demo/fsm 的 agent.json：idle → thinking（ask → review）→ tool → thinking → idle。"""

    def setUp(self):
        super().setUp()
        for d in ("inbox", "work"):
            os.makedirs(self.p(d))
        self.env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", DEMO_DIR=self.tmp)
        self.agent = runpy.run_path(os.path.join(DEMO, "run.py"))["bind"](self.tmp)   # 同 demo：執行期的 key 填進副本

    def round(self, text, ticks=8):
        self.write("inbox/01.txt", text)
        steps = []
        for _ in range(ticks):
            r = subprocess.run([sys.executable, FSM, self.agent], cwd=DEMO, env=self.env,
                               capture_output=True, text=True, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr)
            steps.append(json.loads(r.stdout.splitlines()[-1]))
            if os.path.exists(self.p("outbox.txt")):
                break
        return steps, json.loads(self.read("work/history.json"))

    def test_full_round_with_tool(self):
        # 外層的工具只有 clerk（報時員＝另一個 agent）：外層叫 clerk，clerk 在自己的 frame 裡叫 clock
        steps, hist = self.round("現在幾點？")
        self.assertEqual([(s["from"], s["to"]) for s in steps],
                         [("idle", "thinking"), ("thinking", "thinking"), ("thinking", "tool"),
                          ("tool", "thinking"), ("thinking", "thinking"), ("thinking", "idle")])
        self.assertEqual([m["role"] for m in hist], ["user", "assistant", "tool", "assistant"])
        call = hist[1]["tool_calls"][0]
        self.assertEqual((call["type"], call["function"]["name"]), ("function", "clerk"))
        self.assertEqual(json.loads(call["function"]["arguments"]), {"question": "現在幾點？"})
        self.assertEqual(hist[2]["tool_call_id"], call["id"])
        res = json.loads(hist[2]["content"])                                   # N-30 結果＋result
        self.assertEqual((res["code"], res["signal"], res["timed_out"]), (0, None, False))
        self.assertTrue(res["result"]["reply"].startswith("現在是 "))
        self.assertTrue(self.read("outbox.txt").startswith("報時員說：" + res["result"]["reply"]))
        self.assertEqual(json.loads(self.read("work/2-call.json")), {"question": "現在幾點？"})
        sub = json.loads(self.read("work/ask-1/history.json"))                # clerk 的 frame
        self.assertEqual([m["role"] for m in sub], ["user", "assistant", "tool", "assistant"])
        self.assertEqual(sub[1]["tool_calls"][0]["function"]["name"], "clock")

    def test_clerk_reused_definition_untouched(self):
        clerk = os.path.join(DEMO, "clerk")
        before = tree_hash(clerk)
        self.round("現在幾點？")
        os.remove(self.p("outbox.txt"))
        self.round("幾點了？")
        self.assertEqual(sorted(n for n in os.listdir(self.p("work")) if n.startswith("ask-")), ["ask-1", "ask-2"])
        self.assertEqual(json.loads(self.read("work/ask-2/history.json"))[0]["content"], "幾點了？")
        self.assertEqual(tree_hash(clerk), before)

    def test_unknown_tool_goes_back_to_model(self):
        steps, hist = self.round("亂叫一個")
        self.assertEqual(steps[-1]["to"], "idle")
        self.assertTrue(all("error" not in s for s in steps))                # 不是 fsm 的錯
        self.assertEqual(json.loads(hist[2]["content"])["error"]["code"], "UnknownTool")   # N-29 形狀


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
        stdin = json.dumps(dict(cfg, fsm_state={"phase": "thinking", "step": 0, "running": False, "data": None}))
        return subprocess.run([sys.executable, AGENT, "think"], cwd=self.tmp, input=stdin,
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
    """直接敲 aos_agent_lib.py tool（stdin＝設定本身＋fsm_state）：一次多個 tool_calls、被中斷、沒設定。"""

    def setUp(self):
        super().setUp()
        self.write("tools/echo.json", {"argv": ["sh", "-c", "cat; echo"], "_tool": {"description": "回聲"}})
        self.cfg = {"brain": "brain.json", "tools": {"echo": "tools/echo.json"}, "history": "h.json", "work": "work"}

    def calls(self, *names):
        tc = [{"id": "c%d" % i, "type": "function", "function": {"name": n, "arguments": '{"x": %d}' % i}}
              for i, n in enumerate(names)]
        self.write("h.json", [{"role": "user", "content": "hi"}, {"role": "assistant", "content": None, "tool_calls": tc}])

    def tool(self, running=False, cfg=True):
        win = {"phase": "tool", "step": 1, "running": running, "data": None}
        arg = dict(self.cfg, fsm_state=win) if cfg else []
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

    def test_interrupted_tool_not_rerun(self):
        self.calls("echo")
        r = self.tool(running=True)                                          # fsm_state.running＝上一拍被殺一半
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(json.loads(self.read("h.json"))[-1]["content"])["error"]["code"], "Interrupted")
        self.assertFalse(os.path.exists(self.p("work")))                    # 沒跑工具

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
        self.assertEqual(json.loads(self.read("fr/ctl.json")), {"stop": True})
        self.write("fr/work/think-fails.json", {"n": 3, "error": {"code": "BrainFailed", "msg": "x"}})
        self.run_cell("done", fr)
        self.assertEqual(json.loads(self.read("fr/ret.json")), {"error": {"code": "BrainFailed", "msg": "x"}})

    def test_intake_keeps_bound_history(self):
        self.write("fr/history.json", [{"role": "user", "content": "綁好的"}])
        self.write("fr/args.json", {"question": "別理我"})
        self.assertEqual(self.run_cell("intake", self.p("fr")).returncode, 0)
        self.assertEqual(json.loads(self.read("fr/history.json"))[0]["content"], "綁好的")
        os.makedirs(self.p("empty"))
        r = self.run_cell("intake", self.p("empty"))
        self.assertEqual((r.returncode, json.loads(r.stderr)["error"]["code"]), (1, "NoHistory"))


BRAIN_PY = """import json, sys, time
req = json.load(sys.stdin)
msgs = req["messages"]
last = msgs[-1]
names = sorted(t["function"]["name"] for t in req.get("tools", []))
first = msgs[0].get("content") if msgs[0]["role"] == "user" else msgs[1].get("content")
if first == "fail":
    print(json.dumps({"error": {"code": "Boom", "msg": "壞了"}}), file=sys.stderr)
    sys.exit(1)
if first == "slow":
    time.sleep(0.5)
if (first == "loop" or last.get("content") == "use t") and last["role"] != "assistant":
    out = {"role": "assistant", "content": "還在想", "tool_calls": [
        {"id": "c%d" % len(msgs), "type": "function", "function": {"name": "t", "arguments": "{}"}}]}
else:
    out = {"role": "assistant", "content": json.dumps({"argv": sys.argv[1:], "tools": names, "n": len(msgs)})}
print(json.dumps(out))
"""


class AgentCallTest(Tmp):
    """agent 當函數＋binding（aos_agent_call）：bob/＝定義不動、frame＝history 累積處、呼叫時的參數。"""

    def setUp(self):
        super().setUp()
        self.write("bob/brain.py", BRAIN_PY)
        self.write("bob/brain.json", {"argv": [sys.executable, "brain.py"]})          # 相對 bob/
        self.write("bob/t.json", {"argv": ["sh", "-c", "cat; echo"], "_tool": {"description": "回聲"}})
        self.write("u.json", {"argv": ["true"]})                                          # 呼叫者這邊的工具
        cell = lambda k: {"argv": [sys.executable, AGENT, k]}
        self.write("bob/agent.json", {
            "start": "thinking", "end": ["idle"], "max_steps": 30,
            "states": {"thinking": {"target": cell("think"), "next": "route"}, "route": cell("route"),
                       "tool": {"target": cell("tool"), "next": "thinking"}},
            "brain": "brain.json", "tools": {"t": "t.json"}})
        import aos_agent_call
        self.mod = aos_agent_call
        self.bob = aos_agent_call.Agent(self.p("bob", "agent.json"))

    def call(self, frame, q=None, **kw):
        hist = None if q is None else [{"role": "user", "content": q}]
        out = self.bob.call(self.p(frame), history=hist, cwd=self.tmp, **kw)
        return out, json.loads(out["reply"])

    def ask(self, frame, q, *flags, env=None):
        return subprocess.Popen([sys.executable, AGENT, "ask", "--frame", self.p(frame)] + list(flags)
                                + [self.p("bob", "agent.json")], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", **(env or {})))

    def done(self, p, q):
        out, _ = p.communicate(json.dumps({"question": q}), timeout=30)
        return p.returncode, json.loads(out)

    def test_bob_untouched_frames_hold_history(self):
        before = tree_hash(self.p("bob"))
        out, r = self.call("f1", "use t")
        self.call("f2", "hi")
        self.assertEqual(tree_hash(self.p("bob")), before)
        self.assertEqual(sorted(os.listdir(self.p("f1"))), ["history.json", "state.json", "work"])
        self.assertEqual([m["role"] for m in json.loads(self.read("f1/history.json"))],
                         ["user", "assistant", "tool", "assistant"])
        self.assertEqual(len(json.loads(self.read("f2/history.json"))), 2)
        self.assertEqual((r["tools"], out["ticks"]), (["t"], 5))

    def test_history_override_vs_continue(self):
        self.write("f/history.json", [{"role": "user", "content": "x"}, {"role": "assistant", "content": "y"},
                                      {"role": "user", "content": "z"}])
        _, r = self.call("f")                                  # 沒給＝接著 frame 裡的
        self.assertEqual(r["n"], 3)
        self.assertEqual(len(json.loads(self.read("f/history.json"))), 4)
        _, r = self.call("f", "new")                           # 給了＝換掉
        self.assertEqual(r["n"], 1)
        self.assertEqual(len(json.loads(self.read("f/history.json"))), 2)
        with self.assertRaises(self.mod.CallError) as e:
            self.bob.call(self.p("empty"), cwd=self.tmp)
        self.assertEqual(e.exception.code, "NoHistory")

    def test_tools_append_and_replace(self):
        _, r = self.call("f", "hi", tools_append={"u": "u.json"})        # 相對呼叫者的 cwd
        self.assertEqual(r["tools"], ["t", "u"])
        _, r = self.call("f", "hi", tools={"u": "u.json"})               # 整份取代 bob 綁的
        self.assertEqual(r["tools"], ["u"])
        _, r = self.call("f", "hi", tools={}, tools_append={"u": "u.json"})
        self.assertEqual(r["tools"], ["u"])

    def test_engine_args(self):
        _, r = self.call("f", "hi", engine_args=["--model", "m2"])
        self.assertEqual(r["argv"], ["--model", "m2"])
        _, r = self.call("f", "hi", engine_args={"argv": [sys.executable, "brain.py", "--x"]})
        self.assertEqual(r["argv"], ["--x"])

    def test_ask_normal(self):
        code, out = self.done(self.ask("f", "use t"), "use t")
        self.assertEqual(code, 0, out)
        self.assertEqual(set(out), {"reply", "ticks"})
        self.assertEqual(json.loads(out["reply"])["n"], 3)

    def test_ask_max_ticks(self):
        code, out = self.done(self.ask("f", "loop", "--max-ticks", "4"), "loop")
        self.assertEqual((code, out["error"]["code"], out["partial"]), (1, "MaxTicks", "還在想"))

    def test_ask_busy_same_frame(self):
        os.makedirs(self.p("f", "lock"))
        code, out = self.done(self.ask("f", "hi"), "hi")
        self.assertEqual((code, out["error"]["code"]), (1, "Busy"))

    def test_ask_two_frames_concurrently(self):
        a, b = self.ask("f1", "slow"), self.ask("f2", "slow")
        self.assertEqual(self.done(a, "slow")[0], 0)
        self.assertEqual(self.done(b, "slow")[0], 0)

    def test_ask_depth_limit(self):
        code, out = self.done(self.ask("f", "hi", env={"AOS_ASK_DEPTH": "3"}), "hi")
        self.assertEqual((code, out["error"]["code"]), (1, "TooDeep"))
        self.assertFalse(os.path.exists(self.p("f")))
        code, _ = self.done(self.ask("f", "hi", env={"AOS_ASK_DEPTH": "2"}), "hi")
        self.assertEqual(code, 0)

    def test_ask_sub_agent_failed(self):
        code, out = self.done(self.ask("f", "fail"), "fail")
        self.assertEqual((code, out["error"]["code"]), (1, "SubAgentFailed"))
        self.assertIn("BrainFailed: Boom", out["error"]["msg"])          # N-29 形狀
        self.assertEqual(len(json.loads(self.read("f/history.json"))), 1)       # 沒重試


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
