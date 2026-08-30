#!/usr/bin/env bash
set -u

AOS=${AOS:-/home/lorkhan/repo/simple_tools/aos/build/bin/aos}
ROOT=${ROOT:-/home/lorkhan/repo/simple_tools/aos}
SOLO=$ROOT/wf/workflows/dispatch/trial/sandbox/solo
TEMPLATE=$SOLO/_template
CASE_DIR=$(mktemp -d "$SOLO/C/repro-tmp.C-03.XXXXXX")
WORLD=$CASE_DIR/world
RUN_PID=
RUN_CHILD=
STEP_PID=

cleanup() {
  set +e
  test -n "$STEP_PID" && kill -TERM "$STEP_PID" 2>/dev/null
  test -n "$RUN_CHILD" && kill -TERM "$RUN_CHILD" 2>/dev/null
  test -n "$RUN_PID" && kill -TERM "$RUN_PID" 2>/dev/null
}
trap cleanup EXIT

mkdir -p "$WORLD/.aos"
cp -r "$TEMPLATE/." "$WORLD/"
cd "$WORLD"
export PATH="$ROOT/build/bin:$PATH"
"$AOS" agent init
"$AOS" say "讀 src/main.cpp、src/parse.cpp、src/parse.hpp 和測試，寫一份非常詳細的逐行分析與完整風險清單；只分析不要修改"

( timeout 900 "$AOS" run . --step 9 > run.log 2>&1 ) &
RUN_PID=$!

# Turn 1 通常只提出讀檔；等到 turn 3 的模型長回合再中斷，避免工作自然先結束。
for _ in $(seq 1 300); do
  STATUS=$(jq -r '.status' .aos/agents/*/status.json)
  STATUS_TURN=$(jq -r '.turn' .aos/agents/*/status.json)
  if test "$STATUS" = thinking && test "$STATUS_TURN" -ge 3; then
    break
  fi
  sleep 0.1
done

RUN_CHILD=$(pgrep -P "$RUN_PID" | head -1 || true)
test -n "$RUN_CHILD" && STEP_PID=$(pgrep -P "$RUN_CHILD" | head -1 || true)
TURN_AT_SIGNAL=$(cat .aos/turn)
kill -INT "$RUN_PID"
sleep 1

STEP_ALIVE=no
test -n "$STEP_PID" && kill -0 "$STEP_PID" 2>/dev/null && STEP_ALIVE=yes
OUT_EXISTS=no
test -e ".aos/batch/$TURN_AT_SIGNAL/out/agent-$(basename "$WORLD")-$TURN_AT_SIGNAL.json" && OUT_EXISTS=yes

printf 'EXPECT: Ctrl-C 後 timeout、aos run、aos agent step 都停止，未完成回合被標記為中斷。\n'
printf 'ACTUAL: signal_turn=%s，agent_step_pid=%s，alive_after_1s=%s，該回合 out_exists=%s，status 如下：\n' "$TURN_AT_SIGNAL" "${STEP_PID:--}" "$STEP_ALIVE" "$OUT_EXISTS"
cat .aos/agents/*/status.json
printf 'EVIDENCE_DIR: %s\n' "$CASE_DIR"
