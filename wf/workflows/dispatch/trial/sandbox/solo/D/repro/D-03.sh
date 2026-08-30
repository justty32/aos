#!/usr/bin/env bash
set -uo pipefail

AOS=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4b6627dc8a8b1254/build/bin/aos

printf '%s\n' 'EXPECT: no/such-model is rejected and the command exits nonzero'
printf '%s\n' 'ACTUAL: this intentionally contacts LM Studio; the original trial returned a normal English answer and exit=0'
printf 'hi\n' | AOS_LLM_MODEL=no/such-model timeout 120 "$AOS" llm
rc=$?
printf 'ACTUAL: exit=%d\n' "$rc"

