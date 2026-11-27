#!/usr/bin/env python3
"""llm kernel for mini (nests): keeps an OpenAI-style HTTP proxy on a unix socket running in its own layer (counts and caps requests, only the listed models, upstream = a URL, the outer llm kernel, or a scripted fake brain), declares aos/llm with a relay for the inner layers, hides its budget and ledger from them, and runs the next layer; the agent reaches the brain through the socket without any network."""

import http.client
import json
import os
import re
import shutil
import signal
import socket
import socketserver
import struct
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fake_brain  # noqa: E402
import nest  # noqa: E402

PROG = "llm-kernel"
HERE = os.path.dirname(os.path.abspath(__file__))
DECL = os.path.join(".aos", "interfaces", "aos", "llm")
LOCK = threading.Lock()
K = None  # this kernel's settings (a SimpleNamespace-like object)


class Settings:
    pass


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write_atomic(path, text, mode=0o644):
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path) + ".tmp")
    with open(tmp, "w") as f:
        f.write(text)
    os.chmod(tmp, mode)
    os.replace(tmp, path)


# ------------------------------------------------------------ budget, status, ledger (the budget and the ledger live
# in the state folder, which the inner layers cannot see)

def budget_read():
    try:
        with open(K.budget) as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {"used": 0, "limit": K.limit}


def budget_write(b):
    write_atomic(K.budget, json.dumps(b) + "\n", 0o600)


def status_write(b):
    write_atomic(K.status, "requests_used: %d\nrequests_limit: %d\nmodels: %s\nupstream: %s\n" % (
        b["used"], b["limit"], " ".join(K.models), K.upstream_desc))


def ledger(rec):
    rec["at"] = now()
    with open(K.ledger, "a") as f:
        f.write(json.dumps(rec) + "\n")
    K.counts[rec["result"]] = K.counts.get(rec["result"], 0) + 1


# ------------------------------------------------------------ an aos/llm declaration (the outer kernel's, or ours)

def read_decl(d):
    """The aos/llm declaration in dir d as a dict (sock is absolute), or raise ValueError saying what is wrong."""
    out = {}
    for k in ("kind", "path", "protocol", "api", "base"):
        try:
            with open(os.path.join(d, DECL, k)) as f:
                out[k] = f.read().strip()
        except OSError as e:
            raise ValueError("%s does not declare aos/llm (%s: %s)" % (d, os.path.join(DECL, k), e.strerror))
    for k, v in {"kind": "socket", "protocol": "http/1.1", "api": "openai-completions"}.items():
        if out[k] != v:
            raise ValueError("%s declares aos/llm %s %r, this kernel speaks only %r" % (d, k, out[k], v))
    for k in ("models", "limit"):
        try:
            with open(os.path.join(d, DECL, k)) as f:
                out[k] = f.read().split()
        except OSError:
            out[k] = []
    out["sock"] = os.path.join(d, out["path"])  # an absolute path stays as it is
    return out


# ------------------------------------------------------------ upstream: an http URL, the outer llm kernel, or fake

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
    if K.up_dir:
        d = read_decl(K.up_dir)  # read each time, like pi-sandbox's kernel
        conn, path = UnixHTTPConnection(d["sock"], 300), d["base"].rstrip("/") + "/chat/completions"
    else:
        u = urllib.parse.urlsplit(K.upstream)
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


