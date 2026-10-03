from common import *
PREV=OUT.parent/'2026-10-03-astra-6-infra-evidence'
b=load('old_boundaries',PREV/'boundaries.py');f=load('old_fd',PREV/'fd_sweep.py');e=load('old_extra',PREV/'extra_faults.py');r=load('old_recovery',PREV/'recovery_edges.py');o=load('old_ownership',PREV/'ownership.py');l=load('old_legacy',PREV/'legacy.py')

def collision(s):
    sub=s.root/'n/inner/sub';s.node(items=[{'name':'first','mode':'keep','argv':['aos7-daemon','$AOS7_SUBROOT'],'subroot':'n/inner/sub','allow_stop':False}]);d=s.start();st=wait(lambda:read(sub/'.aosd/status.json'));before=read(sub/'.aosd/owner.json')
    n=s.node('n/inner',items=[{'name':'second','mode':'keep','argv':['aos7-daemon','$AOS7_SUBROOT'],'subroot':'n/inner/sub','allow_stop':True}]);time.sleep(.6)
    write(sub/'.aosd/ctl/stop.json',{'op':'stop','kill':True});receipt=wait(lambda:read(sub/'.aosd/ctl-done/stop.json'))
    return {'before':before,'after':read(sub/'.aosd/owner.json'),'same_daemon_pid':st['pid']==read(sub/'.aosd/status.json')['pid'],'round':read(n/'.aos/round.json'),'receipt':receipt}

def wrapped(fn):
    def run(s):
        tempfile.tempdir=str(s.root)
        try:return fn(s)
        finally:tempfile.tempdir=None
    return run
if __name__=='__main__':
    for name,fn in [('G01-ctl',b.ctl_poison),('G02-rename',lambda s:f.fd_race(s,'rename-mount')),('G02-symlink',lambda s:f.fd_race(s,'symlink-task')),('G03-parent-move',o.parent_move),('G04-collision',collision),('G06-dyn',b.reload_dyn),('G07-atexit',r.cleanup_atexit),('G08-partial',e.partial_summary),('G09-owner-edit',o.owner_task_edit),('G09-delete-mark',o.child_deletes_mark),('G09-syntax',o.owner_syntax),('G10-unverified',r.unknown_owner),('G10-reuse',b.stale_identity),('G10-proc-error',lambda s:b.stale_identity(s,True)),('F05-replay',lambda s:l.replay(s,False)),('F05-timeout',lambda s:l.replay(s,True)),('F09-tock-symlink',lambda s:f.fd_race(s,'symlink-empty','aos7-tock')),('F11-agent-delayed',wrapped(l.delayed_agent)),('F11-demo-eio',wrapped(l.demo_eio))]:case(name,fn)
    for key,val in [('mode','nonsense'),('from_round','bad'),('max_live','bad')]:case('G05-'+key,lambda s,k=key,v=val:b.reload_bad(s,k,v))
