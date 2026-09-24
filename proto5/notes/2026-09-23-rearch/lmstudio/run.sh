#!/usr/bin/env bash
# T3：本機 LM Studio 真模型跑一條龍 daemon → kernel → 工作 cpu。可重跑（第二次起 boot 接手上一代的家）。
# 用法：run.sh [工作目錄]   （預設 $T3 或 ./t3）
# 前提：LM Studio server 在 localhost:1234、已載入 $MODEL（lms server start; lms load $MODEL）。
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
AOS=$(cd "$HERE/../../.." && pwd)            # proto5/
CLI=$AOS/cli
T3=$(realpath -m "${1:-${T3:-./t3}}")
MODEL=${MODEL:-google/gemma-4-e4b}
D=$T3/D; K=$T3/K; W=$T3/work
mkdir -p "$T3" "$W" "$T3/bin"
now() { date +%s.%N; }
since() { python3 -c "import sys; print('%.2f' % (float(sys.argv[2]) - float(sys.argv[1])))" "$1" "$2"; }
peek() { python3 -c "import json,sys; d=json.load(open(sys.argv[1])); exec('for k in sys.argv[2].split(\".\"):\n d=d.get(k) if isinstance(d,dict) else None'); print(json.dumps(d) if not isinstance(d,str) else d)" "$1" "$2" 2>/dev/null || echo null; }
waitfor() { local what=$1 cmd=$2 lim=${3:-60} i=0; until eval "$cmd"; do i=$((i+1)); [ $i -ge $((lim*10)) ] && { echo "逾時：$what" >&2; exit 1; }; sleep 0.1; done; }
T0=$(now)
echo "== 0. LM Studio =="
curl -sf -m 5 localhost:1234/v1/models >/dev/null || { echo "LM Studio server 沒開（lms server start）" >&2; exit 1; }
cp "$HERE/llm-call" "$T3/bin/llm-call"; chmod +x "$T3/bin/llm-call"

echo "== 1. daemon 起來 =="
mkdir -p "$D"
[ -f "$D/info.json" ] || echo '{"_metainfo":{"_type":"daemon","_version":1},"poll_ms":20,"restart_delay_ms":1000,"stop_wait_ms":5000,"kill_wait_ms":5000}' > "$D/info.json"
setsid "$CLI/aos-daemon" --home "$D" </dev/null >/dev/null 2>>"$T3/daemon.stderr" &
DPID=$!
waitfor "daemon 寫 state" '[ "$(peek "$D/state.json" pid)" = "$DPID" ]' 10
echo "daemon pid=$DPID"

echo "== 2. K 家（第一次 init，之後沿用） =="
if [ ! -f "$K/info.json" ]; then
  "$CLI/aos-kernel" init "$K"
  # init 只給預設 cpus（k＋0、1、2）；沒有 CLI 改 cpus，照範本覆寫
  sed "s#@LMDIR@#$T3/bin#; s#@MODEL@#$MODEL#" "$HERE/kernel-info.template.json" > "$K/info.json"
fi
"$CLI/aos-kernel" boot "$K" --daemon "$D"
waitfor "第 1 格 tick" '[ "$(peek "$K/state.json" last_seq)" -ge 1 ] 2>/dev/null' 10
"$CLI/aos-kernel" ls "$K"

echo "== 3. once：問模型一句話（llm pool） =="
printf '用一句話（不超過三十字）說明作業系統的「行程」是什麼。\n' > "$W/question.txt"
ANS=$W/answer-$(date +%s).json
python3 - "$W/ask.json" "$W/question.txt" "$ANS" <<'PY'
import json, sys
json.dump({"argv": ["llm-call"], "stdin": sys.argv[2], "stdout": sys.argv[3], "stderr": sys.argv[3] + ".err"},
          open(sys.argv[1], "w"), ensure_ascii=False)
PY
TA=$(now)
"$CLI/aos-kernel" add "$K" "$W/ask.json" --once --pool llm --timeout-ms 180000 --wait-ms 200000 | tee "$W/once-reply.txt"
TB=$(now)
echo "放單→回音：$(since "$TA" "$TB") 秒"
echo "--- 模型回答（$ANS）---"; cat "$ANS"; echo

echo "== 4. 反覆行程：每 2 秒一次，第 3 次回 100（done） =="
rm -f "$W/counter.txt"
python3 - "$W/repeat.json" "$W/counter.txt" <<'PY'
import json, sys
c = sys.argv[2]
src = 'n=$(( $(cat %s 2>/dev/null || echo 0) + 1 )); echo $n > %s; echo "repeat run $n at $(date +%%T)"; [ $n -eq 3 ] && exit 100; exit 0' % (c, c)
json.dump({"argv": ["sh", "-c", src], "stdout": c + ".log"}, open(sys.argv[1], "w"))
PY
"$CLI/aos-kernel" rm "$K" repeat 2>/dev/null || true   # 重跑：上一輪的 done 紀錄還在帳本，同名會 AlreadyExists
waitfor "上一輪 repeat 從帳本消失" '[ "$(peek "$K/state.json" procs.repeat)" = null ]' 10
"$CLI/aos-kernel" add "$K" "$W/repeat.json" --name repeat --interval-ms 2000
waitfor "repeat done" '[ "$(peek "$K/state.json" procs.repeat.status)" = done ]' 30
"$CLI/aos-kernel" ls "$K"
echo "--- 帳本 procs.repeat ---"; peek "$K/state.json" procs.repeat

echo "== 5. 停機：先 kernel 後 daemon =="
TS=$(now)
"$CLI/aos-kernel" stop "$K"
waitfor "phase=stopped" '[ "$(peek "$K/state.json" phase)" = stopped ]' 20
waitfor "daemon 孩子表清空" '[ "$(peek "$D/state.json" children)" = "{}" ]' 20
# 沒有 daemon 的停機 CLI：照範式 §3.1 放一則 stop notification
N=stop-$(date +%s%N).json
echo '{"jsonrpc":"2.0","method":"stop"}' > "$D/requests/.$N.tmp"; ln "$D/requests/.$N.tmp" "$D/requests/$N"; rm "$D/requests/.$N.tmp"
DRC=0; wait "$DPID" || DRC=$?; echo "daemon 退出碼 $DRC"
TE=$(now)
echo "停機：$(since "$TS" "$TE") 秒；整條龍：$(since "$T0" "$TE") 秒"
# 只算這次的：別的 session 同時在跑測試時，全域 pgrep 會撈到它們（含 zsh -c 命令列本身）
ALL=$(pgrep -fa 'aos-cpu|aos-daemon|aos-kernel|llm-call' | grep -Ev '(zsh|bash|sh) -c' || true)
MINE=$(echo "$ALL" | grep -F "$T3" || true)
echo "pgrep（全域，去掉 shell）：${ALL:-空}"
[ -z "$MINE" ] && echo "pgrep（本次 $T3）：空" || { echo "本次還有殘留：$MINE"; exit 1; }
