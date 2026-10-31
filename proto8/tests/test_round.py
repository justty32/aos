"""test_round - agent-round 落地第 1、4 步：lib/endpoint/fake、lib/endpoint/openai（問腦的格）與 lib/agent/act（跑工具的格）。

endpoint：fake 照規則吐一則；openai 接假的 OpenAI 相容 server 吐真的、usage.jsonl 多一行、經 aos-parts run 帶註冊檔的 env；
  401／403 KeyBad、連不上（dead_brain.DEAD）與 5xx BrainFailed、404 ModelUnknown、其他 4xx RequestBad、壞回覆 ReplyBad，失敗時 stdout 與 usage.jsonl 都不動。
act：兩個 tool_calls 吐兩則、順序對；AOS_ACT_MAX_PARALLEL=2 真的一起跑、順序仍對；pre_tool 退 10＝不跑、stdout 當 content；post_tool 取代；
  ToolUnknown／ArgumentsBad／工具退非 0 接成 tool 訊息；插話（queue 的 new/ 有信＋on_interrupt 說 interrupt）剩下的不跑、退 10；aos-tools 壞＝ToolsBad。
一輪（10-30 起 aos-round：lib/agent/round 的 fsm 表＋五格；舊骨架 round/_entry 與它的 Round 類、--step、hook/pause 第 6 步刪了）：
  題目經 queue push 進 $AOS_STACK/queue/，答案看 history 最新那則 assistant。
RoundFsm（第 2 步）：aos-fsm 一次一格、驗 state.txt 與 trace 的 (state, code, next)；system.txt 與 tools 帶進請求、
  第一題答完後 claim 死在搬進 cur/ 之後的補認領（這兩案第 6 步從舊 Round 類搬來）。
AosRound（第 3 步）：bin/aos-round 單次叫、loop.json 用它整隻跑（stop、idle＋ctl paused／stopped、單子逾時殺在 think）、自己的錯。
設計：proto8/thinking/2026-10-28-agent-round.md § 3、§ 4、文末「實作時代定」；2026-10-30-agent-lifecycle 結論 A、B-11。
LiteLLM（localhost:4000）實跑那案連不上就 skip。"""
import http.server, json, os, re, subprocess, tempfile, threading, time, unittest, urllib.request
from pathlib import Path

from aos_bins import ROOT, tool, path_with  # noqa: E402
from dead_brain import DEAD  # noqa: E402

EXEC = tool("aos-exec")
PARTS = str(ROOT / "bin" / "aos-parts")
FAKE = str(ROOT / "lib" / "endpoint" / "fake")
OPENAI = str(ROOT / "lib" / "endpoint" / "openai")
ACT = str(ROOT / "lib" / "agent" / "act")
CLOCK = str(ROOT / "lib" / "base" / "clock")
REAL_URL = "http://localhost:4000/v1"
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_CF", "AOS_CD", "AOS_CO", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL",
         "AOS_BRAIN_KEY", "AOS_KERNEL_REPORT", "AOS_ENDPOINT_TIMEOUT_MS", "AOS_ENDPOINT_NAME", "AOS_ACT_MAX_PARALLEL", "AOS_ROUND_MAX_RETRIES", "AOS_ROUND_ON_EMPTY")
CLOCK_TOOL = {"type": "function", "function": {"name": "clock", "parameters": {"type": "object", "properties": {}}}}


def err_code(prog, stderr):
    """stderr 最後一行要是「prog: 代號 原因」；回代號。"""
    last = stderr.strip().splitlines()[-1]
    m = re.match(r"%s: ([A-Z][A-Za-z]+) \S" % prog, last)
    assert m, "錯誤行格式不對：%r" % stderr
    return m.group(1)


