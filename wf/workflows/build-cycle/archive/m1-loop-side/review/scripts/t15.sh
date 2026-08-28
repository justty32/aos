#!/bin/bash
. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens3/env.sh

echo "############ 15a 整組殘留（SPEC 保證的那條） ############"
W=$LAB/w15a; mkworld "$W"
echo '[{"argv":["/bin/sh","-c","echo A >> $W/15a.log"]}]' > /dev/null
cat > "$W/.aos/inst.tempd/1000-0.json" <<EOF
[{"argv":["/bin/sh","-c","echo A >> $W/log"]}]
EOF
"$AOS" exec "$W"; echo "exec1 rc=$?"
echo "log after exec1:"; cat "$W/log"
echo "head: $(cat "$W/.aos/inst-head.json")"
# 模擬「發布成功但投遞沒刪掉」：把同名同內容投遞放回去
cat > "$W/.aos/inst.tempd/1000-0.json" <<EOF
[{"argv":["/bin/sh","-c","echo A >> $W/log"]}]
EOF
"$AOS" exec "$W"; echo "exec2 rc=$?"
echo "log after exec2 (應該還是只有一行 A):"; cat "$W/log"
echo "inbox after exec2:"; ls -la "$W/.aos/inst.tempd"

echo
echo "############ 15b 部分殘留 + 新投遞（SPEC 明說不保證） ############"
W=$LAB/w15b; mkworld "$W"
cat > "$W/.aos/inst.tempd/1000-0.json" <<EOF
[{"argv":["/bin/sh","-c","echo OLD >> $W/log"]}]
EOF
cat > "$W/.aos/inst.tempd/1000-1.json" <<EOF
[{"argv":["/bin/sh","-c","echo OLD2 >> $W/log"]}]
EOF
"$AOS" exec "$W"; echo "exec1 rc=$?"
cat "$W/log"
# 殘留其中一份 + 新投遞
cat > "$W/.aos/inst.tempd/1000-0.json" <<EOF
[{"argv":["/bin/sh","-c","echo OLD >> $W/log"]}]
EOF
cat > "$W/.aos/inst.tempd/2000-0.json" <<EOF
[{"argv":["/bin/sh","-c","echo NEW >> $W/log"]}]
EOF
"$AOS" exec "$W"; echo "exec2 rc=$?"
echo "log after exec2:"; cat "$W/log"
echo "inbox:"; ls "$W/.aos/inst.tempd"

echo
echo "############ 15c 陳舊 header + 全新投遞恰好同名同內容（資料遺失？） ############"
W=$LAB/w15c; mkworld "$W"
cat > "$W/.aos/inst.tempd/1234-0.json" <<EOF
[{"argv":["/bin/sh","-c","echo TURN1 >> $W/log"]}]
EOF
"$AOS" exec "$W"; echo "exec1 rc=$?"
echo "log: $(cat "$W/log")"
echo "inbox 清空了嗎: $(ls -A "$W/.aos/inst.tempd" | wc -l) 個檔"
echo "head: $(cat "$W/.aos/inst-head.json")"
# 現在是一個「全新的」投遞：pid 被回收成 1234、seq 從 0 起、內容剛好一樣
cat > "$W/.aos/inst.tempd/1234-0.json" <<EOF
[{"argv":["/bin/sh","-c","echo TURN1 >> $W/log"]}]
EOF
echo "投了新的一份，內容應該再跑一次:"
"$AOS" exec "$W"; echo "exec2 rc=$?"
echo "log after exec2 (期望兩行 TURN1):"; cat "$W/log"
echo "inbox after exec2:"; ls -la "$W/.aos/inst.tempd"
echo "turn=$(cat "$W/.aos/turn")"
