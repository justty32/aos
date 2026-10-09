"""Rerun: python3 proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/core3/r829.py

Bounded real setsid allocation attempts, then explicitly simulated stale ledger
points at a real foreign group; also the blueprint's _table/environ mock case.
"""
import sys
sys.dont_write_bytecode = True
from common import *
from unittest import mock

def probe(c):
    sys.path.insert(0,str(LIB))
    import aos7_proc as proc
    node=str(c.root/'a')
    owned_env=dict(c.env,AOS7_ROOT=str(c.root),AOS7_NODE=node,AOS7_TID='s',AOS7_RUN='1')
    original=c.start(['sleep','600'],env=owned_env,name='original')
    first=ident(original.pid); c.kill(original)
    attempts=[]
    foreign=None
    for _ in range(8):
        p=c.start(['sleep','600'],name='foreign')
        attempts.append(ident(p.pid))
        if p.pid==first['pgid']:
            foreign=p; break
        if len(attempts)<8:c.kill(p)
        else:foreign=p
    outsider=ident(foreign.pid)
    owned=c.start(['sleep','600'],env=owned_env,name='owned-control')
    owner=ident(owned.pid)
    calls=[]
    real_signal=proc._signal
    def record(groups,sig):
        calls.append({'groups':sorted(groups),'signal':int(sig)})
        return real_signal(groups,sig)
    with mock.patch.object(proc,'_signal',record):
        result=proc.kill_node(node,[foreign.pid,owned.pid])
    c.data['injection']={'original_identity':first,'setsid_attempts':attempts,'same_number_obtained':foreign.pid==first['pgid'],
                         'fallback':'mock of remembered pgid ledger only; /proc and signalling real',
                         'foreign':outsider,'owned':owner,'signal_calls':calls,'kill_node_result':result}
    c.check('unrelated live group excluded from signals',all(foreign.pid not in s['groups'] for s in calls))
    c.check('foreign PID/starttime survives',alive(outsider))
    c.check('owned control group was really signalled',any(owned.pid in s['groups'] for s in calls))
    c.check('owned control collected',alive(owner),False)
    c.check('collection returns clean',result[1])
    fake=12345678; signals=[]
    with mock.patch.object(proc,'_table',return_value={fake:('S',1,fake)}), \
         mock.patch.object(proc,'environ_of',return_value={b'OTHER=foreign'}), \
         mock.patch.object(proc,'env_procs',return_value=[]), \
         mock.patch.object(proc,'me_and_ancestors',return_value=set()), \
         mock.patch.object(proc,'_signal',side_effect=lambda g,s:signals.append([list(g),int(s)])):
        result=proc.kill_node(node,[fake])
    c.data['blueprint_mock']={'table':{fake:['S',1,fake]},'environment':['OTHER=foreign'],'signals':signals,'result':result}
    c.check('blueprint mock never calls signal',signals,[])

if __name__=='__main__':run_cases([('r829',probe)])
