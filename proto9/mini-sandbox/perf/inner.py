"""Runs where the agent (pi) would run, at the inside of a mini --kernels chain: stat, open, listdir, fork, exec, touching memory, asking the llm kernel through its socket, and small/large HTTP through the net kernel; prints one line BENCH {json}."""
# usage: python3 -I inner.py [--llm] [--url http://ADDR:PORT/] [--quick]
# Standard library only; copied into the run's temp folder by minibench.py so a uid kernel can still read it.
import json
import os
import socket
import subprocess
import sys
import time


def per(fn, n):
    t = time.perf_counter()
    for _ in range(n):
        fn()
    return round((time.perf_counter() - t) / n * 1e6, 2)


def main():
    args = sys.argv[1:]
    quick = "--quick" in args
    k = 5 if quick else 1  # --quick: a fifth of the loops
    out = {"mounts": sum(1 for _ in open("/proc/self/mountinfo"))}
    env = os.environ.get("AOS_ENV", "")
    if env and os.path.isdir(os.path.join(env, ".aos")):
        n = b = 0
        for dp, _, fns in os.walk(os.path.join(env, ".aos")):
            for f in fns:
                try:
                    b += os.lstat(os.path.join(dp, f)).st_size
                    n += 1
                except OSError:
                    pass
        out["aos_files"], out["aos_bytes"] = n, b
        try:
            out["layers_listed"] = len([l for l in open(os.path.join(env, ".aos", "kernels")) if l.strip()])
        except OSError:
            pass
    out["stat_us"] = per(lambda: os.stat("/usr/bin/ls"), 20000 // k)

    def op():
        with open("/etc/hostname" if os.path.exists("/etc/hostname") else "/etc/passwd", "rb") as f:
            f.read(256)
    out["open_read_us"] = per(op, 20000 // k)
    out["listdir_usrbin_us"] = per(lambda: os.listdir("/usr/bin"), 200 // k)

    def fk():
        p = os.fork()
        if p == 0:
            os._exit(0)
        os.waitpid(p, 0)
    out["fork_us"] = per(fk, 500 // k)
    out["exec_ls_ms"] = round(per(lambda: subprocess.run(["ls", "/"], stdout=subprocess.DEVNULL), 50 // k) / 1000, 3)
    t = time.perf_counter()
    a = bytearray(256 << 20)
    for i in range(0, len(a), 4096):
        a[i] = 1
    out["touch256M_ms"] = round((time.perf_counter() - t) * 1000, 1)
    del a
    if "--llm" in args and env:
        d = os.path.join(env, ".aos", "interfaces", "aos", "llm")
        path = open(os.path.join(d, "path")).read().strip()
        body = json.dumps({"model": "fake-model", "messages": [{"role": "user", "content": "hi"}]}).encode()
        req = (b"POST /v1/chat/completions HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\n"
               b"Content-Length: %d\r\nConnection: close\r\n\r\n" % len(body)) + body
        lat, r = [], b""
        for _ in range(max(30 // k, 5)):
            t = time.perf_counter()
            s = socket.socket(socket.AF_UNIX)
            s.connect(path)
            s.sendall(req)
            r = b""
            while True:
                c = s.recv(65536)
                if not c:
                    break
                r += c
            s.close()
            lat.append((time.perf_counter() - t) * 1000)
        lat.sort()
        out["llm_status"] = r.split(b"\r\n", 1)[0].decode(errors="replace")
        out["llm_ms_median"] = round(lat[len(lat) // 2], 3)
    if "--url" in args:
        url = args[args.index("--url") + 1]
        fmt = "%{http_code} %{time_total}"
        lat = []
        for _ in range(20 // k):
            r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", fmt, url + "small"], capture_output=True, text=True)
            code, tt = r.stdout.split()
            lat.append(float(tt) * 1000)
        lat.sort()
        out["curl_small_code"], out["curl_small_ms_median"] = code, round(lat[len(lat) // 2], 3)
        r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code} %{speed_download}", url + "big"],
                           capture_output=True, text=True)
        code, speed = r.stdout.split()
        out["curl_down_code"], out["curl_down_MBps"] = code, round(float(speed) / 1e6, 1)
        r = subprocess.run(["sh", "-c", "head -c 100000000 /dev/zero | curl -s -o /dev/null -w '%{http_code} "
                            "%{speed_upload}' -X PUT --data-binary @- " + url + "up"], capture_output=True, text=True)
        code, speed = r.stdout.split()
        out["curl_up_code"], out["curl_up_MBps"] = code, round(float(speed) / 1e6, 1)
    print("BENCH " + json.dumps(out), flush=True)


main()
