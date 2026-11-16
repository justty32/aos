"""Test llm_http key handling, structured failures, HTTP classification and one local retry."""

import email.utils
import http.server
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import unittest

ENTRY = Path(__file__).resolve().parents[1] / "_entry"
VAR = "LLM_HTTP_TEST_KEY"
REPLY = {"choices": [{"message": {"role": "assistant", "content": "hi"}}], "model": "m"}
RUNNER = """import runpy, sys
from unittest.mock import patch
sys.argv = sys.argv[1:]
with patch('time.sleep') as sleep:
    try:
        runpy.run_path(sys.argv[0], run_name='__main__')
    finally:
        assert all(c.args == (1,) for c in sleep.call_args_list), sleep.call_args_list
"""


class FakeEndpoint(http.server.BaseHTTPRequestHandler):
    """Record requests and serve queued replies, including broken HTTP responses."""

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self.server.seen.append(dict(self.headers))
        spec = self.server.replies.pop(0) if self.server.replies else {}
        mode = spec.get("mode")
        if mode == "disconnect":
            self.close_connection = True
            return
        if mode == "bad_status":
            self.wfile.write(b"not an HTTP status\r\n\r\n")
            self.close_connection = True
            return
        status = spec.get("status", self.server.status)
        body = spec.get("body", REPLY if status == 200 else {"error": "no key"})
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body) + (10 if mode == "incomplete" else 0)))
        for key, value in spec.get("headers", {}).items():
            self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass
        self.close_connection = True

    def log_message(self, *a):
        pass


