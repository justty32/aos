# 測 agent-fsm（假腦）掛在 llm kernel 上：正常一問一答；kernel 被 kill -9 後再問，agent 卡在哪、表上與 listen 看到什麼；kernel 重起後會不會接上。
source $(dirname $0)/llmk_common.sh
K=$RUN/llmk7; llmk_setup $K || exit 1; llmk_start $K
G=$RUN/agentd; rm -rf $G; mkdir -p $G/ws
echo "{\"interval_ms\": 100, \"procs\": {}}" > $G/daemon.json
( cd $G && setsid $CLEAN env AOS_STACK=$G/stack AOS_LLM_KERNEL=$K/stack AOS_WS=$G/ws aos-daemon --enable-logs $G/daemon.json >>$G/daemon.log 2>>$G/daemon.err & )
for i in $(seq 100); do grep -qs "\"pid\"" $G/stack/procs_state.json && break; sleep 0.1; done
python3 -c "import json;print(json.load(open(\"$G/stack/procs_state.json\"))[\"pid\"])" > $G/daemon.pid
ag() { (cd $G/ws && T=${TT:-40} c env AOS_LLM_KERNEL=$K/stack aos-agent -d $G/stack "$@"); }
ag ctl add --name ann $SRC/templates/agent-fsm 2>&1 | tail -1
sleep 2
echo "== ask 1 (kernel up)"; time TT=40 ag -t ann ask --timeout-s 30 "what time is it?" 2>&1 | tail -3
P=$(cat $K/daemon.pid); [ "$(readlink /proc/$P/cwd)" = "$K/def" ] && kill -9 $P && echo "killed llm daemon $P"
echo "== ask 2 (kernel dead, 20 s)"; time TT=40 ag -t ann ask --timeout-s 20 "second question" 2>&1 | tail -4
echo "stage: $(cat $G/stack/procs/ann/stage.txt 2>/dev/null)"; ag ctl ls 2>&1 | head -3
tail -3 $G/stack/procs/ann/stderr.txt
echo "== restart kernel, listen 25 s"; llmk_start $K; time TT=40 ag -t ann listen --timeout-s 25 2>&1 | tail -3
echo "stage: $(cat $G/stack/procs/ann/stage.txt 2>/dev/null)"
TT=40 ag ctl rm --purge ann 2>&1 | tail -1
stop_daemon $G; llmk_stop $K
