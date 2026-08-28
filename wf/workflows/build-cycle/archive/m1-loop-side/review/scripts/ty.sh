#!/bin/bash
. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens3/env.sh

echo "===== Y-1 .aos/inst.json 是斷掉的 symlink → 世界被無聲卡死 ====="
W=$LAB/wy1; mkworld "$W"; LOG=$W/run.log; : > "$LOG"
ln -s /nonexistent/gone "$W/.aos/inst.json"
for i in 1 2 3; do
  printf '%s\n' '[{"argv":["/bin/sh","-c","echo M'"$i"' >> '"$LOG"'"]}]' | "$AOS" deliver "$W" >/dev/null
done
for i in 1 2 3; do
  "$AOS" exec "$W" > "$LAB/y1.txt" 2>&1; echo "  exec#$i rc=$?  stderr=[$(cat "$LAB/y1.txt")]"
done
echo "  log（應該有 M1 M2 M3）: [$(tr '\n' ',' < "$LOG")]"
echo "  inbox 堆積: $(ls -A "$W/.aos/inst.tempd" | wc -l) 份"
echo "  turn=$(cat "$W/.aos/turn")"
echo "  --- 換成 --loop（會不會至少報錯或退出）---"
timeout 3 "$AOS" exec --loop 100 "$W" > "$LAB/y1loop.txt" 2>&1; echo "  loop 被 timeout 殺掉 rc=$? ; 輸出 $(wc -l < "$LAB/y1loop.txt") 行"
echo "  --- 對照：把 symlink 移掉就恢復 ---"
rm "$W/.aos/inst.json"; "$AOS" exec "$W" >/dev/null 2>&1; echo "  rc=$? log=[$(tr '\n' ',' < "$LOG")]"

echo
echo "===== Y-2 .aos/turn 是目錄 ====="
W=$LAB/wy2; mkworld "$W"; LOG=$W/run.log; : > "$LOG"
rm -f "$W/.aos/turn"; mkdir "$W/.aos/turn"
printf '%s\n' '[{"argv":["/bin/sh","-c","echo R >> '"$LOG"'"]}]' > "$W/.aos/inst.tempd/1000-0.json"
"$AOS" exec "$W" > "$LAB/y2.txt" 2>&1; echo "  rc=$? stderr=[$(cat "$LAB/y2.txt")]"
echo "  log=[$(tr '\n' ',' < "$LOG")]  .aos=[$(ls -A "$W/.aos" | tr '\n' ' ')]"

echo
echo "===== Y-3 exec 被 SIGKILL：退出碼、孤兒子行程、.runi 死鎖（正確取 rc）====="
W=$LAB/wy3; mkworld "$W"; LOG=$W/run.log; : > "$LOG"
printf '%s\n' '[{"argv":["/bin/sh","-c","sleep 4; echo ORPHAN_DONE >> '"$LOG"'"]}]' | "$AOS" deliver "$W" >/dev/null
"$AOS" exec "$W" & E=$!
sleep 1; kill -9 $E; wait $E 2>/dev/null
echo "  被 KILL 後 .aos: [$(ls -A "$W/.aos" | tr '\n' ' ')]"
"$AOS" exec "$W" > "$LAB/y3.txt" 2>&1; echo "  後續 exec rc=$?  stderr=[$(cat "$LAB/y3.txt")]"
sleep 5
echo "  孤兒子行程仍跑完: log=[$(tr '\n' ',' < "$LOG")]"
"$AOS" exec "$W" >/dev/null 2>&1; echo "  再一次 exec rc=$?（永久拒絕）"
echo "  turn=$(cat "$W/.aos/turn")"

echo
echo "===== Y-4 exec 被 SIGTERM（--loop 有裝 handler）vs 單次 ====="
W=$LAB/wy4; mkworld "$W"; LOG=$W/run.log; : > "$LOG"
printf '%s\n' '[{"argv":["/bin/sh","-c","sleep 4; echo T >> '"$LOG"'"]}]' | "$AOS" deliver "$W" >/dev/null
"$AOS" exec --loop 50 "$W" & E=$!
sleep 1; kill -TERM $E; wait $E; echo "  loop 收到 TERM 後 rc=$?"
echo "  .aos: [$(ls -A "$W/.aos" | tr '\n' ' ')]"
sleep 5; echo "  log=[$(tr '\n' ',' < "$LOG")]"
"$AOS" exec "$W" > "$LAB/y4.txt" 2>&1; echo "  之後 exec rc=$? stderr=[$(cat "$LAB/y4.txt")]"
