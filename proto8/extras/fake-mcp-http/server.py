"""Fake streamable-HTTP MCP server for testing external MCP (external-mcp 05/06): 127.0.0.1 only, TLS, checks Authorization: Bearer, two harmless tools (echo, list_threads); logs auth ok/wrong/missing, never the token."""
import json, ssl, sys, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT, CERT, KEY, TOKFILE, LOG = int(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
TOKEN = open(TOKFILE).read().split("=", 1)[1].strip()

TOOLS = [
    {"name": "echo", "description": "Echo back the given text.",
     "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
    {"name": "list_threads", "description": "List forum threads (fixed fake data).",
     "inputSchema": {"type": "object", "properties": {}}},
]
THREADS = [{"id": 101, "title": "fake thread: printer on 3F"}, {"id": 102, "title": "fake thread: VPN slow"}]


def log(**kw):
    kw["t"] = time.strftime("%H:%M:%S")
    with open(LOG, "a") as f:
        f.write(json.dumps(kw) + "\n")


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def auth(self):
        got = self.headers.get("Authorization")
        if got is None:
            return "missing"
        return "ok" if got == "Bearer " + TOKEN else "wrong"

    def reply(self, code, body=None, extra=None):
        data = b"" if body is None else json.dumps(body).encode()
        self.send_response(code)
        if body is not None:
            self.send_header("Content-Type", "application/json")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        a = self.auth()
        log(verb="GET", path=self.path, auth=a)
        self.reply(401 if a != "ok" else 405)

    def do_DELETE(self):
        log(verb="DELETE", path=self.path, auth=self.auth())
        self.reply(200)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n)
        a = self.auth()
        try:
            msg = json.loads(raw)
        except ValueError:
            msg = {}
        method = msg.get("method") if isinstance(msg, dict) else "batch"
        entry = dict(verb="POST", path=self.path, auth=a, method=method)
        if method == "tools/call":
            entry["tool"] = msg.get("params", {}).get("name")
        log(**entry)
        if a != "ok":
            return self.reply(401, {"error": "unauthorized"}, {"WWW-Authenticate": "Bearer"})
        if "id" not in msg:
            return self.reply(202)
        rid, p = msg["id"], msg.get("params") or {}
        if method == "initialize":
            res = {"protocolVersion": p.get("protocolVersion", "2025-03-26"), "capabilities": {"tools": {}},
                   "serverInfo": {"name": "fake-teamsite", "version": "0.0.1"}}
            return self.reply(200, {"jsonrpc": "2.0", "id": rid, "result": res}, {"Mcp-Session-Id": uuid.uuid4().hex})
        if method == "tools/list":
            return self.reply(200, {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}})
        if method == "tools/call":
            name, args = p.get("name"), p.get("arguments") or {}
            if name == "echo":
                text = "echo: " + str(args.get("text", ""))
            elif name == "list_threads":
                text = json.dumps(THREADS)
            else:
                return self.reply(200, {"jsonrpc": "2.0", "id": rid, "error": {"code": -32602, "message": "unknown tool"}})
            return self.reply(200, {"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": text}], "isError": False}})
        if method == "ping":
            return self.reply(200, {"jsonrpc": "2.0", "id": rid, "result": {}})
        return self.reply(200, {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "method not found"}})


srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain(CERT, KEY)
srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
log(verb="START", port=PORT)
srv.serve_forever()
