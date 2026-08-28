#!/bin/bash
R=/tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lead
AOS=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-aadc15218d3266528/build/bin/aos
cd "$R" || exit 1
LOG="$R/loop2.log"

echo "=== turn 壞掉的世界在 --loop 下會怎樣（每輪都回 1 但照樣做事？）==="
rm -rf L1; mkdir -p L1; $AOS init L1 >/dev/null
echo "abc" > L1/.aos/turn
: > "$LOG"
for i in 1 2 3; do
  printf '[{"argv":["/bin/sh","-c","echo R%s >> %s"]}]\n' "$i" "$LOG" > p.json
  $AOS deliver L1 -f p.json >/dev/null 2>&1
  $AOS exec L1 2>&1 | head -1
  echo "  round$i exit=${PIPESTATUS[0]} 累計執行=$(wc -l < "$LOG") turn=[$(cat L1/.aos/turn)]"
done
echo ">>> 若每輪 exit=1 但執行數持續增加 = 世界照跑卻永遠回報失敗"

echo
echo "=== 正常世界的 turn 遞增 ==="
rm -rf L2; mkdir -p L2; $AOS init L2 >/dev/null
echo "init 後 turn=$(cat L2/.aos/turn)"
printf '[{"argv":["/bin/true"]}]\n' > p2.json
$AOS deliver L2 -f p2.json >/dev/null 2>&1; $AOS exec L2 >/dev/null 2>&1
echo "一回合後 turn=$(cat L2/.aos/turn)"
$AOS exec L2 >/dev/null 2>&1
echo "空轉一回合後 turn=$(cat L2/.aos/turn)  (§B-3：沒回合就不該遞增)"
echo "version 全程=$(cat L2/.aos/version | tr -d '\n')  (MUST NOT bump)"
