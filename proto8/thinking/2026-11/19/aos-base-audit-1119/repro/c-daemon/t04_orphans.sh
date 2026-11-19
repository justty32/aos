# t04: orphan descendants (no cgroup): proc forks children (same pgid / setsid / loop body), then sleep / rm / natural exit -- who survives.
. "$HOME/.aos/scratch/aos-base-audit-1119/c-daemon/repro/common.sh"
mkd t04 50; startd || exit 1; echo "daemon pid $(dpid)"
# child in same process group; parent sh waits
mkscript "$D/fork_wait.sh" 'sleep 601 & echo $! > "$AOS_STACK/kid.pid"; wait'
# child escapes with setsid
mkscript "$D/fork_setsid.sh" 'setsid sleep 602 & sleep 0.2; pgrep -n -f "^sleep 602" > "$AOS_STACK/kid.pid"; exec sleep 600'
# parent exits 0 leaving a background child
mkscript "$D/fork_exit.sh" 'sleep 603 & echo $! > "$AOS_STACK/kid.pid"; exit 0'
# loop body leaves a child every run
mkscript "$D/loopbody.sh" 'nohup sleep 604 >/dev/null 2>&1 & echo $! >> "$AOS_STACK/kids.pid"; exit 0'
echo "{\"exec\": \"$D/loopbody.sh\", \"interval_ms\": 300}" > "$D/lp.json"
# TERM-ignoring kid under a parent that dies on TERM
mkscript "$D/fork_noterm.sh" '( trap "" TERM; exec sleep 605 ) & echo $! > "$AOS_STACK/kid.pid"; wait'

for n in fork_wait fork_setsid fork_exit fork_noterm; do ctl add --name $n "$D/$n.sh" >/dev/null; done
ctl add --name lp "$D/lp.json" >/dev/null
sleep 2; rows
kid() { cat "$S/procs/$1/kid.pid" 2>/dev/null; }
echo "  fork_exit row: $(phase fork_exit) (exited 0); its kid $(kid fork_exit) $(alive $(kid fork_exit))"
for n in fork_wait fork_setsid fork_noterm; do echo "  $n main=$(ppid_of $n) pgid=$(ps -o pgid= -p $(ppid_of $n)) kid=$(kid $n) kidpgid=$(ps -o pgid= -p $(kid $n))"; done
echo "== sleep fork_wait, fork_setsid, fork_noterm; rm lp"
for n in fork_wait fork_setsid fork_noterm; do ctl sleep $n >/dev/null; done; ctl rm lp >/dev/null
sleep 12; rows
for n in fork_wait fork_setsid fork_noterm; do echo "  $n kid $(kid $n): $(alive $(kid $n))"; done
echo "  lp kids alive: $(for p in $(cat $S/procs/lp/kids.pid); do alive $p; done | sort | uniq -c | tr '\n' ' ')"
echo "== shutdown daemon"; shut >/dev/null
echo "== cleanup survivors (only recorded pids, cwd checked)"
for p in $(cat $S/procs/*/kid.pid $S/procs/lp/kids.pid 2>/dev/null); do [ "$(alive $p)" = alive ] && { echo "  kill survivor $p ($(ps -o args= -p $p)) cwd=$(readlink /proc/$p/cwd)"; killmine 9 $p; }; done
