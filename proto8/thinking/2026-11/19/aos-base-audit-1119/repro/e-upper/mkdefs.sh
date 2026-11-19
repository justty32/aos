#!/bin/bash
# 準備實驗用定義夾：tree/defs/d1（A 版、無 hook）、tree/defs/d4（A 版、帶 std.hooks()），來源 repro/agent.py；並把 agent.py 放到 agentpy-src/ 給各腳本抄。經 clean 跑：bin/clean bash repro/mkdefs.sh（先跑 up.sh）
set -e
E=$HOME/.aos/scratch/aos-base-audit-1119/e-upper
mkdir -p $E/agentpy-src; cp $E/repro/agent.py $E/agentpy-src/agent.py
for d in d1 d4; do rm -rf $E/tree/defs/$d; mkdir -p $E/tree/defs/$d; cp $E/repro/agent.py $E/tree/defs/$d/; done
(cd $E/tree/defs/d1 && MARK=A python3 agent.py --write-defs >/dev/null)
(cd $E/tree/defs/d4 && MARK=A HOOKS=1 python3 agent.py --write-defs >/dev/null)
echo "defs ready"
