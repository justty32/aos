#!/bin/bash
# r4: renaming one fsm cell under AOS_HOME (what an upgrade + install.py orphan delete can do) stops every running agent of that home at its next tick; no version recorded anywhere. Usage: r4_home_change_kills.sh TREE (tree with agents on home2)
source $(dirname $0)/common.sh; F=$AOS_HOME/templates/agent-fsm
mv $F/idle.py $F/idle_renamed.py; sleep 3; aos-daemon-ctl -d $1/.stack ls; mv $F/idle_renamed.py $F/idle.py
grep -rln "\"version\"" $AOS_HOME/lib/packs $AOS_HOME/lib/tools/base $AOS_HOME/templates/agent-python || echo "no version field in packs, tools, agent-python"
