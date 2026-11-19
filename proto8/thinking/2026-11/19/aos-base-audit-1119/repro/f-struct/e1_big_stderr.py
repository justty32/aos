#!/usr/bin/env python3
# E1: a failing proc whose stderr.txt is huge -> daemon reads the whole file into memory in fail_reason (failure.cpp:22). argv: SIZE_MB [ULIMIT_V_MB]
import json, os, resource, subprocess, sys, time, pathlib, shutil
size_mb = int(sys.argv[1]); cap = int(sys.argv[2]) if len(sys.argv) > 2 else 0
root = pathlib.Path(__file__).resolve().parents[1] / ("e1-%d-%d" % (size_mb, cap))
shutil.rmtree(root, ignore_errors=True); (root / "stack/procs/job").mkdir(parents=True)
fail = root / "fail.sh"; fail.write_text("#!/bin/sh\nsleep 4\necho boom >&2\nexit 3\n"); fail.chmod(0o755)
(root / "daemon.json").write_text(json.dumps({"interval_ms": 50, "procs": {"job": {"exec": [str(fail)]}, "ok": {"exec": ["/bin/sleep", "600"]}}}))
with open(root / "stack/procs/job/stderr.txt", "wb") as f: f.truncate((size_mb << 20) - 1); f.seek(0, 2); f.write(bytes([10]))   # sparse, ends with a newline like a real log
env = {k: v for k, v in os.environ.items()}; env["AOS_STACK"] = str(root / "stack")
def pre():
    if cap: resource.setrlimit(resource.RLIMIT_AS, (cap << 20, cap << 20))
p = subprocess.Popen(["aos-daemon", str(root / "daemon.json")], cwd=root, env=env, stdout=open(root / "d.out", "w"), stderr=open(root / "d.err", "w"), preexec_fn=pre)
print("daemon pid", p.pid, "root", root)
hwm = 0; t0 = time.time(); gap = 0; last = None
while time.time() - t0 < 25:
    try:
        for line in open("/proc/%d/status" % p.pid):
            if line.startswith("VmHWM"): hwm = max(hwm, int(line.split()[1]))
    except OSError: pass
    if p.poll() is not None: break
    try:
        row = json.load(open(root / "stack/procs_state.json"))["procs"].get("job")
        if row and row["phase"] == "stopped": print("job stopped after %.1fs reason=%r" % (time.time() - t0, row["reason"][-120:])); break
    except (OSError, ValueError, KeyError): pass
    time.sleep(0.05)
print("daemon alive:", p.poll() is None, "exit:", p.poll(), "VmHWM_kB:", hwm)
print("d.err:", open(root / "d.err").read()[-400:])
if p.poll() is None:
    subprocess.run(["aos-daemon-ctl", "-d", str(root / "stack"), "shutdown"], timeout=60)
    try: p.wait(30)
    except subprocess.TimeoutExpired: p.kill()
else:
    st = json.load(open(root / "stack/procs_state.json"))
    for n, r in st["procs"].items():
        print("orphan check", n, r.get("pid"), r.get("phase"), "alive" if r.get("pid") and os.path.exists("/proc/%d" % r["pid"]) else "gone")
        if n == "ok" and r.get("pid") and os.path.exists("/proc/%d" % r["pid"]) and os.readlink("/proc/%d/cwd" % r["pid"]).startswith(str(root)): os.kill(r["pid"], 15)
os.remove(root / "stack/procs/job/stderr.txt")
