# 測斷點已下好（觸發器在 stack 自己那份 hooks.json）之後，agent.py 重生時拿掉 HOOKS：斷點還停不停、庫怎麼說。經 clean 跑：bin/clean python3 repro/e10_regen_drops_hooks.py
import json, os, subprocess, sys, time
E = os.path.expanduser("~/.aos/scratch/aos-base-audit-1119/e-upper"); T = E + "/tree"; D = T + "/.stack"
sys.path.insert(0, os.environ["AOS_HOME"] + "/lib")
import aos.gdb as g
g.echo = False
def sh(c):
    r = subprocess.run(c, shell=True, cwd=T, capture_output=True, text=True, timeout=120)
    return (r.stdout + r.stderr).strip()
N = "e10"
sh("aos-agent -d .stack ctl rm --purge %s" % N)
sh("rm -rf defs/d10 && mkdir -p defs/d10 && cp %s/agentpy-src/agent.py defs/d10/ && cd defs/d10 && MARK=A HOOKS=1 python3 agent.py --write-defs" % E)
sh("aos-agent -d .stack ctl add -n %s -w . defs/d10" % N)
a = g.attach(N, daemon=D)
bp = a.bp.add("before_tool", tool="peek_now_time")
print("bp", bp, "stack hooks.json exists:", os.path.exists(D + "/procs/%s/hooks.json" % N))
print(sh("cd defs/d10 && MARK=A python3 agent.py --write-defs")[-40:], "| hooks.json still in def folder:", os.path.exists(T + "/defs/d10/hooks.json"))
print("interfaces hooks key:", json.load(open(T + "/defs/d10/interfaces.json"))["aos-agent"].get("hooks"))
l = a.say("should-stop")
try:
    a.bp.wait_stopped(timeout_s=10); print("stopped at breakpoint: yes")
except Exception as e:
    print("stopped at breakpoint: NO (%s)" % type(e).__name__)
print("answer:", sh("timeout 15 aos-agent -d .stack --target %s listen --timeout-s 10" % N)[-80:])
try: print("bp ls:", a.bp.ls())
except Exception as e: print("bp ls error:", str(e)[:200])
sh("aos-agent -d .stack ctl rm --purge %s" % N); sh("rm -rf defs/d10")
