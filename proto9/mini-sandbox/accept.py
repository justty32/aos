#!/usr/bin/env python3
"""Acceptance run for mini and the net kernel: cpu, mem, pids, -C, process view, the allow list, host services, rates, quota, the status file, rules out of reach, nesting, uid N, what is left open (info), pi --fake through the net kernel, and nothing left over afterwards."""

import argparse
import http.server
import json
import os
import shutil
import socket
import socketserver
import subprocess
import sys
import threading
import time

sys.dont_write_bytecode = True  # keep the repo free of __pycache__
HERE = os.path.dirname(os.path.abspath(__file__))
PI_SANDBOX = os.path.join(os.path.dirname(HERE), "pi-sandbox")
BASE = os.path.expanduser("~/.aos/scratch/proto9-mini-1127/accept")
DEFAULT_PASTA = os.path.expanduser("~/.aos/scratch/proto9-mini-1127/passt/pasta")
MINI, NETK, PROBE = (os.path.join(HERE, f) for f in ("mini.py", "net_kernel.py", "probe.py"))
HOST_ADDR = "169.254.77.1"
DOWN, UP, QUOTA = "16mbit", "8mbit", 12_000_000    # 2 MB/s down, 1 MB/s up
RESULTS = []


def log(*a):
    print(*a, flush=True)


def record(name, ok, detail, must=True):
    """ok: True/False; info lines (must=False) are printed but never fail the run."""
    tag = ("PASS" if ok else "FAIL") if must else "info"
    RESULTS.append((name, tag))
    log("%-26s %s  %s" % (name, tag, detail))


def last_json(text):
    for line in reversed(text.strip().splitlines()):
        try:
            return json.loads(line)
        except ValueError:
            continue
    return {}


def write_json(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f)


# ---------------------------------------------------------------- outside: test servers, the fake brain, kernels

