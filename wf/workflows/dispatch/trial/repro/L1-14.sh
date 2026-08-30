#!/usr/bin/env bash
# 每個子命令的 --help 行為都不一樣：四種 exit code、兩個根本不印用法
set -u
AOS=${AOS:-/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4b6627dc8a8b1254/build/bin/aos}
W=$(mktemp -d); mkdir -p "$W/.aos"; cd "$W"
"$AOS" agent init --name w >/dev/null
for c in run llm tool listen state talk deliver say; do
  out=$("$AOS" $c --help 2>&1); rc=$?
  first=$(printf '%s' "$out" | head -1)
  printf 'aos %-8s --help  exit=%-2s  第一行：%s\n' "$c" "$rc" "${first:-（沒有輸出）}"
done
echo "--- say --help 之後，收件匣多了幾封： $(ls .aos/agents/w/say 2>/dev/null | wc -l)"
echo
echo "EXPECT: 八個子命令的 --help 都印出自己的用法、都以同一個 exit code 結束"
echo "ACTUAL: run/llm/tool/listen/state/talk 印用法但以 exit 2（usage error）結束——「我問了 help」被當成用錯了；"
echo "        deliver 印「無法讀取 --help」exit 1（它把 --help 當成 inst.json 檔名）；"
echo "        say 什麼都不印、exit 0，並把字串 --help 當成一句話投進 agent 收件匣。"
echo "        另外 state --help 與 talk --help 印的 usage 後面是空的，一個選項都沒列"
echo "        （aos agent talk 有 --interface pi，頂層 talk 完全沒提）。"
rm -rf "$W"
