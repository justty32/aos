#!/bin/bash
# t03: "conditional compile" by environment: agent.py reads os.environ; is there a -D? does --dry-run show it?
source ~/.aos/scratch/aos-vs-c-1119/env.sh
cd $HOME/.aos/scratch/aos-vs-c-1119/probe-a/w02/c1
python3 agent.py --dry-run | python3 -c "import json,sys; d=json.load(sys.stdin); print(sorted(d[\"tools.json\"][\"tools\"]), d[\"llm.json\"][\"model\"])"
WITH_SHELL=1 MODEL=luna python3 agent.py --dry-run | python3 -c "import json,sys; d=json.load(sys.stdin); print(sorted(d[\"tools.json\"][\"tools\"]), d[\"llm.json\"][\"model\"])"
echo "== -D flag:"; python3 agent.py --compile -DWITH_SHELL=1 2>&1; echo "exit $?"
echo "== does output record the env it was built with?"; WITH_SHELL=1 python3 agent.py --dry-run | grep -c WITH_SHELL
