#!/bin/sh
# call-sync：父地呼叫子地（同步），子地把結果寫到父指定的結果落點，父再印出來。
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
AOS_PY="$HERE/../../aos.py"
LAND="$HERE"
CHILD="$HERE/child"

echo "== 清乾淨 =="
rm -rf "$LAND/.aos" "$CHILD/.aos" "$LAND/out"

echo "== init 父地與子地 =="
python3 "$AOS_PY" init "$LAND"
python3 "$AOS_PY" init "$CHILD"

echo "== 走格（父每格對子做一次 aos exec，子沒閒著父就停在原地） =="
i=0
while [ "$i" -lt 10 ]; do
  OUT=$(python3 "$AOS_PY" exec "$LAND")
  echo "$OUT"
  if echo "$OUT" | grep -q "閒著了"; then
    break
  fi
  i=$((i + 1))
done

echo "== 結果：父指定的結果落點 out/child-said.txt =="
if [ -f "$LAND/out/child-said.txt" ]; then
  cat "$LAND/out/child-said.txt"
else
  echo "(沒有這個檔，call 大概失敗了，往下看 status)"
fi

echo "== 印出的內容（父的 print 那一步 stdout） =="
FOUND=0
for f in "$LAND"/.aos/ticks/*/results/*.stdout; do
  [ -s "$f" ] || continue
  cat "$f"
  FOUND=1
done
[ "$FOUND" = 1 ] || echo "(沒找到非空的 stdout)"

echo "== 父地串狀態 =="
python3 "$AOS_PY" status "$LAND"
echo "== 呼叫記錄 .aos/calls/ =="
ls "$LAND/.aos/calls" 2>/dev/null || echo "(沒有)"
