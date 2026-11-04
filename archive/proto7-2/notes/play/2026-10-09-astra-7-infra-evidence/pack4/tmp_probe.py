#!/usr/bin/env python3
"""C8-03 repeated SIGKILL at actual product pre-publication points; stdlib only.
Rerun: python3 proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/pack4/tmp_probe.py
Each scenario kills six writers, restarts the responsible sweeper, tests a live writer.
"""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess as sp
import sys
import tempfile
import traceback
import probe as h

HERE=h.HERE
ROWS=[]

def tmpfiles(d): return sorted(p.name for p in d.glob('.*.tmp.*'))
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def step_env(x,extra=None):
    return dict({'AOS7_ROOT':str(x.root),'AOS7_NODE':str(x.n),'AOS7_NODE_ID':'n',
       'AOS7_TASK':str(x.n/'.aos/tasks/interp'),'AOS7_TID':'interp','AOS7_RUN':'1'},**(extra or {}))
def step(x,extra=None):return h.pop([h.PY,h.STEP,'run','jobs/j'],x.n,step_env(x,extra))
def result_args(x):
    return [h.PY,h.TOP/'packs/step/bin/aos7-step-result','--result','jobs/j/results/call/fixed.json',
      '--job','j','--inst','fixed','--step','call','--request','fixed-r','--attempt','fixed-r-a1','--',h.PY,'-c','pass']
def install_wait(x):
    h.write(x.n/'.aos/round.json',{'round':5,'open':False})
    h.write(x.jd/'steps.json',{'job':'j','start':'wait','steps':{
      'wait':{'wait':{'exists':'never-created'},'then':'done'},'done':{'end':'ok'}}})

def frame_case():
    x=h.Node('tmp-frame',True);install_wait(x);kills=[]
    for i in range(6):
        q=step(x,{'AOS7_TEST_HOOKS':str(h.HOOK),'AOS7_TEST_CRASH':'tmp:frame.json'})
        assert q.wait(10)==-9
        names=tmpfiles(x.jd);assert len(names)==1,names
        tmp=x.jd/names[0];kills.append(dict(pid=q.pid,rc=q.returncode,tmp=names,sha256=digest(tmp),content=h.read(tmp)))
        assert names[0].endswith('.'+str(q.pid))
    # A real budget --out writer is active in the job directory while step starts and sweeps.
    # This avoids running two interpreters on one job (explicit misuse in step spec §7).
    ledger=h.pop([h.PY,h.BUDGET,'ledger','budget/demo'],x.n)
    r=x.bcli('call','live');assert r['rc']==0,r
    live=h.pop([h.PY,h.BUDGET,'call','budget/demo','--holder','api','--request','live','--out','jobs/j/live.json'],x.n,
      {'AOS7_TEST_HOOKS':str(h.HOOK),'AOS7_TEST_HANG':'tmp:live.json'})
    path=x.jd/('.live.json.tmp.%s'%live.pid)
    h.wait(path.exists,'live job-folder tmp');before=digest(path)
    sweeper=step(x);h.wait(lambda:x.frame().get('phase')=='running','step recovery')
    remaining=tmpfiles(x.jd)
    assert remaining==[path.name] and live.poll() is None and digest(path)==before,remaining
    h.stop(live);h.stop(sweeper)
    sweeper=step(x);h.wait(lambda:not tmpfiles(x.jd),'dead live writer swept')
    h.stop(sweeper);h.stop(ledger)
    return dict(injection=kills,assertions='six real frame pre-rename kills; <=1 temp; live budget output writer preserved by interpreter sweep',
      live_writer={'pid':live.pid,'before_sha':before,'preserved_sha':before,'remaining_during_live':remaining},
      recovered_tmp_count=len(tmpfiles(x.jd)),evidence=x.evidence())

def results_case():
    x=h.Node('tmp-results');install_wait(x);d=x.jd/'results/call';kills=[]
    def writer(i):
        marker=x.n/('link-%s.json'%i)
        q=h.pop(result_args(x),x.n,{'PYTHONPATH':str(HERE/'linkhook'),'PACK4_LINK_MARKER':str(marker)})
        rec=h.wait(lambda:h.read(marker),'pre-link marker')
        assert not (d/'fixed.json').exists() and Path(x.n/rec['src']).exists()
        return q,marker,rec
    for i in range(6):
        q,marker,rec=writer(i);h.stop(q);assert q.returncode==-9
        kills.append(dict(**rec,rc=q.returncode,tmp_count=len(tmpfiles(d))))
    live,marker,rec=writer('live');path=x.n/rec['src'];before=digest(path)
    sweeper=step(x);h.wait(lambda:x.frame().get('phase')=='running','step sweeps results')
    remaining=tmpfiles(d)
    assert remaining==[path.name] and live.poll() is None and digest(path)==before,remaining
    Path(str(marker)+'.release').write_text('release')
    assert live.wait(10)==0
    assert (d/'fixed.json').exists() and tmpfiles(d)==[]
    h.stop(sweeper)
    return dict(injection=kills,assertions='six pre-hardlink publication kills on same result; restart sweeps dead writers, preserves live writer; release publishes once',
       live_writer=dict(**rec,before_sha=before,remaining_during_live=remaining,rc=live.returncode),
       recovered_tmp_count=len(tmpfiles(d)),result=h.read(d/'fixed.json'),evidence=x.evidence())

