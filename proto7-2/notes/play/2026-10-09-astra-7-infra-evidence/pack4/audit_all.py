#!/usr/bin/env python3
"""Run the byte-identical astra-6 auditor on this run's new snapshots plus five negative controls.
Rerun: python3 proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/pack4/audit_all.py
Reads loose snapshots or their local tar.gz archives. Uses only Python standard library.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess as sp
import sys
import tarfile
import tempfile
sys.dont_write_bytecode=True
from audit import audit
HERE=Path(__file__).resolve().parent
def write(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=1)+'\n')
def main():
    if os.environ.get('PACK4_SCOPED')!='1':
        return sp.call(['systemd-run','--user','--scope','-q','-p','TasksMax=800','-p','RuntimeMaxSec=1800',
          '/usr/bin/env','PACK4_SCOPED=1','PYTHONDONTWRITEBYTECODE=1',sys.executable,str(Path(__file__).resolve())])
    rows=[];negative=[];extracted={}
    with tempfile.TemporaryDirectory(prefix='astra7-pack4-audit-') as temp:
        root=Path(temp)
        def directory(p):
            if p.exists():return p
            for base in [HERE/'crash/verified',HERE/'crash/extra',HERE]:
                if p.is_relative_to(base):
                    archive=base/('cases.tar.gz' if p.is_relative_to(HERE/'cases') else 'snapshots.tar.gz')
                    if not archive.exists():continue
                    if archive not in extracted:
                        dst=root/('extract-'+str(len(extracted)));dst.mkdir()
                        with tarfile.open(archive) as t:t.extractall(dst,filter='data')
                        extracted[archive]=dst
                    candidate=extracted[archive]/p.relative_to(base)
                    if candidate.exists():return candidate
            raise FileNotFoundError(p)
        for batch,base in [('verified',HERE/'crash/verified'),('extra',HERE/'crash/extra'),('new',HERE)]:
            for rec in json.loads((base/'snapshots.json').read_text()):
                p=base/'snapshots'/rec['name']
                r=audit(directory(p),rec['final']);r['path']=str(p.relative_to(HERE));r['batch']=batch;rows.append(r)
        for name in ['tmp-frame','tmp-gateway']:
            p=HERE/'cases'/name/'budget/demo'
            r=audit(directory(p),True);r.update(path=str(p.relative_to(HERE)),batch='tmp');rows.append(r)
        source=directory(HERE/'snapshots/weighted-final')
        for mutation in ['double-backend-count','bad-log-balance','duplicate-reserve','wrong-evidence-hash','missing-op']:
            target=root/mutation;shutil.copytree(source,target)
            lp=target/'ledger.json';bp=target/'backend.json';L=json.loads(lp.read_text());B=json.loads(bp.read_text())
            if mutation=='double-backend-count':B['accepted']+=1;write(bp,B)
            if mutation=='bad-log-balance':L['log'][0]['available']+=1
            if mutation=='duplicate-reserve':L['log'].append(copy.deepcopy(L['log'][0]))
            if mutation=='wrong-evidence-hash':next(iter(L['ops'].values()))['settle']['evidence']='0'*64
            if mutation=='missing-op':L['ops'].pop(next(iter(L['ops'])))
            write(lp,L);r=audit(target,True)
            negative.append(dict(scenario=mutation,injection='mutated independent snapshot copy',
                assertion='auditor rejects corruption',pass_=not r['ok'],errors=r['errors']))
        write(HERE/'audits.json',rows);write(HERE/'negative-controls.json',negative)
        summary=dict(snapshots=len(rows),passed=sum(r['ok'] for r in rows),transitions=sum(r['transitions'] for r in rows),
            negative_controls=len(negative),negative_detected=sum(r['pass_'] for r in negative),
            auditor_sha256=hashlib.sha256((HERE/'audit.py').read_bytes()).hexdigest(),
            batches={b:dict(snapshots=sum(r['batch']==b for r in rows),passed=sum(r['ok'] for r in rows if r['batch']==b)) for b in ['verified','extra','new','tmp']})
        write(HERE/'audit-summary.json',summary);print(json.dumps(summary))
    write(HERE/'audit-cleanup.json',{'root':temp,'root_removed':not Path(temp).exists()})
    return int(not all(r['ok'] for r in rows) or not all(r['pass_'] for r in negative))
if __name__=='__main__':sys.exit(main())
