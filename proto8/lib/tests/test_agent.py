"""proto8/lib 的自動測試：agent 的現成格庫（aos_agent_lib）與真的腦（aos_brain_openai、aos_brain_ollama）。只用標準庫：

    python3 -m unittest discover -s proto8/lib/tests

整圈用 demo/fsm 那套（假的腦），在暫存資料夾一拍一拍敲 aos_fsm；真的腦對一個本機假伺服器（http.server）。
"""
import http.server
import json
import os
import socket
import subprocess
import sys
import threading

from helpers import FSM, LIB, Tmp

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
        self.env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", DEMO_DIR=self.tmp, DEMO_STATE=self.p("a.state.json"),
                        DEMO_THINK_STATE=self.p("t.state.json"), DEMO_LOCK=self.p("a.lock"),
                        DEMO_HISTORY=self.p("work", "history.json"), DEMO_WORK=self.p("work"))

    def round(self, text, ticks=8):
        self.write("inbox/01.txt", text)
        steps = []
        for _ in range(ticks):
            r = subprocess.run([sys.executable, FSM, "agent.json"], cwd=DEMO, env=self.env,
                               capture_output=True, text=True, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr)
            steps.append(json.loads(r.stdout.splitlines()[-1]))
            if os.path.exists(self.p("outbox.txt")):
                break
        return steps, json.loads(self.read("work/history.json"))

    def test_full_round_with_tool(self):
        steps, hist = self.round("現在幾點？")
        self.assertEqual([(s["from"], s["to"]) for s in steps],
                         [("idle", "thinking"), ("thinking", "thinking"), ("thinking", "tool"),
                          ("tool", "thinking"), ("thinking", "thinking"), ("thinking", "idle")])
        self.assertEqual([m["role"] for m in hist], ["user", "assistant", "tool", "assistant"])
        call = hist[1]["tool_calls"][0]
        self.assertEqual((call["type"], call["function"]["name"]), ("function", "clock"))
        self.assertEqual(hist[2]["tool_call_id"], call["id"])
        res = json.loads(hist[2]["content"])
        self.assertEqual(res["code"], 0)
        self.assertIn("time", res["result"])
        self.assertTrue(self.read("outbox.txt").startswith("現在是 " + res["result"]["time"]))
        self.assertEqual(json.loads(self.read("work/2-call.json")), {})       # 引數寫成 N-call.json（N＝那時 history 幾則）

    def test_unknown_tool_goes_back_to_model(self):
        steps, hist = self.round("亂叫一個")
        self.assertEqual(steps[-1]["to"], "idle")
        self.assertTrue(all("error" not in s for s in steps))                # 不是 fsm 的錯
        self.assertTrue(hist[2]["content"].startswith("不認得這個工具"))


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
        stdin = json.dumps({"state": "thinking", "step": 1, "prev": None, "cfg": cfg})
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
    """直接敲 aos_agent_lib.py tool（設定走 stdin 的 cfg）：一次多個 tool_calls、被中斷、沒 cfg。"""

    def setUp(self):
        super().setUp()
        self.write("tools/echo.json", {"argv": ["sh", "-c", "cat; echo"], "_tool": {"description": "回聲"}})
        self.cfg = {"brain": "brain.json", "tools": {"echo": "tools/echo.json"}, "history": "h.json", "work": "work"}

    def calls(self, *names):
        tc = [{"id": "c%d" % i, "type": "function", "function": {"name": n, "arguments": '{"x": %d}' % i}}
              for i, n in enumerate(names)]
        self.write("h.json", [{"role": "user", "content": "hi"}, {"role": "assistant", "content": None, "tool_calls": tc}])

    def tool(self, prev=None, cfg=True):
        arg = {"state": "tool", "step": 1, "prev": prev}
        if cfg:
            arg["cfg"] = self.cfg
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
        self.assertEqual(json.loads(hist[2]["content"]), {"code": 0, "result": {"x": 0}})
        self.assertEqual([m["content"] for m in hist[3:]], ["基礎實作一次只跑一個，這個沒跑"] * 2)
        self.assertEqual(self.tool().stdout.strip(), '{"data": {"tool": null}}')    # 都回過了＝什麼都不跑

    def test_interrupted_tool_not_rerun(self):
        self.calls("echo")
        r = self.tool({"interrupted": True, "data": None})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(self.read("h.json"))[-1]["content"], "被中斷")
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

    def test_think_cell_through_real_brain(self):
        _Stub.reply = {"choices": [{"message": {"role": "assistant", "content": "好"}}]}
        self.write("brain.json", {"argv": [sys.executable, BRAIN, "--base-url", self.url, "--model", "m1"]})
        self.write("tools/clock.json", {"argv": ["true"], "_tool": {"description": "時間"}})
        cfg = {"brain": "brain.json", "tools": {"clock": "tools/clock.json"}, "history": "h.json", "work": "work"}
        self.write("h.json", [{"role": "user", "content": "hi"}])
        r = subprocess.run([sys.executable, AGENT, "think"], cwd=self.tmp, input=json.dumps({"cfg": cfg}),
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(_Stub.seen[0][2]["tools"][0]["function"]["description"], "時間")
        self.assertEqual(json.loads(self.read("h.json"))[-1], {"role": "assistant", "content": "好"})
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
        # 146 試跑的情形：腦回 400 → think 格 BrainFailed 帶原因 → fsm 的 last_error 看得到；錯 3 次就停住不再打
        _Stub.status, _Stub.reply = 400, {"error": "m1 does not support tools"}
        self.write("brain.json", {"argv": [sys.executable, OLLAMA, "--base-url", self.url, "--model", "m1"]})
        self.write("tools/clock.json", {"argv": ["true"], "_tool": {"description": "時間"}})
        self.write("h.json", [{"role": "user", "content": "幾點"}])
        self.write("f.json", {"start": "ask", "states": {"ask": {"argv": [sys.executable, AGENT, "think"]}},
                              "state": "f.state.json", "brain": "brain.json", "tools": {"clock": "tools/clock.json"},
                              "history": "h.json", "work": "work"})
        for _ in range(5):
            r = subprocess.run([sys.executable, FSM, "f.json"], cwd=self.tmp, capture_output=True, text=True, timeout=10)
            self.assertEqual(r.returncode, 0, r.stderr)
        st = json.loads(self.read("f.state.json"))
        self.assertTrue(st["last_error"].startswith("CellFailed: BrainFailed: HttpError: "), st["last_error"])
        self.assertIn("does not support tools", st["last_error"])
        self.assertEqual((st["fails"], st["halted"], len(_Stub.seen)), (3, True, 3))

    def test_bad_num_ctx(self):
        r = self.ollama({"messages": []}, "--num-ctx", "big")
        self.assertEqual((r.returncode, json.loads(r.stderr)["error"]["code"]), (1, "FieldType"))

    # 父類別的 openai 專屬測試不重跑
    test_request_has_tools_and_reply_parsed = test_api_key_from_env = None
    test_http_and_connect_errors = test_think_cell_through_real_brain = None
