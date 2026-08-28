#!/bin/bash
. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens3/env.sh
echo "############ 15d header 命中 + 無關的殘留 inst.json.temp（roll-forward 發布錯的批） ############"
W=$LAB/w15d; mkworld "$W"
cat > "$W/.aos/inst.tempd/1234-0.json" <<EOF
[{"argv":["/bin/sh","-c","echo GOOD >> $W/log"]}]
EOF
"$AOS" exec "$W"; echo "exec1 rc=$?"
echo "log: $(cat "$W/log")"
echo "head: $(cat "$W/.aos/inst-head.json")"
# 同名同內容殘留（觸發去重分支）＋ 一份與這批完全無關的 .temp 殘骸
cat > "$W/.aos/inst.tempd/1234-0.json" <<EOF
[{"argv":["/bin/sh","-c","echo GOOD >> $W/log"]}]
EOF
cat > "$W/.aos/inst.json.temp" <<EOF
[{"argv":["/bin/sh","-c","echo UNRELATED_GARBAGE >> $W/log"]}]
EOF
echo "--- exec2 ---"
"$AOS" exec "$W"; echo "exec2 rc=$?"
echo "log after exec2:"; cat "$W/log"
ls -la "$W/.aos"
