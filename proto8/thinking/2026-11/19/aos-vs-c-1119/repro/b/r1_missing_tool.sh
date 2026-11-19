#!/bin/bash
# r1: a tool path that does not exist compiles fine, agent_def check says no problems; at run time the tool is skipped (stderr warning only). Usage: r1_missing_tool.sh NEWDIR
source $(dirname $0)/common.sh; D=${1:?NEWDIR}; mkdir -p $D
mkdef $D/def "std=defs.std
defs.main(\"d\",\"s\",[defs.tool(\"x\", defs.home(\"/lib/tools/base/nope\")), std.pack(\"look\")],{\"model\":\"fake\"},std.fsm())"
(cd $D/def && python3 agent.py --compile >/dev/null; echo "compile exit $?")
echo "{\"tools\": {\"agent_def\": {\"path\": \"$AOS_HOME/lib/tools/agent/agent_def\"}}}" > $D/reg.json
AOS_WS=$D aos-tools --file $D/reg.json call agent_def "{\"op\":\"check\",\"path\":\"def\"}"
aos-tools --file $D/def/tools.json ls -l 2>&1 | grep -E "^x|warning"
