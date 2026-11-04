#!/usr/bin/env python3
"""Offline 6-agent / 360-round soak; real daemon/actions, timing wrapper only.
Run from any cwd: python3 path/to/reproduce.py [--rounds 360].
All experimental data lives under /tmp/astra3-long-* and is removed on exit.
"""
import argparse
import collections
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
PROTO = next(p for p in HERE.parents if p.name == 'proto7-1')
sys.path.insert(0, str(PROTO / 'lib'))
from aos7_fs import read_json, write_json

LAUNCHER = r'''
import json, os, sys, threading, time
sys.path.insert(0, sys.argv[1])
import aos7_daemon, aos7_daemon_timeline
orig = aos7_daemon_timeline.run_prog
lock = threading.Lock()
def timed(name, root, node):
    begin = time.perf_counter()
    rc, out, err = orig(name, root, node)
    record = dict(name=name, node=node, ms=(time.perf_counter()-begin)*1000,
                  round=(out or {}).get('round'), rc=rc)
    with lock:
        with open(sys.argv[3], 'a') as f: f.write(json.dumps(record)+'\n')
    return rc, out, err
aos7_daemon_timeline.run_prog = timed
sys.exit(aos7_daemon.main([sys.argv[2]]))
'''

def disk(root):
    n = logical = allocated = dirs = 0
    groups = collections.Counter()
    for dp, dns, fns in os.walk(root):
        dirs += len(dns)
        for fn in fns:
            p = Path(dp) / fn
            if p.is_symlink(): continue
            try: s = p.stat()
            except FileNotFoundError: continue
            n += 1; logical += s.st_size; allocated += s.st_blocks * 512
            key = 'rounds' if '/.aos/rounds/' in str(p) else fn
            groups[key] += s.st_size
    return dict(files=n, directories=dirs, logical_bytes=logical,
                allocated_file_bytes=allocated, top_bytes=groups.most_common(8))

def rss(pid):
    try:
        vals = dict(line.split(':', 1) for line in Path(f'/proc/{pid}/status').read_text().splitlines() if ':' in line)
        return {key: int(vals[key].split()[0]) for key in ('VmRSS', 'VmHWM')}
    except FileNotFoundError: return {}

