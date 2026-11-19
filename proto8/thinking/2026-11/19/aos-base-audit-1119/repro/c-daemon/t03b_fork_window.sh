# t03b: kill -9 the daemon right after it forks a batch of exec-type procs but before the table is written: are they started twice after restart?
. "$HOME/.aos/scratch/aos-base-audit-1119/c-daemon/repro/common.sh"
KIND=${1:-exec}   # exec | loop
mkd t03b-$KIND 50; startd || exit 1; echo "daemon pid $(dpid) kind=$KIND"
mkscript "$D/sl.sh" 'echo $$ >> "$AOS_STACK/pids"; exec sleep 300'
python3 - "$S" "$D" "$KIND" <<'PY'
import json, sys
S, D, kind = sys.argv[1:]
spec = (lambda i: D + "/sl.sh") if kind == "exec" else (lambda i: {"exec": D + "/sl.sh", "interval_ms": 1000})
added = {"p%02d" % i: spec(i) for i in range(40)}
tmp = S + "/.procs_ctl.json"; json.dump({"seq": 1, "procs_added": added}, open(tmp, "w")); import os; os.rename(tmp, S + "/procs_ctl.json")
PY
for i in $(seq 400); do ls $S/procs/*/pids >/dev/null 2>&1 && break; sleep 0.005; done
killmine 9 $(dpid); echo "killed daemon after first proc wrote its pid"
sleep 0.3; echo "  rows in table at kill: $(python3 -c "import json;print(len(json.load(open('$S/procs_state.json'))['procs']))")  cells with a live proc: $(ls $S/procs | wc -l)"
startd; sleep 4
python3 - "$S" <<'PY'
import json, os, sys
S = sys.argv[1]; dup = 0; tot = 0
rows = json.load(open(S + "/procs_state.json"))["procs"]
for n in sorted(os.listdir(S + "/procs")):
    try: pids = open(S + "/procs/%s/pids" % n).read().split()
    except OSError: continue
    live = [p for p in pids if os.path.exists("/proc/" + p)]
    tot += len(live)
    if len(live) > 1: dup += 1; print("  DUP", n, "live pids", live, "table pid", rows.get(n, {}).get("pid"))
print("  live procs:", tot, "cells with >1 live copy:", dup, "rows:", len(rows))
PY
shut >/dev/null; echo "daemon $(alive $(dpid))"
left=0; for f in $S/procs/*/pids; do for p in $(cat $f); do if [ "$(alive $p)" = alive ]; then left=$((left+1)); killmine 9 $p; fi; done; done; echo "  survivors after shutdown (killed now): $left"
