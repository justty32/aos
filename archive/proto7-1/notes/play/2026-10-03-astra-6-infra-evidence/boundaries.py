from common import *
from unittest import mock
import errno, types
import aos7_daemon as daemon, aos7_tick as tick, aos7_tock as tock, aos7_mount as mount

def td(n,t):return n/'.aos/tasks'/t

def restart(s,n,tid,item=None,phase='tick'):
    if item is not None:write(n/'.aos/tasks.json',{'tasks':item if isinstance(item,list) else [item]})
    write(td(n,tid)/'ctl.json',{'op':'restart','reload':True})
    out=s.run('aos7-'+phase)['out']
    return {'action':out,'receipt':read(td(n,tid)/'ctl-done.json')}

def reload_matrix(s):
    n=s.node(items=[{'name':'x','mode':'keep','argv':SLEEP+['v1']}]);s.run('aos7-tick');wait(lambda:read(td(n,'x-r1')/'pid.json'));s.run('aos7-tock')
    out=[];current='x-r1'
    for i in range(3):
        item={'name':'x','mode':'keep','max_live':1,'argv':SLEEP+['v'+str(i+2)]}
        r=restart(s,n,current,item);current=r['action']['started'][0];wait(lambda:read(td(n,current)/'pid.json'))
        r.update(birth=read(td(n,current)/'birth.json'),live=task.live_tasks(str(n)));out.append(r);s.run('aos7-tock')
    # Same-name duplicate: first is used; keep suppresses second.
    r=restart(s,n,current,[dict(item,argv=SLEEP+['first']),dict(item,argv=SLEEP+['second'])]);current=r['action']['started'][0]
    wait(lambda:read(td(n,current)/'pid.json'));r['birth']=read(td(n,current)/'birth.json');r['live']=task.live_tasks(str(n));out.append(r)
    return {'reloads':out}

def reload_spawn(s):
    n=s.node();write(n/'.aos/spawn/x.json',{'name':'x','argv':SLEEP});s.run('aos7-tick');wait(lambda:read(td(n,'x-r1')/'pid.json'));s.run('aos7-tock')
    r=restart(s,n,'x-r1');r['alive']=task.task_state(str(td(n,'x-r1')))
    s.run('aos7-tock');r2=restart(s,n,'x-r1',{'name':'x','mode':'keep','argv':SLEEP+['new']})
    return {'no_named_definition':r,'definition_added':r2}

def reload_bad(s,key,value):
    n=s.node(items=[{'name':'x','mode':'keep','argv':SLEEP}]);s.run('aos7-tick');p=wait(lambda:read(td(n,'x-r1')/'pid.json'));s.run('aos7-tock')
    item={'name':'x','mode':'keep','argv':SLEEP+['new'],key:value}
    out=restart(s,n,'x-r1',item);out.update(old_alive=task.pid_alive(p['pid']),round=read(n/'.aos/round.json'))
    return out

def reload_dyn(s):
    n=s.node(items=[{'name':'x','mode':'keep','argv':SLEEP}]);s.run('aos7-tick');wait(lambda:read(td(n,'x-r1')/'pid.json'));s.run('aos7-tock')
    mount.request(str(td(n,'x-r1')),'n/dyn');s.run('aos7-tick');s.run('aos7-tock')
    name=mount.req_name('n/dyn');old=read(td(n,'x-r1')/'birth.json')
    r1=restart(s,n,'x-r1',{'name':'x','mode':'keep','argv':SLEEP,'mounts':{name:'n/static'}})
    new=r1['action']['started'][0];wait(lambda:read(td(n,new)/'pid.json'));b1=read(td(n,new)/'birth.json');s.run('aos7-tock')
    r2=restart(s,n,new,{'name':'x','mode':'keep','argv':SLEEP,'mounts':{}});new2=r2['action']['started'][0]
    b2=read(td(n,new2)/'birth.json')
    return {'before':old['mounts'],'promoted_to_static':b1['mounts'],'removed_static_on_next_reload':b2['mounts'],'reload1':r1,'reload2':r2}

