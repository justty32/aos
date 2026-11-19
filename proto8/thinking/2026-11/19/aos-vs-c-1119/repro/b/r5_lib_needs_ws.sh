#!/bin/bash
# r5: a defs.lib rooted under AOS_WS: the same compiled definition mounted with another -w silently loses the library tools. Usage: r5_lib_needs_ws.sh TREE DEF NAME (DEF compiled with my=defs.lib("my", defs.env("AOS_WS","/lib/my")))
source $(dirname $0)/common.sh; cd $1; mkdir -p $B/repro/otherws
aos-agent -d .stack ctl add -n $3 -w $B/repro/otherws $2 >/dev/null; sleep 2
$B/brain_tools.sh $1 $3 hi | tail -1; aos-daemon-ctl -d .stack ls | grep "^$3"
