#!/bin/sh
# play-agent.sh —— 一個指令，把單人 agent 劇本跟真的 LM Studio 玩一輪。
#
# 做的事：起暫存家 → 起 daemon → 起 LLM 世界（真後端）→ 起 agent →
# 每 5 秒印一次 agent 的 status 跟帳簿最後一行 → agent 收工（或到上限）就停 →
# 把每圈的 prompt／回話、帳簿、usage 收進 proto/play-logs/<時間>/ → 印一段結算。
#
# 開關（環境變數）：
#   AOS_PLAY_BACKEND  本機端點，預設 http://localhost:1234/v1；填 `echo:` 就整組走假
#                     後端（連雲端那筆一起，不打任何網路），用來驗腳本自己有沒有壞
#   AOS_PLAY_MODEL    本機模型 id，預設 qwen/qwen3.5-9b（LM Studio 那邊要先載好）
#   AOS_PLAY_TIER     這一輪叫哪一顆：fast＝本機 LM Studio、smart＝雲端 deepseek。預設 fast
#   AOS_PLAY_CLOUD        雲端端點，預設 https://api.deepseek.com/v1
#   AOS_PLAY_CLOUD_MODEL  雲端模型，預設 deepseek-v4-flash
#   AOS_PLAY_MINUTES  上限幾分鐘，預設 10
#
# 金鑰：雲端那筆單元只在 config 裡寫**環境變數的名字**（`api_key_env`），
# LLM 世界打端點時才去讀那個環境變數。金鑰本身不會進 config、不會進 play-logs。
#
# 怎麼跟 LM Studio 一起玩：看 proto/README.md 最後一節。
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
AOS_PY="$HERE/aos.py"
BIN="$HERE/bin"
SRC="$HERE/examples/agent-real"

BACKEND="${AOS_PLAY_BACKEND:-http://localhost:1234/v1}"
MODEL="${AOS_PLAY_MODEL:-qwen/qwen3.5-9b}"
TIER="${AOS_PLAY_TIER:-fast}"
CLOUD="${AOS_PLAY_CLOUD:-https://api.deepseek.com/v1}"
CLOUD_MODEL="${AOS_PLAY_CLOUD_MODEL:-deepseek-v4-flash}"
CLOUD_KEY_ENV="${AOS_PLAY_CLOUD_KEY_ENV:-DEEPSEEK_API_KEY}"
MINUTES="${AOS_PLAY_MINUTES:-10}"
# 假後端要假到底：連雲端那筆也換成 echo:，保證這支腳本空跑時不打任何網路
if [ "$BACKEND" = "echo:" ]; then
  CLOUD="echo:"
fi
case "$TIER" in
  fast) THIS_UNIT="lmstudio（本機 $MODEL）" ;;
  smart) THIS_UNIT="deepseek（雲端 $CLOUD_MODEL）" ;;
  *) echo "AOS_PLAY_TIER 只認得 fast／smart，收到 $TIER" >&2; exit 2 ;;
esac
STAMP="$(date +%Y%m%d-%H%M%S)-$TIER"
LOGDIR="$HERE/play-logs/$STAMP"

PLAY="$(mktemp -d -t aos-play-XXXXXX)"
export AOS_HOME="$PLAY/home"
AGENT="$PLAY/agent"
LLMWORLD="$AOS_HOME/.aos/llm"
SERVE_PID=""

cleanup() {
  [ -n "$SERVE_PID" ] && kill "$SERVE_PID" 2>/dev/null
  python3 "$AOS_PY" daemon stop >/dev/null 2>&1
}
trap cleanup EXIT INT TERM

echo "############################################################"
echo "# aos 單人 agent 劇本"
echo "#   這一輪：tier=$TIER → $THIS_UNIT"
echo "#   本機 ：$BACKEND（$MODEL，tier=fast）"
echo "#   雲端 ：$CLOUD（$CLOUD_MODEL，tier=smart，金鑰讀環境變數 $CLOUD_KEY_ENV）"
echo "#   上限 ：$MINUTES 分鐘"
echo "#   暫存家：$AOS_HOME"
echo "#   紀錄 ：$LOGDIR"
echo "############################################################"

mkdir -p "$AOS_HOME"

echo
echo "== 1／5 把 agent 那塊地複製到暫存目錄（repo 裡那份保持乾淨） =="
mkdir -p "$AGENT"
cp "$SRC/brain.py" "$SRC/main.aos.json" "$SRC/task.md" "$AGENT/"
python3 -c "
import json, sys
c = json.load(open('$SRC/agent.json'))
c['tier'] = '$TIER'
c['max_llm_calls'] = 30
json.dump(c, open('$AGENT/agent.json', 'w'), ensure_ascii=False, indent=2)
"
cp -r "$SRC/work" "$AGENT/work"
rm -rf "$AGENT/work/__pycache__"
python3 "$AOS_PY" init "$AGENT"
cat > "$AGENT/.aos/config.json" <<JSON
{
  "format_version": 1,
  "path": ["$BIN", "/usr/bin", "/bin"],
  "max_parallel": 4,
  "inst_timeout_ms": 120000,
  "inbox_max": 1000
}
JSON
echo "agent 地：$AGENT（工具白名單只給 $BIN、/usr/bin、/bin）"
echo "任務："
sed 's/^/    /' "$AGENT/task.md"

