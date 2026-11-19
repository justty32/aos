#!/bin/bash
# probe-c minimal agent unit test: needs the probe-c/t1 tree up (up.sh) and endpoint fake-c-test in its llms/def/kernel.json
source ~/.aos/scratch/aos-vs-c-1119/env.sh
T=~/.aos/scratch/aos-vs-c-1119/probe-c/t1/tree; cd $T
rm -rf agents/ut; cp -r $AOS_HOME/templates/agent-python agents/ut
python3 - agents/ut/agent.py <<PY
import sys; p=sys.argv[1]; s=open(p).read()
s=s.replace("TOOLS = [std.pack(\"look\"), std.pack(\"mailbox\"), std.pack(\"json\")]", "TOOLS = [std.pack(\"gadgets\"), std.pack(\"mailbox\")]")
s=s.replace("LLM = {} ", "LLM = {\"model\": \"fake-c-test\"} ")
open(p,"w").write(s)
PY
(cd agents/ut && python3 agent.py --compile >/dev/null) || { echo FAIL compile; exit 1; }
aos-agent -d .stack ctl rm ut >/dev/null 2>&1
aos-agent -d .stack ctl add -n ut -w . agents/ut >/dev/null
aos-agent -d .stack --target ut say "what is 6*7?" >/dev/null
OUT=$(aos-agent -d .stack --target ut listen --timeout-s 30)
H=.stack/procs/ut/history.jsonl
python3 - "$OUT" $H <<PY
import json,sys
out=sys.argv[1]; hist=[json.loads(l) for l in open(sys.argv[2])]
calls=[c["function"]["name"] for m in hist for c in (m.get("tool_calls") or [])]
tool_out=[m["content"] for m in hist if m.get("role")=="tool"]
ok = "42" in out and calls==["math"] and any("42" in t for t in tool_out)
print("PASS" if ok else "FAIL", "| reply:", out.strip().splitlines()[-1][:80], "| calls:", calls, "| tool said:", [t[:40] for t in tool_out])
sys.exit(0 if ok else 1)
PY
R=$?
aos-agent -d .stack ctl stop ut >/dev/null 2>&1
exit $R
