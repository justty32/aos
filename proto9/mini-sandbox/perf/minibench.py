"""Stacks N kernels of one kind with mini.py --kernels and measures: time until the innermost command runs, the scope's memory, resident processes and their RSS, what the agent's own operations cost there (inner.py), and how long mini takes to shut down afterwards."""

import http.server
import json
import os
import select
import shutil
import socketserver
import subprocess
import threading
import time

from common import HERE, PY, r2

MINI = os.path.abspath(os.path.join(HERE, "..", "mini.py"))
HOST_ADDR = "169.254.77.1"  # how the net kernel shows the machine's loopback inside (net_kernel DEFAULTS host_addr)


class _H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def do_GET(self):
        n = 100 if self.path.endswith("small") else 100 * 10 ** 6
        self.send_response(200)
        self.send_header("Content-Length", str(n))
        self.end_headers()
        chunk = b"\0" * (1 << 20)
        while n > 0:
            k = min(n, len(chunk))
            self.wfile.write(chunk[:k])
            n -= k

    def do_PUT(self):
        n = int(self.headers.get("Content-Length", 0))
        while n > 0:
            b = self.rfile.read(min(n, 1 << 20))
            if not b:
                break
            n -= len(b)
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()


class _S(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def gen(work, kind, i, port=None):
    """Write kernels/s/<kind>/<i>.json (loose limits so they do not disturb the measurement); its name."""
    if kind == "cg":
        cfg = {"program": "cg_kernel.py", "config": {"cpu": "%d%%" % (1600 - i), "mem": "%dM" % (8192 - i),
                                                      "pids": 4096 - i}}
    elif kind == "mask":
        t = os.path.join(work, "targets", "d%d" % i)
        os.makedirs(t, exist_ok=True)
        with open(os.path.join(t, "secret"), "w") as f:
            f.write("x\n")
        cfg = {"program": "mask_kernel.py", "config": {"paths": [{"path": t, "how": "tmpfs"}]}}
    elif kind == "llm":
        cfg = {"program": "llm_kernel.py", "config": {"upstream": "fake", "models": ["fake-model"], "limit": 100000}}
    elif kind == "net":
        cfg = {"program": "net_kernel.py", "config": {"host_ports": [port]}}
    else:
        raise ValueError(kind)
    p = os.path.join(work, "kernels", "s", kind, "%d.json" % i)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        json.dump(cfg, f)
    return "s/%s/%d" % (kind, i)


def find_scope(unit):
    uid = os.getuid()
    root = "/sys/fs/cgroup/user.slice/user-%d.slice/user@%d.service" % (uid, uid)
    for dp, dns, _ in os.walk(root):
        if unit in dns:
            return os.path.join(dp, unit)
        if dp.count("/") - root.count("/") >= 1:
            dns[:] = []  # scopes sit in app.slice (one level down)
    return None


def _procs(scope):
    out = []
    for dp, _, _ in os.walk(scope):
        try:
            with open(os.path.join(dp, "cgroup.procs")) as f:
                out += [int(x) for x in f.read().split()]
        except OSError:
            pass
    return out


def _rss_kb(pid):
    try:
        with open("/proc/%d/status" % pid) as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1])
    except OSError:
        pass
    return 0


def _comm(pid):
    try:
        with open("/proc/%d/comm" % pid) as f:
            return f.read().strip()
    except OSError:
        return "?"


