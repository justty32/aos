#!/usr/bin/env bash
# aos say --help 把 "--help" 當成訊息送給 agent
set -u
AOS=${AOS:-/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4b6627dc8a8b1254/build/bin/aos}
W=$(mktemp -d); mkdir -p "$W/.aos"; cd "$W"
"$AOS" agent init --name w >/dev/null
before=$(ls .aos/agents/w/say 2>/dev/null | wc -l)
echo "--- aos say --help 的輸出："
"$AOS" say --help; echo "exit=$?"
after=$(ls .aos/agents/w/say 2>/dev/null | wc -l)
echo "--- say/ 裡的檔案數：$before -> $after"
echo "--- 那個檔的內容："
cat .aos/agents/w/say/* 2>/dev/null
echo
echo "--- 對照：其他子命令的 --help"
"$AOS" listen --help; echo "listen --help exit=$?"
"$AOS" deliver --help; echo "deliver --help exit=$?"
echo
echo "EXPECT: aos say --help 印出 say 的用法，不送出任何訊息"
echo "ACTUAL: 什麼都不印、exit=0，並且把字串 '--help' 當成一句話投進 agent 的收件匣（say/ 檔案數 $before -> $after）"
rm -rf "$W"
