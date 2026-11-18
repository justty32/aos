"""MCP client 的 stdio／HTTP 傳輸：握手、列工具、呼叫工具與關閉 session。"""

import json
import os
import queue
import selectors
import signal
import subprocess
import ssl
import threading
import time
import urllib.error
import urllib.request

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
        if deadline is None:
            return None
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise Error(timeout_code, "MCP server request timed out")
        return remaining

    def _wait_ready(self, selector, deadline, timeout_code):
        while True:
            remaining = self._remaining(deadline, timeout_code)
            if selector.select(0.05 if remaining is None else min(remaining, 0.05)):
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
        deadline = None if timeout_s is None else time.monotonic() + timeout_s
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

    def list_tools(self, timeout_s=30):
        """照 nextCursor 拿完工具；每頁最多等 30 秒。"""
        tools, params, cursors = [], {}, set()
        while True:
            result = self._request("tools/list", params, timeout_s)
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
        """工具結果不做轉換，isError 也由上層決定如何處理；timeout_s=None＝不限。"""
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


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Bearer 不跟著重新導向送到另一個位置。
        return None


class HttpSession(Session):
    """同步 Streamable HTTP；SSE 中非本次回應的訊息直接略過。"""

    def __init__(self, url, bearer, context):
        self._url = url
        self._bearer = bearer
        self._session_id = None
        self._closed = False
        self._next_id = 0
        self.protocol_version = None
        self._opener = urllib.request.build_opener(
            _NoRedirect(), urllib.request.HTTPSHandler(context=context))

    def _result(self, raw, request_id):
        try:
            message = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
        except (ValueError, UnicodeError, RecursionError):
            raise Error("ServerBad", "MCP server response is not JSON") from None
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            raise Error("ServerBad", "MCP server message is not JSON-RPC 2.0")
        if "method" in message:
            if (not isinstance(message["method"], str) or not message["method"] or
                    "result" in message or "error" in message or
                    ("params" in message and not isinstance(message["params"], dict)) or
                    ("id" in message and type(message["id"]) not in (str, int)) or
                    ("id" not in message and not message["method"].startswith("notifications/"))):
                raise Error("ServerBad", "MCP server request has invalid fields")
            return None
        if (type(message.get("id")) not in (str, int) or
                ("result" in message) == ("error" in message)):
            raise Error("ServerBad", "MCP server response has invalid or missing fields")
        if "error" in message:
            error = message["error"]
            if (not isinstance(error, dict) or type(error.get("code")) is not int or
                    not isinstance(error.get("message"), str)):
                raise Error("ServerBad", "MCP server error has invalid or missing fields")
        elif not isinstance(message["result"], dict):
            raise Error("ServerBad", "MCP server result must be an object")
        if message["id"] != request_id:
            return None
        if "error" in message:
            reason = error["message"]
            if self._bearer:
                reason = reason.replace(self._bearer, "[redacted]")
            raise Error("ArgumentsBad" if error["code"] == -32602 else "ServerFailed", reason)
        return message["result"]

    def _exchange(self, message, deadline, timeout_code, verb="POST"):
        try:
            body = None if message is None else json.dumps(
                message, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError, UnicodeError):
            raise Error("ArgumentsBad", "MCP request must contain valid JSON") from None
        headers = {"Content-Type": "application/json",
                   "Accept": "application/json, text/event-stream"}
        if self._bearer is not None:
            headers["Authorization"] = "Bearer " + self._bearer
        if self._session_id is not None:
            headers["Mcp-Session-Id"] = self._session_id
        if self.protocol_version is not None:
            headers["MCP-Protocol-Version"] = self.protocol_version
        request_id = message.get("id") if message else None
        outcomes = queue.Queue(maxsize=1)

        def transfer():
            try:
                request = urllib.request.Request(self._url, data=body, headers=headers, method=verb)
                with self._opener.open(request, timeout=self._remaining(deadline, timeout_code)) as response:
                    session_id = response.headers.get("Mcp-Session-Id")
                    if verb == "DELETE" or request_id is None:
                        outcomes.put((None, session_id))
                        return
                    kind = response.headers.get_content_type()
                    if kind not in ("application/json", "text/event-stream"):
                        raise Error("ServerBad", "MCP server returned an unsupported content type")
                    buffer, event, total = bytearray(), [], 0
                    skip_lf = False
                    while True:
                        self._remaining(deadline, timeout_code)
                        chunk = response.read1(65536)
                        total += len(chunk)
                        if total > _MAX_RESPONSE_BYTES:
                            raise Error("ServerBad", "MCP server response exceeds 16 MB")
                        buffer.extend(chunk)
                        if skip_lf and buffer:
                            if buffer.startswith(b"\n"):
                                del buffer[:1]
                            skip_lf = False
                        if kind == "application/json":
                            if chunk:
                                continue
                            result = self._result(bytes(buffer), request_id)
                            if result is None:
                                raise Error("ServerBad", "MCP server response has no matching id")
                            outcomes.put((result, session_id))
                            return
                        while buffer:
                            ends = [i for i in (buffer.find(b"\n"), buffer.find(b"\r")) if i >= 0]
                            if ends:
                                end = min(ends)
                                skip_lf = buffer[end:] == b"\r"
                                width = 2 if buffer[end:end + 2] == b"\r\n" else 1
                                line = bytes(buffer[:end])
                                del buffer[:end + width]
                            elif not chunk:
                                line, buffer = bytes(buffer), bytearray()
                            else:
                                break
                            if not line:
                                if event:
                                    result = self._result(b"\n".join(event), request_id)
                                    event = []
                                    if result is not None:
                                        outcomes.put((result, session_id))
                                        return
                            elif line.startswith(b"data:"):
                                data = line[5:]
                                event.append(data[1:] if data.startswith(b" ") else data)
                        if not chunk:
                            raise Error("ServerBad", "MCP server stream ended without a matching response")
            except urllib.error.HTTPError as exc:
                code = "ServerRejected" if exc.code in (401, 403) else "ServerFailed"
                exc.close()
                outcomes.put(Error(code, "MCP HTTP request failed (status %s)" % exc.code))
            except Error as exc:
                outcomes.put(exc)
            except (TimeoutError, urllib.error.URLError) as exc:
                reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
                code = timeout_code if isinstance(reason, TimeoutError) else "ServerFailed"
                detail = type(reason).__name__
                if isinstance(reason, OSError) and type(reason.errno) is int:
                    detail += " errno=%s" % reason.errno
                outcomes.put(Error(code, "MCP HTTP request timed out" if isinstance(reason, TimeoutError)
                                   else "MCP HTTP connection failed (%s)" % detail))
            except Exception as exc:
                # urllib 的例外可能帶 URL 或 Authorization；只轉印例外種類。
                outcomes.put(Error("ServerFailed", "MCP HTTP request failed (%s)" % type(exc).__name__))

        # urlopen 與 HTTP header/body 讀取都受同一截止時間約束，滴流不能延長呼叫。
        threading.Thread(target=transfer, daemon=True).start()
        try:
            outcome = outcomes.get(timeout=self._remaining(deadline, timeout_code))
        except queue.Empty:
            raise Error(timeout_code, "MCP server request timed out") from None
        if isinstance(outcome, Error):
            raise outcome from None
        result, session_id = outcome
        if message and message.get("method") == "initialize":
            self._session_id = session_id
        return result

    def _request(self, method, params, timeout_s, timeout_code="ServerFailed", initializing=False):
        if self._closed:
            raise Error("ServerFailed", "MCP session is closed")
        self._next_id += 1
        return self._exchange({"jsonrpc": "2.0", "id": self._next_id,
                               "method": method, "params": params},
                              None if timeout_s is None else time.monotonic() + timeout_s, timeout_code)

    def close(self):
        """DELETE 失敗不阻擋收尾；重複呼叫不再送請求。"""
        if self._closed:
            return
        self._closed = True
        try:
            self._exchange(None, time.monotonic() + 2, "ServerFailed", "DELETE")
        except Error:
            pass


