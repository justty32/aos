#!/bin/sh
# call-async：父地呼叫子地（脫節，子自己有鐘），父再 await 結果落點。
# 子地的時鐘靠 aos run 撐起；沒有 daemon 在看管時，exec 自己會 detach 一支
# `aos run <子> --register` 去跑（WRITER-BRIEF 4.11 第 6 條）。這裡不特別起
# daemon，讓那個自動 detach 接手，一樣能看到子地真的把結果寫回來。
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

echo "== init 父地與子地 =="
python3 "$AOS_PY" init "$LAND"
python3 "$AOS_PY" init "$CHILD"

echo "== 走格（沒起 daemon；exec 自己會 detach 一支 aos run 去撐子地的鐘） =="
i=0
while [ "$i" -lt 10 ]; do
  OUT=$(python3 "$AOS_PY" exec "$LAND")
  echo "$OUT"
  if echo "$OUT" | grep -q "閒著了"; then
    break
  fi
  i=$((i + 1))
done

echo "== 登記表（$AOS_HOME/.aos/registry.json，看子地登記了沒） =="
cat "$AOS_HOME/.aos/registry.json" 2>/dev/null || echo "(沒有)"

echo "== 結果：父指定的結果落點 out/child-said.txt =="
if [ -f "$LAND/out/child-said.txt" ]; then
  cat "$LAND/out/child-said.txt"
else
  echo "(沒有這個檔——看上面的格輸出跟登記表，可能是 detach 的 aos run 還沒跑完)"
fi

echo "== 父地串狀態 =="
python3 "$AOS_PY" status "$LAND"
