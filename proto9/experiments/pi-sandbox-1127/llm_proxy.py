#!/usr/bin/env python3
"""The llm proxy kernel of pi-sandbox-1127: serves OpenAI-style HTTP on one unix socket (/llm/sock), declares aos/llm, counts and caps requests, forwards to the real endpoint."""

import argparse
import http.client
import json
import os
import socket
import socketserver
import struct
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler

LOCK = threading.Lock()
A = None  # parsed arguments


def log(*a):
    print("llm-proxy:", *a, file=sys.stderr, flush=True)


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ------------------------------------------------------------ budget (a small json file that outlives one run)

def budget_read():
    try:
        with open(A.budget) as f:
            return json.load(f)
    except FileNotFoundError:
        return {"used": 0, "limit": A.limit}


def budget_write(b):
    tmp = A.budget + ".tmp"
    with open(tmp, "w") as f:
        json.dump(b, f)
        f.write("\n")
    os.replace(tmp, A.budget)


def status_write(b):
    """The status file in the declared dir: what anyone who sees /llm can read."""
    text = "requests_used: %d\nrequests_limit: %d\nmodels: %s\nupstream: %s\n" % (
        b["used"], b["limit"], " ".join(A.model), "fake" if A.fake else "real")
    tmp = os.path.join(A.dir, ".status.tmp")
    with open(tmp, "w") as f:
        f.write(text)
    os.replace(tmp, os.path.join(A.dir, "status"))


def ledger(rec):
    rec["at"] = now()
    with open(A.log, "a") as f:
        f.write(json.dumps(rec) + "\n")


# ------------------------------------------------------------ the interface declaration (aoslua: reachable = has it)

def declare():
    d = os.path.join(A.dir, "__meta", "__interfaces", "aos", "llm")
    os.makedirs(d, exist_ok=True)
    files = {
        "kind": "socket",                       # like aos/ctl's kind: file | socket
        "path": A.sock_name,                    # relative to the declaring dir
        "protocol": "http/1.1",                 # what is spoken on the socket
        "api": "openai-completions",            # POST <base>/chat/completions, the OpenAI chat shape (pi's name for it)
        "base": "/v1",                          # path prefix of the API on the socket
        "models": "\n".join(A.model),           # model ids accepted; others get 403
        "status": "status",                     # file (relative) with requests_used / requests_limit
    }
    for k, v in files.items():
        with open(os.path.join(d, k), "w") as f:
            f.write(v + "\n")
    with open(os.path.join(A.dir, "__meta", "__interfaces", "aos", "description"), "w") as f:
        f.write("llm proxy kernel: the only way to the model; counts and caps requests\n")


# ------------------------------------------------------------ http on the unix socket

def sse_usage(body):
    """Last usage object seen in an OpenAI SSE stream (or a plain JSON body)."""
    usage = None
    try:
        return json.loads(body).get("usage")
    except ValueError:
        pass
    for line in body.split(b"\n"):
        line = line.strip()
        if not line.startswith(b"data:"):
            continue
        data = line[5:].strip()
        if data == b"[DONE]":
            continue
        try:
            j = json.loads(data)
        except ValueError:
            continue
        if isinstance(j, dict) and j.get("usage"):
            usage = j["usage"]
    return usage


def fake_step(req):
    """The scripted fake brain: pick the script whose "when" is in the first user message, take step N (N = assistant
    messages so far). A step is {"tool": name, "args": {...}} or {"text": "..."}; past the end it says it is done."""
    msgs = req.get("messages", [])
    first = next((m.get("content") for m in msgs if m.get("role") == "user"), "")
    first = first if isinstance(first, str) else json.dumps(first)
    n = sum(1 for m in msgs if m.get("role") == "assistant")
    for s in A.script:
        if s["when"] in first:
            return s["steps"][n] if n < len(s["steps"]) else {"text": "FAKE DONE (scripted fake brain)"}
    return {"text": "FAKE OK (llm proxy in fake mode; no model was called)"}