# ------------------------------------------------------------ http on the unix socket (as in pi-sandbox's kernel;
# here the fake brain counts too, so a used-up budget can be tried without a model)

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
        if self.path.rstrip("/") == K.base + "/models":
            data = [{"id": m, "object": "model", "owned_by": "llm-kernel"} for m in K.models]
            return self.reply(200, "application/json", json.dumps({"object": "list", "data": data}).encode())
        self.error(404, "llm kernel: only GET %s/models and POST %s/chat/completions" % (K.base, K.base))

    def do_POST(self):
        pid = self.peer_pid()
        if self.path.split("?")[0] != K.base + "/chat/completions":
            return self.error(404, "llm kernel: only POST %s/chat/completions" % K.base)
        raw = self.read_body()
        try:
            req = json.loads(raw)
        except ValueError:
            return self.error(400, "llm kernel: body is not JSON")
        model = req.get("model")
        if model not in K.models:
            ledger({"result": "refused", "why": "model", "model": model, "peer_pid": pid})
            return self.error(403, "llm kernel: model %r is not allowed (allowed: %s)" % (model, ", ".join(K.models)))
        with LOCK:  # count before sending, so a crash in the middle still counts
            b = budget_read()
            if b["used"] >= b["limit"]:
                ledger({"result": "refused", "why": "budget", "model": model, "peer_pid": pid, "used": b["used"]})
                status_write(b)
                return self.error(429, "llm kernel: request budget used up (%d of %d)" % (b["used"], b["limit"]))
            b["used"] += 1
            budget_write(b)
            n = b["used"]
            status_write(b)
        t0 = time.monotonic()
        if K.fake:
            (ctype, body), code = fake_brain.body(K.script, model, req), 200
        else:
            try:
                code, ctype, body = upstream_post(raw, self.headers.get("Accept", "*/*"))
            except (OSError, ValueError, http.client.HTTPException) as e:
                ledger({"result": "upstream_error", "n": n, "model": model, "peer_pid": pid, "error": str(e)})
                return self.error(502, "llm kernel: upstream: %s" % e)
        ledger({"result": "fake" if K.fake else "sent", "n": n, "model": model, "peer_pid": pid, "status": code,
                "stream": bool(req.get("stream")), "messages": len(req.get("messages", [])),
                "tools": len(req.get("tools", []) or []), "usage": sse_usage(body), "bytes": len(body),
                "seconds": round(time.monotonic() - t0, 2)})
        self.reply(code, ctype, body)


class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


# ------------------------------------------------------------ setting up the layer

def load(opts, cfg, outer):
    bad = set(cfg) - {"models", "limit", "upstream", "fake_script", "state", "description"}
    if bad:
        raise ValueError("unknown keys %s (known: models, limit, upstream, fake_script, state)" % ", ".join(sorted(bad)))
    k = Settings()
    k.name = opts["name"]
    k.models = cfg.get("models")
    if isinstance(k.models, str):
        k.models = [k.models]
    if not k.models or not all(isinstance(m, str) and m for m in k.models):
        raise ValueError("models: want a non-empty list of model ids")
    k.limit = cfg.get("limit")
    if not isinstance(k.limit, int) or k.limit < 0:
        raise ValueError("limit: want how many requests (an integer >= 0)")
    k.base = "/v1"
    k.script = cfg.get("fake_script") or []
    if not isinstance(k.script, list):
        raise ValueError("fake_script: want a list of {\"when\": ..., \"steps\": [...]}")
    up = cfg.get("upstream")
    k.fake, k.up_dir, k.upstream, warns = up == "fake", None, None, []
    has_outer_llm = nest.declared(outer, "llm")
    has_outer_net = nest.declared(outer, "net")
    if up == "fake":
        k.upstream_desc = "fake"
    elif up in (None, "", "outer"):
        if not has_outer_llm:
            raise ValueError("no upstream given and no outer llm kernel to use (want \"fake\", an http(s) URL, the "
                             "path of a folder that declares aos/llm, or an outer llm kernel)")
        k.up_dir, k.upstream_desc = outer, "outer llm kernel"
    elif re.match(r"^https?://", str(up)):
        k.upstream = str(up)
        u = urllib.parse.urlsplit(k.upstream)
        if has_outer_net and u.hostname in ("127.0.0.1", "localhost"):
            # inside a net kernel "this machine" is the outer kernel's host_addr (as with the net kernel's host_ports)
            addr = nest.decl_read(outer, "net", "host_addr", "")
            if not addr:
                raise ValueError("upstream %s: the outer net kernel gives no way to the machine (no host_addr)" % up)
            port = u.port or (443 if u.scheme == "https" else 80)
            if "tcp %d" % port not in nest.decl_read(outer, "net", "host_ports", "").split("\n"):
                warns.append("upstream %s: the outer net kernel does not let host port %d through; requests will "
                             "fail" % (up, port))
            k.upstream = urllib.parse.urlunsplit((u.scheme, "%s:%d" % (addr, port), u.path, u.query, u.fragment))
        if has_outer_llm:
            warns.append("upstream %s goes around the outer llm kernel (its count does not see these requests)" % up)
        k.upstream_desc = k.upstream
    elif os.path.isabs(str(up)):
        k.up_dir, k.upstream_desc = str(up), "kernel " + str(up)
    else:
        raise ValueError("upstream %r: want \"fake\", an http(s) URL, an absolute folder, or leave it out to use the "
                         "outer llm kernel" % up)
    if k.up_dir:
        lower = read_decl(k.up_dir)
        missing = [m for m in k.models if lower["models"] and m not in lower["models"]]
        if missing:
            warns.append("the upstream llm kernel does not take %s (it takes %s); those requests will be refused "
                         "there" % (", ".join(missing), ", ".join(lower["models"])))
        if lower["limit"] and k.limit > int(lower["limit"][0]):
            warns.append("limit %d is more than the upstream llm kernel's %s; it refuses first" % (
                k.limit, lower["limit"][0]))
    k.state = cfg.get("state")
    if k.state:
        k.state = os.path.abspath(os.path.expanduser(str(k.state).replace("{name}", k.name.replace("/", "-"))))
    k.cut_net = has_outer_net  # see stage1
    return k, warns


