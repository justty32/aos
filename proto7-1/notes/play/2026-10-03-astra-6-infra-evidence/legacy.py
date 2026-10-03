"""Reuse astra-5 repro bodies; output redirection and safe cleanup only.
Old crash hooks still match fd-relative suffixes. Handoff now tolerates the
old owner already being SIGKILLed (the expected fix) before SIGCONT.
"""
from common import *
from unittest import mock
import errno, io, unittest

def old_archive(s):
    m=load('a6_old_archive',OLD/'tasks/archive_probe.py');out=[]
    for k in ('agent','kernel','usage'):
        r=m.race(k)
        if k=='usage':
            r={k:r[k] for k in ('case','barrier_hit','before','during','after')}
        out.append(r)
    return {'cases':out}

def old_stop(s):
    m=load('a6_old_stop',OLD/'tasks/stop_only.py');m.OUT=s.root
    out=[]
    for kind in ('fork','forksetsid'):
        r=m.run(kind)
        out.append({k:r[k] for k in ('case','daemon_rc','stop_ms','survivors_after_stop','owned_before_stop')})
    return {'cases':out}

def old_scan(s):
    m=load('a6_old_node',OLD/'node/repro.py')
    for k in ('estale_walk','timeline_eio','rename_gap'):m.node_case(k)
    return {'cases':m.RESULTS}

def crash(s,kind,held=True):
    s.node('.',action_timeout_s=.25)
    op='replace' if held else 'flock';cfg={'prog':'aos7-'+kind,'op':op,'suffix':'/.aos/round.json','when':'before','onceglob':True}
    if held and kind=='tick':cfg['nth']=2
    cfg['marker']=str(s.root/'marker.json')
    d=s.start(env={'PYTHONPATH':str(OLD/'crash'),'A4_FAULT':json.dumps(cfg)})
    m=wait(lambda:read(s.root/'marker.json'));d.kill();d.wait();d2=s.start();time.sleep(1.15)
    out={'marker':m,'before_resume':read(s.root/'.aos/round.json'),'owner_alive':task.pid_alive(m['pid'])}
    try:os.kill(m['pid'],signal.SIGCONT)
    except ProcessLookupError:pass
    wait(lambda:not task.pid_alive(m['pid']),3)
    wait(lambda:(read(s.root/'.aos/round.json',{}) or {}).get('round',0)>=4)
    out['after_resume']=read(s.root/'.aos/round.json');d2.terminate();d2.wait(10)
    out['handoff_logs']=[r for r in rows(s.root/'.aosd/log.jsonl') if r.get('ev') in ('stale-holder-kill','stale')]
    return out

def replay(s,timeout):
    n=s.node('.',action_timeout_s=.25);write(n/'.aos/spawn/one.json',{'name':'one','argv':['/bin/true']})
    cfg={'prog':'aos7-tock','op':'append_jsonl','suffix':'/rounds.jsonl','when':'after','onceglob':True,'lib':str(LIB),'marker':str(s.root/'marker.json')}
    env={'PYTHONPATH':str(OLD/'crash'),'A4_FAULT':json.dumps(cfg)}
    if timeout:
        d=s.start(env=env);wait(lambda:read(s.root/'marker.json'));wait(lambda:(read(n/'.aos/round.json',{}) or {}).get('round',0)>=4)
        d.terminate();d.wait(10)
    else:
        s.run('aos7-tick','.');wait(lambda:read(n/'.aos/tasks/one-r1/exit.json'))
        q=s.start('aos7-tock','.',env);wait(lambda:read(s.root/'marker.json'));q.kill();q.wait();again=s.run('aos7-tock','.')
    return {'summaries':rows(n/'.aos/rounds.jsonl'),'round':read(n/'.aos/round.json'),'replay_logs':[r for r in rows(n/'.aosd/log.jsonl') if r.get('replay')],**({'again':again} if not timeout else {})}

def delayed_agent(s):
    m=load('a6_old_node2',OLD/'node/repro.py');m.orphan_test();return {'cases':m.RESULTS}

def demo_eio(s):
    play=load('a6_demo',PRODUCT/'demo/play.py');s.node(items=[{'name':'sleep','mode':'keep','argv':SLEEP}]);captured=[];realp=subprocess.Popen;realw=play.fs.write_json
    def cap(*a,**kw):p=realp(*a,**kw);captured.append(p);return p
    def bad(path,obj):
        if str(path).endswith('/zz-play-stop.json'):raise OSError(errno.EIO,'injected demo stop write failure')
        return realw(path,obj)
    with mock.patch.object(play.subprocess,'Popen',cap),mock.patch.object(play.fs,'write_json',bad):left=play.run(str(s.root),.3,True)
    return {'daemon_rc':captured[0].poll(),'returned_left':left,'live_descendants_before_delete':{p:st for p,st in descendants().items() if st['state']!='Z'}}

if __name__=='__main__':
    # All legacy mkdtemp calls are contained in the per-case parent, removed after processes.
    def wrapped(fn):
        def run(s):
            tempfile.tempdir=str(s.root)
            try:return fn(s)
            finally:tempfile.tempdir=None
        return run
    for name,fn in [('legacy-archive',old_archive),('legacy-stop',old_stop),('legacy-scan',old_scan),('legacy-agent-delayed',delayed_agent),('legacy-demo-eio',demo_eio)]:case(name,wrapped(fn))
    for k in ('tick','tock'):
        for held in (False,True):case('handoff-'+k+('-held' if held else '-waiting'),lambda s,k=k,h=held:crash(s,k,h))
    case('replay-same-round',lambda s:replay(s,False));case('replay-timeout',lambda s:replay(s,True))
