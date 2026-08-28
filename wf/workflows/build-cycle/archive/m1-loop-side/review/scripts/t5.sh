#!/bin/bash
. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens3/env.sh

echo "===== 5-1 零長度投遞 ====="
W=$LAB/w5a; mkworld "$W"; IB=$W/.aos/inst.tempd
: > "$IB/1000-0.json"
timeout 10 "$AOS" exec "$W"; echo "rc=$?"; ls -A "$IB"

echo "===== 5-2 只有空白的投遞 ====="
W=$LAB/w5b; mkworld "$W"; IB=$W/.aos/inst.tempd
printf '   \n\t\n' > "$IB/1000-0.json"
timeout 10 "$AOS" exec "$W"; echo "rc=$?"; ls -A "$IB"

echo "===== 5-3 空批次 [] （單獨）====="
W=$LAB/w5c; mkworld "$W"; IB=$W/.aos/inst.tempd
printf '[]' > "$IB/1000-0.json"
timeout 10 "$AOS" exec "$W"; echo "rc=$?"
echo "inbox: [$(ls -A "$IB")]"; ls -A "$W/.aos"
echo "turn=$(cat "$W/.aos/turn")"

echo "===== 5-4 空批次 [] + 有效投遞混合 ====="
W=$LAB/w5d; mkworld "$W"; IB=$W/.aos/inst.tempd
printf '[]' > "$IB/1000-0.json"
cat > "$IB/2000-0.json" <<EOF
[{"argv":["/bin/sh","-c","echo MIX >> $W/log"]}]
EOF
timeout 10 "$AOS" exec "$W"; echo "rc=$?"
echo "log: $(cat "$W/log" 2>/dev/null)"; echo "inbox: [$(ls -A "$IB")]"

echo "===== 5-5 aos deliver 收不收空批次 [] ====="
W=$LAB/w5e; mkworld "$W"
echo -n '[]' | "$AOS" deliver "$W"; echo "rc=$?"
echo '' | "$AOS" deliver "$W"; echo "空輸入 rc=$?"
ls -A "$W/.aos/inst.tempd"
