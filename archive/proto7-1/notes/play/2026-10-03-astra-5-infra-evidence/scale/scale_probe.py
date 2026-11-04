#!/usr/bin/env python3
"""Offline instrumentation; no product source edits. All experiment spaces /tmp/astra5-scale-*.
Usage: python3 scale_probe.py --repo /path/to/workspace --seconds 15 --counts 10 50 100 200
"""
import argparse, ctypes, json, os, pathlib, platform, resource, shutil, signal, statistics, subprocess, sys, tempfile, time

P = pathlib.Path

def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')

def stats(xs):
    if not xs: return {'n': 0}
    x=sorted(xs)
    return {'n':len(x),'min':round(x[0],3),'p50':round(statistics.median(x),3),'p95':round(x[min(len(x)-1,int(len(x)*.95))],3),'max':round(x[-1],3)}

def procstat(pid):
    try:
        s=P(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
        return {'pid':int(pid),'state':s[0],'ppid':int(s[1]),'pgid':int(s[2]),'cpu':(int(s[11])+int(s[12]))/os.sysconf('SC_CLK_TCK'),'children_cpu':(int(s[13])+int(s[14]))/os.sysconf('SC_CLK_TCK'),'rss_kib':int(s[21])*os.sysconf('SC_PAGE_SIZE')/1024}
    except (OSError,ValueError,IndexError): return None

def snapshot(daemon_pid,root):
    rows={}
    for d in P('/proc').iterdir():
        if not d.name.isdigit(): continue
        s=procstat(d.name)
        if s: rows[int(d.name)]=s
    own=set()
    for pid,s in rows.items():
        try:
            if root.encode() in P(f'/proc/{pid}/cmdline').read_bytes(): own.add(pid)
        except OSError: pass
    while True:
        children={p for p,s in rows.items() if s['ppid'] in own}
        if children <= own: break
        own |= children
    d=rows.get(daemon_pid,{})
    try: fd=len(list(P(f'/proc/{daemon_pid}/fd').iterdir()))
    except OSError: fd=None
    return {'mono':time.monotonic(),'daemon_cpu_s':d.get('cpu'),'daemon_waited_children_cpu_s':d.get('children_cpu'),'daemon_rss_kib':d.get('rss_kib'),'daemon_fd':fd,'processes_live':sum(rows[p]['state']!='Z' for p in own),'processes_zombie':sum(rows[p]['state']=='Z' for p in own),'system_processes_live':sum(s['state']!='Z' for s in rows.values()),'load1':os.getloadavg()[0]}

WRAPPER='''import json, os, sys, threading, time
sys.path.insert(0, sys.argv[1])
import aos7_daemon, aos7_daemon_timeline
original=aos7_daemon_timeline.run_prog
lock=threading.Lock()
f=open(sys.argv[3], 'a', buffering=1)
def measured(name,root,node,*args,**kwargs):
    start=time.monotonic()
    try:
        result=original(name,root,node,*args,**kwargs)
    except BaseException as exc:
        with lock: f.write(json.dumps({'node':node,'prog':name,'start':start,'end':time.monotonic(),'exception':repr(exc)})+'\\n')
        raise
    with lock: f.write(json.dumps({'node':node,'prog':name,'start':start,'end':time.monotonic(),'rc':result[0],'round':(result[1] or {}).get('round')})+'\\n')
    return result
aos7_daemon_timeline.run_prog=measured
original_write=aos7_daemon.write_json
def measured_write(path,obj):
    result=original_write(path,obj)
    stamp=time.monotonic()
    row=None
    if path.endswith('/status.json'): row={'prog':'status','end':stamp}
    if '/ctl-done/' in path and '_probe_sent_mono' in obj: row={'prog':'ctl','start':obj['_probe_sent_mono'],'end':stamp,'ok':obj['result']['ok']}
    if row:
        with lock: f.write(json.dumps(row)+'\\n')
    return result
aos7_daemon.write_json=measured_write
raise SystemExit(aos7_daemon.main([sys.argv[2]]))
'''

def reap(daemon_pid):
    for d in P('/proc').iterdir():
        if not d.name.isdigit() or int(d.name)==daemon_pid: continue
        s=procstat(d.name)
        if s and s['ppid']==os.getpid() and s['state']=='Z':
            try: os.waitpid(int(d.name),os.WNOHANG)
            except ChildProcessError: pass

def main():
    a=argparse.ArgumentParser(); a.add_argument('--repo',required=True);a.add_argument('--seconds',type=float,default=15);a.add_argument('--counts',nargs='+',type=int,default=[10,50,100,200]);a.add_argument('--tasks',type=int,default=3);a.add_argument('--interval',type=int,default=100);a.add_argument('--tag',default='');args=a.parse_args()
    repo=P(args.repo).resolve(); out=repo/'proto7-1/notes/play/2026-10-03-astra-5-infra-evidence/scale'
    ctypes.CDLL(None).prctl(36,1,0,0,0) # harness reaps otherwise orphaned runner children; not daemon behavior change
    metadata={'python':sys.version,'kernel':platform.release(),'cpu_count':os.cpu_count(),'affinity':len(os.sched_getaffinity(0)),'interval_ms':args.interval,'task_count_per_timeline_per_round':args.tasks,'task':['/bin/sleep','0.01'],'duration_target_s':args.seconds,'sampler_period_s':.25,'harness_subreaper':True,'notes':'No CPU isolation; daemon cpu excludes tick/tock/runner/task CPU. Proc count is sampled live processes matching root plus descendants. Action wall times include subprocess startup/wait. Product default archival enabled; active and old task dirs both counted.'}
    dump(out/f'metadata{args.tag}.json',metadata)
    summaries=[]
    for count in args.counts:
        root=P(tempfile.mkdtemp(prefix=f'astra5-scale-{count}-')); p=None;samples=[]
        try:
            for i in range(count):
                base=root/f'n{i:03}'/'.aos'
                dump(base/'timeline.json',{'interval_ms':args.interval})
                dump(base/'tasks.json',{'tasks':[{'name':f'p{j}','mode':'each','argv':['/bin/sleep','0.01']} for j in range(args.tasks)]})
            (root/'wrapper.py').write_text(WRAPPER)
            log=open(root/'daemon.stderr','w')
            env=os.environ.copy();env.pop('AOS7_AUDIT',None)
            usage0=resource.getrusage(resource.RUSAGE_CHILDREN)
            t0=time.monotonic();start_epoch=time.time();next_ctl=t0+1;ctl_id=0
            p=subprocess.Popen([sys.executable,str(root/'wrapper.py'),str(repo/'proto7-1/lib'),str(root),str(root/'timings.jsonl')],stdout=log,stderr=log,env=env,start_new_session=True)
            while time.monotonic()-t0<args.seconds and p.poll() is None:
                samples.append(snapshot(p.pid,str(root)));reap(p.pid)
                if time.monotonic()>=next_ctl:
                    dump(root/'.aosd/ctl'/f'probe-{ctl_id}.json',{'op':'rescan','by':'scale-probe','_probe_sent_mono':time.monotonic()})
                    ctl_id+=1;next_ctl=time.monotonic()+2
                time.sleep(.25)
            stopped=time.monotonic()
            p.send_signal(signal.SIGTERM)
            try: p.wait(timeout=30)
            except subprocess.TimeoutExpired: p.kill();p.wait()
            wait_done=time.monotonic()
            log.close();reap(p.pid)
            rows=[json.loads(s) for s in (root/'timings.jsonl').read_text().splitlines()]
            active=[r for r in rows if r['end']<=stopped]
            ticks=[r for r in active if r['prog']=='aos7-tick'];tocks=[r for r in active if r['prog']=='aos7-tock']
            intervals=[];rounds=[]
            for i in range(count):
                ts=sorted(r['start'] for r in ticks if r['node']==f'n{i:03}')
                intervals += [(b-a)*1000 for a,b in zip(ts,ts[1:])]
                rounds.append(len(ts))
            latency=[]
            for t in tocks:
                candidates=[r for r in ticks if r['node']==t['node'] and r.get('round')==t.get('round')]
                if candidates: latency.append((t['start']-(candidates[-1]['start']+args.interval/1000))*1000)
            files=[x for x in root.rglob('*') if x.is_file()]
            useful=[s for s in samples if s.get('daemon_cpu_s') is not None]
            cpu=(useful[-1]['daemon_cpu_s']-useful[0]['daemon_cpu_s'])/(useful[-1]['mono']-useful[0]['mono'])*100 if len(useful)>1 else None
            status_ts=[r['end'] for r in active if r['prog']=='status'];ctls=[r for r in active if r['prog']=='ctl']
            usage1=resource.getrusage(resource.RUSAGE_CHILDREN)
            all_cpu=(usage1.ru_utime+usage1.ru_stime)-(usage0.ru_utime+usage0.ru_stime)
            summary={'start_mono':t0,'first_status_s':min((r['end']-t0 for r in rows if r['prog']=='status'),default=None),'start_epoch_s':start_epoch,'end_epoch_s':time.time(),'aggregate_cpu_s_including_shutdown':round(all_cpu,3),'daemon_waited_tick_tock_cpu_s':round((useful[-1]['daemon_waited_children_cpu_s']-useful[0]['daemon_waited_children_cpu_s']),3) if useful else None,'status_update_gap_ms':stats([(b-a)*1000 for a,b in zip(status_ts,status_ts[1:])]),'ctl_receipt_ms':stats([(r['end']-r['start'])*1000 for r in ctls]),'timelines':count,'sample_wall_s':round(stopped-t0,3),'shutdown_wait_s':round(wait_done-stopped,3),'shutdown_and_analysis_wall_s':round(time.monotonic()-stopped,3),'daemon_rc':p.returncode,'tick_ms':stats([(r['end']-r['start'])*1000 for r in ticks]),'tock_ms':stats([(r['end']-r['start'])*1000 for r in tocks]),'actual_interval_ms':stats(intervals),'tock_start_minus_planned_deadline_ms':stats(latency),'completed_ticks_per_timeline':stats(rounds),'daemon_cpu_pct_one_core':round(cpu,2) if cpu is not None else None,'daemon_rss_peak_kib':max(s['daemon_rss_kib'] or 0 for s in samples),'daemon_fd_peak':max(s['daemon_fd'] or 0 for s in samples),'live_processes_sample_peak':max(s['processes_live'] for s in samples),'file_count_final':len(files),'file_bytes_final':sum(f.stat().st_size for f in files),'task_dirs_final':sum(1 for f in files if f.name=='birth.json'),'nonzero_action_rc':sum(r.get('rc',0)!=0 for r in rows),'exceptions':[r for r in rows if 'exception'in r]}
            dump(out/f'summary-{count}{args.tag}.json',summary);dump(out/f'samples-{count}{args.tag}.json',samples)
            for name in ['status.json','log.jsonl']:
                src=root/'.aosd'/name
                if src.exists():
                    data=src.read_text(); lines=data.splitlines(keepends=True);buf='';idx=0
                    for line in lines:
                        if len((buf+line).encode())>180000:
                            (out/f'daemon-{count}{args.tag}-{idx:02}-{name}').write_text(buf);buf='';idx+=1
                        buf+=line
                    if buf: (out/f'daemon-{count}{args.tag}-{idx:02}-{name}').write_text(buf)
            (out/f'daemon-{count}{args.tag}.stderr').write_text((root/'daemon.stderr').read_text()[-180000:])
            # Each raw shard < 190 KB.
            buf='';idx=0
            for row in rows:
                line=json.dumps(row)+'\n'
                if len(buf.encode())+len(line.encode())>180000:
                    (out/f'timings-{count}{args.tag}-{idx:02}.jsonl').write_text(buf);buf='';idx+=1
                buf+=line
            if buf: (out/f'timings-{count}{args.tag}-{idx:02}.jsonl').write_text(buf)
            summaries.append(summary);print(json.dumps(summary),flush=True)
        finally:
            if p and p.poll() is None: p.kill();p.wait()
            # Clean tracked experiment processes only; detached runners include root in argv.
            for d in P('/proc').iterdir():
                if not d.name.isdigit() or int(d.name)==os.getpid():continue
                try:
                    if str(root).encode() in (d/'cmdline').read_bytes():os.kill(int(d.name),signal.SIGKILL)
                except (ProcessLookupError,OSError):pass
            time.sleep(.1);reap(p.pid if p else -1);shutil.rmtree(root)
    dump(out/f'summary-all{args.tag}.json',summaries)

if __name__=='__main__':main()
