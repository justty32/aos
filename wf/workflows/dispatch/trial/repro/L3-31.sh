#!/usr/bin/env bash
set -u

AOS="${AOS:-/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a15b3afb7ede212cc/build/bin/aos}"
SBX=$(mktemp -d /tmp/l3-31-XXXXXX)
RUN_PID=""
cleanup() {
  if [[ -n "$RUN_PID" ]] && kill -0 "$RUN_PID" 2>/dev/null; then
    kill "$RUN_PID" 2>/dev/null || true
    wait "$RUN_PID" 2>/dev/null || true
  fi
  rm -rf "$SBX"
}
trap cleanup EXIT INT TERM

export HOME="$SBX/home"
mkdir -p "$HOME" "$SBX/world"
export AOS_HOME="$HOME/.aos"
export PATH=/usr/bin:/bin

INIT_OUT=$(cd "$SBX/world" && timeout 10 "$AOS" heartbeat init . --interval 1s 2>&1)
INIT_RC=$?
RUN_OUT=$(cd "$SBX/world" && timeout 15 "$AOS" run . --step 1 2>&1)
RUN_RC=$?

echo "EXPECT: heartbeat init 使用目前 aos 的可執行路徑，下一回合不依賴 PATH 並 exit 0"
echo "ACTUAL: init exit $INIT_RC；run exit $RUN_RC；$RUN_OUT"
if [[ $INIT_RC -eq 0 && $RUN_RC -eq 0 ]]; then
  echo PASS
  exit 0
fi
echo FAIL
exit 1
