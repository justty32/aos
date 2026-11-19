#!/bin/bash
# 測兩隻 agent（a1、a3）指同一個定義夾 defs/d1：一隻用 tools add／system set 改自己，另一隻看不看得到；再看重生、agent_def 那種直接改定義夾的影響。經 clean 跑：bin/clean bash repro/e3_shared_def.sh
E=$HOME/.aos/scratch/aos-base-audit-1119/e-upper; cd $E/tree
timeout 60 aos-agent -d .stack ctl add -n a1 -w . defs/d1 >/dev/null 2>&1
timeout 60 aos-agent -d .stack ctl add -n a3 -w . defs/d1 >/dev/null 2>&1
echo "== a1 adds math to itself, sets its own system"
timeout 30 aos-agent -d .stack --target a1 tools add -n math2 $AOS_HOME/lib/tools/base/math
echo "MINE-ONLY" | timeout 30 aos-agent -d .stack --target a1 system set - 2>&1 | tail -1
echo "-- a1 tools:"; timeout 30 aos-agent -d .stack --target a1 tools ls | tr "\n" " "; echo
echo "-- a3 tools:"; timeout 30 aos-agent -d .stack --target a3 tools ls | tr "\n" " "; echo
echo "-- def folder changed?"; git -C . status --short 2>/dev/null | head -3; ls defs/d1; cat defs/d1/system.txt | head -1
echo "== regen d1 to B: both see it"
(cd defs/d1 && MARK=B python3 agent.py --write-defs >/dev/null)
echo "-- a1 tools:"; timeout 30 aos-agent -d .stack --target a1 tools ls | tr "\n" " "; echo
echo "-- a3 tools:"; timeout 30 aos-agent -d .stack --target a3 tools ls | tr "\n" " "; echo
(cd defs/d1 && MARK=A python3 agent.py --write-defs >/dev/null)
timeout 30 aos-agent -d .stack --target a1 tools reset -y >/dev/null 2>&1
for n in a1 a3; do timeout 60 aos-agent -d .stack ctl rm --purge $n >/dev/null 2>&1; done
