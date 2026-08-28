#!/bin/bash
# 隊長複驗鏡頭 1 的新發現
R=/tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lead
AOS=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-aadc15218d3266528/build/bin/aos
cd "$R" || exit 1

echo "########## 複驗 #2：隔離覆蓋既有 .bad ##########"
rm -rf v2; mkdir -p v2; $AOS init v2 >/dev/null
echo 'FIRST-BAD-EVIDENCE' > v2/.aos/inst.tempd/x.json
$AOS exec v2 2>&1 | head -1
echo "第一次隔離: [$(ls -1A v2/.aos/inst.tempd/)]  內容=[$(cat v2/.aos/inst.tempd/x.json.bad)]"
echo 'SECOND-BAD-EVIDENCE' > v2/.aos/inst.tempd/x.json
$AOS exec v2 2>&1 | head -1
echo "第二次隔離: [$(ls -1A v2/.aos/inst.tempd/)]  內容=[$(cat v2/.aos/inst.tempd/x.json.bad)]"
echo ">>> 若內容變成 SECOND，第一份鑑識證據被無聲銷毀"

echo
echo "########## 複驗 #3：讀不到的合法投遞被貼 .bad ##########"
rm -rf v3; mkdir -p v3; $AOS init v3 >/dev/null
printf '[{"argv":["/bin/true"]}]\n' > v3/.aos/inst.tempd/y.json
chmod 000 v3/.aos/inst.tempd/y.json
$AOS exec v3 2>&1 | head -2; echo "exit=$?"
echo "inbox: [$(ls -1A v3/.aos/inst.tempd/)]"
chmod 644 v3/.aos/inst.tempd/y.json.bad 2>/dev/null
echo "被標 .bad 的內容其實是: [$(cat v3/.aos/inst.tempd/y.json.bad 2>/dev/null)]"
echo ">>> 內容合法卻永久出局（.bad 不進彙整、MUST NOT 自動清）"

echo
echo "########## 複驗 #6：.runi 存在時仍完成整輪彙整才回 3 ##########"
rm -rf v6; mkdir -p v6; $AOS init v6 >/dev/null
printf '[{"argv":["/bin/true"]}]\n' > v6/.aos/inst.tempd/z.json
printf '[{"argv":["/bin/true"]}]\n' > v6/.aos/inst.json.runi
echo "跑之前 .aos: [$(ls -1A v6/.aos | tr '\n' ' ')] inbox:[$(ls -1A v6/.aos/inst.tempd)]"
$AOS exec v6 2>&1 | head -1; echo "exit=${PIPESTATUS[0]}"
echo "跑之後 .aos: [$(ls -1A v6/.aos | tr '\n' ' ')] inbox:[$(ls -1A v6/.aos/inst.tempd)]"
echo ">>> 若 inst.json 與 inst-head.json 出現且 inbox 清空，代表拒絕啟動之前已做了三個不可逆動作"

echo
echo "########## 複驗 #8：version=0 / 無 LF ##########"
rm -rf v8; mkdir -p v8; $AOS init v8 >/dev/null
echo "0" > v8/.aos/version; $AOS exec v8 2>&1 | head -1; echo "  version=0 exit=${PIPESTATUS[0]}"
printf '1' > v8/.aos/version;  $AOS exec v8 2>&1 | head -1; echo "  version=1 無LF exit=${PIPESTATUS[0]}"
