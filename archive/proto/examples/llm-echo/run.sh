#!/bin/sh
# llm-echo：投一筆 kind:"llm" 請求給 LLM 世界（假後端 echo:，不打真的網路），
# aos llm tick 把回話取回來，父地 await 到結果再印出來。
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
AOS_PY="$HERE/../../aos.py"
LAND="$HERE"

echo "== 清乾淨（含 AOS_HOME 用的暫存家） =="
rm -rf "$LAND/.aos" "$LAND/.home" "$LAND/answer.txt" "$LAND/answer.txt.status.json" "$LAND/prompt.txt"
mkdir -p "$LAND/.home"
export AOS_HOME="$LAND/.home"
echo "AOS_HOME=$AOS_HOME（範例自己的暫存目錄，不碰使用者的 ~）"
LLMWORLD="$AOS_HOME/.aos/llm"

echo "== init 這塊地 =="
python3 "$AOS_PY" init "$LAND"

echo "== init LLM 世界（預設處理單元是假後端 echo:，不打網路） =="
python3 "$AOS_PY" llm init

echo "== 寫 prompt 檔 =="
printf '哈囉，這是 llm-echo 範例的 prompt。\n' > "$LAND/prompt.txt"

echo "== 投一筆 kind:llm 請求給 LLM 世界 =="
REQ='{"kind":"llm","prompt":"prompt.txt","result":"answer.txt","tier":"fast"}'
python3 "$AOS_PY" deliver "$LLMWORLD" "$REQ" --sender "$LAND"

echo "== 交替走格：父地 await、LLM 世界 tick =="
i=0
while [ "$i" -lt 8 ]; do
  OUT=$(python3 "$AOS_PY" exec "$LAND")
  echo "$OUT"
  if echo "$OUT" | grep -q "閒著了"; then
    break
  fi
  echo "-- aos llm tick --"
  python3 "$AOS_PY" llm tick --land "$LLMWORLD"
  i=$((i + 1))
done

echo "== 結果：父地的 answer.txt =="
if [ -f "$LAND/answer.txt" ]; then
  cat "$LAND/answer.txt"
else
  echo "(沒有這個檔，看上面的格輸出跟帳簿)"
fi

echo "== 帳簿 \$AOS_HOME/.aos/ledger.jsonl =="
cat "$AOS_HOME/.aos/ledger.jsonl" 2>/dev/null || echo "(沒有)"

echo "== 父地串狀態 =="
python3 "$AOS_PY" status "$LAND"
