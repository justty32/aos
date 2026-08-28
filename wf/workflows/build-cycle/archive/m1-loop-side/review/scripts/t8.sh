#!/bin/bash
# 8：deliver 與 exec 併發交錯，找「投遞被吃掉沒執行」或「重複執行」
. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens3/env.sh
N=${1:-300}; STREAMS=${2:-1}; TAG=${3:-A}
W=$LAB/w8-$TAG; mkworld "$W"
LOG=$W/exec.log; : > "$LOG"
: > "$LAB/exec8-$TAG.err"

"$AOS" exec --loop 1 "$W" >>"$LAB/exec8-$TAG.err" 2>&1 &
LOOP=$!

deliverstream() {
  local s=$1
  for i in $(seq 1 $N); do
    printf '%s\n' '[{"argv":["/bin/sh","-c","echo M'"${s}_${i}"' >> '"$LOG"'"]}]' \
      | "$AOS" deliver "$W" >>"$LAB/dlv8-$TAG.out" 2>>"$LAB/dlv8-$TAG.err"
    echo "M${s}_${i}" >> "$LAB/sent8-$TAG.txt"
  done
}
: > "$LAB/sent8-$TAG.txt"; : > "$LAB/dlv8-$TAG.out"; : > "$LAB/dlv8-$TAG.err"
for s in $(seq 1 $STREAMS); do deliverstream $s & done
wait $(jobs -p | grep -v "$LOOP") 2>/dev/null
# 等投遞流結束
for job in $(jobs -p); do [ "$job" != "$LOOP" ] && wait "$job" 2>/dev/null; done

sleep 1
kill -TERM $LOOP 2>/dev/null; wait $LOOP 2>/dev/null
# 收尾：把還沒吃完的都跑掉
for k in $(seq 1 40); do
  "$AOS" exec "$W" >>"$LAB/exec8-$TAG.err" 2>&1
  left=$(ls -A "$W/.aos/inst.tempd" 2>/dev/null | grep -c '\.json$')
  [ -e "$W/.aos/inst.json" ] && left=$((left+1))
  [ "$left" = "0" ] && break
done

SENT=$(sort "$LAB/sent8-$TAG.txt" | wc -l)
DELIVERED=$(grep -c '"delivery"' "$LAB/dlv8-$TAG.out")
RUN=$(wc -l < "$LOG")
UNIQ=$(sort -u "$LOG" | wc -l)
echo "== 8-$TAG: $STREAMS 條投遞流 × $N =="
echo "  送出        : $SENT"
echo "  deliver 成功: $DELIVERED"
echo "  執行總次數  : $RUN"
echo "  執行唯一標記: $UNIQ"
echo "  遺失（送出了但沒跑）: $(comm -23 <(sort -u "$LAB/sent8-$TAG.txt") <(sort -u "$LOG") | wc -l)"
comm -23 <(sort -u "$LAB/sent8-$TAG.txt") <(sort -u "$LOG") | head -5 | sed 's/^/     遺失: /'
echo "  重複執行的標記: $(sort "$LOG" | uniq -d | wc -l)"
sort "$LOG" | uniq -cd | head -5 | sed 's/^/     重複: /'
echo "  deliver stderr: $(wc -l < "$LAB/dlv8-$TAG.err") 行"; head -3 "$LAB/dlv8-$TAG.err" | sed 's/^/     /'
echo "  exec stderr   : $(wc -l < "$LAB/exec8-$TAG.err") 行"; sort "$LAB/exec8-$TAG.err" | uniq -c | sort -rn | head -5 | sed 's/^/     /'
echo "  收尾後殘留: inbox=[$(ls -A "$W/.aos/inst.tempd")] .aos=[$(ls -A "$W/.aos" | tr '\n' ' ')]"
echo "  turn=$(cat "$W/.aos/turn")"
