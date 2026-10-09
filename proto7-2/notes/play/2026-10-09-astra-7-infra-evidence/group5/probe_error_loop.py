"""100 full error-loop iterations and independent giant-pointer historical comparison.
Re-run: systemd-run --user --scope -q -p TasksMax=800 -p RuntimeMaxSec=1800 python3 proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/group5/probe_error_loop.py
"""
from common import *
from unittest.mock import patch
import errno
import aos7_fs as fs, aos7_daemon_timeline as tm
from aos7_daemon import Daemon
h=Harness('error-loop')

def hundred():
    n=h.node('bad');d=Daemon(str(h.root));t=tm.Timeline(d,'bad',None);hit=[];waits=[];rounds=[];original=t.backoff;ow=t.wake.wait
    def fault(op,path):
        if op=='open' and str(path)==str(n/'.aos/round.json'):
            hit.append([op,str(path)]);raise OSError(errno.EIO,'persistent group5 error')
    def backoff():
        t.wake.set();original();rounds.append(t.phase)
        if len(rounds)==100:d.stopping=True
    def wait_call(timeout):waits.append(timeout);return ow(timeout)
    start=time.monotonic();cpu=time.process_time()
    try:
        with patch.object(fs,'inject',side_effect=fault),patch.object(tm,'RECOVER_BACKOFF_MAX',.02),patch.object(t,'backoff',side_effect=backoff),patch.object(t.wake,'wait',side_effect=wait_call):t._loop()
        elapsed=time.monotonic()-start;used=time.process_time()-cpu
        assert len(rounds)==100 and len(hit)==100 and set(rounds)=={'error'} and len(waits)<=300 and used<.5 and elapsed>=1.8
        return {'injection':{'open_round_EIO_hits':len(hit),'wake_set_each_backoff':True,'backoff_cap_s':.02},'assertion':'full production loop executes exactly 100 unknown/error/backoff cycles, never opens round, low CPU and bounded waits','error_cycles':len(rounds),'wait_calls':len(waits),'wall_s':elapsed,'cpu_s':used,'round_file_exists':(n/'.aos/round.json').exists(),'last_error':t.last_error}
    finally:os.close(d.rfd)

def old_pointer():
    import aos_directives as cur
    source=subprocess.check_output(['git','show','510dd134:proto7-2/lib/aos_directives.py'],text=True,cwd=REPO)
    ns={'__name__':'old_directives','__file__':str(TOP/'lib/aos_directives.py')};exec(compile(source,'git:510dd134/aos_directives.py','exec'),ns)
    records=[]
    for label,resolve in [('510dd134',ns['resolve']),('ad1dfa25',cur.resolve)]:
        try:resolve({'$ref':'#/a/'+'9'*4301},cur.Context(cur.Document(None,{'a':[0]})),['v']);r={'class':'accepted'}
        except Exception as e:r={'class':type(e).__name__,'code':getattr(e,'code',None),'message':str(e)}
        records.append({'version':label,'actual':r})
    assert all(r['actual']['class']=='ValueError' for r in records)
    return {'injection':'same 4301-digit array pointer in old and new product code','assertion':'prove finding pre-existed loop7, not introduced by ASCII check','records':records}

if __name__=='__main__':
    try:h.case('R8-06-full-loop','100 full persistent error loops',hundred);h.case('pointer-origin','baseline/current same failure',old_pointer)
    finally:h.finish()
