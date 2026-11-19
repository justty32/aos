# 測 agent 的 hook 掛掉／卡住：before_queue 的 hook 卡住（timeout_ms 2000、on_error continue）與退 1（on_error stop）時，這則訊息與整隻 agent 會怎樣。
source $(dirname $0)/llmk_common.sh
K=$RUN/llmk8; llmk_setup $K || exit 1
sed -i "s|\"speed\": \"fast\", \"cost\": \"free\"}|\"speed\": \"fast\", \"cost\": \"free\", \"tool\": \"peek_now_time\"}|" $K/def/kernel.json
llmk_start $K
G=$RUN/agentd2; rm -rf $G; mkdir -p $G/ws $G/h
printf "#!/bin/sh\nsleep 600\n" > $G/h/hang; printf "#!/bin/sh\necho hookfail >&2; exit 1\n" > $G/h/fail; chmod +x $G/h/*
echo "{\"interval_ms\": 100, \"procs\": {}}" > $G/daemon.json
( cd $G && setsid $CLEAN env AOS_STACK=$G/stack AOS_LLM_KERNEL=$K/stack AOS_WS=$G/ws aos-daemon --enable-logs $G/daemon.json >>$G/daemon.log 2>>$G/daemon.err & )
for i in $(seq 100); do grep -qs "\"pid\"" $G/stack/procs_state.json && break; sleep 0.1; done
python3 -c "import json;print(json.load(open(\"$G/stack/procs_state.json\"))[\"pid\"])" > $G/daemon.pid
ag() { (cd $G/ws && T=${TT:-60} c env AOS_LLM_KERNEL=$K/stack aos-agent -d $G/stack "$@"); }
ag ctl add --name ann $SRC/templates/agent-fsm 2>&1 | tail -1; sleep 2
ag -t ann hook add --event before_queue -n hanger --on-error continue --timeout-ms 2000 $G/h/hang 2>&1 | tail -1
echo "== hang hook (continue, 2 s)"; time ag -t ann ask --timeout-s 30 "q1" 2>&1 | tail -2
echo "hang procs left: $(pgrep -f "$G/h/hang" | wc -l)"; grep -h "hanger" $G/stack/procs/ann/stderr.txt | tail -2
ag -t ann hook rm hanger >/dev/null
ag -t ann hook add --event before_queue -n failer --on-error stop $G/h/fail 2>&1 | tail -1
echo "== failing hook (stop)"; time ag -t ann ask --timeout-s 15 "q2" 2>&1 | tail -2
sleep 1; ag ctl ls 2>&1 | head -2; echo "stage: $(cat $G/stack/procs/ann/stage.txt)"; tail -3 $G/stack/procs/ann/stderr.txt
ag -t ann hook rm failer >/dev/null
echo "== after removing the failing hook: start again"; ag ctl start ann 2>&1 | tail -1; sleep 2; ag ctl ls | head -1
time ag -t ann listen --timeout-s 15 2>&1 | tail -2
TT=40 ag ctl rm --purge ann 2>&1 | tail -1
stop_daemon $G; llmk_stop $K
