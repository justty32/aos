#!/bin/bash
. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens3/env.sh
T() { local s=$(date +%s.%N); "$@" 2>"$LAB/err.txt"; local r=$?; local e=$(date +%s.%N); echo "  [耗時 $(echo "$e - $s"|bc) 秒, rc=$r, stderr $(wc -l < "$LAB/err.txt") 行]"; head -2 "$LAB/err.txt"; return $r; }

echo "===== 6-1 5000 筆 inst 序列 ====="
W=$LAB/w6a; mkworld "$W"
T "$AOS" deliver "$W" -f "$LAB/big5000.json"
T timeout 300 "$AOS" exec "$W"
echo "turn=$(cat "$W/.aos/turn")"; ls -A "$W/.aos"

echo "===== 6-2 5000 筆全 parallel ====="
W=$LAB/w6b; mkworld "$W"
T "$AOS" deliver "$W" -f "$LAB/big5000p.json"
T timeout 300 "$AOS" exec "$W"
echo "第一個失敗的 record: $(grep -m1 'record' "$LAB/err.txt")"
echo "失敗筆數: $(grep -c 'SpawnFailed' "$LAB/err.txt")"
echo "turn=$(cat "$W/.aos/turn")"; ls -A "$W/.aos"
echo "有沒有留 .runi: $(ls -A "$W/.aos" | grep runi || echo 沒有)"

echo "===== 6-5 500 筆 parallel（合理量）====="
W=$LAB/w6e; mkworld "$W"
python3 -c 'import json;print(json.dumps([{"argv":["/bin/true"],"parallel":True} for _ in range(500)]))' > "$LAB/p500.json"
T "$AOS" deliver "$W" -f "$LAB/p500.json"
T timeout 300 "$AOS" exec "$W"

echo "===== 6-6 極深巢狀 1,000,000 層 ====="
python3 -c 'print("["*1000000 + "]"*1000000)' > "$LAB/deep2.json"
W=$LAB/w6f; mkworld "$W"
T timeout 60 "$AOS" deliver "$W" -f "$LAB/deep2.json"
