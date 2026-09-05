#!/bin/sh
# agent：一個 agent 就是一塊地上的一支 `aos run`（裁決 M-01）。
#
# 裁決 S-02：agent **自己登記時鐘**，不借父地的鐘。這裡的做法是
#   aos daemon add <agent 地> --every 200   ← 只登記，狀態 pending
#   aos daemon start                        ← daemon 看到 pending，替它起
#                                              `aos run <agent 地> --register`
# 所以 `aos daemon ls` 看得到它、`aos stop <agent 地>` 停得掉它。
#
# 這支範例用假後端 `echo:`，不打任何網路：echo: 會把 prompt 原樣回，回話裡沒有
# 「TOOL:」那種行，所以 agent 第一圈就收工——那正是「agent 停於 LLM 不再呼叫工具」。
# 要跟真模型玩看 proto/play-agent.sh。
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
AOS_PY="$HERE/../../aos.py"
BIN="$HERE/../../bin"
LAND="$HERE"

echo "== 清乾淨（含 AOS_HOME 用的暫存家） =="
rm -rf "$LAND/.aos" "$LAND/.home" "$LAND/state"
mkdir -p "$LAND/.home"
export AOS_HOME="$LAND/.home"
echo "AOS_HOME=$AOS_HOME（範例自己的暫存目錄，不碰使用者的 ~）"

SERVE_PID=""
cleanup() {
  [ -n "$SERVE_PID" ] && kill "$SERVE_PID" 2>/dev/null || true
  python3 "$AOS_PY" daemon stop >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

echo "== init 這塊地 + LLM 世界（假後端 echo:） =="
python3 "$AOS_PY" init "$LAND"
python3 "$AOS_PY" llm init >/dev/null
LLMWORLD="$AOS_HOME/.aos/llm"

echo "== 工具白名單：只給 $BIN（aos）跟 /usr/bin /bin =="
cat > "$LAND/.aos/config.json" <<JSON
{
  "format_version": 1,
  "path": ["$BIN", "/usr/bin", "/bin"],
  "max_parallel": 4,
  "inst_timeout_ms": 60000,
  "inbox_max": 1000
}
JSON

echo "== LLM 世界開著（S-05：LLM 世界是一支 aos llm serve） =="
python3 "$AOS_PY" llm serve --land "$LLMWORLD" --steps 200 --every 200 \
  > "$LAND/.home/llm-serve.log" 2>&1 &
SERVE_PID=$!

echo "== S-02：agent 自己登記時鐘（只登記，還沒跑） =="
python3 "$AOS_PY" daemon add "$LAND" --every 200

echo "== 登記表：應該看到一筆 pending =="
python3 "$AOS_PY" daemon ls

echo "== 起 daemon，讓它去起 agent 的 aos run =="
python3 "$AOS_PY" daemon start --every 200

echo "== 等 agent 收工（最多 30 秒） =="
i=0
while [ "$i" -lt 60 ]; do
  if [ -f "$LAND/state/done.json" ]; then
    break
  fi
  sleep 0.5
  i=$((i + 1))
done

echo "== aos daemon ls（S-02：登記表看得到這個 agent） =="
python3 "$AOS_PY" daemon ls

echo "== agent 停在哪 =="
python3 "$AOS_PY" status "$LAND"

echo "== 為什麼收工（state/done.json） =="
if [ -f "$LAND/state/done.json" ]; then
  cat "$LAND/state/done.json"
else
  echo "(沒有 done.json——agent 沒跑完，看 $LAND/.aos/daemon-run.log)"
  cat "$LAND/.aos/daemon-run.log" 2>/dev/null || true
  exit 1
fi

echo "== 第 1 圈的 prompt 與回話（state/rounds/001/） =="
head -5 "$LAND/state/rounds/001/prompt.txt"
echo "…"
head -3 "$LAND/state/rounds/001/answer.txt"

echo "== 帳簿（一圈一筆 LLM 請求） =="
cat "$AOS_HOME/.aos/ledger.jsonl" 2>/dev/null || echo "(沒有)"

echo "== S-02 第二段：agent 在跑的時候，aos stop 停得掉它 =="
echo "（清掉上一輪的串與 state，改一個慢一點的鐘 3 秒一格，好讓我們來得及叫停）"
rm -rf "$LAND/state" "$LAND/.aos/series.json" "$LAND/.aos/stopped.json"
python3 "$AOS_PY" daemon add "$LAND" --every 3000

echo "-- 等 daemon 把它起起來（登記表變 running） --"
i=0
while [ "$i" -lt 40 ]; do
  if python3 -c "
import json, sys
reg = json.load(open('$AOS_HOME/.aos/registry.json'))
e = [x for x in reg['entries'] if x['path'] == '$LAND']
sys.exit(0 if e and e[0]['state'] == 'running' and e[0]['pid'] else 1)
"; then
    break
  fi
  sleep 0.25
  i=$((i + 1))
done
python3 "$AOS_PY" daemon ls

echo "-- aos stop（投一封控制信，它會在這一格跑完後停） --"
python3 "$AOS_PY" stop "$LAND"

echo "-- 等它停 --"
i=0
while [ "$i" -lt 40 ]; do
  if python3 -c "
import json, sys
reg = json.load(open('$AOS_HOME/.aos/registry.json'))
e = [x for x in reg['entries'] if x['path'] == '$LAND']
sys.exit(0 if e and e[0]['state'] == 'stopped' else 1)
"; then
    break
  fi
  sleep 0.25
  i=$((i + 1))
done
python3 "$AOS_PY" daemon ls
echo "-- 停止原因檔 --"
cat "$LAND/.aos/stopped.json" 2>/dev/null || echo "(沒有)"
python3 -c "
import json, sys
st = json.load(open('$LAND/.aos/stopped.json'))
if st.get('reason') != 'control_stop':
    sys.stderr.write('沒看到 control_stop：%r\n' % st)
    sys.exit(1)
print('OK：aos stop 停得掉這個 agent')
"

echo "== 停 daemon =="
python3 "$AOS_PY" daemon stop
