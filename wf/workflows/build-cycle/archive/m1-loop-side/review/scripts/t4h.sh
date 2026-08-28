#!/bin/bash
. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens3/env.sh
echo "=== 4-8 隔離會不會覆蓋既有的 .bad（§D-8：彙整者 MUST NOT 自動刪 .bad）==="
W=$LAB/w4h; mkworld "$W"; IB=$W/.aos/inst.tempd
echo 'FIRST_BAD_EVIDENCE' > "$IB/1111-0.json.bad"
echo "先放好的 .bad 內容: $(cat "$IB/1111-0.json.bad")"
echo 'not json at all' > "$IB/1111-0.json"
timeout 10 "$AOS" exec "$W"; echo "rc=$?"
ls -la "$IB"
echo ".bad 現在的內容: $(cat "$IB/1111-0.json.bad")"
