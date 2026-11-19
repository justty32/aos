#!/bin/bash
# brain_tools.sh TREE NAME [MSG] - say MSG to NAME, wait answer, print sorted tool names the brain got + the answer head. Run after: source env2.sh (or env.sh)
T=$1; N=$2; M=${3:-hi}
cd $T
aos-agent -d .stack --target $N say "$M" >/dev/null
aos-agent -d .stack --target $N listen --timeout-s 20 | head -c 400; echo
python3 - "$T/.stack/procs/$N/think/request.json" <<"PY"
import json,sys
d=json.load(open(sys.argv[1]))["request"]
print("brain tools:", sorted(t["function"]["name"] for t in d.get("tools",[])))
PY
