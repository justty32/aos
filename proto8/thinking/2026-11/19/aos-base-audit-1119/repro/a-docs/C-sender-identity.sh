#!/bin/bash
# 測：同一個 proc（AOS_WS 與 AOS_STACK 不同）用 aos-post send 與 aos-llm send 寄信，信封 sender 各是什麼（對 NORMS N-16「AOS_WS ＞ AOS_STACK ＞ AOS_CF ＞ cwd，程式與人同一條」）
set -u
W=$(mktemp -d "$HOME/.aos/scratch/aos-base-audit-1119/a-docs/sender/run.XXXX")
mkdir -p "$W/ws" "$W/stack" "$W/k"
aos-post init "$W/box" >/dev/null; aos-post init "$W/k/requests" >/dev/null; aos-post init "$W/reply" >/dev/null
export AOS_WS=$W/ws AOS_STACK=$W/stack
n=$(echo "{}" | aos-post send "$W/box")
echo "aos-post sender: $(python3 -c "import json;print(json.load(open(\"$W/box/new/$n/letter.json\"))[\"sender\"])")"
m=$(echo "{\"request\": {\"messages\": [{\"role\": \"user\", \"content\": \"hi\"}]}}" | AOS_LLM_KERNEL=$W/k aos-llm send --reply-to "$W/reply" 2>&1)
echo "aos-llm send printed: $m"
for f in "$W"/k/requests/new/*/letter.json; do echo "aos-llm sender: $(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))[\"sender\"])" "$f")"; done
