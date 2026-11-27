"""The pi-sandbox path (proto9/pi-sandbox, aos-daemon) with --fake only (no model is called, mini is not touched): daemon start, one llm kernel start, one proc start (plain and in pi's full sky), a request through 1 and 2 stacked llm kernels and through /llm/relay, and the whole thing (daemon + llm kernel + pi) until pi's first request."""

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time

from common import REPO, median, r2

PISB = os.path.join(REPO, "proto9", "pi-sandbox")


def _load():
    sys.path.insert(0, PISB)
    sys.dont_write_bytecode = True
    import aos_pi  # noqa: E402
    import daemon_ctl  # noqa: E402
    return aos_pi, daemon_ctl


def _args(aos_pi, work, root, stack, model="fake-model"):
    a = aos_pi.parser().parse_args([work, "say hi", "--model", model, "--fake", "--stack", str(stack),
                                    "--limit", "100000", "--sandbox-root", root, "--name", "perf"])
    aos_pi.check_args(a)
    return a


def _post_unix(path, n):
    body = json.dumps({"model": "fake-model", "messages": [{"role": "user", "content": "hi"}]}).encode()
    req = (b"POST /v1/chat/completions HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\n"
           b"Content-Length: %d\r\nConnection: close\r\n\r\n" % len(body)) + body
    return _ask(lambda: socket.socket(socket.AF_UNIX), path, req, n)


def _post_tcp(port, n):
    body = json.dumps({"model": "fake-model", "messages": [{"role": "user", "content": "hi"}]}).encode()
    req = (b"POST /v1/chat/completions HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Type: application/json\r\n"
           b"Content-Length: %d\r\nConnection: close\r\n\r\n" % len(body)) + body
    return _ask(lambda: socket.socket(socket.AF_INET), ("127.0.0.1", port), req, n)


