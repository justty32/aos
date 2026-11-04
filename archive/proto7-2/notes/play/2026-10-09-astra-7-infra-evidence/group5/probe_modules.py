"""Independent module integration and edge probes.
Re-run: systemd-run --user --scope -q -p TasksMax=800 -p RuntimeMaxSec=1800 python3 proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/group5/probe_modules.py
"""
from common import *
from unittest.mock import patch
from types import SimpleNamespace
import fcntl, errno
sys.path[:0]=[str(TOP/'modules'),str(TOP/'modules/once_retry')]
import history, retry_lost, aos7_mount

h=Harness('modules')
SUBD=TOP/'modules/subd/aos7-subd';AUDIT=TOP/'modules/audit/aos7-audit'
BOOT=['sh','-c','aos7-ctl daemon "$AOS7_SUBROOT" register n1 >/dev/null && exec aos7-daemon "$AOS7_SUBROOT"']

def taskenv(n,tid='probe'):
    s=slot(n,tid);s.mkdir(parents=True,exist_ok=True)
    return dict(h.env,AOS7_ROOT=str(h.root),AOS7_NODE=str(n),AOS7_NODE_ID=str(n.relative_to(h.root)),AOS7_TID=tid,AOS7_RUN='1',AOS7_TASK=str(s),PATH=str(BIN)+os.pathsep+os.environ['PATH'])

def module(cmd,env,timeout=20):
    return subprocess.run([sys.executable,*map(str,cmd)],env=env,cwd=REPO,capture_output=True,text=True,timeout=timeout)

