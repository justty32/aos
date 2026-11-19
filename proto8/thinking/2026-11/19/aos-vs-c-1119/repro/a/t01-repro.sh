#!/bin/bash
# t01: same agent.py compiled twice / under another AOS_HOME spelling / another folder: byte-identical?
source ~/.aos/scratch/aos-vs-c-1119/env.sh
P=~/.aos/scratch/aos-vs-c-1119/probe-a; W=$P/w01; rm -rf $W; mkdir -p $W
cp -r $AOS_HOME/templates/agent-python $W/a1
cd $W/a1 && python3 agent.py --compile >/dev/null && (cd $W/a1 && sha256sum $(ls | grep -v agent.py) > $W/sum1)
python3 agent.py --compile >/dev/null && sha256sum $(ls | grep -v agent.py) > $W/sum2
echo "== compile twice same folder:"; diff $W/sum1 $W/sum2 && echo identical
ln -sfn $AOS_HOME $W/otherhome
AOS_HOME=$W/otherhome python3 agent.py --dry-run > $W/dry-otherhome.json
python3 agent.py --dry-run > $W/dry-home.json
echo "== other AOS_HOME:"; diff $W/dry-home.json $W/dry-otherhome.json && echo identical
cp -r $W/a1 $W/renamed; cd $W/renamed; python3 agent.py --dry-run > $W/dry-renamed.json
echo "== other folder:"; diff $W/dry-home.json $W/dry-renamed.json && echo identical
echo "== absolute paths / host / time in output:"; grep -n "/home/\|$(hostname)\|2026" $W/dry-home.json || echo "none"
