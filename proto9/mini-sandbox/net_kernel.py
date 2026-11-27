#!/usr/bin/env python3
"""net kernel for mini: holds an outer network namespace that pasta connects to the outside, keeps the ip/port allow list, the quota (nft) and the up/down rates (tc) there, and pulls a veth into a sandbox's own netns (on request through ctl, or, as a nesting wrapper, into the netns it starts the next layer in); declares aos/net (locked read-only for the inner layer) and keeps a status file with the counters."""

import argparse
import ipaddress
import json
import os
import pwd
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
import types

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nest  # noqa: E402

PROG = "net-kernel"
HERE = os.path.dirname(os.path.abspath(__file__))
DECL = os.path.join(".aos", "interfaces", "aos", "net")
TAP = "aosnet0"          # pasta's tap in the outer netns
VETH = "vp"              # outer ends are vp0, vp1, ...; the sandbox end is always eth0
DEFAULTS = {"allow": [], "host_ports": [], "down": None, "up": None, "quota": None, "subnet": "10.77.0.0/16",
            "host_addr": "169.254.77.1", "max_attach": 1, "status_interval": 1.0, "burst": None}
RATE = re.compile(r"^(\d+(?:\.\d+)?)(bit|kbit|mbit|gbit)$")
UNITS = {"bit": 1, "kbit": 1e3, "mbit": 1e6, "gbit": 1e9}
SIZE = re.compile(r"^(\d+)\s*(b|bytes|kb|kbytes|mb|mbytes|gb|gbytes)?$", re.I)
SIZES = {"b": 1, "bytes": 1, "kb": 10**3, "kbytes": 10**3, "mb": 10**6, "mbytes": 10**6, "gb": 10**9, "gbytes": 10**9}


def fail(code, msg, exit_code=1):
    sys.stdout.flush()
    print("%s: error: %s %s" % (PROG, code, msg), file=sys.stderr, flush=True)
    sys.exit(exit_code)


def warn(msg):
    print("%s: warning: %s" % (PROG, msg), file=sys.stderr, flush=True)


def write_atomic(path, text):
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path) + ".tmp")
    with open(tmp, "w") as f:
        f.write(text)
    os.replace(tmp, path)


# ------------------------------------------------------------ the config

def rate_bits(s):
    m = RATE.match(str(s))
    if not m:
        raise ValueError("rate %r: want a number and bit|kbit|mbit|gbit, e.g. 16mbit" % s)
    return float(m.group(1)) * UNITS[m.group(2)]


def size_bytes(s):
    if isinstance(s, int):
        return s
    m = SIZE.match(str(s).strip())
    if not m:
        raise ValueError("size %r: want bytes or a number with kb|mb|gb (1000-based)" % s)
    return int(m.group(1)) * SIZES[(m.group(2) or "b").lower()]


def port_spec(p):
    """443 or "8000-8100" -> nft text."""
    if isinstance(p, int) and 0 < p < 65536:
        return str(p)
    m = re.match(r"^(\d+)-(\d+)$", str(p))
    if m and 0 < int(m.group(1)) <= int(m.group(2)) < 65536:
        return "%s-%s" % m.groups()
    raise ValueError("port %r: want 1..65535 or LO-HI" % p)


def load_config(path):
    with open(path) as f:
        return load_config_dict(json.load(f))


