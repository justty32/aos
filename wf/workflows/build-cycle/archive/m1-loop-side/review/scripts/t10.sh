#!/bin/bash
# 10：exec 進行中（子行程還在跑）有新投遞進來
. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens3/env.sh

echo "===== 10-1 單次 exec 執行中投遞（子行程 sleep 3）====="
W=$LAB/w10a; mkworld "$W"; LOG=$W/run.log; : > "$LOG"
printf '%s\n' '[{"argv":["/bin/sh","-c","sleep 3; echo SLOW >> '"$LOG"'"]}]' | "$AOS" deliver "$W"
( "$AOS" exec "$W" > "$LAB/t10a.txt" 2>&1; echo "exec rc=$?" >> "$LAB/t10a.txt" ) & E=$!
sleep 1
echo "  exec 進行中，.aos 狀態: [$(ls -A "$W/.aos" | tr '\n' ' ')]"
printf '%s\n' '[{"argv":["/bin/sh","-c","echo NEW1 >> '"$LOG"'"]}]' | "$AOS" deliver "$W"; echo "  deliver1 rc=$?"
sleep 0.3
printf '%s\n' '[{"argv":["/bin/sh","-c","echo NEW2 >> '"$LOG"'"]}]' | "$AOS" deliver "$W"; echo "  deliver2 rc=$?"
wait $E; cat "$LAB/t10a.txt" | sed 's/^/  /'
echo "  第一回合結束後 log: [$(tr '\n' ',' < "$LOG")]"
echo "  inbox: [$(ls -A "$W/.aos/inst.tempd" | tr '\n' ' ')]  turn=$(cat "$W/.aos/turn")"
"$AOS" exec "$W" 2>&1 | sed 's/^/  /'; echo "  第二回合 rc=$?"
echo "  最終 log: [$(tr '\n' ',' < "$LOG")]"
echo "  最終 inbox: [$(ls -A "$W/.aos/inst.tempd")]  turn=$(cat "$W/.aos/turn")"

echo
echo "===== 10-2 執行中，另一個 exec 併發（新投遞會被誰吃掉）====="
W=$LAB/w10b; mkworld "$W"; LOG=$W/run.log; : > "$LOG"
printf '%s\n' '[{"argv":["/bin/sh","-c","sleep 3; echo SLOW >> '"$LOG"'"]}]' | "$AOS" deliver "$W"
( "$AOS" exec "$W" > "$LAB/t10b1.txt" 2>&1; echo "rc=$?" >> "$LAB/t10b1.txt" ) & E1=$!
sleep 1
printf '%s\n' '[{"argv":["/bin/sh","-c","echo NEW >> '"$LOG"'"]}]' | "$AOS" deliver "$W"
"$AOS" exec "$W" > "$LAB/t10b2.txt" 2>&1; echo "  第二個 exec rc=$? 訊息: $(cat "$LAB/t10b2.txt")"
echo "  此時 .aos: [$(ls -A "$W/.aos" | tr '\n' ' ')]"
wait $E1; echo "  第一個 exec: $(cat "$LAB/t10b1.txt")"
echo "  log: [$(tr '\n' ',' < "$LOG")]"
"$AOS" exec "$W" >/dev/null 2>&1
echo "  收尾後 log: [$(tr '\n' ',' < "$LOG")]  turn=$(cat "$W/.aos/turn")"
echo "  inbox: [$(ls -A "$W/.aos/inst.tempd")]"

echo
echo "===== 10-3 壓力版：exec --loop 執行慢批，同時 100 份投遞湧入 ====="
W=$LAB/w10c; mkworld "$W"; LOG=$W/run.log; : > "$LOG"
"$AOS" exec --loop 5 "$W" > "$LAB/t10c.txt" 2>&1 & L=$!
for i in $(seq 1 100); do
  printf '%s\n' '[{"argv":["/bin/sh","-c","sleep 0.05; echo K'"$i"' >> '"$LOG"'"]}]' | "$AOS" deliver "$W" >/dev/null 2>&1
done
sleep 5
kill -TERM $L 2>/dev/null; wait $L 2>/dev/null
for i in $(seq 1 20); do "$AOS" exec "$W" >>"$LAB/t10c.txt" 2>&1; done
echo "  送出 100，執行 $(wc -l < "$LOG") 次，唯一 $(sort -u "$LOG" | wc -l)"
echo "  遺失: $(comm -23 <(seq 1 100 | sed 's/^/K/' | sort -u) <(sort -u "$LOG") | wc -l)"
echo "  重複: $(sort "$LOG" | uniq -d | wc -l)"
echo "  inbox 殘留: $(ls -A "$W/.aos/inst.tempd" | wc -l)"
echo "  stderr: $(sed 's#/tmp/[^ ]*/w10c#<W>#g' "$LAB/t10c.txt" | sort | uniq -c | sort -rn | head -5)"
