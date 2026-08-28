#!/bin/bash
# 9d：兩個 aos exec --loop 同時跑同一世界 + 持續投遞（最貼近實務的災難情境）
. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens3/env.sh
N=${1:-400}; K=${2:-2}
W=$LAB/w9d; mkworld "$W"
LOG=$W/run.log; : > "$LOG"
: > "$LAB/t9d-err.txt"; : > "$LAB/t9d-sent.txt"
PIDS=""
for k in $(seq 1 $K); do
  "$AOS" exec --loop 1 "$W" >> "$LAB/t9d-err.txt" 2>&1 &
  PIDS="$PIDS $!"
done
for i in $(seq 1 $N); do
  printf '%s\n' '[{"argv":["/bin/sh","-c","echo M'"$i"' >> '"$LOG"'"]}]' | "$AOS" deliver "$W" >/dev/null 2>>"$LAB/t9d-err.txt"
  echo "M$i" >> "$LAB/t9d-sent.txt"
done
sleep 2
for p in $PIDS; do kill -TERM $p 2>/dev/null; done
for p in $PIDS; do wait $p 2>/dev/null; done
for i in $(seq 1 20); do "$AOS" exec "$W" >> "$LAB/t9d-err.txt" 2>&1; done

echo "== 9d: $K 個 exec --loop 同時跑 + $N 份投遞 =="
echo "  送出          : $(wc -l < "$LAB/t9d-sent.txt")"
echo "  執行總次數    : $(wc -l < "$LOG")"
echo "  執行唯一標記  : $(sort -u "$LOG" | wc -l)"
echo "  遺失（沒跑過）: $(comm -23 <(sort -u "$LAB/t9d-sent.txt") <(sort -u "$LOG") | wc -l)"
comm -23 <(sort -u "$LAB/t9d-sent.txt") <(sort -u "$LOG") | head -8 | sed 's/^/     遺失: /'
echo "  重複執行的標記: $(sort "$LOG" | uniq -d | wc -l)"
sort "$LOG" | uniq -cd | sort -rn | head -5 | sed 's/^/     重複: /'
echo "  收尾殘留: inbox=$(ls -A "$W/.aos/inst.tempd" | wc -l) 個檔; .aos=[$(ls -A "$W/.aos" | tr '\n' ' ')]"
echo "  stderr 統計:"
sed 's#/tmp/[^ ]*/w9d#<W>#g; s/[0-9]\{3,\}/<N>/g' "$LAB/t9d-err.txt" | sort | uniq -c | sort -rn | head -14 | sed 's/^/    /'
