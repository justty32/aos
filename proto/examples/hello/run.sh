#!/bin/sh
# hello：三步一串——寫檔、讀檔、印出來。能一鍵重跑。
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
AOS_PY="$HERE/../../aos.py"
LAND="$HERE"

echo "== 清乾淨 =="
rm -rf "$LAND/.aos"

echo "== init =="
python3 "$AOS_PY" init "$LAND"

echo "== 走格（每步一格，最多走 8 格保險） =="
i=0
while [ "$i" -lt 8 ]; do
  OUT=$(python3 "$AOS_PY" exec "$LAND")
  echo "$OUT"
  if echo "$OUT" | grep -q "閒著了"; then
    break
  fi
  i=$((i + 1))
done

echo "== 結果：印出的內容（來自 print 那一步的 stdout） =="
FOUND=0
for f in "$LAND"/.aos/ticks/*/results/*.stdout; do
  [ -s "$f" ] || continue
  cat "$f"
  FOUND=1
done
if [ "$FOUND" = 0 ]; then
  echo "(沒找到非空的 stdout，串大概沒跑完，看上面的格輸出)"
fi

echo "== 串狀態 =="
python3 "$AOS_PY" status "$LAND"
