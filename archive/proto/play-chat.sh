#!/usr/bin/env bash
# 給人玩的互動台。真後端固定是 DeepSeek；AOS_PLAY_BACKEND=echo: 只供離線自測。
set -u
set -o pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
AOS_PY="$HERE/aos.py"
BIN="$HERE/bin"
SOURCE="$HERE/examples/agent-real"
PLAY="$HERE/play"
HELPER="$PLAY/chat_helper.py"
PLAY_BRAIN="$PLAY/brain.py"

DEEPSEEK_ENDPOINT="https://api.deepseek.com/v1"
DEEPSEEK_MODEL="deepseek-v4-flash"
BACKEND="${AOS_PLAY_BACKEND:-$DEEPSEEK_ENDPOINT}"
MAX_ROUNDS="${AOS_PLAY_MAX_ROUNDS:-10}"
ECHO_ROUNDS=0
[[ "$BACKEND" == "echo:" ]] && ECHO_ROUNDS=2

# 估價常數（2026-09-05 查 DeepSeek 官方價目）：高峰、快取未命中的保守算法。
# 輸出價也套在另報的思考 token；實際帳單可能因時段與快取命中更低。
AOS_PLAY_INPUT_USD_PER_MILLION="0.44"
AOS_PLAY_OUTPUT_USD_PER_MILLION="1.32"
export AOS_PLAY_INPUT_USD_PER_MILLION AOS_PLAY_OUTPUT_USD_PER_MILLION

case "$BACKEND" in
  "$DEEPSEEK_ENDPOINT"|echo:) ;;
  *)
    echo "AOS_PLAY_BACKEND 只准留空（用 DeepSeek）或填 echo:（離線自測）。" >&2
    exit 2
    ;;
esac
case "$MAX_ROUNDS" in
  ''|*[!0-9]*|0)
    echo "AOS_PLAY_MAX_ROUNDS 要填大於 0 的整數。" >&2
    exit 2
    ;;
esac
if [[ "$BACKEND" != "echo:" && -z "${DEEPSEEK_API_KEY:-}" ]]; then
  echo "還沒設定 DEEPSEEK_API_KEY；設定好再起互動台。" >&2
  exit 2
fi

STAMP="$(date +%Y%m%d-%H%M%S)"
export AOS_HOME="$PLAY/home-$STAMP"
if [[ -e "$AOS_HOME" ]]; then
  AOS_HOME="$PLAY/home-$STAMP-$$"
  export AOS_HOME
fi
LLM_WORLD="$AOS_HOME/.aos/llm"
LANDS="$AOS_HOME/lands"
SERVE_PID=""
AGENT=""
AGENT_ACTIVE=0
LAST_ROUND=0
TASK_NO=0
QUIT=0
CLEANED=0

cleanup() {
  if (( CLEANED )); then
    return
  fi
  CLEANED=1
  python3 "$AOS_PY" daemon stop >/dev/null 2>&1 || true
  if [[ -n "$SERVE_PID" ]]; then
    kill "$SERVE_PID" >/dev/null 2>&1 || true
    wait "$SERVE_PID" >/dev/null 2>&1 || true
    SERVE_PID=""
  fi
}

on_signal() {
  echo
  echo "收到中斷，正在收尾。"
  QUIT=1
  cleanup
  if [[ -d "$AOS_HOME" ]]; then
    python3 "$HELPER" final "$AOS_HOME" 2>/dev/null || true
    echo "家留在：$AOS_HOME"
  fi
  exit 130
}

trap cleanup EXIT
trap on_signal INT TERM

report_new_rounds() {
  local line
  [[ -n "$AGENT" ]] || return
  while IFS= read -r line; do
    case "$line" in
      __AOS_LAST_ROUND__=*) LAST_ROUND="${line#*=}" ;;
      *) printf '%s\n' "$line" ;;
    esac
  done < <(python3 "$HELPER" report "$AGENT" "$AOS_HOME" "$LAST_ROUND")
}

show_status() {
  if [[ -z "$AGENT" ]]; then
    echo "還沒有 agent 地。"
    return
  fi
  echo "===== 這塊地現在的狀態 ====="
  python3 "$AOS_PY" status "$AGENT" 2>&1 | sed 's/^/  /'
  python3 "$HELPER" registry "$AOS_HOME" "$AGENT"
}

show_log() {
  if [[ -z "$AGENT" ]]; then
    echo "還沒有 agent 地。"
    return
  fi
  python3 "$HELPER" log "$AGENT"
}

start_task() {
  local task="$1"
  if [[ -z "${task//[[:space:]]/}" ]]; then
    echo "任務不能是空的。"
    return 1
  fi
  TASK_NO=$((TASK_NO + 1))
  AGENT="$LANDS/agent-$(printf '%03d' "$TASK_NO")"
  LAST_ROUND=0
  python3 "$HELPER" setup "$SOURCE" "$PLAY_BRAIN" "$AGENT" "$task" "$MAX_ROUNDS" "$ECHO_ROUNDS"
  python3 "$AOS_PY" init "$AGENT" >/dev/null
  python3 "$HELPER" land-config "$AGENT" "$BIN"
  python3 "$AOS_PY" daemon add "$AGENT" --every 300 --budget 2000 >/dev/null
  AGENT_ACTIVE=1
  echo
  echo "任務交給它了：$task"
  echo "agent 地：$AGENT"
  echo "產出在：$AGENT/work"
  echo "跑動時可直接打字插話；也可用 /status、/log、/stop、/new 任務、/quit。"
}

