#!/bin/sh
# L2-01  `aos agent init` 在既有世界的子資料夾裡會「靜默地把 agent 建到祖先世界」
#
# 期待：在 team/boss/ 裡跑 init，boss/ 變成一個世界，agent 住 boss/.aos/agents/boss。
# 實際：find_folder 往上找到最近的 .aos/（這裡是 repo 根），agent 被建在**祖先世界**，
#       子資料夾完全沒有 .aos/，而且沒有任何警告說「我用的是別的資料夾」。
#
# 用法：sh L2-01.sh   （PATH 需含 aos，或設 AOS_BIN）
set -eu
AOS="${AOS_BIN:-aos}"
ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT

# 一個「已經是世界、但還沒有 agent」的祖先資料夾（等同 repo 根：有 .aos/tools 但沒 agents/*）
mkdir -p "$ROOT/parent/.aos/tools"
# 使用者為 worker 開一個乾淨的空資料夾
mkdir -p "$ROOT/parent/worker"

cd "$ROOT/parent/worker"
"$AOS" agent init --name worker

echo "--- worker/.aos 存在嗎？（期待：存在） ---"
if [ -d "$ROOT/parent/worker/.aos" ]; then echo "PASS: worker 是自己的世界"; else echo "FAIL: worker/.aos 不存在"; fi

echo "--- agent 實際被建在哪？ ---"
find "$ROOT/parent" -type d -name worker -path '*/agents/*' -print

echo "--- 祖先世界被汙染了嗎？（期待：沒有） ---"
if [ -d "$ROOT/parent/.aos/agents/worker" ]; then
  echo "FAIL: agent 被建到祖先世界 parent/.aos/agents/worker，且過程無任何警告"
  exit 1
fi
echo "PASS"
