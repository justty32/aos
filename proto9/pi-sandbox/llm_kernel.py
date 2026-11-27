#!/usr/bin/env python3
"""llm kernel: serves OpenAI-style HTTP on one unix socket in the dir it puts out, declares aos/llm there (with a relay), counts and caps requests, forwards to an http URL or to another dir that declares aos/llm (so kernels stack)."""

import argparse
import http.client
import json
import os
import shutil
import socket
import socketserver
import struct
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler

sys.dont_write_bytecode = True  # keep the repo free of __pycache__
import fake_brain  # noqa: E402

PROG = "llm-kernel"
HERE = os.path.dirname(os.path.abspath(__file__))
DECL = os.path.join(".aos", "interfaces", "aos", "llm")
LOCK = threading.Lock()
A = None  # parsed arguments


def fail(code, msg, exit_code=1):
    print("%s: error: %s %s" % (PROG, code, msg), file=sys.stderr, flush=True)
    sys.exit(exit_code)


def warn(msg):
    print("%s: warning: %s" % (PROG, msg), file=sys.stderr, flush=True)


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write_atomic(path, text):
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path) + ".tmp")
    with open(tmp, "w") as f:
        f.write(text)
    os.replace(tmp, path)


# ------------------------------------------------------------ budget, status, ledger

def budget_read():
    try:
        with open(A.budget) as f:
            return json.load(f)
    except FileNotFoundError:
        return {"used": 0, "limit": A.limit}


def budget_write(b):
    write_atomic(A.budget, json.dumps(b) + "\n")


def status_write(b):
    """The status file in the dir put out: anyone who sees the dir can read how much is left."""
    write_atomic(os.path.join(A.dir, "status"), "requests_used: %d\nrequests_limit: %d\nmodels: %s\nupstream: %s\n" % (
        b["used"], b["limit"], " ".join(A.model), A.upstream_desc))


def ledger(rec):
    rec["at"] = now()
    with open(A.log, "a") as f:
        f.write(json.dumps(rec) + "\n")


# ------------------------------------------------------------ the declaration (reachable = has the interface)

def read_decl(d):
    """The aos/llm declaration of dir d as a dict, or raise ValueError saying what is wrong."""
    out = {}
    for k in ("kind", "path", "protocol", "api", "base"):
        try:
            with open(os.path.join(d, DECL, k)) as f:
                out[k] = f.read().strip()
        except OSError as e:
            raise ValueError("%s does not declare aos/llm (%s: %s)" % (d, os.path.join(DECL, k), e.strerror))
    want = {"kind": "socket", "protocol": "http/1.1", "api": "openai-completions"}
    for k, v in want.items():
        if out[k] != v:
            raise ValueError("%s declares aos/llm %s %r, this kernel speaks only %r" % (d, k, out[k], v))
    try:
        with open(os.path.join(d, DECL, "models")) as f:
            out["models"] = f.read().split()
    except OSError:
        out["models"] = []
    out["sock"] = os.path.join(d, out["path"])
    return out


def declare():
    d = os.path.join(A.dir, DECL)
    os.makedirs(d, exist_ok=True)
    files = {
        "kind": "socket",               # like aos/ctl's kind: file | socket
        "path": A.sock_name,            # relative to the declaring dir
        "protocol": "http/1.1",         # what is spoken on the socket
        "api": "openai-completions",    # POST <base>/chat/completions, the OpenAI chat shape (pi's name for it)
        "base": A.base,                 # path prefix of the API on the socket
        "models": "\n".join(A.model),   # model ids accepted; others get 403
        "status": "status",             # file (relative) with requests_used / requests_limit
    }
    if A.relay_name:  # first word: the relay's path (relative); the rest: how to use it
        files["relay"] = ("%s node script: node <dir>/%s --llm <dir> --port N [-- CMD ARGS...]; listens on "
                          "127.0.0.1:N, joins each connection to the socket, runs CMD and exits with its code"
                          % (A.relay_name, A.relay_name))
    for k, v in files.items():
        write_atomic(os.path.join(d, k), v + "\n")
    write_atomic(os.path.join(A.dir, ".aos", "interfaces", "aos", "description"), A.description + "\n")