echo
echo "== 2／5 LLM 世界（裁決 F-02：LLM 是單獨一塊地） =="
python3 "$AOS_PY" llm init >/dev/null
cat > "$AOS_HOME/.aos/config.json" <<JSON
{
  "format_version": 1,
  "llm_world": "$LLMWORLD",
  "max_parallel": 2,
  "max_wait_ms": 600000,
  "units": [
    {"name": "lmstudio", "endpoint": "$BACKEND", "model": "$MODEL",
     "tier": "fast", "max_parallel": 1, "api_key_env": null, "timeout_ms": 600000},
    {"name": "deepseek", "endpoint": "$CLOUD", "model": "$CLOUD_MODEL",
     "tier": "smart", "max_parallel": 2, "api_key_env": "$CLOUD_KEY_ENV",
     "timeout_ms": 600000}
  ]
}
JSON
python3 "$AOS_PY" llm ls --land "$LLMWORLD" | tail -4
python3 "$AOS_PY" llm serve --land "$LLMWORLD" --steps 20000 --every 300 \
  > "$AOS_HOME/llm-serve.log" 2>&1 &
SERVE_PID=$!
echo "aos llm serve 起來了（pid $SERVE_PID，紀錄 $AOS_HOME/llm-serve.log）"

echo
echo "== 3／5 daemon 與 agent 的鐘（裁決 S-02：agent 自己登記時鐘） =="
python3 "$AOS_PY" daemon add "$AGENT" --every 500
python3 "$AOS_PY" daemon start --every 300
sleep 1
python3 "$AOS_PY" daemon ls

echo
echo "== 4／5 盯著它跑（每 5 秒一次，最多 $MINUTES 分鐘） =="
START=$(date +%s)
LIMIT=$((MINUTES * 60))
WHY="still_running"
while :; do
  NOW=$(date +%s)
  ELAPSED=$((NOW - START))
  echo "---- 第 $ELAPSED 秒 ----"
  python3 "$AOS_PY" status "$AGENT" 2>&1 | sed 's/^/  /'
  if [ -s "$AOS_HOME/.aos/ledger.jsonl" ]; then
    echo "  帳簿最後一行：$(tail -1 "$AOS_HOME/.aos/ledger.jsonl")"
  else
    echo "  帳簿：還沒有任何一筆 LLM 請求"
  fi
  if [ -f "$AGENT/state/round.txt" ]; then
    echo "  現在第 $(cat "$AGENT/state/round.txt" | tr -d '\n') 圈"
  fi

  if [ -f "$AGENT/state/done.json" ]; then
    WHY="agent_done"
    echo "  >> agent 說它收工了"
    break
  fi
  if python3 -c "
import json, sys
try:
    reg = json.load(open('$AOS_HOME/.aos/registry.json'))
except Exception:
    sys.exit(1)
e = [x for x in reg['entries'] if x['path'] == '$AGENT']
sys.exit(0 if e and e[0]['state'] == 'stopped' else 1)
" 2>/dev/null; then
    WHY="run_stopped"
    echo "  >> 登記表說那支 run 停了"
    break
  fi
  if [ "$ELAPSED" -ge "$LIMIT" ]; then
    WHY="time_limit"
    echo "  >> 到 $MINUTES 分鐘上限了，叫停"
    python3 "$AOS_PY" stop "$AGENT" 2>&1 | sed 's/^/  /'
    sleep 3
    python3 "$AOS_PY" stop "$AGENT" --kill >/dev/null 2>&1
    break
  fi
  sleep 5
done
ENDED=$(date +%s)

echo
echo "== 5／5 收工、收紀錄 =="
python3 "$AOS_PY" daemon stop 2>&1 | sed 's/^/  /'
[ -n "$SERVE_PID" ] && kill "$SERVE_PID" 2>/dev/null
SERVE_PID=""
sleep 1

mkdir -p "$LOGDIR"
[ -d "$AGENT/state" ] && cp -r "$AGENT/state" "$LOGDIR/agent-state"
[ -d "$AGENT/work" ] && cp -r "$AGENT/work" "$LOGDIR/agent-work"
for f in ledger.jsonl usage.json registry.json config.json daemon.log; do
  [ -f "$AOS_HOME/.aos/$f" ] && cp "$AOS_HOME/.aos/$f" "$LOGDIR/$f"
