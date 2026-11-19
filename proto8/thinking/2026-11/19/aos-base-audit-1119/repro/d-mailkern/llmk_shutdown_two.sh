# 測 llm kernel 正常收工（shutdown）時在途問腦會不會重打端點、帳會不會多記；以及同一個 stack 起第二台 llm daemon、兩台 kernel 各自一個 stack 時會怎樣。
source $(dirname $0)/llmk_common.sh
K=$RUN/llmk4; llmk_setup $K || exit 1; llmk_start $K
B=$K/box; c aos-post init $B >/dev/null
for i in 1 2; do echo "{\"endpoint\": \"slow\", \"request\": {\"messages\": [{\"role\": \"user\", \"content\": \"sd$i\"}]}}" | c env AOS_LLM_KERNEL=$K/stack aos-llm send --reply-to $B >/dev/null; done
sleep 2.5; echo "in flight: $(c aos-daemon-ctl -d $K/stack ls | grep -c llm_)"
T=30 c aos-daemon-ctl -d $K/stack shutdown
echo "== second daemon on the same stack while the first is down? start first again, then a second"
llmk_start $K; P1=$(cat $K/daemon.pid)
( cd $K && T=10 c aos-exec --stack $K/stack $K/def > $K/second.out 2>&1; echo "second exit=$?" >> $K/second.out )
cat $K/second.out | tail -3
sleep 10
c aos-post take-all $B > $K/got.txt; echo "replies: $(wc -l < $K/got.txt)"
python3 -c "
import json,collections
c=collections.Counter(json.loads(l)[\"msg\"] for l in open(\"$K/eps/calls.log\")); print(\"endpoint calls:\", dict(c))
rows=[json.loads(l) for l in open(\"$K/stack/ledger.jsonl\")]; print(\"ledger rows\", len(rows))
print(\"used\", json.load(open(\"$K/stack/used.json\"))[\"counter_calls\"])"
llmk_stop $K
echo "== two kernels, separate stacks, same endpoints file: independent?"
K2=$RUN/llmk5; llmk_setup $K2 >/dev/null; llmk_start $K2; llmk_setup $RUN/llmk6 >/dev/null; llmk_start $RUN/llmk6
ask $K2 fake one 10; ask $RUN/llmk6 fake two 10
llmk_stop $K2; llmk_stop $RUN/llmk6
