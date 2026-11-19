# 測斷點庫的觀察者 proc（a.bp.add("watch")）在目標被 stop、被 start、被 rm、被 rm 後同名換 stack 加回來時的行為。經 clean 跑：bin/clean python3 repro/e6_watcher_target_life.py
import json, os, subprocess, sys, time
E = os.path.expanduser("~/.aos/scratch/aos-base-audit-1119/e-upper"); T = E + "/tree"; D = T + "/.stack"
sys.path.insert(0, os.environ["AOS_HOME"] + "/lib")
import aos.gdb as g
from aos.gdb import watcher
g.echo = False
FLAG = E + "/e6.flag"
def sh(c):
    r = subprocess.run(c, shell=True, cwd=T, capture_output=True, text=True, timeout=120)
    return (r.stdout + r.stderr).strip()
def row(n): return json.load(open(D + "/procs_state.json"))["procs"].get(n)
def st(stack): return json.load(open(stack + "/state.json"))
def wls(): return [(w["name"], w["phase"], w["per_target"]) for w in watcher.ls(D)]
N = "e6"
if os.path.exists(FLAG): os.unlink(FLAG)
sh("aos-agent -d .stack ctl rm --purge %s" % N)
sh("aos-agent -d .stack ctl add -n %s -w . defs/d4" % N)
a = g.attach(N, daemon=D)
w = a.bp.add("watch", sh="test -f %s || exit 10" % FLAG, every_ms=300)
print("watcher", w, wls())
stack = D + "/procs/" + N
print("== 1. stop target, then the condition becomes true while it is stopped")
print(sh("timeout 60 aos-agent -d .stack ctl stop %s" % N)[-80:])
open(FLAG, "w").close(); time.sleep(4)
print(" target row:", row(N)["phase"], "| watcher:", wls())
print(" target notes:", [(x.get("kind"), x.get("by"), x.get("detail", {}).get("stage")) for x in a.bp.notes()])
print(" target ctl.json:", open(stack + "/ctl.json").read().strip())
os.unlink(FLAG); time.sleep(1)
print("== 2. start target (flag gone now)")
print(sh("timeout 60 aos-agent -d .stack ctl start %s" % N)[-80:]); time.sleep(3)
print(" target row:", row(N)["phase"], "| state.json paused:", st(stack).get("paused"))
l = a.say("after-start"); 
print(" answer:", sh("timeout 15 aos-agent -d .stack --target %s listen --timeout-s 10" % N)[-120:])
sh("timeout 30 aos-agent -d .stack ctl resume %s" % N)
print(" after resume answer:", sh("timeout 20 aos-agent -d .stack --target %s listen --timeout-s 15" % N)[-80:])
print("== 3. rm target (stack kept), flag true")
print(sh("timeout 60 aos-agent -d .stack ctl rm %s" % N)[-80:])
open(FLAG, "w").close(); time.sleep(4)
print(" watcher:", wls())
print(" watcher stderr tail:", sh("tail -2 .stack/procs/gdbw_%s/stderr.txt 2>/dev/null; ls .stack/procs/gdbw_%s" % (w, w))[-400:])
os.unlink(FLAG)
print("== 4. same name added back on another stack")
sh("timeout 60 aos-agent -d .stack ctl add -n %s -s %s/e6b-stack -w . defs/d4" % (N, E)); time.sleep(2)
open(FLAG, "w").close(); time.sleep(8)
print(" new target paused?", st(E + "/e6b-stack").get("paused"), "| old stack ctl:", open(stack + "/ctl.json").read().strip()[-60:])
print(" watcher:", wls())
os.unlink(FLAG)
print("== cleanup"); print(a.bp.rm(w) if hasattr(a.bp, "rm") else "")
sh("timeout 60 aos-agent -d .stack ctl rm --purge %s" % N); sh("rm -rf %s/e6b-stack" % E)
print(" left:", [l for l in sh("aos-daemon-ctl -d .stack ls").splitlines() if "e6" in l or "gdbw" in l])
