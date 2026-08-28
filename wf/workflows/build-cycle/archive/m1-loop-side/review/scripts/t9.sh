#!/bin/bash
# 9：兩個（或 K 個）aos exec 同時對同一世界。量化撞上的機率與後果。
. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens3/env.sh
ROUNDS=${1:-200}; K=${2:-2}; NDLV=${3:-1}
W=$LAB/w9;
declare -A RC
DOUBLE=0; LOST=0; BUSY3=0; ERR1=0; PARSEFAIL=0; RUNILEFT=0; INSTLEFT=0
: > "$LAB/t9-detail.txt"
for r in $(seq 1 $ROUNDS); do
  mkworld "$W"
  LOG=$W/run.log; : > "$LOG"
  for d in $(seq 1 $NDLV); do
    printf '%s\n' '[{"argv":["/bin/sh","-c","echo X'"$d"' >> '"$LOG"'"]}]' > "$W/.aos/inst.tempd/$((1000+d))-0.json"
  done
  for k in $(seq 1 $K); do
    ( "$AOS" exec "$W" > "$LAB/t9-out-$k.txt" 2>&1; echo $? > "$LAB/t9-rc-$k.txt" ) &
  done
  wait
  ran=$(wc -l < "$LOG")
  rcs=""
  for k in $(seq 1 $K); do rcs="$rcs$(cat "$LAB/t9-rc-$k.txt")"; done
  RC[$rcs]=$(( ${RC[$rcs]:-0} + 1 ))
  [ "$ran" -gt "$NDLV" ] && DOUBLE=$((DOUBLE+1))
  [ "$ran" -lt "$NDLV" ] && { LOST=$((LOST+1)); echo "round $r 遺失 ran=$ran" >> "$LAB/t9-detail.txt"; cat "$LAB/t9-out-"*.txt >> "$LAB/t9-detail.txt"; ls -la "$W/.aos" >> "$LAB/t9-detail.txt"; }
  grep -qh 'already exists' "$LAB/t9-out-"*.txt && BUSY3=$((BUSY3+1))
  grep -qh 'JsonSyntax\|NotAnObject\|UnknownKey\|FieldTypeMismatch' "$LAB/t9-out-"*.txt && { PARSEFAIL=$((PARSEFAIL+1)); echo "round $r 解析失敗" >> "$LAB/t9-detail.txt"; cat "$LAB/t9-out-"*.txt >> "$LAB/t9-detail.txt"; }
  [ -e "$W/.aos/inst.json.runi" ] && RUNILEFT=$((RUNILEFT+1))
  [ -e "$W/.aos/inst.json" ] && INSTLEFT=$((INSTLEFT+1))
done
echo "== 9: $K 個 aos exec 同時開跑 × $ROUNDS 輪（每輪 inbox $NDLV 份投遞）=="
echo "  重複執行（同一批跑超過一次）: $DOUBLE / $ROUNDS"
echo "  執行不足／遺失            : $LOST / $ROUNDS"
echo "  出現 .runi already exists（退出碼 3）: $BUSY3 / $ROUNDS"
echo "  出現批次解析失敗（批被寫壞）        : $PARSEFAIL / $ROUNDS"
echo "  收尾後殘留 .runi                    : $RUNILEFT / $ROUNDS"
echo "  收尾後殘留 inst.json                : $INSTLEFT / $ROUNDS"
echo "  退出碼組合統計:"
for key in "${!RC[@]}"; do echo "    [$key] × ${RC[$key]}"; done
echo "  細節前 40 行:"; head -40 "$LAB/t9-detail.txt"
