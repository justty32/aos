# 測斷點庫 before_tool 扣住很久（預設 60 秒，HOLD=秒數可改）時：表上看得出嗎、時鐘走不走、信是否累積、ctl pause／daemon stop 收不收得掉、auto-restart 會不會誤判、最後 rm 會怎樣。經 clean 跑：bin/clean python3 repro/e4_long_hold.py
import json, os, subprocess, sys, time
E = os.path.expanduser("~/.aos/scratch/aos-base-audit-1119/e-upper"); T = E + "/tree"; D = T + "/.stack"
sys.path.insert(0, os.environ["AOS_HOME"] + "/lib")
import aos.gdb as g
g.echo = False
HOLD = int(os.environ.get("HOLD", "60"))
def sh(c, check=False):
    r = subprocess.run(c, shell=True, cwd=T, capture_output=True, text=True, timeout=120)
    return (r.stdout + r.stderr).strip()
def row(n): return json.load(open(D + "/procs_state.json"))["procs"].get(n)
def clock(): return open(D + "/clock").read().strip() if os.path.exists(D + "/clock") else None
NAME = "e4"
sh("aos-agent -d .stack ctl rm --purge %s" % NAME)
print(sh("aos-agent -d .stack ctl add -n %s --auto-restart -w . defs/d4" % NAME)[-120:])
a = g.attach(NAME, daemon=D)
bp = a.bp.add("before_tool", tool="peek_now_time")
first = a.say("held-one")
a.bp.wait_stopped()
h = a.bp.held(); pid0 = row(NAME)["pid"]
print("held:", h["event"], h["detail"]["name"], "loop pid", pid0, "stage", a.where())
c0 = clock(); t0 = time.time()
for i in range(3): a.say("queued-%d" % i)
print("ctl pause (no wait):", sh("aos-agent -d .stack ctl pause --no-wait %s" % NAME)[-100:])
print("daemon-level stop:", sh("timeout 10 aos-daemon-ctl -d .stack stop %s" % NAME)[-150:])
while time.time() - t0 < HOLD:
    time.sleep(HOLD / 4)
    r = row(NAME)
    print("t+%ds phase=%s pid=%s same_pid=%s clock %s->%s queue=%d held=%s stage=%s" % (
        time.time() - t0, r["phase"], r["pid"], r["pid"] == pid0, c0, clock(), len(a.queue()), bool(a.bp.held()), a.where()))
print("aos-agent ctl ls:", [l for l in sh("aos-agent -d .stack ctl ls").splitlines() if NAME in l])
print("ctl state:", sh("aos-agent -d .stack --target %s ctl state" % NAME)[:300])
print("== now rm while held+stopping")
t1 = time.time(); print(sh("timeout 60 aos-agent -d .stack ctl rm %s" % NAME)[-200:]); print("rm took %.1fs" % (time.time() - t1))
print("row after rm:", row(NAME))
print("hold pid alive:", os.path.exists("/proc/%d" % h["pid"]))
print("notes:", [n.get("kind") for n in a.bp.notes()][-3:])
print("queue left in stack:", len(os.listdir(D + "/procs/%s/queue/new" % NAME)) if os.path.isdir(D + "/procs/%s/queue/new" % NAME) else "no queue/new")
tool_ran = [m for m in a.history(0) if m.get("role") == "tool"]
print("tool results in history:", len(tool_ran))
