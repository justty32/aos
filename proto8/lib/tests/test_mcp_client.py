"""Verify MCP stdio sessions, fake tools, protocol failures, deadlines, and process cleanup."""

import base64
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import textwrap
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mcp_client
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

    def test_open_session_server_file_env_file_and_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            workspace.mkdir()
            shutil.copyfile(FAKE, workspace / FAKE.name)
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

    def test_open_session_defaults_to_current_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copyfile(FAKE, root / FAKE.name)
            path = root / "server.json"
            path.write_text(json.dumps({"mcp_server": {
                "name": "demo", "transport": "stdio", "command": sys.executable,
                "args": [FAKE.name], "env": {"FAKE_MODE": ""}}}), encoding="utf-8")
            previous = os.getcwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {}, clear=False):
                    os.environ.pop("AOS_WS", None)
                    session = mcp_client.open_session(path)
                try:
                    self.assertEqual(session.protocol_version, "2025-06-18")
                finally:
                    session.close()
            finally:
                os.chdir(previous)

    def test_open_session_http_is_not_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "server.json"
            path.write_text(json.dumps({"mcp_server": {
                "name": "demo", "transport": "http", "url": "http://127.0.0.1:1/mcp"}}), encoding="utf-8")
            error = self.assert_error("PackBad", mcp_client.open_session, path)
            self.assertIn("http is not supported yet", str(error))

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


if __name__ == "__main__":
    unittest.main()
