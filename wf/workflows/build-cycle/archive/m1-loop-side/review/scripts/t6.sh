#!/bin/bash
. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens3/env.sh
T() { local s=$(date +%s.%N); "$@"; local r=$?; local e=$(date +%s.%N); echo "  [耗時 $(echo "$e - $s" | bc) 秒, rc=$r]"; return $r; }

echo "===== 6-1 5000 筆 inst（序列）====="
W=$LAB/w6a; mkworld "$W"
python3 -c 'import json;print(json.dumps([{"argv":["/bin/true"]} for _ in range(5000)]))' > "$LAB/big5000.json"
wc -c "$LAB/big5000.json"
T "$AOS" deliver "$W" -f "$LAB/big5000.json"
T timeout 300 "$AOS" exec "$W"
ls -la "$W/.aos"

echo
echo "===== 6-2 5000 筆全 parallel（5000 thread）====="
W=$LAB/w6b; mkworld "$W"
python3 -c 'import json;print(json.dumps([{"argv":["/bin/true"],"parallel":True} for _ in range(5000)]))' > "$LAB/big5000p.json"
T "$AOS" deliver "$W" -f "$LAB/big5000p.json"
T timeout 300 "$AOS" exec "$W"
ls -A "$W/.aos"

echo
echo "===== 6-3 單筆 10MB argv ====="
W=$LAB/w6c; mkworld "$W"
python3 -c 'import json;print(json.dumps([{"argv":["/bin/true","X"*10*1024*1024]}]))' > "$LAB/big10m.json"
wc -c "$LAB/big10m.json"
T "$AOS" deliver "$W" -f "$LAB/big10m.json"
T timeout 120 "$AOS" exec "$W"
ls -la "$W/.aos"
echo "turn=$(cat "$W/.aos/turn" 2>/dev/null)"

echo
echo "===== 6-4 深層巢狀 JSON（§C-7 自承會爆堆疊）====="
W=$LAB/w6d; mkworld "$W"
python3 -c 'print("["*100000 + "]"*100000)' > "$LAB/deep.json"
T timeout 60 "$AOS" deliver "$W" -f "$LAB/deep.json"
