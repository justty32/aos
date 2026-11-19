#!/usr/bin/env python3
# E2: while the daemon body (where a kernel station runs) is busy, the daemon does not tend: auto_restart, ping letters and child exits all wait. Also shows a proc stdout is /dev/null.
import json, os, subprocess, sys, time, pathlib, shutil
root = pathlib.Path(__file__).resolve().parents[1] / "e2"
shutil.rmtree(root, ignore_errors=True); (root / "stack").mkdir(parents=True)
slow = root / "slow.sh"; slow.write_text("#!/bin/sh\nsleep 12\nexit 0\n"); slow.chmod(0o755)
flap = root / "flap.sh"; flap.write_text("#!/bin/sh\ndate +%s.%N >> " + str(root) + "/flap.log\necho to-stdout\nsleep 4\nexit 0\n"); flap.chmod(0o755)
(root / "daemon.json").write_text(json.dumps({"interval_ms": 100, "exec": [str(slow)], "procs": {"flap": {"exec": [str(flap)], "auto_restart": True}}}))
env = dict(os.environ, AOS_STACK=str(root / "stack"))
p = subprocess.Popen(["aos-daemon", "--enable-logs", str(root / "daemon.json")], cwd=root, env=env, stdout=open(root / "d.out", "w"), stderr=open(root / "d.err", "w"))
print("daemon pid", p.pid)
time.sleep(2.0)
st = json.load(open(root / "stack/procs_state.json")); fp = st["procs"]["flap"]["pid"]
print("flap pid", fp, "stdout ->", os.readlink("/proc/%d/fd/1" % fp), "stderr ->", os.readlink("/proc/%d/fd/2" % fp))
box = root / "box"; subprocess.run(["aos-post", "init", str(box)], check=True)
t0 = time.time()
subprocess.run(["aos-post", "send", "--reply-to", str(box), str(root / "stack/procs_requests")], input=b"{\"ping\":true}", check=True, stdout=subprocess.DEVNULL)
while time.time() - t0 < 30 and not os.listdir(box / "new"): time.sleep(0.05)
print("ping answered after %.1fs (interval_ms is 100)" % (time.time() - t0))
time.sleep(26 - (time.time() - t0))
ts = [float(x) for x in open(root / "flap.log").read().split()]
print("flap starts:", len(ts), "gaps:", ["%.1f" % (b - a) for a, b in zip(ts, ts[1:])], "(flap runs 4s; without a body the gaps are ~4s)")
subprocess.run(["aos-daemon-ctl", "-d", str(root / "stack"), "shutdown"], timeout=90)
try: p.wait(40)
except subprocess.TimeoutExpired: p.kill(); print("had to kill daemon")
print("daemon exit", p.returncode)
