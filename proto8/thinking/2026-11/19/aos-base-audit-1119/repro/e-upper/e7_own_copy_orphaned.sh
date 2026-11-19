#!/bin/bash
# 測 stack 裡「自己那份」是照定義 interfaces.json 宣告的檔名去找：重生把 system 改成 by_hand("prompt.txt") 後，agent 先前 system set 的自己那份會不會悄悄失效。經 clean 跑：bin/clean bash repro/e7_own_copy_orphaned.sh
E=$HOME/.aos/scratch/aos-base-audit-1119/e-upper; cd $E/tree
rm -rf defs/d7; mkdir -p defs/d7; cp $E/agentpy-src/agent.py defs/d7/; (cd defs/d7 && MARK=A python3 agent.py --write-defs >/dev/null)
timeout 60 aos-agent -d .stack ctl add -n e7 -w . defs/d7 >/dev/null
echo "MY-OWN-SYSTEM" | timeout 30 aos-agent -d .stack --target e7 system set - 2>/dev/null
echo "-- system in effect:"; timeout 30 aos-agent -d .stack --target e7 system get 2>&1 | head -2
echo "== regen with SYSTEM = by_hand(prompt.txt)"
echo "HAND-WRITTEN PROMPT" > defs/d7/prompt.txt
(cd defs/d7 && MARK=A SYSFILE=prompt.txt python3 agent.py --write-defs | tail -1)
grep -o "\"system\": *\"[^\"]*\"" defs/d7/interfaces.json
echo "-- system in effect now:"; timeout 30 aos-agent -d .stack --target e7 system get 2>&1 | head -3
echo "-- own copy still in stack:"; cat .stack/procs/e7/system.txt
L=$(timeout 30 aos-agent -d .stack --target e7 say hi); timeout 30 aos-agent -d .stack --target e7 listen --timeout-s 20 >/dev/null 2>&1
python3 -c "import json;r=json.load(open(\".stack/procs/e7/think/request.json\"));print(\"-- brain got system:\", r[\"request\"][\"messages\"][0])"
timeout 60 aos-agent -d .stack ctl rm --purge e7 >/dev/null 2>&1; rm -rf defs/d7
