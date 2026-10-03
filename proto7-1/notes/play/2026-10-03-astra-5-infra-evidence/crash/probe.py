#!/usr/bin/env python3
"""Run from any cwd; only disposable /tmp/astra5-crash-* spaces are modified.

The filesystem pauses are explicit fault injection, not product edits.
Each saved result includes actual control/round/task files and stdout/stderr.
"""
import ctypes, json, os, pathlib, shutil, signal, subprocess, sys, tempfile, time

HERE = pathlib.Path(__file__).resolve().parent
PRODUCT = HERE.parents[3]
BIN = PRODUCT / 'bin'
ctypes.CDLL(None).prctl(36, 1, 0, 0, 0)  # subreaper: all probe orphans are reaped

def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj))

def read(path):
    try: return json.loads(path.read_text())
    except (OSError, ValueError): return None

def wait(pred, timeout=5):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        val = pred()
        if val: return val
        time.sleep(.01)
    raise TimeoutError('probe wait expired')

def snapshot(root):
    out = {}
    for p in sorted(root.rglob('*')):
        if p.is_file() and p.stat().st_size < 12000:
            out[str(p.relative_to(root))] = p.read_text(errors='replace')
    return out

def children():
    out=[]
    for p in pathlib.Path('/proc').iterdir():
        if p.name.isdigit():
            try:
                st=(p/'stat').read_text().rsplit(')',1)[1].split()
                if int(st[1]) == os.getpid(): out.append(int(p.name))
            except (OSError, ValueError): pass
    return out

def cleanup(root, procs):
    for p in root.rglob('*'):
        if p.is_dir(): p.chmod(0o755)
    for _ in range(30):
        live=children()
        if not live: break
        for pid in live:
            try: os.kill(pid, signal.SIGKILL)
            except ProcessLookupError: pass
        time.sleep(.02)
        while True:
            try:
                if os.waitpid(-1, os.WNOHANG)[0] == 0: break
            except ChildProcessError: break
    for p in procs:
        try: p.wait(timeout=.1)
        except subprocess.TimeoutExpired: pass
    remain=children()
    shutil.rmtree(root)
    return {'remaining_children': remain, 'root_exists': root.exists()}

def case(name, body):
    root=pathlib.Path(tempfile.mkdtemp(prefix='astra5-crash-'+name+'-'))
    procs=[]
    write(root/'.aos/timeline.json', {'interval_ms': 200})
    write(root/'.aos/tasks.json', {'tasks': []})
    def start(prog, fault=None):
        env=dict(os.environ)
        if fault:
            env['PYTHONPATH']=str(HERE)
            env['A4_FAULT']=json.dumps(dict(fault, marker=str(root/'fault-marker.json')))
        else:
            env.pop('A4_FAULT',None)
        args=[sys.executable,str(BIN/prog),str(root)]
        if prog in ('aos7-tick','aos7-tock'): args.append('.')
        log=open(root/(prog+'-'+str(len(procs))+'.stderr'),'w')
        p=subprocess.Popen(args,stdout=log,stderr=log,env=env)
        log.close(); procs.append(p)
        return p
    def marker(): return wait(lambda:read(root/'fault-marker.json'))
    record={'case':name,'root':str(root),'fault_injection':'sitecustomize patches selected os call only; SIGSTOP then controller SIGKILL'}
    try:
        body(root,start,marker,record)
        record['final_files']=snapshot(root)
    except Exception as e:
        record['probe_error']=repr(e)
        record['final_files']=snapshot(root)
    finally:
        record['cleanup']=cleanup(root,procs)
    (HERE/(name+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2))
    print(name, record.get('probe_error','OK'), record['cleanup'],flush=True)

def spawn_loss(root,start,marker,r):
    write(root/'.aos/spawn/once.json',{'name':'once','argv':['/bin/true']})
    d=start('aos7-daemon',{'prog':'aos7-tick','op':'remove','suffix':'/spawn/once.json','when':'after'})
    m=marker(); r['at_fault']=snapshot(root); os.kill(m['pid'],signal.SIGKILL)
    wait(lambda: (read(root/'.aos/round.json') or {}).get('round',0)>=3)
    d.kill(); d.wait(); r['before_restart']=snapshot(root)
    d=start('aos7-daemon'); wait(lambda:(read(root/'.aos/round.json') or {}).get('round',0)>=5)
    d.terminate(); d.wait(timeout=5)

def ended_loss(root,start,marker,r):
    write(root/'.aos/tasks.json',{'tasks':[{'name':'done','argv':['/bin/true'],'mode':'keep'}]})
    p=start('aos7-tick'); p.wait(timeout=5)
    wait(lambda:(root/'.aos/tasks/done-r1/exit.json').exists())
    p=start('aos7-tock',{'prog':'aos7-tock','op':'replace','suffix':'/ended.json','when':'after'})
    marker(); r['at_fault']=snapshot(root); p.kill(); p.wait()
    write(root/'.aos/tasks.json',{'tasks':[]})
    d=start('aos7-daemon'); wait(lambda:(read(root/'.aos/round.json') or {}).get('round',0)>=3)
    d.terminate(); d.wait(timeout=5)

