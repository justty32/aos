#!/bin/bash
# r2: a tool added to a dynamically linked pack after compiling, under the name of another tool of the agent, silently replaces it from the next brain call. Usage: r2_dynamic_silent_merge.sh TREE AGENT (AGENT compiled --dynamic from look+json+mailbox, no own tools.json)
source $(dirname $0)/common.sh; TREE=$1; AGENT=$2; P=$AOS_HOME/lib/packs/mailbox.json; cp $P $B/repro/mailbox.json.bak
python3 -c "import json;p=\"$P\";d=json.load(open(p));d[\"tools\"][\"glob\"]={\"path\":{\"\$env\":\"AOS_HOME\",\"\$path\":\"/lib/tools/base/peek_now_time\"}};json.dump(d,open(p,\"w\"))"
cd $TREE; aos-agent -d .stack -t $AGENT tools ls -l 2>/dev/null | grep ^glob | cut -f1,3,4
$B/brain_tools.sh $TREE $AGENT hi | head -1      # fake brain calls glob first: answer carries a timestamp
cp $B/repro/mailbox.json.bak $P
