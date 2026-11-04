from common import *

def bad_types(s):
    bad=[None,0,1,'true',[],{}]
    items=[{'name':'bad'+str(i),'argv':SLEEP,'allow_stop':v,'subroot':'n/s'+str(i)} for i,v in enumerate(bad)]
    n=s.node(items=items+[{'name':'healthy','argv':['/bin/true']}]);write(n/'.aos/spawn/batch.json',{'batch':[dict(x,name='spawn-'+x['name']) for x in items]+[{'name':'spawn-healthy','argv':['/bin/true']}]})
    out=s.run('aos7-tick');return {'action':out,'round':read(n/'.aos/round.json'),'bad_subroots_created':[x['subroot'] for x in items if (s.root/x['subroot']/'.aosd').exists()]}

def all_stopped(s):
    item={'argv':SLEEP,'subroot':'n/sub','allow_stop':True}
    n=s.node(items=[dict(item,name='each',mode='each'),dict(item,name='keep',mode='keep')]);write(n/'sub/.aosd/stopped.json',{'by':'probe','why':'must stay stopped'})
    write(n/'.aos/spawn/one.json',dict(item,name='spawn'))
    d=n/'.aos/tasks/old-r1';write(d/'birth.json',dict(item,name='old',tid='old-r1',round=1));write(d/'exit.json',{'code':0});write(d/'ctl.json',{'op':'restart'})
    out=s.run('aos7-tick');return {'action':out,'round':read(n/'.aos/round.json'),'task_dirs':sorted(x.name for x in (n/'.aos/tasks').iterdir()),'owner':read(n/'sub/.aosd/owner.json')}

if __name__=='__main__':case('allow-stop-types',bad_types);case('stopped-all-modes',all_stopped)
