# t04b: loop / fsm proc whose body is a long foreground command: after sleep, rm and shutdown, does the body (grandchild) survive?
. "$HOME/.aos/scratch/aos-base-audit-1119/c-daemon/repro/common.sh"
mkd t04b 50; startd || exit 1; echo "daemon pid $(dpid)"
mkscript "$D/body.sh" 'echo $$ >> "$AOS_STACK/body.pid"; exec sleep 606'
mkscript "$D/body_tool.sh" 'echo $$ >> "$AOS_STACK/body.pid"; sleep 607; echo done'
echo "{\"exec\": \"$D/body.sh\", \"interval_ms\": 100}" > "$D/lp.json"
echo "{\"_entry\": [\"aos-fsm\", {\"\$env\": \"AOS_CF\"}], \"start\": \"work\", \"states\": {\"work\": {\"exec\": \"$D/body_tool.sh\", \"next\": \"work\"}}}" > "$D/fsm.json"
echo "{\"exec\": \"$D/fsm.json\", \"interval_ms\": 100}" > "$D/lf.json"
ctl add --name lp "$D/lp.json" >/dev/null; ctl add --name lf "$D/lf.json" >/dev/null; ctl add --name lp2 "$D/lp.json" >/dev/null; ctl add --name lf2 "$D/lf.json" >/dev/null
sleep 2; rows
b() { tail -1 "$S/procs/$1/body.pid" 2>/dev/null; }
for n in lp lf lp2 lf2; do echo "  $n main=$(ppid_of $n) body=$(b $n) tree: $(ps -o pid=,pgid=,args= --ppid $(ppid_of $n) | tr -s ' ' | tr '\n' ';')"; done
echo "== sleep lp lf (SIGTERM path)"; ctl sleep lp >/dev/null; ctl sleep lf >/dev/null
echo "== rm lp2"; ctl rm lp2 >/dev/null
sleep 2.5; rows
for n in lp lf lp2; do echo "  $n body $(b $n): $(alive $(b $n))"; done
echo "== stop lf2 (ctl path: waits for the round)"; ctl stop lf2 >/dev/null; sleep 2; echo "  lf2 phase=$(phase lf2)"
echo "== shutdown"; shut >/dev/null; echo "  lf2 body $(b lf2): $(alive $(b lf2))"
for p in $(cat $S/procs/*/body.pid); do [ "$(alive $p)" = alive ] && { echo "  survivor $p ($(ps -o args= -p $p)) ppid=$(ps -o ppid= -p $p)"; killmine 9 $p; }; done
grep -h "aos-loop\|aos-fsm" $S/procs/*/stderr.txt | tail -5
