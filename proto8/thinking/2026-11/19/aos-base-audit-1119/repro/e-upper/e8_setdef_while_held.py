# 測斷點扣住（before_tool）時對那隻下 ctl set-def：set-def 逾時說「沒改」之後，放行時那隻會怎樣（停掉？換了定義？）。經 clean 跑：bin/clean python3 repro/e8_setdef_while_held.py
import json, os, subprocess, sys, time
E = os.path.expanduser("~/.aos/scratch/aos-base-audit-1119/e-upper"); T = E + "/tree"; D = T + "/.stack"
sys.path.insert(0, os.environ["AOS_HOME"] + "/lib")
import aos.gdb as g
g.echo = False
def sh(c):
    r = subprocess.run(c, shell=True, cwd=T, capture_output=True, text=True, timeout=120)
    return "rc=%d %s" % (r.returncode, (r.stdout + r.stderr).strip())
def row(n): return json.load(open(D + "/procs_state.json"))["procs"].get(n)
N = "e8"
sh("aos-agent -d .stack ctl rm --purge %s" % N)
sh("rm -rf defs/d8 && mkdir -p defs/d8 && cp %s/agentpy-src/agent.py defs/d8/ && cd defs/d8 && MARK=B HOOKS=1 python3 agent.py --write-defs" % E)
print(sh("aos-agent -d .stack ctl add -n %s --auto-restart -w . defs/d4" % N)[-60:])
a = g.attach(N, daemon=D)
a.bp.add("before_tool", tool="peek_now_time", once=True)
l = a.say("x"); a.bp.wait_stopped()
print("held; row:", row(N)["phase"], row(N)["def"])
t = time.time(); print("set-def:", sh("aos-agent -d .stack ctl set-def --timeout-s 5 %s defs/d8" % N)[-400:], "(%.0fs)" % (time.time() - t))
print("row after set-def failed:", row(N)["phase"], row(N)["def"])
print("release:", a.bp.resume()[-80:])
time.sleep(6)
r = row(N); print("row 6s after release:", r and (r["phase"], r["def"], r.get("reason")))
print("letter answered?", sh("timeout 15 aos-agent -d .stack --target %s listen --timeout-s 8" % N)[-160:])
sh("aos-agent -d .stack ctl rm --purge %s" % N); sh("rm -rf defs/d8")