def open_http(url, bearer=None, ca_file=None, init_timeout_s=30):
    """以系統 CA 或指定 CA 開啟 HTTP session，再送 initialized 通知。"""
    try:
        context = ssl.create_default_context(cafile=ca_file)
    except (OSError, ValueError):
        raise Error("ServerFailed", "cannot load MCP HTTP TLS certificates") from None
    session = HttpSession(url, bearer, context)
    try:
        result = session._request("initialize", {
            "protocolVersion": _PROTOCOL_VERSION, "capabilities": {},
            "clientInfo": {"name": "aos", "version": "0.1"}}, init_timeout_s)
        info = result.get("serverInfo")
        if (not isinstance(result.get("protocolVersion"), str) or not result["protocolVersion"] or
                not isinstance(result.get("capabilities"), dict) or not isinstance(info, dict) or
                not isinstance(info.get("name"), str) or not isinstance(info.get("version"), str)):
            raise Error("ServerBad", "MCP initialize result has invalid or missing fields")
        session.protocol_version = result["protocolVersion"]
        session._exchange({"jsonrpc": "2.0", "method": "notifications/initialized"},
                          time.monotonic() + init_timeout_s, "ServerFailed")
        return session
    except BaseException:
        if session._session_id is not None:
            session.close()
        else:
            session._closed = True
        raise


def open_session(server_file, init_timeout_s=30):
    """沿用 server 檔與 env 檔讀法，依 transport 開 stdio 或 HTTP。"""
    server = mcp_server_file.load(server_file)
    if server["transport"] == "http":
        if "bearer_token_env" in server and "env_file" not in server:
            raise Error("PackBad", "HTTP bearer_token_env requires env_file; add env_file to the server file")
        return open_http(server["url"], bearer=mcp_server_file.bearer_value(server),
                         ca_file=server.get("ca_file"), init_timeout_s=init_timeout_s)
    argv, env, cwd = mcp_server_file.stdio_launch(server_file)
    return open_stdio(argv, env, cwd=cwd, init_timeout_s=init_timeout_s)
