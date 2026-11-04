"""Real daemon benchmark; no LLM. Temp roots remain inside this evidence directory.

CPU includes daemon and its waited tick/tock children, excludes orphan runner CPU.
Polling samples cannot establish absence of sub-poll-interval uncertainty.
"""
import os, sys, pathlib, tempfile, time, json, statistics, traceback, datetime, collections
E = pathlib.Path(__file__).resolve().parent
TOP = E.parents[2]
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
sys.dont_write_bytecode = True
tempfile.tempdir = str(E)
sys.path.insert(0, str(TOP / 'tests'))
from base import DaemonCase
from aos7_fs import read_json, read_jsonl, write_json

def measure(root):
    files = list(pathlib.Path(root).rglob('*'))
    files = [p for p in files if p.is_file()]
    return {'files':len(files), 'bytes':sum(p.stat().st_size for p in files),
            'dot_tmp':sum('.tmp.' in p.name for p in files)}

def cpu(pid):
    s = pathlib.Path('/proc/%d/stat' % pid).read_text().rsplit(')', 1)[1].split()
    hz = os.sysconf('SC_CLK_TCK')
    return {'self_seconds':(int(s[11])+int(s[12]))/hz,
            'waited_children_seconds':(int(s[13])+int(s[14]))/hz}

def run(label, count, checkpoints, loaded):
    c = DaemonCase(); c.setUp(); root = c.root
    result = {'label':label,'node_count':count,'target_rounds_per_node':checkpoints[-1],
              'workload':'one sleep keep + one true each per node; node n00 also history(max-lines=25)' if loaded else 'empty tasks',
              'samples':[], 'uncertain_observations':[], 'uncertain_reason_counts':{}, 'error_observations':[], 'polls':0,
              'logical_cpus':os.cpu_count()}
    result['root_basename'] = pathlib.Path(root).name
    nodes = ['n%02d' % n for n in range(count)]
    p = None
    try:
        for nid in nodes:
            tasks = []
            if loaded:
                tasks = [{'name':'keep','mode':'keep','argv':['sleep','3600']},
                         {'name':'each','mode':'each','argv':['true']}]
                if nid == nodes[0]:
                    tasks.append({'name':'history','mode':'keep', 'argv':[sys.executable,str(TOP/'modules/history.py'),'--max-lines','25','--status']})
            c.mknode(nid,tasks,interval_ms=0)
        write_json(pathlib.Path(root)/'.aosd/nodes.json',{'nodes':{n:{'by':'load'} for n in nodes}})
        write_json(pathlib.Path(root)/'.aosd/paused.json',{'paused':{n:['load'] for n in nodes}})
        p=c.start_daemon()
        c.wait_for(lambda:len(c.status().get('nodes',{}))==count and all(c.nstat(n).get('phase')=='paused' for n in nodes),30)
        base_cpu=cpu(p.pid); previous=0; started=time.monotonic()
        for goal in checkpoints:
            start=time.monotonic(); reached={}
            for nid in nodes:
                write_json(pathlib.Path(root)/'.aosd/ctl'/('load.resume.'+nid+'.json'),{'op':'resume','node':nid,'owner':'load','rounds':goal-previous})
            deadline=start+240
            while time.monotonic()<deadline:
                status=c.status(); result['polls']+=1
                for nid,s in status.get('nodes',{}).items():
                    for u in s.get('uncertain',[]):
                        reason=u.get('why','unknown')
                        result['uncertain_reason_counts'][reason]=result['uncertain_reason_counts'].get(reason,0)+1
                    if s.get('uncertain') and len(result['uncertain_observations'])<20:
                        result['uncertain_observations'].append({'elapsed_s':round(time.monotonic()-started,3),'node':nid,'uncertain':s['uncertain']})
                    if s.get('last_error') and len(result['error_observations'])<20:
                        row={'node':nid,'last_error':s['last_error']}
                        if row not in result['error_observations']: result['error_observations'].append(row)
                    if s.get('phase')=='paused' and s.get('round',0)>=goal and nid not in reached:
                        reached[nid]=time.monotonic()-start
                if len(reached)==count:break
                time.sleep(.2)
            if len(reached)!=count:raise RuntimeError('checkpoint timeout: '+repr({n:c.nstat(n) for n in nodes if n not in reached}))
            time.sleep(.15)
            end_cpu=cpu(p.pid)
            vals=sorted(reached.values())
            elapsed=time.monotonic()-start
            summary_errors=[]; durations=[]; task_errors=[]; last_runs={}
            for nid in nodes:
                lr=c.last_round(pathlib.Path(root)/nid)
                if lr.get('errors'): summary_errors.append({'node':nid,'errors':lr['errors']})
                if lr.get('tasks_error'): task_errors.append({'node':nid,'errors':lr['tasks_error']})
                durations.append((datetime.datetime.fromisoformat(lr['tock_at'])-datetime.datetime.fromisoformat(lr['tick_at'])).total_seconds())
                if loaded: last_runs[nid]={name:c.birth(pathlib.Path(root)/nid,name).get('run') for name in ['keep','each']}
            result['samples'].append({'round_per_node':goal,'closed_node_rounds':goal*count,'checkpoint_seconds':round(elapsed,3),
                                      'completion_seconds':{'min':round(vals[0],3),'median':round(statistics.median(vals),3),'max':round(vals[-1],3)},
                                      'node_rounds_per_second':round(count*(goal-previous)/elapsed,3),
                                      'cpu_since_start':{k:round(end_cpu[k]-base_cpu[k],3) for k in end_cpu},
                                      'storage':measure(root),'summary_errors':summary_errors,'task_errors':task_errors,
                                      'sampled_round_tick_to_tock_seconds':{'min':min(durations),'median':statistics.median(durations),'max':max(durations)},
                                      'last_runs':last_runs})
            previous=goal
            print(label,goal,result['samples'][-1],flush=True)
        result['total_seconds']=round(time.monotonic()-started,3)
        result['final_rounds']={n:c.round_json(pathlib.Path(root)/n)['round'] for n in nodes}
        if loaded:
            rows=read_jsonl(pathlib.Path(root)/nodes[0]/'history'/('n00.jsonl'))
            result['history']={'rows':len(rows),'last_round':next((r['round'] for r in reversed(rows) if 'round' in r),None),'gap_rows':sum('gap' in r for r in rows)}
        c.stop_daemon(p)
        result['daemon_returncode']=p.returncode
    except Exception:
        result['error']=traceback.format_exc()
    finally:
        c.doCleanups()
        result['cleanup_root_removed']=not pathlib.Path(root).exists()
        result['cleanup_daemon_returncode']=p.returncode if p else None
    return result

if __name__=='__main__':
    long='--long' in sys.argv
    checkpoints=[10,100,250,500,750,1000] if long else [10,50,100]
    for label,count,loaded in [('long-empty' if long else 'empty',50,False),('long-tasks' if long else 'tasks',10,True)]:
        result=run(label,count,checkpoints,loaded)
        (E/('load-'+label+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