class Bytes(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        n = int(self.path.rsplit("/", 1)[-1]) if self.path.startswith("/bytes/") else 2
        self.send_response(200)
        self.send_header("Content-Length", str(n))
        self.end_headers()
        block = b"d" * 65536
        try:
            while n > 0:
                k = min(n, len(block))
                self.wfile.write(block[:k])
                n -= k
        except OSError:
            pass

    def do_POST(self):
        n, left = 0, int(self.headers.get("Content-Length", "0"))
        while left > 0:
            c = self.rfile.read(min(left, 65536))
            if not c:
                break
            n += len(c)
            left -= len(c)
        body = str(n).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def start_server():
    s = Server(("127.0.0.1", 0), Bytes)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


class Bridge:
    """127.0.0.1:PORT on the host -> the fake brain's unix socket (pi only speaks http to an address)."""

    def __init__(self, sock_path):
        self.sock_path = sock_path
        self.l = socket.socket()
        self.l.bind(("127.0.0.1", 0))
        self.l.listen(16)
        self.port = self.l.getsockname()[1]
        threading.Thread(target=self.loop, daemon=True).start()

    def loop(self):
        while True:
            try:
                c, _ = self.l.accept()
            except OSError:
                return
            u = socket.socket(socket.AF_UNIX)
            try:
                u.connect(self.sock_path)
            except OSError:
                c.close()
                continue
            for a, b in ((c, u), (u, c)):
                threading.Thread(target=self.pipe, args=(a, b), daemon=True).start()

    @staticmethod
    def pipe(a, b):
        try:
            while True:
                d = a.recv(65536)
                if not d:
                    break
                b.sendall(d)
        except OSError:
            pass
        for s in (a, b):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def close(self):
        self.l.close()


class NetKernel:
    def __init__(self, name, cfg, pasta):
        self.dir = os.path.join(BASE, name)
        self.cfgp = os.path.join(BASE, name + ".json")
        write_json(self.cfgp, cfg)
        self.log = open(os.path.join(BASE, name + ".log"), "w")
        self.p = subprocess.Popen([sys.executable, NETK, "--dir", self.dir, "--config", self.cfgp, "--pasta", pasta],
                                  stdout=self.log, stderr=subprocess.STDOUT)
        end = time.monotonic() + 15
        while not os.path.exists(os.path.join(self.dir, "ctl")):
            if self.p.poll() is not None or time.monotonic() > end:
                raise RuntimeError("net kernel %s did not start: %s" % (name, open(self.log.name).read()[-500:]))
            time.sleep(0.05)

    def status(self):
        time.sleep(1.3)  # the status file is rewritten every second
        out = {}
        for line in open(os.path.join(self.dir, "status")):
            k, _, v = line.partition(": ")
            out[k] = v.strip()
        return out

    def decl(self, key):
        return open(os.path.join(self.dir, ".aos", "interfaces", "aos", "net", key)).read().strip()

    def stop(self):
        if self.p.poll() is None:
            self.p.terminate()
            try:
                self.p.wait(10)
            except subprocess.TimeoutExpired:
                self.p.kill()
                self.p.wait()
        self.log.close()


# ---------------------------------------------------------------- running mini

class Run:
    def __init__(self, rc, out, err, unit):
        self.rc, self.out, self.err, self.unit = rc, out, err, unit
        self.j = last_json(out)


def mini(name, argv, net="none", uid=0, cpu=None, mem=None, pids=None, env=None, cwd=None, timeout=60,
         while_running=None):
    cfg = {"name": name, "argv": argv, "net": net, "uid": uid, "cwd": cwd or BASE,
           "env": env or {"PATH": "/usr/bin:/bin", "HOME": os.environ["HOME"], "LANG": "C.UTF-8"}}
    for k, v in (("cpu", cpu), ("mem", mem), ("pids", pids)):
        if v is not None:
            cfg[k] = v
    path = os.path.join(BASE, "cfg-%s.json" % name)
    write_json(path, cfg)
    p = subprocess.Popen([sys.executable, MINI, path], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True)  # pi reads a piped stdin as more prompt, so give it none
    unit = "mini-%s-%d.scope" % (name, p.pid)
    seen = while_running(p, unit) if while_running else None
    try:
        out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.terminate()
        out, err = p.communicate()
    r = Run(p.returncode, out, err, unit)
    r.seen = seen
    return r


def probe(*a):
    return [sys.executable, "-I", PROBE] + [str(x) for x in a]


# ---------------------------------------------------------------- what is left over

def our_procs():
    """pid -> cmdline of processes of ours (you, or your subordinate ids) that belong to this run."""
    marks = (HERE, BASE, "pasta", "passt", "llm_kernel.py", "mini-")
    out = {}
    for p in os.listdir("/proc"):
        if not p.isdigit() or int(p) == os.getpid():
            continue
        try:
            st = os.stat("/proc/" + p)
            cmd = open("/proc/%s/cmdline" % p, "rb").read().replace(b"\0", b" ").decode(errors="replace")
        except OSError:
            continue
        shell = os.path.basename(cmd.split(" ", 1)[0]) in ("zsh", "bash")  # e.g. the shell that started us
        if (st.st_uid == os.getuid() or 100000 <= st.st_uid < 165536) and any(m in cmd for m in marks) and not shell:
            out[int(p)] = cmd.strip()[:120]
    return out


def our_netns():
    """net namespaces held by processes of this run (an unnamed netns lives only while someone holds it)."""
    out = set()
    for p in our_procs():
        try:
            out.add(os.readlink("/proc/%d/ns/net" % p))
        except OSError:
            pass
    return out


def our_units():
    r = subprocess.run(["systemctl", "--user", "list-units", "--all", "--plain", "--no-legend", "mini-*"],
                       capture_output=True, text=True)
    return sorted(l.split()[0] for l in r.stdout.splitlines() if l.strip())


def runtime_dirs():
    rd = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
    return sorted(d for d in os.listdir(rd) if d.startswith("aos-mini-"))


def snapshot():
    return {"procs": our_procs(), "netns": our_netns(), "units": our_units(), "rundirs": runtime_dirs()}


# ---------------------------------------------------------------- the checks

def check_base():
    log("\n== base: cpu 20%, mem 100M, pids 30, net none")
    lim = {"cpu": "20%", "mem": "100M", "pids": 30}
    r = mini("cpu", probe("cpu", 3), **lim)
    ratio = r.j.get("ratio", 0)
    record("cpu_quota", 0.15 <= ratio <= 0.25, "cpu/wall %s (%s)" % (ratio, r.j))
    r = mini("mem", probe("mem", 300), **lim)
    record("mem_oom", r.rc == 137, "exit %s after %s" % (r.rc, (r.err.strip().splitlines() or ["-"])[-1]))
    r = mini("pids", probe("pids", 100), **lim)
    record("pids_max", r.j.get("error") is not None and r.j.get("forked", 99) < 30,
           "forked %s then %s" % (r.j.get("forked"), r.j.get("error")))
    r = mini("cgns", ["sh", "-c", 'exec python3 -I %s cgroup "$MINI_UNIT"' % PROBE], **lim)
    j = r.j
    record("cgroup_ns_C", j.get("self_cgroup") == "0::/" and bool(j.get("scope_dir"))
           and not str(j.get("raise_mem", "ok")).startswith("ok") and not str(j.get("move_out", "ok")).startswith("ok"),
           "self %s; raise memory.max: %s; move out: %s" % (j.get("self_cgroup"), j.get("raise_mem"), j.get("move_out")))
    r = mini("procs", probe("procs", os.getpid()), **lim)
    record("no_host_procs", r.j.get("count", 99) < 10 and r.j.get("sees_host_pid") is False,
           "sees %s pids %s; sees accept's pid %s: %s" % (r.j.get("count"), r.j.get("pids"), os.getpid(),
                                                          r.j.get("sees_host_pid")))
    r = mini("nonet", ["sh", "-c", "python3 -I %s ns; python3 -I %s tcp 1.1.1.1 443 2" % (PROBE, PROBE)])
    first = last_json(r.out.strip().splitlines()[0]) if r.out.strip() else {}
    record("no_net_only_lo", first.get("ifaces") == ["lo"] and r.j.get("connect") != "ok",
           "ifaces %s; 1.1.1.1:443 %s" % (first.get("ifaces"), r.j.get("connect")))
    r = mini("exit", ["sh", "-c", "exit 7"])
    record("exit_code_passed", r.rc == 7, "exit %s" % r.rc)


def host_online():
    r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "5", "https://1.1.1.1/"],
                       capture_output=True, text=True)
    return r.stdout.strip() not in ("", "000")


