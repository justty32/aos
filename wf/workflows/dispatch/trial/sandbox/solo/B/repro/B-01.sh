#!/bin/sh
set -eu

AOS=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4b6627dc8a8b1254/build/bin/aos
ROOT=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4b6627dc8a8b1254
BASE=$ROOT/wf/workflows/dispatch/trial/sandbox/solo/B/repro
TEMPLATE=$ROOT/wf/workflows/dispatch/trial/sandbox/solo/_template
WORK=$(mktemp -d "$BASE/tmp.B-01.XXXXXX")

mkdir -p "$WORK/.aos"
cp -R "$TEMPLATE/." "$WORK/"
cd "$WORK"

# The documented absolute invocation works for the parent process, while the
# generated every entry internally invokes a bare `aos` that is absent here.
PATH=/usr/bin:/bin
export PATH
"$AOS" agent init --engine pi
"$AOS" say "只回覆 OK"

set +e
timeout 30 "$AOS" run . --step 1 >run.log 2>&1
outer_exit=$?
set -e
child_exit=$(/usr/bin/jq -r '.exit' .aos/batch/1/out/*.json)
stderr_bytes=$(/usr/bin/jq -r '.stderr | length' .aos/batch/1/out/*.json)

echo "EXPECT: absolute-path aos run either runs the agent or reports a nonzero failure"
echo "ACTUAL: outer_exit=$outer_exit child_exit=$child_exit child_stderr_bytes=$stderr_bytes log=$(tr '\n' ' ' <run.log)"
