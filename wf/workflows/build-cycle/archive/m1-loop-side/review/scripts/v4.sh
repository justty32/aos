#!/bin/bash
R=/tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lead
AOS=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-aadc15218d3266528/build/bin/aos
cd "$R" || exit 1

echo "=== 寫檔失敗（ulimit -f 512 bytes）時 deliver 的殘留 ==="
rm -rf f1; mkdir -p f1; $AOS init f1 >/dev/null
python3 -c "
import json
print(json.dumps([{'argv':['/bin/echo','x'*4000]}]))" > big.json
echo "輸入大小: $(wc -c < big.json) bytes"
( ulimit -f 1; $AOS deliver f1 -f big.json; echo "deliver exit=$?" ) 2>&1 | tail -3
echo "inbox: [$(ls -1A f1/.aos/inst.tempd/ | tr '\n' ' ')]  (應無 .temp 殘留)"

echo
echo "=== 寫檔失敗時 aggregate 的殘留 ==="
rm -rf f2; mkdir -p f2; $AOS init f2 >/dev/null
cp big.json f2/.aos/inst.tempd/big.json
( ulimit -f 1; $AOS exec f2; echo "exec exit=$?" ) 2>&1 | tail -3
echo ".aos: [$(ls -1A f2/.aos | tr '\n' ' ')]"
echo "inbox: [$(ls -1A f2/.aos/inst.tempd/ | tr '\n' ' ')]  (投遞應保留，沒發布不該刪)"

echo
echo "=== 唯讀 inbox 時 deliver 的行為 ==="
rm -rf f3; mkdir -p f3; $AOS init f3 >/dev/null
chmod 500 f3/.aos/inst.tempd
printf '[{"argv":["/bin/true"]}]\n' > small.json
$AOS deliver f3 -f small.json; echo "deliver exit=$?"
chmod 700 f3/.aos/inst.tempd

echo
echo "=== 唯讀 .aos 時 exec 的行為 ==="
rm -rf f4; mkdir -p f4; $AOS init f4 >/dev/null
cp small.json f4/.aos/inst.tempd/a.json
chmod 500 f4/.aos
$AOS exec f4; echo "exec exit=$?"
chmod 700 f4/.aos
echo ".aos: [$(ls -1A f4/.aos | tr '\n' ' ')]"
