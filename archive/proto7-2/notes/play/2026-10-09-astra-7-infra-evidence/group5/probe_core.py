"""Independent core probes, stdlib only.
Re-run: systemd-run --user --scope -q -p TasksMax=800 -p RuntimeMaxSec=1800 python3 proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/group5/probe_core.py
"""
from common import *
from unittest.mock import patch
from types import SimpleNamespace
import errno, threading
import aos7_fs as fs, aos7_proc as proc, aos7_daemon_timeline as tlmod
from aos7_daemon import Daemon

h=Harness('core')

def intervals():
    a=h.node('interval',interval=10**309);b=h.node('peer',interval=70)
    h.ctl('register','interval');h.ctl('register','peer');d=h.start('aos7-daemon',h.root)
    vals=[]
    try:
        for bad in (10**309,-10**309):
            base=(read(a/'.aos/round.json') or {}).get('round',0)
            peer=(read(b/'.aos/round.json') or {}).get('round',0)
            write(a/'.aos/timeline.json',{'interval_ms':bad})
            wait(lambda:(read(a/'.aos/last-round.json') or {}).get('round',0)>=base+2,10)
            status=read(h.root/'.aosd/status.json');row=status['nodes']['interval']
            assert row['interval_ms']==1000,row
            assert 'interval_ms' in str(row.get('last_error')),row
            assert (read(b/'.aos/round.json') or {})['round']>peer
            vals.append({'injected':str(bad),'row':row,'peer_advanced':True})
        before=read(a/'.aos/round.json')['round'];write(a/'.aos/timeline.json',{'interval_ms':83})
        wait(lambda:((read(h.root/'.aosd/status.json') or {}).get('nodes',{}).get('interval',{}).get('interval_ms')==83),5)
        after=read(a/'.aos/round.json')['round'];assert after>=before+1
        vals.append({'repaired_ms':83,'before':before,'after':after})
    finally:
        d.terminate();d.wait(8)
    return {'injection':'actual timeline.json values','assertion':'default + error + peer progresses + repair next round','observations':vals}

def bounds():
    n=h.node('bounds');cases=[]
    for v in (0,31536000000-1,31536000000,31536000000+1,True,float('inf'),float('nan')):
        write(n/'.aos/timeline.json',{'interval_ms':v});got=tlmod.read_config(str(n))
        valid=type(v) in (int,float) and 0<=v<=31536000000
        assert got[0]==(v if valid else 1000) and bool(got[3])!=valid
        cases.append({'value':str(v),'actual':got})
    write(n/'.aos/timeline.json',{'interval_ms':-1,'action_timeout_s':0,'early_tock':'yes'})
    got=tlmod.read_config(str(n));assert got[:3]==(1000,False,30.0) and 'interval_ms' in got[3]
    return {'assertion':'inclusive year bound; first error only; all invalid values default','cases':cases,'multiple_invalid':got}

def owing():
    n=h.node('owing',interval=0);d=Daemon(str(h.root));d.steps={'owing':{'qa':1}}
    timeline=tlmod.Timeline(d,'owing',None);calls=[];hit=[];original=timeline.prog
    def prog(name,*args,**kwargs):
        out=original(name,*args,**kwargs);calls.append([name,out[0]])
        if name=='aos7-tock':
            assert read(n/'.aos/round.json')['open'] is False
            hit.append('tock closed on disk')
        return out
    original_read=fs.inject;read_count=0
    def fault(op,path):
        nonlocal read_count
        if hit and op=='open' and str(path)==str(n/'.aos/round.json') and read_count<2:
            read_count+=1;hit.append('EIO post-tock read %d'%read_count);raise OSError(errno.EIO,'group5 one-shot')
        return original_read(op,path)
    try:
        with patch.object(timeline,'prog',side_effect=prog),patch.object(fs,'inject',side_effect=fault):
            timeline.start();wait(lambda:d.is_paused('owing'),8)
            d.stopping=True;timeline.wake.set();timeline.join(5)
        disk=read(n/'.aos/round.json');assert disk['round']==1 and not disk['open']
        assert d.steps=={} and timeline.owe_round is None and read_count==2
        assert sum(x[0]=='aos7-tick' for x in calls)==1
        return {'injection':hit,'assertion':'one closed round debited exactly once; paused owner qa; no second tick','calls':calls,'round':disk,'steps':d.steps,'paused':d.paused}
    finally:d.stopping=True;timeline.wake.set();timeline.join(5);os.close(d.rfd)

