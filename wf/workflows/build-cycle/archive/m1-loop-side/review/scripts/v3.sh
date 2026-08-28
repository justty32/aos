#!/bin/bash
# decode_header_id 是定點解析：找第一個 `"id"` 後面跟 `:` 的位置。
# 測試「"id" 出現在別的欄位的字串值裡」能不能騙過它。
R=/tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lead
AOS=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-aadc15218d3266528/build/bin/aos
cd "$R" || exit 1
LOG="$R/hdr.log"

prep() {  # 建世界、投一份、跑一輪拿到真 id，然後把投遞放回去
  rm -rf "$1"; mkdir -p "$1"; $AOS init "$1" >/dev/null
  printf '[{"argv":["/bin/sh","-c","echo GO >> %s"]}]\n' "$LOG" > "$1/.aos/inst.tempd/d.json"
  : > "$LOG"
  $AOS exec "$1" >/dev/null 2>&1
  REALID=$(sed 's/.*"id":"\([^"]*\)".*/\1/' "$1/.aos/inst-head.json")
  printf '[{"argv":["/bin/sh","-c","echo GO >> %s"]}]\n' "$LOG" > "$1/.aos/inst.tempd/d.json"
}

echo "=== 基準：正常 header，同名同內容投遞放回 → 應被吃掉（不執行）==="
prep h1
echo "真 id = $REALID  (第一輪已執行 $(wc -l < "$LOG") 次)"
$AOS exec h1 2>&1 | head -2; echo "exit=${PIPESTATUS[0]}  執行總數=$(wc -l < "$LOG")"

echo
echo "=== A：把 \"id\" 藏在 origin 的字串值裡（排在真 id 之前）==="
prep h2
printf '{"version":1,"origin":"x\\"id\\": \\"0000000000000000\\"","id":"%s","result":null}\n' "$REALID" > h2/.aos/inst-head.json
echo "header = $(cat h2/.aos/inst-head.json)"
$AOS exec h2 2>&1 | head -2; echo "exit=${PIPESTATUS[0]}  執行總數=$(wc -l < "$LOG")"
echo ">>> 若執行總數變 2，代表解析器被騙、去重失效（這次方向是「重跑」）"

echo
echo "=== B：header 被截斷 ==="
prep h3
printf '{"version":1,"id":"%s' "$REALID" > h3/.aos/inst-head.json
$AOS exec h3 2>&1 | head -2; echo "exit=${PIPESTATUS[0]}  執行總數=$(wc -l < "$LOG")"

echo
echo "=== C：header 是空檔 ==="
prep h4
: > h4/.aos/inst-head.json
$AOS exec h4 2>&1 | head -2; echo "exit=${PIPESTATUS[0]}  執行總數=$(wc -l < "$LOG")"

echo
echo "=== D：header 的 id 值不是字串（數字）==="
prep h5
printf '{"version":1,"id":12345,"origin":"aggregated","result":null}\n' > h5/.aos/inst-head.json
$AOS exec h5 2>&1 | head -2; echo "exit=${PIPESTATUS[0]}  執行總數=$(wc -l < "$LOG")"
