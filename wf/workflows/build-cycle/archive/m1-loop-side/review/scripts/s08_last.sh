. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens2/env.sh
LOG="$S/ran.log"
mkinst() { printf '[{"argv":["/bin/sh","-c","echo %s >> %s"]}]\n' "$1" "$LOG"; }
fresh() { rm -rf "$1"; mkdir -p "$1"; "$AOS" init "$1" >/dev/null || exit 1; : > "$LOG"; }
show() {
  echo "  -- files: $(cd "$1/.aos" && ls -A | tr '\n' ' ')"
  echo "  -- inbox: $(cd "$1/.aos/inst.tempd" && ls -A | tr '\n' ' ')"
  echo "  -- head:  $(cat "$1/.aos/inst-head.json" 2>/dev/null)"
  echo "  -- ran.log: [$(tr '\n' ',' < "$LOG")]"
}

echo "########## F1：header 舊 id ＋ 批已發布 ＋ 投遞還在（＝header 寫失敗那條退化路徑）"
W="$S/wf1"; fresh "$W"
mkinst A > "$W/.aos/inst.tempd/1000-0.json"
"$S/probe" aggregate "$W/.aos/inst.json" >/dev/null
cp "$S/D1.json" "$W/.aos/inst.tempd/1000-0.json"
rm -f "$W/.aos/inst-head.json"          # 模擬 header 沒寫成／舊 id
echo "  [佈置完成]"; show "$W"
"$AOS" exec "$W" >/dev/null; echo "  exec#1 rc=$?"
"$AOS" exec "$W" >/dev/null; echo "  exec#2 rc=$?"
"$AOS" exec "$W" >/dev/null; echo "  exec#3 rc=$?"
show "$W"

echo
echo "########## F2：header 新 id ＋ 無 .temp ＋ 投遞還在（只清投遞、不重發）"
W="$S/wf2"; fresh "$W"
mkinst A > "$W/.aos/inst.tempd/1000-0.json"
"$S/probe" aggregate "$W/.aos/inst.json" >/dev/null
rm -f "$W/.aos/inst.json"               # 批已被取走執行完
cp "$S/D1.json" "$W/.aos/inst.tempd/1000-0.json"
echo "  [佈置完成]"; show "$W"
"$AOS" exec "$W"; echo "  exec rc=$?"
show "$W"

echo
echo "########## F3：只有壞投遞時，隔離 rename 之後完全沒有目錄 fsync"
W="$S/wf3"; rm -rf "$W"; mkdir -p "$W"; "$AOS" init "$W" >/dev/null
rm -f "$S/trace3.log"; export FSTRACE_LOG="$S/trace3.log"; export FSTRACE_FILTER=".aos"
printf 'not-json\n' > "$W/.aos/inst.tempd/1000-0.json"
LD_PRELOAD="$S/fstrace.so" "$AOS" exec "$W"; echo "  exec rc=$?"
echo "  ---- trace ----"; cat "$S/trace3.log"
