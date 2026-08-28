#!/bin/bash
# 9e：逼出 .aos/inst.json.temp 的 O_TRUNC 交錯寫（兩個 aggregate 內容長度不同）
. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens3/env.sh
ROUNDS=${1:-40}
W=$LAB/w9e
STAGE=$LAB/stage9e; rm -rf "$STAGE"; mkdir -p "$STAGE"
# 200 份 ~50KB 的投遞（A 要寫 ~10MB 的 .temp）
python3 - "$STAGE" <<'PY'
import sys, json, os
d=sys.argv[1]
for i in range(200):
    open(os.path.join(d, f"{20000+i}-0.json"),"w").write(json.dumps([{"argv":["/bin/true","P"*50000]}]))
# 額外一份超大的，讓 B 的 .temp 長很多
open(os.path.join(d,"99999-0.json"),"w").write(json.dumps([{"argv":["/bin/true","Q"*10000000]}]))
PY
ls -la "$STAGE" | head -3
CORRUPT=0; NUL=0
: > "$LAB/t9e-err.txt"
for r in $(seq 1 $ROUNDS); do
  mkworld "$W"
  cp "$STAGE"/2*.json "$W/.aos/inst.tempd/"
  ( "$AOS" exec "$W" > "$LAB/t9e-a.txt" 2>&1 ) & A=$!
  cp "$STAGE/99999-0.json" "$W/.aos/inst.tempd/x99999-0.json"
  ( "$AOS" exec "$W" > "$LAB/t9e-b.txt" 2>&1 ) & B=$!
  # 一邊跑一邊偷看 inst.json / .runi 有沒有 NUL
  for t in $(seq 1 200); do
    for f in "$W/.aos/inst.json" "$W/.aos/inst.json.runi"; do
      [ -e "$f" ] && grep -qa $'\x00' "$f" 2>/dev/null && { NUL=$((NUL+1)); cp "$f" "$LAB/t9e-nul-$r.bin"; break 2; }
    done
  done
  wait $A $B
  cat "$LAB/t9e-a.txt" "$LAB/t9e-b.txt" >> "$LAB/t9e-err.txt"
  grep -qh 'JsonSyntax\|NotAnObject\|UnknownKey\|FieldTypeMismatch\|EmptyArgv' "$LAB/t9e-a.txt" "$LAB/t9e-b.txt" && CORRUPT=$((CORRUPT+1))
  for i in 1 2 3; do "$AOS" exec "$W" >> "$LAB/t9e-err.txt" 2>&1; done
done
echo "== 9e × $ROUNDS 輪 =="
echo "  批被寫壞（解析錯誤）: $CORRUPT"
echo "  抓到含 NUL 的已發布批: $NUL"
ls -la "$LAB"/t9e-nul-*.bin 2>/dev/null | head
echo "  stderr:"; sed 's#/tmp/[^ ]*/w9e#<W>#g; s/[0-9]\{3,\}/<N>/g' "$LAB/t9e-err.txt" | sort | uniq -c | sort -rn | head -10 | sed 's/^/    /'
