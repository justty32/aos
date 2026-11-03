#!/usr/bin/env bash
# LLM 呼叫失敗的那一回合，使用者的訊息已經被吃掉了：端點修好之後也不會有人回答它
set -u
AOS=${AOS:-/home/lorkhan/repo/simple_tools/aos/build/bin/aos}
export PATH="$(dirname "$AOS"):$PATH"
curl -s -m 5 http://localhost:1234/v1/models >/dev/null || { echo "SKIP: LM Studio 沒開"; exit 0; }
W=$(mktemp -d); mkdir -p "$W/.aos"; cd "$W"
printf 'mini 專案\n' > README.md
"$AOS" agent init --name w >/dev/null
"$AOS" say "只回四個字：收到了嗎"
echo "--- 未讀： $(ls .aos/agents/w/say | wc -l) 封"
echo "--- 端點壞掉時推 1 回合（模擬 LM Studio 還沒開）："
AOS_LLM_URL=http://localhost:19999/v1 timeout 60 "$AOS" run . --step 1; echo "run exit=$?"
echo "--- 未讀剩： $(ls .aos/agents/w/say 2>/dev/null | wc -l) 封"
echo "--- 現在端點修好了，再推 4 回合："
timeout 300 "$AOS" run . --step 4
echo "--- 整份對話："; "$AOS" listen --once
echo
echo "EXPECT: 那一回合失敗了，使用者的話應該還留在收件匣，等端點修好後被處理"
echo "ACTUAL: 失敗的那一回合就把 say/ 檔案吃掉了（未讀 1 → 0），只在 log.md 留下一行 user 訊息；"
echo "        端點修好後再推幾回合，agent 沒有任何 assistant 回覆——那句話永遠不會被回答，"
echo "        而且 aos 從頭到尾沒告訴使用者「你剛剛那句話掉了，請再說一次」。"
rm -rf "$W"
