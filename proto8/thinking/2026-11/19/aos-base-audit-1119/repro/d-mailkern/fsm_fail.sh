# 測 aos-fsm 一格掛掉（退 1、逾時、壞 next 表、壞 JSON、stage.txt 指不在表上的狀態）時 loop／daemon 表怎麼顯示；以及 ctl stop 一個卡在身體裡的 loop。
source $(dirname $0)/common.sh
R=$RUN/fsmfail; rm -rf $R; mkdir -p $R/t; TD=$R/t
cat > $TD/fail.json <<J
{"start": "a", "states": {"a": {"exec": {"argv": ["sh", "-c", "echo ran >> $R/a_runs; exit 1"]}, "next": "b"}, "b": {"exec": {"argv": ["true"]}, "next": "a"}}}
J
cat > $TD/star.json <<J
{"start": "a", "states": {"a": {"exec": {"argv": ["sh", "-c", "echo ran >> $R/star_runs; exit 1"]}, "next": {"0": "a", "*": "a"}}}}
J
cat > $TD/tmo.json <<J
{"start": "a", "states": {"a": {"exec": {"argv": ["sleep", "5"], "timeout_ms": 300}, "next": "a"}}}
J
cat > $TD/badnext.json <<J
{"start": "a", "states": {"a": {"exec": {"argv": ["true"]}, "next": "zz"}}}
J
echo "{broken" > $TD/broken.json
cat > $TD/ok.json <<J
{"start": "a", "states": {"a": {"exec": {"argv": ["true"]}, "next": "a"}}}
J
mkdir -p $R/fstage; echo "nosuchstate" > $R/fstage/stage.txt
f() { echo "{\"exec\": {\"argv\": [\"aos-fsm\", \"$TD/$1.json\"]}, \"interval_ms\": 100 $2}"; }
cat > $R/daemon.json <<J
{"interval_ms": 50, "procs": {"f_fail": $(f fail), "f_star": $(f star), "f_tmo": $(f tmo), "f_badnext": $(f badnext), "f_broken": $(f broken),
 "f_stage": $(f ok ", \"stack\": \"$R/fstage\""),
 "l_hang": {"exec": {"argv": ["sleep", "600"]}, "interval_ms": 100}}}
J
start_daemon $R || exit 1
sleep 5
ctl $R ls
for n in f_fail f_tmo f_badnext f_broken; do echo "--- $n stderr.txt:"; tail -3 $R/stack/procs/$n/stderr.txt; done
echo "--- f_stage stderr:"; tail -2 $R/fstage/stderr.txt
echo "a runs: $(cat $R/a_runs | wc -l), star runs in 5s: $(cat $R/star_runs | wc -l)"
echo "== ctl stop on a loop stuck in its body"; time T=20 ctl $R stop l_hang; echo "exit=$?"; row $R l_hang
time T=20 ctl $R sleep l_hang; echo "exit=$?"; sleep 1; row $R l_hang
stop_daemon $R
