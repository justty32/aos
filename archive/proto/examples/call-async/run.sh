#!/bin/sh
# call-async：父地呼叫子地（脫節，子自己有鐘），父再 await 結果落點。
# 裁決 P-01：沒有 daemon 在跑時，脫節呼叫**直接失敗**（狀態檔寫 no_daemon），
# 不再由 exec 自己 detach 一支 run。所以這個範例一開始就先起一個暫存家的 daemon，
# 由它去替子地起 `aos run <子> --register`，跑完再把 daemon 停掉。
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
AOS_PY="$HERE/../../aos.py"
LAND="$HERE"
CHILD="$HERE/child"

echo "== 清乾淨（含 AOS_HOME 用的暫存家） =="
rm -rf "$LAND/.aos" "$CHILD/.aos" "$LAND/out" "$LAND/.home"
mkdir -p "$LAND/.home"
export AOS_HOME="$LAND/.home"
echo "AOS_HOME=$AOS_HOME（範例自己的暫存目錄，不碰使用者的 ~）"

stop_daemon() {
  python3 "$AOS_PY" daemon stop >/dev/null 2>&1 || true
}
trap stop_daemon EXIT INT TERM

echo "== init 父地與子地 =="
python3 "$AOS_PY" init "$LAND"
python3 "$AOS_PY" init "$CHILD"

echo "== 起 daemon（P-01：沒有它，下面那個 async 呼叫會直接失敗） =="
python3 "$AOS_PY" daemon start --every 200

echo "== 走格 =="
i=0
while [ "$i" -lt 15 ]; do
  OUT=$(python3 "$AOS_PY" exec "$LAND")
  echo "$OUT"
  if echo "$OUT" | grep -q "閒著了"; then
    break
  fi
  sleep 0.2
  i=$((i + 1))
done

echo "== 登記表（$AOS_HOME/.aos/registry.json，看子地登記了沒） =="
cat "$AOS_HOME/.aos/registry.json" 2>/dev/null || echo "(沒有)"

echo "== 結果：父指定的結果落點 out/child-said.txt =="
if [ -f "$LAND/out/child-said.txt" ]; then
  cat "$LAND/out/child-said.txt"
else
  echo "(沒有這個檔——看上面的格輸出跟登記表，可能是 daemon 起的 aos run 還沒跑完)"
  exit 1
fi

echo "== 父地串狀態 =="
python3 "$AOS_PY" status "$LAND"

echo "== 停 daemon =="
python3 "$AOS_PY" daemon stop
