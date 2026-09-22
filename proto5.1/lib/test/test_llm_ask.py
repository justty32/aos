"""aos_llm_ask：組請求（build_request）、打引擎（call／ask）、命令列（cli/aos-llm-ask）——照 spec/aos-llm-ask.md。

HTTP 那群用 http.server 在執行緒裡開一個假的 chat/completions（能回正常、回 500、回壞 JSON、回沒有
choices、故意慢讓逾時觸發），**不打真模型**；命令列那群開子進程驗退出碼 0／1／2／3 與 stdout 只有一行。
"""
import json
import os
import socket
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from _util import AgentCase, TOOL_SH

import aos_llm_ask
from aos_llm_ask import AgentError, EngineFailed

OK_MESSAGE = {"role": "assistant", "content": "裡面有 state.json、prompts、tools…"}
# 連不上的 endpoint：.invalid 這個網域保證解不開（RFC 2606），一下就失敗。
# 不用 127.0.0.1 的死 port：這台 WSL 連 localhost 沒人聽的 port 會等到逾時而不是被拒。
UNREACHABLE = "http://nope.invalid/v1"


# ---------------------------------------------------------------- 假的 chat/completions ----

class FakeLLM:
    """一個假的 OpenAI 相容伺服器：`mode` 決定怎麼回，`requests` 記下收到的每一筆（路徑、標頭、body）。"""

    def __init__(self):
        self.mode = "ok"
        self.message = dict(OK_MESSAGE)
        self.sleep = 0.0
        self.requests = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(n)
                fake.requests.append({"path": self.path, "headers": dict(self.headers),
                                      "body": json.loads(raw) if raw else None})
                if fake.sleep:
                    time.sleep(fake.sleep)
                mode = fake.mode
                if mode == "ok":
                    self._json(200, {"id": "x", "object": "chat.completion",
                                     "choices": [{"index": 0, "message": fake.message, "finish_reason": "stop"}],
                                     "usage": {"total_tokens": 1}})
                elif mode == "500":
                    self._json(500, {"error": {"message": "model exploded"}})
                elif mode == "404":
                    self._json(404, {"error": "no such route"})
                elif mode == "badjson":
                    self._raw(200, b"<html>not json</html>")
                elif mode == "nochoices":
                    self._json(200, {"id": "x", "choices": []})
                elif mode == "nomessage":
                    self._json(200, {"choices": [{"index": 0, "text": "old style"}]})
                elif mode == "notobject":
                    self._json(200, [1, 2, 3])
                elif mode == "truncated":       # 標頭說 100 bytes，只給一半就掛掉
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", "100")
                    self.end_headers()
                    self.wfile.write(b'{"choices": [')
                    self.wfile.flush()
                    self.connection.shutdown(socket.SHUT_RDWR)
                else:
                    raise AssertionError(mode)

            def _json(self, code, obj):
                self._raw(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

            def _raw(self, code, data):
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):        # 別把每筆請求印到測試輸出
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.endpoint = "http://127.0.0.1:%d/v1" % self.server.server_address[1]

    def close(self):
        self.server.shutdown()
        self.server.server_close()

    @property
    def last(self):
        return self.requests[-1]


class LLMCase(AgentCase):
    """每條測試自己一個假伺服器；`agent()` 預設把 engine 指到它。"""

    def setUp(self):
        super().setUp()
        self.llm = FakeLLM()
        self.addCleanup(self.llm.close)

    def agent(self, info=None, **kw):
        obj = dict(info or {})
        eng = dict(obj.get("engine") or {})
        eng.setdefault("endpoint", self.llm.endpoint)
        eng.setdefault("model", "fake-model")
        obj["engine"] = eng
        return super().agent(info=obj, **kw)


# ---------------------------------------------------------------- build_request ----

