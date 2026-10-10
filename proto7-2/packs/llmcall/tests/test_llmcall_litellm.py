"""本地 HTTP 假 LiteLLM 的整合測試，不連外部模型。"""
import json
import io
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from urllib.error import HTTPError, URLError
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import Mock, patch
from contextlib import redirect_stdout, redirect_stderr

from llmcallcase import LlmcallCase, LLMCALL, R, last_json, tree, read_json, write_json, _proc
import aos7_llmcall as lc
import aos7_llmcall_litellm as transport


class TestLlmcallLiteLLM(LlmcallCase):
    """〔llmcall〕真 HTTP 傳輸、計量、拒絕、崩潰與本地恢復。"""

    def up(self, *args, gateway="llm.litellm", **kw):
        return super().up(*args, gateway=gateway, **kw)

    def setUp(self):
        super().setUp()
        self.bodies, self.headers, self.followed = [], [], []
        self.code, self.delay = 200, 0
        self.usage = {"total_tokens": 120, "prompt_tokens": 100, "completion_tokens": 20,
                      "prompt_tokens_details": {"cached_tokens": 17}}
        self.reply = {"model": "served-model", "choices": [{"message": {"content": "OK"},
                      "finish_reason": "stop"}], "usage": self.usage}
        case = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                case.assertEqual(self.path, "/v1/chat/completions")
                case.bodies.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                case.headers.append(dict(self.headers))
                code, reply, delay = case.code, case.reply, case.delay
                time.sleep(delay)
                data = reply if isinstance(reply, bytes) else json.dumps(reply).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                if 300 <= code < 400:
                    self.send_header("Location", "/elsewhere")
                self.end_headers()
                try:
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def do_GET(self):
                case.followed.append(self.path)
                self.send_error(404)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.worker = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .02})
        self.worker.start()
        self.env = {"AOS7_LITELLM_URL": "http://127.0.0.1:%d/v1" % self.server.server_port,
                    "AOS7_LITELLM_KEY": ""}
        self.body = {"model": "chatgpt-gpt-6-sol", "messages": [{"role": "user", "content": "回 OK"}],
                     "temperature": .2}
        write_json(self.req, {"litellm": self.body})

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(2)
        super().tearDown()

    def call(self, c="c", **kw):
        return self.cli(*self.args(c, **kw), env=self.env)

    def crash_call(self, c, point):
        self.arm(point)
        p = subprocess.Popen([sys.executable, LLMCALL, *self.args(c)], cwd=self.node,
                             env=dict(os.environ, **self.env), stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, start_new_session=True)
        _proc.track(self, p, group=True)
        out, err = p.communicate(timeout=5)
        self.assertEqual(p.returncode, -signal.SIGKILL, out + err)

    def test_ok_preserves_body_usage_and_replay(self):
        p = self.call()
        obj = self.assert_receipt(p)
        self.assertEqual((obj["meter"], obj["usage"], obj["used"], obj["text"]),
                         ("litellm.total_tokens/1", self.usage, 120, "OK"))
        self.assertEqual(self.bodies, [self.body])
        self.assertNotIn("Authorization", self.headers[0])
        self.assertEqual(self.gw()["gateway"], "llm.litellm")
        req = read_json(str(self.cd() / "request.json"))
        self.assertEqual(req["endpoint"], self.env["AOS7_LITELLM_URL"])
        raw = read_json(str(self.cd() / "raw.json"))["reply"]
        self.assertEqual((raw["model"], raw["http"], raw["response"], raw["finish_reason"]),
                         ("served-model", 200, self.reply, "stop"))
        self.assertIs(type(raw["elapsed"]), float)
        self.assertGreaterEqual(raw["elapsed"], 0)
        self.assertEqual(raw["elapsed"], round(raw["elapsed"], 3))
        self.assertEqual(self.call().stdout.encode(), p.stdout.encode())
        self.assertEqual(len(self.bodies), 1)
        self.assertFalse((self.node / "llmcall" / "fake-remote.json").exists())
        self.audit()

    def test_overrun(self):
        self.usage["total_tokens"] = R + 50
        obj = self.assert_receipt(self.call(), 4)
        self.assertEqual((obj["used"], obj["overrun"], obj["billing"]), (R, 50, "overrun"))
        self.audit()

    def test_missing_usage(self):
        self.reply.pop("usage")
        obj = self.assert_receipt(self.call(), 4)
        self.assertEqual((obj["text"], obj["billing"], obj["used"]), ("OK", "pending", None))
        self.assertFalse((self.cd() / "receipt.json").exists())
        self.assertEqual(self.audit()["inflight"], R)

    def test_http_errors_and_bad_json(self):
        cases = [(400, {"error": "bad"}, 1, "rejected", "final"),
                 (429, {"error": "rate"}, 4, "failed", "pending"),
                 (500, {"error": "down"}, 4, "failed", "pending"),
                 (429, {"usage": self.usage}, 1, "failed", "final"),
                 (500, {"usage": self.usage}, 1, "failed", "final"),
                 (200, b"{broken", 4, "failed", "pending"),
                 (200, {"usage": self.usage}, 1, "failed", "final"),
                 (400, {"error": "after work", "usage": self.usage}, 1, "failed", "final"),
                 (408, {"error": "timeout"}, 4, "failed", "pending"),
                 (302, {"moved": True}, 4, "failed", "pending"),
                 (307, {"moved": True}, 4, "failed", "pending")]
        for i, (self.code, self.reply, rc, outcome, billing) in enumerate(cases):
            with self.subTest(code=self.code, reply=self.reply):
                c = "error%d" % i
                obj = self.assert_receipt(self.call(c), rc)
                self.assertEqual((obj["outcome"], obj["billing"]), (outcome, billing))
                self.assertEqual((self.cd(c) / "receipt.json").exists(), billing == "final")
                if outcome == "rejected":
                    self.assertEqual((obj["used"], obj["usage"]), (0, None))
                    self.assertEqual(obj["text"], json.dumps(self.reply))
                if isinstance(self.reply, bytes):
                    self.assertEqual(read_json(str(self.cd(c) / "raw.json"))["reply"]["response"], "{broken")
        self.assertEqual(len(self.bodies), len(cases))
        self.assertEqual(self.followed, [])
        self.audit()

    def test_lone_surrogate_reply_still_saved(self):
        self.reply = json.dumps(dict(self.reply, extra="\ud800")).encode()
        obj = self.assert_receipt(self.call())
        self.assertEqual((obj["text"], obj["used"]), ("OK", 120))
        raw = read_json(str(self.cd() / "raw.json"))["reply"]
        self.assertEqual(raw["response"]["extra"], "\ufffd")
        self.audit()

    def test_timeout_keeps_intent_without_resending(self):
        self.delay = 1.3
        start = time.monotonic()
        p = self.call(extra=("--deadline", "1"))
        self.assertEqual(p.returncode, 3, p.stdout + p.stderr)
        self.assertLess(time.monotonic() - start, 2.5)
        self.assertNotEqual(last_json(p)["stage"], "done")
        self.assertEqual(self.gw()["stage"], "intent")
        self.assertEqual(self.call().returncode, 3)
        self.assertEqual(len(self.bodies), 1)
        self.assertFalse((self.cd() / "raw.json").exists())
        self.assertEqual(self.audit()["inflight"], R)

    def test_connection_refused_returns_reserve(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        self.env["AOS7_LITELLM_URL"] = "http://127.0.0.1:%d/v1" % port
        obj = self.assert_receipt(self.call(), 1)
        self.assertEqual((obj["outcome"], obj["used"], obj["billing"]), ("rejected", 0, "final"))
        self.assertIn("連線被拒，未送達", obj["text"])
        self.assertEqual(self.audit()["available"], 10000)
        self.assertEqual(len(self.bodies), 0)

    def test_sigkill_windows(self):
        for c, point, count in (("intent", "after-intent", 0), ("send", "after-send", 1),
                                ("raw", "after-raw", 2)):
            with self.subTest(point=point):
                self.crash_call(c, point)
                self.assertEqual(len(self.bodies), count)
                p = self.call(c)
                if point == "after-raw":
                    self.assert_receipt(p)
                    self.assertEqual(self.call(c).stdout, p.stdout)
                else:
                    self.assertEqual(p.returncode, 3)
                    self.assertEqual(self.gw(c)["stage"], "intent")
                self.assertEqual(len(self.bodies), count)
        self.assertEqual(self.audit()["inflight"], 2 * R)

    def test_bad_input_no_files(self):
        variants = [{"fake": {}, "litellm": self.body}, {"litellm": None}, {"litellm": []},
                    {"litellm": {"messages": []}}, {"litellm": dict(self.body, model=7)},
                    {"litellm": {"model": "m"}}, {"litellm": dict(self.body, messages={})},
                    {"litellm": dict(self.body, stream=True)}]
        for request in variants:
            write_json(self.req, request)
            before = tree(self.node)
            self.assertEqual(self.call().returncode, 2, request)
            self.assertEqual(tree(self.node), before)
        self.assertEqual(len(self.bodies), 0)
        self.assertEqual(self.audit()["seq"], 0)

    def test_fake_grant_denied(self):
        bd = self.up("fakegrant", gateway="llm.fake")
        p = self.call(budget="fakegrant")
        self.assertEqual((p.returncode, last_json(p)["outcome"]), (1, "denied"))
        self.assertEqual(len(self.bodies), 0)
        self.assertEqual(self.audit(bd)["seq"], 0)

    def test_key_header(self):
        self.env["AOS7_LITELLM_KEY"] = "test-secret"
        self.assert_receipt(self.call())
        self.assertEqual(self.headers[0]["Authorization"], "Bearer test-secret")

    def test_invalid_key_never_sent_or_saved(self):
        """非法 header 金鑰確定未送達、退款；CLI 與任何證據都不能含金鑰。"""
        keys = ["fx1-test-key\nheader-injection", "fx1-test-key\r", "fx1-test-key\t",
                "fx1-test-key space", "fx1-test-key\x01", "fx1-test-key\x7f", "fx1-test-key中文"]
        for i, key in enumerate(keys):
            with self.subTest(變體=i):
                c = "invalidkey%d" % i
                self.env["AOS7_LITELLM_KEY"] = key
                p = self.call(c)
                obj = self.assert_receipt(p, 1)
                self.assertEqual((obj["outcome"], obj["billing"], obj["used"]),
                                 ("rejected", "final", 0))
                self.assertIn("格式不合", obj["text"])
                self.assertIn("未送請求", obj["text"])
                self.assertEqual(self.bodies, [])
                self.assert_key_absent(p, key)
                # 終局可重印；有效 key 也不讓同 call 重送。
                self.env["AOS7_LITELLM_KEY"] = "fx1-test-key"
                self.assertEqual(self.call(c).stdout, p.stdout)
                self.assertEqual(self.bodies, [])
                ledger = self.audit()
                self.assertEqual((ledger["inflight"], ledger["used"]), (0, 0))

    def assert_key_absent(self, p, key):
        """連 escaped key 與換行前的識別片段都不容許落在輸出／證據。"""
        values = [p.stdout.encode(), p.stderr.encode(), *tree(self.node).values()]
        for value in values:
            for needle in (key.encode(), json.dumps(key)[1:-1].encode(), b"fx1-test-key"):
                self.assertNotIn(needle, value)

    def test_transport_exception_key_never_saved(self):
        """Request、open 與 HTTPError read 例外的原訊息不能進 why；仍 unknown 留 intent。"""
        key = "fx1-test-key"
        unreadable = HTTPError(self.env["AOS7_LITELLM_URL"], 500, "error", {}, io.BytesIO())
        unreadable.read = Mock(side_effect=OSError("Authorization: Bearer " + key))
        failures = [("Request", ValueError("Authorization: Bearer " + key)),
                    ("urlopen", URLError("Authorization: Bearer " + key)),
                    ("urlopen", TimeoutError("Authorization: Bearer " + key)),
                    ("urlopen", unreadable)]
        for i, (name, error) in enumerate(failures):
            with self.subTest(位置=name, 變體=i):
                c = "keyerror%d" % i
                args = self.args(c)
                args[1] = str(self.node / args[1])
                out, err = io.StringIO(), io.StringIO()
                with patch.dict(os.environ, dict(self.env, AOS7_LITELLM_KEY=key)), \
                        patch.object(transport, name, side_effect=error), \
                        redirect_stdout(out), redirect_stderr(err):
                    rc = lc.main(args)
                p = subprocess.CompletedProcess(args, rc, out.getvalue(), err.getvalue())
                self.assertEqual(rc, 3)
                self.assertEqual((last_json(p)["outcome"], last_json(p)["stage"]), ("unknown", "io"))
                self.assertRegex(last_json(p)["why"], r"^LiteLLM 傳輸故障（[A-Za-z_/]+），intent 留著$")
                self.assertEqual(self.gw(c)["stage"], "intent")
                self.assertFalse((self.cd(c) / "raw.json").exists())
                self.assertFalse((self.cd(c) / "receipt.json").exists())
                self.assertEqual(self.bodies, [])
                self.assert_key_absent(p, key)
        self.assertEqual(self.audit()["inflight"], R * len(failures))

    def test_default_deadlines(self):
        # 首次准入真的走 send；攔下 thread 呼叫以觀察 CLI 選定的 timeout。
        for c, request, expected, attr in (("real", {"litellm": self.body}, 86400, "TRANSPORT_LITELLM"),
                                           ("fake", {}, 60, "TRANSPORT")):
            write_json(self.req, request)
            if c == "fake":
                self.up("fakebudget", gateway="llm.fake")
            seen = []

            def reply(node, call_id, body, deadline):
                seen.append(deadline)
                return {"status": "ok", "billed": True, "body": "OK", "usage": self.usage}

            with patch.object(lc, attr, reply):
                # 用絕對 budget 路徑，直接呼叫 CLI main 不需要切換行程 cwd。
                args = self.args(c, budget="fakebudget" if c == "fake" else "llm")
                args[1] = str(self.node / args[1])
                with patch("builtins.print"):
                    self.assertEqual(lc.main(args), 0)
            self.assertEqual(seen, [expected])

    def test_response_shapes_and_text_limit(self):
        self.body["max_tokens"] = 123456
        write_json(self.req, {"litellm": self.body})
        self.reply["choices"][0]["message"]["content"] = [{"text": "not a string"}]
        self.reply["usage"] = []
        obj = self.assert_receipt(self.call("shape"), 4)
        self.assertEqual((obj["text"], obj["usage"]), (None, None))
        self.assertEqual(self.bodies[0], self.body)
        self.code, self.reply = 400, b"x" * (64 * 1024 + 100)
        obj = self.assert_receipt(self.call("limit"), 1)
        reply = read_json(str(self.cd("limit") / "raw.json"))["reply"]
        self.assertEqual(len(obj["text"]), 64 * 1024)
        self.assertEqual(reply["response"], obj["text"])
        self.audit()

    def test_multi_choice_takes_last_nonempty(self):
        """LiteLLM 把 sol 的開場白與答案拆成多個 choice：取最後一個非空的，raw 記 choices_n／skipped。"""
        answer = '{"files":{}}'
        cases = [("two", [("我先確認工作區，再跑三關。", "stop"), (answer, "length")], 1),
                 ("empty0", [("", "stop"), (answer, "length")], 0),
                 ("tail", [("開場白", "stop"), (answer, "length"), ("", "stop")], 1)]
        for c, parts, n_skipped in cases:
            with self.subTest(c):
                self.reply["choices"] = [{"index": i, "message": {"role": "assistant", "content": t},
                                          "finish_reason": f} for i, (t, f) in enumerate(parts)]
                obj = self.assert_receipt(self.call(c))
                self.assertEqual((obj["outcome"], obj["text"]), ("answered", answer))
                raw = read_json(str(self.cd(c) / "raw.json"))["reply"]
                self.assertEqual((raw["choices_n"], raw["finish_reason"], len(raw["skipped"])),
                                 (len(parts), "length", n_skipped))
                self.assertNotIn("choices_n", obj)
        self.assertEqual(read_json(str(self.cd("two") / "raw.json"))["reply"]["skipped"],
                         [{"index": 0, "chars": 13, "head": "我先確認工作區，再跑三關。"}])
        self.reply["choices"] = []
        obj = self.assert_receipt(self.call("none"), 1)
        self.assertEqual((obj["outcome"], obj["text"]), ("failed", None))
        raw = read_json(str(self.cd("none") / "raw.json"))["reply"]
        self.assertEqual((raw["status"], raw["choices_n"], raw["skipped"]), ("error", 0, []))
        self.reply["choices"] = [{"message": {"content": ""}, "finish_reason": "stop"}]
        obj = self.assert_receipt(self.call("allempty"))
        self.assertEqual((obj["outcome"], obj["text"]), ("answered", ""))
        self.audit()

    def test_other_connection_errors_are_unknown(self):
        for error in (URLError("DNS failure"), TimeoutError("timeout"), ConnectionResetError("reset")):
            with self.subTest(error=error), patch.object(transport, "urlopen", side_effect=error):
                with self.assertRaises(lc.Unknown):
                    transport.send(str(self.node), "c", {"litellm": self.body}, 1)
                with patch.object(lc, "TRANSPORT_LITELLM", transport.send):
                    with self.assertRaises((lc.Unknown, OSError)):
                        lc.send(str(self.node), "c", {"litellm": self.body}, 1)
        with patch.object(transport, "urlopen", side_effect=ConnectionRefusedError("refused")):
            reply = transport.send(str(self.node), "c", {"litellm": self.body}, 1)
            self.assertEqual((reply["status"], reply["billed"]), ("reject", False))


if __name__ == "__main__":
    unittest.main()
