#!/usr/bin/env bash
set -uo pipefail

AOS=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4b6627dc8a8b1254/build/bin/aos
ROOT=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4b6627dc8a8b1254
BASE="$ROOT/wf/workflows/dispatch/trial/sandbox/solo/D/repro"
WORK=$(mktemp -d "$BASE/D-02.XXXXXX")
trap 'rm -rf -- "$WORK"' EXIT
export PATH="$ROOT/build/bin:$PATH"

mkdir -p "$WORK/.aos"
cd "$WORK"
"$AOS" agent init
"$AOS" say test
printf '%s\n' 'EXPECT: run exits nonzero and state/listen expose the connection failure'
AOS_LLM_URL=http://localhost:19999/v1 timeout 30 "$AOS" run . --step 2
rc=$?
printf 'ACTUAL: run exit=%d; state and listen follow\n' "$rc"
"$AOS" state
"$AOS" listen --once
printf '%s\n' 'ACTUAL: hidden batch record follows'
find "$WORK/.aos/batch" -path '*/out/*.json' -type f -exec sed -n '1,160p' {} \;

