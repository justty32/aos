# t10: where daemon log and proc stdout/stderr go and how fast they grow: a stderr flood (capped with file_mb), a loop whose body fails every round, stdout flood; 20 s each in parallel.
. "$HOME/.aos/scratch/aos-base-audit-1119/c-daemon/repro/common.sh"
mkd t10 50; startd || exit 1; echo "daemon pid $(dpid)"
mkscript "$D/flood_err.sh" 'exec python3 -c "
import sys
line = \"x\" * 99 + \"\\n\"
while True: sys.stderr.write(line)"'
mkscript "$D/flood_out.sh" 'exec python3 -c "
import sys
line = \"y\" * 99 + \"\\n\"
while True: sys.stdout.write(line)"'
mkscript "$D/fail.sh" 'echo "body failed once" >&2; exit 3'
echo "{\"exec\": \"$D/fail.sh\", \"interval_ms\": 0}" > "$D/lfail.json"
ctl add --name ferr --limits '{"file_mb": 200}' "$D/flood_err.sh" >/dev/null
ctl add --name fout --limits '{"file_mb": 200}' "$D/flood_out.sh" >/dev/null
ctl add --name lfail --limits '{"file_mb": 200}' "$D/lfail.json" >/dev/null
sz() { stat -c %s "$1" 2>/dev/null || echo 0; }
for t in 5 10 15 20; do sleep 5; echo "t=${t}s ferr/stderr.txt=$(sz $S/procs/ferr/stderr.txt) fout/stderr.txt=$(sz $S/procs/fout/stderr.txt) lfail/stderr.txt=$(sz $S/procs/lfail/stderr.txt) daemon.log=$(sz $D/daemon.log) daemon.err=$(sz $D/daemon.err) stack-du=$(du -sk $S | cut -f1)K"; done
rows
echo "== where does fout stdout go?"; ls -l /proc/$(ppid_of fout)/fd/1 2>/dev/null | awk '{print $NF}'; echo "== ferr stderr fd:"; ls -l /proc/$(ppid_of ferr)/fd/2 2>/dev/null | awk '{print $NF}'
echo "== lfail stderr sample:"; tail -3 $S/procs/lfail/stderr.txt; echo "  lines: $(wc -l < $S/procs/lfail/stderr.txt)"
echo "== daemon CPU ticks: $(awk '{print $14+$15}' /proc/$(dpid)/stat)"
ctl rm ferr >/dev/null; ctl rm fout >/dev/null; ctl rm lfail >/dev/null; sleep 2
shut >/dev/null; echo "daemon $(alive $(dpid))"
echo "== free space"; df -h "$S" | tail -1
rm -f $S/procs/ferr/stderr.txt; echo "removed the big ferr stderr.txt to free space"
