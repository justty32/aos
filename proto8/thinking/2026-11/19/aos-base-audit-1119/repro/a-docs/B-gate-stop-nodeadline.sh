#!/bin/bash
# 測：經 kernel_gate 式的站寄 stop（aos-agent ctl stop）時信不帶 queue_wait_ms：站把它留著、寄件人逾時失敗，信卻還留在站上，之後誰 pass 就晚到套上（對 kernel.json#/gate「aos-agent ctl sets 30 s」）
set -u
W=$(mktemp -d "$HOME/.aos/scratch/aos-base-audit-1119/a-docs/forkB/gstop.XXXX")
mkdir -p "$W/daemon" "$W/cell" "$W/me"
aos-post init "$W/daemon/procs_requests" >/dev/null
echo "{\"procs\": {\"x\": {\"phase\": \"running\", \"stack\": \"$W/xs\"}}, \"procs_requests\": \"procs_requests\"}" > "$W/daemon/procs_state.json"
echo "{\"hooks\": {\"hold\": {\"event\": \"after_verdict\", \"condition\": \"pass\", \"handler\": \"$AOS_HOME/lib/tools/agent/kernel_gate/hold\"}}}" > "$W/cell/kernel.json"
aos-post init "$W/cell/requests" >/dev/null
( sleep 1; AOS_DAEMON=$W/daemon aos-exec --stack "$W/cell" "$AOS_HOME/lib/tools/aos/kernel" "$W/cell/kernel.json" ) &
AOS_STACK=$W/me AOS_DAEMON=$W/daemon AOS_KERNEL=$W/cell/requests timeout 30 aos-agent ctl stop --target x --timeout-s 3; echo "ctl stop exit $?"
wait
echo "held after sender gave up: $(cat $W/cell/hold.json)"
n=$(ls $W/cell/requests/cur | head -1); python3 -c "import json;print(\"body:\", json.load(open(\"$W/cell/requests/cur/$n/letter.json\"))[\"body\"])"
