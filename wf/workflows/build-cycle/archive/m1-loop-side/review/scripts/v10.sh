#!/bin/bash
# 複驗 smoke-notes.md 裡的 deliver 段落是否真的可重現
R=/tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lead
AOS=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-aadc15218d3266528/build/bin/aos
cd "$R" || exit 1
rm -rf S1; mkdir -p S1; cd S1 || exit 1
$AOS init . ; echo "[exit $?]"
printf '{"argv":["touch","a"]}' | $AOS deliver ; echo "[exit $?]"
printf '[{"argv":["touch","c"]},{"argv":["touch","d"]}]' > batch.json
$AOS deliver . -f batch.json ; echo "[exit $?]"
$AOS deliver . -f /dev/null ; echo "[exit $?]"
printf 'not json' | $AOS deliver . ; echo "[exit $?]"
printf '{"argv":["touch","a"],"nope":1}' | $AOS deliver . ; echo "[exit $?]"
printf '[{"argv":["touch","a"]},{"argv":[]}]' | $AOS deliver . ; echo "[exit $?]"
$AOS deliver . . -f batch.json ; echo "[exit $?]"
echo "--- inbox ---"; ls -1 .aos/inst.tempd/
$AOS exec . ; echo "[exit $?]"
echo "--- 事後 ---"; ls -1a .aos/