stop_current() {
  local state tries text
  (( AGENT_ACTIVE )) || return 0
  state="$(python3 "$HELPER" state "$AOS_HOME" "$AGENT")"
  tries=0
  while [[ "$state" == "pending" && $tries -lt 30 ]]; do
    sleep 0.1
    tries=$((tries + 1))
    state="$(python3 "$HELPER" state "$AOS_HOME" "$AGENT")"
  done
  if [[ "$state" == "running" ]]; then
    python3 "$AOS_PY" stop "$AGENT" 2>&1 | sed 's/^/  /'
  fi
  tries=0
  while [[ "$(python3 "$HELPER" state "$AOS_HOME" "$AGENT")" != "stopped" && $tries -lt 350 ]]; do
    sleep 0.1
    tries=$((tries + 1))
  done
  if [[ "$(python3 "$HELPER" state "$AOS_HOME" "$AGENT")" != "stopped" ]]; then
    echo "它還在這一格裡，先不開新任務；等一下再打 /new。"
    return 1
  fi
  report_new_rounds
  text="$(python3 "$HELPER" finished "$AGENT" "$AOS_HOME" 2>/dev/null || true)"
  [[ -n "$text" ]] && echo "$text"
  AGENT_ACTIVE=0
  return 0
}

send_mail() {
  local message="$1"
  if python3 "$HELPER" mail-json "$message" \
      | python3 "$AOS_PY" deliver "$AGENT" - --sender "$AOS_HOME" >/dev/null; then
    echo "信送進去了；它下一圈組 prompt 時會看到：$message"
  else
    echo "這封信沒投進去，請用 /status 看 agent 是否已停。" >&2
  fi
}

handle_active_input() {
  local line="$1" task
  case "$line" in
    /quit)
      QUIT=1
      ;;
    /status)
      show_status
      ;;
    /log)
      show_log
      ;;
    /stop)
      stop_current || true
      ;;
    /new)
      echo "用法：/new 接著寫新任務。"
      ;;
    /new\ *)
      task="${line#/new }"
      if stop_current; then
        start_task "$task"
      fi
      ;;
    /*)
      echo "不認得這個指令。可用：/status、/log、/stop、/new 任務、/quit。"
      ;;
    '')
      ;;
    *)
      send_mail "$line"
      ;;
  esac
}

handle_idle_input() {
  local line="$1" task
  case "$line" in
    /quit) QUIT=1 ;;
    /status) show_status ;;
    /log) show_log ;;
    /new) echo "用法：/new 接著寫新任務。" ;;
    /new\ *)
      task="${line#/new }"
      start_task "$task"
      ;;
    /*) echo "現在沒有 agent 在跑。打一行新任務，或用 /quit。" ;;
    '') echo "任務不能是空的。" ;;
    *) start_task "$line" ;;
  esac
}

mkdir -p "$AOS_HOME" "$LANDS"
echo "正在起 daemon……"
python3 "$AOS_PY" daemon start --every 200 >/dev/null
echo "正在起 LLM 世界……"
python3 "$AOS_PY" llm init >/dev/null
python3 "$HELPER" home-config "$AOS_HOME" "$LLM_WORLD" "$BACKEND" "$DEEPSEEK_MODEL"
python3 "$AOS_PY" llm serve --land "$LLM_WORLD" --steps 200000 --every 200 \
  >"$AOS_HOME/llm-serve.log" 2>&1 &
SERVE_PID=$!
sleep 0.3
if ! kill -0 "$SERVE_PID" 2>/dev/null; then
  echo "LLM 世界沒起來；請看 $AOS_HOME/llm-serve.log" >&2
  exit 1
fi

echo
echo "aos 互動台好了。模型：$DEEPSEEK_MODEL"
if [[ "$BACKEND" == "echo:" ]]; then
  echo "目前是離線假後端，不會打網路。"
else
  echo "目前會連 DeepSeek；金鑰只會從 DEEPSEEK_API_KEY 讀取。"
fi
echo "花費用高峰、快取未命中價估，僅供參考。"
echo "這一輪的家：$AOS_HOME"

NEXT_CHECK=0
while (( ! QUIT )); do
  if (( ! AGENT_ACTIVE )); then
    echo
    echo "你要它做什麼？"
    if ! IFS= read -r line; then
      QUIT=1
      break
    fi
    handle_idle_input "$line"
    NEXT_CHECK=0
    continue
  fi

  NOW="$(date +%s)"
  if (( NOW >= NEXT_CHECK )); then
    report_new_rounds
    if FINISHED_TEXT="$(python3 "$HELPER" finished "$AGENT" "$AOS_HOME" 2>/dev/null)"; then
      echo
      echo "$FINISHED_TEXT"
      echo "東西留在：$AGENT/work"
      AGENT_ACTIVE=0
      continue
    fi
    NEXT_CHECK=$((NOW + 2))
  fi

  if IFS= read -r -t 0.2 line; then
    handle_active_input "$line"
  else
    READ_STATUS=$?
    if (( READ_STATUS == 1 )); then
      QUIT=1
    fi
  fi
done

report_new_rounds
cleanup
echo
echo "===== 這一輪結算 ====="
python3 "$HELPER" final "$AOS_HOME"
echo "估價只是估的；實際帳單會受時段、快取與後端計量影響。"
echo "家留在：$AOS_HOME"
