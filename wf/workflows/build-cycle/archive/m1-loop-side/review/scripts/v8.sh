#!/bin/bash
# 複驗鏡頭 2 的 #2：decode_header_id 會先吃到巢狀物件裡的 "id"
R=/tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lead
AOS=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-aadc15218d3266528/build/bin/aos
cd "$R" || exit 1
LOG="$R/nest.log"

prep() {
  rm -rf "$1"; mkdir -p "$1"; $AOS init "$1" >/dev/null
  printf '[{"argv":["/bin/sh","-c","echo GO >> %s"]}]\n' "$LOG" > "$1/.aos/inst.tempd/d.json"
  : > "$LOG"
  $AOS exec "$1" >/dev/null 2>&1
  REALID=$(sed 's/.*"id":"\([^"]*\)".*/\1/' "$1/.aos/inst-head.json")
  printf '[{"argv":["/bin/sh","-c","echo GO >> %s"]}]\n' "$LOG" > "$1/.aos/inst.tempd/d.json"
}

echo "=== A. 巢狀 result.id 排在頂層 id 之前，且巢狀值 = 真 id、頂層 = 假 id ==="
echo "===    （模擬 M2 把 result 填成物件之後的 header）==="
prep n1
echo "真 id = $REALID"
printf '{"version":1,"result":{"id":"%s"},"origin":"aggregated","id":"0000000000000000"}\n' "$REALID" > n1/.aos/inst-head.json
echo "header = $(cat n1/.aos/inst-head.json)"
$AOS exec n1 2>&1 | head -2; echo "exit=${PIPESTATUS[0]}"
echo "執行總數=$(wc -l < "$LOG")  inbox=[$(ls -1A n1/.aos/inst.tempd/)]"
echo ">>> 若執行總數維持 1 且 inbox 被清空 = 解析器讀到巢狀的 id、把全新的批靜默丟掉"

echo
echo "=== B. 反向：巢狀 id = 假，頂層 id = 真 ==="
prep n2
printf '{"version":1,"result":{"id":"0000000000000000"},"origin":"aggregated","id":"%s"}\n' "$REALID" > n2/.aos/inst-head.json
echo "header = $(cat n2/.aos/inst-head.json)"
$AOS exec n2 2>&1 | head -2; echo "exit=${PIPESTATUS[0]}"
echo "執行總數=$(wc -l < "$LOG")  inbox=[$(ls -1A n2/.aos/inst.tempd/)]"
echo ">>> 若執行總數變 2 = 解析器讀到假 id、去重失效（改成重跑方向）"

echo
echo "=== C. M1 自己寫出來的 header 版面（id 是第二個 key、無巢狀）==="
prep n3
echo "header = $(cat n3/.aos/inst-head.json)"
$AOS exec n3 2>&1 | head -2; echo "exit=${PIPESTATUS[0]}"
echo "執行總數=$(wc -l < "$LOG")"
echo ">>> M1 現行版面不受影響（執行總數應維持 1）"
