#!/bin/bash
R=/tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lead
AOS=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-aadc15218d3266528/build/bin/aos
cd "$R" || exit 1

echo "########## FIFO 單獨測試 ##########"
rm -rf Y1; mkdir -p Y1; $AOS init Y1 >/dev/null
mkfifo Y1/.aos/inst.tempd/pipe.json
printf '[{"argv":["/bin/true"]}]\n' > Y1/.aos/inst.tempd/zz-ok.json
echo "inbox: [$(ls -1A Y1/.aos/inst.tempd/ | tr '\n' ' ')]"
START=$(date +%s)
timeout 10 $AOS exec Y1 > /dev/null 2>&1
RC=$?
END=$(date +%s)
echo "exec 退出碼=$RC   耗時=$((END-START))s   (124 = 被 timeout 砍掉 = 卡死)"
echo "inbox 事後: [$(ls -1A Y1/.aos/inst.tempd/ | tr '\n' ' ')]"
echo ">>> 若 rc=124 且 zz-ok.json 還在，代表一個 FIFO 就讓整個世界停擺"
rm -f Y1/.aos/inst.tempd/pipe.json

echo
echo "########## 同一個世界，把 FIFO 拿掉之後 ##########"
timeout 10 $AOS exec Y1 > /dev/null 2>&1; echo "exec 退出碼=$?"
echo "inbox 事後: [$(ls -1A Y1/.aos/inst.tempd/ | tr '\n' ' ')]"

echo
echo "########## 符號連結（指向存在的非 JSON 檔）##########"
rm -rf Y2; mkdir -p Y2; $AOS init Y2 >/dev/null
ln -s /etc/passwd Y2/.aos/inst.tempd/link.json
timeout 10 $AOS exec Y2 2>&1 | head -3
echo "exec 退出碼=${PIPESTATUS[0]}"
echo "inbox 事後: [$(ls -1A Y2/.aos/inst.tempd/ | tr '\n' ' ')]"
echo "  .bad 是連結還是檔? $(ls -la Y2/.aos/inst.tempd/ | grep bad | sed 's/.*inst.tempd//')"

echo
echo "########## 斷掉的符號連結 ##########"
rm -rf Y3; mkdir -p Y3; $AOS init Y3 >/dev/null
ln -s /no/such/target Y3/.aos/inst.tempd/dead.json
timeout 10 $AOS exec Y3 2>&1 | head -3
echo "exec 退出碼=${PIPESTATUS[0]}"
echo "inbox 事後: [$(ls -1A Y3/.aos/inst.tempd/ | tr '\n' ' ')]"

echo
echo "########## 目錄 ##########"
rm -rf Y4; mkdir -p Y4; $AOS init Y4 >/dev/null
mkdir Y4/.aos/inst.tempd/adir.json
timeout 10 $AOS exec Y4 2>&1 | head -3
echo "exec 退出碼=${PIPESTATUS[0]}"
echo "inbox 事後: [$(ls -1A Y4/.aos/inst.tempd/ | tr '\n' ' ')]"
