"""MCP client 的 stdio 傳輸：握手、列工具、呼叫工具與收回 server 行程群。"""

import json
import os
import selectors
import signal
import subprocess
import time

import mcp_server_file
from tool_io import Error

_PROTOCOL_VERSION = "2025-06-18"
_MAX_RESPONSE_BYTES = 16 * 1024 * 1024


def _reject_constant(value):
    raise ValueError("invalid JSON constant")


class Session:
    """一個同步的 stdio session；同一時間只等自己送出的那一則請求。"""

    def __init__(self, process):
        self._process = process
        self._closed = False
        self._next_id = 0
        self._buffer = bytearray()
        self._non_json_lines = 0
        self.protocol_version = None
        self._reader = selectors.DefaultSelector()
        os.set_blocking(process.stdout.fileno(), False)
        os.set_blocking(process.stdin.fileno(), False)
        self._reader.register(process.stdout, selectors.EVENT_READ)

    @staticmethod
    def _remaining(deadline, timeout_code):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise Error(timeout_code, "MCP server request timed out")
        return remaining

    def _wait_ready(self, selector, deadline, timeout_code):
        while True:
            remaining = self._remaining(deadline, timeout_code)
            if selector.select(min(remaining, 0.05)):
                return
            if self._process.poll() is not None:
                raise Error("ServerFailed", "MCP server exited")

    def _send(self, message, deadline, timeout_code):
        try:
            data = memoryview((json.dumps(message, ensure_ascii=False,
                                          allow_nan=False) + "\n").encode("utf-8"))
        except (TypeError, ValueError, UnicodeError):
            raise Error("ArgumentsBad", "MCP request must contain valid JSON") from None
        try:
            with selectors.DefaultSelector() as writer:
                writer.register(self._process.stdin, selectors.EVENT_WRITE)
                while data:
                    self._wait_ready(writer, deadline, timeout_code)
                    try:
                        written = os.write(self._process.stdin.fileno(), data)
                    except BlockingIOError:
                        continue
                    data = data[written:]
        except OSError:
            raise Error("ServerFailed", "MCP server input closed") from None

    def _line(self, deadline, timeout_code):
        while True:
            self._remaining(deadline, timeout_code)
            end = self._buffer.find(b"\n")
            if end > _MAX_RESPONSE_BYTES or (end < 0 and len(self._buffer) > _MAX_RESPONSE_BYTES):
                raise Error("ServerBad", "MCP server response exceeds 16 MB")
            if end >= 0:
                line = bytes(self._buffer[:end])
                del self._buffer[:end + 1]
                return line
            try:
                self._wait_ready(self._reader, deadline, timeout_code)
                chunk = os.read(self._process.stdout.fileno(), 65536)
            except BlockingIOError:
                continue
            except OSError:
                raise Error("ServerFailed", "cannot read MCP server output") from None
            if not chunk:
                raise Error("ServerFailed", "MCP server closed its output")
            self._buffer.extend(chunk)

    def _message(self, deadline, timeout_code, initializing):
        while True:
            line = self._line(deadline, timeout_code)
            try:
                message = json.loads(line.decode("utf-8"), parse_constant=_reject_constant)
            except (ValueError, UnicodeError, RecursionError):
                self._non_json_lines += 1
                if not initializing or self._non_json_lines >= 100:
                    raise Error("ServerBad", "MCP server output is not JSON") from None
                continue
            self._non_json_lines = 0
            if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
                raise Error("ServerBad", "MCP server message is not JSON-RPC 2.0")
            return message

    def _request(self, method, params, timeout_s, timeout_code="ServerFailed", initializing=False):
        if self._closed:
            raise Error("ServerFailed", "MCP session is closed")
        self._next_id += 1
        request_id = self._next_id
        deadline = time.monotonic() + timeout_s
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method,
                    "params": params}, deadline, timeout_code)
        while True:
            message = self._message(deadline, timeout_code, initializing)
            if "method" in message:
                name = message["method"]
                if (not isinstance(name, str) or not name or
                        "result" in message or "error" in message or
                        ("params" in message and not isinstance(message["params"], dict))):
                    raise Error("ServerBad", "MCP server request has invalid fields")
                if "id" in message:
                    if type(message["id"]) not in (str, int):
                        raise Error("ServerBad", "MCP server request has an invalid id")
                    self._send({"jsonrpc": "2.0", "id": message["id"],
                                "error": {"code": -32601, "message": "method not supported"}},
                               deadline, timeout_code)
                elif not name.startswith("notifications/"):
                    raise Error("ServerBad", "MCP server request is missing an id")
                continue
            if (type(message.get("id")) not in (str, int) or message["id"] != request_id or
                    ("result" in message) == ("error" in message)):
                raise Error("ServerBad", "MCP server response has invalid or missing fields")
            if "error" in message:
                error = message["error"]
                if (not isinstance(error, dict) or type(error.get("code")) is not int or
                        not isinstance(error.get("message"), str)):
                    raise Error("ServerBad", "MCP server error has invalid or missing fields")
                code = "ArgumentsBad" if error["code"] == -32602 else "ServerFailed"
                raise Error(code, error["message"])
            if not isinstance(message["result"], dict):
                raise Error("ServerBad", "MCP server result must be an object")
            return message["result"]

    def list_tools(self):
        """照 nextCursor 拿完工具；每頁最多等 30 秒。"""
        tools, params, cursors = [], {}, set()
        while True:
            result = self._request("tools/list", params, 30)
            page = result.get("tools")
            if not isinstance(page, list) or not all(
                    isinstance(tool, dict) and isinstance(tool.get("name"), str) and
                    tool["name"] and isinstance(tool.get("inputSchema"), dict) for tool in page):
                raise Error("ServerBad", "MCP tools/list result has invalid or missing tools")
            tools.extend(page)
            if "nextCursor" not in result:
                return tools
            cursor = result["nextCursor"]
            if not isinstance(cursor, str) or cursor in cursors:
                raise Error("ServerBad", "MCP tools/list returned an invalid or repeated cursor")
            cursors.add(cursor)
            params = {"cursor": cursor}

    def call_tool(self, name, arguments, timeout_s):
        """工具結果不做轉換，isError 也由上層決定如何處理。"""
        return self._request("tools/call", {"name": name, "arguments": arguments},
                             timeout_s, "CommandFailed")

    def _wait_group(self, timeout_s):
        deadline = time.monotonic() + timeout_s
        while True:
            self._process.poll()  # 回收直接子行程，避免 zombie 讓 killpg 一直看得到群組。
            try:
                os.killpg(self._process.pid, 0)
            except ProcessLookupError:
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(min(0.02, remaining))

    def close(self):
        """先關 stdin，再等兩秒、TERM 整群、再等兩秒才 KILL；可以重複收。"""
        if self._closed:
            return
        self._closed = True
        try:
            self._process.stdin.close()
        except OSError:
            pass
        try:
            for sig in (signal.SIGTERM, signal.SIGKILL):
                if self._wait_group(2):
                    break
                try:
                    os.killpg(self._process.pid, sig)
                except ProcessLookupError:
                    break
            self._process.wait()
        finally:
            self._reader.close()
            self._process.stdout.close()


