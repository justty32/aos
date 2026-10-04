#!/usr/bin/env python3
"""Independent CLI/file-protocol edges; only own temp node and evidence are written."""
from pathlib import Path
import os
source=Path(__file__).with_name('run_probes.py')
os.environ.setdefault('QA_OUTPUT',str(source.parent/'edges'))
exec(compile(source.read_text().rsplit('\ntry:\n',1)[0],str(source),'exec'))
import uuid

def submit(b,op,key,content=None):
    kid=hashlib.sha256(json.dumps([key['budget'],key['holder'],key['request']],sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:20]
    name=f'{kid}.{op}.{uuid.uuid4().hex[:12]}.json';req=dict(op=op,key=key)
    if content is not None:req.update(content=content,digest=hashlib.sha256(json.dumps({'key':key,'content':content},sort_keys=True,ensure_ascii=False).encode()).hexdigest())
    write(b/'inbox'/name,req);return b/'receipts'/name

def advance(n,c):
    write(n/'.aos/round.json',dict(round=c,open=False));time.sleep(.12)

def orphan_restart():
    n,b=setup('orphan-restart');l=pop(n,'ledger');assert cmd(n,'call','r')['rc']==0
    rec=next(iter(load(b/'ledger.json')['ops'].values()))
    p=submit(b,'settle',rec['key']);wait(p.exists)
    advance(n,6);raw=p.read_bytes();advance(n,8);assert p.exists()
    stop(l);l=pop(n,'ledger');time.sleep(.2)
    # Restart loses only in-memory orphan age; starts a fresh safe 3-round grace.
    time.sleep(.35);assert p.read_bytes()==raw
    advance(n,10);assert p.exists();advance(n,11);wait(lambda:not p.exists())
    stop(l);snap(b,'orphan-restart-final');return dict(first_seen=6,restarted_at=8,retained_through=10,swept_at=11,pause_kept=True,final=basic(b,1))

def orphan_clock_unknown():
    n,b=setup('orphan-clock-unknown');l=pop(n,'ledger');assert cmd(n,'call','r')['rc']==0
    rec=next(iter(load(b/'ledger.json')['ops'].values()));p=submit(b,'settle',rec['key']);wait(p.exists);advance(n,6)
    path=n/'.aos/round.json';mode=path.stat().st_mode & 0o777
    try:
        path.chmod(0);time.sleep(.2);assert p.exists()
    finally:path.chmod(mode)
    time.sleep(.15);advance(n,8);assert p.exists();advance(n,9);wait(lambda:not p.exists())
    stop(l);snap(b,'orphan-clock-unknown-final');return dict(uid=os.getuid(),external_fault='true EACCES on clock',retained_during_unknown=True,swept_at=9,final=basic(b,1))

def preservation():
    n,b=setup('preservation');l=pop(n,'ledger');outs=[]
    for i in range(30):
        mode=('ok','fail','reject','cancel','ok','fail')[i%6]
        args=()
        if mode=='cancel':assert cmd(n,'cancel',str(i))['rc']==0
        else:
            write(n/'payload.json',{'mode':mode});args=('--payload',str(n/'payload.json'))
        r=cmd(n,'call',str(i),extra=args);assert r['rc']==(0 if mode=='ok' else 1),r
        outs.append(r['result']['outcome'])
    stop(l);snap(b,'preservation-before-rounds')
    paths=[b/'ledger.json',b/'backend.json']+list((b/'gateway').glob('*'))
    saved={str(p.relative_to(b)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    l=pop(n,'ledger')
    for c in range(6,19):advance(n,c)
    stop(l);assert saved=={str(p.relative_to(b)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    L=load(b/'ledger.json');B=load(b/'backend.json')
    counts=dict(ops=len(L['ops']),log=len(L['log']),gateway_json=len(list((b/'gateway').glob('*.json'))),gateway_locks=len(list((b/'gateway').glob('*.lock'))),backend_effects=len(B['effects']),accepted=B['accepted'],inbox=len(list((b/'inbox').glob('*.json'))),receipts=len(list((b/'receipts').glob('*.json'))))
    assert counts==dict(ops=30,log=60,gateway_json=30,gateway_locks=30,backend_effects=25,accepted=20,inbox=0,receipts=0),counts
    snap(b,'preservation-final');return dict(counts=counts,preserved_hashes=saved,outcomes=outs,final=basic(b,20))

def retired_unreadable():
    n,b=setup('retired-unreadable');l=pop(n,'ledger');assert cmd(n,'call','old')['rc']==0
    path=b/'retired.json';write(path,dict(at='probe',why='all callers stopped, inflight zero'));before=load(b/'ledger.json')
    try:
        path.chmod(0);new=cmd(n,'call','new');old=cmd(n,'call','old')
        assert new['rc']==3 and old['rc']==0,(new,old)
    finally:path.chmod(0o600)
    stop(l);l=pop(n,'ledger');denied=cmd(n,'call','new');assert denied['rc']==1
    assert cmd(n,'call','old')['rc']==0
    stop(l);assert load(b/'ledger.json')==before
    snap(b,'retired-unreadable-final');return dict(unreadable=new,replay=old,after_restart=denied,ledger_identical=True,final=basic(b,1))

def rollback_above_hw():
    n,b=setup('rollback-above-hw');l=pop(n,'ledger');assert cmd(n,'call','seed')['rc']==0
    advance(n,20);assert load(b/'ledger.json')['clock_hw']==5
    advance(n,10);r=cmd(n,'call','after-rollback');assert r['rc']==0
    stop(l);snap(b,'rollback-above-hw-final');return dict(classification='M',contract='budget spec §2 precondition and §9.2',clock_sequence=[5,20,10],previous_hw=5,rollback_detected=False,result=r,final=basic(b,2))

def permission_boundaries():
    n,b=setup('permission-boundaries');l=pop(n,'ledger');(b/'.crash').write_text('gateway-after-intent');assert cmd(n,'call','r')['rc']==-9
    lock=next((b/'gateway').glob('*.lock'));lock.chmod(0);outs=[]
    try:
        for op in ('call','cancel'):
            r=cmd(n,op,'r');assert r['rc']==3 and r['result']['outcome']=='unknown' and 'Traceback' not in r['stderr'],r;outs.append(r)
    finally:lock.chmod(0o600)
    inbox=b/'inbox';mode=inbox.stat().st_mode & 0o777;inbox.chmod(0o500)
    try:
        r=cmd(n,'settle','r');assert r['rc']==3 and r['result']['outcome']=='unknown' and 'Traceback' not in r['stderr'],r;outs.append(r)
    finally:inbox.chmod(mode)
    assert basic(b)['inflight']==1;snap(b,'permission-boundaries-interrupted',False)
    assert cmd(n,'call','r')['rc']==0;stop(l);snap(b,'permission-boundaries-final');return dict(uid=os.getuid(),failures=outs,final=basic(b,1))

try:
    for name,fn in [('orphan-restart-pause',orphan_restart),('orphan-clock-unknown',orphan_clock_unknown),('preservation-30K',preservation),('retired-EACCES-restart',retired_unreadable),('rollback-above-hw-M',rollback_above_hw),('permission-common-boundary',permission_boundaries)]:case(name,fn)
finally:
    for p in PROCS:stop(p)
    ps=sp.run(['ps','-eo','pid,ppid,pgid,stat,args'],capture_output=True,text=True).stdout;(E/'cleanup-ps.txt').write_text(ps)
    shutil.rmtree(ROOT)
    write(E/'cleanup.json',dict(root=str(ROOT),tracked_pids=[p.pid for p in PROCS],all_waited=all(p.poll() is not None for p in PROCS),remaining_mentions=[x for x in ps.splitlines() if str(ROOT) in x],root_removed=not ROOT.exists()))
    write(E/'results.json',RESULTS);write(E/'snapshots.json',MANIFEST)
