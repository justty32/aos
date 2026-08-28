#!/bin/bash
. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens3/env.sh

vcase() {
  local tag="$1"; local mode="$2"; local content="$3"
  W=$LAB/w12-$tag; mkworld "$W"
  cat > "$W/.aos/inst.tempd/1000-0.json" <<EOF
[{"argv":["/bin/sh","-c","echo RAN >> $W/log"]}]
EOF
  case "$mode" in
    del) rm -f "$W/.aos/version" ;;
    dir) rm -f "$W/.aos/version"; mkdir "$W/.aos/version" ;;
    *)   printf '%s' "$content" > "$W/.aos/version" ;;
  esac
  echo "--- version = [$mode:$content] ---"
  echo -n "  exec: "; timeout 10 "$AOS" exec "$W" 2>&1 | tr '\n' '|'; echo " rc=${PIPESTATUS[0]}"
  timeout 10 "$AOS" exec "$W" >/dev/null 2>&1; echo "  exec rc=$?"
  echo -n "  deliver: "; echo '[{"argv":["/bin/true"]}]' | timeout 10 "$AOS" deliver "$W" 2>&1 | tr '\n' '|'
  echo '[{"argv":["/bin/true"]}]' | timeout 10 "$AOS" deliver "$W" >/dev/null 2>&1; echo "  deliver rc=$?"
  echo "  跑了嗎: [$(cat "$W/log" 2>/dev/null)]"
}

echo "############ 12 .aos/version 異常 ############"
vcase missing del ''
vcase empty  x  ''
vcase two    x  '2\n'
vcase two_real x "$(printf '2\n')"
vcase nonnum x 'abc'
vcase nolf   x '1'
vcase extra  x '1
trailing'
vcase dir    dir ''