def fake_body(model, req):
    step = fake_step(req)
    usage = {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
    if "tool" in step:
        call = {"index": 0, "id": "call_fake_%d" % int(time.monotonic() * 1000), "type": "function",
                "function": {"name": step["tool"], "arguments": json.dumps(step["args"])}}
        delta, finish = {"role": "assistant", "content": None, "tool_calls": [call]}, "tool_calls"
        msg = {"role": "assistant", "content": None, "tool_calls": [{k: v for k, v in call.items() if k != "index"}]}
    else:
        delta = {"role": "assistant", "content": step["text"]}
        msg, finish = {"role": "assistant", "content": step["text"]}, "stop"
    if not req.get("stream"):
        return "application/json", json.dumps({
            "id": "fake", "object": "chat.completion", "created": int(time.time()), "model": model,
            "choices": [{"index": 0, "message": msg, "finish_reason": finish}], "usage": usage}).encode()
    chunks = [
        {"choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": finish}]},
        {"choices": [], "usage": usage},
    ]
    out = b""
    for c in chunks:
        c.update({"id": "fake", "object": "chat.completion.chunk", "created": int(time.time()), "model": model})
        out += b"data: " + json.dumps(c).encode() + b"\n\n"
    return "text/event-stream", out + b"data: [DONE]\n\n"


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # client_address is '' on a unix socket
        pass

    def peer_pid(self):
        try:
            cred = self.connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
            return struct.unpack("3i", cred)[0]
        except OSError:
            return None

    def reply(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def error(self, code, msg):
        self.reply(code, "application/json", json.dumps({"error": {"message": msg, "type": "llm_proxy"}}).encode())

    def read_body(self):
        if self.headers.get("Transfer-Encoding", "").lower() == "chunked":
            body = b""
            while True:
                n = int(self.rfile.readline().split(b";")[0], 16)
                if n == 0:
                    self.rfile.readline()
                    return body
                body += self.rfile.read(n)
                self.rfile.readline()
        return self.rfile.read(int(self.headers.get("Content-Length", "0")))

    def do_GET(self):
        if self.path.rstrip("/") == A.base + "/models":
            data = [{"id": m, "object": "model", "owned_by": "llm-proxy"} for m in A.model]
            return self.reply(200, "application/json", json.dumps({"object": "list", "data": data}).encode())
        self.error(404, "llm proxy: only GET %s/models and POST %s/chat/completions" % (A.base, A.base))

    def do_POST(self):
        pid = self.peer_pid()
        if self.path.split("?")[0] != A.base + "/chat/completions":
            return self.error(404, "llm proxy: only POST %s/chat/completions" % A.base)
        raw = self.read_body()
        try:
            req = json.loads(raw)
        except ValueError:
            return self.error(400, "llm proxy: body is not JSON")
        model = req.get("model")
        if model not in A.model:
            ledger({"result": "refused", "why": "model", "model": model, "peer_pid": pid})
            return self.error(403, "llm proxy: model %r is not allowed (allowed: %s)" % (model, ", ".join(A.model)))
        with LOCK:  # count before sending, so a crash in the middle still counts
            b = budget_read()
            if b["used"] >= b["limit"]:
                ledger({"result": "refused", "why": "budget", "model": model, "peer_pid": pid, "used": b["used"]})
                status_write(b)
                return self.error(429, "llm proxy: request budget used up (%d of %d)" % (b["used"], b["limit"]))
            if not A.fake:
                b["used"] += 1
                budget_write(b)
            n = b["used"]
            status_write(b)
        t0 = time.monotonic()
        if A.fake:
            with open(os.path.join(os.path.dirname(A.log), "last_request.json"), "w") as f:
                json.dump(req, f, indent=1)
            ctype, body = fake_body(model, req)
            code = 200
        else:
            u = urllib.parse.urlsplit(A.upstream)
            conn = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=300)
            try:
                # no Authorization header is passed on: pi only has a fake key; the endpoint holds the real ones
                conn.request("POST", u.path.rstrip("/") + "/chat/completions", body=raw,
                             headers={"Content-Type": "application/json", "Accept": self.headers.get("Accept", "*/*")})
                r = conn.getresponse()
                code, ctype, body = r.status, r.getheader("Content-Type", "application/json"), r.read()
            except OSError as e:
                ledger({"result": "upstream_error", "n": n, "model": model, "peer_pid": pid, "error": str(e)})
                return self.error(502, "llm proxy: upstream: %s" % e)
            finally:
                conn.close()
        ledger({"result": "sent" if not A.fake else "fake", "n": n, "model": model, "peer_pid": pid, "status": code,
                "stream": bool(req.get("stream")), "messages": len(req.get("messages", [])),
                "tools": len(req.get("tools", []) or []), "usage": sse_usage(body), "bytes": len(body),
                "seconds": round(time.monotonic() - t0, 2)})
        self.reply(code, ctype, body)


class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def main():
    global A
    ap = argparse.ArgumentParser(description="llm proxy kernel: OpenAI-style HTTP on a unix socket, counted and capped")
    ap.add_argument("--dir", required=True, help="the dir that appears as /llm: socket, declaration, status")
    ap.add_argument("--sock-name", default="sock")
    ap.add_argument("--base", default="/v1")
    ap.add_argument("--budget", required=True, help="json file {used, limit}; kept across runs")
    ap.add_argument("--limit", type=int, required=True, help="refuse once used reaches this (a lower value in the file wins)")
    ap.add_argument("--log", required=True, help="jsonl ledger, one line per request")
    ap.add_argument("--upstream", default="http://127.0.0.1:4000/v1")
    ap.add_argument("--model", action="append", required=True, help="allowed model id (repeat)")
    ap.add_argument("--fake", action="store_true", help="answer from a script, never call the upstream")
    ap.add_argument("--fake-script", help='json [{"when": text in the first user message, "steps": [...]}]')
    A = ap.parse_args()
    A.script = []
    if A.fake_script:
        with open(A.fake_script) as f:
            A.script = json.load(f)
    b = budget_read()
    b["limit"] = min(b.get("limit", A.limit), A.limit)
    budget_write(b)
    declare()
    status_write(b)
    sp = os.path.join(A.dir, A.sock_name)
    if os.path.exists(sp):
        os.unlink(sp)
    srv = Server(sp, Handler)
    log("listening on %s (%s); budget %d of %d used; models %s" % (
        sp, "fake" if A.fake else A.upstream, b["used"], b["limit"], ",".join(A.model)))
    srv.serve_forever()


if __name__ == "__main__":
    main()
