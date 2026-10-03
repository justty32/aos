from common import *
from unittest import mock
import aos7_tick as tick, aos7_tock as tock, aos7_daemon as daemon
import aos7_kernel_rules as rules
from test_astra7 import FAIL_HOOK

def hook(s,code):
    p=s.root/'hook';p.mkdir(exist_ok=True);(p/'sitecustomize.py').write_text(code)
    return {'PYTHONPATH':str(p),'HOOK_LIB':str(LIB),'HOOK_FAIL':str(s.root/'fail'),'MARK':str(s.root/'mark')}
def ctl(root,op,**kw):
    name=uuid.uuid4().hex+'.json';t=time.monotonic();write(root/'.aosd/ctl'/name,dict(op=op,**kw));r=wait(lambda:read(root/'.aosd/ctl-done'/name));return {'receipt':r,'latency_s':time.monotonic()-t}
def status(s):return read(s.root/'.aosd/status.json',{})
def error_controls(s):
    n=s.node(items=[{'name':'live','mode':'keep','argv':SLEEP}]);(s.root/'fail').touch();d=s.start(env=hook(s,FAIL_HOOK))
    wait(lambda:status(s).get('nodes',{}).get('n',{}).get('phase')=='error')
    first=status(s);r=ctl(s.root,'pause',node='n');wait(lambda:status(s)['nodes']['n']['phase']=='paused',10)
    paused=status(s);open_=read(n/'.aos/round.json');time.sleep(.6);still=read(n/'.aos/round.json')
    resume=ctl(s.root,'resume',node='n');wait(lambda:status(s)['nodes']['n']['phase']=='error',10)
    # Exercise capped exponential backoff: recover_fails >= 6 => 8 seconds.
    wait(lambda:'已試 6 次' in status(s)['nodes']['n'].get('last_error',{}).get('err',''),25)
    before=status(s);log=rows(s.root/'.aosd/log.jsonl');t=time.monotonic();stop=ctl(s.root,'stop',kill=True);d.wait(10)
    return {'first':first,'pause':r,'paused':paused,'open_when_paused':open_,'round_after_pause_wait':still,'resume':resume,'before_stop':before,'stop':stop,'stop_exit_s':time.monotonic()-t,'rc':d.returncode,'final':status(s),'tock_error_times':[x['at'] for x in log if x.get('ev')=='tock' and x.get('rc')],'product_live_before_cleanup':{p:v for p,v in descendants().items() if v['state']!='Z'}}
def error_rounds(s):
    n=s.node();write(s.root/'.aosd/paused.json',{'paused':['n']});(s.root/'fail').touch();d=s.start(env=hook(s,FAIL_HOOK));wait(lambda:status(s).get('nodes',{}).get('n',{}).get('phase')=='paused')
    resume=ctl(s.root,'resume',node='n',rounds=1);wait(lambda:status(s)['nodes']['n']['phase']=='error');before=status(s);(s.root/'fail').unlink()
    wait(lambda:status(s)['nodes']['n']['phase']=='paused',10);after=status(s);stop=ctl(s.root,'stop',kill=True);d.wait(10)
    return {'resume':resume,'before':before,'after':after,'summaries':rows(n/'.aos/rounds.jsonl'),'steps_done':[x for x in rows(s.root/'.aosd/log.jsonl') if x.get('ev')=='steps-done']}