def hierarchy():
    sub1=h.root/'parent/sub';sub2=sub1/'n1/sub'
    leaf='import os,json;from pathlib import Path;Path(os.environ["AOS7_NODE"],"env.json").write_text(json.dumps(dict(os.environ)))'
    h.node('parent/sub/n1/sub/n1',[{'name':'leaf','mode':'once','argv':[sys.executable,'-c',leaf]}])
    h.node('parent/sub/n1',[{'name':'sub','mode':'keep','argv':[sys.executable,str(SUBD),'n1/sub','--',*BOOT]}])
    n=h.node('parent',[{'name':'sub','mode':'keep','argv':[sys.executable,str(AUDIT),'--',sys.executable,str(SUBD),'parent/sub','--',*BOOT]}])
    h.ctl('register','parent');d=h.start('aos7-daemon',h.root)
    env=wait(lambda:read(sub2/'n1/env.json'),25)
    s1=read(sub1/'.aosd/status.json');s2=read(sub2/'.aosd/status.json')
    assert s1['pid']!=s2['pid'] and s1['root']==str(sub1) and s2['root']==str(sub2)
    blocked=False
    with open(sub1/'.aosd/daemon.lock','a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:blocked=True
    assert blocked and 'AOS7_SUBROOT' not in env and env['AOS7_ROOT']==str(sub2)
    audit=slot(n,'sub')/'writes.jsonl'
    rows=[json.loads(x) for x in audit.read_text().splitlines()]
    writes=[x for x in rows if '/parent/sub/.aosd/' in x['path']]
    assert writes and all(x['ok'] for x in writes),[x for x in writes if not x['ok']][:5]
    # Duplicate daemon must fail on D1 lock while D2 exists.
    contender=h.cli('aos7-daemon',sub1);assert contender.returncode!=0
    d.terminate();d.wait(12)
    return {'injection':'three real daemon levels with audit -> subd wrappers','assertion':'D2 right root, D1 locked, leaf no inherited SUBROOT; child .aosd audit writes ok','D1':{'pid':s1['pid'],'root':s1['root']},'D2':{'pid':s2['pid'],'root':s2['root']},'lock_blocked':blocked,'contender_rc':contender.returncode,'leaf_aos_env':{k:v for k,v in env.items() if k.startswith('AOS7_')},'audit_child_records':len(writes),'audit_false':[x for x in writes if not x['ok']]}

def recovery50():
    n=h.node('recover');sub=n/'sub';life=sub/'.aosd/subd-life.json';seed={'state':'running','subroot':'recover/sub','owner':{'node':'recover','tid':'probe','run':'old'},'since':'2000-01-01T00:00:00Z'};write(life,seed)
    env=taskenv(n);env['AOS7_TEST_CRASH']='subd-reaped';records=[]
    for i in range(50):
        p=module([SUBD,'recover/sub','--','true'],env);rec=read(life)
        assert p.returncode==-9 and rec['state']=='recovering' and rec['attempt']==i+1 and rec['prev']==seed
        records.append({'i':i+1,'rc':p.returncode,'bytes':life.stat().st_size,'attempt':rec['attempt']})
    assert max(x['bytes'] for x in records)-min(x['bytes'] for x in records)<20
    return {'injection':'50 real SIGKILLs at subd-reaped','assertion':'prev remains original; size bounded; attempts advance','actual_file':'subd-life.json (state recovering), not recovering.json','records':records,'last':read(life)}

def alias():
    n=h.node('alias-parent');sub=n/'sub';(sub/'registered').mkdir(parents=True)
    alias=h.root/'registered-alias';alias.symlink_to(sub/'registered',target_is_directory=True)
    rootreg=read(h.root/'.aosd/nodes.json') or {'nodes':{}};rootreg['nodes']['registered-alias']={};write(h.root/'.aosd/nodes.json',rootreg)
    p=module([SUBD,'alias-parent/sub','--','true'],taskenv(n))
    assert p.returncode==1 and '包住' in p.stderr and not (sub/'.aosd/owner.json').exists()
    return {'injection':{'registered_alias':str(alias),'realpath':str(alias.resolve())},'assertion':'subroot enclosing registered node via alias refused','rc':p.returncode,'stderr':p.stderr}

def history_names():
    out=h.root/'history';ids=['a/b','a+b','a%2Bb','daemon-events'];me={'root':str(h.root),'node_id':'hist'}
    for i,nid in enumerate(ids):write(h.root/nid/'.aos/last-round.json',{'round':1,'node':nid,'sentinel':i})
    args=SimpleNamespace(src=ids,out=str(out),max_lines=0,status=True)
    write(h.root/'.aosd/status.json',{'last_event':{'ev':'qa'}})
    changed=history.once(me,args,lambda p:None,{})
    paths={nid:history.hist_name(nid)+'.jsonl' for nid in ids}
    rows={key:[json.loads(x) for x in (out/value).read_text().splitlines()] for key,value in paths.items()}
    assert changed and len(set(paths.values()))==4
    assert all(rows[k][0]['node']==k for k in ids)
    # Upgrade with old filename: old a+b.jsonl belonged to a+b; new a/b now shares that existing path.
    legacy=h.root/'legacy-history';legacy.mkdir();(legacy/'a+b.jsonl').write_text(json.dumps({'round':7,'legacy_node':'a+b'})+'\n')
    for nid in ('a+b','a/b'):write(h.root/nid/'.aos/last-round.json',{'round':8,'node':nid})
    st={'seen':{'a+b':7,'a/b':7}};args=SimpleNamespace(src=['a+b','a/b'],out=str(legacy),max_lines=0,status=False)
    history.once(me,args,lambda p:None,st)
    migrated={p.name:[json.loads(x) for x in p.read_text().splitlines()] for p in legacy.glob('*.jsonl')}
    return {'injection':{'new_ids':ids,'legacy_file':'a+b.jsonl held node a+b round 7'},'assertion':'new encoding unique; migration observation recorded separately','new_paths':paths,'new_rows':rows,'legacy_after':migrated,'migration_mixes_nodes':len(migrated['a+b.jsonl'])==2}

def audit_edges():
    n=h.node('audit-edge');sub=n/'sub';(sub/'.aosd').mkdir(parents=True);outside=h.root/'outside';outside.mkdir()
    env=taskenv(n);env['AOS7_AUDIT_ALLOW']=':relative::'+str(outside)+':'+str(sub)+':'
    code='import os;from pathlib import Path;n=Path(os.environ["AOS7_NODE"]);r=Path(os.environ["AOS7_ROOT"]);(n/"sub/allowed").write_text("ok");(r/"outside/denied").write_text("x");os.environ["AOS7_AUDIT_ALLOW"]=":sub::";(n/"sub/relative-denied").write_text("x")'
    p=module([AUDIT,'--',sys.executable,'-c',code],env);assert p.returncode==0,p.stderr
    rows=[json.loads(x) for x in (Path(env['AOS7_TASK'])/'writes.jsonl').read_text().splitlines()]
    mapped={Path(r['path']).name:r['ok'] for r in rows}
    assert mapped['allowed'] and not mapped['denied'] and not mapped['relative-denied']
    return {'injection':{'allow':env['AOS7_AUDIT_ALLOW'],'changed_allow':':sub::'},'assertion':'empty and relative entries do not exempt; outside node remains false; real child allowed','rows':rows}

def threads():
    n=h.node('threads');env=taskenv(n)
    code='''import os,threading,json
from pathlib import Path
entered=threading.Event();second_done=threading.Event();orig=os.write;overlap=[]
def write(fd,data):
    if threading.current_thread().name=='first':
        entered.set();overlap.append(second_done.wait(5))
    return orig(fd,data)
os.write=write
def first():Path(os.environ['AOS7_NODE'],'first.txt').write_text('a')
def second():
    entered.wait(5);Path(os.environ['AOS7_NODE'],'second.txt').write_text('b');second_done.set()
a=threading.Thread(target=first,name='first');b=threading.Thread(target=second,name='second')
a.start();b.start();a.join();b.join();print(json.dumps({'overlap':overlap}))
'''
    # First hook holds log flock while its patched write waits. Second hook reaches flock and blocks.
    # Release after a short timeout, still proving second open occurred during first hook.
    code=code.replace('second_done.wait(5)','second_done.wait(.25)')
    p=module([AUDIT,'--',sys.executable,'-c',code],env);assert p.returncode==0,p.stderr
    rows=[json.loads(x) for x in (Path(env['AOS7_TASK'])/'writes.jsonl').read_text().splitlines()]
    assert {Path(x['path']).name for x in rows}=={'first.txt','second.txt'} and len(rows)==2
    return {'injection':'first hook held inside os.write for 250ms while second thread opens file','assertion':'both overlapping writes logged exactly once','rows':rows,'child_observation':json.loads(p.stdout)}

def retry_reuse():
    n=h.node('retry',[{'name':'o','mode':'once','argv':['true'],'x':{'retry_lost':True}}])
    h.action('tick','retry',env={'AOS7_TEST_CRASH':'after-birth'},rc=-9);h.action('tock','retry')
    h.action('tick','retry');h.action('tock','retry')
    h.action('tick','retry');summary=h.action('tock','retry')
    candidates=retry_lost.candidates(str(n));assert len(candidates)==1,(summary,candidates)
    rid,s,b=candidates[0]
    write(n/'.aos/tasks.json',{'tasks':[{'name':'o','mode':'keep','argv':['true']}]})
    h.action('tick','retry');actual=read(slot(n,'o')/'birth.json');ended(n,'o',actual['run'])
    assert actual['run']!=b['run'] and actual.get('once') is not True
    pending=retry_lost.scan(str(n),{rid:(s,b)});table=read(n/'.aos/tasks.json')
    assert pending=={} and len(table['tasks'])==1 and table['tasks'][0]['mode']=='keep'
    return {'injection':{'crash_rc':-9,'lost':summary,'candidate_run':rid,'slot_reused_run':actual['run']},'assertion':'real lost candidate pending discarded after real keep slot reuse','pending':pending,'table':table}

def mount_readlink():
    n=h.node('linkerr');s=slot(n,'probe');s.mkdir(parents=True);write(s/'birth.json',{'run':1,'mounts':{}})
    req=s/'mount-req/a.json';write(req,{'name':'a','path':'dest'})
    aos7_mount.make(str(h.root),str(s),{'a':'dest'});hits=[];orig=os.readlink
    def eio(path,*a,**kw):
        if str(path)==str(s/'mnt/a'):hits.append(str(path));raise OSError(errno.EIO,'readlink injection')
        return orig(path,*a,**kw)
    with patch.object(aos7_mount.os,'readlink',side_effect=eio):
        first=[aos7_mount.serve(str(h.root),str(s),None) for _ in range(3)]
    assert len(hits)>=3 and req.exists() and not (s/'mount-done/a.json').exists()
    after=aos7_mount.serve(str(h.root),str(s),None);assert after[0]['ok'] and not req.exists()
    return {'injection':{'readlink_eio_hits':len(hits)},'assertion':'unknown retained while failing; succeeds as soon as I/O recovers','during':first,'after':after,'classification':'X: persistent external I/O failure intentionally retries'}

if __name__=='__main__':
    try:
        for ident,desc,fn in [('N-66-subroot+audit','three daemons and D9 audit',hierarchy),('R8-18','50 interrupted recoveries',recovery50),('R8-24','registered node symlink alias',alias),('R8-17+edge-history','new encoding and legacy coexistence',history_names),('edge-audit-allow','empty relative outside allow entries',audit_edges),('R8-25','overlapping audit hooks in two threads',threads),('R8-26','lost candidate then real keep reuse',retry_reuse),('edge-mount-readlink','retention and recovery',mount_readlink)]:h.case(ident,desc,fn)
    finally:h.finish()
