#!/usr/bin/env bash
set -u

AOS="${AOS:-/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a15b3afb7ede212cc/build/bin/aos}"
ROOT="$(mktemp -d /tmp/l3-XXXXXX)"

cleanup() {
  if [ -d "$ROOT/w" ]; then
    (cd "$ROOT/w" && timeout 10 "$AOS" stop >/dev/null 2>&1) || true
  fi
  rm -rf -- "$ROOT"
}
trap cleanup EXIT INT TERM

export HOME="$ROOT/home"
mkdir -p "$HOME" "$ROOT/w"
export AOS_HOME="$HOME/.aos"

(cd "$ROOT/w" && timeout 30 "$AOS" agent init --name w --engine pi >/dev/null)
(cd "$ROOT/w" && timeout 10 "$AOS" say "請只回答收到，不要使用工具。" >/dev/null)
(cd "$ROOT/w" && timeout 10 "$AOS" run --daemon --interval 5000 >/dev/null)

SEEN=0
for _ in $(seq 1 1000); do
  DIRECT="$(jq -r '.status' "$ROOT/w/.aos/agents/w/status.json" 2>/dev/null || echo missing)"
  if [ "$DIRECT" = "thinking" ]; then
    SEEN=1
    break
  fi
  sleep 0.01
done

if [ "$SEEN" -eq 0 ]; then
  echo "EXPECT: daemon 推 LLM 回合時可觀察到 thinking，才能驗證 stop 後狀態"
  echo "ACTUAL: 10 秒內沒有觀察到 thinking"
  echo FAIL
  exit 1
fi

(cd "$ROOT/w" && timeout 30 "$AOS" stop >/dev/null)
STOP_RC=$?
sleep 0.05
DIRECT_AFTER="$(jq -r '.status' "$ROOT/w/.aos/agents/w/status.json")"
CLI_JSON="$(cd "$ROOT/w" && timeout 10 "$AOS" state)"
CLI_STATUS="$(printf '%s' "$CLI_JSON" | jq -r '.status')"
UNREAD="$(printf '%s' "$CLI_JSON" | jq -r '.unread')"
PID_FILE="$ROOT/w/.aos/run.pid"
if [ -f "$PID_FILE" ]; then
  PID_AFTER="$(cat "$PID_FILE")"
else
  PID_AFTER="none"
fi

echo "EXPECT: stop 成功後不再顯示 thinking；未處理訊息應顯示 pending"
echo "ACTUAL: stop_rc=$STOP_RC direct_after=$DIRECT_AFTER aos_state=$CLI_STATUS unread=$UNREAD daemon_pid=$PID_AFTER"
if [ "$STOP_RC" -eq 0 ] && [ "$DIRECT_AFTER" != "thinking" ]; then
  echo PASS
  exit 0
fi
echo FAIL
exit 1
