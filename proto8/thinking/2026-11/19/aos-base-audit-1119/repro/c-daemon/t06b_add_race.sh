# t06b: racing "add" of one name: several callers told OK, one runs; after sleep/wake, which caller's config runs?
. "$HOME/.aos/scratch/aos-base-audit-1119/c-daemon/repro/common.sh"
mkd t06b 50; startd || exit 1; echo "daemon pid $(dpid)"
mkscript "$D/a.sh" 'echo "$$ $1" >> "$AOS_STACK/who.txt"; exec sleep 600'
for round in 1 2 3; do
  ctl rm same >/dev/null 2>&1; for i in $(seq 30); do [ "$(phase same)" = NOROW ] && break; sleep 0.1; done
  pids=""; for i in $(seq 10); do ( ctl add --name same "$D/a.sh" -- r${round}v$i >/dev/null 2>&1 && echo r${round}v$i >> "$D/ok.txt" ) & pids="$pids $!"; done; wait $pids
  sleep 1.5; echo "round $round: told OK: $(grep -c "^r${round}v" $D/ok.txt) [$(grep "^r${round}v" $D/ok.txt | tr '\n' ' ')] running: $(tail -1 $S/procs/same/who.txt)"
  ctl sleep same >/dev/null; waitphase same sleeping; ctl wake same >/dev/null; waitphase same running; sleep 0.5
  echo "   after sleep+wake running: $(tail -1 $S/procs/same/who.txt); launch=$(row same | python3 -c 'import json,sys;print(json.load(sys.stdin)["launch"])')"
done
shut >/dev/null; echo "daemon $(alive $(dpid))"
