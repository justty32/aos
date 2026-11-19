# 測時鐘：clock_register 的 every／after／at 定時信會不會到、收件 proc 停著或被刪時怎樣、daemon 收工期間到期的、daemon 重起後登記還在不在。
source $(dirname $0)/common.sh
R=$RUN/clock; rm -rf $R; mkdir -p $R/def
cat > $R/def/daemon.json <<J
{"interval_ms": 50, "procs": {"_clock": {"exec": {"argv": ["aos-clock", {"\$env": "AOS_DAEMON", "\$path": "clock"}]}, "interval_ms": 500, "auto_restart": true, "stuck_after_ms": 10000},
 "rcv": {"exec": {"argv": ["sleep", "600"]}}, "gone": {"exec": {"argv": ["sleep", "600"]}}}}
J
echo "[\"aos-daemon\", \"--enable-logs\", \"daemon.json\"]" > $R/def/_entry
printf "AOS_CLOCK=\${AOS_STACK}/clock\nAOS_CLOCK_INTERVAL=500\n" > $R/def/.env
start() { ( cd $R && setsid $CLEAN aos-exec --stack $R/stack $R/def >>$R/daemon.log 2>>$R/daemon.err & ); for i in $(seq 100); do [ -f $R/stack/procs_state.json ] && grep -q "\"pid\"" $R/stack/procs_state.json && break; sleep 0.1; done; python3 -c "import json;print(json.load(open(\"$R/stack/procs_state.json\"))[\"pid\"])" > $R/daemon.pid; }
start; sleep 1.5
echo "pid $(cat $R/daemon.pid) cwd $(readlink /proc/$(cat $R/daemon.pid)/cwd)"
QR=$R/stack/procs/rcv/queue; QG=$R/stack/procs/gone/queue
c aos-post init $QR >/dev/null; c aos-post init $QG >/dev/null
reg() { c aos-clock-register -d $R/stack "$@"; }
reg add --every 4 --box $QR ev "every4"
reg add --after 6 --box $QR af "after6"
reg add --at +5s --box $QR at5 "at+5s"   2>&1
reg add --every 2 --box $QG g2 "to-gone"
reg ls
echo "clock now: $(cat $R/stack/clock)"
sleep 4
echo "== t=4s clock $(cat $R/stack/clock); rcv queue: $(ls $QR/new | wc -l)"
ctl $R stop rcv; ctl $R rm gone; sleep 0.5; rm -rf $R/stack/procs/gone
sleep 4
echo "== t=8s (rcv stopping/stopped, gone deleted) clock $(cat $R/stack/clock)"; ctl $R ls | head -4
for l in $QR/new/*/letter.json; do python3 -c "import json,sys;print(json.load(open(sys.argv[1]))[\"body\"][\"content\"])" $l; done | sort | uniq -c
grep -c "cannot send" $R/stack/procs/_clock/stderr.txt; grep "cannot send" $R/stack/procs/_clock/stderr.txt | tail -1
reg ls
echo "== shutdown daemon, add an --at +3s entry while down, wait 6 s, restart"
reg add --at +3s --box $QR atdown "at-while-down"
stop_daemon $R; c0=$(cat $R/stack/clock); n0=$(ls $QR/new | wc -l)
sleep 6; echo "while down: clock $c0 -> $(cat $R/stack/clock), letters $n0 -> $(ls $QR/new | wc -l)"
start; sleep 3
echo "== after restart: clock $(cat $R/stack/clock)"; reg ls
for l in $QR/new/*/letter.json; do python3 -c "import json,sys;print(json.load(open(sys.argv[1]))[\"body\"][\"content\"])" $l; done | sort | uniq -c
stop_daemon $R