def _ask(mk, addr, req, n):
    lat, status = [], ""
    for _ in range(n):
        t = time.perf_counter()
        s = mk()
        s.settimeout(10)
        s.connect(addr)
        s.sendall(req)
        r = b""
        while True:
            c = s.recv(65536)
            if not c:
                break
            r += c
        s.close()
        lat.append((time.perf_counter() - t) * 1000)
        status = r.split(b"\r\n", 1)[0].decode(errors="replace")
    return status, lat


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def pisandbox(work, quick):
    try:
        aos_pi, dc = _load()
    except Exception as e:  # noqa: BLE001 - report, do not crash the other benches
        return [{"bench": "pisandbox", "error": "cannot load %s: %s" % (PISB, e)}]
    if not os.path.exists(dc.DAEMON_BIN):
        return [{"bench": "pisandbox", "error": "no aos-daemon at %s (make it in proto9/cpp/aos-daemon)" % dc.DAEMON_BIN}]
    pw = os.path.join(work, "pi-work")
    os.makedirs(pw, exist_ok=True)
    with open(os.path.join(pw, "NOTES.md"), "w") as f:
        f.write("perf\n")
    root = os.path.join(work, "sb")
    out = []
    reps = 5 if quick else 20
    asks = 30 if quick else 200

    # -- pieces: daemon, two stacked llm kernels, procs, requests
    a = _args(aos_pi, pw, root, 2)
    sb = aos_pi.Sandbox(a)
    relay = None
    try:
        sb.prepare()
        sb.d = dc.Daemon(sb.run, a.daemon)
        t = time.perf_counter()
        sb.d.start()
        out.append({"bench": "pisandbox", "case": "daemon-start", "ms": r2((time.perf_counter() - t) * 1000, 1),
                    "how": "aos-daemon with daemon.json {} until it prints export AOS_DAEMON="})
        marks, orig = [], sb.d.start_proc

        def timed(c, p):
            marks.append(time.perf_counter())
            return orig(c, p)
        sb.d.start_proc = timed
        sb.start_kernels()
        marks.append(time.perf_counter())
        sb.d.start_proc = orig
        for i in range(len(marks) - 1):
            out.append({"bench": "pisandbox", "case": "llm-kernel-start", "n": i + 1,
                        "ms": r2((marks[i + 1] - marks[i]) * 1000, 1),
                        "how": "ctl start of llm-%d (python, --fake%s) until its sock exists" %
                               (i, "" if i == 0 else ", upstream = the one below")})
        # one proc: /usr/bin/true with only /usr etc., and the same in pi's whole sky
        for case, mk in (("proc-start-minimal", lambda nm: sb.proc_config(nm, ["/usr/bin/true"], aos_pi.base_sky(),
                                                                          {"PATH": "/usr/bin:/bin"})),
                         ("proc-start-pi-sky", lambda nm: sb.proc_config(nm, ["/usr/bin/true"], sb.sky(),
                                                                         dict(aos_pi.PI_ENV), cwd="/home/pi/work",
                                                                         locks=aos_pi.PI_LOCKS))):
            ctl_ms, end_ms = [], []
            for i in range(reps):
                nm = "%s-%d" % ("tmin" if case.endswith("minimal") else "tsky", i)
                t = time.perf_counter()
                sb.d.start_proc(mk(nm), sb.p(nm + ".json"))
                ctl_ms.append((time.perf_counter() - t) * 1000)
                dc.wait_for(lambda: sb.d.fact(nm, "state") == "dead\n", 10, 0.002)
                end_ms.append((time.perf_counter() - t) * 1000)
                sb.d.ctl("forget " + nm)
            out.append({"bench": "pisandbox", "case": case, "n": reps, "ctl_start_ms_median": r2(median(ctl_ms), 2),
                        "until_dead_ms_median": r2(median(end_ms), 2),
                        "how": "write 'start CONFIG' to ctl (returns when started), then poll procs/NAME/state"})
        # requests: 1 kernel, 2 stacked, through the relay
        for i, k in enumerate(sb.kernels):
            st, lat = _post_unix(os.path.join(k["dir"], "sock"), asks)
            out.append({"bench": "pisandbox", "case": "llm-request", "n": i + 1, "status": st, "asks": asks,
                        "ms_median": r2(median(lat), 3), "ms_p90": r2(sorted(lat)[len(lat) * 9 // 10], 3),
                        "how": "POST /v1/chat/completions over the unix socket of the %s kernel (fake answer)" %
                               ("bottom" if i == 0 else "top of %d stacked" % (i + 1))})
        node = sb.node
        port = _free_port()
        top = sb.kernels[-1]["dir"]
        relay = subprocess.Popen([node, os.path.join(top, "relay"), "--llm", top, "--port", str(port)],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        ok = dc.wait_for(lambda: _can_connect(port), 10, 0.02)
        if ok:
            st, lat = _post_tcp(port, asks)
            out.append({"bench": "pisandbox", "case": "llm-request-via-relay", "n": len(sb.kernels), "status": st,
                        "asks": asks, "ms_median": r2(median(lat), 3), "ms_p90": r2(sorted(lat)[len(lat) * 9 // 10], 3),
                        "how": "node /llm/relay on the host's loopback -> top kernel's socket (pi's path)"})
        else:
            out.append({"bench": "pisandbox", "case": "llm-request-via-relay", "error": "relay did not listen"})
    except Exception as e:  # noqa: BLE001
        out.append({"bench": "pisandbox", "case": "pieces", "error": "%s: %s" % (type(e).__name__, e)})
    finally:
        if relay and relay.poll() is None:
            relay.send_signal(signal.SIGTERM)
            try:
                relay.wait(5)
            except subprocess.TimeoutExpired:
                relay.kill()
                relay.wait()
        t = time.perf_counter()
        sb.stop()
        out.append({"bench": "pisandbox", "case": "daemon-stop", "ms": r2((time.perf_counter() - t) * 1000, 1),
                    "how": "SIGTERM to the daemon (no init: it SIGKILLs everything under it) until it exits"})

    # -- the whole thing: daemon + 1 llm kernel + pi, until pi's first request and until pi is done
    node, pkg = aos_pi.find_node()
    if not os.path.exists(os.path.join(pkg, "dist", "bundle", "cli.js")):
        out.append({"bench": "pisandbox", "case": "whole", "error": "no pi package at %s (not measured)" % pkg})
        return out
    for rep in range(1 if quick else 3):
        a = _args(aos_pi, pw, root, 1)
        sb = aos_pi.Sandbox(a)
        rec = {"bench": "pisandbox", "case": "whole-fake", "n": rep + 1,
               "how": "aos_pi.Sandbox start (daemon + 1 llm kernel --fake) then pi 'say hi'; first request = first "
                      "ledger line of the kernel"}
        try:
            t0 = time.perf_counter()
            sb.start()
            rec["daemon_and_kernel_ms"] = r2((time.perf_counter() - t0) * 1000, 1)
            res, t_pi = {}, time.perf_counter()
            th = threading.Thread(target=lambda: res.update(sb.run_pi("say hi", timeout=120)), daemon=True)
            th.start()
            led = os.path.join(sb.kernels[0]["state"], "ledger.jsonl")
            first = None
            while th.is_alive():
                if first is None and os.path.exists(led) and os.path.getsize(led) > 0:
                    first = time.perf_counter()
                time.sleep(0.005)
            th.join()
            t_end = time.perf_counter()
            rec["pi_start_to_first_request_ms"] = r2((first - t_pi) * 1000, 1) if first else None
            rec["start_to_first_request_ms"] = r2((first - t0) * 1000, 1) if first else None
            rec["pi_until_done_ms"] = r2((t_end - t_pi) * 1000, 1)
            rec["pi_done"], rec["turns"] = res.get("done"), res.get("turns")
        except Exception as e:  # noqa: BLE001
            rec["error"] = "%s: %s" % (type(e).__name__, e)
        finally:
            sb.stop()
        out.append(rec)
    shutil.rmtree(root, ignore_errors=True)
    return out


def _can_connect(port):
    s = socket.socket()
    try:
        s.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()