def declare(env):
    files = {
        "kind": "socket",
        "path": K.sock,                 # absolute: inner layers get a copy of this folder elsewhere
        "protocol": "http/1.1",
        "api": "openai-completions",    # POST <base>/chat/completions
        "base": K.base,
        "models": "\n".join(K.models),  # others get 403
        "limit": str(K.limit),          # requests; then 429
        "status": K.status,             # requests_used / requests_limit, rewritten after each request
        "relay": "%s node script: node %s [--llm DIR] [--port N] [-- CMD ARGS...]; DIR defaults to $AOS_ENV, N to "
                 "8787; listens on 127.0.0.1:N, joins each connection to the socket, runs CMD and exits with its "
                 "code" % (K.relay, K.relay),
        "network": ("cut: an outer net kernel gives this layer a network; the layers inside get their own, empty "
                    "one (only lo), so they reach the model only through the socket") if K.cut_net else
                   ("unchanged: the proxy uses this layer's network; the agent gets its own (empty, or a net kernel's "
                    "further in), not this one"),
    }
    nest.declare(env, "llm", files, "llm kernel: the only way to the model here (HTTP on a unix socket); counts and "
                 "caps requests, only the listed models")
    if K.cut_net:  # what the inner layers get is an empty network: no aos/net any more
        shutil.rmtree(os.path.join(env, ".aos", "interfaces", "aos", "net"), ignore_errors=True)


