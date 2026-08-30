#!/usr/bin/env bash
set -u

AOS="${AOS:-/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a15b3afb7ede212cc/build/bin/aos}"
SBX=$(mktemp -d /tmp/l3-25-XXXXXX)
DAEMON_PID=""
CHILD_PID=""
STEP_PID=""
PI_PID=""

cleanup() {
  if test -e "$SBX/world/.aos/run.pid"; then
    (cd "$SBX/world" && timeout 10 "$AOS" stop >/dev/null 2>&1) || true
  fi
  if test -n "$PI_PID" && kill -0 "$PI_PID" 2>/dev/null; then
    kill -KILL "$PI_PID" 2>/dev/null || true
  fi
  if test -n "$STEP_PID" && kill -0 "$STEP_PID" 2>/dev/null; then
    kill -KILL "$STEP_PID" 2>/dev/null || true
  fi
  if test -n "$CHILD_PID" && kill -0 "$CHILD_PID" 2>/dev/null; then
    kill -KILL "$CHILD_PID" 2>/dev/null || true
  fi
  if test -n "$DAEMON_PID" && kill -0 "$DAEMON_PID" 2>/dev/null; then
    kill -KILL "$DAEMON_PID" 2>/dev/null || true
  fi
  for PROC_DIR in /proc/[0-9]*; do
    PROC_CWD=$(readlink "$PROC_DIR/cwd" 2>/dev/null || true)
    test "$PROC_CWD" = "$SBX/world" || continue
    PROC_CMD=$(tr '\0' ' ' <"$PROC_DIR/cmdline" 2>/dev/null || true)
    case "$PROC_CMD" in
      *"$AOS"*|*"$SBX/bin/pi"*|*"sleep 60"*)
        kill -KILL "${PROC_DIR##*/}" 2>/dev/null || true
        ;;
    esac
  done
  rm -rf "$SBX"
}
trap cleanup EXIT

export HOME="$SBX/home"
mkdir -p "$HOME" "$SBX/world" "$SBX/bin"
export AOS_HOME="$HOME/.aos"

printf '%s\n' '#!/usr/bin/env bash' 'trap "" TERM INT HUP' 'exec sleep 60' >"$SBX/bin/pi"
chmod +x "$SBX/bin/pi"
export PATH="$SBX/bin:$PATH"

cd "$SBX/world" || exit 2
timeout 10 "$AOS" agent init --name worker --engine pi >/dev/null
timeout 10 "$AOS" run . --daemon --interval 3000 >/dev/null
DAEMON_PID=$(tr -dc '0-9' <.aos/run.pid)
timeout 10 "$AOS" say "讓 fake pi 卡住" >/dev/null

for _ in $(seq 1 200); do
  CHILD_PID=$(pgrep -P "$DAEMON_PID" | head -n 1 || true)
  if test -n "$CHILD_PID"; then
    STEP_PID=$(pgrep -P "$CHILD_PID" | head -n 1 || true)
  fi
  test -n "$STEP_PID" && break
  sleep 0.02
done
if test -n "$STEP_PID"; then
  PI_PID=$(pgrep -P "$STEP_PID" | head -n 1 || true)
fi

timeout 10 "$AOS" stop >"$SBX/stop.out" 2>"$SBX/stop.err"
STOP_RC=$?
sleep 0.2
if test -n "$STEP_PID" && kill -0 "$STEP_PID" 2>/dev/null; then
  STEP_ALIVE=yes
else
  STEP_ALIVE=no
fi

echo "EXPECT: aos stop 要停止 daemon 的整棵行程樹，忙碌中的 aos agent step 也必須消失"
echo "ACTUAL: stop_exit=$STOP_RC，daemon_pid=$DAEMON_PID，agent_step_pid=${STEP_PID:--}，agent_step_alive_after_200ms=$STEP_ALIVE"

if test "$STEP_ALIVE" = no; then
  echo PASS
  exit 0
fi
echo FAIL
exit 1
