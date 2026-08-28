. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens2/env.sh
LOG="$S/ran.log"
W="$S/wt"
rm -rf "$W"; mkdir -p "$W"; : > "$LOG"
rm -f "$S/trace2.log"
export FSTRACE_LOG="$S/trace2.log"
export FSTRACE_FILTER=".aos"
LD_PRELOAD="$S/fstrace.so" "$AOS" init "$W" || exit 1
# 一份壞投遞（走隔離路徑）＋一份好投遞（帶 exit 檔）
printf 'not-json\n' > "$W/.aos/inst.tempd/1000-0.json"
printf '[{"argv":["/bin/true"],"exit":"%s/.aos/exit.txt"}]\n' "$W" > "$W/.aos/inst.tempd/2000-0.json"
LD_PRELOAD="$S/fstrace.so" "$AOS" exec "$W"
echo "exec rc=$?"
echo "===== trace ====="
sed -e "s#$W/#W/#g" -e "s#$W#W#g" "$S/trace2.log"
