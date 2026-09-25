#!/usr/bin/env bash
# 把 COMMON.md 併進每份任務書，產生 <op>.full.md
set -eu
T=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4b6627dc8a8b1254/wf/workflows/dispatch/trial/sandbox/solo/tasks
for op in A B C D; do
  awk -v common="$T/COMMON.md" '
    /^<!-- COMMON -->$/ { while ((getline line < common) > 0) print line; close(common); next }
    { print }
  ' "$T/$op.md" > "$T/$op.full.md"
  wc -l "$T/$op.full.md"
done
