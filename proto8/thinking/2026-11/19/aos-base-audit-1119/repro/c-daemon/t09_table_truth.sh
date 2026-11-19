# t09: does the table (ls / procs_state.json) match reality: external kill -9 latency, SIGSTOP'd proc, dead daemon, pid reuse check.
. "$HOME/.aos/scratch/aos-base-audit-1119/c-daemon/repro/common.sh"
mkd t09 200; startd || exit 1; echo "daemon pid $(dpid) (interval_ms 200)"
mkscript "$D/sl.sh" 'exec sleep 600'
for n in a b c; do ctl add --name $n "$D/sl.sh" >/dev/null; done; waitphase a running; waitphase b running; waitphase c running
echo "== external kill -9 of a; poll procs_state.json every 10 ms"
A=$(ppid_of a); t0=$(now); killmine 9 $A
python3 - "$S" "$t0" <<'PY'
import json, sys, time
s, t0 = sys.argv[1], float(sys.argv[2])
while time.time() - t0 < 5:
    try: r = json.load(open(s + "/procs_state.json"))["procs"].get("a")
    except ValueError: continue
    if r and r["phase"] != "running":
        print("  table says %s after %.3fs (code %s signal %s)" % (r["phase"], time.time() - t0, r["code"], r["signal"])); break
    time.sleep(0.01)
PY
echo "== SIGSTOP b: table?"; B=$(ppid_of b); killmine STOP $B; sleep 1; echo "  b=$(phase b) /proc state=$(awk '{print $3}' /proc/$B/stat)"; ctl ls | grep "^b"; killmine CONT $B
echo "== kill -9 daemon; what does ls say?"; killmine 9 $(dpid); sleep 0.3; ctl ls; echo "  (c real: $(alive $(ppid_of c)))"
echo "== external kill c while daemon is dead, then ls (still dead)"; killmine 9 $(ppid_of c); sleep 0.2; ctl ls | head -3
echo "== restart"; startd; sleep 1; ctl ls
shut >/dev/null; echo "daemon $(alive $(dpid))"