class LlmHttpTest(unittest.TestCase):
    def setUp(self):
        self.server = http.server.HTTPServer(("127.0.0.1", 0), FakeEndpoint)
        self.server.seen, self.server.status, self.server.replies = [], 200, []
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()
        self.url = "http://127.0.0.1:%d/v1" % self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def arguments(self):
        return {"endpoint": {"url": self.url, "model": "m"},
                "request": {"messages": [{"role": "user", "content": "hi"}]}}

    def call(self, key=None, key_env=True, args=None, raw=None, flags=None, runner=RUNNER):
        env = {k: v for k, v in os.environ.items() if k != VAR}
        if key is not None:
            env[VAR] = key
        argv = [sys.executable, "-c", runner, str(ENTRY)]
        argv += flags if flags is not None else (["--key-env", VAR] if key_env else [])
        data = raw if raw is not None else json.dumps(self.arguments() if args is None else args)
        r = subprocess.run(argv, input=data, text=True, capture_output=True, env=env, timeout=30)
        return r.returncode, r.stdout.strip(), r.stderr.strip()

    def failure(self, result, code, retry, tries, status=None, stderr_code=None):
        exit_code, out, err = result
        self.assertEqual(exit_code, 1, (out, err))
        self.assertEqual(len(out.splitlines()), 1, out)
        reply = json.loads(out)
        self.assertEqual(set(reply), {"error"})
        error = reply["error"]
        self.assertEqual(error["code"], code)
        self.assertIs(error["retry"], retry)
        self.assertEqual(error["tries"], tries)
        self.assertIsInstance(error["msg"], str)
        self.assertEqual(len(err.splitlines()), 1, err)
        self.assertTrue(err.startswith("llm_http: error: %s " % (stderr_code or code)), err)
        if status is None:
            self.assertNotIn("status", error)
        else:
            self.assertEqual(error["status"], status)
        return error

    def auth(self):
        return [h.get("Authorization") for h in self.server.seen]

    def test_unset_sends_no_header(self):
        code, out, err = self.call()
        self.assertEqual(code, 0, (out, err))
        reply = json.loads(out)
        self.assertEqual(reply["message"]["content"], "hi")
        self.assertNotIn("tries", reply)
        self.assertEqual(err, "")
        self.assertEqual(self.auth(), [None])

    def test_empty_sends_no_header(self):
        code, out, err = self.call(key="")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(self.auth(), [None])

    def test_without_key_env_sends_no_header(self):
        code, out, err = self.call(key="sk-abc123", key_env=False)
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(self.auth(), [None])

    def test_set_sends_bearer(self):
        code, out, err = self.call(key="sk-abc123")
        self.assertEqual(code, 0, (out, err))
        self.assertEqual(self.auth(), ["Bearer sk-abc123"])

    def test_bad_key_blocked_before_sending(self):
        for bad in ("\u586b\u4f60\u7684\u91d1\u9470", "sk-abc\n", "sk abc"):
            with self.subTest(bad=repr(bad)):
                result = self.call(key=bad)
                error = self.failure(result, "KeyBad", False, 0)
                self.assertIn("environment variable %s (--key-env)" % VAR, error["msg"])
                self.assertNotIn(bad.strip(), result[1] + result[2])
                self.assertNotIn("bad url", error["msg"])
        self.assertEqual(self.server.seen, [])

    def test_401_without_key_names_variable(self):
        self.server.status = 401
        error = self.failure(self.call(), "EndpointFailed", False, 1, 401)
        self.assertIn("environment variable %s (--key-env) is not set" % VAR, error["msg"])
        self.assertEqual(len(self.server.seen), 1)

    def test_401_with_key_says_refused_key(self):
        self.server.status = 401
        result = self.call(key="sk-wrong")
        error = self.failure(result, "EndpointFailed", False, 1, 401)
        self.assertIn("HTTP 401 (the endpoint refused the key from %s)" % VAR, error["msg"])
        self.assertNotIn("sk-wrong", result[1] + result[2])
        self.assertNotIn("not set", error["msg"])

    def test_403_without_key_env_suggests_flag(self):
        self.server.status = 403
        error = self.failure(self.call(key_env=False), "EndpointFailed", False, 1, 403)
        self.assertIn("give --key-env NAME", error["msg"])

    def test_http_status_classification_without_local_retry(self):
        for status in (500, 501, 502, 503, 504, 505, 408, 429, 400, 401, 403, 404, 422, 418, 301, 307):
            with self.subTest(status=status):
                self.server.status = status
                before = len(self.server.seen)
                retry = status in (408, 429) or 500 <= status < 600
                error = self.failure(self.call(), "EndpointFailed", retry, 1, status)
                self.assertEqual(len(self.server.seen), before + 1)
                if status not in (401, 403):
                    self.assertNotIn(VAR, error["msg"])

    def test_retry_after_numeric_and_invalid_values(self):
        for status in (429, 503, 408, 500):
            for value, expected in (("20", 20), ("1.2", 2), ("0", 0), (None, None),
                                    ("nonsense", None), ("-2", None), ("nan", None), ("inf", None)):
                with self.subTest(status=status, value=value):
                    headers = {} if value is None else {"Retry-After": value}
                    self.server.replies = [{"status": status, "headers": headers}]
                    before = len(self.server.seen)
                    error = self.failure(self.call(), "EndpointFailed", True, 1, status)
                    if expected is None:
                        self.assertNotIn("retry_after_s", error)
                    else:
                        self.assertEqual(error["retry_after_s"], expected)
                    self.assertEqual(len(self.server.seen), before + 1)

    def test_retry_after_http_dates(self):
        for offset in (-60, 120):
            with self.subTest(offset=offset):
                value = email.utils.formatdate(time.time() + offset, usegmt=True)
                self.server.replies = [{"status": 503, "headers": {"Retry-After": value}}]
                error = self.failure(self.call(), "EndpointFailed", True, 1, 503)
                if offset < 0:
                    self.assertEqual(error["retry_after_s"], 0)
                else:
                    self.assertGreaterEqual(error["retry_after_s"], 115)
                    self.assertLessEqual(error["retry_after_s"], 120)

    def test_permanent_http_ignores_retry_after(self):
        self.server.replies = [{"status": 401, "headers": {"Retry-After": "20"}}]
        error = self.failure(self.call(), "EndpointFailed", False, 1, 401)
        self.assertNotIn("retry_after_s", error)

    def test_bad_reply_twice(self):
        bodies = (b'{"notice": "missing choices"}', b"not JSON", {"choices": []},
                  {"choices": [{"message": "bad"}]},
                  {"choices": [{"message": {"tool_calls": "bad"}}]},
                  {"choices": [{"message": {"tool_calls": ["bad"]}}]},
                  {"choices": [{"message": {"tool_calls": {}}}]},
                  b"\xff", [], {"choices": None})
        for body in bodies:
            with self.subTest(body=body):
                before = len(self.server.seen)
                self.server.replies = [{"body": body}, {"body": body}]
                error = self.failure(self.call(), "ReplyBad", True, 2, 200)
                self.assertEqual(len(self.server.seen), before + 2)
                text = body.decode("utf-8", "replace") if isinstance(body, bytes) else json.dumps(body)
                self.assertIn(text, error["msg"])

    def test_bad_reply_excerpt_is_normalized_before_truncation(self):
        text = " \n\t " * 100 + "marker\x00" + "x" * 250 + "TAIL"
        self.server.replies = [{"body": text.encode()}, {"body": text.encode()}]
        error = self.failure(self.call(), "ReplyBad", True, 2, 200)
        excerpt = "marker" + "x" * 194
        self.assertTrue(error["msg"].endswith(excerpt), error)
        self.assertNotIn("TAIL", error["msg"])
        self.assertNotIn("\x00", error["msg"])
        self.assertNotIn("\n", error["msg"])

    def test_bad_reply_then_success(self):
        self.server.replies = [{"body": {"notice": "missing choices"}}, {}]
        code, out, err = self.call()
        self.assertEqual(code, 0, (out, err))
        self.assertEqual(json.loads(out)["message"]["content"], "hi")
        self.assertEqual(json.loads(out)["tries"], 2)
        self.assertEqual(len(self.server.seen), 2)
        self.assertEqual(len(err.splitlines()), 1)
        self.assertTrue(err.startswith("llm_http: warning: retried once after ReplyBad: "), err)

    def test_second_attempt_result_wins(self):
        self.server.replies = [{"body": {}}, {"status": 401}]
        self.failure(self.call(), "EndpointFailed", False, 2, 401)
        self.assertEqual(len(self.server.seen), 2)

    def test_reply_bad_preserves_actual_2xx_and_retry_after(self):
        spec = {"status": 201, "body": {}, "headers": {"Retry-After": "1.2"}}
        self.server.replies = [spec, spec]
        error = self.failure(self.call(), "ReplyBad", True, 2, 201)
        self.assertEqual(error["retry_after_s"], 2)

    def test_phase_two_disconnects_retry_once(self):
        for mode in ("incomplete", "disconnect", "bad_status"):
            with self.subTest(mode=mode):
                before = len(self.server.seen)
                self.server.replies = [{"mode": mode}, {"mode": mode}]
                self.failure(self.call(), "EndpointFailed", True, 2, 200 if mode == "incomplete" else None)
                self.assertEqual(len(self.server.seen), before + 2)

    def test_incomplete_reply_then_success(self):
        self.server.replies = [{"mode": "incomplete"}, {}]
        code, out, err = self.call()
        self.assertEqual(code, 0, (out, err))
        self.assertEqual(json.loads(out)["tries"], 2)
        self.assertIn("warning: retried once after EndpointFailed:", err)
        self.assertEqual(len(self.server.seen), 2)

    def test_phase_two_oserror_retries(self):
        runner = RUNNER.replace("with patch('time.sleep') as sleep:",
                                "import http.client\nwith patch('http.client.HTTPConnection.getresponse', side_effect=OSError('read failed')), patch('time.sleep') as sleep:")
        self.failure(self.call(runner=runner), "EndpointFailed", True, 2)

    def test_phase_one_http_exception_does_not_retry(self):
        runner = RUNNER.replace("with patch('time.sleep') as sleep:",
                                "import http.client\nwith patch('http.client.HTTPConnection.connect', side_effect=http.client.HTTPException('connect failed')), patch('time.sleep') as sleep:")
        self.failure(self.call(runner=runner), "EndpointFailed", True, 1)
        self.assertEqual(self.server.seen, [])

    def test_connection_refused_does_not_retry(self):
        with socket.socket() as closed:
            closed.bind(("127.0.0.1", 0))
            port = closed.getsockname()[1]
        args = self.arguments()
        args["endpoint"]["url"] = "http://127.0.0.1:%d/v1" % port
        self.failure(self.call(args=args), "EndpointFailed", True, 1)
        self.assertEqual(self.server.seen, [])

    def test_illegal_url_is_permanent_without_request(self):
        for url in ("file:///tmp/no", "http://", "http://[bad", "http://127.0.0.1:bad", "http://bad host/v1",
                    self.url + "/bad path"):
            with self.subTest(url=url):
                args = self.arguments()
                args["endpoint"]["url"] = url
                self.failure(self.call(args=args), "EndpointFailed", False, 0)
        self.assertEqual(self.server.seen, [])

    def test_own_argument_errors(self):
        for where, key, value in (("endpoint", "key", "not accepted"), ("endpoint", "url", 42),
                                  ("endpoint", "url", ""), ("endpoint", "fixed", []),
                                  ("request", "messages", "not an array")):
            with self.subTest(where=where, key=key):
                args = self.arguments()
                args[where][key] = value
                self.failure(self.call(args=args), "ArgumentsBad", False, 0)
        self.assertEqual(self.server.seen, [])

    def test_tool_io_argument_errors(self):
        for raw in ("", "not json", "[]", "{}", '{"endpoint": [], "request": {}}',
                    '{"endpoint": {}, "request": null}'):
            with self.subTest(raw=raw):
                self.failure(self.call(raw=raw), "ArgumentsBad", False, 0)
        args = self.arguments()
        args["key_env"] = 42
        self.failure(self.call(args=args, key_env=False), "ArgumentsBad", False, 0)
        self.failure(self.call(flags=["--unknown"]), "ArgumentsBad", False, 0, stderr_code="FlagUnknown")
        self.assertEqual(self.server.seen, [])

    def test_help_still_exits_zero(self):
        code, out, err = self.call(flags=["--help"])
        self.assertEqual((code, err), (0, ""))
        self.assertIn('one JSON object {"error":', out)
        self.assertEqual(self.server.seen, [])

    def test_success_preserves_model_usage_and_tool_calls(self):
        self.server.replies = [{"body": {"choices": [{"message": {"content": None, "tool_calls": [
            {"id": "1", "type": "function", "function": {"name": "test", "arguments": "{}"}, "extra": 1}]}}],
            "usage": {"total_tokens": 3}, "model": "answered"}}]
        code, out, err = self.call()
        self.assertEqual((code, err), (0, ""))
        reply = json.loads(out)
        self.assertEqual(reply["model"], "answered")
        self.assertEqual(reply["usage"], {"total_tokens": 3})
        self.assertEqual(reply["message"]["tool_calls"][0]["function"]["name"], "test")
        self.assertNotIn("extra", reply["message"]["tool_calls"][0])
        self.assertNotIn("tries", reply)


if __name__ == "__main__":
    unittest.main()
