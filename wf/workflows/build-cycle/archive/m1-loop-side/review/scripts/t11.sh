#!/bin/bash
. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens3/env.sh

turncase() {
  local tag="$1"; shift
  W=$LAB/w11-$tag; mkworld "$W"
  printf "$1" > "$W/.aos/turn"
  cat > "$W/.aos/inst.tempd/1000-0.json" <<EOF
[{"argv":["/bin/sh","-c","echo RAN >> $W/log"]}]
EOF
  echo "--- turn 內容 = $(od -c "$W/.aos/turn" | head -2 | tr '\n' ' ') ---"
  timeout 10 "$AOS" exec "$W"; echo "  rc=$?"
  echo "  跑了嗎: [$(cat "$W/log" 2>/dev/null)]"
  echo "  turn 之後: $(od -c "$W/.aos/turn" | head -2 | tr '\n' ' ')"
  echo "  .aos 殘留: $(ls -A "$W/.aos" | tr '\n' ' ')"
  echo "  inbox: [$(ls -A "$W/.aos/inst.tempd")]"
}

echo "############ 11 .aos/turn 損壞 ############"
turncase abc      'abc\n'
turncase huge     '99999999999999999999999999\n'
turncase neg      '-5\n'
turncase empty    ''
turncase nolf     '7'
turncase onlylf   '\n'
turncase leadws   ' 7\n'
turncase u64max   '18446744073709551615\n'
turncase binary   '\x00\x01\xff\n'
turncase missing  '0\n'
echo "--- turn 檔不存在（舊世界）---"
W=$LAB/w11-missing; rm -f "$W/.aos/turn"
cat > "$W/.aos/inst.tempd/1000-0.json" <<EOF
[{"argv":["/bin/sh","-c","echo RAN2 >> $W/log"]}]
EOF
timeout 10 "$AOS" exec "$W"; echo "  rc=$?"
echo "  log: [$(cat "$W/log" 2>/dev/null | tr '\n' ',')]"
echo "  turn: $(cat "$W/.aos/turn" 2>/dev/null || echo 沒建)"
