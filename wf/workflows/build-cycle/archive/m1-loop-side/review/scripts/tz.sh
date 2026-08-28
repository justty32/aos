#!/bin/bash
. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens3/env.sh

echo "===== Z-1 一顆 FIFO 就把整個世界卡死（含正常投遞）====="
W=$LAB/wz1; mkworld "$W"; IB=$W/.aos/inst.tempd; LOG=$W/run.log; : > "$LOG"
printf '%s\n' '[{"argv":["/bin/sh","-c","echo GOOD >> '"$LOG"'"]}]' > "$IB/1000-0.json"
mkfifo "$IB/0500-0.json"      # 字典序在正常投遞之前
ls -la "$IB"
timeout 6 "$AOS" exec "$W" > "$LAB/z1.txt" 2>&1; echo "  exec rc=$?（124=卡住被 timeout 殺）"
echo "  stderr=[$(cat "$LAB/z1.txt")]"
echo "  log=[$(tr '\n' ',' < "$LOG")]  ← 空的表示正常投遞也沒跑到"
echo "  .aos=[$(ls -A "$W/.aos" | tr '\n' ' ')]  ← 沒有 .runi，鎖也沒拿到"
echo "  --- 同時第二、三個 exec 也一起卡 ---"
timeout 4 "$AOS" exec "$W" >/dev/null 2>&1 & P1=$!
timeout 4 "$AOS" exec "$W" >/dev/null 2>&1 & P2=$!
sleep 1; echo "  卡住的 aos 行程數: $(pgrep -c -f 'build/bin/aos exec' || echo 0)"
wait $P1 $P2 2>/dev/null
echo "  --- deliver 不受影響嗎 ---"
printf '%s\n' '[{"argv":["/bin/true"]}]' | timeout 5 "$AOS" deliver "$W"; echo "  deliver rc=$?"
echo "  --- 把 FIFO 拿掉就恢復 ---"
rm "$IB/0500-0.json"
timeout 10 "$AOS" exec "$W" >/dev/null 2>&1; echo "  exec rc=$?  log=[$(tr '\n' ',' < "$LOG")]"

echo
echo "===== Z-2 是誰都能塞：inbox 是 0777（世界的公開介面）====="
W=$LAB/wz2; mkworld "$W"
stat -c '  %A %n' "$W/.aos" "$W/.aos/inst.tempd"
echo "  umask=$(umask)"

echo
echo "===== Z-3 名字帶多個點的投遞永遠不會被處理也不會被警告（累積）====="
W=$LAB/wz3; mkworld "$W"; IB=$W/.aos/inst.tempd; LOG=$W/run.log; : > "$LOG"
# 很自然的第三方生產者命名：帶毫秒的時間戳
printf '%s\n' '[{"argv":["/bin/sh","-c","echo TS >> '"$LOG"'"]}]' > "$IB/2026-08-28T10:00:00.123.json"
printf '%s\n' '[{"argv":["/bin/sh","-c","echo OK >> '"$LOG"'"]}]' > "$IB/1000-0.json"
for i in 1 2 3; do timeout 8 "$AOS" exec "$W" > "$LAB/z3.txt" 2>&1; echo "  exec#$i rc=$? stderr=[$(cat "$LAB/z3.txt")]"; done
echo "  log=[$(tr '\n' ',' < "$LOG")]"
echo "  inbox 殘留: [$(ls -A "$IB" | tr '\n' ' ')]"
