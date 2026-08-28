#!/bin/bash
R=/tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lead
AOS=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-aadc15218d3266528/build/bin/aos
cd "$R" || exit 1
mk() { rm -rf "$1"; mkdir -p "$1"; $AOS init "$1" >/dev/null; }
run() { $AOS exec "$1" >/dev/null 2>&1; printf "  %-46s exit=%s\n" "$2" "$?"; }

echo "=== §D-9 退出碼實測 ==="
mk e1; run e1 "沒有 inst.json（§A-4）"
mk e2; printf '[{"argv":["/bin/false"]}]\n' > e2/.aos/inst.json; run e2 "子行程回非零"
mk e3; printf '[{"argv":["/no/such/cmd"]}]\n' > e3/.aos/inst.json; run e3 "指令不存在"
mk e4; printf 'not json\n' > e4/.aos/inst.json; run e4 "整批解析失敗"
mk e5; printf '[{"argv":[{"$env":"NO_SUCH_VAR_XYZ"}]}]\n' > e5/.aos/inst.json; run e5 "resolve 失敗（\$env 缺變數）"
mk e6; printf '[{"argv":["/bin/true"],"exit":"/nonexistent-dir/x"}]\n' > e6/.aos/inst.json; run e6 "exit 檔寫不進去"
mk e7; printf '[{"argv":["/bin/true"],"stdout":"/nonexistent-dir/x"}]\n' > e7/.aos/inst.json; run e7 "重導向檔開不起來"
mk e8; printf '[{"argv":["/bin/true"]}]\n' > e8/.aos/inst.json.runi; run e8 ".runi 已存在"
mk e9; echo abc > e9/.aos/turn; printf '[{"argv":["/bin/true"]}]\n' > e9/.aos/inst.json; run e9 "turn 壞掉（回合其實跑完）"
rm -rf e10; mkdir -p e10; run e10 "不是世界（無 .aos）"
$AOS exec --loop >/dev/null 2>&1; echo "  用法錯誤（exec --loop 無值）              exit=$?"
$AOS nosuchcmd >/dev/null 2>&1; echo "  不存在的子命令                             exit=$?"

echo
echo "=== 檢查 e9 是否真的跑完了（.runi 不存在 = 回合正常收尾）==="
echo "  e9/.aos: [$(ls -1A e9/.aos | tr '\n' ' ')]"
