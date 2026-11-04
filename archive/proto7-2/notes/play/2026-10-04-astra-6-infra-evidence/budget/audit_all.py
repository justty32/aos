#!/usr/bin/env python3
"""Run unchanged astra-5 independent auditor against all astra-6 budget snapshots.
Extract snapshots.tar.gz in each directory first when rerunning archived evidence.
"""
import json,sys,copy,tempfile,shutil,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'integration'))
from audit import audit
rows=[]
for batch in ('verified','extra','loop6','edges'):
    base=HERE/'crash'/batch
    for rec in json.loads((base/'snapshots.json').read_text()):
        r=audit(base/'snapshots'/rec['name'],rec['final']);r['batch']=batch;rows.append(r)
old=json.loads((HERE/'integration/results.json').read_text())
for prev in old['audits']:
    r=audit(prev['path'],prev['final']);r['batch']='integration';rows.append(r)
(HERE/'audits.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
assert all(r['ok'] for r in rows),[r for r in rows if not r['ok']]
source=next((HERE/'integration/snapshots').glob('*/clock-boundaries'))
neg=[]
for name in ('double-backend-count','bad-log-balance','duplicate-reserve','wrong-evidence-hash','missing-op'):
    with tempfile.TemporaryDirectory(prefix='astra6-budget-audit-negative-') as tmp:
        target=Path(tmp)/'budget';shutil.copytree(source,target)
        lp=target/'ledger.json';bp=target/'backend.json';L=json.loads(lp.read_text());b=json.loads(bp.read_text())
        if name=='double-backend-count':b['accepted']+=1;bp.write_text(json.dumps(b))
        if name=='bad-log-balance':L['log'][0]['available']+=1
        if name=='duplicate-reserve':L['log'].append(copy.deepcopy(L['log'][0]))
        if name=='wrong-evidence-hash':next(iter(L['ops'].values()))['settle']['evidence']='0'*64
        if name=='missing-op':L['ops'].pop(next(iter(L['ops'])))
        lp.write_text(json.dumps(L));r=audit(target,True);assert not r['ok'];neg.append(dict(mutation=name,detected=True,errors=r['errors']))
(HERE/'negative-controls.json').write_text(json.dumps(neg,ensure_ascii=False,indent=2))
summary=dict(snapshots=len(rows),transitions=sum(r['transitions'] for r in rows),passed=sum(r['ok'] for r in rows),negative_detected=len(neg),by_batch={b:dict(snapshots=sum(r['batch']==b for r in rows),transitions=sum(r['transitions'] for r in rows if r['batch']==b)) for b in ('verified','extra','loop6','edges','integration')})
(HERE/'audit-summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))
