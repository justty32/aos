# 測 llm kernel 基本：假腦問答、端點失敗／壞回信／錯誤 JSON、逾時、卡住不回（佔格）、記帳檔 used.json 與 ledger.jsonl 在哪。
source $(dirname $0)/llmk_common.sh
K=$RUN/llmk1; llmk_setup $K "\"timeout_ms\": 4000," || exit 1; llmk_start $K
echo "kernel pid $(cat $K/daemon.pid)"
for ep in fake tok fail failjson badjson; do echo "--- $ep"; ask $K $ep "hi-$ep" 20 2>&1 | cut -c1-300; done
echo "--- slow (6s) with timeout_ms 4000"; time ask $K slow "hi-slow" 30 2>&1 | cut -c1-300
echo "--- hang with timeout_ms 4000"; time ask $K hang "hi-hang" 30 2>&1 | cut -c1-300
echo "--- unknown endpoint"; ask $K nosuch "x" 10 2>&1
echo "== files"; ls $K/stack; echo "used.json:"; cat $K/stack/used.json; echo; echo "ledger lines: $(wc -l < $K/stack/ledger.jsonl)"; tail -2 $K/stack/ledger.jsonl
echo "calls.log:"; cat $K/eps/calls.log | python3 -c "import sys,json,collections;print(collections.Counter(json.loads(l)[\"mode\"] for l in sys.stdin))"
c aos-daemon-ctl -d $K/stack ls
llmk_stop $K
