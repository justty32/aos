#!/bin/bash
# 9f：把 .aos/inst.json.temp 的並寫窗口撐大（批 ~20MB），用 mv（瞬間）改變第二個 exec 看到的投遞集合
. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens3/env.sh
ROUNDS=${1:-100}
W=$LAB/w9f
STAGE=$LAB/stage9f; rm -rf "$STAGE"; mkdir -p "$STAGE"
python3 - "$STAGE" <<'PY'
import sys, json, os
d = sys.argv[1]
os.makedirs(os.path.join(d, "base"), exist_ok=True)
os.makedirs(os.path.join(d, "extra"), exist_ok=True)
for i in range(40):
    open(os.path.join(d, "base", f"{30000+i}-0.json"), "w").write(
        json.dumps([{"argv": ["/bin/true", "P" * 500000]}]))
for i in range(200):
    open(os.path.join(d, "extra", f"9{i:05d}-0.json"), "w").write(
        json.dumps([{"argv": ["/bin/true", "Q" * 500000]}]))
PY
du -sh "$STAGE/base" "$STAGE/extra"
CORRUPT=0; NUL=0
: > "$LAB/t9f-err.txt"
for r in $(seq 1 $ROUNDS); do
  mkworld "$W"
  IB=$W/.aos/inst.tempd
  cp "$STAGE/base"/*.json "$IB/"
  rm -rf "$LAB/hot"; cp -r "$STAGE/extra" "$LAB/hot"     # 同一個 tmpfs，mv 是瞬間的
  ( "$AOS" exec "$W" > "$LAB/t9f-a.txt" 2>&1 ) & A=$!
  ( "$AOS" exec "$W" > "$LAB/t9f-b.txt" 2>&1 ) & B=$!
  mv "$LAB/hot"/*.json "$IB/" 2>/dev/null
  # 偷看已發布的批有沒有 NUL
  for t in $(seq 1 400); do
    for f in "$W/.aos/inst.json" "$W/.aos/inst.json.runi" "$W/.aos/inst.json.temp"; do
      [ -e "$f" ] && head -c 2000000 "$f" 2>/dev/null | grep -qa $'\x00' && { NUL=$((NUL+1)); cp "$f" "$LAB/t9f-nul-$r.bin" 2>/dev/null; break 2; }
    done
  done
  wait $A $B
  cat "$LAB/t9f-a.txt" "$LAB/t9f-b.txt" >> "$LAB/t9f-err.txt"
  grep -qh 'JsonSyntax\|NotAnObject\|UnknownKey\|FieldTypeMismatch\|EmptyArgv\|DirectiveValue' "$LAB/t9f-a.txt" "$LAB/t9f-b.txt" && {
     CORRUPT=$((CORRUPT+1)); { echo "=== round $r ==="; grep -h 'record\|inst.json' "$LAB/t9f-a.txt" "$LAB/t9f-b.txt" | head -3; } >> "$LAB/t9f-detail.txt"; }
  for i in 1 2 3; do "$AOS" exec "$W" >> "$LAB/t9f-err.txt" 2>&1; done
done
echo "== 9f × $ROUNDS 輪（批約 20MB）=="
echo "  已發布／已取件的批解析失敗: $CORRUPT"
echo "  掃到含 NUL 的批檔          : $NUL"
head -20 "$LAB/t9f-detail.txt" 2>/dev/null
echo "  stderr:"; sed 's#/tmp/[^ ]*/w9f#<W>#g; s/[0-9]\{3,\}/<N>/g' "$LAB/t9f-err.txt" | sort | uniq -c | sort -rn | head -10 | sed 's/^/    /'
