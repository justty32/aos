"""Rerun: python3 proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/core3/k04.py

Real tick, runner, aos-exec, inst child and tock main. A scheduling shim delays
the first real _signal(TERM) after its descendant snapshot; no return is mocked.
"""
import sys
sys.dont_write_bytecode = True
from common import *

def probe(c,negative_control=False):
    node=c.node(inst=True)
    env=dict(c.env,AOS7_TEST_RUNNER_CRASH='runner-before-pid')
    c.cli('aos7-tick',c.root,'a',env=env)
    sd=node/'.aos/tasks/s'
    birth=read(sd/'birth.json')
    runner=birth['runner']
    wait(lambda:not alive(runner),what='runner SIGKILL hook')
    procs=wait(lambda:scan(node=node,tid='s'),what='orphan aos-exec')
    executor=next(p for p in procs if 'aos-exec' in p['cmd'])
    # FIFO open blocks before _spawn; wchan is independent Linux evidence.
    wait(lambda:Path('/proc/%d/wchan'%executor['pid']).read_text().strip()=='wait_for_partner',what='aos-exec FIFO open')
    c.data['injection']={'runner_identity':runner,'runner_after':ident(runner['pid']),
                         'executor':executor,'wchan':Path('/proc/%d/wchan'%executor['pid']).read_text(),
                         'pid_json_absent':not (sd/'pid.json').exists(),'ready_absent':not (c.root/'old.ready').exists()}
    shim=c.root/'tock_gate.py'
    shim.write_text('''import sys,os,json,signal,time
from pathlib import Path
sys.path.insert(0,%r)
import aos7_proc,aos7_tock
root=Path(sys.argv[1]); original=aos7_proc._signal; armed=True
def gate(groups,sig):
    global armed
    if armed and sig==signal.SIGTERM:
        armed=False
        (root/'signal-entered.json').write_text(json.dumps({'groups':sorted(groups),'at':time.monotonic()}))
        until=time.monotonic()+20
        while not (root/'signal-release').exists() and time.monotonic()<until:time.sleep(.005)
    original(groups,sig)
aos7_proc._signal=gate
if os.environ.get('CORE3_DISABLE_RESCAN')=='1':
    aos7_proc._kill_remaining=lambda *a,**kw:True
sys.exit(aos7_tock.main([str(root),'a']))
'''%str(LIB))
    tock=c.start([sys.executable,shim,c.root],name='gated-tock',env=dict(c.env,CORE3_DISABLE_RESCAN='1' if negative_control else '0'))
    entered=wait(lambda:read(c.root/'signal-entered.json'),what='tock resolves and snapshots before TERM')
    c.check('child absent at completed descendant snapshot',not (c.root/'old.ready').exists())
    fifo_fd=os.open(c.root/'stdin.fifo',os.O_RDWR|os.O_NONBLOCK)
    try:
        old=c.ready()
        child=ident(old['pid'])
        c.check('late child born in different session after snapshot',child['pgid'] not in entered['groups'])
        c.check('late child old run matches',old['run'],'1')
        c.data['injection'].update(signal_snapshot=entered,late_child=child,late_ready=old)
        (c.root/'signal-release').touch()
        c.check('real tock exits successfully',tock.wait(20),0)
        c.data['exit_before_restart']=read(sd/'exit.json')
        if negative_control:
            c.check('oracle calibration: disabling rescan leaves late child',alive(old))
            c.data['negative_control']='in-memory _kill_remaining bypass only; deliberately old behavior, not product finding'
        else:
            c.check('late old child collected',alive(old),False)
            c.check('no run1 process survives tock',[p for p in scan(node=node,tid='s') if p['run']=='1'],[])
        started=c.cli('aos7-tick',c.root,'a')
        new=wait(lambda:read(c.root/'old.ready') if read(c.root/'old.ready',{}).get('run')=='2' else None,what='generation2 ready')
        ps=scan(node=node,tid='s')
        c.data.update(next_tick=started,new_task=new,processes_after=ps)
        c.check('negative oracle sees two live runs' if negative_control else 'only one node/tid generation remains',
                sorted({p['run'] for p in ps}),['1','2'] if negative_control else ['2'])
        c.check('next generation is alive',alive(new))
    finally:
        os.close(fifo_fd)

if __name__=='__main__':
    run_cases([('k04-%02d'%i,probe) for i in range(1,11)])
