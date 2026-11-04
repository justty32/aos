"""Rerun: python3 proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/core3/edges.py"""
import sys
sys.dont_write_bytecode = True
from common import *
import fcntl
from c802 import replacement

def corrupt(c,value):
    p=c.root/'.aosd/nodes.json'
    p.parent.mkdir()
    raw=value if isinstance(value,str) else json.dumps(value)
    p.write_text(raw)
    d=c.start([sys.executable,BIN/'aos7-daemon',c.root],name='bad-state-daemon')
    code=d.wait(10)
    c.data['injection']={'nodes_raw':raw,'exit':code,'source':'explicit simulated disk corruption; no live state edited'}
    c.check('corrupt durable state refuses startup',code,3)
    c.check('corrupt state not overwritten',p.read_text(),raw)
    c.check('no status pretending startup succeeded',not (c.root/'.aosd/status.json').exists())
    c.data['classification']='X: fault refused safely'

def repeat(c):
    node=c.node(); d=c.daemon(); c.ctl('register')
    old=c.ready(); c.running()
    (c.root/'rules').write_text('proc-stat:/proc/%d/stat:EIO\n'%old['pid'])
    c.check('first unregister accepted',c.ctl('unregister')['ok'])
    wait(lambda:'a' in c.nodes().get('reaping',{}),what='obligation')
    c.check('duplicate unregister accepted',c.ctl('unregister')['ok'])
    with open(node/'.aos/tasks.json.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        tasks=read(node/'.aos/tasks.json')
        tasks['tasks'][0]['argv']=[sys.executable,str(HERE/'worker.py'),str(c.root/'new.ready'),str(c.root/'new.term'),json.dumps(old)]
        write(node/'.aos/tasks.json',tasks)
    c.check('register same id while reaping accepted',c.ctl('register')['ok'])
    c.check('duplicate register accepted',c.ctl('register')['ok'])
    c.monitor(old)
    time.sleep(.5)
    c.data['during']={'nodes':c.nodes(),'status':c.status(),'old':ident(old['pid'])}
    c.check('registry and obligation coexist','a' in c.nodes()['nodes'] and 'a' in c.nodes()['reaping'])
    c.check('re-registration cannot launch through obligation',not (c.root/'new.ready').exists())
    c.check('old task preserved while scan unknown',alive(old))
    c.data['injection']={'hits':(c.root/'hits').read_text().splitlines()}
    (c.root/'rules').write_text('')
    new=c.ready('new'); time.sleep(.7)
    prior=new.get('prior')
    c.check('reregistered generation starts after old dead',not prior or prior['state']=='Z' or prior['starttime']!=old['starttime'])
    c.check('no observed overlap',not any(s['old_alive'] and s['new_alive'] for s in c.snapshots))
    c.check('same slot moves to generation 2',new['run'],'2')
    c.data['classification']='X: repeat requests/reaping recover safely'

def twice(c):
    c.node(); d=c.daemon(); c.ctl('register')
    old=c.ready(); c.running(); c.monitor(old)
    replacement(c,d,old)
    crashes=[]
    for n in (1,2):
        wait(lambda:(c.root/'old.term').exists() and len((c.root/'old.term').read_text().splitlines())>=n,what='TERM for crash %d'%n)
        t=json.loads((c.root/'old.term').read_text().splitlines()[-1])
        elapsed=time.monotonic()-t['monotonic']
        pending=c.nodes()
        c.kill(d)
        crashes.append({'daemon':d.pid,'returncode':d.returncode,'after_TERM_s':elapsed,'old_alive':alive(old),'nodes':pending})
        c.check('crash%d inside grace'%n,elapsed<1)
        c.check('crash%d retains obligation'%n,'a' in pending.get('reaping',{}))
        c.check('crash%d old still live'%n,alive(old))
        d=c.daemon()
    new=c.ready('new'); time.sleep(.7)
    c.data['injection']={'crashes':crashes}
    c.check('third daemon collects old',alive(old),False)
    c.check('third daemon starts new',alive(new))
    c.check('continuous observations never overlap',not any(s['old_alive'] and s['new_alive'] for s in c.snapshots))
    wait(lambda:not c.nodes().get('reaping'),what='third daemon clears obligation')
    c.data['classification']='X: repeated crash recovers safely'

def stop_pending(c,fault=False):
    c.node(); d=c.daemon(); c.ctl('register')
    old=c.ready(); c.running()
    if fault:
        (c.root/'rules').write_text('proc-stat:/proc/%d/stat:EIO\n'%old['pid'])
    c.ctl('unregister')
    pending=c.nodes()
    c.check('stop setup has unregistered reaping obligation','a' in pending.get('reaping',{}) and 'a' not in pending['nodes'])
    c.check('stop --kill accepted',c.ctl('stop',node=None,kill=True)['ok'])
    c.check('daemon finishes stop',d.wait(20),0)
    c.data['stopped']={'nodes':c.nodes(),'status':c.status(),'old':ident(old['pid'])}
    if fault:
        c.check('unknown scan preserves obligation across stop','a' in c.nodes().get('reaping',{}))
        c.check('fault really blocked collection',alive(old))
        c.data['injection']={'hits':(c.root/'hits').read_text().splitlines()}
        (c.root/'rules').write_text('')
        c.daemon()
        wait(lambda:not alive(old),what='restart after unknown stop collects')
    else:
        c.check('healthy stop kills old task',alive(old),False)
    wait(lambda:not c.nodes().get('reaping'),what='stop/restart clears obligation')
    c.data['classification']='X: stop preserves unknown obligation and resumes safely' if fault else 'normal stop collected'

def restart_unknown(c):
    c.node(); d=c.daemon(); c.ctl('register')
    old=c.ready(); c.running()
    (c.root/'rules').write_text('proc-stat:/proc/%d/stat:EIO\n'%old['pid'])
    replacement(c,d,old)
    wait(lambda:c.status().get('nodes',{}).get('a',{}).get('phase')=='missing',what='missing before crash')
    c.kill(d); c.daemon()
    samples=[]
    for _ in range(40):
        samples.append({'phase':c.status().get('nodes',{}).get('a',{}).get('phase'),
                        'old_alive':alive(old),'round_exists':(c.root/'a/.aos/round.json').exists(),
                        'reaping':c.nodes().get('reaping')})
        time.sleep(.025)
    c.data['injection']={'hits':(c.root/'hits').read_text().splitlines(),'daemon_crashed':True}
    c.data['restart_samples']=samples
    c.check('pending reaping remains missing after restart',all(s['phase']=='missing' for s in samples))
    c.check('restart with unknown scan does not start rounds',not any(s['round_exists'] for s in samples))
    c.check('unknown restart keeps old alive',all(s['old_alive'] for s in samples))
    (c.root/'rules').write_text('')
    new=c.ready('new')
    c.check('withdrawal recovers safely',alive(new) and not alive(old))

if __name__=='__main__':
    run_cases([('edge-truncated',lambda c:corrupt(c,'{"nodes":{},"reaping":{"a":')),
               ('edge-reaping-type-list',lambda c:corrupt(c,{'nodes':{},'reaping':[]})),
               ('edge-reaping-type-null',lambda c:corrupt(c,{'nodes':{},'reaping':None})),
               ('edge-repeat-register',repeat),('edge-double-crash',twice),
               ('edge-stop-pending',stop_pending),('edge-stop-pending-eio',lambda c:stop_pending(c,True)),
               ('edge-restart-unknown',restart_unknown)])
