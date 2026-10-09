"""Rerun: python3 proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/core3/c802.py"""
import sys
sys.dont_write_bytecode = True
from common import *

def replacement(c,d,old):
    # Stop only this daemon to install the replacement without a rename/mkdir scheduling gap.
    os.kill(d.pid,signal.SIGSTOP)
    (c.root/'a').rename(c.root/'old-node')
    c.node(label='new',old=old)
    os.kill(d.pid,signal.SIGCONT)

def probe(c,crash=False,fault=False):
    c.node(); d=c.daemon(); c.ctl('register')
    old=c.ready(); c.running(); time.sleep(.3)
    c.data['before']={'nodes':c.nodes(),'status':c.status(),'old':old}
    if fault:
        (c.root/'rules').write_text('proc-stat:/proc/%d/stat:EIO\n'%old['pid'])
    c.monitor(old)
    replacement(c,d,old)
    wait(lambda:'a' in c.nodes().get('reaping',{}),what='replacement reaping persisted')
    c.data['injection']={'crash':crash,'fault':fault,'pending':c.nodes()}
    if fault:
        wait(lambda:(c.root/'hits').exists(),what='proc EIO hit')
        samples=[]
        for _ in range(60):
            samples.append({'old_live':alive(old),'phase':c.status().get('nodes',{}).get('a',{}).get('phase'),
                            'new_round_exists':(c.root/'a/.aos/round.json').exists(),'reaping':c.nodes().get('reaping')})
            time.sleep(.025)
        c.data['blocked_samples']=samples
        c.check('EIO keeps old task alive',all(s['old_live'] for s in samples))
        c.check('EIO holds missing',all(s['phase']=='missing' for s in samples))
        c.check('EIO prohibits new rounds',not any(s['new_round_exists'] for s in samples))
        c.data['injection']['hits']=(c.root/'hits').read_text().splitlines()
        c.check('proc-stat EIO really hit',len(c.data['injection']['hits'])>0)
        (c.root/'rules').write_text('')
    else:
        wait(lambda:(c.root/'old.term').exists(),what='old ignored TERM')
        term=json.loads((c.root/'old.term').read_text().splitlines()[0])
        c.data['injection']['term']=term
        c.check('old is live within grace',alive(old))
        if crash:
            elapsed=time.monotonic()-term['monotonic']
            c.kill(d)
            c.data['injection'].update(kill_after_term_s=elapsed,daemon_returncode=d.returncode,
                                      old_alive_after_kill=alive(old),persisted_after_kill=c.nodes())
            c.check('crash inside grace',elapsed<1)
            c.check('daemon SIGKILL hit',d.returncode,-9)
            c.daemon()
    new=c.ready('new')
    wait(lambda:not c.nodes().get('reaping'),what='reaping cleared')
    time.sleep(.8)
    c.data.update(new=new,old_after=ident(old['pid']),after=c.nodes())
    prior=new.get('prior')
    c.check('new worker directly observes old absent/dead/reused',not prior or prior['state']=='Z' or prior['starttime']!=old['starttime'])
    c.check('old no longer live after restart',alive(old),False)
    c.check('new worker is live',alive(new))
    c.check('at least 30 consecutive observations',len(c.snapshots)>=30)
    c.check('no observed overlap',any(s['old_alive'] and s['new_alive'] for s in c.snapshots),False)

if __name__ == '__main__':
    run_cases([('c802-%s-%d'%('crash' if crash else 'control',i),lambda c,x=crash:probe(c,x))
               for crash in (True,False) for i in range(1,4)]+[('c802-eio',lambda c:probe(c,fault=True))])
