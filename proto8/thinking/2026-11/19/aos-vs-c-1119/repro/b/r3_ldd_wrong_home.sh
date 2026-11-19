#!/bin/bash
# r3: aos-agent tools ls -l resolves AOS_HOME with the CLI environment, not with the environment of the agent; observed.jsonl shows what really ran. Usage: r3_ldd_wrong_home.sh TREE AGENT (tree started under env.sh; AGENT added with --envs AOS_HOME=probe-b/home2 and asked once)
source $HOME/.aos/scratch/aos-vs-c-1119/env.sh; cd $1
echo "tools ls says: $(aos-agent -d .stack -t $2 tools ls -l 2>/dev/null | grep ^glob | cut -f3)"
echo "it ran:        $(grep "\"tool\"" .stack/procs/$2/observed.jsonl | tail -1 | python3 -c "import json,sys;print(json.loads(sys.stdin.read())[\"def\"])")"
