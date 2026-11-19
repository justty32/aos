#!/bin/bash
# t02: compile each broken variant (w02/<name>), show exit code + stderr; then agent_def check on the ones that compiled
source ~/.aos/scratch/aos-vs-c-1119/env.sh
W=$HOME/.aos/scratch/aos-vs-c-1119/probe-a/w02
for e in "$@"; do
  echo "=== $e --compile"; (cd $W/$e && python3 agent.py --compile 2>&1 >/dev/null | tail -6; echo "exit ${PIPESTATUS[0]}")
done