def gateway():
    r = subprocess.run(["ip", "-j", "route", "show", "default"], capture_output=True, text=True)
    try:
        return json.loads(r.stdout)[0]["gateway"]
    except (ValueError, IndexError, KeyError):
        return None


def check_net(pasta, online, s1, s2):
    log("\n== net kernel K1: allow tcp 1.1.1.1:443; host ports %d (test server); down %s up %s quota %d bytes"
        % (s1, DOWN, UP, QUOTA))
    k = NetKernel("k1", {"allow": [{"to": "1.1.1.1", "port": 443}], "host_ports": [s1], "down": DOWN, "up": UP,
                         "quota": QUOTA}, pasta)
    try:
        decl = {x: k.decl(x) for x in ("kind", "allow", "host_ports", "down", "up", "quota")}
        record("declaration", decl == {"kind": "veth", "allow": "tcp 1.1.1.1/32 443", "host_ports": "tcp %d" % s1,
                                       "down": DOWN, "up": UP, "quota": str(QUOTA)}, json.dumps(decl))
        r = mini("netns", probe("ns"), net=k.dir)
        record("net_ifaces", r.j.get("ifaces") == ["eth0", "lo"], "ifaces %s" % r.j.get("ifaces"))
        if online:
            r = mini("allow1", probe("curl", "https://1.1.1.1/", 8), net=k.dir)
            record("allowed_external_open", r.j.get("code") not in (None, "", "000"), "https://1.1.1.1/ -> %s" % r.j)
        else:
            record("allowed_external_open", True, "host has no internet; skipped (the test server below stands in)",
                   must=False)
        for name, url in (("denied_external_8888", "https://8.8.8.8/"), ("denied_external_port80", "http://1.1.1.1/")):
            r = mini(name, probe("curl", url, 4), net=k.dir)
            record(name, r.j.get("code") == "000", "%s -> %s%s" % (url, r.j, "" if online else " (host offline too)"))
        r = mini("hostok", probe("tcp", HOST_ADDR, s1), net=k.dir)
        record("allowed_host_port_open", r.j.get("connect") == "ok", "%s:%d (host 127.0.0.1:%d) %s" % (
            HOST_ADDR, s1, s1, r.j))
        gw = gateway()
        tries = [("host_port_not_listed", HOST_ADDR, s2), ("litellm_4000_closed", HOST_ADDR, 4000),
                 ("own_lo_is_not_host", "127.0.0.1", s1), ("outer_ns_closed", "10.77.0.1", 22)]
        if gw:
            tries.append(("gateway_not_host", gw, s1))
        for name, host, port in tries:
            r = mini(name, probe("tcp", host, port, 3), net=k.dir)
            record(name, r.j.get("connect") != "ok", "%s:%s %s" % (host, port, r.j))
        r = mini("ctl", probe("ctl", os.path.join(k.dir, "ctl"), 1), net=k.dir)
        ans = r.j.get("answer")
        record("ctl_refused_inside", isinstance(ans, dict) and not ans.get("ok") and "Refused" in ans.get("error", ""),
               "attach from inside: %s" % ans)
        r = mini("flush", ["sh", "-c", "nft flush ruleset; echo nft_rc=$?; tc qdisc del dev eth0 root 2>&1; "
                           "python3 -I %s tcp %s %d 3" % (PROBE, HOST_ADDR, s2)], net=k.dir)
        record("rules_out_of_reach", "nft_rc=0" in r.out and r.j.get("connect") != "ok",
               "nft flush inside rc 0, then %s:%d still %s" % (HOST_ADDR, s2, r.j.get("connect")))
        r = mini("nest", ["sh", "-c", "unshare -Urn sh -c 'id -u; ip -br link' 2>&1"], net=k.dir)
        record("nested_unshare_ok", r.rc == 0 and r.out.startswith("0"), "unshare -Urn inside: rc %s %s" % (
            r.rc, r.out.strip().replace("\n", " | ")))
        uid1_check("uid1_net", net=k.dir, extra="curl -s -o /dev/null -w code=%%{http_code} --max-time 5 http://%s:%d/"
                   % (HOST_ADDR, s1))
        leaks_check(k.dir)

        st0 = k.status()
        r = mini("down", probe("get", HOST_ADDR, s1, 4_000_000, 15), net=k.dir)
        rate = r.j.get("rate", 0)
        record("down_rate", 0.75 * 2e6 <= rate <= 1.25 * 2e6 and r.j.get("bytes") == 4_000_000,
               "4 MB in %ss = %.2f MB/s (set %s = 2.00 MB/s)" % (r.j.get("seconds"), rate / 1e6, DOWN))
        r = mini("up", probe("put", HOST_ADDR, s1, 2_000_000, 15), net=k.dir)
        rate = r.j.get("rate", 0)
        record("up_rate", 0.75 * 1e6 <= rate <= 1.25 * 1e6 and r.j.get("server") == "2000000",
               "2 MB in %ss = %.2f MB/s (set %s = 1.00 MB/s); server read %s" % (
                   r.j.get("seconds"), rate / 1e6, UP, r.j.get("server")))
        st = k.status()
        used, left, total = int(st["quota_used"]), int(st["quota_left"]), int(st["quota_bytes"])
        moved = used - int(st0["quota_used"])
        record("status_matches", total == QUOTA == int(k.decl("quota")) and used + left == total
               and 6_000_000 <= moved <= 6_600_000 and "new_connections" in st.get("host.0", ""),
               "quota_bytes %d = declared %s; used %d + left %d = %d; these 6 MB of payload moved %d bytes "
               "(headers included); host.0: %s" % (total, k.decl("quota"), used, left, used + left, moved,
                                                   st.get("host.0")))
        r = mini("quota", probe("get", HOST_ADDR, s1, 30_000_000, 8), net=k.dir)
        got = r.j.get("bytes", 0)
        r2 = mini("quota2", probe("tcp", HOST_ADDR, s1, 3), net=k.dir)
        st = k.status()
        record("quota_cut", got < 30_000_000 and abs(got - left) < 0.1 * left + 100_000
               and r2.j.get("connect") not in (None, "ok") and int(st["quota_left"]) == 0,
               "asked 30 MB, got %d before the cut (left was %d); next connect %s; status quota_left %s" % (
                   got, left, r2.j.get("connect") or r2.err.strip()[-200:], st["quota_left"]))
    finally:
        k.stop()


