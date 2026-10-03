from common import *
import aos7_daemon as daemon

def subitem(name='child',sub='n/sub',allow=False):return {'name':name,'mode':'keep','argv':['aos7-daemon','$AOS7_SUBROOT'],'subroot':sub,'allow_stop':allow}
def status(root):return read(root/'.aosd/status.json',{}) or {}
def ctl(root,name,**obj):
    write(root/'.aosd/ctl'/(name+'.json'),obj)
    return wait(lambda:read(root/'.aosd/ctl-done'/(name+'.json')))['result']
def setup(s,allow=False):
    n=s.node(items=[subitem(allow=allow)]);p=s.start();sub=n/'sub';wait(lambda:status(sub).get('pid'));return n,p,sub

def owner_bad(s):
    n,p,sub=setup(s);path=sub/'.aosd/owner.json';original=read(path);out=[]
    for i,v in enumerate([{},[],None,{'allow_stop':'true'},{'allow_stop':1},{'allow_stop':True}]):
        write(path,v);r=ctl(sub,str(i),op='stop',kill=True);out.append({'owner':v,'result':r})
    wait(lambda:status(sub).get('stopped'));return {'original':original,'cases':out,'mark':read(sub/'.aosd/stopped.json')}

def owner_syntax(s):
    n,p,sub=setup(s);path=sub/'.aosd/owner.json';path.write_text('{broken');r=ctl(sub,'bad',op='stop',kill=True)
    path.unlink();r2=ctl(sub,'missing',op='stop',kill=True);wait(lambda:status(sub).get('stopped'));time.sleep(.4)
    return {'corrupt_receipt':r,'missing_receipt':r2,'stopped_marker_exists':(sub/'.aosd/stopped.json').exists(),'later_gen':read(sub/'.aosd/gen.json'),'later_status':status(sub)}

def owner_task_edit(s):
    n,p,sub=setup(s)
    payload="import os,json;from pathlib import Path;p=Path(os.environ['AOS7_ROOT'])/'.aosd/owner.json';x=json.loads(p.read_text());x['allow_stop']=True;p.write_text(json.dumps(x));(p.parent/'edited').write_text('by child task')"
    write(sub/'w/.aos/timeline.json',{'interval_ms':100});write(sub/'w/.aos/tasks.json',{'tasks':[{'name':'edit','mode':'keep','argv':[sys.executable,'-c',payload]}]})
    wait(lambda:(sub/'.aosd/edited').exists());r=ctl(sub,'stop',op='stop',kill=True)
    wait(lambda:status(sub).get('stopped'));return {'parent_definition':read(n/'.aos/tasks.json'),'effective_owner':read(sub/'.aosd/owner.json'),'receipt':r,'stopped':read(sub/'.aosd/stopped.json')}

def child_deletes_mark(s):
    n,p,sub=setup(s,True)
    payload="import os,time;from pathlib import Path;p=Path(os.environ['AOS7_ROOT'])/'.aosd/stopped.json'\nwhile not p.exists():time.sleep(.005)\np.unlink()\n(p.parent/'deleted-by-child').write_text('yes')\n"
    write(sub/'w/.aos/timeline.json',{'interval_ms':100});write(sub/'w/.aos/tasks.json',{'tasks':[{'name':'erase','mode':'keep','argv':[sys.executable,'-c',payload]}]})
    wait(lambda:read(sub/'w/.aos/tasks/erase-r1/pid.json'));g=status(sub)['gen'];r=ctl(sub,'stop',op='stop',kill=False)
    wait(lambda:(sub/'.aosd/deleted-by-child').exists());wait(lambda:status(sub).get('gen',0)>g)
    return {'receipt':r,'before_gen':g,'after_gen':status(sub)['gen'],'marker_exists':(sub/'.aosd/stopped.json').exists(),'deletion_by_real_child_task':True}

def duplicate_owner(s):
    n,p,sub=setup(s,False);initial=status(sub);ow1=read(sub/'.aosd/owner.json')
    write(n/'.aos/spawn/second.json',subitem('other','n/sub',True));wait(lambda:(read(sub/'.aosd/owner.json',{}) or {}).get('tid','').startswith('other-'))
    ow2=read(sub/'.aosd/owner.json');wait(lambda:read(n/'.aos/tasks'/ow2['tid']/'exit.json'))
    later=status(sub);r=ctl(sub,'stop',op='stop',kill=True)
    return {'original_owner':ow1,'replacement_owner':ow2,'running_pid_before':initial['pid'],'running_pid_after_failed_second_start':later['pid'],'second_exit':read(n/'.aos/tasks'/ow2['tid']/'exit.json'),'receipt':r}

def parent_move(s):
    n,p,sub=setup(s,True);oldpid=status(sub)['pid'];m=s.root/'m';n.rename(m)
    # Keep follows Q4 after owner node rename; update root-relative subroot in moved tasks definition.
    write(m/'.aos/tasks.json',{'tasks':[subitem(sub='m/sub',allow=True)]})
    wait(lambda:any(x.get('ev')=='node-' and x.get('node')=='n' for x in rows(s.root/'.aosd/log.jsonl')))
    wait(lambda:status(m/'sub').get('pid') not in (None,oldpid));time.sleep(.15)
    return {'old_child_pid':oldpid,'old_child_alive':task.pid_alive(oldpid),'old_path_recreated':n.exists(),'old_path_files':[str(x.relative_to(n)) for x in n.rglob('*') if x.is_file()] if n.exists() else [],'new_owner':read(m/'sub/.aosd/owner.json'),'new_status':status(m/'sub'),'parent_events':[x for x in rows(s.root/'.aosd/log.jsonl') if x.get('ev') in ('node+','node-','node-gone-kill')]}

def nested_owner(s):
    n=s.node(items=[subitem(allow=True)]);sub=n/'sub';write(sub/'x/.aos/timeline.json',{'interval_ms':100});write(sub/'x/.aos/tasks.json',{'tasks':[subitem('deep','x/deep',False)]})
    deep=sub/'x/deep';write(deep/'z/.aos/timeline.json',{'interval_ms':100});write(deep/'z/.aos/tasks.json',{'tasks':[{'name':'leaf','mode':'keep','argv':SLEEP}]})
    p=s.start();wait(lambda:status(deep).get('nodes',{}).get('z',{}).get('live'));pids=[status(sub)['pid'],status(deep)['pid'],read(deep/'z/.aos/tasks/leaf-r1/pid.json')['pid']]
    before={'middle':read(sub/'.aosd/owner.json'),'deep':read(deep/'.aosd/owner.json')}
    denied=ctl(deep,'stop-deep',op='stop',kill=True);accepted=ctl(sub,'stop-middle',op='stop',kill=True)
    wait(lambda:not task.pid_alive(pids[0]));time.sleep(.2)
    return {'owners':before,'deep_stop':denied,'middle_stop':accepted,'pids':pids,'alive_after':[task.pid_alive(x) for x in pids],'middle_marker':read(sub/'.aosd/stopped.json'),'deep_marker':read(deep/'.aosd/stopped.json')}

if __name__=='__main__':
    for name,fn in [('owner-bad',owner_bad),('owner-syntax-missing',owner_syntax),('owner-task-edit',owner_task_edit),('child-deletes-mark',child_deletes_mark),('duplicate-owner',duplicate_owner),('parent-move',parent_move),('nested-owner',nested_owner)]:case(name,fn)
