#!/usr/bin/env bash
# aos 不在 PATH 上時，世界每回合靜默 no-op，run 仍印「1 insts」
set -u
AOS=${AOS:-/home/lorkhan/repo/simple_tools/aos/build/bin/aos}
W=$(mktemp -d)
mkdir -p "$W/.aos"
cd "$W"
"$AOS" agent init --name w >/dev/null
"$AOS" say "把 parse() 改成回傳 optional"
echo "--- every/agent-w.json 裡登記的 argv："
cat .aos/every/agent-w.json
echo "--- 在一個沒有 aos 的 PATH 底下推 5 回合（使用者用絕對路徑呼叫 aos 就是這個情境）："
env PATH=/usr/bin:/bin "$AOS" run . --step 5
echo "--- 每一回合的真實結果："
cat .aos/batch/*/out/*.json | grep -E '"(id|exit|stderr)"'
echo "--- 使用者看得到的狀態："
"$AOS" state
"$AOS" listen --once
echo
echo "EXPECT: run 應該告訴使用者「agent-w 這條指令找不到 aos（exit 127）」，或至少不要把它印成跟成功一樣的『1 insts』"
echo "ACTUAL: run 印 5 次『turn N: 1 insts (1 every), 0 ms』；out/*.json 每一筆都是 exit 127、stderr 空白；"
echo "        aos state 仍是 idle／等待訊息；aos listen --once 印空。使用者完全不知道什麼都沒發生"
rm -rf "$W"
