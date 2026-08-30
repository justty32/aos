#!/usr/bin/env bash
set -uo pipefail

AOS=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4b6627dc8a8b1254/build/bin/aos
ROOT=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4b6627dc8a8b1254
BASE="$ROOT/wf/workflows/dispatch/trial/sandbox/solo/D/repro"
WORK=$(mktemp -d "$BASE/D-08.XXXXXX")
trap 'rm -rf -- "$WORK"' EXIT

mkdir -p "$WORK/.aos"
cd "$WORK"
"$AOS" agent init
"$AOS" say test
printf '%s\n' 'EXPECT: invoking the documented absolute AOS path is sufficient'
env PATH=/usr/bin:/bin "$AOS" run . --step 2
rc=$?
printf 'ACTUAL: outer run exit=%d; generated batch records show argv aos agent step and exit 127\n' "$rc"
find "$WORK/.aos/batch" -path '*/out/*.json' -type f -exec sed -n '1,160p' {} \;

