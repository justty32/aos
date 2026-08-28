#!/bin/bash
R=/tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lead
AOS=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-aadc15218d3266528/build/bin/aos
cd "$R" || exit 1

echo "=== 零長度投遞 / 只有空白 / 只有 LF ==="
rm -rf Z1; mkdir -p Z1; $AOS init Z1 >/dev/null
: > Z1/.aos/inst.tempd/empty.json
printf '   \n\t ' > Z1/.aos/inst.tempd/blank.json
printf '\n' > Z1/.aos/inst.tempd/lf.json
printf '[{"argv":["/bin/true"]}]\n' > Z1/.aos/inst.tempd/good.json
$AOS exec Z1 2>&1 | head -5; echo "exit=${PIPESTATUS[0]}"
echo "inbox: [$(ls -1A Z1/.aos/inst.tempd/ | tr '\n' ' ')]"

echo
echo "=== 檔名含空白 / UTF-8 / 很長 ==="
rm -rf Z2; mkdir -p Z2; $AOS init Z2 >/dev/null
printf '[{"argv":["/bin/true"]}]\n' > "Z2/.aos/inst.tempd/has space.json"
printf '[{"argv":["/bin/true"]}]\n' > "Z2/.aos/inst.tempd/中文檔名.json"
LONG=$(python3 -c "print('n'*200)")
printf '[{"argv":["/bin/true"]}]\n' > "Z2/.aos/inst.tempd/$LONG.json"
echo "投遞前: $(ls -1A Z2/.aos/inst.tempd/ | wc -l) 份"
$AOS exec Z2 2>&1 | head -3; echo "exit=${PIPESTATUS[0]}"
echo "inbox 事後: [$(ls -1A Z2/.aos/inst.tempd/ | wc -l) 份殘留]"

echo
echo "=== .temp 殘檔與既有 .bad 混在 inbox 裡 ==="
rm -rf Z3; mkdir -p Z3; $AOS init Z3 >/dev/null
printf '[{"argv":["/bin/true"]}]\n' > Z3/.aos/inst.tempd/leftover.json.temp
printf 'garbage' > Z3/.aos/inst.tempd/old.json.bad
printf '[{"argv":["/bin/true"]}]\n' > Z3/.aos/inst.tempd/new.json
$AOS exec Z3 2>&1 | head -3; echo "exit=${PIPESTATUS[0]}"
echo "inbox 事後: [$(ls -1A Z3/.aos/inst.tempd/ | tr '\n' ' ')]"
echo ">>> .temp 與 .bad 應原地不動、new.json 應被吃掉"

echo
echo "=== deliver 的 -f 來源在別的檔案系統（EXDEV 檢查）==="
rm -rf Z4; mkdir -p Z4; $AOS init Z4 >/dev/null
printf '[{"argv":["/bin/true"]}]\n' > /dev/shm/aos-src-$$.json 2>/dev/null && {
  echo "來源在 /dev/shm（tmpfs），世界在 $(df --output=fstype . | tail -1)"
  $AOS deliver Z4 -f /dev/shm/aos-src-$$.json; echo "deliver exit=$?"
  rm -f /dev/shm/aos-src-$$.json
}
