#!/usr/bin/env python3
import json
from pathlib import Path
from audit import audit
HERE=Path(__file__).resolve().parent
results=[]
for batch in ('verified','extra'):
    source=HERE.parent/'budget-crash'/batch
    manifest=json.loads((source/'snapshots.json').read_text())
    results.extend(audit(source/'snapshots'/x['name'],x['final']) for x in manifest)
(HERE/'crash-audits.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
print(json.dumps({'snapshots':len(results),'passed':sum(r['ok'] for r in results),'transitions':sum(r.get('transitions',0) for r in results),'failed':[r for r in results if not r['ok']]},ensure_ascii=False,indent=2))