def restart_steps():
    # Dedicated daemon root to exclude already registered interval nodes.
    root=h.root/'restart';root.mkdir();n=root/'a';write(n/'.aos/tasks.json',{'tasks':[]})
    write(n/'.aos/timeline.json',{'interval_ms':700,'early_tock':True})
    write(root/'.aosd/nodes.json',{'nodes':{'a':{}}});write(root/'.aosd/paused.json',{'paused':{'a':['qa']},'steps':{}})
    p=h.start('aos7-daemon',root)
    wait(lambda:read(root/'.aosd/status.json'))
    p1=h.cli('aos7-ctl','daemon',root,'resume','a','--owner','qa','--rounds','3')
    assert p1.returncode==0,(p1.stdout,p1.stderr)
    wait(lambda:(read(root/'.aosd/paused.json') or {}).get('steps',{}).get('a',{}).get('qa')==2)
    before=read(root/'.aosd/paused.json');rnd=read(n/'.aos/round.json');assert rnd['round']==1 and not rnd['open']
    p.kill();p.wait();p=h.start('aos7-daemon',root)
    wait(lambda:'qa' in (read(root/'.aosd/paused.json') or {}).get('paused',{}).get('a',[]),10)
    after=read(root/'.aosd/paused.json');disk=read(n/'.aos/round.json')
    p.terminate();p.wait(8)
    assert disk['round']==3 and not disk['open'] and after['steps']=={}
    return {'injection':{'daemon_sigkill':True,'before':before,'closed_round':rnd},'assertion':'persisted remaining 2, restart closes total 3 then pauses same owner','after':after,'round':disk}

def mounts():
    n=h.node('mount',[{'name':'worker','mode':'keep','argv':['sleep','300']}]);h.action('tick','mount');s=slot(n,'worker');wait(lambda:read(s/'pid.json'));h.action('tock','mount')
    req=s/'mount-req/dyn.json';write(req,{'name':'dyn','path':'shared','why':'qa'})
    hit=h.action('tick','mount',env={'AOS7_TEST_CRASH':'after-symlink'},rc=-9)
    snap={'link':(s/'mnt/dyn').is_symlink(),'birth':read(s/'birth.json'),'request':read(req),'receipt':read(s/'mount-done/dyn.json')}
    assert snap['link'] and 'dyn' not in snap['birth'].get('mounts',{}) and snap['request'] and snap['receipt'] is None
    h.action('tock','mount');h.action('tick','mount');receipt=read(s/'mount-done/dyn.json');birth=read(s/'birth.json')
    assert receipt['result']['ok'] and birth['mounts']['dyn']['dyn'] and not req.exists()
    h.action('tock','mount');birth['mounts']['retry']={'to':'other','error':'injected prior mount failure'};write(s/'birth.json',birth)
    write(s/'mount-req/retry.json',{'name':'retry','path':'other'});h.action('tick','mount')
    r=read(s/'mount-done/retry.json');assert r['result']['ok'] and (s/'mnt/retry').is_symlink()
    return {'injection':{'crash_rc':-9,'snapshot':snap,'static_error':birth['mounts']['retry']},'assertion':'crash replay and failed static mount retry both commit dyn and receipts','replay':receipt,'static_retry':r}