def place_relay():
    """Put the relay into the dir (from --relay, or relay.js next to this file); keep one that is already there."""
    if not A.relay_name:
        return
    dst = os.path.join(A.dir, A.relay_name)
    src = A.relay or os.path.join(HERE, "relay.js")
    if os.path.exists(src):
        tmp = dst + ".tmp"
        shutil.copyfile(src, tmp)
        os.chmod(tmp, 0o755)
        os.replace(tmp, dst)
    elif not os.path.exists(dst):
        warn("no relay to put out (%s is missing and %s has none); the aos/llm declaration has no relay line" % (src, A.dir))
        A.relay_name = None


# ------------------------------------------------------------ upstream: an http URL or another aos/llm dir

class UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, path, timeout):
        super().__init__("llm", timeout=timeout)
        self.unix_path = path

    def connect(self):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        s.connect(self.unix_path)
        self.sock = s


def upstream_post(raw, accept):
    """POST the request body to the upstream; returns (status, content type, body)."""
    if A.up_dir:
        d = read_decl(A.up_dir)  # read each time: the lower kernel may have been restarted
        conn, path = UnixHTTPConnection(d["sock"], 300), d["base"].rstrip("/") + "/chat/completions"
    else:
        u = urllib.parse.urlsplit(A.upstream)
        cls = http.client.HTTPSConnection if u.scheme == "https" else http.client.HTTPConnection
        conn, path = cls(u.hostname, u.port, timeout=300), u.path.rstrip("/") + "/chat/completions"
    try:
        # no Authorization header is passed on: the client only has a fake key; the endpoint holds the real ones
        conn.request("POST", path, body=raw, headers={"Content-Type": "application/json", "Accept": accept})
        r = conn.getresponse()
        return r.status, r.getheader("Content-Type", "application/json"), r.read()
    finally:
        conn.close()


def sse_usage(body):
    """Last usage object in an OpenAI SSE stream (or a plain JSON body)."""
    try:
        return json.loads(body).get("usage")
    except (ValueError, AttributeError):
        pass
    usage = None
    for line in body.split(b"\n"):
        line = line.strip()
        if line.startswith(b"data:") and line[5:].strip() != b"[DONE]":
            try:
                j = json.loads(line[5:])
            except ValueError:
                continue
            if isinstance(j, dict) and j.get("usage"):
                usage = j["usage"]
    return usage


# ------------------------------------------------------------ http on the unix socket

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # the ledger is the log
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
        self.reply(code, "application/json", json.dumps({"error": {"message": msg, "type": "llm_kernel"}}).encode())

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
            data = [{"id": m, "object": "model", "owned_by": "llm-kernel"} for m in A.model]
            return self.reply(200, "application/json", json.dumps({"object": "list", "data": data}).encode())
        self.error(404, "llm kernel: only GET %s/models and POST %s/chat/completions" % (A.base, A.base))

    def do_POST(self):
        pid = self.peer_pid()
        if self.path.split("?")[0] != A.base + "/chat/completions":
            return self.error(404, "llm kernel: only POST %s/chat/completions" % A.base)
        raw = self.read_body()
        try:
            req = json.loads(raw)
        except ValueError:
            return self.error(400, "llm kernel: body is not JSON")
        model = req.get("model")
        if model not in A.model:
            ledger({"result": "refused", "why": "model", "model": model, "peer_pid": pid})
            return self.error(403, "llm kernel: model %r is not allowed (allowed: %s)" % (model, ", ".join(A.model)))
        with LOCK:  # count before sending, so a crash in the middle still counts
            b = budget_read()
            if b["used"] >= b["limit"]:
                ledger({"result": "refused", "why": "budget", "model": model, "peer_pid": pid, "used": b["used"]})
                status_write(b)
                return self.error(429, "llm kernel: request budget used up (%d of %d)" % (b["used"], b["limit"]))
            if not A.fake:
                b["used"] += 1
                budget_write(b)
            n = b["used"]
            status_write(b)
        t0 = time.monotonic()
        if A.fake:
            (ctype, body), code = fake_brain.body(A.script, model, req), 200
        else:
            try:
                code, ctype, body = upstream_post(raw, self.headers.get("Accept", "*/*"))
            except (OSError, ValueError, http.client.HTTPException) as e:
                ledger({"result": "upstream_error", "n": n, "model": model, "peer_pid": pid, "error": str(e)})
                return self.error(502, "llm kernel: upstream: %s" % e)
        ledger({"result": "fake" if A.fake else "sent", "n": n, "model": model, "peer_pid": pid, "status": code,
                "stream": bool(req.get("stream")), "messages": len(req.get("messages", [])),
                "tools": len(req.get("tools", []) or []), "usage": sse_usage(body), "bytes": len(body),
                "seconds": round(time.monotonic() - t0, 2)})
        self.reply(code, ctype, body)


