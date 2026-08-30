#!/bin/sh
set -eu

AOS=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4b6627dc8a8b1254/build/bin/aos
ROOT=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4b6627dc8a8b1254
BASE="$ROOT/wf/workflows/dispatch/trial/sandbox/solo/A"
TEMPLATE="$ROOT/wf/workflows/dispatch/trial/sandbox/solo/_template"
WORLD=$(mktemp -d "$BASE/repro-A-01.XXXXXX")

mkdir -p "$WORLD/.aos"
cp -R "$TEMPLATE/." "$WORLD/"
cd "$WORLD"

env PATH=/usr/bin:/bin "$AOS" agent init
env PATH=/usr/bin:/bin "$AOS" say "回覆收到即可"
set +e
env PATH=/usr/bin:/bin timeout 30 "$AOS" run . --step 3 > run.log 2>&1
RUN_EXIT=$?
set -e

WORLD_TURN=$(tr -d '\n' < .aos/turn)
AGENT_TURN=$(sed -n 's/.*"turn": \([0-9][0-9]*\).*/\1/p' .aos/agents/*/status.json | head -1)
LOG_LINES=$(wc -l < run.log | tr -d ' ')

echo "WORLD=$WORLD"
cat .aos/every/agent-*.json
cat run.log
cat .aos/agents/*/status.json
echo "EXPECT: 使用絕對路徑啟動 aos 後，run 應驅動 agent 處理訊息；若排程失敗則 run 應回傳非零並報錯。"
echo "ACTUAL: run exit=$RUN_EXIT，world turn=$WORLD_TURN，agent turn=$AGENT_TURN，run.log lines=$LOG_LINES。"
