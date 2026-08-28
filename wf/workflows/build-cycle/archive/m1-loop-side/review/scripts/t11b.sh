#!/bin/bash
. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens3/env.sh

echo "=== 11-neg 負數 turn（改用 printf '%s'）==="
W=$LAB/w11-neg2; mkworld "$W"
printf '%s\n' '-5' > "$W/.aos/turn"
cat > "$W/.aos/inst.tempd/1000-0.json" <<EOF
[{"argv":["/bin/sh","-c","echo RAN >> $W/log"]}]
EOF
timeout 10 "$AOS" exec "$W"; echo "rc=$?"
echo "turn=$(cat "$W/.aos/turn")"

echo
echo "=== 11-loop turn 壞掉時 --loop 會不會無限重跑（10 秒觀察）==="
W=$LAB/w11-loop; mkworld "$W"
printf '%s\n' 'abc' > "$W/.aos/turn"
# 每輪都會有新投遞的話會不會一直重跑？先看只有一批的情況
cat > "$W/.aos/inst.tempd/1000-0.json" <<EOF
[{"argv":["/bin/sh","-c","echo TICK >> $W/log"]}]
EOF
timeout 5 "$AOS" exec --loop 200 "$W" > "$LAB/loopout.txt" 2>&1
echo "timeout rc=$?"
echo "log 行數（跑了幾次）: $(wc -l < "$W/log" 2>/dev/null)"
echo "stderr 行數: $(wc -l < "$LAB/loopout.txt")"
head -3 "$LAB/loopout.txt"
echo "turn=$(cat "$W/.aos/turn")"
echo "剩下: $(ls -A "$W/.aos" | tr '\n' ' ')"

echo
echo "=== 11-loop2 對照組：turn 正常時 --loop 只會跑一次 ==="
W=$LAB/w11-loop2; mkworld "$W"
cat > "$W/.aos/inst.tempd/1000-0.json" <<EOF
[{"argv":["/bin/sh","-c","echo TICK >> $W/log"]}]
EOF
timeout 5 "$AOS" exec --loop 200 "$W" > "$LAB/loopout2.txt" 2>&1
echo "log 行數: $(wc -l < "$W/log" 2>/dev/null)"
echo "turn=$(cat "$W/.aos/turn")"
