# t05: same-name procs: add the same name twice (different target), rm then add the same name right away; do two copies ever run?
. "$HOME/.aos/scratch/aos-base-audit-1119/c-daemon/repro/common.sh"
mkd t05 50; startd || exit 1; echo "daemon pid $(dpid)"
mkscript "$D/a.sh" 'echo "A $$" >> "$AOS_STACK/who.txt"; exec sleep 600'
mkscript "$D/b.sh" 'echo "B $$" >> "$AOS_STACK/who.txt"; exec sleep 600'
mkscript "$D/nt.sh" 'echo "NT $$" >> "$AOS_STACK/who.txt"; trap "" TERM; while :; do sleep 1; done'
cnt() { local n=0 p; for p in /proc/[0-9]*; do [ "$(cat $p/cmdline 2>/dev/null | tr '\0' ' ')" = "sleep 600 " ] && case "$(readlink $p/cwd)" in "$D"*) n=$((n+1));; esac; done; echo $n; }
echo "== add x=a.sh, then add x=b.sh"; ctl add --name x "$D/a.sh"; waitphase x running; P1=$(ppid_of x)
ctl add --name x "$D/b.sh"; echo "  exit $?"; sleep 1; echo "  row: pid=$(ppid_of x) (was $P1) exec=$(row x | python3 -c 'import json,sys;print(json.load(sys.stdin)["exec"])')"; cat $S/procs/x/who.txt
echo "== stop/start x -> which target now?"; ctl sleep x >/dev/null; waitphase x sleeping; ctl wake x >/dev/null; waitphase x running; tail -1 $S/procs/x/who.txt
echo "== rm x then add x immediately (b.sh), copies of sleep 600 under tree:"
ctl rm x >/dev/null & j1=$!; ctl add --name x "$D/a.sh" >/dev/null & j2=$!; wait $j1 $j2
for i in 1 2 3 4 5 6 7 8 9 10; do echo -n "$(cnt)/$(phase x) "; sleep 0.2; done; echo; tail -3 $S/procs/x/who.txt
echo "== rm x (wait for reply) then add x right after"; ctl add --name x "$D/a.sh" >/dev/null; waitphase x running
ctl rm x >/dev/null; ctl add --name x "$D/b.sh"; echo "  add exit $?"
for i in 1 2 3 4 5 6 7 8 9 10; do echo -n "$(cnt)/$(phase x) "; sleep 0.2; done; echo; tail -3 $S/procs/x/who.txt
echo "== same with a TERM-ignoring proc y: rm y; add y (rm takes 10 s)"
ctl add --name y "$D/nt.sh" >/dev/null; waitphase y running; Y1=$(ppid_of y)
ctl rm y >/dev/null; ctl add --name y "$D/nt.sh" >/dev/null
for i in $(seq 14); do echo -n "$(phase y):$(ppid_of y) "; sleep 1; done; echo; echo "  old y $Y1 $(alive $Y1)"; cat $S/procs/y/who.txt
echo "== ls"; ctl ls
shut >/dev/null; echo "  daemon $(alive $(dpid)); leftover sleep 600: $(cnt)"