RUNHOOK='''import os,sys,signal
if os.path.basename(sys.argv[0])=='aos7-run':
 sys.path.insert(0,os.environ['HOOK_LIB']);import aos7_run as r
 def barrier(label):
  open(os.environ['MARK'],'w').write(label);os.kill(os.getpid(),signal.SIGSTOP)
 point=os.environ['POINT']
 if point=='before-main':barrier(point)
 real=r.write_at
 def write(fd,name,obj):
  if point=='before-pid' and name=='pid.json':barrier(point)
  if point=='before-exit' and name=='exit.json':barrier(point)
  v=real(fd,name,obj)
  if point=='after-pid' and name=='pid.json':barrier(point)
  return v
 r.write_at=write
'''
def runner_kill(s,point):
    argv=['true'] if point=='before-exit' else SLEEP
    n=s.node(items=[{'name':'x','mode':'keep','argv':argv}]);env=hook(s,RUNHOOK);env['POINT']=point
    r=s.run('aos7-tick',env=env);wait((s.root/'mark').exists);td=n/'.aos/tasks/x-r1';ri=wait(lambda:read(td/'runner.json'))
    before={'state':task.task_state(str(td)),'runner':ri,'pid':read(td/'pid.json')};os.kill(ri['pid'],signal.SIGKILL);wait(lambda:not task.pid_alive(ri['pid']))
    after=task.task_state(str(td));tr=s.run('aos7-tock');next_=s.run('aos7-tick')
    return {'point':point,'tick':r,'before':before,'after_kill':after,'tock':tr,'next_tick':next_,'old_exit':read(td/'exit.json'),'old_task_processes':{p:v for p,v in descendants().items() if v['state']!='Z'}}
def runner_handoff(s,fail_write=False):
    n=s.node(items=[{'name':'x','mode':'keep','argv':SLEEP}]);real=task.subprocess.Popen;born=[];realwrite=task.write_json
    def spawn(args,*a,**kw):
        p=real(args,*a,**kw)
        if len(args)>1 and str(args[1]).endswith('/aos7-run'):
            p.kill();p.wait();born.append(p.pid)
        return p
    def writefail(p,v):
        if str(p).endswith('/runner.json'):raise OSError(5,'injected runner record EIO')
        return realwrite(p,v)
    with mock.patch.object(task.subprocess,'Popen',spawn),mock.patch.object(task,'write_json',writefail if fail_write else realwrite):first=tick.tick(str(s.root),'n')
    td=n/'.aos/tasks/x-r1';tr=tock.tock(str(s.root),'n');second=tick.tick(str(s.root),'n')
    return {'injection':'runner SIGKILL + wait before Popen returns to tick'+(' and runner.json EIO' if fail_write else ''),'runner':read(td/'runner.json'),'pid':read(td/'pid.json'),'exit':read(td/'exit.json'),'state':task.task_state(str(td)),'first':first,'tock':tr,'next_tick':second,'dead_pids':born}
def runner_identity(s):
    n=s.node();td=n/'.aos/tasks/x-r1';write(td/'birth.json',{'tid':'x-r1','name':'x'})
    p=s.start(args=['sleep','30']);st=fs.proc_starttime(p.pid);out={}
    for label,value in [('matching',st),('reused',st-1),('missing',None)]:
        write(td/'runner.json',{'pid':p.pid,'starttime':value});out[label]=task.task_state(str(td))
    write(td/'runner.json',{'pid':p.pid,'starttime':st})
    with mock.patch.object(task,'proc_starttime',return_value=None):out['proc_unreadable']=task.task_state(str(td))
    write(td/'runner.json',{'pid':p.pid,'starttime':st-1});write(td/'pid.json',{'pid':p.pid,'runner_pid':p.pid,'pgid':p.pid});out['reused_with_pid_json']=task.task_state(str(td))
    out['unrelated_still_alive']=p.poll() is None;return out

