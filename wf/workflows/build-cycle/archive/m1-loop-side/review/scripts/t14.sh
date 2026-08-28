#!/bin/bash
. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens3/env.sh

echo "############ 14 aos init 在已 init 的世界重跑 ############"
W=$LAB/w14; mkworld "$W"
# 造出一個「有狀態」的世界：turn=3、有 .runi、有待彙整投遞、有 header
cat > "$W/.aos/inst.tempd/1000-0.json" <<EOF
[{"argv":["/bin/sh","-c","echo R >> $W/log"]}]
EOF
timeout 10 "$AOS" exec "$W" >/dev/null 2>&1
printf '3\n' > "$W/.aos/turn"
echo '[{"argv":["/bin/true"]}]' > "$W/.aos/inst.json"
echo '[{"argv":["/bin/false"]}]' > "$W/.aos/inst.json.runi"
echo '[{"argv":["/bin/true"]}]' > "$W/.aos/inst.tempd/5555-0.json"
echo "--- 重跑前 ---"
ls -la "$W/.aos"; ls -la "$W/.aos/inst.tempd"
echo "turn=$(cat "$W/.aos/turn")  head=$(cat "$W/.aos/inst-head.json")"
S_TURN=$(md5sum "$W/.aos/turn"); S_INST=$(md5sum "$W/.aos/inst.json"); S_RUNI=$(md5sum "$W/.aos/inst.json.runi")
echo "--- aos init 重跑 ---"
"$AOS" init "$W"; echo "rc=$?"
echo "--- 重跑後 ---"
ls -la "$W/.aos"; ls -la "$W/.aos/inst.tempd"
echo "turn=$(cat "$W/.aos/turn")"
echo "version=$(cat "$W/.aos/version")"
md5sum "$W/.aos/turn" "$W/.aos/inst.json" "$W/.aos/inst.json.runi"
echo "原本: $S_TURN / $S_INST / $S_RUNI"

echo
echo "--- 14b：.aos 存在但殘缺（只有 .aos 目錄，沒有 version）時重 init ---"
W=$LAB/w14b; rm -rf "$W"; mkdir -p "$W/.aos"
"$AOS" init "$W"; echo "rc=$?"
ls -la "$W/.aos"

echo
echo "--- 14c：.aos 是個檔案不是目錄 ---"
W=$LAB/w14c; rm -rf "$W"; mkdir -p "$W"; echo x > "$W/.aos"
"$AOS" init "$W"; echo "init rc=$?"
timeout 5 "$AOS" exec "$W"; echo "exec rc=$?"
echo '[{"argv":["/bin/true"]}]' | timeout 5 "$AOS" deliver "$W"; echo "deliver rc=$?"

echo
echo "--- 14d：init 到不存在的資料夾 / 檔案 ---"
"$AOS" init "$LAB/does-not-exist"; echo "rc=$?"
"$AOS" init /etc/passwd; echo "rc=$?"
