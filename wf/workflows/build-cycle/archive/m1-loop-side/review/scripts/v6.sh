#!/bin/bash
R=/tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lead
AOS=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-aadc15218d3266528/build/bin/aos
cd "$R" || exit 1

echo "=== 超大批次：5000 筆 inst ==="
python3 -c "
import json
print(json.dumps([{'argv':['/bin/true']} for _ in range(5000)]))" > huge.json
echo "輸入 $(wc -c < huge.json) bytes"
rm -rf X1; mkdir -p X1; $AOS init X1 >/dev/null
time $AOS deliver X1 -f huge.json
echo "投遞檔大小: $(wc -c < X1/.aos/inst.tempd/*.json)"
time $AOS exec X1
echo "exec exit=$?  turn=$(cat X1/.aos/turn)"

echo
echo "=== 單筆超長 argv（8MB）==="
python3 -c "
import json
print(json.dumps([{'argv':['/bin/true','A'*8000000]}]))" > wide.json
rm -rf X2; mkdir -p X2; $AOS init X2 >/dev/null
$AOS deliver X2 -f wide.json; echo "deliver exit=$?"
$AOS exec X2 2>&1 | head -2; echo "exec exit=${PIPESTATUS[0]}"

echo
echo "=== inbox 混入目錄與 FIFO ==="
rm -rf X3; mkdir -p X3; $AOS init X3 >/dev/null
mkdir X3/.aos/inst.tempd/adir.json
mkfifo X3/.aos/inst.tempd/afifo.json 2>/dev/null && echo "(fifo 建好)"
ln -s /etc/passwd X3/.aos/inst.tempd/alink.json
ln -s /no/such/target X3/.aos/inst.tempd/dead.json
printf '[{"argv":["/bin/true"]}]\n' > X3/.aos/inst.tempd/ok.json
timeout 20 $AOS exec X3 2>&1 | head -10; echo "exec exit=$?"
echo "inbox: [$(ls -1A X3/.aos/inst.tempd/ | tr '\n' ' ')]"
