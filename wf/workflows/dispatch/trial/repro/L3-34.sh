#!/usr/bin/env bash
set -u

AOS="${AOS:-/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a15b3afb7ede212cc/build/bin/aos}"
SBX=$(mktemp -d /tmp/l3-34-XXXXXX)
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
export PATH="$(dirname "$AOS"):/usr/bin:/bin"

timeout 10 "$AOS" heartbeat init "$SBX/world" --interval 1s >/dev/null 2>&1
AT=$(date '+%Y-%m-%d %H:%M')
ADD_OUT=$(timeout 10 "$AOS" schedule add "$SBX/world" --at "$AT" --id orphan-ask --ask '必須交給 agent 的工作' 2>&1)
ADD_RC=$?
TICK_OUT=$(timeout 10 "$AOS" tick "$SBX/world" 2>&1)
TICK_RC=$?
LS_OUT=$(timeout 10 "$AOS" schedule ls "$SBX/world" 2>&1)
LS_RC=$?

echo "EXPECT: 沒有 agent 時 add 或 tick 應失敗，且一次性行程不能被靜默刪除"
echo "ACTUAL: add exit $ADD_RC；tick exit $TICK_RC 並印「$TICK_OUT」；ls exit $LS_RC 並印「$LS_OUT」"
if [[ $ADD_RC -ne 0 || $TICK_RC -ne 0 || "$LS_OUT" != *"沒有登記任何一次性行程"* ]]; then
  echo PASS
  exit 0
fi
echo FAIL
exit 1
