# 測 agent-fsm 問腦失敗的冷卻：端點回 retry:true 的錯（failjson）會不會照冷卻重送、多久一次；端點硬失敗（fail，非 retry）agent 會不會停；BudgetMissing（once 包用完）。
source $(dirname $0)/llmk_common.sh
K=$RUN/llmk9; llmk_setup $K || exit 1; llmk_start $K
G=$RUN/agentd3; rm -rf $G; mkdir -p $G/ws
echo "{\"interval_ms\": 100, \"procs\": {}}" > $G/daemon.json
( cd $G && setsid $CLEAN env AOS_STACK=$G/stack AOS_LLM_KERNEL=$K/stack AOS_WS=$G/ws aos-daemon --enable-logs $G/daemon.json >>$G/daemon.log 2>>$G/daemon.err & )
for i in $(seq 100); do grep -qs "\"pid\"" $G/stack/procs_state.json && break; sleep 0.1; done
python3 -c "import json;print(json.load(open(\"$G/stack/procs_state.json\"))[\"pid\"])" > $G/daemon.pid
ag() { (cd $G/ws && T=${TT:-60} c env AOS_LLM_KERNEL=$K/stack aos-agent -d $G/stack "$@"); }
ag ctl add --name ann $SRC/templates/agent-fsm 2>&1 | tail -1; sleep 1.5
ag -t ann llm set model=failjson 2>&1 | tail -1
ag -t ann say "retry me" >/dev/null; sleep 40
echo "== failjson after 40 s: endpoint calls $(grep -c failjson $K/eps/calls.log)"; cat $G/stack/procs/ann/cooldown.json; echo; ag ctl ls | head -1
grep -c "BrainFailed" $G/stack/procs/ann/stderr.txt; grep "warning" $G/stack/procs/ann/stderr.txt | tail -2 | cut -c1-300
ls $G/stack/procs/ann/mailbox/new 2>/dev/null | wc -l
echo "== switch to fail (permanent)"; ag -t ann llm set model=fail 2>&1 | tail -1; sleep 35
echo "after 35 s: fail calls $(grep -c "\"fail\"" $K/eps/calls.log)"; ag ctl ls | head -1; tail -2 $G/stack/procs/ann/stderr.txt | cut -c1-300
TT=40 ag ctl rm --purge ann 2>&1 | tail -1
stop_daemon $G; llmk_stop $K
