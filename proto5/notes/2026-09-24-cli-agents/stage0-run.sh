#!/usr/bin/env bash
# 階 0 一條龍：daemon → 一般 kernel 家 K（只有 1 顆 cpu）＋花錢的 kernel 家 K2（claude 1、codex 2）
# → 丟一張 codex 唯讀審查單 → 收回音 → 停機。加 --with-claude 再丟兩張最小的 claude 單（第二張從第一張分岔）。
# 用法：bash stage0-run.sh [W] [--with-claude]      W 預設 $HOME/aos-cli-try，必須還不存在。
# 花費：codex 1 次（審一支 34 行的工具）；--with-claude 多 claude 2 次（都只回 ok）。
# 不碰 LM Studio／ollama；不用任何「跳過權限」旗標。
set -u
W=$HOME/aos-cli-try; WITH_CLAUDE=0
for a in "$@"; do case $a in --with-claude) WITH_CLAUDE=1 ;; *) W=$a ;; esac; done
R=$(cd "$(dirname "$0")/../../.." && pwd)            # repo 根目錄
T=$R/proto5/templates/cli-agents
[ -e "$W" ] && { echo "$W 已經在；換一個 W，或先 rm -rf $W"; exit 2; }
case $W in /*) ;; *) echo "W 要寫絕對路徑"; exit 2 ;; esac
mkdir -p "$W/jobs" "$W/ws" "$W/codex-home"
export PATH=$R/proto5/cli:$PATH
D=$W/D K=$W/K K2=$W/K2

stop_all() {
  echo "== 停機"
  aos-kernel halt --target "$K2" --wait-ms 60000
  aos-kernel halt --target "$K" --wait-ms 60000
  aos-daemon halt --target "$D"
}
trap stop_all EXIT

wait_echo() {   # $1＝回音檔路徑，$2＝最多等幾秒
  local i=0
  while [ ! -e "$1" ] && [ $i -lt "$2" ]; do sleep 1; i=$((i + 1)); done
  [ -e "$1" ] || { echo "等了 $2 秒沒有回音：$1"; return 1; }
  echo "回音（等了約 $i 秒）："; cat "$1"; echo
}

echo "== 開 daemon"
setsid aos-daemon boot --target "$D" >>"$W/daemon.log" 2>&1 </dev/null &
for i in 1 2 3 4 5 6 7 8 9 10; do [ -e "$D/state.json" ] && break; sleep 0.5; done

echo "== 一般 kernel 家 K（kernel 池那顆自動叫 k）"
echo '{"cpus": {"0": {}}}' > "$W/kernel.json"
aos-kernel init --target "$K" --config "$W/kernel.json"
aos-kernel boot --target "$K" --daemon-target "$D"

echo "== 花錢的 kernel 家 K2（kernel 池那顆叫 k2，不然跟 K 的 k 撞名 NameTaken）"
sed "s|@W@|$W|g" "$T/kernel2.json" > "$W/kernel2.json"
aos-kernel init --target "$K2" --config "$W/kernel2.json"
aos-kernel boot --target "$K2" --daemon-target "$D"

echo "== codex 專用設定資料夾：只放登入（符號連結，不複製；見 stage0.md 的坑）"
ln -s "$HOME/.codex/auth.json" "$W/codex-home/auth.json"

echo "== 放一張 codex 唯讀審查單"
J=$W/jobs/review-ls; mkdir -p "$J"
cat > "$J/task.md" <<'EOF'
你是唯讀審查員，不要改任何檔。審 proto5/tools/base/ls 這一支（它 import 同資料夾的 _common.py，必要時可以讀）。
找真的會出錯的地方（邊界、錯誤處理、跟 proto5/tools/README.md 說的不一致），每條一句、附行號；沒有就說沒有。全文 ≤ 800 字，繁體中文。
EOF
sed -e "s|@JOB@|$J|g" -e "s|@WS@|$R|g" "$T/codex-review.json" > "$J/inst.json"
line=$(aos-kernel add "$J/inst.json" --target "$K2" --once --pool codex --timeout-ms 600000 --name review-ls)
echo "$line"
sleep 3
aos-kernel ls --target "$K2"
# 回音檔名是 kernel 取的（第一欄），不是 --name；ack 要用它
wait_echo "$(echo "$line" | awk '{print $2}')" 660 && aos-kernel ack "$(echo "$line" | awk '{print $1}')" --target "$K2"
echo "== codex 事件（成功要有 turn.completed）"
grep -o '"type":"\(thread.started\|turn.completed\|turn.failed\)"[^}]*' "$J/out/events.jsonl" | cut -c1-120
echo "== 審查結果 $J/out/answer.md"
cat "$J/out/answer.md"; echo

if [ $WITH_CLAUDE = 1 ]; then
  echo "== claude 單 c1（只回 ok）"
  J1=$W/jobs/c1; mkdir -p "$J1"; echo '只回 ok 兩個字，不要用任何工具。' > "$J1/task.md"
  sed -e "s|@JOB@|$J1|g" -e "s|@WS@|$W/ws|g" "$T/claude-job.json" > "$J1/inst.json"
  aos-kernel add "$J1/inst.json" --target "$K2" --once --pool claude --timeout-ms 300000 --name c1 --wait-ms 330000
  python3 - "$J1/out/result.json" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1]))
print({k: d.get(k) for k in ('subtype', 'is_error', 'result', 'session_id', 'total_cost_usd')})
EOF
  S=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print('' if d.get('is_error') else d['session_id'])" "$J1/out/result.json")
  if [ -n "$S" ]; then
    echo "$S" > "$W/last-ok-session"
    echo "== claude 單 c2：從 c1（上一次成功的）分岔"
    J2=$W/jobs/c2; mkdir -p "$J2"; echo '剛才你回了什麼？只回那兩個字。' > "$J2/task.md"
    sed -e "s|@JOB@|$J2|g" -e "s|@WS@|$W/ws|g" -e "s|@SESSION@|$S|g" "$T/claude-next.json" > "$J2/inst.json"
    aos-kernel add "$J2/inst.json" --target "$K2" --once --pool claude --timeout-ms 300000 --name c2 --wait-ms 330000
    python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print({k: d.get(k) for k in ('subtype','is_error','result','session_id')})" "$J2/out/result.json"
  fi
fi
