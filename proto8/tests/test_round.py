"""test_round - agent-round 落地第 1、4 步：lib/endpoint/fake、lib/endpoint/openai（問腦的格）與 lib/agent/act（跑工具的格）。

endpoint：fake 照規則吐一則；openai 接假的 OpenAI 相容 server 吐真的、usage.jsonl 多一行、經 aos-parts run 帶註冊檔的 env；
  401／403 KeyBad、連不上（dead_brain.DEAD）與 5xx BrainFailed、404 ModelUnknown、其他 4xx RequestBad、壞回覆 ReplyBad，失敗時 stdout 與 usage.jsonl 都不動。
act：兩個 tool_calls 吐兩則、順序對；MAX_PARALLEL=2 真的一起跑、順序仍對；pre_tool 退 10＝不跑、stdout 當 content；post_tool 取代；
  ToolUnknown／ArgumentsBad／工具退非 0 接成 tool 訊息；插話（new/ 有題＋on_interrupt 說 interrupt）剩下的不跑、退 10；aos-tools 壞＝ToolsBad。
設計：proto8/thinking/2026-10-28-agent-round.md § 3、§ 4、文末「實作時代定」。LiteLLM（localhost:4000）實跑那案連不上就 skip。"""
import http.server, json, os, re, subprocess, tempfile, threading, unittest, urllib.request
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
         "AOS_BRAIN_KEY", "AOS_KERNEL_REPORT", "TIMEOUT_MS", "ENDPOINT_NAME", "MAX_PARALLEL")
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
        # 第二次：stdin 給的 model 優先、空 tools 不送、沒 usage 也記一行（usage＝null）、ENDPOINT_NAME 改名
        r = self.ask(b.url, {"ENDPOINT_NAME": "litellm"}, stdin=json.dumps({"messages": [user("x")], "tools": [], "model": "m2"}))
        self.assertEqual(self.lines(r.stdout), [{"role": "assistant", "content": "好"}])
        self.assertEqual(b.requests[1], {"messages": [user("x")], "model": "m2"})
        self.assertIsNone(b.auth[1])
        self.assertEqual([(x["endpoint"], x["model"], x["usage"]) for x in self.usage()[1:]], [("litellm", "m2", None)])

    def test_via_parts_registry_env(self):
        b = self.brain({"choices": [{"message": {"role": "assistant", "content": "經註冊檔"}}]})
        (self.agent / "parts.json").write_text(json.dumps({"parts": {"endpoint/main": {
            "path": OPENAI, "env": {"AOS_BRAIN_URL": b.url, "AOS_BRAIN_MODEL": "reg", "ENDPOINT_NAME": "main"}}}}))
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
        self.assert_fails("TimeoutBad", self.ask(DEAD, {"TIMEOUT_MS": "0"}))
        self.assert_fails("RequestBad", self.ask(DEAD, stdin='{"messages": "x"}'))

    @unittest.skipUnless(os.environ.get("AOS_TEST_REAL", "1") != "0", "")
    def test_real_litellm(self):
        try:
            urllib.request.urlopen(REAL_URL + "/models", timeout=3).read()
        except OSError:
            self.skipTest("localhost:4000 連不上")
        model = os.environ.get("AOS_REAL_MODEL", "fast")
        r = self.ask(REAL_URL, {"AOS_BRAIN_MODEL": model, "TIMEOUT_MS": "120000"}, stdin=req(user("只回一個字：好")))
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
        r = self.act(calls, {"MAX_PARALLEL": "2"})
        self.assertEqual(r.returncode, 0, r.stderr)
        out = self.lines(r.stdout)
        self.assertEqual([m["tool_call_id"] for m in out], ["a", "b"])
        self.assertTrue(out[0]["content"].startswith("saw\nA\n"), out[0])          # a 等到了 b 建的檔＝真的一起跑
        os.unlink(self.ws / "mark")
        r = self.act(calls)                                                     # 依序：a 先跑、等不到
        self.assertTrue(self.lines(r.stdout)[0]["content"].startswith("no\nA\n"))
        r = self.act(calls, {"MAX_PARALLEL": "x"})
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
        (self.ws / "new").mkdir()
        (self.ws / "new" / "q9.txt").write_text("插話")
        calls = assistant(call("a", "say", text="A"), call("b", "say", touch="ran_b"), call("c", "clock"))
        r = self.act(calls)                                                     # 沒掛 on_interrupt＝wait
        self.assertEqual((r.returncode, len(self.lines(r.stdout))), (0, 3), r.stderr)
        os.unlink(self.ws / "ran_b")
        self.hook("on_interrupt", 'read n; [ "$n" = q9.txt ] && echo interrupt\n')
        r = self.act(calls)
        self.assertEqual(r.returncode, 10, r.stderr)
        out = self.lines(r.stdout)
        self.assertEqual([m["tool_call_id"] for m in out], ["a", "b", "c"])
        self.assertEqual(out[0]["content"], "A|%s/say/\n" % self.stack)
        self.assertEqual(out[1]["content"], "act: Interrupted 有新題（q9.txt），這個工具沒跑\n")
        self.assertFalse((self.ws / "ran_b").exists())
        os.unlink(self.ws / "new" / "q9.txt")                                   # new/ 空了＝不問、全跑
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


