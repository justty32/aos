#!/bin/sh
# L2-07  「看誰在忙」是壞的：狀態看不到未讀信，而且沒有任何指令看得到信箱。
#
# 劇本：boss 連投三封信給 w1，w1 還沒被推進任何一回合。
#
# 期待：boss 想知道 w1 忙不忙，`aos state` 應該顯示「有 3 封未讀」或 status=pending。
# 實際：(1) w1 的 `aos state` 一直是 {"status":"idle","detail":"等待訊息"}——
#           status 只反映**上一次跑完的 step**，完全不看 say/ 裡堆了幾封；
#       (2) `aos listen --once` 印空白、exit 0——listen 讀的是 log，
#           而 log 只有 step 跑過才會寫，所以未讀信在任何 aos 指令下都是隱形的；
#       (3) history.json 仍是 {"messages":[]}；
#       (4) 唯一看得到信的辦法是自己 `ls .aos/agents/<name>/say/`。
#
# 連帶：世界層 state.json 的 agents 欄只涵蓋**本世界**，
#       所以「一眼看全隊」必須一個世界一個世界地跑，沒有 `aos contact status`。
set -eu
AOS="${AOS_BIN:-aos}"
ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT

mkdir -p "$ROOT/boss/.aos" "$ROOT/w1/.aos"
(cd "$ROOT/boss" && "$AOS" agent init --name boss >/dev/null)
(cd "$ROOT/w1"   && "$AOS" agent init --name w1   >/dev/null)
(cd "$ROOT/boss" && "$AOS" contact add w1 ../w1 >/dev/null)

for i in 1 2 3; do (cd "$ROOT/boss" && "$AOS" say --to w1 "任務 $i" >/dev/null); done

echo "=== say/ 裡實際有幾封（自己 ls 才看得到） ==="
ls -1 "$ROOT/w1/.aos/agents/w1/say/" | wc -l

echo "=== w1 的 aos state ==="
(cd "$ROOT/w1" && "$AOS" state)

echo "=== w1 的 aos listen --once（未讀信是隱形的） ==="
(cd "$ROOT/w1" && "$AOS" listen --once 2>&1); echo "[exit=$?]"

echo "=== w1 的 history.json ==="
cat "$ROOT/w1/.aos/agents/w1/history.json"

echo
echo "=== 世界層 state.json 只有本世界的 agent ==="
echo "--- boss 的 state.json（看不到 w1）---"
cat "$ROOT/boss/.aos/state.json"

echo
echo "=== 有沒有一個指令能列出通訊錄上所有人的狀態？ ==="
(cd "$ROOT/boss" && "$AOS" contact status 2>&1) || echo "  -> 沒有 contact status 這個子命令"
echo "  -> 只能一個世界一個世界地跑 aos state：N 個 worker = N 次 cd + N 次指令"

if (cd "$ROOT/w1" && "$AOS" state) | grep -q '"status": "idle"'; then
  echo "FAIL: 堆了 3 封未讀，狀態還是 idle"
  exit 1
fi
