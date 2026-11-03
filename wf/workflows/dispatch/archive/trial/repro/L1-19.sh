#!/usr/bin/env bash
# 改寫自 D 隊的 D-02.sh
# LM Studio 沒開（最常見的真實故障）時，aos run 照樣 exit 0、state 照樣 idle，
# 真正的錯誤埋在 .aos/batch/<turn>/out/*.json 裡。
set -u
AOS=${AOS:-/home/lorkhan/repo/simple_tools/aos/build/bin/aos}
export PATH="$(dirname "$AOS"):$PATH"
W=$(mktemp -d); mkdir -p "$W/.aos"; cd "$W"
"$AOS" agent init --name w >/dev/null
"$AOS" say "讀 README.md 告訴我它在說什麼"
echo "--- 把端點指到一個沒人在聽的 port，推 2 回合："
AOS_LLM_URL=http://localhost:19999/v1 timeout 60 "$AOS" run . --step 2; echo "run exit=$?"
echo "--- aos state 說："; "$AOS" state
echo "--- aos listen --once 說："; "$AOS" listen --once; echo "(以上為全部)"
echo "--- 真正的錯誤在這裡（沒有任何 aos 指令會帶你來）："
for f in .aos/batch/*/out/*.json; do echo "  $f"; cat "$f"; done
echo
echo "EXPECT: 端點連不上時 aos run 非 0 結束，state 或 listen 要說「連不上 http://localhost:19999/v1，"
echo "        請確認 LM Studio 有沒有開，或用 AOS_LLM_URL 指到正確的位址」"
echo "ACTUAL: run 印兩條正常的 turn 行、exit 0；state 仍是 status=idle、detail=等待訊息；"
echo "        listen --once 只看得到使用者自己那句話。錯誤原文"
echo "        「aos agent: LLM 連線失敗: Failed to connect to localhost port 19999 ...」"
echo "        連同 inner exit=1 只寫在 .aos/batch/<turn>/out/*.json，使用者要先知道有這個檔才找得到。"
rm -rf "$W"
