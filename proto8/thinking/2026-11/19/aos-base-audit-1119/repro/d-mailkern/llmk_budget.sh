# 測 llm kernel 額度：總額 max_calls 3（window all）用完後的回信、包額度 once、寄件人額度、used.json／ledger 會不會一直長、壞掉的 used.json。
source $(dirname $0)/llmk_common.sh
K=$RUN/llmk2; S1=$RUN/llmk2_sender1; mkdir -p $S1
llmk_setup $K "\"budget\": {\"max_calls\": 4, \"window\": \"all\", \"senders\": {\"$S1\": {\"max_calls\": 1}}}," || exit 1; llmk_start $K
echo "--- once pack x2"; ask $K once a1 20 2>&1; ask $K once a2 20 2>&1 | cut -c1-400
echo "--- sender S1 x2 (AOS_STACK=$S1)"; for i in 1 2; do echo "{\"endpoint\": \"tok\", \"request\": {\"messages\": [{\"role\": \"user\", \"content\": \"s$i\"}]}}" | T=20 c env AOS_LLM_KERNEL=$K/stack AOS_STACK=$S1 aos-llm ask 2>&1 | cut -c1-300; done
echo "--- total: tok until refused"; for i in 1 2 3 4; do ask $K tok t$i 20 2>&1 | cut -c1-400; done
echo "--- full error object via send/recv"
c aos-post init $K/box >/dev/null; n=$(echo "{\"endpoint\": \"tok\", \"request\": {\"messages\": [{\"role\": \"user\", \"content\": \"x\"}]}}" | c env AOS_LLM_KERNEL=$K/stack aos-llm send --reply-to $K/box); sleep 2; c aos-llm recv --full $K/box $n; echo
echo "used.json:"; python3 -c "import json;d=json.load(open(\"$K/stack/used.json\"));print({k:v for k,v in d.items() if k.startswith(\"counter\")}, d[\"senders\"])"
echo "ledger lines: $(wc -l < $K/stack/ledger.jsonl) (refusals not recorded per doc)"
echo "--- corrupt used.json"; cp $K/stack/used.json $K/used.bak; echo "{bad" > $K/stack/used.json; sleep 1; ask $K fake z 8 2>&1 | cut -c1-200; tail -3 $K/daemon.err; c aos-daemon-ctl -d $K/stack ls | tail -2
cp $K/used.bak $K/stack/used.json
llmk_stop $K
