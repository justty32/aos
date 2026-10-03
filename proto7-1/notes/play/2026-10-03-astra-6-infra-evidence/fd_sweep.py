from common import *
from unittest import mock
import errno, types
import aos7_daemon as daemon, aos7_tick as tick

def fd_race(s,kind,prog='aos7-tick'):
    mounts={'box':'n/inbox'} if kind=='rename-mount' else {}
    tasks=[{'name':'x','mode':'keep','argv':SLEEP,'mounts':mounts}] if kind in ('rename-mount','symlink-task') else []
    n=s.node(items=tasks);other=s.node('other');write(other/'sentinel.json',{'unchanged':True})
    if prog=='aos7-tock':write(n/'.aos/round.json',{'round':1,'open':True,'started':[],'ctl':[]})
    cfg={'prog':prog,'op':'replace' if prog=='aos7-tick' else 'append_jsonl','suffix':'/.aos/round.json' if prog=='aos7-tick' else '/rounds.jsonl','when':'before','onceglob':True,'lib':str(LIB),'marker':str(s.root/'mark.json')}
    q=s.start(prog,'n',env={'PYTHONPATH':str(OLD/'crash'),'A4_FAULT':json.dumps(cfg)});m=wait(lambda:read(s.root/'mark.json'));moved=s.root/'moved';n.rename(moved)
    if kind.startswith('symlink'):n.symlink_to(other,target_is_directory=True)
    os.kill(q.pid,signal.SIGCONT);q.wait(10);time.sleep(.15)
    before=read(moved/'.aos/round.json');out={'hook':m,'rc':q.returncode,'moved_round':before,'old_path_exists':n.exists(),'old_path_symlink':n.is_symlink(),'target_round':read(other/'.aos/round.json'),'target_sentinel':read(other/'sentinel.json')}
    if tasks:
        tid=before['started'][0];d=moved/'.aos/tasks'/tid
        out['task_files']=sorted(x.name for x in d.iterdir());out['task_state']=task.task_state(str(d))
        # no live daemon: direct tick demonstrates starting sentinel does not self-heal
        out['next_tick']=s.run('aos7-tick','moved');out['after_state']=task.task_state(str(d));out['exit']=read(d/'exit.json')
    if kind=='rename-mount':out['ghost_files']=[str(x.relative_to(n)) for x in n.rglob('*')]
    return out

def cross_fs(s):
    n=s.node();moved=s.root/'moved';err=None
    # No distinct filesystem exists inside authorized paths. Inject EXDEV at rename;
    # then exercise the actual copy+remove fallback against a held inode.
    real=os.rename
    def exdev(src,dst,*a,**kw):
        if pathlib.Path(src)==n:raise OSError(errno.EXDEV,'injected cross-device rename')
        return real(src,dst,*a,**kw)
    observations={}
    def act(fnode,node):
        nonlocal err
        with mock.patch('os.rename',exdev):
            try:os.rename(n,moved)
            except OSError as e:err=e.errno
        shutil.copytree(n,moved);shutil.rmtree(n)
        try:write(pathlib.Path(fnode)/'.aos/round.json',{'round':7})
        except OSError as e:observations['write_errno']=e.errno;raise
    out=tick.held_node(act,str(s.root),'n',{'gone':True})
    return {'real_cross_device_test':False,'method':'EXDEV injected; real copytree+rmtree while directory fd held','errno':err,'action':out,'old_path_recreated':n.exists(),'copied_round':read(moved/'.aos/round.json'),**observations}

def sweep_isolation(s):
    n=s.node();subnode=s.node('n/sub/w');outside=s.root/'unrelated';outside.mkdir()
    ps={}
    for name,node,root,tid in [('owned',n,s.root,'a'),('nested',subnode,s.root/'n/sub','b'),('foreign',outside,s.root/'unrelated','c'),('same_node_other_root',n,s.root/'different','d'),('node_no_tid',n,s.root,None)]:
        env={'AOS7_NODE':str(node),'AOS7_ROOT':str(root)}
        if tid:env['AOS7_TID']=tid
        ps[name]=s.start(args=['sleep','60'],env=env)
    time.sleep(.04);groups,clean=task.sweep_nodes([str(n)]);time.sleep(.03)
    return {'groups':groups,'clean':clean,'alive_after':{k:p.poll() is None for k,p in ps.items()},'note':'same_node_other_root explicitly supplies mismatching ROOT; Q1 identity is NODE/TID, not a security test'}

def nested_sweep(s):
    # Ended intermediate parent task left nested daemon alive; normal parent stop
    # must kill matching child daemon plus its tasks, without unrelated node.
    child=s.root/'n/sub';write(child/'w/.aos/timeline.json',{'interval_ms':100});write(child/'w/.aos/tasks.json',{'tasks':[{'name':'leaf','mode':'keep','argv':SLEEP}]})
    payload="import os,subprocess\nsubprocess.Popen(['aos7-daemon',os.environ['AOS7_SUBROOT']],start_new_session=True)\n"
    n=s.node(items=[{'name':'launch','mode':'keep','argv':[sys.executable,'-c',payload],'subroot':'n/sub'}])
    d=s.start();wait(lambda:read(child/'w/.aos/tasks/leaf-r1/pid.json'));write(n/'.aos/tasks.json',{'tasks':[]});leaf=read(child/'w/.aos/tasks/leaf-r1/pid.json')['pid'];childpid=read(child/'.aosd/status.json')['pid']
    d.terminate();d.wait(10);time.sleep(.1)
    return {'rc':d.returncode,'child_pid':childpid,'child_alive':task.pid_alive(childpid),'leaf_pid':leaf,'leaf_alive':task.pid_alive(leaf),'sweep_logs':[r for r in rows(s.root/'.aosd/log.jsonl') if r.get('ev')=='stop-sweep']}

if __name__=='__main__':
    for k in ('symlink-empty','symlink-task','rename-mount'):case('fd-'+k,lambda s,k=k:fd_race(s,k))
    case('fd-tock-symlink',lambda s:fd_race(s,'symlink-empty','aos7-tock'))
    case('fd-crossfs',cross_fs);case('sweep-isolation',sweep_isolation);case('sweep-nested',nested_sweep)
