#!/bin/bash
# mk.sh NAME BODYFILE: copy agent-python to probe-a/w02/NAME (must not exist) and replace the part under "# ---- your agent" with BODYFILE
source ~/.aos/scratch/aos-vs-c-1119/env.sh
W=$HOME/.aos/scratch/aos-vs-c-1119/probe-a/w02; mkdir -p $W
[ -e "$W/$1" ] && { echo "exists: $W/$1"; exit 1; }
cp -r $AOS_HOME/templates/agent-python "$W/$1"
python3 - "$W/$1/agent.py" "$2" <<PY
import sys
src=open(sys.argv[1]).read(); body=open(sys.argv[2]).read()
head=src.split("# ---- your agent")[0]
open(sys.argv[1],"w").write(head+"# ---- your agent: change the lines below ----\n"+body)
PY