def once_schedule():
    records=[]
    for variant in ('postpone','disable'):
        nid='once-'+variant
        n=h.node(nid,[{'name':'o','mode':'once','argv':['sh','-c','echo once >> "$AOS7_NODE/effects.log"']},{'name':'o','mode':'keep','argv':['true']}])
        h.action('tick',nid,env={'AOS7_TEST_CRASH':'before-once-delete'},rc=-9);ended(n,'o',1)
        items=read(n/'.aos/tasks.json');launch=items['tasks'][0]['launch']
        h.action('tock',nid)
        items['tasks'][0].update({'from_round':3} if variant=='postpone' else {'enabled':False});write(n/'.aos/tasks.json',items)
        for k in range(5):
            if variant=='disable' and k==2:
                items=read(n/'.aos/tasks.json')
                for item in items['tasks']:
                    if item.get('mode')=='once':item['enabled']=True
                write(n/'.aos/tasks.json',items)
            h.action('tick',nid);run=read(slot(n,'o')/'birth.json')['run'];ended(n,'o',run);h.action('tock',nid)
        effects=(n/'effects.log').read_text().splitlines();assert effects==['once'] and run>1
        records.append({'variant':variant,'injection':{'crash_rc':-9,'launch':launch},'effects':effects,'final_run':run,'tasks':read(n/'.aos/tasks.json')})
    return {'assertion':'once launches once despite schedule edits and real keep slot reuse','variants':records}

def pgid_read():
    n=h.node('pgid',[{'name':'k','mode':'keep','argv':['sleep','300']}]);h.action('tick','pgid');pj=wait(lambda:read(slot(n,'k')/'pid.json'))
    d=Daemon(str(h.root));tl=tlmod.Timeline(d,'pgid',None)
    try:
        first=d.live_of('pgid',tl);before=sorted(d._pgids['pgid']);d._live.clear();orig=fs.inject;hit=[]
        def fault(op,path):
            if op=='open' and str(path).endswith('/pid.json'):
                hit.append(str(path))
                if len(hit)==2:raise OSError(errno.EIO,'second pid read')
            return orig(op,path)
        with patch.object(fs,'inject',side_effect=fault):second=d.live_of('pgid',tl)
        after=sorted(d._pgids['pgid']);assert len(hit)>=2 and before==after==[pj['pgid']] and first==second
        return {'injection':{'pid_reads':hit,'eio_read':2},'assertion':'remembered pgid survives second read failure','before':before,'after':after,'live':second}
    finally:os.close(d.rfd)

def backoff():
    n=h.node('backoff');d=SimpleNamespace(root=str(h.root),gen=None,stopping=False,stopping_since=None,kill_on_stop=False)
    t=tlmod.Timeline(d,'backoff',None);waits=[];orig=t.wake.wait
    def w(timeout):waits.append(timeout);return orig(timeout)
    start=time.monotonic();cpu=time.process_time()
    # 100 genuine production backoff invocations, shortened cap only; separate unscaled saturation run.
    with patch.object(tlmod,'RECOVER_BACKOFF_MAX',.02),patch.object(t.wake,'wait',side_effect=w):
        for _ in range(100):t.wake.set();t.backoff()
    elapsed=time.monotonic()-start;used=time.process_time()-cpu
    assert len(waits)<=350 and elapsed>=1.8 and used<.5
    t.recover_fails=10**100;t.wake.set();start=time.monotonic();t.backoff();large=time.monotonic()-start
    assert 7.8<=large<10
    return {'injection':'wake set each of 100 calls; recover_fails=10**100','assertion':'bounded waits; low CPU; production maximum ~8s without exponent overflow','calls':100,'waits':len(waits),'elapsed_s':elapsed,'cpu_s':used,'large_n_elapsed_s':large,'note':'100-call cap shortened to 20ms; large-n uses production 8s cap'}

def fds():
    p=h.root/'fd.json';write(p,{'ok':1});before=len(os.listdir('/proc/self/fd'));hits=[]
    def bad(fd):hits.append(fd);raise OSError(errno.EIO,'fstat injected')
    with patch.object(fs.os,'fstat',side_effect=bad):states=[fs.fact(p)[0] for _ in range(300)]
    after=len(os.listdir('/proc/self/fd'));assert before==after and set(states)=={fs.U} and len(hits)==300
    return {'injection':{'fstat_eio_hits':len(hits)},'assertion':'300 unknown reads leak zero fds','before':before,'after':after}

