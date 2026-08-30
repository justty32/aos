#!/usr/bin/env bash
set -u

AOS="${AOS:-/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a15b3afb7ede212cc/build/bin/aos}"
SBX=$(mktemp -d /tmp/l3-26-XXXXXX)
DAEMON_PID=""

cleanup() {
  if test -e "$SBX/world/.aos/run.pid"; then
    (cd "$SBX/world" && timeout 10 "$AOS" stop >/dev/null 2>&1) || true
  fi
  if test -n "$DAEMON_PID" && kill -0 "$DAEMON_PID" 2>/dev/null; then
    kill -TERM "$DAEMON_PID" 2>/dev/null || true
  fi
  rm -rf "$SBX"
}
trap cleanup EXIT

export HOME="$SBX/home"
mkdir -p "$HOME" "$SBX/world"
export AOS_HOME="$HOME/.aos"
cd "$SBX/world" || exit 2

timeout 10 "$AOS" agent init --name worker >/dev/null
AOS_LLM_URL=http://localhost:19999/v1 timeout 10 "$AOS" run . --daemon --interval 3000 >/dev/null
DAEMON_PID=$(tr -dc '0-9' <.aos/run.pid)

printf '讓 talk 觸發連線錯誤\n' | timeout -s TERM -k 1 2 "$AOS" talk >"$SBX/talk.out" 2>"$SBX/talk.err"
TALK_RC=$?
TURN=$(tr -dc '0-9' <.aos/turn)
timeout 10 "$AOS" stop >/dev/null 2>&1

echo "EXPECT: talk 應把 daemon 的 LLM 連線錯誤帶回前台並在 2 秒內結束；--interval 3000 不應忙迴圈重試"
echo "ACTUAL: talk_exit=$TALK_RC（124=逾時），2 秒內 world_turn=$TURN，talk_stdout_bytes=$(wc -c <"$SBX/talk.out")，talk_stderr_bytes=$(wc -c <"$SBX/talk.err")"

if test "$TALK_RC" -ne 124 && test "$TURN" -le 2; then
  echo PASS
  exit 0
fi
echo FAIL
exit 1
