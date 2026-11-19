#!/bin/bash
# probe-c: agent.py with an unreachable state whose cell file is missing, a tool path that does not exist,
# and system text naming tools it does not have -> --compile exit 0, agent_def check {"problems": []}.
source ~/.aos/scratch/aos-vs-c-1119/env.sh
P=~/.aos/scratch/aos-vs-c-1119/probe-c/lint; mkdir -p $P/st; cd $P
echo "{\"op\":\"check\",\"path\":\"$P/bad1\"}" | AOS_WS=$P aos-exec --stack st/ad $AOS_HOME/lib/tools/agent/agent_def; echo "agent_def check exit=$?"
(cd bad1 && python3 agent.py --dry-run >/dev/null; echo "compile dry-run exit=$?")
grep -n "orphan\|nosuchcell\|ghost\|web_fetch" bad1/agent.py
(cd bad1 && aos-tools ls >/dev/null; echo "aos-tools ls exit=$? (warning only)")
python3 -c "import json;print(\"longtool description chars:\", len(json.load(open(\"$P/longtool/_tooldef.json\"))[\"description\"]))"
