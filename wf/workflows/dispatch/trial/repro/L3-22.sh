#!/usr/bin/env bash
set -u

AOS="${AOS:-/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a15b3afb7ede212cc/build/bin/aos}"
SBX=$(mktemp -d /tmp/l3-22-XXXXXX)
FOREIGN_PID=""

cleanup() {
  if test -n "$FOREIGN_PID" && kill -0 "$FOREIGN_PID" 2>/dev/null; then
    kill -TERM "$FOREIGN_PID" 2>/dev/null || true
  fi
  rm -rf "$SBX"
}
trap cleanup EXIT

export HOME="$SBX/home"
mkdir -p "$HOME" "$SBX/world"
export AOS_HOME="$HOME/.aos"
cd "$SBX/world" || exit 2

timeout 10 "$AOS" agent init --name worker --engine pi >/dev/null
sleep 60 &
FOREIGN_PID=$!
printf '%s\n' "$FOREIGN_PID" >.aos/run.pid

timeout 10 "$AOS" stop >"$SBX/stop.out" 2>"$SBX/stop.err"
STOP_RC=$?
sleep 0.1

if kill -0 "$FOREIGN_PID" 2>/dev/null; then
  ALIVE=yes
else
  ALIVE=no
fi

echo "EXPECT: run.pid 若碰巧指到無關的存活 PID，aos stop 必須拒絕誤殺，無關 sleep 應保持存活"
echo "ACTUAL: stop exit=$STOP_RC，輸出「$(tr '\n' ' ' <"$SBX/stop.out")」，foreign_pid=$FOREIGN_PID，alive_after_stop=$ALIVE"

if test "$ALIVE" = yes; then
  echo PASS
  exit 0
fi
echo FAIL
exit 1
