#!/bin/sh
# L2-14  同一個世界可以被兩條 aos run 同時推，沒有鎖、沒有警告。
#
# 期待：第二條 run 偵測到已經有 loop 在推這個世界，拒絕或等待。
# 實際：兩條都成功，各自推了一回合，回合號互相穿插。
#       派隊時不小心對同一個 worker 開兩條 loop，它一回合會被推兩次。
set -eu
AOS="${AOS_BIN:-aos}"
ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT

mkdir -p "$ROOT/w/.aos"
(cd "$ROOT/w" && "$AOS" agent init --name w >/dev/null)

# 放一條會拖住回合的 inst，讓兩條 run 確實重疊
printf '{"argv":["sleep","2"]}\n' > "$ROOT/w/.aos/every/slow.json"

(cd "$ROOT/w" && "$AOS" run --step 2 > "$ROOT/one.log" 2>&1) &
P1=$!
sleep 0.3
(cd "$ROOT/w" && "$AOS" run --step 2 > "$ROOT/two.log" 2>&1) &
P2=$!
wait $P1; R1=$?
wait $P2; R2=$?

echo "=== loop 1 (exit $R1) ==="; cat "$ROOT/one.log"
echo "=== loop 2 (exit $R2) ==="; cat "$ROOT/two.log"

TOTAL=$(cat "$ROOT/one.log" "$ROOT/two.log" | grep -c '^turn ')
echo "=== 兩條 loop 合計推了 $TOTAL 回合，最終 turn = $(cat "$ROOT/w/.aos/turn") ==="

if [ "$R1" -eq 0 ] && [ "$R2" -eq 0 ]; then
  echo "FAIL: 兩條 run 同時推同一個世界都成功，沒有鎖也沒有任何警告"
  exit 1
fi
