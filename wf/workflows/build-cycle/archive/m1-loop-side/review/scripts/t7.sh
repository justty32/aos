#!/bin/bash
. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens3/env.sh
N=${1:-50}; ROUNDS=${2:-10}
FAIL=0
echo "############ 7 每輪 $N 個並發 aos deliver × $ROUNDS 輪 ############"
for r in $(seq 1 $ROUNDS); do
  W=$LAB/w7; mkworld "$W"
  IB=$W/.aos/inst.tempd
  rm -f "$LAB/d7out.txt"
  for i in $(seq 1 $N); do
    ( printf '%s\n' '[{"argv":["/bin/true","'"r${r}i${i}"'"]}]' | "$AOS" deliver "$W" >> "$LAB/d7out.txt" 2>&1 ) &
  done
  wait
  ok=$(grep -c '"delivery"' "$LAB/d7out.txt")
  files=$(ls -A "$IB" | grep -c '\.json$')
  temps=$(ls -A "$IB" | grep -c '\.temp$')
  uniq=$(ls -A "$IB" | grep '\.json$' | sort -u | wc -l)
  # 每一份投遞的內容標記都不同，數一數標記總數
  marks=$(cat "$IB"/*.json 2>/dev/null | grep -o 'r[0-9]*i[0-9]*' | sort -u | wc -l)
  err=$(grep -vc '"delivery"' "$LAB/d7out.txt" 2>/dev/null || echo 0)
  printf 'round %2d: deliver成功=%d  inbox .json=%d  唯一名=%d  唯一標記=%d  .temp殘留=%d\n' \
      "$r" "$ok" "$files" "$uniq" "$marks" "$temps"
  if [ "$ok" != "$N" ] || [ "$files" != "$N" ] || [ "$uniq" != "$N" ] || [ "$marks" != "$N" ] || [ "$temps" != "0" ]; then
    FAIL=1; echo "  !!! 不一致，stderr:"; grep -v '"delivery"' "$LAB/d7out.txt" | head -5
  fi
done
echo "結果: $([ $FAIL = 0 ] && echo 全部通過 || echo 有不一致)"

echo
echo "############ 7b 不清空 inbox，連投 8 輪 × $N（測撞名重試）############"
W=$LAB/w7b; mkworld "$W"; IB=$W/.aos/inst.tempd
for r in $(seq 1 8); do
  for i in $(seq 1 $N); do
    ( printf '%s\n' '[{"argv":["/bin/true","'"R${r}I${i}"'"]}]' | "$AOS" deliver "$W" > /dev/null 2>>"$LAB/d7berr.txt" ) &
  done
  wait
done
echo "累積投遞成功應為 $((N*8))"
echo "  inbox .json 檔數: $(ls -A "$IB" | grep -c '\.json$')"
echo "  唯一標記數: $(cat "$IB"/*.json 2>/dev/null | grep -o 'R[0-9]*I[0-9]*' | sort -u | wc -l)"
echo "  .temp 殘留: $(ls -A "$IB" | grep -c '\.temp$')"
echo "  stderr: $(cat "$LAB/d7berr.txt" 2>/dev/null | head -3)"
echo "  最後全部彙整執行一次："
"$AOS" exec "$W" >/dev/null 2>&1; echo "  exec rc=$?"
echo "  inbox 清空: [$(ls -A "$IB")]"