def ownership(s,edit=False):
    n=s.node(items=[{'name':'child','mode':'keep','argv':['aos7-daemon','$AOS7_SUBROOT'],'subroot':'n/sub'}]);sub=n/'sub'
    if edit:
        code="import os;os.environ['AOS7_OWNER_NODE']='edited';os.environ['AOS7_OWNER_TID']='edited-r99';os.environ['AOS7_ALLOW_STOP']='1';os.execvp('aos7-daemon',['aos7-daemon',os.environ['AOS7_SUBROOT']])"
        write(n/'.aos/tasks.json',{'tasks':[{'name':'child','mode':'keep','argv':[sys.executable,'-c',code],'subroot':'n/sub'}]})
    first=s.run('aos7-tick');st=wait(lambda:read(sub/'.aosd/status.json'));ow=read(sub/'.aosd/owner.json')
    if edit:
        r=ctl(sub,'stop',kill=True);wait(lambda:read(n/'.aos/tasks/child-r1/exit.json'));return {'owner':ow,'stop':r}
    os.kill(st['pid'],signal.SIGTERM);wait(lambda:read(n/'.aos/tasks/child-r1/exit.json'));s.run('aos7-tock');second=s.run('aos7-tick');wait(lambda:read(sub/'.aosd/status.json',{}).get('pid')!=st['pid']);ow2=read(sub/'.aosd/owner.json');st2=read(sub/'.aosd/status.json');os.kill(st2['pid'],signal.SIGTERM);wait(lambda:read(n/'.aos/tasks/child-r2/exit.json'))
    write(sub/'.aosd/stopped.json',{'by':'test'});manual=s.start(args=[sys.executable,str(BIN/'aos7-daemon'),str(sub)]);wait(lambda:read(sub/'.aosd/status.json',{}).get('pid')==manual.pid);r=ctl(sub,'stop',kill=True)
    return {'first':first,'second':second,'owner_first':ow,'owner_restarted':ow2,'manual_pid':manual.pid,'manual_owner':read(sub/'.aosd/owner.json'),'stopped_cleared':not(sub/'.aosd/stopped.json').exists(),'manual_stop':r}
def nested(s):
    # Three daemon levels, leaf task explicitly records whether claim env leaked.
    top=s.node(items=[{'name':'child','mode':'keep','argv':['aos7-daemon','$AOS7_SUBROOT'],'subroot':'n/sub'}]);d=s.start();sub=top/'sub';wait(lambda:read(sub/'.aosd/status.json'))
    mid=sub/'m';write(mid/'.aos/tasks.json',{'tasks':[{'name':'grand','mode':'keep','argv':['aos7-daemon','$AOS7_SUBROOT'],'subroot':'m/sub'}]});write(mid/'.aos/timeline.json',{'interval_ms':100});grand=mid/'sub';wait(lambda:read(grand/'.aosd/status.json'))
    leaf=grand/'leaf';code="import os,json;open('env.json','w').write(json.dumps({k:v for k,v in os.environ.items() if k.startswith('AOS7_')}))"
    write(leaf/'.aos/tasks.json',{'tasks':[{'name':'env','argv':[sys.executable,'-c',code]}]});write(leaf/'.aos/timeline.json',{'interval_ms':200});en=wait(lambda:read(leaf/'env.json'));owners=[read(x/'.aosd/owner.json') for x in (sub,grand)];r=ctl(s.root,'stop',kill=True);d.wait(10);time.sleep(.2)
    return {'owners':owners,'leaf_env':en,'stop':r,'product_live_before_cleanup':{p:v for p,v in descendants().items() if v['state']!='Z'}}

def retention_values(s):
    results=[]
    for i,value in enumerate([0,-1,1.5,'2',True,None,2]):
        n=s.node('n'+str(i));write(n/'.aos/timeline.json',{'keep_ended_rounds':0,'keep_old_rounds':value});td=n/'.aos/tasks-old/x-r1';write(td/'birth.json',{'tid':'x-r1'});write(td/'ended.json',{'round':1});write(n/'.aos/round.json',{'round':3,'open':True});tr=tock.tock(str(s.root),'n'+str(i))
        d=daemon.Daemon(str(s.root));write(s.root/'.aosd/retention.json',{k:value for k in ('ctl_done_max','ctl_failed_max','log_max_bytes')})
        for sub in ('ctl-done','ctl-failed'):
            for j in range(3):write(s.root/'.aosd'/sub/(str(j)+'.json'),{'i':j})
        d.log(ev='value',value=value);d.retention();result={'value':value,'old_exists':td.exists(),'purged':tr.get('purged',[]),'done_count':len(list((s.root/'.aosd/ctl-done').iterdir())),'failed_count':len(list((s.root/'.aosd/ctl-failed').iterdir())),'current_log_exists':(s.root/'.aosd/log.jsonl').exists()};os.close(d.rfd);results.append(result)
    return {'values':results}
