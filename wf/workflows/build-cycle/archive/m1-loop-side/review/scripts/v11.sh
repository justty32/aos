#!/bin/bash
# 隊長複驗鏡頭 3 的新發現
R=/tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lead
AOS=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-aadc15218d3266528/build/bin/aos
cd "$R" || exit 1

echo "################ Y-1：.aos/inst.json 是斷掉的 symlink ################"
rm -rf Q1; mkdir -p Q1; $AOS init Q1 >/dev/null
ln -s /nonexistent/gone Q1/.aos/inst.json
: > Q1.log
for i in 1 2 3; do
  printf '[{"argv":["/bin/sh","-c","echo M%s >> %s/Q1.log"]}]\n' "$i" "$R" > Q1/.aos/inst.tempd/d$i.json
done
for i in 1 2 3; do
  OUT=$($AOS exec Q1 2>&1); RC=$?
  echo "  exec#$i rc=$RC stderr=[$OUT]"
done
echo "  log 內容: [$(tr '\n' ',' < Q1.log)]   (空 = 一筆都沒跑)"
echo "  inbox 堆積: $(ls -1A Q1/.aos/inst.tempd/ | wc -l) 份"
echo "  turn=$(cat Q1/.aos/turn)"
rm -f Q1/.aos/inst.json
$AOS exec Q1 >/dev/null 2>&1
echo "  移除壞 symlink 後: log=[$(tr '\n' ',' < Q1.log)]"

echo
echo "################ X-1：header 寫失敗 + 投遞刪失敗 → 無限重跑 ################"
rm -rf Q2; mkdir -p Q2; $AOS init Q2 >/dev/null
mkdir Q2/.aos/inst-head.json.temp          # 讓 header 寫入 EISDIR
: > Q2.log
printf '[{"argv":["/bin/sh","-c","echo R >> %s/Q2.log"]}]\n' "$R" > Q2/.aos/inst.tempd/1000-0.json
chmod 500 Q2/.aos/inst.tempd               # 讓投遞刪不掉
for i in 1 2 3; do
  $AOS exec Q2 2>&1 | sed 's/^/    /'
  echo "  exec#$i 後 log 行數=$(wc -l < Q2.log)"
done
chmod 700 Q2/.aos/inst.tempd

echo
echo "################ turn = UINT64_MAX 溢位 ################"
rm -rf Q3; mkdir -p Q3; $AOS init Q3 >/dev/null
echo "18446744073709551615" > Q3/.aos/turn
printf '[{"argv":["/bin/true"]}]\n' > Q3/.aos/inst.tempd/a.json
$AOS exec Q3; echo "  rc=$?"
echo "  turn 之後 = [$(cat Q3/.aos/turn)]   (0 = 靜默回繞)"

echo
echo "################ 15d：去重命中 + 無關的 inst.json.temp 殘骸 ################"
rm -rf Q4; mkdir -p Q4; $AOS init Q4 >/dev/null
: > Q4.log
printf '[{"argv":["/bin/sh","-c","echo GOOD >> %s/Q4.log"]}]\n' "$R" > Q4/.aos/inst.tempd/1234-0.json
$AOS exec Q4 >/dev/null 2>&1
echo "  exec1 後 log=[$(tr '\n' ',' < Q4.log)]  header=$(cat Q4/.aos/inst-head.json)"
# 放回同名同內容（觸發去重）＋ 手動塞一份完全無關的 .temp
printf '[{"argv":["/bin/sh","-c","echo GOOD >> %s/Q4.log"]}]\n' "$R" > Q4/.aos/inst.tempd/1234-0.json
printf '[{"argv":["/bin/sh","-c","echo UNRELATED_GARBAGE >> %s/Q4.log"]}]\n' "$R" > Q4/.aos/inst.json.temp
$AOS exec Q4; echo "  rc=$?"
echo "  exec2 後 log=[$(tr '\n' ',' < Q4.log)]"
echo "  >>> 若出現 UNRELATED_GARBAGE = 無關殘骸被當成這一批扶正執行"