def open_stdio(argv, env, cwd, init_timeout_s=30):
    """起一個獨立行程群、initialize，再通知 initialized；失敗先收乾淨。"""
    try:
        process = subprocess.Popen(argv, env=env, cwd=cwd, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=None, bufsize=0,
                                   start_new_session=True)
    except (OSError, ValueError, TypeError):
        raise Error("CommandMissing", "cannot start MCP server") from None
    session = Session(process)
    try:
        result = session._request("initialize", {
            "protocolVersion": _PROTOCOL_VERSION, "capabilities": {},
            "clientInfo": {"name": "aos", "version": "0.1"}},
            init_timeout_s, initializing=True)
        info = result.get("serverInfo")
        if (not isinstance(result.get("protocolVersion"), str) or not result["protocolVersion"] or
                not isinstance(result.get("capabilities"), dict) or not isinstance(info, dict) or
                not isinstance(info.get("name"), str) or not isinstance(info.get("version"), str)):
            raise Error("ServerBad", "MCP initialize result has invalid or missing fields")
        session.protocol_version = result["protocolVersion"]
        session._send({"jsonrpc": "2.0", "method": "notifications/initialized"},
                      time.monotonic() + init_timeout_s, "ServerFailed")
        return session
    except BaseException:
        session.close()
        raise


def open_session(server_file):
    """沿用 server 檔與 env 檔的讀法；這一步只接受 stdio。"""
    server = mcp_server_file.load(server_file)
    if server["transport"] == "http":
        raise Error("PackBad", "http is not supported yet")
    argv, env = mcp_server_file.stdio_launch(server_file)
    return open_stdio(argv, env, cwd=os.environ.get("AOS_WS") or os.getcwd())
