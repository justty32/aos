"""proto8/lib 的自動測試：agent 的現成格庫（aos_agent_lib）與真的腦（aos_brain_openai）。
frame 與 agent 當函數／當工具的測試在 test_agent_frame.py。只用標準庫：

    python3 -m unittest discover -s proto8/lib/tests

整圈用 demo/fsm 那套（假的腦）：在暫存 frame（frame.json 指回 demo/fsm）一拍一拍敲 `aos agent fsm`；
真的腦對一個本機假伺服器（http.server）。PATH 照 helpers.ENV。
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
DEMO = os.path.realpath(os.path.join(LIB, "..", "demo", "fsm"))


class AgentRoundTest(Tmp):
    """demo/fsm 這個定義資料夾：idle → thinking（ask → review）→ tool → thinking → idle；frame＝暫存資料夾。"""

    def setUp(self):
        super().setUp()
        os.makedirs(self.p("inbox"))
        self.write("frame.json", {"parent": DEMO})

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
        self.assertFalse(os.path.exists(self.p("work/1/args.json")))                          # 引數→clerk 接走就刪
        self.assertEqual(json.loads(self.read("work/1/frame.json")), {"parent": os.path.join(DEMO, "clerk")})
        sub = json.loads(self.read("work/1/history.json"))                    # clerk 的 frame
        self.assertEqual([m["role"] for m in sub], ["user", "assistant", "tool", "assistant"])
        self.assertEqual(sub[1]["tool_calls"][0]["function"]["name"], "clock")
        self.assertEqual(json.loads(self.read("work/1/ret.json")), res["result"])
        self.assertEqual(json.loads(self.read("work/1/loop/state.json"))["state"], "done")   # fsm 結束＝clerk 的 loop 停
        self.assertFalse(os.path.exists(self.p("work", "1", "loop", "ctl.json")))     # 不靠 ctl

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
        self.assertEqual(json.loads(hist[2]["content"])["error"]["code"], "ToolUnknown")   # N-29 形狀

    def test_empty_inbox_done_stops(self):
        # inbox 空了＝idle 回 next done：done 格寫 ret.json，fsm 結束（那行帶 end、phase 歸位 idle）
        r = subprocess.run(["aos", "agent", "fsm"], cwd=self.tmp, env=ENV, capture_output=True, text=True, timeout=30)
        self.assertEqual(json.loads(r.stdout.splitlines()[0])["to"], "done")
        r = subprocess.run(["aos", "agent", "fsm"], cwd=self.tmp, env=ENV, capture_output=True, text=True, timeout=30)
        out = [json.loads(x) for x in r.stdout.splitlines()]
        self.assertEqual((out[0]["end"], out[-1]), (True, {"data": {"reply": None}}))
        self.assertEqual(json.loads(self.read("fsm/state.json")), {"phase": "idle"})


class AgentSystemTest(Tmp):
    """system 提示檔：第一則 system 訊息、不進 history、檔不存在＝格出錯。"""

    def setUp(self):
        super().setUp()
        self.write("brain.py", "import json, sys\nreq = json.load(sys.stdin)\n"
                   "open('seen.json', 'w').write(json.dumps(req))\n"
                   "print(json.dumps({'role': 'assistant', 'content': 'ok'}))\n")
        self.write("brain.json", {"argv": ["python3", "brain.py"]})
        self.write("history.json", [{"role": "user", "content": "hi"}])
        self.cfg = {"brain": "brain.json", "tools": {}}

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
        self.assertEqual([m["role"] for m in json.loads(self.read("history.json"))], ["user", "assistant"])

    def test_no_system_key_no_system_message(self):
        r = self.think(self.cfg)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([m["role"] for m in json.loads(self.read("seen.json"))["messages"]], ["user"])

    def test_missing_system_file_is_cell_error(self):
        r = self.think(dict(self.cfg, system="nope.md"))
        self.assertEqual(r.returncode, 1)
        self.assertEqual(json.loads(r.stderr.strip().splitlines()[-1])["error"]["code"], "ReadFailed")
        self.assertEqual(len(json.loads(self.read("history.json"))), 1)


class AgentCellTest(Tmp):
    """直接敲 aos_agent_lib.py tool（stdin＝設定）：一次多個 tool_calls、沒設定。"""

    def setUp(self):
        super().setUp()
        self.write("tools/echo.json", {"argv": ["sh", "-c", "cat; pwd > where.txt"], "_tool": {"description": "回聲"}})
        self.cfg = {"brain": "brain.json", "tools": {"echo": "tools/echo.json"}}

    def calls(self, *names):
        tc = [{"id": "c%d" % i, "type": "function", "function": {"name": n, "arguments": '{"x": %d}' % i}}
              for i, n in enumerate(names)]
        self.write("history.json", [{"role": "user", "content": "hi"}, {"role": "assistant", "content": None, "tool_calls": tc}])

    def tool(self, cfg=True):
        arg = self.cfg if cfg else []
        return subprocess.run([sys.executable, AGENT, "tool"], cwd=self.tmp, capture_output=True,
                              text=True, input=json.dumps(arg), timeout=10)

    def test_no_cfg_is_cell_error(self):
        self.calls("echo")
        r = self.tool(cfg=False)
        self.assertEqual((r.returncode, json.loads(r.stderr)["error"]["code"]), (1, "FieldType"))

    def test_multiple_tool_calls_all_run_in_order(self):
        # 10-15 使用者「都按照推薦」：一拍內照順序全部跑，每個 id 都有對應的 tool 訊息（原本只跑第一個、其餘 Skipped）
        self.calls("echo", "echo", "nope")
        r = self.tool()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, "")                                                 # 不再警告 ToolCallsSkipped
        hist = json.loads(self.read("history.json"))
        self.assertEqual([m.get("tool_call_id") for m in hist[2:]], ["c0", "c1", "c2"])   # 照順序、每個 id 都有回
        res = [json.loads(m["content"]) for m in hist[2:]]
        self.assertEqual((res[0]["code"], res[0]["result"], res[0]["id"]), (0, {"x": 0}, self.p("tools", "echo.json")))
        self.assertEqual((res[1]["code"], res[1]["result"]), (0, {"x": 1}))           # 第二個也真的跑了
        self.assertEqual(res[2]["error"]["code"], "ToolUnknown")
        self.assertEqual([json.loads(self.read("work/%d/args.json" % n)) for n in (1, 2)], [{"x": 0}, {"x": 1}])
        self.assertEqual(json.loads(r.stdout), {"data": {"tools": ["echo", "echo", "nope"]}})     # stdout 一格（結果在 history）
        self.assertEqual(self.tool().stdout.strip(), '{"data": {"tools": []}}')      # 都回過了＝什麼都不跑

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
        r = self.brain({"messages": []})
        self.assertEqual((r.returncode, json.loads(r.stderr)["error"]["code"]), (1, "ConnectFailed"))

    def test_usage_passed_through(self):
        _Stub.reply = dict(_Stub.reply, usage={"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7})
        out = json.loads(self.brain({"messages": []}).stdout)
        self.assertEqual((out["role"], out["usage"]["total_tokens"]), ("assistant", 7))

    def test_think_cell_through_real_brain(self):
        _Stub.reply = {"choices": [{"message": {"role": "assistant", "content": "好"}}], "usage": {"total_tokens": 3}}
        self.write("brain.json", {"argv": [sys.executable, BRAIN, "--base-url", self.url, "--model", "m1"]})
        self.write("tools/clock.json", {"argv": ["true"], "_tool": {"description": "時間"}})
        cfg = {"brain": "brain.json", "tools": {"clock": "tools/clock.json"}}
        self.write("history.json", [{"role": "user", "content": "hi"}])
        r = subprocess.run([sys.executable, AGENT, "think"], cwd=self.tmp, input=json.dumps(cfg),
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(_Stub.seen[0][2]["tools"][0]["function"]["description"], "時間")
        self.assertEqual(json.loads(self.read("history.json"))[-1], {"role": "assistant", "content": "好"})   # usage 沒進 history
        self.assertEqual(json.loads(r.stdout), {"data": {"content": "好", "tool_calls": []}})
