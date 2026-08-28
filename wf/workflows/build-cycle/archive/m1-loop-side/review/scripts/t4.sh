#!/bin/bash
. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens3/env.sh
run() { echo "=== $1 ==="; }

W=$LAB/w4a; mkworld "$W"; IB=$W/.aos/inst.tempd
run "4-1 子目錄 sub.json"
mkdir "$IB/sub.json"
timeout 10 "$AOS" exec "$W"; echo "rc=$?"
ls -la "$IB"

W=$LAB/w4b; mkworld "$W"; IB=$W/.aos/inst.tempd
run "4-2 symlink → 存在的合法投遞"
cat > "$LAB/real.json" <<EOF
[{"argv":["/bin/sh","-c","echo VIA_SYMLINK >> $W/log"]}]
EOF
ln -s "$LAB/real.json" "$IB/link-ok.json"
timeout 10 "$AOS" exec "$W"; echo "rc=$?"
echo "log: $(cat "$W/log" 2>/dev/null)"; ls -la "$IB"

W=$LAB/w4c; mkworld "$W"; IB=$W/.aos/inst.tempd
run "4-3 symlink → 不存在"
ln -s /nonexistent/nope "$IB/dangling.json"
timeout 10 "$AOS" exec "$W"; echo "rc=$?"
ls -la "$IB"

W=$LAB/w4d; mkworld "$W"; IB=$W/.aos/inst.tempd
run "4-4 symlink → /etc/passwd"
ln -s /etc/passwd "$IB/passwd.json"
timeout 10 "$AOS" exec "$W"; echo "rc=$?"
ls -la "$IB"
echo "被隔離的檔還是 symlink 嗎（原檔有沒有被動到）:"; ls -la /etc/passwd | head -1

W=$LAB/w4e; mkworld "$W"; IB=$W/.aos/inst.tempd
run "4-5 .temp 殘檔 + 既有 .bad 檔"
echo '[{"argv":["/bin/true"]}]' > "$IB/9999-0.json.temp"
echo 'garbage' > "$IB/8888-0.json.bad"
cat > "$IB/7777-0.json" <<EOF
[{"argv":["/bin/sh","-c","echo REAL >> $W/log"]}]
EOF
timeout 10 "$AOS" exec "$W"; echo "rc=$?"
echo "log: $(cat "$W/log" 2>/dev/null)"; ls -la "$IB"

W=$LAB/w4f; mkworld "$W"; IB=$W/.aos/inst.tempd
run "4-6 FIFO 名為 fifo.json（預期會不會卡住？10 秒 timeout）"
mkfifo "$IB/fifo.json"
timeout 10 "$AOS" exec "$W"; echo "rc=$? (124=timeout 逾時被殺)"
ls -la "$IB"

W=$LAB/w4g; mkworld "$W"; IB=$W/.aos/inst.tempd
run "4-7 怪檔名：空白／換行／UTF-8／超長／多個點"
cat > "$IB/has space.json" <<EOF
[{"argv":["/bin/sh","-c","echo SPACE >> $W/log"]}]
EOF
cat > "$IB/$(printf 'new\nline').json" <<EOF
[{"argv":["/bin/sh","-c","echo NEWLINE >> $W/log"]}]
EOF
cat > "$IB/中文檔名.json" <<EOF
[{"argv":["/bin/sh","-c","echo UTF8 >> $W/log"]}]
EOF
LONG=$(printf 'x%.0s' $(seq 1 240))
cat > "$IB/$LONG.json" <<EOF
[{"argv":["/bin/sh","-c","echo LONG >> $W/log"]}]
EOF
cat > "$IB/a.b.json" <<EOF
[{"argv":["/bin/sh","-c","echo DOTDOT >> $W/log"]}]
EOF
cat > "$IB/.hidden.json" <<EOF
[{"argv":["/bin/sh","-c","echo HIDDEN >> $W/log"]}]
EOF
ls -la "$IB"
timeout 10 "$AOS" exec "$W"; echo "rc=$?"
echo "log:"; cat "$W/log" 2>/dev/null
echo "inbox 剩下:"; ls -A "$IB"