def uid1_check(name, net="none", extra=""):
    secret = os.path.join(BASE, "secret600")
    with open(secret, "w") as f:
        f.write("top secret\n")
    os.chmod(secret, 0o600)

    def watch(p, unit):
        seen = set()
        end = time.monotonic() + 6
        while time.monotonic() < end and p.poll() is None:
            for q in os.listdir("/proc"):
                if q.isdigit():
                    try:
                        if unit in open("/proc/%s/cgroup" % q).read():
                            seen.add(os.stat("/proc/" + q).st_uid)
                    except OSError:
                        pass
            time.sleep(0.2)
        return seen
    cmd = "id -u; cat %s 2>&1; %s; sleep 2" % (secret, extra or "true")
    r = mini(name, ["sh", "-c", cmd], net=net, uid=1, cwd="/", while_running=watch)
    lines = r.out.strip().splitlines()
    ok = lines[:1] == ["1"] and "Permission denied" in r.out and 100000 in (r.seen or set())
    if extra:  # uid 1 cannot enter your 700 home, so this one uses curl from /usr, not probe.py
        ok = ok and "code=200" in r.out
    record(name, ok, "inside id -u %s; read 600 file: %s; outside uids in the scope %s%s" % (
        lines[:1], "denied" if "Permission denied" in r.out else "READ", sorted(r.seen or []),
        "; allowed port: %s" % ("open" if "code=200" in r.out else r.out.strip()[-80:]) if extra else ""))