def runner_exit(root,start,marker,r):
    write(root/'.aos/tasks.json',{'tasks':[{'name':'done','argv':[sys.executable,'-c','raise SystemExit(23)']}]})
    p=start('aos7-tick',{'prog':'aos7-run','op':'replace','suffix':'/exit.json','when':'before'}); p.wait(timeout=5)
    m=marker(); r['at_fault']=snapshot(root); os.kill(m['pid'],signal.SIGKILL)
    time.sleep(.05)
    write(root/'.aos/tasks.json',{'tasks':[]})
    d=start('aos7-daemon'); wait(lambda:(root/'.aos/tasks/done-r1/ended.json').exists())
    d.terminate(); d.wait(timeout=5)

def stale_tick(root,start,marker,r):
    d=start('aos7-daemon',{'prog':'aos7-tick','op':'replace','suffix':'/.aos/round.json','nth':2,'when':'before'})
    m=marker(); r['at_fault']=snapshot(root); d.kill(); d.wait()
    # New daemon completes round 2, then pause it, leaving an unambiguous stable round.
    d2=start('aos7-daemon')
    wait(lambda:(read(root/'.aos/round.json') or {}).get('round',0)>=2)
    write(root/'.aosd/ctl/pause.json',{'op':'pause','node':'.'})
    wait(lambda:(read(root/'.aosd/status.json') or {}).get('nodes',{}).get('.',{}).get('phase')=='paused')
    r['before_old_tick_resume']=snapshot(root)
    os.kill(m['pid'],signal.SIGCONT)
    wait(lambda:(read(root/'.aos/round.json') or {}).get('round')==1)
    time.sleep(.05); r['after_old_tick_resume']=snapshot(root)
    d2.terminate(); d2.wait(timeout=5)

def stale_tock(root,start,marker,r):
    d=start('aos7-daemon',{'prog':'aos7-tock','op':'replace','suffix':'/.aos/round.json','when':'before'})
    m=marker(); r['at_fault']=snapshot(root); d.kill(); d.wait()
    d2=start('aos7-daemon'); wait(lambda:(read(root/'.aos/round.json') or {}).get('round',0)>=2)
    write(root/'.aosd/ctl/pause.json',{'op':'pause','node':'.'})
    wait(lambda:(read(root/'.aosd/status.json') or {}).get('nodes',{}).get('.',{}).get('phase')=='paused')
    r['before_old_tock_resume']=snapshot(root)
    os.kill(m['pid'],signal.SIGCONT)
    wait(lambda:(read(root/'.aos/round.json') or {}).get('round')==1)
    time.sleep(.05); r['after_old_tock_resume']=snapshot(root)
    d2.terminate(); d2.wait(timeout=5)

def readonly(root,start,marker,r):
    r['fault_injection']='actual chmod .aosd 0555 after daemon has started; uid 1000, no root bypass'
    write(root/'.aos/tasks.json',{'tasks':[{'name':'sleep','argv':['/bin/sleep','30'],'mode':'keep'}]})
    d=start('aos7-daemon'); wait(lambda:(root/'.aos/tasks/sleep-r1/pid.json').exists())
    (root/'.aosd').chmod(0o555)
    r['daemon_rc']=d.wait(timeout=5)
    r['after_failure']=snapshot(root)
    pid=read(root/'.aos/tasks/sleep-r1/pid.json')['pid']
    try: os.kill(pid,0); r['task_alive_after_failure']=True
    except ProcessLookupError: r['task_alive_after_failure']=False
    (root/'.aosd').chmod(0o755)
    d2=start('aos7-daemon'); wait(lambda:(read(root/'.aosd/status.json') or {}).get('pid')==d2.pid)
    d2.terminate(); d2.wait(timeout=5)

def enospc(root,start,marker,r):
    r['fault_injection']='os.replace to status.json raises OSError ENOSPC once in daemon; models metadata-write failure, not a filled filesystem'
    d=start('aos7-daemon',{'prog':'aos7-daemon','op':'replace','suffix':'/status.json','action':'enospc'})
    r['daemon_rc']=d.wait(timeout=5); r['after_failure']=snapshot(root)
    d2=start('aos7-daemon'); wait(lambda:(read(root/'.aos/round.json') or {}).get('round',0)>=3)
    d2.terminate(); d2.wait(timeout=5)

if __name__=='__main__':
    for name,fn in [('spawn-loss',spawn_loss),('ended-loss',ended_loss),('runner-exit',runner_exit),('stale-tick',stale_tick),('stale-tock',stale_tock),('readonly',readonly),('enospc',enospc)]:
        case(name,fn)
