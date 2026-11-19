# common.sh: shared paths and helpers for the probe-b repro scripts (aos-vs-c-1119).
# common.sh - probe-b repro helpers: private AOS_HOME copy (home2) so std can be changed safely.
B=$HOME/.aos/scratch/aos-vs-c-1119/probe-b
source $B/env2.sh
mkdef(){ # mkdef NEWDIR "python lines after the setup lines" (NEWDIR must not exist yet)
  [ -e "$1" ] && { echo "$1 exists; pick a new dir"; exit 1; }
  cp -r $AOS_HOME/templates/agent-python "$1"
  { sed -n "1,/^# ---- your agent/p" $AOS_HOME/templates/agent-python/agent.py; printf "%s\n" "$2"; } > "$1/agent.py"; }