def leaks_check(netdir):
    """Left open on purpose (user 11-27: 3.甲): measure and print, never fail."""
    unit = "mini-leak-%d.service" % os.getpid()
    outfile = os.path.join(BASE, "leak.out")
    env = {"PATH": "/usr/bin:/bin", "HOME": os.environ["HOME"], "XDG_RUNTIME_DIR": os.environ["XDG_RUNTIME_DIR"]}
    if "DBUS_SESSION_BUS_ADDRESS" in os.environ:
        env["DBUS_SESSION_BUS_ADDRESS"] = os.environ["DBUS_SESSION_BUS_ADDRESS"]
    r = mini("leak", probe("leaks", unit, outfile), net=netdir, cpu="20%", mem="100M", pids=30, env=env)
    j = r.j
    end = time.monotonic() + 5
    while time.monotonic() < end and not (os.path.exists(outfile) and len(open(outfile).read().splitlines()) >= 2):
        time.sleep(0.1)
    leak = open(outfile).read().splitlines() if os.path.exists(outfile) else []
    host_net, host_ipc = os.readlink("/proc/self/ns/net"), os.readlink("/proc/self/ns/ipc")
    how = "systemd-run --user: %s; busctl --user StartTransientUnit: %s" % (j.get("systemd_run"), j.get("busctl", "-"))
    if leak:
        record("leak_systemd_user", True, "from inside (%s) started %s: its netns %s (%s; the sandbox's is %s), cgroup "
               "%s (not under the mini scope, so no cpu/mem/pids limit)" % (
                   how, unit, leak[0], "the host's" if leak[0] == host_net else "not the host's", j.get("net"),
                   leak[1][3:]), must=False)
    else:
        record("leak_systemd_user", True, "did not get out: %s" % how, must=False)
    subprocess.run(["systemctl", "--user", "stop", unit], capture_output=True)
    subprocess.run(["systemctl", "--user", "reset-failed", unit], capture_output=True)
    record("leak_ssh", True, "~/.ssh %s; %s" % (j.get("ssh_dir"), j.get("ssh_key", "no id_* key")), must=False)
    record("leak_ipc_shared", True, "ipc ns inside %s, outside %s: %s" % (
        j.get("ipc"), host_ipc, "same" if j.get("ipc") == host_ipc else "different"), must=False)
    record("leak_run_user", True, str(j.get("run_user")), must=False)


def check_nomap(pasta, s1):
    """Without host_ports pasta runs with --no-map-gw: even an allowed gateway:port does not reach the host."""
    gw = gateway()
    if not gw:
        record("default_no_host_map", True, "no default route; skipped", must=False)
        return
    log("\n== net kernel K2: no host ports; allow tcp %s:%d (the gateway, pasta's default host alias)" % (gw, s1))
    k = NetKernel("k2", {"allow": [{"to": gw, "port": s1}, {"to": HOST_ADDR, "port": s1}]}, pasta)
    try:
        for name, host in (("default_no_host_map_gw", gw), ("default_no_host_map_addr", HOST_ADDR)):
            r = mini(name, probe("tcp", host, s1, 3), net=k.dir)
            record(name, r.j.get("connect") != "ok", "%s:%d allowed by nft but pasta maps nothing: %s" % (
                host, s1, r.j))
    finally:
        k.stop()


# ---------------------------------------------------------------- pi --fake through the net kernel