def load_config_dict(c):
    unknown = set(c) - set(DEFAULTS)
    if unknown:
        raise ValueError("unknown keys: %s" % ", ".join(sorted(unknown)))
    c = dict(DEFAULTS, **c)
    rules = []
    for i, r in enumerate(c["allow"]):
        bad = set(r) - {"to", "port", "proto"}
        if bad:
            raise ValueError("allow[%d]: unknown keys %s" % (i, ", ".join(sorted(bad))))
        net = ipaddress.ip_network(r["to"], strict=False)
        if net.version != 4:
            raise ValueError("allow[%d]: only IPv4 for now (got %s)" % (i, r["to"]))
        proto = r.get("proto", "tcp")
        if proto not in ("tcp", "udp"):
            raise ValueError("allow[%d]: proto must be tcp or udp" % i)
        rules.append({"to": str(net), "port": port_spec(r["port"]), "proto": proto})
    c["allow"] = rules
    hp = []
    for p in c["host_ports"]:
        if isinstance(p, int):
            p = {"port": p}
        hp.append({"port": port_spec(p["port"]), "proto": p.get("proto", "tcp")})
    c["host_ports"] = hp
    for k in ("down", "up"):
        if c[k] is not None:
            rate_bits(c[k])
    if c["quota"] is not None:
        c["quota"] = size_bytes(c["quota"])
    ipaddress.ip_address(c["host_addr"])
    sub = ipaddress.ip_network(c["subnet"])
    if sub.prefixlen > 28:
        raise ValueError("subnet %s is too small (want /28 or bigger)" % sub)
    if int(c["max_attach"]) < 1:
        raise ValueError("max_attach must be >= 1")
    return c


def nft_ruleset(c):
    """The whole table for the outer netns. Everything from a vp* (a sandbox) is dropped unless it is a reply or
    matches the allow list; accepted bytes both ways go through the one quota."""
    out = ["table inet aosnet {"]
    if c["quota"] is not None:
        out.append("  quota total { over %d bytes }" % c["quota"])
    names = ["up", "down", "denied", "to_outer"] + ["r%d" % i for i in range(len(c["allow"]))] + \
            ["h%d" % i for i in range(len(c["host_ports"]))]
    out += ["  counter %s { }" % n for n in names]
    q = "quota name \"total\" drop; " if c["quota"] is not None else ""
    out += [
        "  chain upc { %scounter name \"up\" accept; }" % q,
        "  chain downc { %scounter name \"down\" accept; }" % q,
        "  chain allow {",
    ]
    for i, r in enumerate(c["allow"]):
        out.append("    ip daddr %s %s dport %s counter name \"r%d\" goto upc" % (r["to"], r["proto"], r["port"], i))
    for i, h in enumerate(c["host_ports"]):
        out.append("    ip daddr %s %s dport %s counter name \"h%d\" goto upc" % (c["host_addr"], h["proto"], h["port"], i))
    out += [
        "  }",
        "  chain forward { type filter hook forward priority 0; policy drop;",
        "    iifname \"%s*\" ct state established,related goto upc" % VETH,
        "    oifname \"%s*\" ct state established,related goto downc" % VETH,
        "    iifname \"%s*\" ct state new jump allow" % VETH,
        "    iifname \"%s*\" counter name \"denied\" reject with icmpx admin-prohibited" % VETH,
        "  }",
        "  chain input { type filter hook input priority 0; policy accept;",
        "    iifname \"%s*\" counter name \"to_outer\" drop" % VETH,
        "  }",
        "  chain postrouting { type nat hook postrouting priority 100; oifname \"%s\" masquerade; }" % TAP,
        "}",
    ]
    return "\n".join(out) + "\n"


def tbf(dev, rate, burst, latency):
    bps = rate_bits(rate) / 8
    b = int(burst) if burst else max(64 * 1024, int(bps / 50))  # never below a few full packets
    return ["tc", "qdisc", "replace", "dev", dev, "root", "tbf", "rate", rate, "burst", str(b), "latency", latency]


# Upload goes into pasta, which ends the sandbox's TCP itself; one dropped packet there cost a third more bytes and
# up to 5x the time in our runs (11-27), so the upload queue is deep enough (1s) that tbf delays instead of drops.
# Download ends in the sandbox's own kernel, which copes with drops; a short queue keeps the delay low.
UP_LATENCY, DOWN_LATENCY = "1s", "200ms"


# ------------------------------------------------------------ the holder: runs inside the outer namespaces

