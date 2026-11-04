#!/bin/sh
# 用法：make_stuck.sh <node 路徑>　故意讓 node 問 AI 問到一半被打斷（模擬當機），之後心跳在背景重開。
set -e
N="$1"; UP="python3 /home/lorkhan/repo/simple_tools/aos-wt/ST2/proto7-2/modules/up/aos7-up"
python3 -c "import json,sys;p=sys.argv[1]+'/.aos/up.json';d=json.load(open(p));d['fake_delay']=30;json.dump(d,open(p,'w'))" "$N"
$UP ask "$N" '幫我寫一首短詩' --wait 4 || true
$UP stop "$N" >/dev/null
$UP "$N" -d >/dev/null
echo "好了：剛剛模擬了一次當機（問 AI 問到一半被打斷），心跳已在背景重開。現在用 status 看看。"
