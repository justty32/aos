# t07: rlimit shares cpu_s / mem_mb / files / procs / file_mb with small numbers: do they hit, and what does the table say (reason, limit_hit, limit_suspect)?
. "$HOME/.aos/scratch/aos-base-audit-1119/c-daemon/repro/common.sh"
mkd t07 50; startd || exit 1; echo "daemon pid $(dpid)"
mkscript "$D/cpu.sh" 'exec python3 -c "
while True: pass"'
mkscript "$D/cpu_sh.sh" 'python3 -c "
while True: pass"; echo "child ended $?" >&2; exit 3'
mkscript "$D/mem.sh" 'exec python3 -c "
x = bytearray(200*1024*1024); print(len(x))"'
mkscript "$D/files.sh" 'exec python3 -c "
fs=[open(\"/dev/null\") for i in range(100)]; print(len(fs))"'
mkscript "$D/procs.sh" 'n=0; for i in 1 2 3 4 5 6 7 8 9 10; do sleep 5 & n=$((n+1)); done; echo "spawned $n" >&2; wait; exit 0'
mkscript "$D/fsize.sh" 'exec dd if=/dev/zero of="$AOS_STACK/big.bin" bs=1M count=5'
mkscript "$D/busy_forks.sh" 'for i in 1 2 3; do python3 -c "
import time; t=time.time()
while time.time()-t<0.9: pass" ; done; echo "three 0.9s CPU children done" >&2; exit 0'
ctl add --name cpu --limits '{"cpu_s": 1}' "$D/cpu.sh" >/dev/null
ctl add --name cpu_sh --limits '{"cpu_s": 1}' "$D/cpu_sh.sh" >/dev/null
ctl add --name mem --limits '{"mem_mb": 50}' "$D/mem.sh" >/dev/null
ctl add --name files --limits '{"files": 20}' "$D/files.sh" >/dev/null
ctl add --name procs --limits '{"procs": 5}' "$D/procs.sh" >/dev/null
ctl add --name fsize --limits '{"file_mb": 1}' "$D/fsize.sh" >/dev/null
ctl add --name forks --limits '{"cpu_s": 1}' "$D/busy_forks.sh" >/dev/null
sleep 6; rows
for n in cpu cpu_sh mem files procs fsize forks; do echo "-- $n stderr: $(tail -c 300 $S/procs/$n/stderr.txt | tr '\n' '|')"; done
ls -la $S/procs/fsize/big.bin 2>/dev/null
echo "== limits on table"; row cpu | python3 -c 'import json,sys;r=json.load(sys.stdin);print({k:r.get(k) for k in ("limits","limit_hit","limit_suspect","reason")})'
echo "== bad limits"; ctl add --name bad --limits '{"cpu_s": 0}' "$D/cpu.sh" 2>&1 | tail -1
ctl add --name bad2 --limits '{"mem_mb": 99999999}' "$D/cpu.sh" 2>&1 | tail -1; sleep 1; row bad2 | cut -c1-300
echo "== K11 warning in daemon.err:"; grep -i warning "$D/daemon.err" | head -3
shut >/dev/null; echo "daemon $(alive $(dpid))"
