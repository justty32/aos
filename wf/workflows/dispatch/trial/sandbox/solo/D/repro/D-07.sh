#!/usr/bin/env bash
set -uo pipefail

AOS=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4b6627dc8a8b1254/build/bin/aos

printf '%s\n' 'EXPECT: the error says that /nonexistent/path does not exist'
"$AOS" run /nonexistent/path --step 1
rc=$?
printf 'ACTUAL: exit=%d; observed error says it cannot create .aos/inbox: Permission denied\n' "$rc"