done
[ -f "$AOS_HOME/llm-serve.log" ] && cp "$AOS_HOME/llm-serve.log" "$LOGDIR/llm-serve.log"
[ -f "$AGENT/.aos/stopped.json" ] && cp "$AGENT/.aos/stopped.json" "$LOGDIR/agent-stopped.json"
[ -f "$AGENT/.aos/daemon-run.log" ] && cp "$AGENT/.aos/daemon-run.log" "$LOGDIR/agent-run.log"
[ -d "$LLMWORLD/.aos/llm-done" ] && cp -r "$LLMWORLD/.aos/llm-done" "$LOGDIR/llm-done"
cp "$AGENT/task.md" "$LOGDIR/task.md" 2>/dev/null
printf '%s\n' "tier=$TIER" "unit=$THIS_UNIT" "backend=$BACKEND" "model=$MODEL" \
  "cloud=$CLOUD" "cloud_model=$CLOUD_MODEL" "minutes=$MINUTES" \
  "agent_land=$AGENT" "home=$AOS_HOME" "why=$WHY" \
  "elapsed_s=$((ENDED - START))" > "$LOGDIR/play.txt"
echo "  紀錄收進：$LOGDIR"

echo
python3 - "$LOGDIR" "$AGENT" "$WHY" "$((ENDED - START))" "$THIS_UNIT" "tier=$TIER" <<'PY'
import json, os, sys

logdir, agent, why, elapsed, model, backend = sys.argv[1:7]

def jread(p, d=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d

ledger = []
try:
    with open(os.path.join(logdir, "ledger.jsonl"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    ledger.append(json.loads(line))
                except ValueError:
                    pass
except OSError:
    pass

done = jread(os.path.join(logdir, "agent-state", "done.json"))
stopped = jread(os.path.join(logdir, "agent-stopped.json"))
rounds_dir = os.path.join(logdir, "agent-state", "rounds")
rounds = sorted(os.listdir(rounds_dir)) if os.path.isdir(rounds_dir) else []

tin = sum(x.get("tokens_in") or 0 for x in ledger)
tout = sum(x.get("tokens_out") or 0 for x in ledger)
ms = sum(x.get("ms") or 0 for x in ledger)
bad = [x for x in ledger if x.get("outcome") != "ok"]

print("############################################################")
print("# 這一輪")
print("############################################################")
print("這一輪叫的是：%s（%s）" % (model, backend))
print("跑了 %s 秒。" % elapsed)
print("圈數：%d 圈（每圈的 prompt／回話在 %s/agent-state/rounds/）" % (len(rounds), logdir))
print("LLM 請求：%d 次，其中壞掉 %d 次。" % (len(ledger), len(bad)))
units = {}
for x in ledger:
    units[x.get("unit")] = units.get(x.get("unit"), 0) + 1
print("處理單元：%s" % ("、".join("%s %d 次" % kv for kv in units.items()) or "（沒有）"))
print("token：進 %d、出 %d，合計 %d。後端花了 %d 毫秒（平均一次 %d 毫秒）。"
      % (tin, tout, tin + tout, ms, (ms // len(ledger)) if ledger else 0))
for x in bad:
    print("  壞的那次：%s — %s" % (x.get("outcome"), x.get("request_id")))

print("")
print("最後停在哪：")
if done:
    print("  agent 自己收工了：why=%s" % done.get("why"))
    print("  它最後說：%s" % (done.get("message") or "")[:300])
    print("  跑到第 %s 圈" % done.get("rounds"))
else:
    print("  agent 沒寫 done.json——不是自己收工的（why=%s）" % why)
if stopped:
    print("  那支 run 的停止原因檔：%s — %s" % (stopped.get("reason"), stopped.get("message")))

print("")
print("為什麼：")
reasons = {
    "no_tool_call": "LLM 這一圈沒有再叫工具（裁決 M-01 的停法：agent 停於 LLM 不再呼叫工具）。",
    "said_done": "LLM 自己說 DONE:，收工。",
    "round_cap": "跑滿 agent.json 的圈數上限（max_rounds）還沒收工。",
    "call_cap": "打滿 agent.json 的 LLM 次數上限（max_llm_calls）還沒收工。",
    "empty_answer": "LLM 回了空的。",
}
if done:
    print("  " + reasons.get(done.get("why"), "done.json 寫 why=%s" % done.get("why")))
elif why == "time_limit":
    print("  到時間上限，是我把它叫停的，不是它自己停的。")
elif why == "run_stopped":
    print("  登記表說那支 run 停了，但 agent 沒寫 done.json——去看 %s/agent-run.log。" % logdir)
else:
    print("  %s" % why)

# 任務到底有沒有做成：跑一次它改完的測試
work = os.path.join(logdir, "agent-work")
if os.path.isdir(work):
    import subprocess
    p = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", work, "-t", work],
                       capture_output=True, text=True)
    tail = (p.stderr or p.stdout).strip().splitlines()[-1:] or [""]
    print("")
    print("任務做成了嗎：跑 agent 改完的 work/ 測試 → %s（%s）"
          % ("全綠" if p.returncode == 0 else "還是紅的", tail[0]))
PY

echo
echo "紀錄都在：$LOGDIR"
