"""Run copied astra-5/6 original 41+9 crash scenarios with unchanged assertions.
Rerun: python3 proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/pack4/rerun_crash.py
The only source edits are docstrings/temp prefix, recorded in provenance.json.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess as sp
import sys
import tempfile
HERE=Path(__file__).resolve().parent
TOP=next(p for p in HERE.parents if p.name=='proto7-2')
def main():
    if os.environ.get('PACK4_SCOPED')!='1':
        return sp.call(['systemd-run','--user','--scope','-q','-p','TasksMax=800','-p','RuntimeMaxSec=1800',
          '/usr/bin/env','PACK4_SCOPED=1','PYTHONDONTWRITEBYTECODE=1',sys.executable,str(Path(__file__).resolve())],cwd=TOP.parent)
    rows=[]
    for name,script,count in [('verified','run_probes.py',41),('extra','run_extra.py',9)]:
        with tempfile.TemporaryDirectory(prefix='astra7-pack4-rerun-') as tmp:
            env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',QA_OUTPUT=tmp)
            log=HERE/'crash'/(name+'-run.log')
            with log.open('w') as out:
                r=sp.run([sys.executable,str(HERE/'crash'/script)],cwd=TOP.parent,env=env,stdout=out,stderr=sp.STDOUT,timeout=300)
            result=json.loads((Path(tmp)/'results.json').read_text())
            assert len(result)==count and r.returncode==0,(r.returncode,len(result))
            dest=HERE/'crash'/name
            if dest.exists():shutil.rmtree(dest)
            shutil.copytree(tmp,dest)
            rows.append(dict(batch=name,cases=count,passed=sum(x['ok'] for x in result),script=script))
    (HERE/'crash-rerun.json').write_text(json.dumps(rows,indent=1)+'\n');print(rows)
    return int(any(r['cases']!=r['passed'] for r in rows))
if __name__=='__main__':sys.exit(main())
