from common import *
from boundaries import ctl,status

def controls(s):
    n=s.node(items=[{'name':'stay','mode':'keep','argv':SLEEP}],action_timeout_s=2);d=s.start();wait(lambda:read(n/'.aos/tasks/stay-r1/pid.json'));wait(lambda:read(n/'.aos/round.json',{}).get('round',0)>=3)
    single=s.start();single.wait(5)
    pause=ctl(s.root,'pause',node='n');wait(lambda:status(s)['nodes']['n']['phase']=='paused');r1=read(n/'.aos/round.json');pid=read(n/'.aos/tasks/stay-r1/pid.json')['pid'];time.sleep(.25);r2=read(n/'.aos/round.json');live=task.pid_alive(pid)
    resume=ctl(s.root,'resume',node='n',rounds=2);wait(lambda:status(s)['nodes']['n']['phase']=='paused' and status(s)['nodes']['n']['round']>=r1['round']+2);r3=read(n/'.aos/round.json')
    # Task ctl waits on a paused node; resume causes tick/tock to process it.
    td=n/'.aos/tasks/stay-r1';write(td/'ctl.json',{'op':'kill'});time.sleep(.2);pending=(td/'ctl.json').exists() and task.pid_alive(pid)
    ctl(s.root,'resume',node='n',rounds=1);receipt=wait(lambda:read(td/'ctl-done.json'));wait(lambda:not task.pid_alive(pid));ctl(s.root,'stop',kill=True);d.wait(10)
    return {'D02_single_daemon_rc':single.returncode,'D03_pause':{'receipt':pause,'same_round':r1['round']==r2['round'],'closed':r2['open'] is False,'task_survived':live},'D04_resume_n':{'receipt':resume,'before':r1['round'],'after':r3['round'],'delta':r3['round']-r1['round']},'D06_task_ctl_paused':{'pending_until_resume':pending,'receipt':receipt,'task_dead':not task.pid_alive(pid)},'D05_keep_cross_round':{'birth_tid':'stay-r1','round_before_pause':r1['round'],'tock':read(td/'tock.json')}}
def discovery(s):
    d=s.start();wait(lambda:status(s).get('pid'));samples=[]
    for i in range(15):
        nid='n'+str(i);n=s.root/nid;write(n/'.aos/tasks.json',{'tasks':[]});t=time.perf_counter();write(n/'.aos/timeline.json',{'interval_ms':1000})
        while not (n/'.aos/round.json').exists():
            if time.perf_counter()-t>3:raise TimeoutError('node not picked up')
            time.sleep(.0005)
        samples.append((time.perf_counter()-t)*1000)
    ctl(s.root,'stop',kill=True);d.wait(10);logs=rows(s.root/'.aosd/log.jsonl')
    return {'D01_new_node_ms_until_first_round_json':samples,'all_nodes_discovered':len([r for r in logs if r.get('ev')=='node+']),'note':'upper endpoint includes tick process start/write; the docs say 1-2ms detection, not this whole interval'}
def discovery_scan(s):
    # Creation immediately after observed status publication approximates early poll sleep.
    d=s.start();wait(lambda:status(s).get('pid'));results=[]
    for i in range(10):
        nid='probe'+str(i);n=s.root/nid;write(n/'.aos/tasks.json',{'tasks':[]});at=status(s)['at'];wait(lambda:status(s)['at']!=at)
        t=time.perf_counter();write(n/'.aos/timeline.json',{'interval_ms':1000})
        while not any(r.get('ev')=='node+' and r.get('node')==nid for r in rows(s.root/'.aosd/log.jsonl')):
            if time.perf_counter()-t>3:raise TimeoutError('node+')
            time.sleep(.0005)
        results.append((time.perf_counter()-t)*1000)
    ctl(s.root,'stop',kill=True);d.wait(10);return {'D01_create_to_node_plus_ms':results,'polling_resolution_ms':.5}
def task_table(s):
    n=s.node(items=[{'name':'broken','argv':123},{'name':'each','argv':['true']},{'name':'stay','mode':'keep','argv':SLEEP}]);write(n/'.aos/spawn/once.json',{'name':'once','argv':['true']})
    rounds=[]
    for i in range(3):
        tr=s.run('aos7-tick');wait(lambda:read(n/f'.aos/tasks/each-r{i+1}/exit.json'));rounds.append({'tick':tr,'tock':s.run('aos7-tock')})
    return {'D07_spawn_each_isolation':rounds,'spawn_consumed':not(n/'.aos/spawn/once.json').exists(),'task_names':sorted(x.name for x in (n/'.aos/tasks').iterdir())}
def mounts(s):
    body="import os,json;from pathlib import Path;p=Path(os.environ['AOS7_TASK']);(p/'observed.json').write_text(json.dumps({'cwd':os.getcwd(),'env':{k:v for k,v in os.environ.items() if k.startswith('AOS7_')},'mounted':(p/'mnt/peer').is_dir()}))"
    n=s.node('team/n',items=[{'name':'record','argv':[sys.executable,'-c',body],'mounts':{'peer':'peer/inbox'}}]);r=s.run('aos7-tick','team/n');td=n/'.aos/tasks/record-r1';obs=wait(lambda:read(td/'observed.json'));return {'D08_mount_env':obs,'birth':read(td/'birth.json'),'mount_target':os.readlink(td/'mnt/peer'),'tick':r}
def node_gone(s):
    n=s.node(items=[{'name':'stay','mode':'keep','argv':SLEEP}]);d=s.start();pid=wait(lambda:read(n/'.aos/tasks/stay-r1/pid.json'))['pid'];(n/'.aos/timeline.json').unlink();wait(lambda:not task.pid_alive(pid));ctl(s.root,'stop',kill=True);d.wait(10)
    return {'D09_timeline_removed':{'pid':pid,'dead':not task.pid_alive(pid),'gone_log':[x for x in rows(s.root/'.aosd/log.jsonl') if x.get('ev') in ('node-','node-gone-kill')]}}
def archiving(s):
    n=s.node();write(n/'.aos/timeline.json',{'keep_ended_rounds':0});write(n/'.aos/tasks.json',{'tasks':[{'name':'one','argv':['true']}]});results=[]
    for i in range(1,4):
        s.run('aos7-tick');wait(lambda:read(n/f'.aos/tasks/one-r{i}/exit.json'));results.append(s.run('aos7-tock')['out'])
    return {'D10_default_archive':{'summaries':results,'active':sorted(x.name for x in (n/'.aos/tasks').iterdir()),'old':sorted(x.name for x in (n/'.aos/tasks-old').iterdir())}}
if __name__=='__main__':
    for name,fn in [('docs-controls',controls),('docs-discovery',discovery),('docs-scan-latency',discovery_scan),('docs-task-table',task_table),('docs-mounts',mounts),('docs-node-gone',node_gone),('docs-archive',archiving)]:case(name,fn)
