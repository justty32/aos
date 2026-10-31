"""test_round_endpoint - agent-round 落地第 1 步：lib/endpoint/fake、lib/endpoint/openai（問腦的格）（10-31 自 test_round.py 拆出，行為不變）。

endpoint：fake 照規則吐一則；openai 接假的 OpenAI 相容 server 吐真的、usage.jsonl 多一行、經 aos-parts run 帶註冊檔的 env；
  401／403 KeyBad、連不上（dead_brain.DEAD）與 5xx BrainFailed、404 ModelUnknown、其他 4xx RequestBad、壞回覆 ReplyBad，失敗時 stdout 與 usage.jsonl 都不動。
設計：proto8/thinking/2026-10-28-agent-round.md § 3、§ 4、文末「實作時代定」；2026-10-30-agent-lifecycle 結論 A、B-11。
LiteLLM（localhost:4000）實跑那案連不上就 skip。"""
import http.server, json, os, subprocess, threading, unittest, urllib.request

from round_common import req, Base, FAKE, user, err_code, OPENAI, PARTS  # noqa: E402
from dead_brain import DEAD  # noqa: E402

REAL_URL = "http://localhost:4000/v1"
CLOCK_TOOL = {"type": "function", "function": {"name": "clock", "parameters": {"type": "object", "properties": {}}}}


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


if __name__ == "__main__":
    unittest.main()
