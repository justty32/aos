#!/usr/bin/env python3
"""Additional probes reuse only the QA harness helpers, never import the budget package."""
from pathlib import Path
import os
source=Path(__file__).with_name('run_probes.py')
os.environ.setdefault('QA_OUTPUT',str(source.parent/'extra'))
# Load helper definitions while excluding the driver main loop.
exec(compile(source.read_text().rsplit('\ntry:\n',1)[0],str(source),'exec'))
def eio_other(target):
    n,b=setup('eio-'+target.replace('/','_'));l=pop(n,'ledger');(b/'.crash').write_text('call-after-reserve')
    assert cmd(n,'call','r')['rc']==-9
    r=cmd(n,'call','r',inject=('EIO',target));assert r['rc']==3,r
    hits=[json.loads(x) for f in n.glob('hit-*.jsonl') for x in f.read_text().splitlines()];assert hits
    assert basic(b)['inflight']==1
    snap(b,'eio-'+target.replace('/','_')+'-interrupted',False)
    z=cmd(n,'call','r');assert z['rc']==0,z
    stop(l);snap(b,'eio-'+target.replace('/','_')+'-final');return dict(hits=hits,failure=r,recovered=z,final=basic(b,1))
def permission_backend():
    n,b=setup('eacces-backend');l=pop(n,'ledger')
    seed=cmd(n,'call','seed');assert seed['rc']==0
    (b/'.crash').write_text('gateway-after-intent');assert cmd(n,'call','r')['rc']==-9
    backend=b/'backend.json';saved=backend.read_bytes();oldmode=backend.stat().st_mode & 0o777
    try:
        backend.chmod(0)
        r=cmd(n,'call','r')
        assert r['rc']==1 and r['result'] is None and 'PermissionError' in r['stderr'],r
        unknown=cmd(n,'settle','r');assert unknown['rc']==3
        before=basic(b);assert before['used']==1 and before['inflight']==1
    finally: backend.chmod(oldmode)
    assert saved==backend.read_bytes()
    snap(b,'eacces-backend-interrupted',False)
    z=cmd(n,'call','r');assert z['rc']==0
    stop(l);snap(b,'eacces-backend-final');return dict(real_EACCES=True,uid=os.getuid(),failure=r,unknown=unknown,before=before,recovered=z,final=basic(b,2),data_unchanged_during_fault=True)
def cancel_window(mode,point):
    name='cancel-window-'+mode+'-'+point;n,b=setup(name);l=pop(n,'ledger');(b/'.crash').write_text(point)
    assert cmd(n,'call','r')['rc']==-9
    r=cmd(n,'cancel','r',inject=(mode,'gateway-done'));assert r['rc']==-9,r
    hits=[json.loads(x) for f in n.glob('hit-*.jsonl') for x in f.read_text().splitlines()];assert len(hits)==1
    snap(b,name+'-interrupted',False)
    cancel=cmd(n,'cancel','r');expected='accepted' if point=='backend-after-effect' else 'cancelled'
    assert cancel['result']['outcome']==expected,cancel
    late=cmd(n,'call','r');assert late['result']['outcome']==expected,late
    stop(l);snap(b,name+'-final');return dict(hits=hits,cancel=cancel,late=late,final=basic(b,1 if expected=='accepted' else 0))
def init_window(mode):
    n=ROOT/('init-'+mode);b=n/'budget/demo'
    write(n/'.aos/round.json',dict(round=5,open=False))
    write(b/'grant.json',{'v':1,'grant':'g1','budget':'demo','holder':'api','resource':'fakeapi.calls','gateway':'fakeapi','amount':5,'clock':'completed_tock','from':0,'until':1000,'delegate':False})
    r=cmd(n,'init',inject=(mode,'ledger-init'));assert r['rc']==-9,r
    hits=[json.loads(x) for f in n.glob('hit-*.jsonl') for x in f.read_text().splitlines()];assert len(hits)==1
    exists=(b/'ledger.json').exists();assert exists==(mode=='after')
    again=cmd(n,'init');assert again['rc']==(1 if exists else 0),again
    l=pop(n,'ledger');assert cmd(n,'call','r')['rc']==0;stop(l)
    snap(b,'init-'+mode+'-final');return dict(hits=hits,ledger_existed_after_kill=exists,reinit=again,final=basic(b,1))
try:
    for target in ('grant.json','gateway/519457d6f54d32335539.json'):case('eio-'+target,lambda t=target:eio_other(t))
    case('eacces-backend',permission_backend)
    for mode in ('before','after'):
        for point in ('gateway-after-intent','backend-after-effect'):case('cancel-window-'+mode+'-'+point,lambda m=mode,p=point:cancel_window(m,p))
        case('init-window-'+mode,lambda m=mode:init_window(m))
finally:
    for p in PROCS:stop(p)
    ps=sp.run(['ps','-eo','pid,ppid,pgid,stat,args'],capture_output=True,text=True).stdout
    (E/'cleanup-ps.txt').write_text(ps)
    write(E/'cleanup.json',dict(root=str(ROOT),tracked_pids=[p.pid for p in PROCS],all_waited=all(p.poll() is not None for p in PROCS),remaining_mentions=[x for x in ps.splitlines() if str(ROOT) in x],root_removed=True))
    shutil.rmtree(ROOT)
    write(E/'results.json',RESULTS);write(E/'snapshots.json',MANIFEST)