class TestBuildRequest(AgentCase):

    def test_spec_example(self):
        """aos-llm-ask.md §3 那個 body：system 一則 ＋ 記憶 ＋ 去 _meta 的工具 ＋ params。"""
        d = self.agent(system={"content": "你是個簡潔、會用工具的助手。"},
                       history=[{"role": "user", "content": "看看資料夾裡有什麼"}],
                       tools={"tools/base.json": [TOOL_SH]},
                       info={"engine": {"endpoint": "http://127.0.0.1:1234/v1", "model": "qwen/qwen3-1.7b",
                                        "params": {"temperature": 0.2}}})
        body = aos_llm_ask.build_request(d)
        self.assertEqual(body, {
            "model": "qwen/qwen3-1.7b",
            "messages": [{"role": "system", "content": "你是個簡潔、會用工具的助手。"},
                         {"role": "user", "content": "看看資料夾裡有什麼"}],
            "tools": [{"type": "function", "function": TOOL_SH["function"]}],
            "temperature": 0.2})
        self.assertEqual(list(body), ["model", "messages", "tools", "temperature"])

    def test_empty_system_means_no_system_message(self):
        d = self.agent(system={"content": ""}, history=[{"role": "user", "content": "hi"}])
        self.assertEqual(aos_llm_ask.build_request(d)["messages"], [{"role": "user", "content": "hi"}])
        d = self.agent(history=[{"role": "user", "content": "hi"}])          # 沒檔也一樣
        self.assertEqual(aos_llm_ask.build_request(d)["messages"], [{"role": "user", "content": "hi"}])

    def test_empty_history_means_only_system(self):
        d = self.agent(system={"content": "S"})
        self.assertEqual(aos_llm_ask.build_request(d)["messages"], [{"role": "system", "content": "S"}])

    def test_nothing_at_all_means_empty_messages(self):
        self.assertEqual(aos_llm_ask.build_request(self.agent())["messages"], [])

    def test_history_verbatim_including_unknown_keys(self):
        h = [{"role": "user", "content": "a", "name": "bob", "_ts": 1},
             {"role": "assistant", "content": None, "tool_calls": [{"id": "c", "type": "function",
                                                                    "function": {"name": "sh", "arguments": "{}"}}],
              "reasoning_content": "hmm"},
             {"role": "tool", "tool_call_id": "c", "content": "out"}]
        self.assertEqual(aos_llm_ask.build_request(self.agent(history=h))["messages"], h)

    def test_no_tools_means_no_tools_field(self):
        self.assertNotIn("tools", aos_llm_ask.build_request(self.agent()))
        self.assertNotIn("tools", aos_llm_ask.build_request(self.agent(tools={"t.json": []})))

    def test_tools_merged_and_stripped(self):
        a = {"type": "function", "function": {"name": "a"}, "_meta": {"argv": ["x"]}, "_note": "n"}
        b = {"type": "function", "function": {"name": "b"}, "_meta": {"argv": ["y"]}}
        body = aos_llm_ask.build_request(self.agent(tools={"t1.json": [a], "t2.json": [b]}))
        self.assertEqual(body["tools"], [{"type": "function", "function": {"name": "a"}},
                                         {"type": "function", "function": {"name": "b"}}])

    def test_params_merged_at_top_level(self):
        d = self.agent(info={"engine": {"endpoint": "e", "model": "m",
                                        "params": {"temperature": 0.2, "max_tokens": 10, "response_format": {"type": "text"}}}})
        body = aos_llm_ask.build_request(d)
        self.assertEqual((body["temperature"], body["max_tokens"], body["response_format"]), (0.2, 10, {"type": "text"}))

    def test_params_cannot_override_reserved(self):
        d = self.agent(history=[{"role": "user", "content": "hi"}],
                       info={"engine": {"endpoint": "e", "model": "m",
                                        "params": {"model": "other", "messages": [], "tools": [{"x": 1}],
                                                   "stream": True, "temperature": 1}}})
        body = aos_llm_ask.build_request(d)
        self.assertEqual(body["model"], "m")
        self.assertEqual(body["messages"], [{"role": "user", "content": "hi"}])
        self.assertNotIn("tools", body)
        self.assertNotIn("stream", body)
        self.assertEqual(body["temperature"], 1)

    def test_stream_never_sent(self):
        self.assertNotIn("stream", aos_llm_ask.build_request(self.agent()))

    def test_cpu_never_sent_even_from_params(self):
        d = self.agent(info={"engine": {"endpoint": "e", "model": "m", "cpu": "../cpu",
                                        "params": {"cpu": "private/path", "temperature": 0.3}}})
        body = aos_llm_ask.build_request(d)
        self.assertNotIn("cpu", body)
        self.assertEqual(body["temperature"], 0.3)

    def test_read_errors_raise_agent_error(self):
        with self.assertRaises(AgentError) as cm:
            aos_llm_ask.build_request(self.d)
        self.assertEqual(cm.exception.code, "NotAnAgent")
        d = self.agent(history=[{"role": "system", "content": "x"}])
        with self.assertRaises(AgentError) as cm:
            aos_llm_ask.build_request(d)
        self.assertEqual(cm.exception.code, "MessageInvalid")

    def test_env_parameter(self):
        d = self.agent(info={"engine": {"endpoint": "e", "model": {"$env": "MODEL"}}})
        self.assertEqual(aos_llm_ask.build_request(d, env={"MODEL": "from-env"})["model"], "from-env")

    def test_does_not_touch_network_or_state(self):
        self.write("state.json", "{broken")
        d = self.agent(info={"engine": {"endpoint": UNREACHABLE, "model": "m"}})
        aos_llm_ask.build_request(d)        # 打不到的 endpoint 也沒關係
        self.assertEqual(self.read("state.json"), "{broken")


