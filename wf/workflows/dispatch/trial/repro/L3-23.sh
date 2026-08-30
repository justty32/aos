#!/usr/bin/env bash
set -u

AOS="${AOS:-/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a15b3afb7ede212cc/build/bin/aos}"
SBX=$(mktemp -d /tmp/l3-23-XXXXXX)
trap 'rm -rf "$SBX"' EXIT

export HOME="$SBX/home"
mkdir -p "$HOME" "$SBX/world"
export AOS_HOME="$HOME/.aos"
cd "$SBX/world" || exit 2

timeout 10 "$AOS" agent init --name worker --engine pi >/dev/null
timeout 10 "$AOS" say "EMPTY-ID-MUST-STAY" >/dev/null
BEFORE=$(find .aos/agents/worker/say -maxdepth 1 -type f | wc -l)
timeout 10 "$AOS" inbox read "" >"$SBX/read.out" 2>"$SBX/read.err"
READ_RC=$?
AFTER=$(find .aos/agents/worker/say -maxdepth 1 -type f | wc -l)

echo "EXPECT: 顯式空 id 是無效輸入，inbox read 應非 0 且保留唯一一封未讀"
echo "ACTUAL: before=$BEFORE，read_exit=$READ_RC，after=$AFTER，stdout「$(tr '\n' ' ' <"$SBX/read.out")」"

if test "$READ_RC" -ne 0 && test "$AFTER" -eq "$BEFORE"; then
  echo PASS
  exit 0
fi
echo FAIL
exit 1
