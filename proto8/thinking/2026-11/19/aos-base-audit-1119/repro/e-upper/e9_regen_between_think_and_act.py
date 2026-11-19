# 測腦（think）照舊版 tools 選了工具、在 act 跑之前定義重生拿掉那支工具：act 會怎樣（用 before_tool 斷點把時間點卡住）。經 clean 跑：bin/clean python3 repro/e9_regen_between_think_and_act.py
import json, os, subprocess, sys, time
E = os.path.expanduser("~/.aos/scratch/aos-base-audit-1119/e-upper"); T = E + "/tree"; D = T + "/.stack"
sys.path.insert(0, os.environ["AOS_HOME"] + "/lib")
import aos.gdb as g
g.echo = False
def sh(c):
    r = subprocess.run(c, shell=True, cwd=T, capture_output=True, text=True, timeout=120)
    return (r.stdout + r.stderr).strip()
N = "e9"
sh("aos-agent -d .stack ctl rm --purge %s" % N)
sh("rm -rf defs/d9 && mkdir -p defs/d9 && cp %s/agentpy-src/agent.py defs/d9/ && cd defs/d9 && MARK=A HOOKS=1 python3 agent.py --write-defs" % E)
sh("aos-agent -d .stack ctl add -n %s -w . defs/d9" % N)
a = g.attach(N, daemon=D)
a.bp.add("before_tool", tool="peek_now_time", once=True)
l = a.say("x"); a.bp.wait_stopped()
print("held at", a.bp.held()["detail"]["name"])
print(sh("cd defs/d9 && MARK=B HOOKS=1 python3 agent.py --write-defs")[-60:])
a.bp.resume()
print("answer:", sh("timeout 25 aos-agent -d .stack --target %s listen --timeout-s 20" % N)[-200:])
print("tool message:", [m.get("content")[:200] for m in a.history(0) if m.get("role") == "tool"])
sh("aos-agent -d .stack ctl rm --purge %s" % N); sh("rm -rf defs/d9")
