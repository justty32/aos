#!/usr/bin/env bash
# 模型名打錯，aos 照樣回一段答案、exit 0，也不說實際回答的是誰
set -u
AOS=${AOS:-/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4b6627dc8a8b1254/build/bin/aos}
echo "--- 端點上有的模型："
curl -s -m 5 http://localhost:1234/v1/models | grep -o '"id": *"[^"]*"' || { echo "SKIP: LM Studio 沒開"; exit 0; }
echo "--- 用一個絕對不存在的模型名呼叫："
out=$(printf '只回一個字：好\n' | AOS_LLM_MODEL=no/such-model-xyz timeout 60 "$AOS" llm 2>&1); rc=$?
echo "exit=$rc"
echo "回覆：$out"
echo
echo "EXPECT: 端點沒有 no/such-model-xyz 這顆模型，aos llm 應該報錯並以非 0 結束"
echo "ACTUAL: exit=0 並正常回了一段內容。aos 不驗證模型名，也不回報實際回答的是哪一顆。"
echo "        agent 的 lmstudio 引擎走同一條路（見 L1-07：engine.json 根本不記 model），"
echo "        所以「我以為在用 A 模型、其實是 B」在 aos 這一層完全查不出來。"
