#!/bin/bash
# 起 e-upper 暫存樹（start-api 抄本、假腦）：根 daemon＋llm kernel，pid 記在 $E/pids.txt；要經 clean 跑：bin/clean bash repro/up.sh
set -e
E=$HOME/.aos/scratch/aos-base-audit-1119/e-upper
T=$E/tree
if [ ! -d "$T" ]; then
  cp -r "$AOS_HOME/templates/start-api" "$T"
fi
cd "$T"
setsid aos-exec root > $E/root.log 2>&1 < /dev/null &
echo "root $!" >> $E/pids.txt
for i in $(seq 100); do [ -f .stack/state.json ] && break; sleep 0.1; done
cd llms
setsid aos-exec --stack stacks/llm def > $E/llm.log 2>&1 < /dev/null &
echo "llm $!" >> $E/pids.txt
for i in $(seq 100); do [ -f stacks/llm/state.json ] && break; sleep 0.1; done
echo up
