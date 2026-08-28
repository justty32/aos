#!/bin/bash
# 在 user namespace 裡跑：掛一個 64KB 的 tmpfs 當世界
. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens3/env.sh
M=$LAB/tinyfs
mount -t tmpfs -o size=64k tmpfs "$M" || { echo "MOUNT FAILED"; exit 9; }
df -h "$M" | tail -1
"$AOS" init "$M" || echo "init 失敗"
ls -la "$M/.aos"

echo "=== 1-1 投遞一份塞不下的批（>64KB）==="
python3 -c 'import json;print(json.dumps([{"argv":["/bin/true","Y"*200000]}]))' > /tmp/big.json
"$AOS" deliver "$M" -f /tmp/big.json; echo "  deliver rc=$?"
echo "  inbox 殘留:"; ls -la "$M/.aos/inst.tempd"
df -h "$M" | tail -1

echo
echo "=== 1-2 先塞一個剛好塞得下的投遞，再把剩餘空間吃光，然後 exec（彙整寫 .temp 會 ENOSPC）==="
python3 -c 'import json;print(json.dumps([{"argv":["/bin/sh","-c","echo R >> /tmp/enospc.log"]}]))' > /tmp/small.json
"$AOS" deliver "$M" -f /tmp/small.json; echo "  deliver rc=$?"
ls -la "$M/.aos/inst.tempd"
# 把剩下的空間吃光
dd if=/dev/zero of="$M/filler" bs=1k count=200 2>/dev/null
df -h "$M" | tail -1
echo "  --- exec ---"
"$AOS" exec "$M"; echo "  exec rc=$?"
echo "  .aos:"; ls -la "$M/.aos"
echo "  inbox:"; ls -la "$M/.aos/inst.tempd"
echo "  log: [$(cat /tmp/enospc.log 2>/dev/null)]"
echo "  turn=$(cat "$M/.aos/turn")"

echo
echo "=== 1-3 空出一點點空間：讓批 .temp 寫得下、header 寫不下 ==="
truncate -s 1000 "$M/filler" 2>/dev/null || rm -f "$M/filler"
df -h "$M" | tail -1
ls -la "$M/.aos" "$M/.aos/inst.tempd"
"$AOS" exec "$M"; echo "  exec rc=$?"
echo "  .aos:"; ls -la "$M/.aos"
echo "  log: [$(cat /tmp/enospc.log 2>/dev/null | tr '\n' ',')]"
echo "  turn=$(cat "$M/.aos/turn")"

echo
echo "=== 1-4 空間全放開後再 exec 一次（會不會重複執行 / 殘留能不能自癒）==="
rm -f "$M/filler"
df -h "$M" | tail -1
"$AOS" exec "$M"; echo "  exec rc=$?"
echo "  log: [$(cat /tmp/enospc.log 2>/dev/null | tr '\n' ',')]"
ls -la "$M/.aos" "$M/.aos/inst.tempd"
echo "  turn=$(cat "$M/.aos/turn")"

echo
echo "=== 1-5 init 到一個沒空間的 fs ==="
M2=$LAB/tinyfs2
mkdir -p "$M2"
mount -t tmpfs -o size=4k tmpfs "$M2" || echo mount2 failed
dd if=/dev/zero of="$M2/x" bs=1k count=10 2>/dev/null
df -h "$M2" | tail -1
"$AOS" init "$M2"; echo "  init rc=$?"
ls -la "$M2"
ls -la "$M2/.aos" 2>&1
