#!/bin/bash
# 9b：兩個 exec 併發 → 併發階段跑幾次 + 收尾（drain）後總共跑幾次
. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens3/env.sh
ROUNDS=${1:-200}; K=${2:-2}
W=$LAB/w9b
DUR_CONC=0; DUR_TOTAL=0; LOST=0; RUNILEFT=0
: > "$LAB/t9b-err.txt"
for r in $(seq 1 $ROUNDS); do
  mkworld "$W"
  LOG=$W/run.log; : > "$LOG"
  printf '%s\n' '[{"argv":["/bin/sh","-c","echo X >> '"$LOG"'"]}]' > "$W/.aos/inst.tempd/1000-0.json"
  for k in $(seq 1 $K); do
    ( "$AOS" exec "$W" > "$LAB/t9b-out-$k.txt" 2>&1 ) &
  done
  wait
  conc=$(wc -l < "$LOG")
  cat "$LAB/t9b-out-"*.txt >> "$LAB/t9b-err.txt"
  # 收尾：再跑到沒事做為止
  for i in 1 2 3 4 5; do "$AOS" exec "$W" >> "$LAB/t9b-err.txt" 2>&1; done
  tot=$(wc -l < "$LOG")
  [ "$conc" -gt 1 ] && DUR_CONC=$((DUR_CONC+1))
  [ "$tot" -gt 1 ] && { DUR_TOTAL=$((DUR_TOTAL+1)); echo "round $r: 併發階段跑 $conc 次，收尾後總共 $tot 次" >> "$LAB/t9b-detail.txt"; }
  [ "$tot" -lt 1 ] && LOST=$((LOST+1))
  [ -e "$W/.aos/inst.json.runi" ] && RUNILEFT=$((RUNILEFT+1))
done
echo "== 9b: $K 個 exec 併發 × $ROUNDS 輪，每輪只有 1 份投遞（應該只跑 1 次）=="
echo "  併發階段就跑超過 1 次        : $DUR_CONC / $ROUNDS"
echo "  併發＋收尾後總共跑超過 1 次  : $DUR_TOTAL / $ROUNDS   ← 真正的重複執行率"
echo "  完全沒跑（遺失）             : $LOST / $ROUNDS"
echo "  收尾後仍殘留 .runi           : $RUNILEFT / $ROUNDS"
echo "  stderr 訊息統計:"
sed 's#/tmp/[^ ]*/w9b#<W>#g' "$LAB/t9b-err.txt" | sort | uniq -c | sort -rn | head -12 | sed 's/^/    /'
echo "  重複明細前 10 行:"; head -10 "$LAB/t9b-detail.txt" 2>/dev/null