def retention_reader(s):
    import threading
    d=daemon.Daemon(str(s.root));write(s.root/'.aosd/retention.json',{'log_max_bytes':0});d.log(ev='before',seq=-1);lp=s.root/'.aosd/log.jsonl';f=lp.open();first=f.read();errors=[];seen=[];done=threading.Event()
    def reader():
        while not done.is_set():
            try:seen.extend(x['seq'] for x in rows(lp) if 'seq' in x)
            except Exception as e:errors.append(repr(e))
            time.sleep(.001)
    th=threading.Thread(target=reader);th.start()
    try:
        for i in range(60):d.log(ev='sequence',seq=i);d.retention();time.sleep(.001)
        d.log(ev='after',seq=60);time.sleep(.01)
    finally:done.set();th.join()
    held=f.read();f.close();disk=rows(lp)+rows(s.root/'.aosd/log.1.jsonl');os.close(d.rfd)
    return {'initial_open_read':first,'held_fd_after_rotations':held,'reopening_reader_unique_seen':len(set(seen)),'read_errors':errors,'retained_seq':[x['seq'] for x in disk],'total_emitted':62}
def retention_usage(s):
    n=s.node();write(n/'.aos/timeline.json',{'keep_old_rounds':0});write(n/'.aos/round.json',{'round':3,'open':True});td=n/'.aos/tasks-old/a-r1';write(td/'birth.json',{'tid':'a-r1','name':'a','round':1});write(td/'ended.json',{'round':1});write(td/'exit.json',{'code':0});write(td/'usage.json',{'tokens':1000,'calls':2})
    before=rules.snapshot_node(str(n/'.aos'));tr=tock.tock(str(s.root),'n');after=rules.snapshot_node(str(n/'.aos'))
    return {'before':before,'tock':tr,'after':after}
def disk_cost(s):
    from types import SimpleNamespace
    n=s.node();d=daemon.Daemon(str(s.root));d.timelines={'n':SimpleNamespace(node=str(n))};r=[];base=s.root/'.aosd/ctl-done';base.mkdir(parents=True,exist_ok=True);old=n/'.aos/tasks-old';old.mkdir(parents=True)
    for target in (1000,10000,30000):
        for i in range(len(list(base.iterdir())),target):(base/(str(i)+'.json')).write_text('{}');(old/str(i)).mkdir()
        samples=[]
        for _ in range(3):t=time.perf_counter();v=d.disk_usage();samples.append(time.perf_counter()-t)
        r.append({'files':target,'old_dirs':target,'seconds':samples,'disk':v})
    os.close(d.rfd);return {'samples':r,'note':'warm-cache local filesystem; synchronous main-loop scan, not an SLA'}

if __name__=='__main__':
    cases=[('error-controls',error_controls),('error-rounds',error_rounds),('runner-null-start',runner_handoff),('runner-record-eio',lambda s:runner_handoff(s,True)),('runner-identity',runner_identity),('owner-restart-manual',ownership),('owner-env-edited',lambda s:ownership(s,True)),('owner-nested3',nested),('retention-values',retention_values),('retention-reader',retention_reader),('retention-usage',retention_usage),('disk-cost',disk_cost)]
    cases += [('runner-'+p,lambda s,p=p:runner_kill(s,p)) for p in ('before-main','before-pid','after-pid','before-exit')]
    for name,fn in cases:case(name,fn)