def holder_main(cfg_path):
    """Inside the outer user+net namespace (root there). Reads one json command per line on stdin, answers one
    json line on stdout. Ends when stdin closes (the kernel is gone)."""
    c = load_config(cfg_path)
    out = sys.stdout
    sys.stdout = sys.stderr  # nothing else may write to the answer channel

    def sh(argv, inp=None):
        r = subprocess.run(argv, input=inp, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("%s: %s" % (" ".join(argv[:4]), (r.stderr or r.stdout).strip()[:300]))
        return r.stdout

    def ifaces():
        return {i["ifname"]: i for i in json.loads(sh(["ip", "-j", "addr"]))}

    attached = {}  # vpN -> (pid, start time) of the sandbox's first process

    def start_time(pid):
        try:
            with open("/proc/%d/stat" % pid) as f:
                return f.read().rsplit(")", 1)[1].split()[19]
        except (OSError, IndexError):
            return None

    def reap():
        """Take down the veth of a sandbox that has ended: its netns may linger (closing sockets hold it), and
        the slot must be free for the next one."""
        for dev, (pid, st) in list(attached.items()):
            if start_time(pid) != st:
                subprocess.run(["ip", "link", "del", dev], capture_output=True)
                del attached[dev]

    def do(cmd):
        op = cmd.get("op")
        if op == "tap":  # is pasta's tap up with an address and a default route?
            tap = ifaces().get(TAP)
            routes = json.loads(sh(["ip", "-j", "route", "show", "default"]))
            addr = [a["local"] for a in (tap or {}).get("addr_info", []) if a.get("family") == "inet"]
            return {"up": bool(tap and addr and routes), "addr": addr, "gateway": [r.get("gateway") for r in routes]}
        if op == "init":
            sh(["sysctl", "-q", "-w", "net.ipv4.ip_forward=1"])
            sh(["nft", "-f", "-"], nft_ruleset(c))
            if c["up"]:
                sh(tbf(TAP, c["up"], c["burst"], UP_LATENCY))
            return {}
        if op == "attach":
            pid = int(cmd["pid"])
            end = time.monotonic() + 3  # a sandbox that just ended may still be taking its veth down
            while True:
                reap()
                names = ifaces()
                vps = [n for n in names if n.startswith(VETH) and n[len(VETH):].isdigit()]
                if len(vps) < int(c["max_attach"]):
                    break
                if time.monotonic() > end:
                    raise RuntimeError("max_attach %s reached (%s)" % (c["max_attach"], ", ".join(sorted(vps))))
                time.sleep(0.1)
            n = next(i for i in range(10**6) if VETH + str(i) not in names)
            sub = ipaddress.ip_network(c["subnet"])
            pair = list(sub.subnets(new_prefix=30))
            if n >= len(pair):
                raise RuntimeError("subnet %s has no room for attach %d" % (sub, n))
            hosts = list(pair[n].hosts())
            outer, inner, dev = str(hosts[0]), str(hosts[1]), VETH + str(n)
            ns = "/proc/%d/ns/net" % pid
            sh(["ip", "link", "add", dev, "type", "veth", "peer", "name", "eth0", "netns", ns])
            try:
                sh(["ip", "addr", "add", outer + "/30", "dev", dev])
                sh(["ip", "link", "set", dev, "up"])
                ins = ["nsenter", "--net=" + ns]
                sh(ins + ["ip", "link", "set", "lo", "up"])
                sh(ins + ["ip", "addr", "add", inner + "/30", "dev", "eth0"])
                sh(ins + ["ip", "link", "set", "eth0", "up"])
                sh(ins + ["ip", "route", "add", "default", "via", outer])
                if c["down"]:
                    sh(tbf(dev, c["down"], c["burst"], DOWN_LATENCY))
            except Exception:
                subprocess.run(["ip", "link", "del", dev], capture_output=True)
                raise
            attached[dev] = (pid, start_time(pid))
            return {"if": dev, "addr": inner, "gateway": outer}
        if op == "stats":
            reap()
            objs = json.loads(sh(["nft", "-j", "list", "table", "inet", "aosnet"]))["nftables"]
            counters, quota = {}, None
            for o in objs:
                if "counter" in o and "name" in o["counter"]:
                    counters[o["counter"]["name"]] = [o["counter"]["packets"], o["counter"]["bytes"]]
                elif "quota" in o:
                    quota = {"bytes": o["quota"]["bytes"], "used": o["quota"]["used"]}
            return {"counters": counters, "quota": quota,
                    "attached": sorted(n for n in ifaces() if n.startswith(VETH) and n[len(VETH):].isdigit())}
        raise RuntimeError("unknown op %r" % op)

    for line in sys.stdin:
        try:
            cmd = json.loads(line)
            res = dict(do(cmd), ok=True)
        except Exception as e:  # one bad request must not end the holder
            res = {"ok": False, "error": str(e)}
        out.write(json.dumps(res) + "\n")
        out.flush()


def decl_files(c, wrapped=False):
    """The aos/net declaration (one small file per field). wrapped: no ctl, the inner layer already sits behind it."""
    files = {
        "kind": "veth",          # a veth into your own netns; the rules live on the other end
        "ctl": "ctl",            # socket (relative): one json line in, one out; ops info, attach
        "protocol": "json-lines",
        "allow": "\n".join("%s %s %s" % (r["proto"], r["to"], r["port"]) for r in c["allow"]),
        "host_addr": c["host_addr"] if c["host_ports"] else "",
        "host_ports": "\n".join("%s %s" % (h["proto"], h["port"]) for h in c["host_ports"]),
        "down": c["down"] or "",
        "up": c["up"] or "",
        "quota": "" if c["quota"] is None else str(c["quota"]),
        "max_attach": str(c["max_attach"]),
        "ipv6": "no",
        "dns": "only if allowed above (by ip and port 53)",
        "status": "status",
    }
    if wrapped:
        del files["ctl"], files["protocol"], files["max_attach"]
    return files


# ------------------------------------------------------------ the kernel: runs outside, in your own namespaces

def subid_range(path, user):
    """(start, count) of the first range for this user in /etc/subuid or /etc/subgid, or None."""
    try:
        with open(path) as f:
            for line in f:
                p = line.strip().split(":")
                if len(p) == 3 and p[0] in (user, str(os.getuid())):
                    return int(p[1]), int(p[2])
    except OSError:
        pass
    return None


class Kernel:
    def __init__(self, a, c):
        self.a, self.c = a, c
        self.lock = threading.Lock()
        self.holder = self.pasta = None
        self.userns = os.readlink("/proc/self/ns/user")  # callers must be outside any sandbox (same user ns)
        self.stats = {}
        self.stopping = threading.Event()

    def ask(self, cmd):
        with self.lock:
            self.holder.stdin.write(json.dumps(cmd) + "\n")
            self.holder.stdin.flush()
            line = self.holder.stdout.readline()
        if not line:
            raise RuntimeError("the holder of the outer netns is gone")
        r = json.loads(line)
        if not r.get("ok"):
            raise RuntimeError(r.get("error", "failed"))
        return r

    def holder_argv(self):
        user = pwd.getpwuid(os.getuid()).pw_name
        su, sg = subid_range("/etc/subuid", user), subid_range("/etc/subgid", user)
        self.subids = min(su[1], sg[1]) if su and sg and shutil.which("newuidmap") else 0
        if self.subids:  # also map the subordinate ids, so a sandbox under us can run as uid N >= 1
            m = ["--map-user=0", "--map-users=1:%d:%d" % (su[0], self.subids),
                 "--map-group=0", "--map-groups=1:%d:%d" % (sg[0], self.subids)]
        else:
            m = ["--map-root-user"]
        if not nest.in_init_userns():  # nested in another kernel: keep every id we have (nest.userns_args)
            m = nest.userns_args()[1:]
        return ["unshare", "--user"] + m + ["--net", "--", sys.executable, "-I", os.path.abspath(__file__),
                                            "--holder", os.path.abspath(self.a.config)]

    def pasta_argv(self, pid):
        hostmap = ["--map-host-loopback", self.c["host_addr"]] if self.c["host_ports"] else ["--no-map-gw"]
        # -T/-U none: the sandbox gets no way to the host's 127.0.0.1 ports; -t/-u none: it opens no port on the
        # host; -m 1500: tc's burst must hold a packet; -4: IPv4 only for now
        return [self.a.pasta, "--config-net", "-q", "-f", "-4", "-m", "1500", "-T", "none", "-U", "none",
                "-t", "none", "-u", "none", "-I", TAP] + hostmap + [str(pid)]

    def start(self):
        self.holder = subprocess.Popen(self.holder_argv(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       text=True, start_new_session=True)
        time.sleep(0.05)
        end = time.monotonic() + 5
        while self.holder.poll() is None and time.monotonic() < end:  # wait for its namespaces to exist
            try:
                if os.readlink("/proc/%d/ns/user" % self.holder.pid) != self.userns:
                    break
            except OSError:
                pass
            time.sleep(0.02)
        if self.holder.poll() is not None:
            raise RuntimeError("could not make the outer namespaces (unshare exited %s)" % self.holder.returncode)
        self.pasta = subprocess.Popen(self.pasta_argv(self.holder.pid), start_new_session=True)
        end = time.monotonic() + 10
        while True:
            t = self.ask({"op": "tap"})
            if t["up"]:
                self.tap = t
                break
            if self.pasta.poll() is not None or time.monotonic() > end:
                raise RuntimeError("pasta did not bring up %s (pasta exit %s)" % (TAP, self.pasta.poll()))
            time.sleep(0.05)
        self.ask({"op": "init"})

    def stop(self):
        self.stopping.set()
        for p in (self.pasta, self.holder):
            if p and p.poll() is None:
                try:
                    p.terminate()
                    p.wait(3)
                except subprocess.TimeoutExpired:
                    p.kill()
                    p.wait()

    # ---- the dir it puts out

    def declare(self):
        d = os.path.join(self.a.dir, DECL)
        os.makedirs(d, exist_ok=True)
        for k, v in decl_files(self.c).items():
            write_atomic(os.path.join(d, k), v + "\n" if v else "")
        write_atomic(os.path.join(self.a.dir, ".aos", "interfaces", "aos", "description"),
                     "net kernel: the outside network, only to the allowed ip:port, at the declared rates, "
                     "until the quota is used\n")

    def write_status(self, state="running"):
        s = self.stats
        cn = s.get("counters", {})
        q = s.get("quota")
        c = self.c
        lines = ["state: %s" % state, "updated: %s" % time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                 "attached: %d" % len(s.get("attached", []))]
        if q:
            lines += ["quota_bytes: %d" % q["bytes"], "quota_used: %d" % q["used"],
                      "quota_left: %d" % max(0, q["bytes"] - q["used"])]
        else:
            lines += ["quota_bytes: none"]
        for k in ("up", "down", "denied", "to_outer"):
            p, b = cn.get(k, [0, 0])
            lines.append("%s: packets %d bytes %d" % (k, p, b))
        for i, r in enumerate(c["allow"]):
            p, b = cn.get("r%d" % i, [0, 0])
            lines.append("allow.%d: %s %s %s new_connections %d bytes %d" % (i, r["proto"], r["to"], r["port"], p, b))
        for i, h in enumerate(c["host_ports"]):
            p, b = cn.get("h%d" % i, [0, 0])
            lines.append("host.%d: %s %s new_connections %d bytes %d" % (i, h["proto"], h["port"], p, b))
        write_atomic(os.path.join(self.a.dir, "status"), "\n".join(lines) + "\n")

    def status_loop(self):
        while not self.stopping.wait(float(self.c["status_interval"])):
            try:
                self.stats = self.ask({"op": "stats"})
                self.write_status()
            except Exception as e:
                if not self.stopping.is_set():
                    warn("status: %s" % e)

    # ---- ctl

    def handle(self, req, peer_pid):
        """info: what a caller needs to put a sandbox under us; attach: a veth into the netns of pid."""
        try:
            peer_ns = os.readlink("/proc/%d/ns/user" % peer_pid)
        except OSError:
            peer_ns = None
        if peer_ns != self.userns:
            return {"ok": False, "error": "Refused only callers outside any sandbox may use ctl"}
        op = req.get("op")
        if op == "info":
            return {"ok": True, "outer_pid": self.holder.pid, "subids": self.subids}
        if op == "attach":
            try:
                r = self.ask({"op": "attach", "pid": int(req["pid"])})
            except (RuntimeError, KeyError, ValueError) as e:
                return {"ok": False, "error": "AttachFailed %s" % e}
            self.stats = self.ask({"op": "stats"})
            self.write_status()
            return r
        return {"ok": False, "error": "ArgumentsBad unknown op %r (info, attach)" % op}

    def serve(self):
        k = self

        class H(socketserver.StreamRequestHandler):
            def handle(self):
                cred = self.connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
                pid = struct.unpack("3i", cred)[0]
                for line in self.rfile:
                    try:
                        res = k.handle(json.loads(line), pid)
                    except ValueError:
                        res = {"ok": False, "error": "ArgumentsBad not json"}
                    self.wfile.write((json.dumps(res) + "\n").encode())
                    self.wfile.flush()

        class S(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
            daemon_threads = True

        sp = os.path.join(self.a.dir, "ctl")
        if os.path.lexists(sp):
            os.unlink(sp)
        self.srv = S(sp, H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()


# ------------------------------------------------------------ as a nesting wrapper: net_kernel.py --json CFG -- NEXT...

def free_subnet():
    """10.77.0.0/16 unless the netns we run in already uses it (a net kernel inside another one): then the next
    free one of 10.78 .. 10.99."""
    try:
        used = [ipaddress.ip_interface("%s/%s" % (a["local"], a["prefixlen"])).network
                for i in json.loads(subprocess.run(["ip", "-j", "addr"], capture_output=True, text=True).stdout)
                for a in i.get("addr_info", []) if a.get("family") == "inet"]
    except (ValueError, KeyError):
        used = []
    for n in range(77, 100):
        net = ipaddress.ip_network("10.%d.0.0/16" % n)
        if not any(net.overlaps(u) for u in used):
            return str(net)
    raise RuntimeError("no free 10.77-99.0.0/16 for the veths")


def nested_config(cfg, outer):
    """Read what an outer net kernel declared and fit our config into the network it gives us: our host_ports
    mean the machine outside, which for us is the outer kernel's host_addr, so they become allow rules to it.
    Returns (config, declaration overrides, warnings)."""
    c = dict(cfg)
    c.pop("description", None)
    over, warns = {}, []
    if not nest.declared(outer, "net"):
        return c, over, warns
    oaddr = nest.decl_read(outer, "net", "host_addr", "")
    ohost = set(nest.decl_read(outer, "net", "host_ports", "").split("\n")) - {""}
    oallow = set(nest.decl_read(outer, "net", "allow", "").split("\n")) - {""}
    hp = c.get("host_ports") or []
    if hp:
        if not oaddr:
            raise ValueError("host_ports %s: the outer net kernel gives no way to the machine (it declares no "
                             "host_addr)" % hp)
        hp = [p if isinstance(p, dict) else {"port": p} for p in hp]
        c["allow"] = list(c.get("allow") or []) + [{"to": oaddr, "port": p["port"], "proto": p.get("proto", "tcp")}
                                                     for p in hp]
        c["host_ports"] = []  # pasta: --no-map-gw, our "host" would only be the outer sandbox itself
        over = {"host_addr": oaddr, "host_ports": "\n".join("%s %s" % (p.get("proto", "tcp"), p["port"]) for p in hp)}
        for p in hp:
            if "%s %s" % (p.get("proto", "tcp"), p["port"]) not in ohost:
                warns.append("host port %s is not allowed by the outer net kernel; it stays closed" % p["port"])
    for r in cfg.get("allow") or []:
        net = ipaddress.ip_network(r["to"], strict=False)
        if "%s %s %s" % (r.get("proto", "tcp"), net, r["port"]) not in oallow:
            warns.append("allow %s:%s is not in the outer allow list (by text); the outer one decides" % (
                r["to"], r["port"]))
    oq = nest.decl_read(outer, "net", "quota", "")
    if oq:
        mine = size_bytes(c["quota"]) if c.get("quota") is not None else None
        if mine is None or mine > int(oq):
            warns.append("quota %s is more than the outer %s bytes; the outer one cuts first" % (
                c.get("quota", "none"), oq))
            over["quota"] = oq
    return c, over, warns


def gate_main(argv):
    """First program of the inner layer (root in its own user ns under the outer netns, in its own net and mount
    ns): say ready, wait until the kernel has pulled the veth in, lock the declarations, then run the next layer."""
    w, r = int(argv[0]), int(argv[1])
    nxt = argv[3:] if argv[2:3] == ["--"] else argv[2:]
    os.write(w, b"ready\n")
    ans = os.read(r, 4096).decode().strip()
    os.close(w)
    os.close(r)
    if ans != "ok":
        fail("NetFailed", ans or "no answer from the net kernel", 125)
    nest.lock_env(PROG)  # our own mount namespace: the kernel outside keeps writing its status file
    try:
        os.execvp(nxt[0], nxt)
    except OSError as e:
        fail("ExecFailed", "%s: %s" % (nxt[0], e.strerror), 127)


def wrapper_main():
    opts, cfg, nxt = nest.parse(PROG, sys.argv[1:], flags=())
    pasta = os.environ.get("MINI_PASTA") or shutil.which("pasta")
    if not pasta or not os.access(pasta, os.X_OK):
        fail("PastaMissing", "no pasta (install the passt package, or set MINI_PASTA)", 2)
    outer = nest.env_outer()
    try:
        c, over, warns = nested_config(cfg, outer)
        if "subnet" not in c:
            c["subnet"] = free_subnet()
        raw, c = c, load_config_dict(dict(c))
    except (ValueError, KeyError, TypeError, RuntimeError) as e:
        fail("ConfigBad", "%s: %s" % (opts["name"], e), 2)
    for w in warns:
        warn("%s: %s" % (opts["name"], w))
    env = nest.new_env("net", opts["name"], opts.get("from"))
    cfgp = os.path.join(env, "net.json")
    with open(cfgp, "w") as f:
        json.dump(raw, f)  # the holder reads it again
    k = Kernel(types.SimpleNamespace(dir=env, config=cfgp, pasta=pasta), c)
    for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(s, signal.SIG_IGN)  # while we set up; passed on to the inner layer once it runs
    try:
        k.start()
        inner_cg = nest.cg_split(PROG, [os.getpid(), k.holder.pid, k.pasta.pid], "k-net", "in")
        k.stats = k.ask({"op": "stats"})
        # status: absolute, like the llm kernel's: the declaration is copied into each inner layer's dir, the file is not
        files = dict(decl_files(c, wrapped=True), status=os.path.join(env, "status"), **over)
        nest.declare(env, "net", files, "net kernel: you are in a netns behind it; only the allowed ip:port, at "
                     "the declared rates, until the quota is used (an outer net kernel, if any, still applies)")
        k.write_status()
    except (RuntimeError, OSError) as e:
        k.stop()
        fail("StartFailed", str(e))
    r1, w1 = os.pipe()
    r2, w2 = os.pipe()
    argv = ["nsenter", "--user=/proc/%d/ns/user" % k.holder.pid, "--preserve-credentials",
            "unshare", "--user", "--map-users=all", "--map-groups=all", "--net", "--mount", "--"] + \
        nest.py(os.path.abspath(__file__)) + ["--gate", str(w1), str(r2), "--"] + nxt
    box = []  # caught (not ignored) while we start it: an ignored signal stays ignored in the inner layers
    for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(s, lambda sig, _: box and box[0].send_signal(sig))
    inner = subprocess.Popen(argv, pass_fds=(w1, r2), env=dict(os.environ, AOS_ENV=env))
    box.append(inner)
    os.close(w1)
    os.close(r2)
    ok = False
    try:
        if os.read(r1, 64).strip() == b"ready":
            k.ask({"op": "attach", "pid": inner.pid})
            if inner_cg:
                nest.cg_move(inner.pid, inner_cg)
            ok = True
            os.write(w2, b"ok\n")
        else:
            os.write(w2, b"no ready line from the inner layer\n")
    except (RuntimeError, OSError) as e:
        try:
            os.write(w2, ("AttachFailed %s\n" % e).encode())
        except OSError:
            pass
    os.close(r1)
    os.close(w2)
    threading.Thread(target=k.status_loop, daemon=True).start()
    rc = inner.wait()
    k.stopping.set()
    try:
        k.stats = k.ask({"op": "stats"})
    except Exception:
        pass
    k.stop()
    k.write_status("stopped")
    if not ok and rc == 0:
        rc = 125
    sys.exit(128 - rc if rc < 0 else rc)


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "--holder":
        return holder_main(sys.argv[2])
    if len(sys.argv) >= 2 and sys.argv[1] == "--gate":
        return gate_main(sys.argv[2:])
    if "--json" in sys.argv[1:sys.argv.index("--") if "--" in sys.argv else None]:
        return wrapper_main()
    ap = argparse.ArgumentParser(prog=PROG, description="net kernel for mini: an outer netns behind pasta with the "
                                 "allow list, quota and rates; sandboxes attach a veth to it through DIR/ctl")
    ap.error = lambda m: fail("ArgumentsBad", "%s (usage: %s --help)" % (m, PROG), 2)
    ap.add_argument("--dir", required=True, help="the dir it puts out: ctl, status, .aos/interfaces/aos/net/")
    ap.add_argument("--config", required=True, help="json: allow, host_ports, down, up, quota, ... (see README)")
    ap.add_argument("--pasta", help="the pasta binary (default: pasta on PATH)")
    ap.add_argument("--dry-run", action="store_true", help="print the nft ruleset and the commands, start nothing")
    if len(sys.argv) == 1:
        ap.error("no arguments")
    a = ap.parse_args()
    try:
        c = load_config(a.config)
    except (OSError, ValueError, KeyError, TypeError) as e:
        fail("ConfigBad", "%s: %s" % (a.config, e), 2)
    a.pasta = a.pasta or shutil.which("pasta")
    if not a.dry_run:
        if not a.pasta or not os.access(a.pasta, os.X_OK):
            fail("PastaMissing", "no pasta (install the passt package, or give --pasta PATH)", 2)
        for t in ("unshare", "nsenter", "ip", "nft", "tc", "sysctl"):
            if not shutil.which(t):
                fail("ToolMissing", "%s is not on PATH" % t, 2)
    os.makedirs(a.dir, exist_ok=True)
    k = Kernel(a, c)
    if a.dry_run:
        print("holder: %s" % " ".join(k.holder_argv()))
        print("pasta:  %s" % " ".join(k.pasta_argv("<holder-pid>")))
        if c["up"]:
            print("up:     %s" % " ".join(tbf(TAP, c["up"], c["burst"], UP_LATENCY)))
        if c["down"]:
            print("down:   %s (on each vpN when attached)" % " ".join(tbf("vpN", c["down"], c["burst"], DOWN_LATENCY)))
        print(nft_ruleset(c), end="")
        return
    for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(s, lambda *_: k.stopping.set())
    try:
        k.start()
        k.stats = k.ask({"op": "stats"})
        k.declare()
        k.write_status()
        k.serve()
    except (RuntimeError, OSError) as e:
        k.stop()
        fail("StartFailed", str(e))
    print("%s: ready, ctl %s, outer pid %d, tap %s via %s" % (
        PROG, os.path.join(a.dir, "ctl"), k.holder.pid, ",".join(k.tap["addr"]), ",".join(map(str, k.tap["gateway"]))),
        flush=True)
    threading.Thread(target=k.status_loop, daemon=True).start()
    while not k.stopping.wait(0.5):
        if k.pasta.poll() is not None or k.holder.poll() is not None:
            warn("pasta or the holder ended (pasta %s, holder %s); stopping" % (k.pasta.poll(), k.holder.poll()))
            break
    k.stopping.set()
    try:
        k.srv.shutdown()
        k.srv.server_close()
        os.unlink(os.path.join(a.dir, "ctl"))
    except OSError:
        pass
    try:
        k.stats = k.ask({"op": "stats"})
    except Exception:
        pass
    k.stop()
    k.write_status("stopped")


if __name__ == "__main__":
    main()