def stats(vals):
    vals = sorted(vals)
    return dict(n=len(vals), median_ms=round(statistics.median(vals), 3),
                p95_ms=round(vals[int(.95*(len(vals)-1))], 3), mean_ms=round(statistics.mean(vals), 3)) if vals else {}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--rounds', type=int, default=360)
    args = ap.parse_args()
    tmp = Path(tempfile.mkdtemp(prefix='astra3-long-'))
    root = tmp / 'space'; root.mkdir()
    launcher = tmp / 'daemon_timed.py'; launcher.write_text(LAUNCHER)
    timing = tmp / 'timing.jsonl'
    members = [f'agents/a{i}' for i in range(6)]
    nodes = ['team'] + ['team/'+x for x in members]
    write_json(str(root/'team/kernel.json'), dict(members=members, stuck_rounds=20,
                 budget_tokens=10**12, cap_tokens=10**12, cool_rounds=3))
    for nid in nodes:
        node = root/nid
        write_json(str(node/'.aos/timeline.json'), {'interval_ms': 180})
        kind = 'kernel' if nid == 'team' else 'agent'
        write_json(str(node/'.aos/tasks.json'), {'tasks': [dict(name=kind, mode='keep', argv=['aos7-'+kind])]})
        if kind == 'agent':
            write_json(str(node/'agent.json'), dict(llm='fake', max_ping=1000000, memory=12))
            i = int(nid[-1])
            if i % 2 == 0:
                write_json(str(node/'goal.json'), {'say_first': {'to': f'team/agents/a{i+1}', 'body': 'ping 0'}})
    env = dict(os.environ); env.pop('AOS7_AUDIT', None)
    report = dict(config=dict(agents=6, kernel=1, target_rounds=args.rounds, interval_ms=180,
                  memory=12, backend='fake', audit=False, workload='3 pairs uninterrupted ping',
                  python=sys.version, platform=platform.platform(), cpu_count=os.cpu_count()),
                  samples=[], periodic_rss=[])
    started=time.monotonic(); proc=None
    try:
        with open(tmp/'daemon.log','w') as output:
            proc=subprocess.Popen([sys.executable,str(launcher),str(PROTO/'lib'),str(root),str(timing)],
                                  stdout=output,stderr=subprocess.STDOUT,env=env,start_new_session=True)
        thresholds=[10,60,120,180,240,300,args.rounds]; next_rss=0
        while thresholds:
            if proc.poll() is not None: raise RuntimeError('daemon exited: '+(tmp/'daemon.log').read_text())
            elapsed=time.monotonic()-started
            if elapsed > 600: raise TimeoutError('600s timeout')
            st=read_json(str(root/'.aosd/status.json'),{})
            nr=st.get('nodes',{})
            low=min((nr.get(n,{}).get('round',0) for n in nodes), default=0)
            if elapsed >= next_rss:
                report['periodic_rss'].append(dict(seconds=round(elapsed,3),min_round=low,**rss(proc.pid)))
                next_rss=elapsed+2
            if low >= thresholds[0]:
                report['samples'].append(dict(threshold=thresholds.pop(0),seconds=round(elapsed,3),
                      rounds={n:nr[n]['round'] for n in nodes},rss_kib=rss(proc.pid),disk=disk(root)))
            time.sleep(.08)
        # Give agents time to consume the final tock before requesting clean stop.
        time.sleep(.25)
        write_json(str(root/'.aosd/ctl/finish.json'),dict(op='stop',kill=True,by='astra3-longrun'))
        proc.wait(timeout=20)
        report['seconds']=round(time.monotonic()-started,3); report['daemon_rc']=proc.returncode
        report['final_status']=read_json(str(root/'.aosd/status.json'))
        report['final_disk']=disk(root)
        report['agents']={}
        for nid in nodes[1:]:
            node=root/nid; tasks=list((node/'.aos/tasks').iterdir())
            report['agents'][nid]=dict(tasks=len(tasks),state=read_json(str(tasks[-1]/'state.json')),
              usage=read_json(str(tasks[-1]/'usage.json')),exit=read_json(str(tasks[-1]/'exit.json')),
              received=len(list((node/'inbox/done').glob('*.json'))),
              sent=sum(1 for _ in open(node/'sent.jsonl')))
        rows=[json.loads(x) for x in timing.read_text().splitlines()]
        report['timing_windows']={}
        for label,lo,hi in [('early',11,60),('middle',156,205),('late',311,360)]:
            report['timing_windows'][label]={name:stats([r['ms'] for r in rows if r['name']==name and lo <= (r['round'] or 0) <= hi]) for name in ['aos7-tick','aos7-tock']}
        report['timing_failures']=[r for r in rows if r['rc']]
        report['timing_calls']=len(rows)
        # Bound each evidence shard to 150 KB.
        chunks=[]; buf=''
        for row in rows:
            line=json.dumps(row)+'\n'
            if len(buf)+len(line)>150000: chunks.append(buf); buf=''
            buf+=line
        if buf: chunks.append(buf)
        for i, chunk in enumerate(chunks): (HERE/f'timing-{i:02d}.jsonl').write_text(chunk)
        (HERE/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({k:report[k] for k in ('seconds','samples','timing_windows','timing_calls','timing_failures')},ensure_ascii=False,indent=2))
    finally:
        if proc and proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try: proc.wait(timeout=20)
            except subprocess.TimeoutExpired: proc.kill(); proc.wait()
        # Any runner/task still alive is our own experiment's process; stop its PGID.
        alive=[]
        for p in root.glob('**/pid.json'):
            obj=read_json(str(p),{})
            if obj.get('pgid'):
                try: os.killpg(obj['pgid'],signal.SIGKILL)
                except ProcessLookupError: pass
        shutil.rmtree(tmp)
        print('cleaned',tmp)

if __name__=='__main__': main()