PROJECT = {
    "NOTES.md": "# Notes\n\nThe secret word is: pinecone\n",
    "config.ini": "[app]\nname = demo\nlevel = low\ncolor = blue\n",
    "test_app.py": (
        "import configparser, pathlib\n"
        "c = configparser.ConfigParser()\n"
        "c.read('config.ini')\n"
        "assert c['app']['level'] == 'high', 'config.ini: level is %s, want high' % c['app']['level']\n"
        "h = pathlib.Path('hello.txt')\n"
        "assert h.exists() and h.read_text().strip() == 'pinecone', 'hello.txt is wrong'\n"
        "print('ALL TESTS PASSED')\n"),
}
TASK = ("Do these four steps with your tools, one tool per step: 1) read NOTES.md 2) write hello.txt with the secret "
        "word 3) edit config.ini: level = low -> level = high 4) bash: python3 test_app.py")
FAKE_SCRIPT = [{"when": "four steps", "steps": [  # same steps as pi-sandbox/accept.py
    {"tool": "read", "args": {"path": "NOTES.md"}},
    {"tool": "write", "args": {"path": "hello.txt", "content": "pinecone\n"}},
    {"tool": "edit", "args": {"path": "config.ini", "edits": [{"oldText": "level = low", "newText": "level = high"}]}},
    {"tool": "bash", "args": {"command": "python3 test_app.py"}},
    {"text": "FAKE: ran the four steps"}]}]
MODEL = "fake-model"


