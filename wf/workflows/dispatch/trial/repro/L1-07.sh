#!/usr/bin/env bash
# lmstudio 世界記不住模型：--model 被靜默吃掉，實際用哪顆腦由跑 run 的那個 shell 的環境變數決定
set -u
AOS=${AOS:-/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4b6627dc8a8b1254/build/bin/aos}
W=$(mktemp -d); mkdir -p "$W/a/.aos" "$W/b/.aos"

cd "$W/a"
"$AOS" agent init --name a --model google/gemma-4-12b-qat; echo "init --model exit=$?"
echo "--- a/engine.json（我指定了 --model google/gemma-4-12b-qat）："
cat .aos/agents/a/engine.json

cd "$W/b"
"$AOS" agent init --name b --engine pi --model deepseek-chat >/dev/null
echo "--- b/engine.json（pi 引擎，同樣的 --model）："
cat .aos/agents/b/engine.json

echo "--- 有沒有任何 aos 指令印得出 a 用哪個模型？"
cd "$W/a"; "$AOS" state
echo
echo "EXPECT: lmstudio 世界也把 model 記進 engine.json，且 aos state 看得到自己接的是哪顆腦"
echo "ACTUAL: lmstudio 的 engine.json 只有 {\"engine\":\"lmstudio\"}，--model 被靜默丟掉、exit 仍是 0；"
echo "        pi 的 engine.json 則完整記下 provider/model/session_id。aos state 兩邊都不印引擎與模型，"
echo "        所以 lmstudio agent 實際用哪顆模型，取決於後來哪個 shell 跑 aos run（AOS_LLM_MODEL），世界檔案裡查不到"
rm -rf "$W"
