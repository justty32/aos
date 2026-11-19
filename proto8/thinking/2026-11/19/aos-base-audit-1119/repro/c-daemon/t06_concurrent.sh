# t06: many aos-daemon-ctl commands at once: 10 parallel add of one name, 20 parallel add of distinct names, mixed stop/start/rm; check table integrity, lost commands, half-written json.
. "$HOME/.aos/scratch/aos-base-audit-1119/c-daemon/repro/common.sh"
mkd t06 50; startd || exit 1; echo "daemon pid $(dpid)"
mkscript "$D/a.sh" 'echo "$$ $1" >> "$AOS_STACK/who.txt"; exec sleep 600'
# background JSON validity watcher on procs_state.json / state.json / state_flux.json
python3 - "$S" > "$D/watch.txt" 2>&1 <<'PY' &
import json, sys, time, os
s = sys.argv[1]; bad = 0; n = 0; end = time.time() + 25
while time.time() < end:
    for f in ("procs_state.json", "state.json", "state_flux.json"):
        try:
            with open(os.path.join(s, f)) as fh: t = fh.read()
            json.loads(t); n += 1
        except FileNotFoundError: pass
        except ValueError as e: bad += 1; print("BAD", f, repr(t[:80]), e)
    time.sleep(0.002)
print("reads", n, "bad", bad)
PY
W=$!
echo "== 10 parallel add of the same name 'same'"
pids=""; for i in $(seq 10); do ( ctl add --name same "$D/a.sh" -- v$i > "$D/same.$i.out" 2>&1; echo "exit $?" >> "$D/same.$i.out" ) & pids="$pids $!"; done; wait $pids
grep -h exit "$D"/same.*.out | sort | uniq -c; grep -h error "$D"/same.*.out | cut -c1-80 | sort | uniq -c
sleep 2; echo "  row: $(phase same) pid=$(ppid_of same); started: $(wc -l < $S/procs/same/who.txt) times:"; cat $S/procs/same/who.txt
echo "  alive sleep copies for 'same': $(for p in $(cut -d' ' -f1 $S/procs/same/who.txt); do alive $p; done | grep -c alive)"
echo "== 20 parallel add of distinct names"
pids=""; for i in $(seq 20); do ctl add --name p$i "$D/a.sh" >/dev/null 2>"$D/p$i.err" & pids="$pids $!"; done; wait $pids
sleep 2; echo "  rows running: $(rows | grep -c ' running ') of $(rows | wc -l); errors: $(cat $D/p*.err | wc -l)"; cat $D/p*.err | head -3
echo "== mixed: parallel stop p1-5, sleep p6-10, rm p11-15, start p1 (while stopping), wake p6"
pids=""; for i in 1 2 3 4 5; do ctl stop p$i >/dev/null 2>>"$D/mix.err" & pids="$pids $!"; done
for i in 6 7 8 9 10; do ctl sleep p$i >/dev/null 2>>"$D/mix.err" & pids="$pids $!"; done
for i in 11 12 13 14 15; do ctl rm p$i >/dev/null 2>>"$D/mix.err" & pids="$pids $!"; done; wait $pids
sleep 3; rows | awk '{print $2}' | sort | uniq -c; echo "  mix errors:"; cat "$D/mix.err" | cut -c1-120
echo "== 10 parallel stop+start+sleep+wake+rm+add on ONE name (race storm)"
ctl add --name storm "$D/a.sh" >/dev/null; waitphase storm running
pids=""; for c in sleep wake sleep wake rm add sleep wake rm add; do if [ $c = add ]; then ctl add --name storm "$D/a.sh" >/dev/null 2>>"$D/storm.err" & else ctl $c storm >/dev/null 2>>"$D/storm.err" & fi; pids="$pids $!"; done; wait $pids
sleep 3; echo "  storm: $(phase storm); starts: $(wc -l < $S/procs/storm/who.txt); alive copies: $(for p in $(cut -d' ' -f1 $S/procs/storm/who.txt); do alive $p; done | grep -c alive)"
cut -c1-120 "$D/storm.err" | sort | uniq -c
echo "== mailbox leftovers"; for d in new cur tmp; do echo "  $d: $(ls $S/procs_requests/$d 2>/dev/null | wc -l)"; done
wait $W; echo "== json watcher"; tail -3 "$D/watch.txt"
grep -i warn "$D/daemon.err" | head -5
echo "== daemon CPU (ticks)"; awk '{print "utime",$14,"stime",$15}' /proc/$(dpid)/stat
shut >/dev/null; echo "  daemon $(alive $(dpid))"
for f in $S/procs/*/who.txt; do for p in $(cut -d' ' -f1 $f); do [ "$(alive $p)" = alive ] && { echo "  survivor $p"; killmine 9 $p; }; done; done
