#!/bin/bash
# 9c：兩個 exec 的「投遞集合大小不同」→ 共用固定名 .aos/inst.json.temp（O_TRUNC）
#     交錯寫入 → 已發布的批被寫壞 → 整批消失（§D-7 壞批直接丟）
. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens3/env.sh
ROUNDS=${1:-120}
W=$LAB/w9c
CORRUPT=0; LOSTALL=0; TOTALRUN_BAD=0
: > "$LAB/t9c-err.txt"; : > "$LAB/t9c-detail.txt"
for r in $(seq 1 $ROUNDS); do
  mkworld "$W"
  LOG=$W/run.log; : > "$LOG"
  # 先放 400 份小投遞
  for d in $(seq 1 400); do
    printf '%s\n' '[{"argv":["/bin/true","'"$d"'"]}]' > "$W/.aos/inst.tempd/$((10000+d))-0.json"
  done
  # A 先起跑（要彙整 400 份）
  ( "$AOS" exec "$W" > "$LAB/t9c-a.txt" 2>&1 ) &
  A=$!
  # 極短暫之後再灌 400 份，然後起 B（B 會彙整 800 份，內容比 A 長很多）
  for d in $(seq 401 800); do
    printf '%s\n' '[{"argv":["/bin/true","'"$d"'"]}]' > "$W/.aos/inst.tempd/$((10000+d))-0.json"
  done
  ( "$AOS" exec "$W" > "$LAB/t9c-b.txt" 2>&1 ) &
  B=$!
  wait $A $B
  cat "$LAB/t9c-a.txt" "$LAB/t9c-b.txt" >> "$LAB/t9c-err.txt"
  if grep -qh 'JsonSyntax\|NotAnObject\|UnknownKey\|FieldTypeMismatch\|EmptyArgv' "$LAB/t9c-a.txt" "$LAB/t9c-b.txt"; then
    CORRUPT=$((CORRUPT+1))
    { echo "=== round $r 批被寫壞 ==="; grep -h 'record\|inst.json' "$LAB/t9c-a.txt" "$LAB/t9c-b.txt" | head -4; } >> "$LAB/t9c-detail.txt"
  fi
  # 收尾
  for i in 1 2 3; do "$AOS" exec "$W" >> "$LAB/t9c-err.txt" 2>&1; done
  left=$(ls -A "$W/.aos/inst.tempd" | grep -c '\.json$')
  if [ "$left" != "0" ]; then echo "round $r inbox 還剩 $left" >> "$LAB/t9c-detail.txt"; fi
done
echo "== 9c: A（400 份）與 B（800 份）兩個 exec 併發 × $ROUNDS 輪 =="
echo "  已發布的批被寫壞（解析失敗）: $CORRUPT / $ROUNDS"
echo "  stderr 訊息統計:"
sed 's#/tmp/[^ ]*/w9c#<W>#g; s/[0-9]\{3,\}/<N>/g' "$LAB/t9c-err.txt" | sort | uniq -c | sort -rn | head -14 | sed 's/^/    /'
echo "  明細:"; head -30 "$LAB/t9c-detail.txt"
