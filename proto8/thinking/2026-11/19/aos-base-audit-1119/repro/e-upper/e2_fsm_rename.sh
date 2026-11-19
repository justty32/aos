#!/bin/bash
# 測 agent.py 重生把狀態機的格改名（idle→rest）時，正在跑、停在 idle 的 agent（有／沒有 --auto-restart）會怎樣；經 clean 跑：bin/clean bash repro/e2_fsm_rename.sh
E=$HOME/.aos/scratch/aos-base-audit-1119/e-upper; cd $E/tree
for n in d2; do rm -rf defs/$n; mkdir -p defs/$n; cp $E/agentpy-src/agent.py defs/$n/; (cd defs/$n && MARK=A python3 agent.py --write-defs >/dev/null); done
timeout 60 aos-agent -d .stack ctl add -n e2a -w . defs/d2 >/dev/null
timeout 60 aos-agent -d .stack ctl add -n e2b --auto-restart -w . defs/d2 >/dev/null
sleep 2
echo "== before"; cat .stack/procs/e2a/stage.txt .stack/procs/e2b/stage.txt
(cd defs/d2 && MARK=A FSMV=renamed python3 agent.py --write-defs >/dev/null)
sleep 15
echo "== 15s after regen with renamed states"
timeout 30 aos-daemon-ctl -d .stack ls | grep e2
python3 - <<'PY'
import json; d=json.load(open(".stack/procs_state.json"))["procs"]
for n in ("e2a","e2b"): print(n, {k: d[n].get(k) for k in ("phase","code","reason")})
PY
echo "== stderr of e2a (tail)"; tail -3 .stack/procs/e2a/stderr.txt 2>/dev/null
tail -5 $E/root.log | cut -c1-300
echo "== does ctl start revive it?"; timeout 30 aos-agent -d .stack ctl start e2a 2>&1 | tail -2; sleep 3; timeout 30 aos-daemon-ctl -d .stack ls | grep e2a
echo "== cleanup"; timeout 60 aos-agent -d .stack ctl rm e2a >/dev/null 2>&1; timeout 60 aos-agent -d .stack ctl rm e2b >/dev/null 2>&1; timeout 30 aos-daemon-ctl -d .stack ls | grep e2 || echo "e2 rows gone"
