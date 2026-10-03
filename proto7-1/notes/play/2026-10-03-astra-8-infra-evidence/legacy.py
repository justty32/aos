from common import *
PREV=OUT.with_name('2026-10-03-astra-7-infra-evidence')
e=load('r7edges',PREV/'edges.py');j=load('r7jsonl',PREV/'jsonl_edges.py');f=load('r7follow',PREV/'followup.py');l=load('r7legacy',PREV/'legacy.py');c=load('r7claim',PREV/'claim_batch.py')
def batch(s):
    # Same 12 batches as R7; no longer wait for a losing runner that H02 now refuses to start.
    runs=[]
    for i in range(12):
        nid=f'n{i}';sub=nid+'/sub'
        n=s.node(nid,items=[{'name':name,'argv':['aos7-daemon','$AOS7_SUBROOT'],'subroot':sub,'allow_stop':allow} for name,allow in [('first',False),('second',True)]])
        r=s.run('aos7-tick',nid);st=wait(lambda:read(s.root/sub/'.aosd/status.json'));ow=read(s.root/sub/'.aosd/owner.json')
        pj=wait(lambda:read(n/'.aos/tasks/first-r1/pid.json'))
        runs.append({'started':r['out']['started'],'owner':ow,'actual_pid':pj['pid'],'matches':ow['daemon_pid']==st['pid']==pj['pid'],'tasks_error':read(n/'.aos/round.json').get('tasks_error')})
        os.kill(st['pid'],signal.SIGTERM);wait(lambda:read(n/'.aos/tasks/first-r1/exit.json'))
    return {'runs':runs,'matches':sum(r['matches'] for r in runs)}
if __name__=='__main__':
    for name,fn in [('H01-readback',lambda s:e.readback(s,True)),('H01-torn',f.readback_torn),('H02-race',e.claim_race),('H02-batch',batch),('H03-H04-jsonl',j.logs),('H05-late-move',j.late_move),('H06-out',f.out_poison),('H07-collision',e.ctl),('H09-fd',e.runner),('G01-ctl',l.b.ctl_poison),('G02-rename',lambda s:l.f.fd_race(s,'rename-mount')),('G02-symlink',lambda s:l.f.fd_race(s,'symlink-task')),('G04-collision',l.collision),('G04-existing',c.same_node_existing),('G08-partial',l.e.partial_summary)]:case(name,fn)
