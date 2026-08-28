. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens2/env.sh
cd "$S" || exit 1
gcc -shared -fPIC -O0 -o fault.so fault.c -ldl || exit 1
LOG="$S/ran.log"
W="$S/wq"; rm -rf "$W"; mkdir -p "$W"; "$AOS" init "$W" >/dev/null; : > "$LOG"
printf '[{"argv":["/bin/sh","-c","echo A >> %s"]}]\n' "$LOG" > "$S/b.json"

echo "== 1) 只逼走 link+unlink 退路（unlink 正常）=="
FAULT_NO_RENAMEAT2=1 LD_PRELOAD="$S/fault.so" "$AOS" deliver "$W" -f "$S/b.json"
echo "   rc=$?  inbox: $(cd "$W/.aos/inst.tempd" && ls -A | tr '\n' ' ')"

echo
echo "== 2) 退路的 unlink 也失敗（link 已成功）=="
rm -f "$W"/.aos/inst.tempd/*
FAULT_NO_RENAMEAT2=1 FAULT_UNLINK_TEMP=1 LD_PRELOAD="$S/fault.so" "$AOS" deliver "$W" -f "$S/b.json"
echo "   deliver rc=$?"
echo "   inbox: $(cd "$W/.aos/inst.tempd" && ls -A | tr '\n' ' ')"
echo "   ^^ deliver 回報失敗，但投遞是不是已經在收件匣裡？"

echo
echo "== 3) 生產者依據失敗回報重投一次（正常路徑）=="
"$AOS" deliver "$W" -f "$S/b.json"
echo "   rc=$?  inbox: $(cd "$W/.aos/inst.tempd" && ls -A | tr '\n' ' ')"
"$AOS" exec "$W" >/dev/null; echo "   exec rc=$?"
echo "   ran.log: [$(tr '\n' ',' < "$LOG")]   <= 執行幾次？"
echo "   inbox 殘留: $(cd "$W/.aos/inst.tempd" && ls -A | tr '\n' ' ')"