def check_pi(pasta):
    sys.path.insert(0, PI_SANDBOX)
    import aos_pi
    node, pkg = aos_pi.find_node()
    cli = os.path.join(pkg, "dist", "bundle", "cli.js")
    if not (os.path.exists(node) and os.path.exists(cli)):
        record("pi_fake", True, "no node/pi here (%s, %s); skipped" % (node, cli), must=False)
        return
    log("\n== pi --fake: fake brain outside (llm_kernel.py --fake behind 127.0.0.1:PORT), net kernel K3 lets only "
        "that port through")
    brain, state, work, home = (os.path.join(BASE, x) for x in ("brain", "brain-state", "work", "pihome"))
    for d in (state, work):
        os.makedirs(d)
    for f, t in PROJECT.items():
        with open(os.path.join(work, f), "w") as fh:
            fh.write(t)
    write_json(os.path.join(BASE, "fake_script.json"), FAKE_SCRIPT)
    blog = open(os.path.join(BASE, "brain.log"), "w")
    bp = subprocess.Popen([sys.executable, os.path.join(PI_SANDBOX, "llm_kernel.py"), "--dir", brain,
                           "--upstream", "http://unused.invalid/v1", "--model", MODEL, "--limit", "50",
                           "--budget", os.path.join(state, "budget.json"), "--log", os.path.join(state, "ledger.jsonl"),
                           "--fake", "--fake-script", os.path.join(BASE, "fake_script.json"), "--no-relay"],
                          stdout=blog, stderr=subprocess.STDOUT)
    bridge = k = None
    try:
        end = time.monotonic() + 10
        while not os.path.exists(os.path.join(brain, "sock")) and time.monotonic() < end:
            time.sleep(0.05)
        bridge = Bridge(os.path.join(brain, "sock"))
        k = NetKernel("k3", {"host_ports": [bridge.port]}, pasta)
        models = {"providers": {"aosllm": {
            "name": "fake brain via the net kernel", "baseUrl": "http://%s:%d/v1" % (HOST_ADDR, bridge.port),
            "api": "openai-completions", "apiKey": "fake-key",
            "compat": {"supportsDeveloperRole": False, "supportsStore": False, "maxTokensField": "max_tokens"},
            "models": [{"id": MODEL, "name": MODEL, "contextWindow": 200000, "maxTokens": 4096,
                        "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0}}]}}}
        os.makedirs(os.path.join(home, ".pi", "agent"))
        write_json(os.path.join(home, ".pi", "agent", "models.json"), models)
        write_json(os.path.join(home, ".pi", "agent", "settings.json"),
                   {"defaultProvider": "aosllm", "defaultModel": MODEL, "retry": {"baseDelayMs": 500}})
        env = {"PATH": "%s:/usr/bin:/bin" % os.path.dirname(node), "HOME": home, "LANG": "C.UTF-8",
               "PI_OFFLINE": "1", "PI_SKIP_VERSION_CHECK": "1", "PI_TELEMETRY": "0"}
        t0 = time.monotonic()
        r = mini("pi", [node, cli, "--mode", "json", "--thinking", "off", "--provider", "aosllm", "--model", MODEL,
                        TASK], net=k.dir, mem="2G", pids=512, env=env, cwd=work, timeout=180)
        sec = round(time.monotonic() - t0, 1)
        with open(os.path.join(BASE, "pi.out"), "w") as f:
            f.write(r.out)
        events = []
        for line in r.out.splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                pass
        o = aos_pi.pi_outcome(events)
        ledger = [json.loads(l) for l in open(os.path.join(state, "ledger.jsonl"))] if os.path.exists(
            os.path.join(state, "ledger.jsonl")) else []
        hello = open(os.path.join(work, "hello.txt")).read().strip() if os.path.exists(
            os.path.join(work, "hello.txt")) else None
        level = "level = high" in open(os.path.join(work, "config.ini")).read()
        st = k.status()
        tools = [t for t, ok in o["tools"] if ok]
        record("pi_fake", o["done"] and tools == ["read", "write", "edit", "bash"] and hello == "pinecone" and level
               and len(ledger) == o["turns"],
               "%s in %ss (exit %s), stopReason %s, tools %s, hello.txt %r, config level high %s, %d LLM turns = "
               "%d brain ledger lines; final %r; net kernel host.0 %s" % (
                   "DONE" if o["done"] else "NOT DONE", sec, r.rc, o["stop_reason"], o["tools"], hello, level,
                   o["turns"], len(ledger), o["final"], st.get("host.0")))
        if not o["done"]:
            log(r.err[-800:])
    finally:
        if k:
            k.stop()
        if bridge:
            bridge.close()
        bp.terminate()
        bp.wait()
        blog.close()


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Acceptance run for mini and the net kernel (PASS/FAIL/info lines).")
    ap.add_argument("--pasta", help="pasta binary (default: on PATH, else %s)" % DEFAULT_PASTA)
    ap.add_argument("--no-pi", action="store_true", help="skip pi --fake")
    ap.add_argument("--keep", action="store_true", help="keep %s afterwards" % BASE)
    a = ap.parse_args()
    pasta = a.pasta or shutil.which("pasta") or DEFAULT_PASTA
    if not os.access(pasta, os.X_OK):
        sys.exit("accept: error: PastaMissing no pasta at %s (install passt, or --pasta PATH)" % pasta)
    shutil.rmtree(BASE, ignore_errors=True)
    os.makedirs(BASE)
    before = snapshot()
    online = host_online()
    log("pasta %s; host online: %s; LiteLLM 127.0.0.1:4000 on the host: %s" % (
        pasta, online, "listening" if socket.socket().connect_ex(("127.0.0.1", 4000)) == 0 else "not listening"))
    s1, s2 = start_server(), start_server()
    p1, p2 = s1.server_address[1], s2.server_address[1]
    log("test servers on the host: 127.0.0.1:%d (to be allowed), 127.0.0.1:%d (never allowed)" % (p1, p2))
    t0 = time.monotonic()
    try:
        check_base()
        check_net(pasta, online, p1, p2)
        log("\n== uid 1 without a net kernel")
        uid1_check("uid1_none")
        check_nomap(pasta, p1)
        if not a.no_pi:
            check_pi(pasta)
    finally:
        for s in (s1, s2):
            s.shutdown()
            s.server_close()
    time.sleep(1)
    after = snapshot()
    left = {k: (sorted(set(after[k]) - set(before[k])) if k != "procs" else
                {p: c for p, c in after[k].items() if p not in before[k]}) for k in after}
    servers_open = [p for p in (p1, p2) if socket.socket().connect_ex(("127.0.0.1", p)) == 0]
    clean = not any(left.values()) and not servers_open
    record("cleanup", clean, "left over: %s; test servers still open: %s" % (
        {k: v for k, v in left.items() if v} or "nothing", servers_open or "none"))
    fails = [n for n, t in RESULTS if t == "FAIL"]
    log("\nSUMMARY %s (%d PASS, %d FAIL, %d info, %.0fs)%s" % (
        "ok" if not fails else "FAILED", sum(t == "PASS" for _, t in RESULTS), len(fails),
        sum(t == "info" for _, t in RESULTS), time.monotonic() - t0, ": " + ", ".join(fails) if fails else ""))
    if not a.keep and not fails:
        shutil.rmtree(BASE, ignore_errors=True)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
