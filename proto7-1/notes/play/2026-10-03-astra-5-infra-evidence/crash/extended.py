"""Bounded local crash-recovery regressions; uses original astra4 harness cleanup."""
import os, signal, time
import probe as p

def handoff(root,start,marker,r,kind,held):
    p.write(root/'.aos/timeline.json',{'interval_ms':100,'action_timeout_s':.25})
    cfg={'prog':'aos7-'+kind,'op':'replace' if held else 'flock','suffix':'/.aos/round.json','when':'before','onceglob':True}
    if held and kind=='tick': cfg['nth']=2
    d=start('aos7-daemon',cfg)
    m=marker(); r['at_fault']=p.snapshot(root); d.kill();d.wait()
    d2=start('aos7-daemon')
    time.sleep(1.15)
    r['new_daemon_alive_while_old_stopped']=d2.poll() is None
    r['before_old_resume']=p.snapshot(root)
    os.kill(m['pid'],signal.SIGCONT)
    time.sleep(.15)
    try:
        r['old_action_state_after_resume']=open('/proc/%d/stat'%m['pid']).read().rsplit(')',1)[1].split()[0]
    except OSError:
        r['old_action_state_after_resume']='gone'
    p.wait(lambda:(p.read(root/'.aos/round.json') or {}).get('round',0)>=4)
    r['after_old_resume']=p.snapshot(root)
    d2.terminate();d2.wait(timeout=5)

def io_recovery(root,start,marker,r,kind):
    p.write(root/'.aos/timeline.json',{'interval_ms':100})
    if kind=='readonly':
        d=start('aos7-daemon')
        p.wait(lambda:(root/'.aosd/status.json').exists())
        (root/'.aosd').chmod(0o555)
        time.sleep(.35)
        r['alive_during_fault']=d.poll() is None
        r['during_fault']=p.snapshot(root)
        (root/'.aosd').chmod(0o755)
    else:
        d=start('aos7-daemon',{'prog':'aos7-daemon','op':'replace','suffix':'/status.json','action':'enospc'})
        time.sleep(.35)
        r['alive_during_fault']=d.poll() is None
    p.wait(lambda:(p.read(root/'.aosd/status.json') or {}).get('io_errors',0)>0)
    r['recovered_status']=p.read(root/'.aosd/status.json')
    d.terminate(); d.wait(timeout=5)
    r['daemon_rc']=d.returncode

def timeout_summary(root,start,marker,r):
    p.write(root/'.aos/timeline.json',{'interval_ms':100,'action_timeout_s':.25})
    p.write(root/'.aos/spawn/one.json',{'name':'one','argv':['/bin/true']})
    d=start('aos7-daemon',{'prog':'aos7-tock','op':'append_jsonl','suffix':'/rounds.jsonl','when':'after','onceglob':True,'lib':str(p.PRODUCT/'lib')})
    marker();r['at_fault']=p.snapshot(root)
    p.wait(lambda:(p.read(root/'.aos/round.json') or {}).get('round',0)>=4)
    d.terminate(); d.wait(timeout=5)
    r['daemon_rc']=d.returncode

def runner_exit_fd(root,start,marker,r):
    p.write(root/'.aos/tasks.json',{'tasks':[{'name':'done','argv':['/bin/sh','-c','exit 23']}]})
    q=start('aos7-tick',{'prog':'aos7-run','op':'replace','suffix':'exit.json','when':'before'})
    q.wait(timeout=5)
    m=marker(); r['at_fault']=p.snapshot(root);os.kill(m['pid'],signal.SIGKILL)
    time.sleep(.05)
    p.write(root/'.aos/tasks.json',{'tasks':[]})
    d=start('aos7-daemon');p.wait(lambda:(root/'.aos/tasks/done-r1/ended.json').exists())
    d.terminate();d.wait(timeout=5)

def same_round_replay(root,start,marker,r):
    p.write(root/'.aos/tasks.json',{'tasks':[{'name':'done','argv':['/bin/true']}]})
    q=start('aos7-tick');q.wait(timeout=5)
    p.wait(lambda:(root/'.aos/tasks/done-r1/exit.json').exists())
    q=start('aos7-tock',{'prog':'aos7-tock','op':'append_jsonl','suffix':'/rounds.jsonl','when':'after','onceglob':True,'lib':str(p.PRODUCT/'lib')})
    marker();r['at_fault']=p.snapshot(root);q.kill();q.wait()
    q=start('aos7-tock');q.wait(timeout=5)

if __name__=='__main__':
    for kind in ('tick','tock'):
        for held in (False,True):
            p.case('handoff-'+kind+('-held' if held else '-waiting'),lambda *args,k=kind,h=held:handoff(*args,k,h))
    for kind in ('readonly','enospc'):
        p.case(kind+'-recovery',lambda *args,k=kind:io_recovery(*args,k))
    p.case('timeout-after-summary',timeout_summary)
    p.case('runner-exit-fd',runner_exit_fd)
    p.case('same-round-replay',same_round_replay)
