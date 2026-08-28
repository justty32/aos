#!/bin/bash
. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens3/env.sh
DOC='[{"argv":["/bin/sh","-c","echo R >> LOGPATH"]}]'

mk() { W=$LAB/w3-$1; mkworld "$W"; }
put() { printf '%s\n' "${DOC//LOGPATH/$W/log}" > "$W/.aos/inst.tempd/$1"; }

echo "############ 3-1 inbox 唯讀 chmod 500 ############"
mk inbox
chmod 500 "$W/.aos/inst.tempd"
echo -n "deliver: "; echo "$DOC" | timeout 5 "$AOS" deliver "$W" 2>&1; echo "  rc=$?"
timeout 5 "$AOS" exec "$W" 2>&1 | sed 's/^/  exec: /';
timeout 5 "$AOS" exec "$W" >/dev/null 2>&1; echo "  exec rc=$?"
chmod 700 "$W/.aos/inst.tempd"; ls -la "$W/.aos/inst.tempd"

echo
echo "############ 3-1b inbox 唯讀但裡面有投遞（彙整刪不掉）############"
mk inbox2
put "1000-0.json"
chmod 500 "$W/.aos/inst.tempd"
timeout 5 "$AOS" exec "$W" 2>&1 | sed 's/^/  /'
timeout 5 "$AOS" exec "$W" >/dev/null 2>&1; echo "  第2次 exec rc=$?"
echo "  log: [$(cat "$W/log" 2>/dev/null | tr '\n' ',')]"
chmod 700 "$W/.aos/inst.tempd"; ls -A "$W/.aos/inst.tempd"

echo
echo "############ 3-1c inbox 完全不可讀 chmod 000 ############"
mk inbox3
chmod 000 "$W/.aos/inst.tempd"
timeout 5 "$AOS" exec "$W" 2>&1 | sed 's/^/  exec: /'
timeout 5 "$AOS" exec "$W" >/dev/null 2>&1; echo "  exec rc=$?"
echo -n "  deliver: "; echo "$DOC" | timeout 5 "$AOS" deliver "$W" 2>&1
chmod 700 "$W/.aos/inst.tempd"

echo
echo "############ 3-2 .aos 唯讀 chmod 500 ############"
mk aosdir
put "1000-0.json"
chmod 500 "$W/.aos"
timeout 5 "$AOS" exec "$W" 2>&1 | sed 's/^/  exec: /'
timeout 5 "$AOS" exec "$W" >/dev/null 2>&1; echo "  exec rc=$?"
echo "  log: [$(cat "$W/log" 2>/dev/null)]"
chmod 700 "$W/.aos"; ls -A "$W/.aos"

echo
echo "############ 3-3 inst.json 唯讀（claim 要 rename 它）############"
mk instjson
echo "$DOC" | sed "s#LOGPATH#$W/log#" > "$W/.aos/inst.json"
chmod 400 "$W/.aos/inst.json"
timeout 5 "$AOS" exec "$W" 2>&1 | sed 's/^/  exec: /'
timeout 5 "$AOS" exec "$W" >/dev/null 2>&1; echo "  exec rc=$?"
echo "  log: [$(cat "$W/log" 2>/dev/null | tr '\n' ',')]"
ls -A "$W/.aos"

echo
echo "############ 3-3b inst.json 不可讀 chmod 000 ############"
mk instjson2
echo "$DOC" > "$W/.aos/inst.json"
chmod 000 "$W/.aos/inst.json"
timeout 5 "$AOS" exec "$W" 2>&1 | sed 's/^/  exec: /'
timeout 5 "$AOS" exec "$W" >/dev/null 2>&1; echo "  exec rc=$?"
chmod 600 "$W/.aos/inst.json"

echo
echo "############ 3-4 header 檔唯讀（彙整要覆蓋它）############"
mk header
put "1000-0.json"
timeout 5 "$AOS" exec "$W" >/dev/null 2>&1
chmod 400 "$W/.aos/inst-head.json"
put "2000-0.json"
timeout 5 "$AOS" exec "$W" 2>&1 | sed 's/^/  exec: /'
timeout 5 "$AOS" exec "$W" >/dev/null 2>&1; echo "  exec rc=$?"
echo "  log: [$(cat "$W/log" 2>/dev/null | tr '\n' ',')]"
ls -la "$W/.aos"
chmod 600 "$W/.aos/inst-head.json"

echo
echo "############ 3-5 世界資料夾本身唯讀 ############"
mk worldro
put "1000-0.json"
chmod 500 "$W"
timeout 5 "$AOS" exec "$W" 2>&1 | sed 's/^/  exec: /'
timeout 5 "$AOS" exec "$W" >/dev/null 2>&1; echo "  exec rc=$?"
chmod 700 "$W"
