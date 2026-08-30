#!/usr/bin/env bash
# 在既有世界的子資料夾裡 agent init，agent 被靜默建到祖先世界，名字也取自祖先資料夾
set -u
AOS=${AOS:-/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4b6627dc8a8b1254/build/bin/aos}
BASE=$(mktemp -d)/outer-world      # 模擬「我的 repo 根已經是一個 aos 世界」
mkdir -p "$BASE/.aos" "$BASE/src/my-feature"
cd "$BASE/src/my-feature"
echo "--- 我站在： $PWD"
"$AOS" agent init; echo "init exit=$?（印了什麼？上面就是全部）"
echo "--- 我站的地方有 .aos 嗎： $([ -d .aos ] && echo yes || echo no)"
echo "--- agent 實際被建到哪裡："
find "$BASE/.aos/agents" -maxdepth 1 -mindepth 1
echo "--- 於是 aos state 讀的是祖先世界的 agent："
"$AOS" state
echo
echo "EXPECT: 要嘛在 $PWD 就地建世界，要嘛報錯說「這裡沒有 .aos，最近的世界在 $BASE，要用它嗎」"
echo "ACTUAL: 什麼都不印、exit=0，agent 被建到 $BASE/.aos/agents/ 底下，名字取自祖先資料夾 outer-world；"
echo "        使用者站的資料夾連 .aos 都沒有。要就地建，必須先自己 mkdir .aos"
rm -rf "$(dirname "$BASE")"
