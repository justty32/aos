# 測 aos-loop／aos-fsm 一格掛掉：退非 0、逾時、卡住不回、loop.json／fsm.json 壞、stage 壞、on_start／on_stop 掛掉或卡住、auto_restart 下慢失敗會不會無限重起。
source $(dirname $0)/common.sh
R=$RUN/loopfail; rm -rf $R; mkdir -p $R/t; cd $R/t
cat > fsm_fail.json <<J
{"start": "a", "states": {"a": {"exec": {"argv": ["sh", "-c", "echo ran >> \$AOS_STACK/../runs; exit 1"]}, "next": "b"}, "b": {"exec": {"argv": ["true"]}, "next": "a"}}}
J
cat > fsm_badjson.json <<J
{"start": "a", "states": {"a": {"exec": {"argv": ["true"]}, "next": "zz"}}}
J
echo "{broken" > broken.json
cat > fsm_stage.json <<J
{"start": "a", "states": {"a": {"exec": {"argv": ["true"]}, "next": "a"}}}
J
cd - >/dev/null
TD=$R/t
cat > $R/daemon.json <<J
{"interval_ms": 50, "procs": {
 "l_exit1":   {"exec": {"argv": ["sh", "-c", "exit 1"]}, "interval_ms": 100},
 "l_exit1_ar_fast": {"exec": {"argv": ["sh", "-c", "exit 1"]}, "interval_ms": 100, "auto_restart": true},
 "l_exit1_ar_slow": {"exec": {"argv": ["sh", "-c", "sleep 3.5; echo x >> $R/slow_runs; exit 1"]}, "interval_ms": 100, "auto_restart": true},
 "l_timeout": {"exec": {"argv": ["sleep", "5"], "timeout_ms": 500}, "interval_ms": 100},
 "l_hang":    {"exec": {"argv": ["sleep", "600"]}, "interval_ms": 100},
 "l_hang_stuck": {"exec": {"argv": ["sleep", "600"]}, "interval_ms": 100, "stuck_after_ms": 2000},
 "l_onstart_fail": {"exec": {"argv": ["sh", "-c", "echo body >> $R/onstart_body; sleep 600"]}, "interval_ms": 100, "on_start": {"argv": ["sh", "-c", "exit 7"]}},
 "l_onstop_hang": {"exec": {"argv": ["sh", "-c", "exit 10"]}, "interval_ms": 100, "on_stop": {"argv": ["sleep", "600"]}},
 "l_body10": {"exec": {"argv": ["sh", "-c", "exit 10"]}, "interval_ms": 100},
 "f_fail":    {"exec": ["aos-fsm", "$TD/fsm_fail.json"], "interval_ms": 100},
 "f_badnext": {"exec": ["aos-fsm", "$TD/fsm_badjson.json"], "interval_ms": 100},
 "f_broken":  {"exec": ["aos-fsm", "$TD/broken.json"], "interval_ms": 100},
 "f_stage":   {"exec": ["aos-fsm", "$TD/fsm_stage.json"], "interval_ms": 100, "stack": "$R/fstage_stack"}
}}
J
mkdir -p $R/fstage_stack; echo "nosuchstate" > $R/fstage_stack/stage.txt
start_daemon $R || exit 1
sleep 7
echo "== t=7s"; ctl $R ls
echo "== slow auto_restart runs so far: $(wc -l < $R/slow_runs 2>/dev/null)"
echo "== loop.json broken via ctl add of a loop file"
echo "{\"exec\": [\"true\"], \"interval_ms\": 100, oops" > $R/t/badloop.json
ctl $R add --name l_badfile $R/t/badloop.json 2>&1 | tail -1
echo "== stop the hanging one (ctl stop, 10 s)"; ( time T=15 ctl $R stop l_hang ) 2>&1 | tail -4
echo "== sleep the hanging one"; ( time T=20 ctl $R sleep l_hang ) 2>&1 | tail -4
sleep 8
echo "== t=~25s"; ctl $R ls
echo "== slow auto_restart runs: $(wc -l < $R/slow_runs)"
echo "== onstart body ran: $(wc -l < $R/onstart_body 2>/dev/null)"
grep -h "warning" $R/stack/procs/*/stderr.txt 2>/dev/null | sort | uniq -c | head
echo "== f_fail stage:"; cat $R/stack/procs/f_fail/stage.txt 2>/dev/null || echo "(no stage.txt = still at start)"; echo "runs of a: $(cat $R/stack/procs/runs 2>/dev/null | wc -l)"
stop_daemon $R
echo "== slow auto_restart total runs after stop: $(wc -l < $R/slow_runs)"
