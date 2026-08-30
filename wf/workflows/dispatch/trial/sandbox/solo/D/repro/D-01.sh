#!/usr/bin/env bash
set -uo pipefail

AOS=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4b6627dc8a8b1254/build/bin/aos
ROOT=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4b6627dc8a8b1254
BASE="$ROOT/wf/workflows/dispatch/trial/sandbox/solo/D/repro"
WORK=$(mktemp -d "$BASE/D-01.XXXXXX")
trap 'rm -rf -- "$WORK"' EXIT

cd "$WORK"
printf '%s\n' 'EXPECT: no-agent run exits nonzero and says to run aos agent init'
"$AOS" run . --step 1
rc=$?
printf 'ACTUAL: exit=%d; the observed message above is "turn 1: idle"\n' "$rc"

