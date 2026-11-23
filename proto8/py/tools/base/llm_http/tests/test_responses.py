"""Test llm_http endpoint.api "responses" and reasoning_effort: request conversion, the configuration_update item, reply and usage converted back."""

import http.server
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import unittest

ENTRY = Path(__file__).resolve().parents[1] / "_entry"
sys.path.insert(0, str(ENTRY.parent))
import responses_api  # noqa: E402

RESPONSES_REPLY = {"model": "m-answered", "output": [
    {"type": "reasoning", "summary": []},
    {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "o"}, {"type": "output_text", "text": "k"}]},
    {"type": "function_call", "call_id": "c1", "name": "peek", "arguments": "{}"}],
    "usage": {"input_tokens": 100, "output_tokens": 7, "total_tokens": 107,
              "input_tokens_details": {"cached_tokens": 64}, "output_tokens_details": {"reasoning_tokens": 3}}}
CHAT_REPLY = {"choices": [{"message": {"role": "assistant", "content": "hi"}}], "model": "m"}


class Recorder(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)))
        self.server.seen.append((self.path, data))
        body = json.dumps(RESPONSES_REPLY if self.path.endswith("/responses") else CHAT_REPLY).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def log_message(self, *a):
        pass


class Convert(unittest.TestCase):
    def test_request_shape(self):
        request = {"model": "m", "temperature": 0.2, "max_tokens": 5, "litellm_session_id": "s",
                   "tools": [{"type": "function", "function": {"name": "peek", "parameters": {"type": "object"}}}],
                   "tool_choice": {"type": "function", "function": {"name": "peek"}},
                   "messages": [{"role": "system", "content": "be brief"},
                                {"role": "user", "content": "hi"},
                                {"role": "assistant", "content": None, "tool_calls": [
                                    {"id": "c0", "type": "function", "function": {"name": "peek", "arguments": "{}"}}]},
                                {"role": "tool", "tool_call_id": "c0", "content": "12:00"},
                                {"role": "user", "content": [{"type": "text", "text": "and now"},
                                                             {"type": "image_url", "image_url": {"url": "data:x"}}]}]}
        out = responses_api.body(request, "high")
        self.assertEqual(out["instructions"], "be brief")
        self.assertEqual(out["input"], [
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hi"}]},
            {"type": "function_call", "call_id": "c0", "name": "peek", "arguments": "{}"},
            {"type": "function_call_output", "call_id": "c0", "output": "12:00"},
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "and now"},
                                                            {"type": "input_image", "image_url": "data:x"}]},
            {"type": "configuration_update", "reasoning": {"effort": "high"}}])
        self.assertEqual(out["tools"], [{"type": "function", "name": "peek", "parameters": {"type": "object"},
                                         "strict": False}])
        self.assertEqual(out["tool_choice"], {"type": "function", "name": "peek"})
        self.assertEqual(out["max_output_tokens"], 5)
        self.assertEqual((out["model"], out["temperature"], out["litellm_session_id"]), ("m", 0.2, "s"))
        for key in ("messages", "max_tokens", "reasoning"):
            self.assertNotIn(key, out)

    def test_function_tools_without_strict_get_strict_false(self):
        params = {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}}}
        out = responses_api.body({"messages": [], "tools": [
            {"type": "function", "function": {"name": "a", "parameters": params}},
            {"type": "function", "function": {"name": "b", "parameters": params, "strict": True}},
            {"type": "function", "name": "c", "parameters": params},
            {"type": "web_search"}]})
        self.assertEqual([tool.get("strict", "absent") for tool in out["tools"]], [False, True, False, "absent"])
        self.assertEqual(out["tools"][0]["parameters"], params)           # parameters untouched: no required added

    def test_without_effort_there_is_no_update_item_and_the_prefix_is_the_same(self):
        request = {"messages": [{"role": "user", "content": "hi"}]}
        low, plain = responses_api.body(request, "low"), responses_api.body(request)
        self.assertEqual(plain["input"], low["input"][:-1])
        self.assertNotIn("reasoning", low)

    def test_request_parameter_goes_to_the_top_level(self):
        out = responses_api.body({"messages": [], "reasoning_effort": "low"}, "high")
        self.assertEqual(out["reasoning"], {"effort": "low"})
        self.assertEqual(out["input"], [{"type": "configuration_update", "reasoning": {"effort": "high"}}])

    def test_reply_and_usage(self):
        message, usage = responses_api.reply(RESPONSES_REPLY)
        self.assertEqual(message, {"role": "assistant", "content": "ok", "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "peek", "arguments": "{}"}}]})
        self.assertEqual(usage, {"prompt_tokens": 100, "completion_tokens": 7, "total_tokens": 107,
                                 "prompt_tokens_details": {"cached_tokens": 64},
                                 "completion_tokens_details": {"reasoning_tokens": 3}})
        self.assertEqual(responses_api.reply({"output": []}), ({"role": "assistant", "content": None}, None))
        for bad in ({}, {"output": [1]}, {"output": [{"type": "function_call"}]}):
            with self.subTest(bad=bad):
                self.assertRaises((ValueError, KeyError, TypeError), responses_api.reply, bad)


class Run(unittest.TestCase):
    def setUp(self):
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Recorder)
        self.server.daemon_threads = True
        self.server.seen = []
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()
        self.url = "http://127.0.0.1:%d/v1" % self.server.server_address[1]
        self.addCleanup(self.thread.join)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def call(self, endpoint, **top):
        args = dict({"endpoint": dict({"url": self.url, "model": "m"}, **endpoint),
                     "request": {"messages": [{"role": "user", "content": "hi"}]}}, **top)
        r = subprocess.run([sys.executable, str(ENTRY)], input=json.dumps(args), text=True, capture_output=True,
                           timeout=30, env={k: v for k, v in os.environ.items()})
        return r.returncode, r.stdout.strip(), r.stderr.strip()

    def test_responses_api_with_effort(self):
        code, out, err = self.call({"api": "responses"}, reasoning_effort="xhigh")
        self.assertEqual((code, err), (0, ""))
        path, sent = self.server.seen[0]
        self.assertEqual(path, "/v1/responses")
        self.assertEqual(sent["input"][-1], {"type": "configuration_update", "reasoning": {"effort": "xhigh"}})
        reply = json.loads(out)
        self.assertEqual(reply["model"], "m-answered")
        self.assertEqual(reply["message"]["content"], "ok")
        self.assertEqual(reply["usage"]["prompt_tokens_details"], {"cached_tokens": 64})

    def test_chat_api_with_effort_sets_the_parameter(self):
        code, out, err = self.call({}, reasoning_effort="low")
        self.assertEqual((code, err), (0, ""))
        path, sent = self.server.seen[0]
        self.assertEqual(path, "/v1/chat/completions")
        self.assertEqual(sent["reasoning_effort"], "low")

    def test_chat_api_without_effort_is_unchanged(self):
        self.call({})
        self.assertNotIn("reasoning_effort", self.server.seen[0][1])

    def test_bad_api_and_bad_effort(self):
        for endpoint, top in (({"api": "completions"}, {}), ({}, {"reasoning_effort": ""}),
                              ({"api": "responses"}, {"reasoning_effort": 3})):
            with self.subTest(endpoint=endpoint, top=top):
                code, out, err = self.call(endpoint, **top)
                self.assertEqual(code, 1)
                self.assertEqual(json.loads(out)["error"]["code"], "ArgumentsBad")
        self.assertEqual(self.server.seen, [])


if __name__ == "__main__":
    unittest.main()