def stage1(opts, cfg, nxt):
    global K
    outer = nest.env_outer()
    try:
        K, warns = load(opts, cfg, outer)
    except (ValueError, TypeError) as e:
        nest.fail(PROG, "ConfigBad", "%s: %s" % (opts["name"], e), 2)
    for w in warns:
        nest.warn(PROG, "%s: %s" % (opts["name"], w))
    env = nest.new_env("llm", opts["name"])
    if not K.state:  # this run only: next to our folder, removed with the run folder
        K.state = env + ".state"
    os.makedirs(K.state, mode=0o700, exist_ok=True)
    K.budget, K.ledger = os.path.join(K.state, "budget.json"), os.path.join(K.state, "ledger.jsonl")
    K.sock, K.status, K.relay = (os.path.join(env, x) for x in ("sock", "status", "relay"))
    K.counts = {}
    shutil.copyfile(os.path.join(HERE, "relay.js"), K.relay)
    os.chmod(K.relay, 0o755)
    b = budget_read()
    b["limit"] = min(b.get("limit", K.limit), K.limit)
    budget_write(b)
    status_write(b)
    srv = Server(K.sock, Handler)  # listening from here on: early clients wait in the backlog
    os.chmod(K.sock, 0o666)  # a uid kernel further in makes the agent "others"
    declare(env)
    inner_cg = nest.cg_split(PROG, [os.getpid()], "k-llm", "in")
    hide = [K.state]
    if K.up_dir:  # the upstream kernel's socket too: the agent must go through our count, not around it
        hide.append(read_decl(K.up_dir)["sock"])
    argv = ["unshare"] + nest.userns_args() + ["--mount"] + (["--net"] if K.cut_net else []) + ["--"] + \
        nest.py(os.path.abspath(__file__)) + ["--stage2", "--name", opts["name"], "--json",
                                              json.dumps({"hide": hide, "lo": K.cut_net}), "--"] + nxt

    def into_inner_cgroup():  # in the child before exec: a cgroup kernel further in must find itself alone
        if inner_cg:
            nest.cg_move(0, inner_cg)
    box = []
    for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):  # caught, not ignored (see net_kernel.wrapper_main)
        signal.signal(s, lambda sig, _: box and box[0].send_signal(sig))
    try:
        inner = subprocess.Popen(argv, env=dict(os.environ, AOS_ENV=env), preexec_fn=into_inner_cgroup)
    except OSError as e:
        nest.fail(PROG, "StartFailed", "%s: %s" % (argv[0], e.strerror))
    box.append(inner)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    rc = inner.wait()
    srv.shutdown()
    srv.server_close()
    b = budget_read()
    print("%s: %s: %d answered (%s), %d refused, %d upstream errors; %d of %d used" % (
        PROG, K.name, K.counts.get("fake", 0) + K.counts.get("sent", 0), "fake" if K.fake else "sent",
        K.counts.get("refused", 0), K.counts.get("upstream_error", 0), b["used"], b["limit"]),
        file=sys.stderr, flush=True)
    try:
        os.unlink(K.sock)
    except OSError:
        pass
    sys.exit(128 - rc if rc < 0 else rc)


def stage2(opts, cfg, nxt):
    """In the new user and mount (and, inside a net kernel, net) namespace: hide the state folder (budget, ledger)
    under an empty tmpfs and the upstream kernel's socket under /dev/null (the agent, further in, cannot take them
    off: mounts from here are locked there); lo up."""
    if cfg.get("lo"):
        subprocess.run(["ip", "link", "set", "lo", "up"], stderr=subprocess.DEVNULL)
    for p in cfg.get("hide", []):
        try:
            if os.path.isdir(p):
                nest.mount("tmpfs", p, "tmpfs", nest.MS_NOSUID | nest.MS_NODEV | nest.MS_NOEXEC, "size=4k,mode=0")
            elif os.path.lexists(p):
                nest.mount("/dev/null", p, None, nest.MS_BIND)
        except OSError as e:
            nest.fail(PROG, "HideFailed", "%s: %s" % (p, e))
    try:
        os.execvp(nxt[0], nxt)
    except OSError as e:
        nest.fail(PROG, "ExecFailed", "%s: %s" % (nxt[0], e.strerror), 127)


def main():
    opts, cfg, nxt = nest.parse(PROG, sys.argv[1:])
    if opts.get("stage2"):
        return stage2(opts, cfg, nxt)
    stage1(opts, cfg, nxt)


if __name__ == "__main__":
    main()