class FakeBrain:
    """假的 OpenAI 相容 server（同 test_dan）：每次 POST 回劇本的下一個；記下 request body 與 Authorization。
    劇本一項＝dict（200 回 JSON）或 (狀態碼, 字串)。"""

    def __init__(self, script):
        self.script, self.requests, self.auth = list(script), [], []
        brain = self

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                brain.requests.append(json.loads(body))
                brain.auth.append(self.headers.get("Authorization"))
                item = brain.script.pop(0) if brain.script else (500, "劇本用完了")
                status, text = (200, json.dumps(item)) if isinstance(item, dict) else item
                if self.path != "/v1/chat/completions":
                    status, text = 404, "path " + self.path
                data = text.encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass

        self.server = http.server.HTTPServer(("127.0.0.1", 0), H)
        self.url = "http://127.0.0.1:%d/v1" % self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class Base(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.tmp = Path(self._t.name)
        self.agent = self.tmp / "agent"
        self.agent.mkdir()
        self.ws = self.tmp / "ws"
        self.ws.mkdir()
        self.stack = self.ws / ".stack"

    def env(self, extra=None):
        e = {k: v for k, v in os.environ.items() if k not in CLEAR}
        e["PATH"] = path_with(e.get("PATH", ""))
        e["AOS_WS"] = str(self.ws)
        e["AOS_STACK"] = str(self.stack) + "/"
        e.update(extra or {})
        return e

    def cell(self, path, stdin, env=None, args=None):
        args = [str(self.agent)] if args is None else args
        return subprocess.run([EXEC, path] + args, input=stdin, capture_output=True, text=True,
                              env=self.env(env), cwd=self.tmp, timeout=60)

    def lines(self, text):
        return [json.loads(l) for l in text.splitlines()]


def req(*messages, tools=None):
    body = {"messages": list(messages)}
    if tools is not None:
        body["tools"] = tools
    return json.dumps(body, ensure_ascii=False)


def user(text):
    return {"role": "user", "content": text}


class EndpointFake(Base):
    def test_calls_clock_then_answers(self):
        r = self.cell(FAKE, req(user("幾點？"), tools=[CLOCK_TOOL]))
        self.assertEqual(r.returncode, 0, r.stderr)
        msg = self.lines(r.stdout)
        self.assertEqual(len(msg), 1)
        self.assertEqual(msg[0]["tool_calls"][0]["function"], {"name": "clock", "arguments": "{}"})
        r = self.cell(FAKE, req(user("幾點？"), msg[0], {"role": "tool", "tool_call_id": "call_fake_1", "content": "T0\n"},
                                tools=[CLOCK_TOOL]))
        self.assertEqual(self.lines(r.stdout), [{"role": "assistant", "content": "FAKE ANSWER to: 幾點？（clock said: T0）"}])
        self.assertFalse((self.stack / "usage.jsonl").exists())          # 假腦不寫 usage

    def test_without_clock_answers_last_user(self):
        r = self.cell(FAKE, req({"role": "system", "content": "s"}, user("一"), {"role": "assistant", "content": "a"}, user("二")))
        self.assertEqual(self.lines(r.stdout), [{"role": "assistant", "content": "FAKE ANSWER to: 二"}])

    def test_request_bad(self):
        for stdin in ("not json", "[]", req({"role": "system", "content": "s"})):
            with self.subTest(stdin=stdin):
                r = self.cell(FAKE, stdin)
                self.assertEqual((r.returncode, r.stdout), (1, ""))
                self.assertEqual(err_code("endpoint", r.stderr), "RequestBad")


class EndpointOpenai(Base):
    def brain(self, *script):
        b = FakeBrain(script)
        self.addCleanup(b.close)
        return b

    def ask(self, url, extra=None, stdin=None):
        env = {"AOS_BRAIN_URL": url, "AOS_BRAIN_MODEL": "m1"}
        env.update(extra or {})
        return self.cell(OPENAI, stdin or req(user("hi"), tools=[CLOCK_TOOL]), env)

    def usage(self):
        p = self.stack / "usage.jsonl"
        return self.lines(p.read_text()) if p.exists() else []

    def test_answer_and_usage(self):
        reply = {"choices": [{"message": {"role": "assistant", "content": None, "reasoning_content": "想一想",
                                          "tool_calls": [{"id": "c1", "type": "function", "index": 0,
                                                          "function": {"name": "clock", "arguments": "{}"}}]}}],
                 "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7}}
        b = self.brain(reply, {"choices": [{"message": {"role": "assistant", "content": "好"}}]})
        report = self.tmp / "report.json"
        r = self.ask(b.url, {"AOS_BRAIN_KEY": "sk-1", "AOS_KERNEL_REPORT": str(report)})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.lines(r.stdout), [{"role": "assistant", "content": None, "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "clock", "arguments": "{}"}}]}])   # 只留三個 key
        self.assertEqual(b.requests[0], {"messages": [user("hi")], "tools": [CLOCK_TOOL], "model": "m1"})
        self.assertEqual(b.auth[0], "Bearer sk-1")
        u = self.usage()
        self.assertEqual(len(u), 1)
        self.assertEqual((u[0]["endpoint"], u[0]["model"], u[0]["usage"]["total_tokens"]), ("openai", "m1", 7))
        self.assertRegex(u[0]["answered_at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$")
        self.assertEqual(json.loads(report.read_text())["total_tokens"], 7)
        # 第二次：stdin 給的 model 優先、空 tools 不送、沒 usage 也記一行（usage＝null）、AOS_ENDPOINT_NAME 改名
        r = self.ask(b.url, {"AOS_ENDPOINT_NAME": "litellm"}, stdin=json.dumps({"messages": [user("x")], "tools": [], "model": "m2"}))
        self.assertEqual(self.lines(r.stdout), [{"role": "assistant", "content": "好"}])
        self.assertEqual(b.requests[1], {"messages": [user("x")], "model": "m2"})
        self.assertIsNone(b.auth[1])
        self.assertEqual([(x["endpoint"], x["model"], x["usage"]) for x in self.usage()[1:]], [("litellm", "m2", None)])

    def test_via_parts_registry_env(self):
        b = self.brain({"choices": [{"message": {"role": "assistant", "content": "經註冊檔"}}]})
        (self.agent / "parts.json").write_text(json.dumps({"parts": {"endpoint/main": {
            "path": OPENAI, "env": {"AOS_BRAIN_URL": b.url, "AOS_BRAIN_MODEL": "reg", "AOS_ENDPOINT_NAME": "main"}}}}))
        r = subprocess.run([PARTS, "--file", str(self.agent / "parts.json"), "run", "endpoint/main", str(self.agent)],
                           input=req(user("q")), capture_output=True, text=True, env=self.env(), timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.lines(r.stdout), [{"role": "assistant", "content": "經註冊檔"}])
        self.assertEqual(b.requests[0]["model"], "reg")
        self.assertEqual(self.usage()[0]["endpoint"], "main")

    def assert_fails(self, code, r):
        self.assertEqual((r.returncode, r.stdout), (1, ""), r.stderr)
        self.assertEqual(err_code("endpoint", r.stderr), code)
        self.assertEqual(self.usage(), [])

    def test_error_codes(self):
        cases = [((401, '{"error": "bad key"}'), "KeyBad"), ((403, "no"), "KeyBad"),
                 ((404, '{"error": "model not found"}'), "ModelUnknown"), ((400, "bad"), "RequestBad"),
                 ((422, "bad"), "RequestBad"), ((429, "slow"), "BrainFailed"), ((503, "down"), "BrainFailed"),
                 ({"choices": []}, "ReplyBad"), ((200, "not json"), "ReplyBad"),
                 ({"choices": [{"message": "x"}]}, "ReplyBad"),
                 ({"choices": [{"message": {"role": "assistant", "tool_calls": "x"}}]}, "ReplyBad")]
        for item, code in cases:
            with self.subTest(item=item):
                b = self.brain(item)
                self.assert_fails(code, self.ask(b.url))
        r = self.ask(b.url)                                              # 劇本用完＝500
        self.assertIn("HTTP 500", r.stderr)

    def test_brain_unreachable(self):
        self.assert_fails("BrainFailed", self.ask(DEAD))

    def test_config_errors(self):
        self.assert_fails("UrlMissing", self.cell(OPENAI, req(user("q"))))
        self.assert_fails("ModelUnknown", self.cell(OPENAI, req(user("q")), {"AOS_BRAIN_URL": DEAD}))
        self.assert_fails("TimeoutBad", self.ask(DEAD, {"AOS_ENDPOINT_TIMEOUT_MS": "0"}))
        self.assert_fails("RequestBad", self.ask(DEAD, stdin='{"messages": "x"}'))

    @unittest.skipUnless(os.environ.get("AOS_TEST_REAL", "1") != "0", "")
    def test_real_litellm(self):
        try:
            urllib.request.urlopen(REAL_URL + "/models", timeout=3).read()
        except OSError:
            self.skipTest("localhost:4000 連不上")
        model = os.environ.get("AOS_REAL_MODEL", "fast")
        r = self.ask(REAL_URL, {"AOS_BRAIN_MODEL": model, "AOS_ENDPOINT_TIMEOUT_MS": "120000"}, stdin=req(user("只回一個字：好")))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.lines(r.stdout)[0]["role"], "assistant")
        self.assertEqual(len(self.usage()), 1)


TOOL_SAY = """#!/usr/bin/env python3
# say - 測試用：把 arguments 的 text 印出來；有 code 就用那個結束碼；wait_for＝等 $AOS_WS/<那個名字> 出現（最多 3 秒）；touch＝建 $AOS_WS/<那個名字>
import json, os, sys, time
a = json.loads(sys.stdin.read() or "{}")
ws = os.environ["AOS_WS"]
if a.get("touch"):
    open(os.path.join(ws, a["touch"]), "w").close()
if a.get("wait_for"):
    end = time.time() + 3
    while not os.path.exists(os.path.join(ws, a["wait_for"])) and time.time() < end:
        time.sleep(0.02)
    print("saw" if os.path.exists(os.path.join(ws, a["wait_for"])) else "no")
print(a.get("text", ""), end="")
print("|" + os.environ["AOS_STACK"])
sys.exit(a.get("code", 0))
"""


def call(cid, name, **arguments):
    return {"id": cid, "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}


def assistant(*calls):
    return json.dumps({"role": "assistant", "content": None, "tool_calls": list(calls)})


class Act(Base):
    def setUp(self):
        super().setUp()
        say = self.tmp / "say"
        say.mkdir()
        (say / "_entry").write_text(TOOL_SAY)
        (say / "_entry").chmod(0o755)
        (say / "_tooldef.json").write_text('{"description": "say", "parameters": {"type": "object"}}')
        (self.agent / "tools.json").write_text(json.dumps({"tools": {"say": {"path": str(say)}, "clock": {"path": CLOCK}}}))

    def hook(self, point, script, registered=False):
        """掛一個 sh 寫的掛勾：registered＝登記進 parts.json，否則放固定名字 hook/<點>/。"""
        d = (self.tmp / "hooks" / point) if registered else (self.agent / "hook" / point)
        d.mkdir(parents=True)
        (d / "_entry").write_text("#!/bin/sh\n" + script)
        (d / "_entry").chmod(0o755)
        if registered:
            p = self.agent / "parts.json"
            reg = json.loads(p.read_text()) if p.exists() else {"parts": {}}
            reg["parts"]["hook/" + point] = {"path": str(d), "env": {"HOOK_SAYS": "註冊檔的 env"}}
            p.write_text(json.dumps(reg, ensure_ascii=False))

    def act(self, stdin, env=None):
        return self.cell(ACT, stdin, env)

    def test_two_calls_in_order(self):
        r = self.act(assistant(call("a", "say", text="一\n"), call("b", "clock")))
        self.assertEqual(r.returncode, 0, r.stderr)
        out = self.lines(r.stdout)
        self.assertEqual([(m["role"], m["tool_call_id"]) for m in out], [("tool", "a"), ("tool", "b")])
        self.assertEqual(out[0]["content"], "一\n|%s/say/\n" % self.stack)           # 工具的小格＝$AOS_STACK/<名>/
        self.assertRegex(out[1]["content"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\n$")

    def test_no_tool_calls(self):
        r = self.act(json.dumps({"role": "assistant", "content": "答"}))
        self.assertEqual((r.returncode, r.stdout), (0, ""), r.stderr)

    def test_parallel_runs_together_order_kept(self):
        calls = assistant(call("a", "say", wait_for="mark", text="A\n"), call("b", "say", touch="mark", text="B\n"))
        r = self.act(calls, {"AOS_ACT_MAX_PARALLEL": "2"})
        self.assertEqual(r.returncode, 0, r.stderr)
        out = self.lines(r.stdout)
        self.assertEqual([m["tool_call_id"] for m in out], ["a", "b"])
        self.assertTrue(out[0]["content"].startswith("saw\nA\n"), out[0])          # a 等到了 b 建的檔＝真的一起跑
        os.unlink(self.ws / "mark")
        r = self.act(calls)                                                     # 依序：a 先跑、等不到
        self.assertTrue(self.lines(r.stdout)[0]["content"].startswith("no\nA\n"))
        r = self.act(calls, {"AOS_ACT_MAX_PARALLEL": "x"})
        self.assertEqual((r.returncode, r.stdout, err_code("act", r.stderr)), (1, "", "ParallelBad"))

    def test_tool_problems_go_back_to_brain(self):
        r = self.act(assistant(call("a", "nope"), {"id": "b", "type": "function", "function": {"name": "say", "arguments": "{x"}},
                               call("c", "say", text="壞了", code=3)))
        self.assertEqual(r.returncode, 0, r.stderr)
        out = [m["content"] for m in self.lines(r.stdout)]
        self.assertTrue(out[0].startswith("act: ToolUnknown nope（能叫的：clock、say）"), out[0])
        self.assertTrue(out[1].startswith("act: ArgumentsBad say："), out[1])
        self.assertEqual(out[2], "壞了|%s/say/\n(工具 say 結束碼 3)\n" % self.stack)

    def test_pre_tool_10_skips(self):
        self.hook("pre_tool", 'read c; case "$c" in *\\"b\\"*) echo "policy 不准"; exit 10;; esac; exit 0\n')
        r = self.act(assistant(call("a", "say", text="A\n"), call("b", "say", touch="ran_b", text="B\n")))
        self.assertEqual(r.returncode, 0, r.stderr)
        out = self.lines(r.stdout)
        self.assertEqual(out[0]["content"], "A\n|%s/say/\n" % self.stack)
        self.assertEqual(out[1], {"role": "tool", "tool_call_id": "b", "content": "policy 不准\n"})
        self.assertFalse((self.ws / "ran_b").exists())                          # 真的沒跑

    def test_pre_tool_other_code_fails(self):
        self.hook("pre_tool", "exit 3\n")
        r = self.act(assistant(call("a", "say", touch="ran_a")))
        self.assertEqual((r.returncode, r.stdout, err_code("act", r.stderr)), (1, "", "HookFailed"))
        self.assertFalse((self.ws / "ran_a").exists())

    def test_post_tool_replaces(self):
        self.hook("post_tool", 'read m; case "$m" in *\\"a\\"*) printf \'{"role": "tool", "tool_call_id": "a", "content": "%s"}\\n\' "$HOOK_SAYS";; esac\n',
                  registered=True)
        r = self.act(assistant(call("a", "say", text="長長的"), call("b", "say", text="B")))
        self.assertEqual(r.returncode, 0, r.stderr)
        out = self.lines(r.stdout)
        self.assertEqual(out[0], {"role": "tool", "tool_call_id": "a", "content": "註冊檔的 env"})   # 取代，且拿到註冊檔的 env
        self.assertEqual(out[1]["content"], "B|%s/say/\n" % self.stack)          # stdout 空＝原樣

    def test_interrupt(self):
        new = self.stack / "queue" / "new"
        new.mkdir(parents=True)
        (new / "000000000009.x").mkdir()                                       # act 只看名字，不讀信
        calls = assistant(call("a", "say", text="A"), call("b", "say", touch="ran_b"), call("c", "clock"))
        r = self.act(calls)                                                     # 沒掛 on_interrupt＝wait
        self.assertEqual((r.returncode, len(self.lines(r.stdout))), (0, 3), r.stderr)
        os.unlink(self.ws / "ran_b")
        self.hook("on_interrupt", 'read n; [ "$n" = 000000000009.x ] && echo interrupt\n')
        r = self.act(calls)
        self.assertEqual(r.returncode, 10, r.stderr)
        out = self.lines(r.stdout)
        self.assertEqual([m["tool_call_id"] for m in out], ["a", "b", "c"])
        self.assertEqual(out[0]["content"], "A|%s/say/\n" % self.stack)
        self.assertEqual(out[1]["content"], "act: Interrupted 有新題（000000000009.x），這個工具沒跑\n")
        self.assertFalse((self.ws / "ran_b").exists())
        os.rmdir(new / "000000000009.x")                                        # new/ 空了＝不問、全跑
        r = self.act(calls)
        self.assertEqual((r.returncode, len(self.lines(r.stdout))), (0, 3))

    def test_own_errors(self):
        (self.agent / "tools.json").write_text("{壞")
        r = self.act(assistant(call("a", "say")))
        self.assertEqual((r.returncode, r.stdout, err_code("act", r.stderr)), (1, "", "ToolsBad"))
        for stdin, code in (("x", "MessageBad"), ('{"tool_calls": [{"id": "a"}]}', "MessageBad")):
            r = self.act(stdin)
            self.assertEqual((r.returncode, err_code("act", r.stderr)), (1, code))
        r = self.cell(ACT, assistant(call("a", "say")), args=["agent"])          # 相對路徑不收
        self.assertEqual((r.returncode, err_code("act", r.stderr)), (1, "AgentBad"))
        (self.agent / "parts.json").write_text(json.dumps({"parts": {"hook/pre_tool": {"path": str(self.tmp / "nope")}}}))
        (self.agent / "tools.json").write_text("{}")
        r = self.act(assistant(call("a", "say")))
        self.assertEqual((r.returncode, err_code("act", r.stderr)), (1, "PartsBad"))   # 登記了但壞＝不當沒掛


ROUND = str(ROOT / "lib" / "agent" / "round")
AGENT_LIB = ROOT / "lib" / "agent"
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


class AgentCase(Base):
    """tmp agent（queue、history、act、fake 腦、tools.json 只有 clock）＋queue 裡一題；RoundFsm 與 AosRound 共用。"""

    def setUp(self):
        super().setUp()
        self.parts = {"queue": {"path": str(AGENT_LIB / "queue")},
                      "history": {"path": str(AGENT_LIB / "history")}, "act": {"path": ACT},
                      "endpoint/default": {"path": FAKE}}
        self.save()
        (self.agent / "tools.json").write_text(json.dumps({"tools": {"clock": {"path": CLOCK}}}))
        self.q1 = self.put("幾點？")

    def save(self):
        (self.agent / "parts.json").write_text(json.dumps({"parts": self.parts}, ensure_ascii=False))

    def put(self, text):
        """經 queue 格放一則 user（同 aos-say）；回信號。"""
        r = subprocess.run([EXEC, str(AGENT_LIB / "queue"), str(self.agent), "push"], input=json.dumps(user(text)),
                           capture_output=True, text=True, env=self.env(), cwd=self.tmp, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def answer(self):
        """history 最新那則沒有 tool_calls 的 assistant 的 content（答案）。"""
        for m in reversed(self.history()):
            if m["role"] == "assistant" and not m.get("tool_calls"):
                return m["content"]
        return None

    def script(self, name, body, sh=True):
        p = self.tmp / "scripts" / name
        p.mkdir(parents=True)
        (p / "_entry").write_text(("#!/bin/sh\n" if sh else "") + body)
        (p / "_entry").chmod(0o755)
        return str(p)

    def hook(self, point, body):
        self.parts["hook/" + point] = {"path": self.script("hook_" + point, body)}
        self.save()

    def history(self):
        p = self.stack / "history.jsonl"
        return self.lines(p.read_text()) if p.exists() else []

    def ls(self, stage):
        d = self.stack / "queue" / stage
        return sorted(x.name for x in d.iterdir()) if d.is_dir() else []


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


class AosRound(AgentCase):
    """bin/aos-round（10-30 aos-round 第 3 步）：挑表（AOS_ROUND_ON_EMPTY）、設 AOS_ROUND_AGENT、cd lib/agent/round、換成 aos-fsm；
    agent 的 loop.json 用 aos-round、aos-exec <agent> 整隻跑；驗 fsm trace 的 state／next 序列。"""

    def loop(self, **cfg):
        cfg = dict({"exec": {"argv": ["aos-round", {"$env": "AOS_CD"}]}}, **cfg)
        (self.agent / "loop.json").write_text(json.dumps(cfg))
        (self.agent / "_entry").write_text('["aos-loop", "loop.json"]')

    def whole(self):
        return subprocess.run([EXEC, str(self.agent)], capture_output=True, text=True, env=self.env(), cwd=self.tmp, timeout=120)

    def aos_round(self, *args, env=None):
        return subprocess.run([tool("aos-round")] + list(args), capture_output=True, text=True, env=self.env(env),
                              cwd=self.tmp, timeout=120)

    def states(self):
        return [(t["state"], t["code"], t["next"]) for t in self.lines((self.stack / "trace.jsonl").read_text())]

    def state(self):
        return (self.stack / "state.txt").read_text().strip()

    def test_one_step(self):
        r = self.aos_round(str(self.agent))
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual((self.state(), self.states()), ("think", [("idle", 0, "think")]))
        self.assertEqual(self.ls("cur"), [self.q1])

    def test_relative_stack(self):
        r = self.aos_round(str(self.agent), env={"AOS_STACK": "ws/.stack/", "AOS_WS": "ws"})   # 從 cwd（tmp）算，不是從 round 資料夾
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(self.state(), "think")

    def test_stop_under_loop(self):
        self.loop(max=50)
        r = self.whole()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([x for x, _, _ in self.states()], ["idle", "think", "act", "think", "finish", "idle"])
        self.assertEqual(self.states()[-1], ("idle", 10, None))
        self.assertTrue(self.answer().startswith("FAKE ANSWER to: 幾點？（clock said:"))
        self.assertEqual((self.ls("new"), self.ls("cur")), ([], []))

    def test_idle_under_loop_with_ctl(self):
        """AOS_ROUND_ON_EMPTY=idle（round 槽的 env）＋interval_ms：答完後 idle 一行一行（next 都是 idle）；paused 時新信留在 new/，放行後答出；stopped 收工。"""
        self.parts["round"] = {"path": ROUND, "env": {"AOS_ROUND_ON_EMPTY": "idle"}}
        self.save()
        self.loop(interval_ms=100, ctl="ctl.json", state="state.json")
        p = subprocess.Popen([EXEC, str(self.agent)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                             env=self.env(), cwd=self.tmp)
        self.addCleanup(lambda: (p.poll() is None and p.kill(), p.communicate()))

        def until(what, cond, secs=30):
            end = time.time() + secs
            while time.time() < end:
                if cond():
                    return
                time.sleep(0.05)
            self.fail("等不到：" + what)

        def phase():
            try:
                return json.loads((self.stack / "state.json").read_text()).get("phase")
            except (OSError, ValueError):
                return None

        def idles():
            n = 0
            for x in reversed(self.states()):
                if x != ("idle", 10, "idle"):
                    break
                n += 1
            return n

        until("第一題答完、idle 空轉兩次", lambda: self.answer() is not None and idles() >= 2)
        (self.stack / "ctl.json").write_text('{"paused": true}')
        until("loop 暫停", lambda: phase() == "paused")
        q2 = self.put("第二題")
        time.sleep(1)
        self.assertEqual(self.ls("new"), [q2])                                                   # 暫停：兩格之間不再起
        (self.stack / "ctl.json").write_text('{"paused": false}')
        until("第二題答完", lambda: (self.answer() or "").startswith("FAKE ANSWER to: 第二題") and not self.ls("cur") and not self.ls("new"))
        (self.stack / "ctl.json").write_text('{"stopped": true}')
        self.assertEqual(p.wait(timeout=30), 0)
        self.assertEqual(self.state(), "idle")

    def test_loop_timeout_kills_think(self):
        self.parts["endpoint/default"] = {"path": self.script("slow", "cat > /dev/null; sleep 30\n")}
        self.save()
        self.loop(exec={"argv": ["aos-round", {"$env": "AOS_CD"}], "timeout_ms": 2000}, max=10)
        t0 = time.time()
        r = self.whole()
        self.assertLess(time.time() - t0, 20)
        self.assertEqual(self.state(), "think")
        self.assertEqual(r.returncode, 143, r.stderr)                                           # 單子逾時：整群收，fsm 那格 143、表沒接
        self.assertEqual(self.states()[-1], ("think", 143, None))
        self.assertEqual([m["role"] for m in self.history()], ["user"])

    def test_own_errors(self):
        r = self.aos_round()
        self.assertEqual((r.returncode, err_code("aos-round", r.stderr)), (1, "ArgumentsBad"))
        r = self.aos_round(str(self.agent), "x")
        self.assertEqual((r.returncode, err_code("aos-round", r.stderr)), (1, "ArgumentsBad"))
        r = self.aos_round("agent")
        self.assertEqual((r.returncode, err_code("aos-round", r.stderr)), (1, "AgentBad"))
        self.parts["round"] = {"path": ROUND, "env": {"AOS_ROUND_ON_EMPTY": "wait"}}
        self.save()
        r = self.aos_round(str(self.agent))
        self.assertEqual((r.returncode, err_code("aos-round", r.stderr)), (1, "SettingBad"))
        self.parts["round"] = {"path": str(self.tmp / "nope")}
        self.save()
        r = self.aos_round(str(self.agent))
        self.assertEqual((r.returncode, err_code("aos-round", r.stderr)), (1, "PartsBad"))
        self.assertFalse((self.stack / "state.txt").exists())

    def test_fsm_not_on_path(self):
        """PATH 上沒有 aos-fsm：CommandMissing、說「PATH 上找不到」，不印 PATH 最後一格的路徑（10-30 晚真腦實測發現 1）。"""
        path = os.pathsep.join([str(ROOT / "bin"), "/usr/bin", "/bin"])        # 有 aos-parts、沒有 aos-fsm
        r = self.aos_round(str(self.agent), env={"PATH": path})
        self.assertEqual((r.returncode, err_code("aos-round", r.stderr)), (1, "CommandMissing"))
        self.assertIn("PATH 上找不到可執行的 aos-fsm", r.stderr)
        self.assertNotIn("/bin/aos-fsm", r.stderr)


if __name__ == "__main__":
    unittest.main()
