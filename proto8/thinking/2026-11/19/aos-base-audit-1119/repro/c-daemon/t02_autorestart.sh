# t02: auto_restart crash loops: immediate exit 1, immediate exit 0, exit after 3.3s (beats the 3s window) -- cap, backoff, table display.
. "$HOME/.aos/scratch/aos-base-audit-1119/c-daemon/repro/common.sh"
mkd t02 50; startd || exit 1; echo "daemon pid $(dpid)"
mkscript "$D/die1.sh" 'echo "die1 at $(date +%T.%N)" >&2; exit 1'
mkscript "$D/die0.sh" 'echo "die0 at $(date +%T.%N)" >&2; exit 0'
mkscript "$D/die33.sh" 'echo "die33 at $(date +%T.%N)" >&2; sleep 3.3; exit 1'
echo "== add three auto-restart procs"
ctl add --auto-restart --name d1 "$D/die1.sh" >/dev/null
ctl add --auto-restart --name d0 "$D/die0.sh" >/dev/null
ctl add --auto-restart --name d33 "$D/die33.sh" >/dev/null
sleep 3; echo "-- after 3s"; rows
sleep 17; echo "-- after 20s"; rows
for n in d1 d0 d33; do echo "  $n starts: $(grep -c "^die" $S/procs/$n/stderr.txt)  first/last: $(head -1 $S/procs/$n/stderr.txt | cut -d' ' -f3) .. $(tail -1 $S/procs/$n/stderr.txt | cut -d' ' -f3)"; done
echo "-- d1 start times"; cut -d' ' -f3 $S/procs/d1/stderr.txt
echo "== ls"; ctl ls
echo "== start d1 again: counter reset?"; ctl start d1; sleep 2; rows | grep d1; echo "  d1 starts now: $(grep -c ^die $S/procs/d1/stderr.txt)"
echo "== non-auto-restart, exit 0 immediately -> off table; exit 1 -> stopped"
ctl add --name n0 "$D/die0.sh" >/dev/null; ctl add --name n1 "$D/die1.sh" >/dev/null; sleep 1.5; rows | grep -E " n[01] " ; echo "  n0 row: $(phase n0)"
shut; echo "  daemon $(alive $(dpid))"
grep -E '"d1"' "$D/daemon.log" | head -12
