#!/usr/bin/env bash
set -u

AOS=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4b6627dc8a8b1254/build/bin/aos
ROOT=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4b6627dc8a8b1254
SOLO=$ROOT/wf/workflows/dispatch/trial/sandbox/solo
TEMPLATE=$SOLO/_template
CASE_DIR=$(mktemp -d "$SOLO/C/repro-tmp.C-06.XXXXXX")
WORLD=$CASE_DIR/world

mkdir -p "$WORLD/.aos"
cp -r "$TEMPLATE/." "$WORLD/"
cd "$WORLD"
"$AOS" agent init

set +e
timeout 2 "$AOS" talk --interface pi < /dev/null > talk-pi.log 2>&1
TALK_RC=$?
set -e

printf 'EXPECT: CLI 清楚回報 --interface pi 尚未內建。\n'
printf 'ACTUAL: exit=%s，完整輸出如下：\n' "$TALK_RC"
cat talk-pi.log
printf 'EVIDENCE_DIR: %s\n' "$CASE_DIR"
