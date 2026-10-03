from common import *
def batch(s):
    runs=[]
    for i in range(12):
        nid=f'n{i}';sub=nid+'/sub'
        n=s.node(nid,items=[{'name':name,'argv':['aos7-daemon','$AOS7_SUBROOT'],'subroot':sub,'allow_stop':allow} for name,allow in [('first',False),('second',True)]])
        result=s.run('aos7-tick',nid);st=wait(lambda:read(s.root/sub/'.aosd/status.json'))
        wait(lambda:any(read(n/'.aos/tasks'/tid/'exit.json') for tid in result['out']['started']))
        owner=read(s.root/sub/'.aosd/owner.json');pidfiles={tid:read(n/'.aos/tasks'/tid/'pid.json') for tid in result['out']['started']};actual=next((tid for tid,pj in pidfiles.items() if pj and pj['pid']==st['pid']),None)
        runs.append({'case':i,'started':result['out']['started'],'owner':owner,'actual_tid':actual,'owner_mismatch':owner['tid']!=actual,'exits':{tid:read(n/'.aos/tasks'/tid/'exit.json') for tid in result['out']['started']}})
        # PID-targeted normal stop, wait for the child daemon's runner to publish exit.
        os.kill(st['pid'],signal.SIGTERM);wait(lambda:read(n/'.aos/tasks'/actual/'exit.json'))
    return {'unmodified_product':True,'no_fault_hook':True,'runs':runs,'mismatches':sum(x['owner_mismatch'] for x in runs),'iterations':len(runs)}

def same_node_existing(s):
    n=s.node(items=[{'name':'first','mode':'keep','argv':['aos7-daemon','$AOS7_SUBROOT'],'subroot':'n/sub','allow_stop':False}]);d=s.start();sub=s.root/'n/sub';st=wait(lambda:read(sub/'.aosd/status.json'));before=read(sub/'.aosd/owner.json')
    write(n/'.aos/spawn/second.json',{'name':'other','argv':['aos7-daemon','$AOS7_SUBROOT'],'subroot':'n/sub','allow_stop':True})
    wait(lambda:not(n/'.aos/spawn/second.json').exists());time.sleep(.1)
    return {'before':before,'after':read(sub/'.aosd/owner.json'),'same_pid':st['pid']==read(sub/'.aosd/status.json')['pid'],'errors':[e for r in rows(n/'.aos/rounds.jsonl') for e in r.get('tasks_error',[])]}
if __name__=='__main__':
    case('claim-natural-batch',batch);case('G04-same-node-existing',same_node_existing)
