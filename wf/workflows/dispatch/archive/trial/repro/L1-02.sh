#!/usr/bin/env bash
# 說了三句話，state/listen 完全看不出來有未讀
set -u
AOS=${AOS:-/home/lorkhan/repo/simple_tools/aos/build/bin/aos}
W=$(mktemp -d); mkdir -p "$W/.aos"; cd "$W"
"$AOS" agent init --name w >/dev/null
echo "--- init 之後的 state："; "$AOS" state
"$AOS" say "第一句"; "$AOS" say "第二句"; "$AOS" say "第三句"
echo "--- 說完三句之後的 state："; "$AOS" state
echo "--- listen --once："; "$AOS" listen --once; echo "(以上為 listen 的全部輸出)"
echo "--- log.md 大小："; wc -c .aos/agents/w/log.md
echo "--- history.json："; cat .aos/agents/w/history.json
echo "--- 真正的未讀在這裡（使用者要自己知道去翻）："; ls .aos/agents/w/say/
echo
echo "EXPECT: 有 3 封未讀時，aos state 或 aos listen 至少要讓使用者看到自己說過的話／未讀封數"
echo "ACTUAL: state 三句前後完全一樣（idle／等待訊息／turn 0／updated_at 不動）；listen --once 印空；"
echo "        log.md 0 bytes；history.json 是 {\"messages\": []}。未讀只存在 .aos/agents/w/say/ 這個沒有任何指令會列的資料夾"
rm -rf "$W"
