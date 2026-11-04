"""Rerun: python3 proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/core3/c801.py"""
import sys
sys.dont_write_bytecode = True
from common import *

def probe(c, crash):
    c.node()
    d=c.daemon(); c.ctl('register')
    task=c.ready(); c.running()
    c.data['before']=c.nodes()
    rec=c.ctl('unregister')
    pending=c.nodes()
    wait(lambda:(c.root/'old.term').exists(),what='ignored TERM')
    term=json.loads((c.root/'old.term').read_text().splitlines()[0])
    c.data['injection']={'crash':crash,'term':term,'task_alive_at_receipt':alive(task),'pending':pending}
    c.check('unregister accepted',rec['ok'])
    c.check('registry removes id before receipt','a' not in pending['nodes'])
    c.check('durable reaping at receipt','a' in pending.get('reaping',{}))
    c.check('TERM-resistant task still live in grace',alive(task))
    if crash:
        elapsed=time.monotonic()-term['monotonic']
        c.kill(d)
        c.data['injection'].update(kill_after_term_s=elapsed,daemon_returncode=d.returncode,
                                   task_alive_after_daemon_kill=alive(task),durable_after_kill=c.nodes())
        c.check('SIGKILL within one second grace',elapsed<1)
        c.check('daemon terminated by SIGKILL',d.returncode,-9)
        c.check('task survives daemon SIGKILL',alive(task))
        c.daemon()
    wait(lambda:not alive(task),what='old PID reaped')
    wait(lambda:not c.nodes().get('reaping'),what='reaping obligation removed')
    c.data.update(task_before=task,task_after=ident(task['pid']),after=c.nodes())
    c.check('old PID/starttime no longer non-zombie live',alive(task),False)
    c.check('reaping cleared only after collection',c.nodes().get('reaping',{}),{})
    c.check('unregistered node not relaunched',scan(root=c.root),[])

if __name__ == '__main__':
    run_cases([('c801-%s-%d'%('crash' if crash else 'control',i),lambda c,x=crash:probe(c,x))
               for crash in (True,False) for i in range(1,4)])