def reload_maxlive(s):
    n=s.node(items=[{'name':'x','mode':'each','max_live':2,'argv':SLEEP}]);s.run('aos7-tick');s.run('aos7-tock');s.run('aos7-tick');wait(lambda:read(td(n,'x-r2')/'pid.json'));s.run('aos7-tock')
    out=restart(s,n,'x-r1',{'name':'x','mode':'each','max_live':1,'argv':SLEEP+['new']})
    out['live']=task.live_tasks(str(n));out['note']='reload spawn explicitly strips max_live; record contract, not automatically a bug'
    return out

def ctl_poison(s):
    n=s.node();write(s.root/'.aosd/paused.json',{'paused':['n']})
    (s.root/'.aosd/ctl-done/000.json').mkdir(parents=True)
    write(s.root/'.aosd/ctl/000.json',{'op':'wake','node':'n'})
    write(s.root/'.aosd/ctl/001.json',{'op':'stop','kill':True})
    p=s.start();time.sleep(.7)
    out={'alive':p.poll() is None,'status':read(s.root/'.aosd/status.json'),'stop_receipt':read(s.root/'.aosd/ctl-done/001.json'),'pending':sorted(x.name for x in (s.root/'.aosd/ctl').iterdir())}
    (s.root/'.aosd/ctl-done/000.json').rmdir();t=time.monotonic();p.wait(8);out['after_repair_stop_ms']=round((time.monotonic()-t)*1000,1);out['rc']=p.returncode
    return out

def ctl_budget(s,count=150):
    s.node();write(s.root/'.aosd/paused.json',{'paused':['n']})
    for i in range(count):write(s.root/'.aosd/ctl'/('%05d.json'%i),{'op':'wake','node':'n'})
    write(s.root/'.aosd/ctl'/('%05d.json'%count),{'op':'stop','kill':True})
    start=time.monotonic();p=s.start();wait(lambda:read(s.root/'.aosd/ctl-done'/('%05d.json'%count)));lat=(time.monotonic()-start)*1000;p.wait(10)
    return {'wake_count':count,'stop_receipt_from_launch_ms':round(lat,1),'rc':p.returncode,'ctl_done':len(list((s.root/'.aosd/ctl-done').iterdir()))}

def stale_identity(s,unreadable=False):
    n=s.node();p=s.start(args=['sleep','60']);st=fs.proc_starttime(p.pid);write(n/'.aos/action.owner.json',{'pid':p.pid,'gen':1,'starttime':st if unreadable else st+1})
    if unreadable:
        with mock.patch.object(fs,'proc_starttime',return_value=None):k=fs.reap_stale_owner(str(n),2)
    else:k=fs.reap_stale_owner(str(n),2)
    return {'pid':p.pid,'real_starttime':st,'reaped':k,'alive':p.poll() is None,'method':'simulate proc stat unavailable' if unreadable else 'mismatched starttime simulates reused PID; no host PID manipulated'}

def fd_count(s):
    s.node();before=len(os.listdir('/proc/self/fd'))
    for _ in range(300):tick.tick(str(s.root),'n');tock.tock(str(s.root),'n')
    after=len(os.listdir('/proc/self/fd'))
    return {'tick_tock_pairs':300,'before':before,'after':after,'round':read(s.root/'n/.aos/round.json')['round']}

if __name__=='__main__':
    for name,fn in [('reload-matrix',reload_matrix),('reload-spawn',reload_spawn),('reload-dyn',reload_dyn),('reload-maxlive',reload_maxlive),('ctl-poison',ctl_poison),('ctl-budget',ctl_budget),('stale-pid-reuse',stale_identity),('stale-unreadable',lambda s:stale_identity(s,True)),('fd-count',fd_count)]:case(name,fn)
    for key,val in [('mode','nonsense'),('from_round','bad'),('max_live','bad')]:case('reload-bad-'+key,lambda s,k=key,v=val:reload_bad(s,k,v))
