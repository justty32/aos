#!/bin/bash
# probe-c: same failing tool call forever (needs probe-c/t1 tree up and endpoint fake-c-loop in its llms/def/kernel.json).
source ~/.aos/scratch/aos-vs-c-1119/env.sh
cd ~/.aos/scratch/aos-vs-c-1119/probe-c/t1/tree
aos-agent -d .stack ctl start loop1 >/dev/null 2>&1 || aos-agent -d .stack ctl add -n loop1 -w . agents/loop1 >/dev/null
aos-agent -d .stack --target loop1 say go >/dev/null; sleep 25
echo "glob calls so far: $(grep -c "\"name\": \"glob\"" .stack/procs/loop1/observed.jsonl)"; aos-daemon-ctl -d .stack ls | grep loop1
aos-agent -d .stack ctl stop loop1
