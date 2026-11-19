#!/bin/bash
# t06: what --compile and agent_def check let through, and when it blows up (fake brain). Needs w02/{e2,e6,e7} from mk.sh + bodies/.
source ~/.aos/scratch/aos-vs-c-1119/env.sh
P=$HOME/.aos/scratch/aos-vs-c-1119/probe-a; W=$P/w02; D=$P/run2
for e in e2 e6 e7; do (cd $W/$e && python3 agent.py --compile >/dev/null && echo "$e compile ok"); echo "$e check: $(echo "{\"op\":\"check\",\"path\":\"$W/$e\"}" | AOS_WS=$W python3 $AOS_HOME/lib/tools/agent/agent_def/_entry)"; done
bash $HOME/.aos/scratch/aos-vs-c-1119/up.sh $D >/dev/null; cd $D/tree
for e in e2 e6 e7; do aos-agent -d .stack ctl add -n $e -w . $W/$e >/dev/null 2>&1; done; sleep 1
for e in e2 e6 e7; do aos-agent -d .stack --target $e say hi >/dev/null 2>&1; done; sleep 8
for e in e2 e6 e7; do echo "== $e: $(aos-agent -d .stack --target $e ctl state 2>&1 | grep -E "^(state|tools)" | cut -c1-160 | tr "\n" " ")"; grep -E "error|warning" .stack/procs/$e/stderr.txt | sort -u | head -2; done
bash $HOME/.aos/scratch/aos-vs-c-1119/down.sh $D >/dev/null
