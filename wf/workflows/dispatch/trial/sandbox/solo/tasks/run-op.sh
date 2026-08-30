#!/usr/bin/env bash
# usage: run-op.sh <A|B|C|D>
set -u
OP="$1"
ROOT=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4b6627dc8a8b1254
T="$ROOT/wf/workflows/dispatch/trial/sandbox/solo/tasks"
O="$ROOT/wf/workflows/dispatch/trial/sandbox/solo/out"
mkdir -p "$O"
codex exec -m gpt-5.6-sol -C "$ROOT" --dangerously-bypass-approvals-and-sandbox \
  -o "$O/$OP.report.md" - < "$T/$OP.full.md" > "$O/$OP.stdout.log" 2>&1
echo "op $OP exit=$?"