def gateway_case():
    x=h.Node('tmp-gateway',True);h.write(x.n/'.aos/round.json',{'round':5,'open':False})
    ledger=h.pop([h.PY,h.BUDGET,'ledger','budget/demo'],x.n)
    (x.b/'.crash').write_text('call-after-reserve')
    r=x.bcli('call','r');assert r['rc']==-9,r
    kid=next(iter(h.read(x.b/'ledger.json')['ops']))
    d=x.b/'gateway';kills=[]
    for i in range(6):
        q=h.pop([h.PY,h.BUDGET,'call','budget/demo','--holder','api','--request','r'],x.n,
          {'AOS7_TEST_HOOKS':str(h.HOOK),'AOS7_TEST_CRASH':'tmp:'+kid+'.json'})
        assert q.wait(10)==-9
        tmp=d/('.%s.json.tmp.%s'%(kid,q.pid));assert tmp.exists()
        kills.append(dict(pid=q.pid,rc=q.returncode,tmp=tmp.name,sha256=digest(tmp),content=h.read(tmp)))
    h.stop(ledger)
    # A live call holds the K lock at the real pre-rename hook while the ledger sweeper starts.
    live=h.pop([h.PY,h.BUDGET,'cancel','budget/demo','--holder','api','--request','r'],x.n,
      {'AOS7_TEST_HOOKS':str(h.HOOK),'AOS7_TEST_HANG':'tmp:'+kid+'.json'})
    path=d/('.%s.json.tmp.%s'%(kid,live.pid));h.wait(path.exists,'live gateway tmp');before=digest(path)
    ledger=h.pop([h.PY,h.BUDGET,'ledger','budget/demo'],x.n)
    h.wait(lambda:len(tmpfiles(d))==1,'ledger startup sweep')
    remaining=tmpfiles(d);assert remaining==[path.name] and live.poll() is None and digest(path)==before
    h.stop(live);h.stop(ledger)
    ledger=h.pop([h.PY,h.BUDGET,'ledger','budget/demo'],x.n)
    r=x.bcli('call','r');assert r['rc']==0,r
    h.wait(lambda:not tmpfiles(d),'gateway final sweep');h.stop(ledger)
    L=h.read(x.b/'ledger.json');B=h.read(x.b/'backend.json');assert L['used']==B['accepted']==1,(L,B)
    return dict(injection=kills,assertions='six same-K gateway pre-rename kills; restart preserves only live tmp; recovery one backend effect',
       live_writer=dict(pid=live.pid,before_sha=before,remaining_during_live=remaining),recovered_tmp_count=len(tmpfiles(d)),
       used=L['used'],accepted=B['accepted'],evidence=x.evidence())

def main():
    if os.environ.get('PACK4_SCOPED')!='1':
        return sp.call(['systemd-run','--user','--scope','-q','-p','TasksMax=800','-p','RuntimeMaxSec=1800',
          '/usr/bin/env','PACK4_SCOPED=1','PYTHONDONTWRITEBYTECODE=1',sys.executable,str(Path(__file__).resolve())],cwd=h.REPO)
    ctypes.CDLL(None).prctl(36,1,0,0,0)
    h.ROOT=Path(tempfile.mkdtemp(prefix='astra7-pack4-tmp-'))
    try:
        for name,fn in [('job-folder',frame_case),('results-folder',results_case),('gateway-folder',gateway_case)]:
            try:row=dict(scenario=name,pass_=True,data=fn())
            except Exception as e:row=dict(scenario=name,pass_=False,error=repr(e),traceback=traceback.format_exc())
            ROWS.append(row);h.write(HERE/'tmp-results.json',ROWS)
            print(json.dumps({'scenario':name,'pass':row['pass_'],'error':row.get('error')}),flush=True)
            h.clean_procs(h.ROOT)
    finally:
        c=h.clean_procs(h.ROOT);assert not c['remaining'],c
        c['root']=str(h.ROOT);shutil.rmtree(h.ROOT);c['root_removed']=not h.ROOT.exists()
        h.write(HERE/'tmp-cleanup.json',c)
    return int(any(not r['pass_'] for r in ROWS))
if __name__=='__main__':sys.exit(main())
