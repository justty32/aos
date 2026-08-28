#!/bin/bash
. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens3/env.sh
WT=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-aadc15218d3266528
EXT4=/home/lorkhan/.cache/aos-lens3
rm -rf "$EXT4"; mkdir -p "$EXT4"

echo "=== 檔案系統確認 ==="
df -T /tmp | tail -1
df -T "$EXT4" | tail -1
stat -c '%d %n' /tmp "$EXT4"

echo
echo "=== 2-1 來源檔在 /tmp(tmpfs)、世界在 ext4 → deliver ==="
W=$EXT4/world; rm -rf "$W"; mkdir -p "$W"; "$AOS" init "$W"
SRC=/tmp/aos-lens3-src.json
printf '%s\n' '[{"argv":["/bin/sh","-c","echo XDEV >> '"$W"'/log"]}]' > "$SRC"
"$AOS" deliver "$W" -f "$SRC"; echo "  rc=$?"
ls -la "$W/.aos/inst.tempd"
stat -c '  投遞檔 dev=%d  來源檔 dev=%d' "$W/.aos/inst.tempd/"*.json "$SRC"
"$AOS" exec "$W"; echo "  exec rc=$?"; echo "  log: $(cat "$W/log")"

echo
echo "=== 2-2 反向：來源在 ext4、世界在 /tmp(tmpfs) ==="
W2=$LAB/w2-tmpfs; mkworld "$W2"
SRC2=$EXT4/src.json
printf '%s\n' '[{"argv":["/bin/sh","-c","echo XDEV2 >> '"$W2"'/log"]}]' > "$SRC2"
"$AOS" deliver "$W2" -f "$SRC2"; echo "  rc=$?"
"$AOS" exec "$W2"; echo "  exec rc=$?"; echo "  log: $(cat "$W2/log")"

echo
echo "=== 2-3 inbox 本身是跨檔案系統的 symlink（.aos/inst.tempd -> /tmp/...）==="
W3=$EXT4/world3; rm -rf "$W3"; mkdir -p "$W3"; "$AOS" init "$W3"
rmdir "$W3/.aos/inst.tempd"
REALIB=/tmp/aos-lens3-inbox; rm -rf "$REALIB"; mkdir -p "$REALIB"
ln -s "$REALIB" "$W3/.aos/inst.tempd"
printf '%s\n' '[{"argv":["/bin/sh","-c","echo XDEV3 >> '"$W3"'/log"]}]' | "$AOS" deliver "$W3"; echo "  deliver rc=$?"
ls -la "$REALIB"
"$AOS" exec "$W3"; echo "  exec rc=$?"; echo "  log: $(cat "$W3/log" 2>/dev/null)"
ls -la "$REALIB"; ls -la "$W3/.aos"

echo
echo "=== 2-4 .aos/inst.json 是跨 fs 的 symlink（claim 的 rename 目標）==="
W4=$EXT4/world4; rm -rf "$W4"; mkdir -p "$W4"; "$AOS" init "$W4"
printf '%s\n' '[{"argv":["/bin/sh","-c","echo XDEV4 >> '"$W4"'/log"]}]' > /tmp/aos-lens3-inst.json
ln -s /tmp/aos-lens3-inst.json "$W4/.aos/inst.json"
"$AOS" exec "$W4"; echo "  exec rc=$?"; echo "  log: $(cat "$W4/log" 2>/dev/null)"
ls -la "$W4/.aos"
echo "  /tmp 的原檔還在嗎: $(ls -la /tmp/aos-lens3-inst.json 2>&1)"
