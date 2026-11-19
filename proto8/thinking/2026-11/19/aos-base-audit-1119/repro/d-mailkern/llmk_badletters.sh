# 測 llm kernel 收到壞信（四種壞信與一個同步 ask 在同一輪；這組合曾連續 3 次讓身體退 141 一次，之後重跑沒再出現＝偶發）：letter.json 壞 JSON、只有夾、缺 body.request、reply_to 指到已刪的信箱；會不會卡住、重讀、後面的好信照不照答。
source $(dirname $0)/llmk_common.sh
K=$RUN/llmk10; llmk_setup $K || exit 1; llmk_start $K
N=$K/stack/requests/new; B=$K/box; c aos-post init $B >/dev/null
mkdir $K/x1; echo "{bad" > $K/x1/letter.json; mv $K/x1 $N/00000000000000000001.bad.json
mkdir $N/00000000000000000002.emptydir
echo "{\"nothing\": 1}" | c aos-post send --reply-to $B $K/stack/requests >/dev/null
c aos-post init $K/gonebox >/dev/null
echo "{\"request\": {\"messages\": [{\"role\": \"user\", \"content\": \"to-gone\"}]}}" | c aos-post send --reply-to $K/gonebox $K/stack/requests >/dev/null; rm -rf $K/gonebox
ask $K fake after-bad 15 2>&1 | tail -2
echo "after ask: $(grep -c "code 141" $K/daemon.err) x141"
sleep 1; c aos-post take-all $B | while read n; do python3 -c "import json,sys;print(\"reply:\", json.load(open(sys.argv[1]))[\"body\"])" $B/cur/$n/letter.json; done
echo "left in new/cur:"; ls $K/stack/requests/new $K/stack/requests/cur
grep -v "^$" $K/daemon.err | sort | uniq -c | cut -c1-250 | head
llmk_stop $K
