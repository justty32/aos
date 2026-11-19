#!/usr/bin/env python3
# E3: daemon is kill -9ed and its procs_state.json is unusable (stand-in for "forked but table not yet written"): an exec-type proc is started a second time on the same stack while the first still runs.
import json, os, signal, subprocess, time, pathlib, shutil
root = pathlib.Path(__file__).resolve().parents[1] / "e3"
shutil.rmtree(root, ignore_errors=True); (root / "stack").mkdir(parents=True)
job = root / "job.sh"; job.write_text("#!/bin/sh\necho $$ >> " + str(root) + "/pids.log\nexec sleep 300\n"); job.chmod(0o755)
(root / "daemon.json").write_text(json.dumps({"interval_ms": 50, "procs": {"once": {"exec": [str(job)]}, "looped": {"exec": [str(job)], "interval_ms": 1000}}}))
env = dict(os.environ, AOS_STACK=str(root / "stack"))
def start():
    return subprocess.Popen(["aos-daemon", str(root / "daemon.json")], cwd=root, env=env, stdout=open(root / "d.out", "a"), stderr=open(root / "d.err", "a"))
p = start(); time.sleep(2)
print("first daemon", p.pid, "job pids:", open(root / "pids.log").read().split())
os.kill(p.pid, signal.SIGKILL); p.wait()
(root / "stack/procs_state.json").write_text("{")          # table lost
p = start(); time.sleep(3)
pids = [int(x) for x in open(root / "pids.log").read().split()]
alive = [x for x in pids if os.path.exists("/proc/%d" % x)]
print("after restart job pids:", pids, "alive:", alive)
st = json.load(open(root / "stack/procs_state.json"))
print("table:", {n: (r["pid"], r["phase"]) for n, r in st["procs"].items()})
print("flux adopt_warning:", json.load(open(root / "stack/state_flux.json")).get("adopt_warning"))
subprocess.run(["aos-daemon-ctl", "-d", str(root / "stack"), "shutdown"], timeout=60)
try: p.wait(30)
except subprocess.TimeoutExpired: p.kill()
time.sleep(1)
for x in pids:
    if os.path.exists("/proc/%d" % x) and os.readlink("/proc/%d/cwd" % x).startswith(str(root)):
        print("leftover (not on any table) pid", x, "-> killing"); os.kill(x, 15)
