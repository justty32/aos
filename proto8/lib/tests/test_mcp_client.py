"""Verify MCP stdio and HTTP sessions, authentication, wire failures, deadlines, and cleanup."""

import base64
import json
import io
from email.message import Message
import secrets
import socket
import subprocess
import urllib.error
import urllib.request
import os
from pathlib import Path
import shutil
import sys
import tempfile
import textwrap
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mcp_client
import mcp_server_file
from tool_io import Error


FAKE = Path(__file__).with_name("fake_mcp_stdio.py")
NAMES = ["echo", "fail", "image", "sleep", "big", "refschema", "show_env"]
INITIALIZED = {
    "protocolVersion": "2025-06-18",
    "capabilities": {"tools": {}},
    "serverInfo": {"name": "test", "version": "1"},
}


class McpClientTests(unittest.TestCase):
    def assert_error(self, code, function, *args, **kwargs):
        with self.assertRaises(Error) as caught:
            function(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)
        self.assertTrue(str(caught.exception))
        return caught.exception

    def open_fake(self, mode=None, extra_env=None):
        env = dict(os.environ)
        env.pop("FAKE_MODE", None)
        if mode is not None:
            env["FAKE_MODE"] = mode
        env.update(extra_env or {})
        session = mcp_client.open_stdio([sys.executable, str(FAKE)], env, os.getcwd(), 1)
        self.addCleanup(session.close)
        return session

    def open_script(self, action="send({'jsonrpc': '2.0', 'id': request['id'], 'result': {}})",
                    startup="", initialize=None, timeout=1, extra_env=None):
        """Use tiny real servers for malformed wire messages without extra fixture modes."""
        if initialize is None:
            initialize = "send({'jsonrpc': '2.0', 'id': request['id'], 'result': %r})" % INITIALIZED
        script = "\n".join([
            "import json, os, sys, time",
            "def send(message):",
            "    print(json.dumps(message), flush=True)",
            "request = json.loads(sys.stdin.readline())",
            "assert request['method'] == 'initialize'",
            "assert request['params']['protocolVersion'] == '2025-06-18'",
            "assert not any(key in request['params']['capabilities'] for key in ('sampling', 'elicitation', 'roots'))",
            startup,
            initialize,
            "line = sys.stdin.readline()",
            "if not line: sys.exit(0)",
            "notification = json.loads(line)",
            "assert notification['method'] == 'notifications/initialized'",
            "assert 'id' not in notification",
            "for line in sys.stdin:",
            "    request = json.loads(line)",
            textwrap.indent(action, "    "),
        ])
        env = dict(extra_env or {})
        session = mcp_client.open_stdio([sys.executable, "-u", "-c", script], env, os.getcwd(), timeout)
        self.addCleanup(session.close)
        return session

    def test_handshake_and_tool_list(self):
        session = self.open_fake()
        self.assertEqual(session.protocol_version, "2025-06-18")
        self.assertEqual([tool["name"] for tool in session.list_tools()], NAMES)

    def test_initialize_capabilities_and_initialized_notification(self):
        session = self.open_script()
        self.assertEqual(session.call_tool("echo", {}, 1), {})

    def test_two_page_tool_list(self):
        session = self.open_fake("two_pages")
        tools = session.list_tools()
        self.assertEqual(len(tools), 7)
        self.assertEqual([tool["name"] for tool in tools], NAMES)

    def test_echo(self):
        session = self.open_fake()
        self.assertEqual(session.call_tool("echo", {"text": "hello 世界"}, 1),
                         {"content": [{"type": "text", "text": "hello 世界"}]})

    def test_tool_failure_result_is_returned(self):
        session = self.open_fake()
        self.assertEqual(session.call_tool("fail", {}, 1), {
            "content": [{"type": "text", "text": "the fake tool failed"}], "isError": True})

    def test_image_big_and_refschema(self):
        session = self.open_fake()
        image = session.call_tool("image", {}, 1)["content"][0]
        self.assertEqual(image["type"], "image")
        self.assertEqual(image["mimeType"], "image/png")
        self.assertTrue(base64.b64decode(image["data"], validate=True).startswith(b"\x89PNG\r\n\x1a\n"))
        big = session.call_tool("big", {}, 1)["content"][0]
        self.assertEqual(big["type"], "text")
        self.assertEqual(len(big["text"]), 200 * 1024)
        schema = next(tool for tool in session.list_tools() if tool["name"] == "refschema")["inputSchema"]
        self.assertIn("$defs", schema)
        self.assertIn('"$ref"', json.dumps(schema))

    def test_show_env_only_returns_presence(self):
        secret = "mcp-test-secret-must-not-be-returned"
        present, absent = "MCP_TEST_PRESENT", "MCP_TEST_ABSENT"
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(absent, None)
            session = self.open_fake(extra_env={present: secret})
        result = session.call_tool("show_env", {"names": [present, absent]}, 1)
        self.assertEqual(json.loads(result["content"][0]["text"]), {present: True, absent: False})
        self.assertNotIn(secret, json.dumps(result))

    def test_initialize_error(self):
        error = self.assert_error("ServerFailed", self.open_fake, "init_fail")
        self.assertIn("fake initialize failed", str(error))

    def test_server_dies_during_call(self):
        session = self.open_fake("die")
        self.assert_error("ServerFailed", session.call_tool, "echo", {}, 1)

    def test_garbage_limit(self):
        self.assert_error("ServerBad", self.open_fake, "garbage")

    def test_reverse_sampling_request_is_rejected_and_call_completes(self):
        session = self.open_fake("ask_sampling")
        self.assertEqual(session.call_tool("echo", {"text": "after sampling"}, 1),
                         {"content": [{"type": "text", "text": "after sampling"}]})

    def test_changed_description(self):
        before = next(tool for tool in self.open_fake().list_tools() if tool["name"] == "echo")
        after = next(tool for tool in self.open_fake("changed_desc").list_tools() if tool["name"] == "echo")
        self.assertNotEqual(before["description"], after["description"])

    def test_call_deadline(self):
        session = self.open_fake()
        start = time.monotonic()
        self.assert_error("CommandFailed", session.call_tool, "sleep", {"seconds": 0.3}, 0.04)
        self.assertLess(time.monotonic() - start, 1)

    def test_command_missing(self):
        self.assert_error("CommandMissing", mcp_client.open_stdio,
                          ["/nonexistent/aos-mcp-client-test-command"], dict(os.environ), os.getcwd())

    def test_close_removes_process_group_and_is_repeatable(self):
        session = self.open_fake()
        pgid = os.getpgid(session._process.pid)
        self.assertEqual(pgid, session._process.pid)
        session.close()
        session.close()
        with self.assertRaises(ProcessLookupError):
            os.killpg(pgid, 0)

    def test_open_session_server_file_env_file_and_folder(self):
        """相對 args 從 server 檔的資料夾算（Q2 代定 G13），不是 $AOS_WS。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            workspace.mkdir()
            shutil.copyfile(FAKE, root / FAKE.name)
            (root / "server.env").write_text(
                "# test environment\nexport FAKE_MODE=changed_desc\nMCP_FILE_ONLY='private-file-value'\n",
                encoding="utf-8")
            path = root / "server.json"
            path.write_text(json.dumps({"description": "Test MCP server.", "mcp_server": {
                "name": "demo", "transport": "stdio", "command": sys.executable,
                "args": [FAKE.name], "env": {"FAKE_MODE": "init_fail", "MCP_INLINE_ONLY": "inline"},
                "env_file": "server.env"}}), encoding="utf-8")
            with patch.dict(os.environ, {"AOS_WS": str(workspace), "MCP_INHERITED": "inherited"}):
                session = mcp_client.open_session(path)
            try:
                echo = next(tool for tool in session.list_tools() if tool["name"] == "echo")
                default_echo = next(tool for tool in self.open_fake().list_tools() if tool["name"] == "echo")
                self.assertNotEqual(echo["description"], default_echo["description"])
                names = ["MCP_FILE_ONLY", "MCP_INLINE_ONLY", "MCP_INHERITED"]
                result = session.call_tool("show_env", {"names": names}, 1)
                self.assertEqual(json.loads(result["content"][0]["text"]), dict.fromkeys(names, True))
                self.assertNotIn("private-file-value", json.dumps(result))
            finally:
                session.close()

    def test_open_session_relative_command_and_args_from_server_folder(self):
        """command（含 /）與 args 的相對路徑都從 server 檔的資料夾算，不管呼叫者的 cwd 與 $AOS_WS（Q2 代定 G13）。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pack, elsewhere = root / "pack", root / "elsewhere"
            (pack / "bin").mkdir(parents=True)
            elsewhere.mkdir()
            shutil.copyfile(FAKE, pack / "bin" / FAKE.name)
            run = pack / "bin" / "run"
            run.write_text("#!/bin/sh\nexec %s \"$@\"\n" % sys.executable, encoding="utf-8")
            run.chmod(0o755)
            path = pack / "server.json"
            path.write_text(json.dumps({"mcp_server": {
                "name": "demo", "transport": "stdio", "command": "bin/run",
                "args": ["bin/" + FAKE.name], "env": {"FAKE_MODE": ""}}}), encoding="utf-8")
            previous = os.getcwd()
            try:
                os.chdir(elsewhere)
                with patch.dict(os.environ, {"AOS_WS": str(elsewhere)}):
                    argv, _, cwd = mcp_server_file.stdio_launch("../pack/server.json")
                    session = mcp_client.open_session("../pack/server.json")
                try:
                    self.assertEqual(session.protocol_version, "2025-06-18")
                finally:
                    session.close()
            finally:
                os.chdir(previous)
            self.assertEqual(cwd, str(pack))
            self.assertEqual(argv, [str(run), "bin/" + FAKE.name])

    def test_stdio_args_element_directive(self):
        """args 裡單一元素可寫指示詞（$env），每次起才解。"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "server.json"
            path.write_text(json.dumps({"mcp_server": {
                "name": "demo", "transport": "stdio", "command": "python3",
                "args": ["-u", {"$env": "AOS_WS", "$path": "data"}]}}), encoding="utf-8")
            with patch.dict(os.environ, {"AOS_WS": "/ws"}):
                argv, _, _ = mcp_server_file.stdio_launch(path)
            self.assertEqual(argv, ["python3", "-u", "/ws/data"])

    def test_invalid_arguments_rpc_error(self):
        session = self.open_fake()
        self.assert_error("ArgumentsBad", session.call_tool, "not_a_tool", {}, 1)

    def test_rpc_error_preserves_message(self):
        session = self.open_script(
            "send({'jsonrpc': '2.0', 'id': request['id'], 'error': {'code': -32603, 'message': 'test server refused'}})")
        error = self.assert_error("ServerFailed", session.call_tool, "echo", {}, 1)
        self.assertIn("test server refused", str(error))

    @unittest.skipUnless(Path("/proc/self/fd").is_dir(), "requires Linux procfs")
    def test_dead_server_with_output_pipe_still_open(self):
        session = self.open_script("os._exit(0)")
        # A duplicate writer reproduces a descendant holding stdout open, without orphaning a child.
        with open("/proc/%s/fd/1" % session._process.pid, "wb", buffering=0):
            start = time.monotonic()
            self.assert_error("ServerFailed", session.call_tool, "echo", {}, 1)
            self.assertLess(time.monotonic() - start, 0.7)

    def test_call_result_is_not_transformed(self):
        result = {"content": [], "isError": True, "structuredContent": {"nested": [1, False]},
                  "_meta": {"test": "preserved"}}
        session = self.open_script("send({'jsonrpc': '2.0', 'id': request['id'], 'result': %r})" % result)
        self.assertEqual(session.call_tool("custom", {"anything": True}, 1), result)

    def test_notifications_are_ignored(self):
        session = self.open_script("\n".join([
            "send({'jsonrpc': '2.0', 'method': 'notifications/progress', 'params': {'progress': 1}})",
            "send({'jsonrpc': '2.0', 'id': request['id'], 'result': {'content': []}})",
        ]))
        self.assertEqual(session.call_tool("echo", {}, 1), {"content": []})

    def test_startup_non_json_lines_are_skipped_and_counter_resets(self):
        startup = "\n".join([
            "print('startup banner\\n' * 99, end='', flush=True)",
            "send({'jsonrpc': '2.0', 'method': 'notifications/progress'})",
            "print('another banner\\n' * 99, end='', flush=True)",
        ])
        session = self.open_script(startup=startup)
        self.assertEqual(session.protocol_version, "2025-06-18")

    def test_non_json_after_initialize_is_bad(self):
        session = self.open_script("print('not JSON', flush=True)")
        self.assert_error("ServerBad", session.call_tool, "echo", {}, 1)

    def test_malformed_rpc_messages(self):
        messages = [[], {}, {"jsonrpc": "1.0", "id": 1, "result": {}},
                    {"jsonrpc": "2.0", "result": {}}, {"jsonrpc": "2.0", "id": 1},
                    {"jsonrpc": "2.0", "id": 1, "result": {}, "error": {"code": -1, "message": "bad"}},
                    {"jsonrpc": "2.0", "id": 1, "error": {"code": -1}}]
        for message in messages:
            with self.subTest(message=message):
                self.assert_error("ServerBad", self.open_script, initialize="send(%r)" % message)

    def test_initialize_result_missing_fields(self):
        for missing in ("protocolVersion", "capabilities", "serverInfo"):
            with self.subTest(missing=missing):
                result = dict(INITIALIZED)
                del result[missing]
                self.assert_error("ServerBad", self.open_script,
                                  initialize="send({'jsonrpc': '2.0', 'id': request['id'], 'result': %r})" % result)

    def test_initialize_deadline_with_partial_line(self):
        start = time.monotonic()
        self.assert_error("ServerFailed", self.open_script, timeout=0.04,
                          initialize="sys.stdout.write('{\"jsonrpc\":'); sys.stdout.flush(); time.sleep(0.3)")
        self.assertLess(time.monotonic() - start, 1.5)

    def test_call_deadline_with_partial_line(self):
        session = self.open_script("sys.stdout.write('{\"jsonrpc\":'); sys.stdout.flush(); time.sleep(0.3)")
        start = time.monotonic()
        self.assert_error("CommandFailed", session.call_tool, "echo", {}, 0.04)
        self.assertLess(time.monotonic() - start, 1)

    def test_response_larger_than_16_mb_is_bad(self):
        session = self.open_script(
            "send({'jsonrpc': '2.0', 'id': request['id'], 'result': {'padding': 'x' * (16 * 1024 * 1024)}})")
        self.assert_error("ServerBad", session.call_tool, "big", {}, 3)


class HttpWireTests(unittest.TestCase):
    """Exercise public sessions with an in-memory HTTP peer, without binding sockets."""

    def setUp(self):
        self.requests = []
        self.reply = None
        self.token = "FAKE-" + secrets.token_hex(16)
        self.env = patch.dict(os.environ, {
            "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost"})
        self.env.start()
        self.addCleanup(self.env.stop)
        opened = patch.object(urllib.request.OpenerDirector, "open", autospec=True,
                              side_effect=self.respond)
        opened.start()
        self.addCleanup(opened.stop)

    def response(self, body, content_type="application/json", headers=None):
        response = io.BytesIO(body)
        response.headers = Message()
        response.headers["Content-Type"] = content_type
        for name, value in (headers or {}).items():
            response.headers[name] = value
        response.status = 200
        response.getcode = lambda: 200
        return response

    def respond(self, opener, request, *args, **kwargs):
        self.requests.append(request)
        message = json.loads(request.data) if request.data else None
        if self.reply is not None:
            replacement = self.reply(request, message)
            if replacement is not None:
                return replacement
        if request.get_method() == "DELETE" or "id" not in message:
            response = self.response(b"")
            response.status = 202
            return response
        if message["method"] == "initialize":
            result = INITIALIZED
        elif message["method"] == "tools/list":
            result = {"tools": []}
        else:
            result = {"content": [{"type": "text", "text": "echo"}]}
        return self.response(json.dumps({"jsonrpc": "2.0", "id": message["id"],
                                         "result": result}).encode(),
                             headers={"Mcp-Session-Id": "test-session"})

    def open(self, **kwargs):
        session = mcp_client.open_http("http://127.0.0.1/mcp", **kwargs)
        self.addCleanup(session.close)
        return session

    def error(self, code, function, *args, **kwargs):
        with self.assertRaises(Error) as caught:
            function(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)
        self.assertTrue(self.token not in str(caught.exception), "Error disclosed the bearer")
        return caught.exception

    def test_headers_session_notification_and_delete(self):
        session = self.open(bearer=self.token)
        self.assertEqual(session.protocol_version, "2025-06-18")
        self.assertEqual(session.list_tools(), [])
        self.assertEqual(session.call_tool("echo", {}, 1)["content"][0]["text"], "echo")
        session.close()
        count = len(self.requests)
        session.close()
        self.assertEqual(len(self.requests), count)
        self.assertEqual(self.requests[-1].get_method(), "DELETE")
        for index, request in enumerate(self.requests):
            headers = {name.lower(): value for name, value in request.header_items()}
            self.assertTrue(headers.get("authorization") == "Bearer " + self.token,
                            "Authorization header did not match the supplied bearer")
            if index:
                self.assertEqual(headers["mcp-session-id"], "test-session")
            if request.get_method() == "POST":
                self.assertEqual(headers["content-type"], "application/json")
                self.assertIn("application/json", headers["accept"])
                self.assertIn("text/event-stream", headers["accept"])
        initialize = json.loads(self.requests[0].data)
        self.assertEqual(initialize["params"]["protocolVersion"], "2025-06-18")
        self.assertFalse(set(initialize["params"]["capabilities"]) &
                         {"sampling", "elicitation", "roots"})
        notification = json.loads(self.requests[1].data)
        self.assertEqual(notification["method"], "notifications/initialized")
        self.assertNotIn("id", notification)

    def test_sse_ignores_notifications_and_other_ids(self):
        session = self.open()
        def reply(request, message):
            if message and message.get("method") == "tools/call":
                messages = [{"jsonrpc": "2.0", "method": "notifications/progress"},
                            {"jsonrpc": "2.0", "id": -123, "result": {}},
                            {"jsonrpc": "2.0", "id": "reverse-request",
                             "method": "sampling/createMessage", "params": {}},
                            {"jsonrpc": "2.0", "id": message["id"],
                             "result": {"content": [], "structuredContent": {"ok": True}}}]
                # Multiline data and CRLF delimiters cross tiny reads.
                body = ": heartbeat\r\n\r\n" + "".join(
                    "event: message\r\n" + "".join("data: " + line + "\r\n"
                        for line in json.dumps(item, indent=2).splitlines()) + "\r\n"
                    for item in messages)
                response = self.response(body.encode(), "text/event-stream")
                response.read1 = lambda size=-1: response.read(min(size, 3))
                return response
        self.reply = reply
        self.assertEqual(session.call_tool("echo", {}, 1),
                         {"content": [], "structuredContent": {"ok": True}})

    def test_http_statuses_do_not_echo_headers_or_body(self):
        for status in (401, 403, 400, 404, 500, 503):
            with self.subTest(status=status):
                def reply(request, message):
                    raise urllib.error.HTTPError(request.full_url, status, self.token,
                                                 {"Authorization": self.token},
                                                 io.BytesIO(self.token.encode()))
                self.reply = reply
                self.error("ServerRejected" if status in (401, 403) else "ServerFailed",
                           self.open, bearer=self.token)

    def test_network_failures_and_timeout_mapping(self):
        def unavailable(request, message):
            raise urllib.error.URLError("connection refused")
        self.reply = unavailable
        self.error("ServerFailed", self.open)
        self.reply = None
        session = self.open()
        def timeout(request, message):
            raise TimeoutError("timed out")
        self.reply = timeout
        self.error("ServerFailed", session.list_tools)
        self.error("CommandFailed", session.call_tool, "echo", {}, 0.01)
        self.error("ServerFailed", self.open, init_timeout_s=0.01)

    def test_close_ignores_delete_failure_and_rejects_later_calls(self):
        session = self.open()
        def unavailable(request, message):
            if request.get_method() == "DELETE":
                raise urllib.error.URLError("connection closed")
        self.reply = unavailable
        session.close()
        count = len(self.requests)
        session.close()
        self.error("ServerFailed", session.list_tools)
        self.error("ServerFailed", session.call_tool, "echo", {}, 1)
        self.assertEqual(len(self.requests), count)
        self.assertEqual(self.requests[-1].get_method(), "DELETE")

    def test_call_deadline_applies_to_entire_dripping_body(self):
        session = self.open()
        release, entered = threading.Event(), threading.Event()
        readers = []
        reads = []
        response = self.response(b" " * 1000)
        def drip(size=-1):
            if not readers:
                readers.append(threading.current_thread())
            entered.set()
            release.wait(0.015)
            reads.append(1)
            return response.read(1)
        response.read1 = drip
        self.reply = lambda request, message: response
        try:
            start = time.monotonic()
            self.error("CommandFailed", session.call_tool, "echo", {}, 0.08)
            self.assertLess(time.monotonic() - start, 0.6)
            self.assertTrue(entered.is_set(), "HTTP body was not read")
            self.assertGreaterEqual(len(reads), 2)
        finally:
            release.set()
            for reader in readers:
                reader.join(timeout=1)
                self.assertFalse(reader.is_alive(), "HTTP response reader did not finish")
            # Cleanup's DELETE must not reuse a closed response.
            self.reply = None

    def test_malformed_json_rpc_and_initialize_fields(self):
        messages = [[], {}, {"jsonrpc": "1.0", "id": 1, "result": {}},
                    {"jsonrpc": "2.0", "result": {}},
                    {"jsonrpc": "2.0", "id": 1},
                    {"jsonrpc": "2.0", "id": 1, "result": {},
                     "error": {"code": -1, "message": "bad"}}]
        for missing in INITIALIZED:
            result = dict(INITIALIZED)
            del result[missing]
            messages.append({"jsonrpc": "2.0", "id": 1, "result": result})
        for item in messages:
            with self.subTest(item=item):
                self.reply = lambda request, message: self.response(json.dumps(item).encode())
                self.error("ServerBad", self.open)
        self.reply = lambda request, message: self.response(b"not JSON")
        self.error("ServerBad", self.open)

    def test_response_limit_and_rpc_error_mapping(self):
        session = self.open(bearer=self.token)
        for rpc_code, expected in ((-32602, "ArgumentsBad"), (-32603, "ServerFailed")):
            def reply(request, message):
                return self.response(json.dumps({"jsonrpc": "2.0", "id": message["id"],
                    "error": {"code": rpc_code, "message": "refused " + self.token}}).encode())
            self.reply = reply
            self.error(expected, session.call_tool, "echo", {}, 1)
        self.reply = lambda request, message: self.response(b"x" * (16 * 1024 * 1024 + 1))
        self.error("ServerBad", session.call_tool, "echo", {}, 3)

    def test_open_session_http_file_requires_explicit_env_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "server.json"
            path.write_text(json.dumps({"mcp_server": {"name": "demo", "transport": "http",
                "url": "http://127.0.0.1/mcp", "bearer_token_env": "MCP_HTTP_TEST_TOKEN"}}))
            with patch.dict(os.environ, {"MCP_HTTP_TEST_TOKEN": self.token}):
                error = self.error("PackBad", mcp_client.open_session, path)
                self.assertIn("env_file", str(error))


@unittest.skipUnless(shutil.which("openssl"), "requires openssl")
class HttpTlsTests(unittest.TestCase):
    """Use the repository's real HTTPS fixture and a freshly signed leaf certificate."""

    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        commands = [
            ["req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", "ca.key",
             "-out", "ca.pem", "-days", "1", "-subj", "/CN=mcp-test-ca",
             "-addext", "keyUsage=critical,keyCertSign,cRLSign"],   # Python 3.13+ verifies strictly
            ["req", "-newkey", "rsa:2048", "-nodes", "-keyout", "key.pem",
             "-out", "leaf.csr", "-subj", "/CN=127.0.0.1"],
            ["x509", "-req", "-in", "leaf.csr", "-CA", "ca.pem", "-CAkey", "ca.key",
             "-CAcreateserial", "-out", "cert.pem", "-days", "1", "-extfile", "leaf.ext"]]
        (cls.root / "leaf.ext").write_text("subjectAltName=IP:127.0.0.1,DNS:localhost\n"
            "basicConstraints=CA:FALSE\nextendedKeyUsage=serverAuth\n"
            "subjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\n")
        for command in commands:
            subprocess.run(["openssl", *command], cwd=cls.root, check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.token = "FAKE-" + secrets.token_hex(24)
        (cls.root / "server.env").write_text("MCP_HTTP_TEST_TOKEN=" + cls.token + "\n")
        (cls.root / "server.env").chmod(0o600)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        server = Path(__file__).resolve().parents[2] / "extras/fake-mcp-http/server.py"
        cls.process = subprocess.Popen([sys.executable, str(server), str(port),
            str(cls.root / "cert.pem"), str(cls.root / "key.pem"),
            str(cls.root / "server.env"), str(cls.root / "server.log")],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.addClassCleanup(cls.stop_server)
        cls.url = "https://127.0.0.1:%s/mcp" % port
        deadline = time.monotonic() + 5
        while not (cls.root / "server.log").exists():
            if cls.process.poll() is not None or time.monotonic() >= deadline:
                raise RuntimeError("HTTPS fixture failed to start")
            time.sleep(0.01)

    @classmethod
    def stop_server(cls):
        cls.process.terminate()
        try:
            cls.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            cls.process.kill()
            cls.process.wait(timeout=3)

    def setUp(self):
        environment = patch.dict(os.environ, {
            "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost"})
        environment.start()
        self.addCleanup(environment.stop)

    def test_tls_handshake_list_echo_and_auth_log(self):
        session = mcp_client.open_http(self.url, bearer=self.token, ca_file=self.root / "ca.pem")
        try:
            self.assertEqual(session.protocol_version, "2025-06-18")
            self.assertEqual([tool["name"] for tool in session.list_tools()], ["echo", "list_threads"])
            self.assertEqual(session.call_tool("echo", {"text": "hello"}, 1)["content"][0]["text"],
                             "echo: hello")
        finally:
            session.close()
        log = (self.root / "server.log").read_text()
        self.assertIn('"auth": "ok"', log)
        self.assertTrue(self.token not in log, "Server log disclosed the bearer")

    def test_wrong_token_and_untrusted_ca(self):
        for bearer, ca_file, expected in (("wrong-token", self.root / "ca.pem", "ServerRejected"),
                                           (self.token, None, "ServerFailed")):
            with self.subTest(expected=expected):
                with self.assertRaises(Error) as caught:
                    mcp_client.open_http(self.url, bearer=bearer, ca_file=ca_file)
                self.assertEqual(caught.exception.code, expected)
                self.assertTrue(self.token not in str(caught.exception), "Error disclosed the bearer")
                self.assertNotIn("wrong-token", str(caught.exception))

    def test_open_session_http_file_and_env_file(self):
        path = self.root / "server.json"
        path.write_text(json.dumps({"mcp_server": {"name": "demo", "transport": "http",
            "url": self.url, "bearer_token_env": "MCP_HTTP_TEST_TOKEN",
            "env_file": "server.env", "ca_file": "ca.pem"}}))
        with patch.dict(os.environ, {"MCP_HTTP_TEST_TOKEN": "wrong-inherited-value"}):
            before = dict(os.environ)
            session = mcp_client.open_session(path)
            try:
                self.assertEqual(session.call_tool("echo", {"text": "file"}, 1)
                                 ["content"][0]["text"], "echo: file")
                self.assertEqual(dict(os.environ), before)
            finally:
                session.close()


if __name__ == "__main__":
    unittest.main()