# ---------------------------------------------------------------- call／ask（假伺服器）----

class TestAsk(LLMCase):

    def test_ok_returns_choices0_message(self):
        d = self.agent(system={"content": "S"}, history=[{"role": "user", "content": "hi"}],
                       tools={"t.json": [TOOL_SH]}, info={"engine": {"params": {"temperature": 0.2}}})
        msg = aos_llm_ask.ask(d)
        self.assertEqual(msg, OK_MESSAGE)
        req = self.llm.last
        self.assertEqual(req["path"], "/v1/chat/completions")
        self.assertEqual(req["headers"]["Content-Type"], "application/json")
        self.assertEqual(req["body"], aos_llm_ask.build_request(d))
        self.assertEqual(req["body"]["messages"][0], {"role": "system", "content": "S"})
        self.assertNotIn("_meta", req["body"]["tools"][0])
        self.assertNotIn("stream", req["body"])

    def test_message_verbatim_with_tool_calls_and_null_content(self):
        self.llm.message = {"role": "assistant", "content": None,
                            "tool_calls": [{"id": "c1", "type": "function",
                                            "function": {"name": "sh", "arguments": "{\"cmd\":\"ls\"}"}}],
                            "reasoning_content": "thinking…"}
        self.assertEqual(aos_llm_ask.ask(self.agent()), self.llm.message)

    def test_body_is_utf8_json(self):
        d = self.agent(history=[{"role": "user", "content": "中文 ✓"}])
        aos_llm_ask.ask(d)
        self.assertEqual(self.llm.last["body"]["messages"][0]["content"], "中文 ✓")

    def test_no_api_key_means_no_authorization_header(self):
        aos_llm_ask.ask(self.agent())
        self.assertNotIn("Authorization", self.llm.last["headers"])

    def test_empty_api_key_means_no_authorization_header(self):
        aos_llm_ask.ask(self.agent(info={"engine": {"api_key": ""}}))
        self.assertNotIn("Authorization", self.llm.last["headers"])

    def test_api_key_sent_as_bearer(self):
        aos_llm_ask.ask(self.agent(info={"engine": {"api_key": "sk-123"}}))
        self.assertEqual(self.llm.last["headers"]["Authorization"], "Bearer sk-123")

    def test_trailing_slashes_stripped(self):
        aos_llm_ask.ask(self.agent(info={"engine": {"endpoint": self.llm.endpoint + "/"}}))
        self.assertEqual(self.llm.last["path"], "/v1/chat/completions")
        aos_llm_ask.ask(self.agent(info={"engine": {"endpoint": self.llm.endpoint + "///"}}))
        self.assertEqual(self.llm.last["path"], "/v1/chat/completions")

    def test_endpoint_without_v1_is_literal(self):
        base = self.llm.endpoint[:-len("/v1")]
        aos_llm_ask.ask(self.agent(info={"engine": {"endpoint": base}}))
        self.assertEqual(self.llm.last["path"], "/chat/completions")

    def fails(self, mode, **engine):
        self.llm.mode = mode
        with self.assertRaises(EngineFailed) as cm:
            aos_llm_ask.ask(self.agent(info={"engine": engine}))
        return str(cm.exception)

    def test_http_500(self):
        msg = self.fails("500")
        self.assertIn("500", msg)
        self.assertIn("model exploded", msg)

    def test_http_404(self):
        self.assertIn("404", self.fails("404"))

    def test_bad_json(self):
        self.assertIn("JSON", self.fails("badjson"))

    def test_no_choices(self):
        self.assertIn("choices[0]", self.fails("nochoices"))

    def test_no_message(self):
        self.assertIn("message", self.fails("nomessage"))

    def test_response_not_object(self):
        self.assertIn("choices[0]", self.fails("notobject"))

    def test_truncated_response(self):
        self.fails("truncated")

    def test_cannot_connect(self):
        """主機名解不開（.invalid 保證不存在）；timeout_ms 只是保險，這條不該等到它。"""
        with self.assertRaises(EngineFailed) as cm:
            aos_llm_ask.ask(self.agent(info={"engine": {"endpoint": UNREACHABLE, "timeout_ms": 3000}}))
        self.assertIn("連不上", str(cm.exception))

    def test_timeout(self):
        self.llm.sleep = 1.0
        t0 = time.monotonic()
        msg = self.fails("ok", timeout_ms=150)
        self.assertLess(time.monotonic() - t0, 0.9)
        self.assertIn("逾時", msg)
        self.assertIn("150", msg)

    def test_engine_failed_is_not_agent_error(self):
        self.assertFalse(issubclass(EngineFailed, AgentError))
        self.assertFalse(issubclass(AgentError, EngineFailed))

    def test_read_error_raised_before_any_http(self):
        d = self.agent(history="[broken")
        with self.assertRaises(AgentError):
            aos_llm_ask.ask(d)
        self.assertEqual(self.llm.requests, [])

    def test_call_with_engine_and_body_directly(self):
        msg = aos_llm_ask.call({"endpoint": self.llm.endpoint, "model": "m", "params": {}, "api_key": None,
                                "timeout_ms": 1000}, {"model": "m", "messages": []})
        self.assertEqual(msg, OK_MESSAGE)
        self.assertEqual(self.llm.last["body"], {"model": "m", "messages": []})

    def test_ask_writes_nothing(self):
        d = self.agent(history=[{"role": "user", "content": "hi"}])
        before = self.read(os.path.join("prompts", "history.json"))
        aos_llm_ask.ask(d)
        self.assertEqual(self.read(os.path.join("prompts", "history.json")), before)
        self.assertFalse(self.exists("state.json"))


