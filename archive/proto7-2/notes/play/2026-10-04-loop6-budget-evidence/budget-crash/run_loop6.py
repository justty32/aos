#!/usr/bin/env python3
"""loop6 新增探針（B 線驗收）：沿用 run_probes.py 的子程序工具（同 run_extra.py 的做法），不 import budget 包。

- A6-02：後端 EIO 下 call／cancel／settle 都 rc 3、一行 JSON、無 traceback，intent／預留留著；恢復後同 K 一次效果。
- clock_hw：到期被拒、重播之後水位都推高；之後退鐘到水位以下＝unknown。
- 孤兒回條：送了不讀的回條，K 已結算者滿 3 個本 node 回合後被帳掃掉、在途 K 的留著；重播回條除 at 外一致。
- 退役：retired.json 在＝新 K denied、舊 K 照重播。
"""
from pathlib import Path
import os
source=Path(__file__).with_name('run_probes.py')
os.environ.setdefault('QA_OUTPUT',str(source.parent/'loop6'))
exec(compile(source.read_text().rsplit('\ntry:\n',1)[0],str(source),'exec'))
import uuid
def ledger_of(b): return load(b/'ledger.json')
def eio_backend_all(rep):
    name='loop6-eio-backend-%d'%rep;n,b=setup(name);l=pop(n,'ledger')
    (b/'.crash').write_text('gateway-after-intent');assert cmd(n,'call','r')['rc']==-9
    outs={}
    for op in ('call','cancel','settle','call'):
        r=cmd(n,op,'r',inject=('EIO','backend.json'))
        assert r['rc']==3,r
        assert 'Traceback' not in r['stderr'],r
        assert len(r['stdout'].strip().splitlines())==1 and 'unknown' in (r['result'].get('outcome'),r['result'].get('result')),r
        outs.setdefault(op,[]).append(dict(rc=r['rc'],result=r['result']))
    hits=[json.loads(x) for f in n.glob('hit-*.jsonl') for x in f.read_text().splitlines()];assert hits
    assert load(b/'gateway'/(sorted(p.stem for p in (b/'gateway').glob('*.json'))[0]+'.json'))['stage']=='intent'
    kept=basic(b);assert kept['inflight']==1 and kept['used']==0
    snap(b,name+'-interrupted',False)
    z=cmd(n,'call','r');assert z['rc']==0,z
    again=cmd(n,'call','r');assert again['rc']==0
    stop(l);final=basic(b,1);assert load(b/'backend.json')['accepted']==1
    snap(b,name+'-final');return dict(faults=outs,hits=len(hits),kept=kept,recovered=z['result'],final=final)
def clock_hw():
    n,b=setup('loop6-clock-hw')
    g=load(b/'grant.json');g['until']=10;write(b/'grant.json',g);(b/'ledger.json').unlink();assert cmd(n,'init')['rc']==0
    l=pop(n,'ledger');seen=[]
    assert cmd(n,'call','a')['rc']==0;seen.append(('success@5',ledger_of(b)['clock_hw']))
    write(n/'.aos/round.json',dict(round=10,open=False));r=cmd(n,'call','late');assert r['rc']==1,r
    seen.append(('denied@10',ledger_of(b)['clock_hw']));assert seen[-1][1]==10
    write(n/'.aos/round.json',dict(round=12,open=False));assert cmd(n,'call','a')['rc']==0
    seen.append(('replay@12',ledger_of(b)['clock_hw']));assert seen[-1][1]==12
    write(n/'.aos/round.json',dict(round=6,open=False));r=cmd(n,'call','back');assert r['rc']==3 and r['result']['outcome']=='unknown',r
    seen.append(('rollback@6',ledger_of(b)['clock_hw']));assert seen[-1][1]==12
    stop(l);final=basic(b,1);snap(b,'loop6-clock-hw-final');return dict(clock_hw=seen,rollback=r['result'],final=final)
def submit(b,op,key,content=None):
    name='%s.%s.%s.json'%(hashlib.sha256(json.dumps([key['budget'],key['holder'],key['request']],sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:20],op,uuid.uuid4().hex[:12])
    req=dict(op=op,key=key)
    if content is not None:req.update(content=content,digest=hashlib.sha256(json.dumps({'key':key,'content':content},sort_keys=True,ensure_ascii=False).encode()).hexdigest())
    write(b/'inbox'/name,req);return b/'receipts'/name
def orphans():
    n,b=setup('loop6-orphans');l=pop(n,'ledger')
    assert cmd(n,'call','s')['rc']==0
    (b/'.crash').write_text('call-after-reserve');assert cmd(n,'call','p')['rc']==-9
    L=ledger_of(b);ops={v['key']['request']:v for v in L['ops'].values()}
    paths=[submit(b,'reserve',ops['s']['key'],ops['s']['content']),submit(b,'settle',ops['s']['key']),
           submit(b,'reserve',ops['p']['key'],ops['p']['content'])]
    wait(lambda:all(p.exists() for p in paths))
    before=[load(p) for p in paths]
    kept_at=[]
    for c in (6,7,8):
        write(n/'.aos/round.json',dict(round=c,open=False));time.sleep(.3)
        assert all(p.exists() for p in paths),c;kept_at.append(c)
    write(n/'.aos/round.json',dict(round=9,open=False))
    wait(lambda:not any(p.exists() for p in paths[:2]));time.sleep(.2)
    assert paths[2].exists()
    replay=[submit(b,'reserve',ops['s']['key'],ops['s']['content']),submit(b,'settle',ops['s']['key'])]
    wait(lambda:all(p.exists() for p in replay))
    strip=lambda r:{k:v for k,v in r.items() if k!='at'}
    after=[load(p) for p in replay];assert [strip(x) for x in after]==[strip(x) for x in before[:2]],(after,before)
    for p in replay+[paths[2]]:p.unlink()
    snap(b,'loop6-orphans-interrupted',False)
    assert cmd(n,'call','p')['rc']==0
    stop(l);final=basic(b,2);snap(b,'loop6-orphans-final')
    return dict(kept_through=kept_at,swept_at=9,inflight_receipt_kept=True,replay_equal_except_at=True,final=final)
def retired():
    n,b=setup('loop6-retired');l=pop(n,'ledger')
    assert cmd(n,'call','old')['rc']==0
    write(b/'retired.json',dict(at='probe',why='loop6'))
    new=cmd(n,'call','new');assert new['rc']==1 and new['result']['outcome']=='denied',new
    old=cmd(n,'call','old');assert old['rc']==0
    stop(l);final=basic(b,1);assert len(ledger_of(b)['ops'])==1
    snap(b,'loop6-retired-final');return dict(new=new['result'],old=old['result'],final=final)
try:
    for rep in (1,2,3):case('loop6-eio-backend-%d'%rep,lambda r=rep:eio_backend_all(r))
    case('loop6-clock-hw',clock_hw)
    case('loop6-orphans',orphans)
    case('loop6-retired',retired)
finally:
    for p in PROCS:stop(p)
    ps=sp.run(['ps','-eo','pid,ppid,pgid,stat,args'],capture_output=True,text=True).stdout
    (E/'cleanup-ps.txt').write_text(ps)
    write(E/'cleanup.json',dict(root=str(ROOT),tracked_pids=[p.pid for p in PROCS],all_waited=all(p.poll() is not None for p in PROCS),remaining_mentions=[x for x in ps.splitlines() if str(ROOT) in x],root_removed=True))
    shutil.rmtree(ROOT)
    write(E/'results.json',RESULTS);write(E/'snapshots.json',MANIFEST)
