# t08b: daemon kill -9 while a sub:N proc runs: after restart is it adopted (same pid) or started twice? then sleep/wake and a TERM-ignoring sub proc.
. "$HOME/.aos/scratch/aos-base-audit-1119/c-daemon/repro/common.sh"
mkd t08b 50; startd || exit 1; echo "daemon pid $(dpid)"
mkscript "$D/sl.sh" 'echo $$ >> "$AOS_STACK/pids"; exec sleep 600'
mkscript "$D/nt.sh" 'echo $$ >> "$AOS_STACK/pids"; trap "" TERM; while :; do sleep 1; done'
echo '{"exec": {"argv": ["'"$D"'/sl.sh"]}, "interval_ms": 100, "limits": {"user": "sub:9"}}' > "$D/lsub.json"
ctl add --name s1 --limits '{"user": "sub:7"}' "$D/sl.sh" >/dev/null
ctl add --name nt --limits '{"user": "sub:8"}' "$D/nt.sh" >/dev/null
ctl add --name ls1 "$D/lsub.json" >/dev/null
sleep 2; rows
for n in s1 nt ls1; do echo "  $n uid=$(grep ^Uid: /proc/$(ppid_of $n)/status | awk '{print $2}')"; done
S1=$(ppid_of s1); L1=$(ppid_of ls1)
echo "== kill -9 daemon, restart"; killmine 9 $(dpid); sleep 0.3; startd; sleep 1.5; rows
echo "  s1 same pid? $S1 -> $(ppid_of s1); starts recorded: $(wc -l < $S/procs/s1/pids); old alive: $(alive $S1)"
echo "  ls1 same pid? $L1 -> $(ppid_of ls1); old alive: $(alive $L1)"
tail -n 5 "$D/daemon.err"
echo "== sleep nt (TERM-ignoring, subuid)"; N=$(ppid_of nt); t0=$(now); ctl sleep nt >/dev/null; waitphase nt sleeping 20; echo "  took $(since $t0)s; old $(alive $N)"
echo "== shutdown"; shut >/dev/null; echo "  daemon $(alive $(dpid)); remaining subuid pids:"
for f in $S/procs/*/pids; do for p in $(cat $f); do echo "   $p $(alive $p)"; done; done