def one(work, kind, n, url, auto_mask, quick, timeout):
    names = []
    for i in range(1, n + 1):
        k = kind if kind != "mix" else ("cg" if i % 2 else "mask")
        names.append(gen(work, k, i, port=url and int(url.rsplit(":", 1)[1].strip("/"))))
    inner = os.path.join(work, "inner.py")
    py = os.path.realpath(PY)
    iargs = (["--llm"] if kind == "llm" else []) + (["--url", url] if kind == "net" else []) + \
        (["--quick"] if quick else [])
    cmd = [PY, "-B", MINI, "--name", "perf"] + ([] if auto_mask else ["--no-auto-mask"]) + \
        ["--kernels", ",".join(names), "--", "sh", "-c",
         "echo READY; read x; exec %s -I -B %s %s" % (py, inner, " ".join(iargs))]
    env = dict(os.environ, MINI_KERNELS_PATH=os.path.join(work, "kernels"), PYTHONDONTWRITEBYTECODE="1")
    rec = {"bench": "mini", "case": kind, "n": n, "auto_mask": auto_mask}
    t0 = time.perf_counter()
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                         text=True)
    unit = "mini-perf-%d.scope" % p.pid
    line = ""
    while True:
        r, _, _ = select.select([p.stdout], [], [], 0.2)
        if r:
            line = p.stdout.readline()
            break
        if p.poll() is not None or time.perf_counter() - t0 > timeout:
            break
    rec["ready_s"] = r2(time.perf_counter() - t0, 3)
    scope = find_scope(unit)
    if line.strip() != "READY":
        rec["failed"] = True
        if scope:  # only our own scope: kill what is left in it (e.g. a stuck unshare id-map helper)
            rec["left_in_scope"] = [_comm(x) for x in _procs(scope)]
            try:
                with open(scope + "/cgroup.kill", "w") as f:
                    f.write("1")
            except OSError as e:
                rec["kill_error"] = str(e)
        if p.poll() is None:
            p.kill()
        p.stdin.close()
        err = p.stderr.read()
        p.wait()
        rec["rc"] = p.returncode
        rec["stderr_tail"] = err.strip().splitlines()[-4:]
        return rec
    time.sleep(0.5)
    if scope:
        try:
            with open(scope + "/memory.current") as f:
                rec["scope_mem_MB"] = r2(int(f.read()) / 2 ** 20, 1)
            pids = _procs(scope)
            rec["procs"] = len(pids)
            rec["rss_sum_MB"] = r2(sum(_rss_kb(x) for x in pids) / 1024, 1)
            cnt = {}
            for x in pids:
                cnt[_comm(x)] = cnt.get(_comm(x), 0) + 1
            rec["comm"] = cnt
            rec["cgroup_depth_below_scope"] = max(dp.count("/") for dp, _, _ in os.walk(scope)) - scope.count("/")
        except OSError as e:
            rec["scope_error"] = str(e)
    p.stdin.write("go\n")
    p.stdin.flush()
    bench_line, t_bench = None, None
    for l in p.stdout:
        if l.startswith("BENCH "):
            bench_line, t_bench = l, time.perf_counter()
            break
    try:
        out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        if scope:
            try:
                with open(scope + "/cgroup.kill", "w") as f:
                    f.write("1")
            except OSError:
                pass
        p.kill()
        out, err = p.communicate()
        rec["teardown_timeout"] = True
    if t_bench:
        rec["shutdown_s"] = r2(time.perf_counter() - t_bench, 3)
    rec["rc"] = p.returncode
    if bench_line:
        rec.update(json.loads(bench_line[6:]))
    warns = [l for l in err.splitlines() if "warning" in l or "error" in l]
    if warns:
        rec["stderr_lines"] = len(warns)
        rec["stderr_first"] = warns[:2]
    return rec


def mini(work, quick, kinds, layers, auto_mask=False, timeout=300):
    os.chmod(work, 0o755)  # a uid kernel further in must still read inner.py
    shutil.copy(os.path.join(HERE, "inner.py"), os.path.join(work, "inner.py"))
    srv = url = None
    if "net" in kinds:
        srv = _S(("127.0.0.1", 0), _H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        url = "http://%s:%d/" % (HOST_ADDR, srv.server_address[1])
    out = []
    try:
        for kind in kinds:
            for n in layers:
                out.append(one(work, kind, n, url, auto_mask, quick, timeout))
    finally:
        if srv:
            srv.shutdown()
            srv.server_close()
    return out
