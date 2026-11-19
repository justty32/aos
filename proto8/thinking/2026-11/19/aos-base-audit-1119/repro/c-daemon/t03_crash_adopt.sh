# t03: daemon kill -9 / kill -TERM: do live procs survive, get adopted (no duplicates), what happens to procs that died meanwhile, locks.
. "$HOME/.aos/scratch/aos-base-audit-1119/c-daemon/repro/common.sh"
mkd t03 50; startd || exit 1; echo "daemon pid $(dpid)"
mkscript "$D/sl.sh" 'exec sleep 600'
mkscript "$D/noterm.sh" 'trap "" TERM
while :; do sleep 1; done'
echo '{"exec": {"argv": ["sleep", "0.2"]}, "interval_ms": 100}' > "$D/lp.json"
count_cells() { # how many live processes have AOS_STACK-cell cwd under this stack (proc trees)
  local n=0 p c; for p in /proc/[0-9]*; do c=$(readlink $p/cwd 2>/dev/null); case "$c" in "$S"/procs/*|"$D") n=$((n+1));; esac; done; echo $n; }
ctl add --name sl "$D/sl.sh" >/dev/null; ctl add --name lp "$D/lp.json" >/dev/null
ctl add --name ar --auto-restart "$D/sl.sh" >/dev/null; ctl add --name sl2 "$D/sl.sh" >/dev/null
waitphase sl running; waitphase lp running; waitphase ar running; waitphase sl2 running; sleep 0.5; rows
SL=$(ppid_of sl); LP=$(ppid_of lp); AR=$(ppid_of ar); SL2=$(ppid_of sl2)
echo "  procs under tree: $(count_cells)"
echo "== kill -9 daemon $(dpid)"; killmine 9 $(dpid); sleep 0.3
echo "  daemon $(alive $(dpid)); sl $(alive $SL) ppid=$(ps -o ppid= -p $SL); lp $(alive $LP); ar $(alive $AR)"
echo "  table on disk still says:"; rows
echo "  lock: flock -n on stack -> $(flock -n $S true && echo free || echo held)"
echo "== while daemon is dead: kill -9 sl (no auto_restart) and ar (auto_restart); kill -TERM sl2"
killmine 9 $SL; killmine 9 $AR; killmine 15 $SL2; sleep 0.3
echo "== restart daemon"; startd || exit 1; echo "  new daemon $(dpid)"; sleep 1; rows
echo "  lp pid same? old=$LP now=$(ppid_of lp); procs under tree: $(count_cells)"
grep -h adopt "$D/daemon.log" | tail -3; tail -n 3 "$D/daemon.err"
echo "== adopted lp: kill -9 it from outside; how long until table updates, and to what?"
LP=$(ppid_of lp); t0=$(now); killmine 9 $LP
for i in $(seq 100); do [ "$(ppid_of lp)" != "$LP" ] && break; sleep 0.05; done; echo "  table changed after $(since $t0)s -> $(row lp)"
echo "== daemon-born proc killed -9 from outside: table update latency"
ctl add --name k9 "$D/sl.sh" >/dev/null; waitphase k9 running; K=$(ppid_of k9); t0=$(now); killmine 9 $K
for i in $(seq 100); do [ "$(phase k9)" != running ] && break; sleep 0.02; done; echo "  table changed after $(since $t0)s -> $(phase k9) $(row k9 | python3 -c 'import json,sys;r=json.load(sys.stdin);print(r["code"],r["signal"],r["reason"])')"
echo "== kill -9 daemon while nt (TERM-ignoring) is being slept"
ctl add --name nt "$D/noterm.sh" >/dev/null; waitphase nt running; NT=$(ppid_of nt)
ctl sleep nt >/dev/null; sleep 1; echo "  nt phase=$(phase nt) stop_mode=$(row nt | python3 -c 'import json,sys;print(json.load(sys.stdin).get("stop_mode"))')"
killmine 9 $(dpid); sleep 0.3; startd || exit 1; t0=$(now); waitphase nt sleeping 20; echo "  after restart nt sleeping in $(since $t0)s; old nt $(alive $NT)"
echo "== second daemon on same stack"; ( cd $D; AOS_STACK=$S timeout 5 aos-daemon $D/daemon.json; echo "  exit $?" ) 2>&1 | tail -2
echo "== kill -TERM daemon (graceful) then restart"; rows; killmine 15 $(dpid); for i in $(seq 300); do [ "$(alive $(dpid))" = dead ] && break; sleep 0.05; done; echo "  daemon $(alive $(dpid))"; rows
startd; sleep 1; echo "  after restart:"; rows; echo "  procs under tree: $(count_cells)"
shut >/dev/null; echo "  final daemon $(alive $(dpid)); procs under tree: $(count_cells)"
