#!/bin/bash
# probe-c: tar a compiled definition, unpack it under another AOS_HOME (a copy with glob removed from look.json).
P=~/.aos/scratch/aos-vs-c-1119/probe-c/pack
[ -d $P/home2 ] || { cp -r ~/.aos/scratch/aos-vs-c-1119/src/proto8 $P/home2; python3 -c "
import json; p=\"$P/home2/lib/packs/look.json\"; d=json.load(open(p)); del d[\"tools\"][\"glob\"]; json.dump(d,open(p,\"w\"),indent=2)"; }
rm -rf $P/elsewhere; mkdir -p $P/elsewhere/ws; cd $P/elsewhere/ws; tar xzf $P/pk.tgz
for v in $(compgen -e | grep "^AOS_"); do unset "$v"; done
export AOS_HOME=$P/home2 PATH=$P/home2/bin:$PATH PYTHONDONTWRITEBYTECODE=1 AOS_WS=$P/elsewhere/ws
cd pk; aos-tools ls 2>&1 | cut -c1-120; python3 agent.py --compile 2>&1 | tail -1
