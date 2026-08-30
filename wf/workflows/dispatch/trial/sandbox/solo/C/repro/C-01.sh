#!/usr/bin/env bash
set -u

AOS=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4b6627dc8a8b1254/build/bin/aos
ROOT=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4b6627dc8a8b1254
SOLO=$ROOT/wf/workflows/dispatch/trial/sandbox/solo
TEMPLATE=$SOLO/_template
CASE_DIR=$(mktemp -d "$SOLO/C/repro-tmp.C-01.XXXXXX")
WORLD=$CASE_DIR/world

mkdir -p "$WORLD/.aos"
cp -r "$TEMPLATE/." "$WORLD/"
cd "$WORLD"

PATH=/usr/bin:/bin "$AOS" agent init
PATH=/usr/bin:/bin "$AOS" say "讀 src/parse.cpp"

set +e
PATH=/usr/bin:/bin "$AOS" run . --step 1 > run.log 2>&1
RUN_RC=$?
set -e

CHILD_EXIT=$(jq -r '.running[0].exit' .aos/state.json)
printf 'EXPECT: 用絕對路徑啟動 aos run 時，內部 agent 也能啟動；否則 run 應非零退出並報錯。\n'
printf 'ACTUAL: run exit=%s，state.json running[0].exit=%s，run.log 如下：\n' "$RUN_RC" "$CHILD_EXIT"
cat run.log
printf 'EVIDENCE_DIR: %s\n' "$CASE_DIR"