def birth_error():
    s=h.root/'runner-slot';s.mkdir();write(s/'birth.json',{'run':37,'argv':['true']});hits=h.root/'runner-hits.txt'
    p=h.cli('aos7-run',s,env={'AOS7_RUN':'37','AOS7_TEST_FAULT':'open:birth.json:EIO','AOS7_TEST_FAULT_HITS':str(hits)})
    ex=read(s/'exit.json');assert p.returncode==1 and ex['run']==37 and ex['code']==127 and hits.exists()
    return {'injection':hits.read_text().splitlines(),'assertion':'startup failure preserves integer run and code 127','rc':p.returncode,'exit':ex}

def ordinary_arg():
    n=h.node('argument',[{'name':'k','mode':'keep','argv':[sys.executable,'-c','import time;time.sleep(300)','x/aos7-run']}]);h.action('tick','argument')
    s=slot(n,'k');pj=wait(lambda:read(s/'pid.json'));assert not proc.is_runner(pj['pid'])
    write(s/'ctl.json',{'op':'kill','run':1});h.action('tock','argument')
    wait(lambda:proc.same_process(pj['pid'],pj['starttime'])==proc.GONE)
    return {'injection':{'argv_tail':'x/aos7-run','pid':pj},'assertion':'ordinary argument does not exclude task from kill','receipt':read(s/'ctl-done.json'),'identity':proc.same_process(pj['pid'],pj['starttime'])}

def bad_comm():
    # Real Linux comm set to bytes, then real /proc scan (stronger than a text fixture).
    code='import ctypes,time;ctypes.CDLL(None).prctl(15,b"qa\\xff",0,0,0);time.sleep(300)'
    p=subprocess.Popen([sys.executable,'-c',code,str(h.root)],env=h.env);h.ps.append((p,open(os.devnull,'w')))
    wait(lambda:b'qa\xff' in Path('/proc/%s/stat'%p.pid).read_bytes())
    raw=Path('/proc/%s/stat'%p.pid).read_bytes();row=proc.stat_of(p.pid);table=proc._table();assert p.pid in table and row[0]!='Z'
    p.terminate();p.wait()
    return {'injection':{'comm_hex':raw.split(b')')[0].hex()},'assertion':'non-UTF8 comm has valid process identity, scan succeeds (K1 bytes-parser decision)','stat':row,'scan_count':len(table)}

def directives():
    from aos_directives import Document, Context, resolve, DirectiveError
    ctx=Context(Document(None,{'array':[1,2,3]}));out=[]
    for directive in ({'$ref':'#/array/１'},{'$ref':'#/array/²'},{'$ref':'','$at':None}):
        try:resolve(directive,ctx,['request']);raise AssertionError('accepted invalid')
        except DirectiveError as e:out.append({'input':directive,'code':e.code,'message':str(e)})
    assert [x['code'] for x in out]==['ReferencePointerInvalid','ReferencePointerInvalid','DirectiveValueTypeMismatch']
    return {'injection':'literal malformed directive values','assertion':'typed errors, no raw ValueError','errors':out}

if __name__=='__main__':
    cases=[('A8-11+R8-20','huge intervals live daemon and peer',intervals),('edge-interval','year boundaries and multiple invalid fields',bounds),('R8-05','real tick/tock with exact in-process post-tock read EIO',owing),('N-06','SIGKILL daemon after persisted first round',restart_steps),('A8-07+R8-09','mount crash and static failure recovery',mounts),('N-86','once schedule changes with shared keep slot',once_schedule),('R8-04','LIVE second pid read EIO',pgid_read),('R8-06','100 backoffs and huge failure counter',backoff),('R8-07','300 fstat EIOs',fds),('R8-10','runner birth EIO',birth_error),('R8-11','ordinary argv contains runner-looking path',ordinary_arg),('R8-12','real non-UTF8 Linux comm',bad_comm),('R8-28','non-ASCII digits and null directive',directives)]
    try:
        for ident,scenario,fn in cases:h.case(ident,scenario,fn)
    finally:h.finish()
