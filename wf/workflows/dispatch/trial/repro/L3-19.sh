#!/usr/bin/env bash
set -u

AOS="${AOS:-/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a15b3afb7ede212cc/build/bin/aos}"
ROOT="$(mktemp -d /tmp/l3-XXXXXX)"
RUN_PID=""

cleanup() {
  if [ -n "$RUN_PID" ] && kill -0 "$RUN_PID" 2>/dev/null; then
    kill -TERM -- "-$RUN_PID" 2>/dev/null || true
    wait "$RUN_PID" 2>/dev/null || true
  fi
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

setsid bash -c 'cd "$1" && exec timeout 120 "$2" run --step 1' _ "$ROOT/w" "$AOS" \
  >"$ROOT/run.out" 2>&1 &
RUN_PID=$!

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
  echo "EXPECT: agent 進入 thinking 時，各狀態入口顯示同一個忙碌狀態"
  echo "ACTUAL: 10 秒內沒有觀察到 thinking，無法完成比對"
  echo FAIL
  exit 1
fi

CLI_JSON="$(cd "$ROOT/w" && timeout 10 "$AOS" state)"
CLI_STATUS="$(printf '%s' "$CLI_JSON" | jq -r '.status')"
WORLD_PHASE="$(jq -r '.phase' "$ROOT/w/.aos/state.json")"
WORLD_AGENT="$(jq -r '.agents.w.status' "$ROOT/w/.aos/state.json")"
WORLD_TURN="$(jq -r '.agents.w.turn' "$ROOT/w/.aos/state.json")"

kill -INT -- "-$RUN_PID" 2>/dev/null || true
wait "$RUN_PID" 2>/dev/null || true
RUN_PID=""

echo "EXPECT: direct agent status、aos state、state.json.agents.w 都顯示 thinking，世界 phase=running"
echo "ACTUAL: direct=$DIRECT aos_state=$CLI_STATUS world_phase=$WORLD_PHASE world_agent=$WORLD_AGENT world_agent_turn=$WORLD_TURN"
if [ "$DIRECT" = "thinking" ] && [ "$CLI_STATUS" = "thinking" ] && [ "$WORLD_PHASE" = "running" ] && [ "$WORLD_AGENT" = "thinking" ]; then
  echo PASS
  exit 0
fi
echo FAIL
exit 1
