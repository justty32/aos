#!/usr/bin/env bash
set -u

AOS=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4b6627dc8a8b1254/build/bin/aos
ROOT=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4b6627dc8a8b1254
SOLO=$ROOT/wf/workflows/dispatch/trial/sandbox/solo
TEMPLATE=$SOLO/_template
CASE_DIR=$(mktemp -d "$SOLO/C/repro-tmp.C-05.XXXXXX")
WORLD=$CASE_DIR/world

mkdir -p "$WORLD/.aos"
cp -r "$TEMPLATE/." "$WORLD/"
cd "$WORLD"
"$AOS" agent init

set +e
printf 'hello\n' | timeout 2 "$AOS" talk > talk.log 2>&1
TALK_RC=$?
set -e

OUTPUT_BYTES=$(wc -c < talk.log)
QUEUED_MESSAGES=$(find .aos/agents/*/say -type f 2>/dev/null | wc -l)
printf 'EXPECT: talk 自行推進並回覆，或立即說明需要另一個 aos run。\n'
printf 'ACTUAL: 2 秒後 exit=%s，output_bytes=%s，queued_say_files=%s。\n' "$TALK_RC" "$OUTPUT_BYTES" "$QUEUED_MESSAGES"
printf 'EVIDENCE_DIR: %s\n' "$CASE_DIR"