class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


class Parser(argparse.ArgumentParser):
    def error(self, message):
        fail("ArgumentsBad", "%s (usage: %s --help)" % (message, self.prog), 2)


def main():
    global A
    ap = Parser(prog=PROG, description="llm kernel: OpenAI-style HTTP on a unix socket in the dir it puts out, "
                "declared as aos/llm, counted and capped; forwards to an http URL or to another aos/llm dir")
    ap.add_argument("--dir", required=True, help="the dir it puts out (seen as /llm by the client): socket, relay, "
                    ".aos/interfaces/aos/llm/, status")
    ap.add_argument("--upstream", required=True, help="http(s)://host:port/v1 (e.g. LiteLLM), or the absolute path "
                    "of another dir that declares aos/llm (a lower kernel)")
    ap.add_argument("--model", action="append", required=True, help="allowed model id (repeat)")
    ap.add_argument("--limit", type=int, required=True, help="refuse once used reaches this (a lower value in the "
                    "budget file wins)")
    ap.add_argument("--budget", required=True, help='json file {"used": N, "limit": M}; may outlive one run')
    ap.add_argument("--log", required=True, help="jsonl ledger, one line per request")
    ap.add_argument("--sock-name", default="sock")
    ap.add_argument("--base", default="/v1")
    ap.add_argument("--relay", help="relay script to put out as <dir>/relay (default: relay.js next to this file)")
    ap.add_argument("--no-relay", action="store_true", help="put out no relay")
    ap.add_argument("--description", default="llm kernel: the only way to the model here; counts and caps requests")
    ap.add_argument("--fake", action="store_true", help="answer from a script, never call the upstream")
    ap.add_argument("--fake-script", help='json [{"when": text in the first user message, "steps": [...]}]')
    if len(sys.argv) == 1:
        ap.error("no arguments")
    A = ap.parse_args()
    A.relay_name = None if A.no_relay else "relay"
    A.up_dir = None
    if A.upstream.startswith(("http://", "https://")):
        A.upstream_desc = "fake" if A.fake else A.upstream
    elif os.path.isabs(A.upstream):
        A.up_dir = A.upstream
        A.upstream_desc = "fake" if A.fake else "kernel " + A.upstream
        if not A.fake:
            try:
                lower = read_decl(A.up_dir)
            except ValueError as e:
                fail("UpstreamBad", str(e), 2)
            missing = [m for m in A.model if lower["models"] and m not in lower["models"]]
            if missing:
                warn("the lower kernel does not take %s (it takes %s); those requests will be refused below" % (
                    ", ".join(missing), ", ".join(lower["models"])))
    else:
        fail("ArgumentsBad", "--upstream %r is neither an http(s) URL nor an absolute path" % A.upstream, 2)
    A.script = []
    if A.fake_script:
        with open(A.fake_script) as f:
            A.script = json.load(f)
    os.makedirs(A.dir, exist_ok=True)
    b = budget_read()
    b["limit"] = min(b.get("limit", A.limit), A.limit)
    budget_write(b)
    place_relay()
    declare()
    status_write(b)
    sp = os.path.join(A.dir, A.sock_name)
    if os.path.lexists(sp):
        os.unlink(sp)
    srv = Server(sp, Handler)
    print("%s: listening on %s (upstream %s); budget %d of %d used; models %s" % (
        PROG, sp, A.upstream_desc, b["used"], b["limit"], ",".join(A.model)), flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
