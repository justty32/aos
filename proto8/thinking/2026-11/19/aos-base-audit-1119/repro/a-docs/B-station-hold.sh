#!/bin/bash
# 測：框架站＋kernel_gate 的 hold（不起 daemon、不起 agent）：查表信直接放行、加 proc 信被留、表態 pass 後轉寄、期限到被拒 SlotMissing（對 knowledge/aos/kernel.json#/gate）
set -u
W=$(mktemp -d "$HOME/.aos/scratch/aos-base-audit-1119/a-docs/forkB/station.XXXX")
mkdir -p "$W/daemon" "$W/cell" "$W/sender"
aos-post init "$W/daemon/procs_requests" >/dev/null
aos-post init "$W/sender/daemon_reply" >/dev/null
echo "{\"procs\": {}, \"procs_requests\": \"procs_requests\"}" > "$W/daemon/procs_state.json"
H=$AOS_HOME/lib/tools/agent/kernel_gate/hold
echo "{\"hooks\": {\"hold\": {\"event\": \"after_verdict\", \"condition\": \"pass\", \"handler\": \"$H\"}}}" > "$W/cell/kernel.json"
aos-post init "$W/cell/requests" >/dev/null
export AOS_DAEMON=$W/daemon
R=$W/sender/daemon_reply
q=$(echo "{\"procs_state_path\": true}" | AOS_STACK=$W/sender aos-post send --reply-to "$R" "$W/cell/requests")
a=$(echo "{\"procs_added\": {\"w\": {\"exec\": \"x\"}}, \"desc\": \"please\"}" | AOS_STACK=$W/sender AOS_WS=$W aos-post send --reply-to "$R" "$W/cell/requests")
b=$(echo "{\"procs_added\": {\"v\": {\"exec\": \"x\"}}, \"queue_wait_ms\": 1500}" | AOS_STACK=$W/sender aos-post send --reply-to "$R" "$W/cell/requests")
round(){ aos-exec --stack "$W/cell" "$AOS_HOME/lib/tools/aos/kernel" "$W/cell/kernel.json"; echo "round exit $?"; }
round
echo "daemon box new: $(ls $W/daemon/procs_requests/new | wc -l) (expect 1 = query)"
echo "held: $(cat $W/cell/hold.json)"
python3 -c "import json;print(\"sender of held a:\", json.load(open(\"$W/cell/requests/cur/$a/letter.json\"))[\"sender\"])"
mkdir -p "$W/cell/decisions"; echo "{\"verdict\": \"pass\"}" > "$W/cell/decisions/$a.json"
sleep 2
round
echo "daemon box new: $(ls $W/daemon/procs_requests/new | wc -l) (expect 2 = query + a)"
echo "held: $(cat $W/cell/hold.json)"
for n in $(ls $R/new); do cat $R/new/$n/letter.json; echo; done
