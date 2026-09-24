#!/usr/bin/env bash
# 階 0 一條龍：daemon → 一般 kernel 家 K（只有 1 顆 cpu）＋花錢的 kernel 家 K2（claude 1、codex 2）
# → 丟一張 codex 唯讀審查單 → 收回音 → 停機。加 --with-claude 再丟兩張最小的 claude 單（第二張從第一張分岔）。
# 用法：bash stage0-run.sh [W] [--with-claude] [--no-codex]
#   W 預設 $HOME/aos-cli-try，必須是還不存在的絕對路徑，只准英數與 / . _ -（範本用 sed 換字）。
# 花費：codex 1 次（審一支 34 行的工具，約十幾萬 input token）；--with-claude 多 claude 2 次（都只回 ok）。
# 任何一步失敗就停、不再放下一張單，退出碼非 0。不碰 LM Studio／ollama；不用任何「跳過權限」旗標。
set -u
W=$HOME/aos-cli-try; WITH_CLAUDE=0; WITH_CODEX=1
for a in "$@"; do case $a in --with-claude) WITH_CLAUDE=1 ;; --no-codex) WITH_CODEX=0 ;; *) W=$a ;; esac; done
R=$(cd "$(dirname "$0")/../../.." && pwd)            # repo 根目錄
T=$R/proto5/templates/cli-agents
case $W in /*) ;; *) echo "W 要寫絕對路徑"; exit 2 ;; esac
case "$W$R" in *[!A-Za-z0-9/._-]*) echo "W 或 repo 路徑有英數與 / . _ - 以外的字（sed 換字會壞）：$W $R"; exit 2 ;; esac
[ -e "$W" ] && { echo "$W 已經在；換一個 W，或先 rm -rf $W"; exit 2; }
[ -e "$HOME/.codex/auth.json" ] || { echo "沒有 ~/.codex/auth.json：先 codex login"; exit 2; }
mkdir -p "$W/cli-jobs" "$W/ws" "$W/codex-home"
export PATH=$R/proto5/cli:$PATH
D=$W/D K=$W/K K2=$W/K2
FAIL=0

die() { echo "失敗：$*"; FAIL=1; exit 1; }
stop_all() {
  rc=$?; [ $FAIL = 1 ] && rc=1
  echo "== 停機"
  aos-kernel halt --target "$K2" --wait-ms 60000
  aos-kernel halt --target "$K" --wait-ms 60000
  aos-daemon halt --target "$D"
  exit $rc
}
trap stop_all EXIT

# 回音與輸出兩層都過才算成功。$1＝回音檔、$2＝claude|codex、$3＝結果檔；成功時印出下一次要用的 session id
check_ok() {
  python3 - "$@" <<'EOF'
import json, sys
echo, cli, out = sys.argv[1:4]
e = json.load(open(echo))
r = e.get('result')
if not isinstance(r, dict) or r.get('kind') != 'child' or r.get('code') != 0 or r.get('timed_out') is not False or r.get('stopped') is not False:
    sys.exit('回音不是成功：%s' % json.dumps(e, ensure_ascii=False))
if cli == 'claude':
    d = json.load(open(out))
    if d.get('is_error') is not False or d.get('subtype') != 'success' or not d.get('session_id'):
        sys.exit('claude 說失敗：%s' % {k: d.get(k) for k in ('subtype', 'is_error', 'result')})
    print(d['session_id'])
else:
    ev = [json.loads(l) for l in open(out) if l.strip()]
    types = [x.get('type') for x in ev]
    if 'turn.completed' not in types or 'turn.failed' in types:
        sys.exit('codex 沒有 turn.completed：%s' % types)
    print(next(x['thread_id'] for x in ev if x.get('type') == 'thread.started'))
EOF
}

# $1＝inst、$2＝池、$3＝逾時毫秒；放單、等回音、印回音、ack；印出回音檔的暫存副本路徑
submit_wait() {
  local line name
  line=$(aos-kernel add "$1" --target "$K2" --once --pool "$2" --timeout-ms "$3") || die "add 失敗"
  name=${line%% *}                                   # 第一欄＝kernel 取的單名（ack 用它，不用 --name）
  echo "放單：$name" >&2
  sleep 3; aos-kernel ls --target "$K2" >&2
  local i=0 max=$(( $3 / 1000 + 60 ))
  while [ ! -e "$K2/responses/$name" ] && [ $i -lt $max ]; do sleep 1; i=$((i + 1)); done
  [ -e "$K2/responses/$name" ] || die "等了 $max 秒沒有回音：$name"
  echo "回音（等了約 $i 秒）：$(cat "$K2/responses/$name")" >&2
  cp "$K2/responses/$name" "$1.echo.json"
  aos-kernel ack "$name" --target "$K2" >/dev/null || die "ack 失敗"
  echo "$1.echo.json"
}

echo "== 開 daemon"
setsid aos-daemon boot --target "$D" >>"$W/daemon.log" 2>&1 </dev/null &
for i in 1 2 3 4 5 6 7 8 9 10; do [ -e "$D/state.json" ] && break; sleep 0.5; done

echo "== 一般 kernel 家 K（kernel 池那顆自動叫 k）"
echo '{"cpus": {"0": {}}}' > "$W/kernel.json"
aos-kernel init --target "$K" --config "$W/kernel.json" || die "K init"
aos-kernel boot --target "$K" --daemon-target "$D" || die "K boot"

echo "== 花錢的 kernel 家 K2（kernel 池那顆叫 k2，不然跟 K 的 k 撞名 NameTaken）"
sed "s|@W@|$W|g" "$T/kernel2.json" > "$W/kernel2.json"
aos-kernel init --target "$K2" --config "$W/kernel2.json" || die "K2 init"
aos-kernel boot --target "$K2" --daemon-target "$D" || die "K2 boot"

echo "== codex 專用設定資料夾：只放登入（符號連結，不複製；見 stage0.md 的坑）"
ln -s "$HOME/.codex/auth.json" "$W/codex-home/auth.json" || die "登入連結"

if [ $WITH_CODEX = 1 ]; then
  echo "== 放一張 codex 唯讀審查單"
  J=$W/cli-jobs/review-ls; mkdir -p "$J"
  cat > "$J/task.md" <<'EOF'
你是唯讀審查員，不要改任何檔。審 proto5/tools/base/ls 這一支（它 import 同資料夾的 _common.py，必要時可以讀）。
找真的會出錯的地方（邊界、錯誤處理、跟 proto5/tools/README.md 說的不一致），每條一句、附行號；沒有就說沒有。全文 ≤ 800 字，繁體中文。
EOF
  sed -e "s|@JOB@|$J|g" -e "s|@WS@|$R|g" "$T/codex-review.json" > "$J/inst.json"
  E=$(submit_wait "$J/inst.json" codex 600000) || exit 1
  TID=$(check_ok "$E" codex "$J/out/events.jsonl") || die "codex 單"
  echo "成功；thread_id=$TID"
  echo "== 審查結果 $J/out/answer.md"; cat "$J/out/answer.md"; echo
fi

if [ $WITH_CLAUDE = 1 ]; then
  echo "== claude 單 c1（只回 ok）"
  J1=$W/cli-jobs/c1; mkdir -p "$J1"; echo '只回 ok 兩個字，不要用任何工具。' > "$J1/task.md"
  sed -e "s|@JOB@|$J1|g" -e "s|@WS@|$W/ws|g" "$T/claude-job.json" > "$J1/inst.json"
  E=$(submit_wait "$J1/inst.json" claude 300000) || exit 1
  S=$(check_ok "$E" claude "$J1/out/result.json") || die "claude c1"
  echo "$S" > "$W/last-ok-session"; echo "成功；last-ok-session=$S"
  echo "== claude 單 c2：從上一次成功的（c1）分岔"
  J2=$W/cli-jobs/c2; mkdir -p "$J2"; echo '剛才你回了什麼？只回那兩個字。' > "$J2/task.md"
  sed -e "s|@JOB@|$J2|g" -e "s|@WS@|$W/ws|g" -e "s|@SESSION@|$(cat "$W/last-ok-session")|g" "$T/claude-next.json" > "$J2/inst.json"
  E=$(submit_wait "$J2/inst.json" claude 300000) || exit 1
  S=$(check_ok "$E" claude "$J2/out/result.json") || die "claude c2"
  echo "$S" > "$W/last-ok-session"; echo "成功；回答=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['result'])" "$J2/out/result.json")；last-ok-session=$S"
fi
