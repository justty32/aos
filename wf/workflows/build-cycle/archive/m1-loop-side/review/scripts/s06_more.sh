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

echo "########## 1) decode_header_id：巢狀物件裡的 \"id\" 先被吃掉"
W="$S/wn"; fresh "$W"
mkinst A > "$W/.aos/inst.tempd/1000-0.json"
"$S/probe" aggregate "$W/.aos/inst.json" >/dev/null
REAL=$(sed -n 's/.*"id":"\([0-9a-f]*\)".*/\1/p' "$W/.aos/inst-head.json")
echo "  這一批的真 id = $REAL"
rm -f "$W/.aos/inst.json"
cp "$S/D1.json" "$W/.aos/inst.tempd/1000-0.json"
# 手寫一份 header：真 id 藏在 result 的巢狀物件裡，頂層 id 是別的值
printf '{"version":1,"result":{"id":"%s"},"origin":"aggregated","id":"0000000000000000"}\n' "$REAL" > "$W/.aos/inst-head.json"
echo "  佈置的 header: $(cat "$W/.aos/inst-head.json")"
echo "  期望：頂層 id=0000... 與本輪摘要不同 → 應該正常發布並執行 A"
"$AOS" exec "$W"; echo "  exec rc=$?"
show "$W"

echo
echo "########## 2) .bad 覆蓋：同名的第二份壞投遞會蓋掉第一份的證據（§D-8）"
W="$S/wb"; fresh "$W"
printf 'FIRST-BAD-not-json\n' > "$W/.aos/inst.tempd/1000-0.json"
"$AOS" exec "$W"; echo "  exec#1 rc=$?"
echo "  bad 內容: [$(cat "$W/.aos/inst.tempd/1000-0.json.bad")]"
printf 'SECOND-BAD-not-json\n' > "$W/.aos/inst.tempd/1000-0.json"
"$AOS" exec "$W"; echo "  exec#2 rc=$?"
echo "  bad 內容: [$(cat "$W/.aos/inst.tempd/1000-0.json.bad")]  <= 第一份不見了"
echo "  inbox: $(cd "$W/.aos/inst.tempd" && ls -A | tr '\n' ' ')"

echo
echo "########## 3) 投遞內容含 raw NUL 會不會被 parser 接受（框架漏洞前提）"
W="$S/wz"; fresh "$W"
printf '[{"argv":["/bin/sh","-c","echo Z\000Q >> %s"]}]\n' "$LOG" > "$W/.aos/inst.tempd/1000-0.json"
od -c "$W/.aos/inst.tempd/1000-0.json" | head -3
"$AOS" exec "$W"; echo "  exec rc=$?"
show "$W"

echo
echo "########## 4) O_CLOEXEC 稽核：各處 open 旗標"
grep -n 'open_retry(.*O_\|open(' /home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-aadc15218d3266528/core/inst/src/exec.cpp
echo "---- run_batch 是否用 thread ----"
grep -n 'thread\|join\|parallel' /home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-aadc15218d3266528/core/inst/src/run_batch.cpp