# ---------------------------------------------------------------- 命令列（開子進程）----

class TestCli(LLMCase):

    def one_line(self, r):
        self.assertEqual(r.stdout.count("\n"), 1, r.stdout)
        self.assertTrue(r.stdout.endswith("\n"))
        return json.loads(r.stdout)

    def test_dry_run_prints_request_and_exits_0(self):
        d = self.agent(system={"content": "S"}, history=[{"role": "user", "content": "hi"}],
                       tools={"t.json": [TOOL_SH]}, info={"engine": {"params": {"temperature": 0.2}}})
        r = self.ask(d, "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, "")
        self.assertEqual(self.one_line(r), aos_llm_ask.build_request(d))
        self.assertEqual(self.llm.requests, [])                 # 真的沒打出去

    def test_dry_run_flag_before_dir(self):
        d = self.agent()
        r = self.ask("--dry-run", d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.one_line(r)["model"], "fake-model")

    def test_dir_defaults_to_cwd(self):
        d = self.agent()
        r = self.ask("--dry-run", cwd=d)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_ask_prints_message_and_exits_0(self):
        d = self.agent(history=[{"role": "user", "content": "hi"}])
        r = self.ask(d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, "")
        self.assertEqual(self.one_line(r), OK_MESSAGE)
        self.assertEqual(len(self.llm.requests), 1)

    def test_output_is_compact_and_not_ascii_escaped(self):
        d = self.agent(history=[{"role": "user", "content": "hi"}])
        r = self.ask(d)
        self.assertIn("裡面有", r.stdout)
        self.assertNotIn(", ", r.stdout)

    def test_message_with_newlines_still_one_line(self):
        self.llm.message = {"role": "assistant", "content": "第一行\n第二行\n"}
        r = self.ask(self.agent())
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.one_line(r)["content"], "第一行\n第二行\n")

    def test_read_error_is_1(self):
        d = self.agent(history=[{"role": "system", "content": "x"}])
        for args in ((d,), (d, "--dry-run")):
            r = self.ask(*args)
            self.assertEqual(r.returncode, 1, r.stderr)
            self.assertEqual(r.stdout, "")
            self.assertTrue(r.stderr.startswith("aos-llm-ask: MessageInvalid: "), r.stderr)
            self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)

    def test_not_an_agent_is_1(self):
        r = self.ask(self.d)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertTrue(r.stderr.startswith("aos-llm-ask: NotAnAgent: "), r.stderr)

    def test_directive_error_is_1(self):
        d = self.agent(info={"system": {"$env": "AOSTEST_NOPE"}})
        r = self.ask(d, "--dry-run", env={k: v for k, v in os.environ.items() if k != "AOSTEST_NOPE"})
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertTrue(r.stderr.startswith("aos-llm-ask: EnvironmentVariableMissing: "), r.stderr)

    def test_env_is_the_process_environment(self):
        d = self.agent(info={"engine": {"model": {"$env": "AOSTEST_MODEL"}}})
        r = self.ask(d, "--dry-run", env=dict(os.environ, AOSTEST_MODEL="from-outer"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.one_line(r)["model"], "from-outer")

    def test_missing_dir_is_2(self):
        r = self.ask(os.path.join(self.d, "nope"))
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertEqual(r.stdout, "")
        self.assertTrue(r.stderr.startswith("aos-llm-ask: "), r.stderr)
        self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)

    def test_file_instead_of_dir_is_2(self):
        p = self.write("x.json", "{}")
        self.assertEqual(self.ask(p).returncode, 2)

    def test_unknown_flag_is_2(self):
        r = self.ask(self.agent(), "--stream")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertEqual(r.stdout, "")

    def test_extra_positional_is_2(self):
        self.assertEqual(self.ask(self.agent(), "extra").returncode, 2)

    def test_engine_failure_is_3(self):
        d = self.agent(history=[{"role": "user", "content": "hi"}])
        for mode, hint in (("500", "500"), ("badjson", "JSON"), ("nochoices", "choices[0]"), ("nomessage", "message")):
            self.llm.mode = mode
            r = self.ask(d)
            self.assertEqual(r.returncode, 3, r.stderr)
            self.assertEqual(r.stdout, "")
            self.assertTrue(r.stderr.startswith("aos-llm-ask: engine: "), r.stderr)
            self.assertIn(hint, r.stderr)
            self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)

    def test_cannot_connect_is_3(self):
        r = self.ask(self.agent(info={"engine": {"endpoint": UNREACHABLE, "timeout_ms": 3000}}))
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertTrue(r.stderr.startswith("aos-llm-ask: engine: "), r.stderr)

    def test_timeout_is_3(self):
        self.llm.sleep = 1.0
        r = self.ask(self.agent(info={"engine": {"timeout_ms": 150}}))
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertIn("逾時", r.stderr)

    def test_engine_failure_500_body_kept_on_one_line(self):
        self.llm.mode = "500"
        r = self.ask(self.agent())
        self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)

    def test_writes_nothing(self):
        d = self.agent(history=[{"role": "user", "content": "hi"}])
        before = sorted(os.listdir(d))
        self.ask(d)
        self.assertEqual(sorted(os.listdir(d)), before)


if __name__ == "__main__":
    unittest.main()