class Round(Base):
    """lib/agent/round（agent-round § 7 第 5 步）：照「從哪接著做」叫各格；經 aos-parts run round 叫（註冊檔的 env 給 round）。"""

    def setUp(self):
        super().setUp()
        self.parts = {"round": {"path": ROUND}, "queue": {"path": str(AGENT_LIB / "queue")},
                      "history": {"path": str(AGENT_LIB / "history")}, "act": {"path": ACT},
                      "endpoint/default": {"path": FAKE}}
        self.save()
        (self.agent / "tools.json").write_text(json.dumps({"tools": {"clock": {"path": CLOCK}}}))
        self.put("q1.txt", "幾點？")

    def save(self):
        (self.agent / "parts.json").write_text(json.dumps({"parts": self.parts}, ensure_ascii=False))

    def put(self, name, text):
        (self.ws / "new").mkdir(exist_ok=True)
        (self.ws / "new" / name).write_text(text)

    def script(self, name, body, sh=True):
        p = self.tmp / "scripts" / name
        p.mkdir(parents=True)
        (p / "_entry").write_text(("#!/bin/sh\n" if sh else "") + body)
        (p / "_entry").chmod(0o755)
        return str(p)

    def hook(self, point, body):
        self.parts["hook/" + point] = {"path": self.script("hook_" + point, body)}
        self.save()

    def round(self, *flags, env=None):
        return subprocess.run([PARTS, "--file", str(self.agent / "parts.json"), "run", "round", str(self.agent)] + list(flags),
                              capture_output=True, text=True, env=self.env(env), cwd=self.tmp, timeout=120)

    def history(self):
        p = self.stack / "history.jsonl"
        return self.lines(p.read_text()) if p.exists() else []

    def trace(self):
        return [t["unit"] for t in self.lines((self.stack / "trace.jsonl").read_text())]

    def ls(self, stage):
        d = self.ws / stage
        return sorted(x.name for x in d.iterdir()) if d.is_dir() else []

    def test_fake_brain_one_question_then_no_question(self):
        (self.agent / "system.txt").write_text("你是測試")
        log = self.tmp / "req.log"
        self.parts["endpoint/default"] = {"path": self.script("rec", 'tee -a "%s" | exec aos-exec "%s" "$1"\n' % (log, FAKE))}
        self.save()
        r = self.round()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex((self.ws / "out" / "q1.txt").read_text(), r"^FAKE ANSWER to: 幾點？（clock said: \d{4}-.*Z）\n$")
        self.assertEqual((self.ls("new"), self.ls("cur"), self.ls("done")), ([], [], ["q1.txt"]))
        self.assertEqual([m["role"] for m in self.history()], ["user", "assistant", "tool", "assistant"])
        first = self.lines(log.read_text())[0]
        self.assertEqual(first["messages"][0], {"role": "system", "content": "你是測試"})      # system 每次帶、不進 history
        self.assertEqual(first["tools"][0]["function"]["name"], "clock")                       # tools.json → OpenAI tools
        self.assertEqual(self.trace(), ["queue claim", "history read", "endpoint/default", "history append", "queue emit",
                                        "history read", "act", "history append", "history read", "endpoint/default",
                                        "history append", "queue emit", "history read", "queue finish"])
        t = self.lines((self.stack / "trace.jsonl").read_text())[0]
        self.assertEqual(set(t), {"started_at", "unit", "code", "elapsed_ms"})
        self.assertRegex(t["started_at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$")
        r = self.round()
        self.assertEqual((r.returncode, r.stderr), (10, ""))                                    # 沒題退 10

    def test_endpoint_broken_then_on_error_switch(self):
        self.parts["endpoint/default"] = {"path": OPENAI, "env": {"AOS_BRAIN_URL": DEAD, "AOS_BRAIN_MODEL": "m"}}
        self.save()
        r = self.round()
        self.assertEqual(r.returncode, 1)
        self.assertEqual(err_code("endpoint", r.stderr), "BrainFailed")                         # 格自己說、round 不轉述
        self.assertEqual([m["role"] for m in self.history()], ["user"])                          # 沒多接 assistant
        self.assertEqual(self.ls("cur"), ["q1.txt"])
        self.parts["endpoint/fake"] = {"path": FAKE}
        self.hook("on_error", 'read line; case "$line" in "endpoint: BrainFailed "*) echo switch;; esac\n')
        r = self.round()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.stack / "endpoint.txt").read_text(), "fake\n")
        self.assertTrue((self.ws / "out" / "q1.txt").read_text().startswith("FAKE ANSWER to: 幾點？"))
        self.assertEqual([m["role"] for m in self.history()], ["user", "assistant", "tool", "assistant"])

    def test_retry_has_a_limit(self):
        self.parts["endpoint/default"] = {"path": OPENAI, "env": {"AOS_BRAIN_URL": DEAD, "AOS_BRAIN_MODEL": "m"}}
        self.parts["round"]["env"] = {"MAX_RETRIES": "2"}
        self.hook("on_error", "cat > /dev/null; echo retry\n")
        r = self.round()
        self.assertEqual(r.returncode, 1)
        self.assertEqual(err_code("round", r.stderr), "EndpointFailed")
        self.assertEqual(self.trace().count("endpoint/default"), 3)                              # 1 次＋重來 2 次
        self.assertFalse((self.stack / "endpoint.txt").exists())

    def test_pause_yields_and_next_round_resumes(self):
        self.hook("pause", "exit 10\n")
        r = self.round()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.ls("cur"), self.ls("out")), (["q1.txt"], []))                     # yield：還沒答
        self.assertEqual([m["role"] for m in self.history()], ["user", "assistant", "tool"])
        r = self.round()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.ls("done"), ["q1.txt"])
        self.assertEqual(self.trace().count("queue claim"), 1)                                   # 接著做、不重新認領

    def test_step_one_unit_at_a_time(self):
        codes = [self.round("--step").returncode for _ in range(7)]
        self.assertEqual(codes, [0, 0, 0, 0, 0, 10, 10])                                          # 認領、問腦、工具、問腦、交卷
        self.assertTrue((self.ws / "out" / "q1.txt").read_text().startswith("FAKE ANSWER to: 幾點？（clock said:"))

    def test_step_under_aos_loop(self):
        (self.agent / "loop.json").write_text(json.dumps(
            {"exec": {"argv": ["aos-parts", "run", "round", {"$env": "AOS_CD"}, "--step"]}, "max": 20}))
        (self.agent / "_entry").write_text('["aos-loop", "loop.json"]')
        r = subprocess.run([EXEC, str(self.agent)], capture_output=True, text=True, env=self.env(), cwd=self.tmp, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.ls("done"), ["q1.txt"])
        self.assertEqual(self.trace().count("queue claim"), 1)

    def test_pre_round_fails_round_fails(self):
        self.hook("pre_round", "exit 3\n")
        r = self.round()
        self.assertEqual(r.returncode, 3)
        self.assertEqual((self.ls("new"), self.ls("cur")), (["q1.txt"], []))                     # 沒認領
        self.assertEqual(self.history(), [])

    def test_interrupt_claims_more_and_asks_again(self):
        self.parts["endpoint/default"] = {"path": self.script("two", TWO_CLOCKS, sh=False)}
        self.hook("on_interrupt", 'read n; [ "$n" = q2.txt ] && echo interrupt\n')
        self.put("q2.txt", "插話")
        r = self.round()
        self.assertEqual(r.returncode, 0, r.stderr)
        h = self.history()
        self.assertEqual([m["role"] for m in h], ["user", "assistant", "tool", "tool", "user", "assistant"])
        self.assertTrue(h[3]["content"].startswith("act: Interrupted 有新題（q2.txt）"), h[3])
        self.assertEqual(h[4]["content"].strip(), "插話")
        self.assertEqual(self.ls("done"), ["q1.txt", "q2.txt"])                                   # 一起答
        for q in ("q1.txt", "q2.txt"):
            self.assertEqual((self.ws / "out" / q).read_text(), "答：幾點？／插話\n")
        self.assertIn("queue claim --more", self.trace())

    def test_own_errors(self):
        del self.parts["act"]
        self.save()
        r = self.round()
        self.assertEqual((r.returncode, err_code("round", r.stderr)), (1, "PartMissing"))         # 必要的格沒有
        r = subprocess.run([EXEC, ROUND, "agent"], capture_output=True, text=True, env=self.env(), cwd=self.tmp, timeout=60)
        self.assertEqual((r.returncode, err_code("round", r.stderr)), (1, "AgentBad"))
        self.parts["round"]["env"] = {"MAX_RETRIES": "-1"}
        self.save()
        r = self.round()
        self.assertEqual((r.returncode, err_code("round", r.stderr)), (1, "SettingBad"))


if __name__ == "__main__":
    unittest.main()
