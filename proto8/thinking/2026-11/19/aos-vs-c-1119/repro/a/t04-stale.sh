#!/bin/bash
# t04: incremental / dependency: compile base + derived, then change the library pack and base agent.py; who notices?
source ~/.aos/scratch/aos-vs-c-1119/env.sh
P=$HOME/.aos/scratch/aos-vs-c-1119/probe-a; W=$P/w02
echo "{\"tools\": {\"t1\": {\"path\": \"../tools/t1\"}}}" > $P/lib2/packs/p.json
sed -i "s/base system v[0-9]/base system v1/" $W/base/agent.py
(cd $W/base && python3 agent.py --compile >/dev/null); (cd $W/derived && python3 agent.py --compile >/dev/null)
echo "{\"tools\": {\"t1\": {\"path\": \"../tools/t1\"}, \"t2\": {\"path\": \"../tools/t2\"}}}" > $P/lib2/packs/p.json
sed -i "s/base system v1/base system v2/" $W/base/agent.py
echo "== after changing lib2 pack and base/agent.py (nothing recompiled):"
for d in base derived; do echo "-- $d tools.json has lib2_t2? $(grep -c lib2_t2 $W/$d/tools.json); system: $(head -1 $W/$d/system.txt)"; done
echo "-- agent_def check base: $(echo "{\"op\":\"check\",\"path\":\"$W/base\"}" | AOS_WS=$W python3 $AOS_HOME/lib/tools/agent/agent_def/_entry)"
echo "-- newer-than test (make-style): agent.py newer than tools.json? $( [ $W/base/agent.py -nt $W/base/tools.json ] && echo yes || echo no ); pack newer? $( [ $P/lib2/packs/p.json -nt $W/base/tools.json ] && echo yes || echo no )"
echo "== the only way to see it: dry-run and diff against the folder"
(cd $W/derived && python3 agent.py --dry-run) | python3 -c "
import json,sys,os
d=json.load(sys.stdin); W=sys.argv[1]
for n,v in d.items():
    p=os.path.join(W,n)
    if n=='README.md' or not os.path.exists(p): continue
    have=open(p).read(); want=v if isinstance(v,str) else json.dumps(v,ensure_ascii=False,indent=2)+'\n'
    if n=='_metainfo.json': continue
    print(n, 'same' if have==want else 'DIFFERS')
" $W/derived
echo "== recompile derived only (base folder not recompiled):"
(cd $W/derived && python3 agent.py --compile >/dev/null); echo "derived lib2_t2: $(grep -c lib2_t2 $W/derived/tools.json); derived system: $(head -1 $W/derived/system.txt); base system still: $(head -1 $W/base/system.txt)"
