#!/bin/bash
# 測 ctl set-def 之後 stack 那份 tools 仍疊在舊定義上：換到新定義後腦看到哪些工具、舊定義重生或被刪時這隻怎樣。經 clean 跑：bin/clean bash repro/e5_setdef_old_tools.sh
E=$HOME/.aos/scratch/aos-base-audit-1119/e-upper; cd $E/tree
mk() { rm -rf defs/$1; mkdir -p defs/$1; cp $E/agentpy-src/agent.py defs/$1/; (cd defs/$1 && MARK=$2 python3 agent.py --write-defs >/dev/null); }
mk old5 A; mk new5 B
timeout 60 aos-agent -d .stack ctl add -n e5 -w . defs/old5 >/dev/null
timeout 30 aos-agent -d .stack --target e5 tools add -n math2 $AOS_HOME/lib/tools/base/math 2>/dev/null >/dev/null
echo "== stack tools.json:"; cat .stack/procs/e5/tools.json; echo
echo "== set-def e5 -> defs/new5 (B: mailbox+look, no gadgets)"
timeout 90 aos-agent -d .stack ctl set-def e5 defs/new5 2>&1 | fold -w 220
echo "== tools e5 now sees (names):"; timeout 30 aos-agent -d .stack --target e5 tools ls 2>/dev/null | cut -f1 | tr "\n" " "; echo
echo "== system/llm e5 now uses:"; timeout 30 aos-agent -d .stack --target e5 system get 2>/dev/null | head -1; timeout 30 aos-agent -d .stack --target e5 llm 2>/dev/null | tr "\n" " "; echo
echo "== ask it: fake brain calls peek_now_time if offered"
L=$(timeout 30 aos-agent -d .stack --target e5 say q1); timeout 40 aos-agent -d .stack --target e5 listen --timeout-s 30 2>&1 | tail -1
echo "== now the old definition folder is deleted (user cleans up defs/old5)"
rm -rf defs/old5
L=$(timeout 30 aos-agent -d .stack --target e5 say q2); timeout 40 aos-agent -d .stack --target e5 listen --timeout-s 25 2>&1 | tail -2
sleep 2
timeout 30 aos-daemon-ctl -d .stack ls | grep e5
tail -4 .stack/procs/e5/stderr.txt | cut -c1-300
echo "== cleanup"; timeout 60 aos-agent -d .stack ctl rm --purge e5 >/dev/null 2>&1 || timeout 60 aos-agent -d .stack ctl rm e5; rm -rf defs/new5
