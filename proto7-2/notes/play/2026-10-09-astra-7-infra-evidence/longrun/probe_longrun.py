#!/usr/bin/env python3
"""Reproduce: python3 proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/longrun/probe_longrun.py step
For adapt use the same command with adapt. Standard library; real product CLIs only.
The script reexecutes inside a bounded systemd scope when invoked directly.
"""
import csv, hashlib, io, json, os, re, shutil, signal, subprocess, sys, tarfile, tempfile, time, traceback
from pathlib import Path
E=Path(__file__).resolve().parent
REPO=E.parents[4]
P=REPO/'proto7-2'
MODE=sys.argv[1]
if '--scoped' not in sys.argv:
    raise SystemExit(subprocess.call(['systemd-run','--user','--scope','-q','-p','TasksMax=800','-p','RuntimeMaxSec=1800',sys.executable,str(__file__),MODE,'--scoped'],cwd=REPO))
sys.dont_write_bytecode=True
os.environ['PYTHONDONTWRITEBYTECODE']='1'
for key in list(os.environ):
    if key.startswith('AOS7_'): os.environ.pop(key)
PY=sys.executable

def save(p,v):
    p=Path(p); p.parent.mkdir(parents=True,exist_ok=True)
    t=p.with_name('.'+p.name+'.qa-tmp'); t.write_text(json.dumps(v,ensure_ascii=False,separators=(',',':'))+'\n'); t.replace(p)
def read(p):
    try: return json.loads(Path(p).read_text())
    except (FileNotFoundError,json.JSONDecodeError): return {}
def wait(fn,timeout=30):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        v=fn()
        if v:return v
        time.sleep(.005)
    raise AssertionError('timeout waiting for '+str(fn))
def cli(prog,*args,cwd=None):
    cmd=[PY,str(prog),*map(str,args)]
    r=subprocess.run(cmd,cwd=cwd or REPO,capture_output=True,text=True,timeout=30)
    if r.returncode: raise AssertionError({'command':cmd,'rc':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
    return json.loads(r.stdout) if r.stdout.strip() else None

def files(root):
    # os.walk includes dot files and does not follow mounted directory symlinks.
    out=[]
    for parent,ds,fs in os.walk(root):
        for n in fs: out.append(str((Path(parent)/n).relative_to(root)))
        for n in ds:
            q=Path(parent)/n
            if q.is_symlink():out.append(str(q.relative_to(root))+'@')
    return sorted(out)
def proc(root):
    ans=[]; root=str(root).encode(); envwant=b'AOS7_ROOT='+root
    for d in Path('/proc').iterdir():
        if not d.name.isdigit() or int(d.name)==os.getpid():continue
        try:
            stat=(d/'stat').read_bytes().rsplit(b')',1)[1].split()
            if stat[0]==b'Z': continue
            env=(d/'environ').read_bytes().split(b'\0')
            cmd=(d/'cmdline').read_bytes().split(b'\0')
            if any(x==envwant or x.startswith(envwant+b'/') for x in env) or any(x==root or x.startswith(root+b'/') for x in cmd):
                ans.append({'pid':int(d.name),'starttime':stat[19].decode(),'cmd':[x.decode(errors='replace') for x in cmd if x]})
        except OSError:pass
    return ans

def rss(pid):
    d=Path('/proc')/str(pid); s=(d/'status').read_text()
    return {'pid':pid,'rss_kb':int(re.search(r'VmRSS:\s+(\d+)',s)[1]),'fd':len(list((d/'fd').iterdir()))}
class Space:
    def __init__(self,name):
        self.name=name;self.root=Path(tempfile.mkdtemp(prefix='astra7-longrun-'+name+'-'));self.daemon=None
        self.snap=tarfile.open(E/(name+'-snapshots.tar.gz'),'w:gz')
        self.report={'scenario':name,'injection':{'kind':'none; ordinary long run','fault_hooks_env':[]},'root':str(self.root),'checks':[]}
        save(E/(name+'-active.json'),{'root':str(self.root),'observer_pid':os.getpid()})
    def check(self,name,yes,actual):
        self.report['checks'].append({'assertion':name,'actual':actual,'pass':bool(yes)})
    def archive(self,name,obj):
        raw=json.dumps(obj,ensure_ascii=False,separators=(',',':')).encode(); i=tarfile.TarInfo(name+'.json');i.size=len(raw);self.snap.addfile(i,io.BytesIO(raw))
    def ctl(self,op,*args):return cli(P/'bin/aos7-ctl','daemon',self.root,op,*args)
    def finish(self):
        before=proc(self.root);daemon_rc=None
        if self.daemon and self.daemon.poll() is None:
            self.ctl('stop','--kill');daemon_rc=self.daemon.wait(timeout=30)
        elif self.daemon:daemon_rc=self.daemon.returncode
        killed=[]
        # Manual tick/tock has no daemon; verify root/starttime before each own PID signal.
        for _ in range(5):
            owned=proc(self.root)
            if not owned:break
            for row in owned:
                try:
                    current=(Path('/proc')/str(row['pid'])/'stat').read_bytes().rsplit(b')',1)[1].split()
                    if current[19].decode()==row['starttime']:
                        os.kill(row['pid'],signal.SIGTERM if _==0 else signal.SIGKILL);killed.append(row)
                except OSError:pass
            time.sleep(.15)
        after=proc(self.root)
        self.archive('final-tree',{'files':files(self.root)})
        # Final files plus per-round evidence, split naturally into a compact gzip archive.
        self.snap.add(self.root,arcname='final-root',recursive=True)
        self.snap.close()
        if not after:shutil.rmtree(self.root)
        cleanup={'root':str(self.root),'owned_before':before,'signalled':killed,'daemon_rc':daemon_rc,'remaining':after,'root_removed':not self.root.exists()}
        save(E/(self.name+'-cleanup.json'),cleanup)
        self.check('no own live process and temporary root removed',not after and not self.root.exists(),cleanup)
        self.report['pass']=all(x['pass'] for x in self.report['checks'])
        save(E/(self.name+'.json'),self.report)
        print(json.dumps({'mode':self.name,'pass':self.report['pass'],'checks':len(self.report['checks'])}),flush=True)

def normalize(names):
    return sorted(re.sub(r'([0-9a-f]{8,32})-(convert|stats)-\d+-a\d+',r'<inst>-\2-1-a1',re.sub(r'\.tmp\.\d+',r'.tmp.<pid>',n)) for n in names)

def step():
    s=Space('step');start=time.monotonic();r=s.report
    rounds=[];completed=[];inventories=[];seen_inst=[];last_inst=None;last_round=0;bad=[];samples=[];completed_ids=set();frame_max={}
    try:
        node=s.root/'a';job=node/'jobs/csv'
        shutil.copytree(P/'packs/step/examples/csv',job)
        table=read(job/'steps.json');table['options']={'restart_on_end':True};save(job/'steps.json',table)
        # Independent CSV oracle (not the example stats implementation).
        with (job/'data.csv').open() as f:src=list(csv.DictReader(f))
        expected={}
        for dept in sorted({v['dept'] for v in src}):
            vals=[float(v['amount']) for v in src if v['dept']==dept];expected[dept]={'n':len(vals),'sum':sum(vals),'avg':round(sum(vals)/len(vals),2)}
        save(node/'.aos/tasks.json',{'tasks':[{'name':'step-csv','mode':'keep','max_live':1,'argv':[PY,str(P/'packs/step/bin/aos7-step'),'run','jobs/csv']}]})
        save(node/'.aos/timeline.json',{'interval_ms':150,'early_tock':False})
        save(s.root/'.aosd/paused.json',{'paused':{'a':['qa']},'steps':{}})
        s.ctl('register','a')
        with (E/'step-daemon.log').open('w') as log:
            s.daemon=subprocess.Popen([PY,str(P/'bin/aos7-daemon'),str(s.root)],cwd=REPO,stdout=log,stderr=log,start_new_session=True)
        wait(lambda:read(s.root/'.aosd/status.json').get('nodes',{}).get('a',{}).get('phase')=='paused')
        s.ctl('resume','a','--owner','qa','--rounds','450')
        while time.monotonic()-start<1200:
            fr=read(job/'frame.json');lr=read(node/'.aos/last-round.json');nr=lr.get('round',0)
            inst=fr.get('inst')
            if inst and inst!=last_inst:
                if last_inst and last_inst not in completed_ids:bad.append({'missed_completion':last_inst})
                seen_inst.append(inst);last_inst=inst
            for k,v in fr.items():
                if isinstance(v,(dict,list)):frame_max[k]=max(frame_max.get(k,0),len(v))
            if fr.get('phase')=='halted' or (job/'error.json').exists():
                bad.append({'frame':fr,'error':read(job/'error.json')});break
            if nr>last_round:
                inv={'round':nr,'job':files(job),'slots':files(node/'.aos/tasks'),'aosd':files(s.root/'.aosd')}
                inventories.append(inv)
                row={'round':nr,'errors':lr.get('errors'),'tasks_error':lr.get('tasks_error'),'counts':{k:len(inv[k]) for k in ('job','slots','aosd')}}
                rounds.append(row)
                if lr.get('errors') or lr.get('tasks_error'):bad.append(row)
                if nr==1 or nr%25==0:samples.append({'round':nr,**rss(s.daemon.pid)})
                last_round=nr
                if nr%50==0:print('step closed',nr,flush=True)
            if fr.get('phase')=='ended' and inst not in completed_ids:
                data=read(job/'out/data.json');report=read(job/'out/report.json')
                results={x.stem:read(x) for x in (job/'results').rglob('*.json')}
                inv={'round':nr,'job':files(job),'slots':files(node/'.aos/tasks'),'aosd':files(s.root/'.aosd')}
                if read(job/'frame.json').get('inst')==inst:
                    acc=fr.get('accepted',{});convert_req=acc.get('convert',{}).get('request')
                    good=(fr.get('end')=='ok' and report=={'from':convert_req,'rows':len(src),'by_dept':expected} and data.get('request')==convert_req and data.get('rows')==[dict(v,amount=float(v['amount'])) for v in src])
                    result_good=len(results)==2 and all(v.get('ok') is True and v.get('code')==0 and v.get('inst')==inst and v.get('attempt','').endswith('-a1') and all(hashlib.sha256((node/p).read_bytes()).hexdigest()==h for p,h in v.get('artifacts',{}).items()) for v in results.values())
                    tries=fr.get('tries',{});attempt_ok=len(tries)==2 and list(tries.values())==[1,1] and all(x.startswith(inst+'-') for x in tries)
                    snap={'frame':fr,'data':data,'report':report,'results':results,'files':inv}
                    s.archive('completed/'+inst,snap)
                    completed.append({'round':nr,'inst':inst,'report_ok':good,'result_ok':result_good,'attempt1':attempt_ok,'resends':fr.get('resends'),'job_files':len(inv['job']),'slots_files':len(inv['slots'])})
                    completed_ids.add(inst)
                    if not (good and result_good and attempt_ok and fr.get('resends')=={}):bad.append(snap)
            status=read(s.root/'.aosd/status.json');ns=status.get('nodes',{}).get('a',{})
            if nr>=450 and ns.get('phase')=='paused':
                time.sleep(.1);break
            if s.daemon.poll() is not None:raise AssertionError('daemon unexpectedly exited')
            time.sleep(.003)
        closed=read(node/'.aos/round.json');fr=read(job/'frame.json');paused=read(s.root/'.aosd/paused.json');nodes=read(s.root/'.aosd/nodes.json');status=read(s.root/'.aosd/status.json')
        samples.append({'round':closed.get('round'),**rss(s.daemon.pid)})
        r.update(seconds=round(time.monotonic()-start,3),observed_closed=closed,final_frame=fr,paused=paused,nodes=nodes,status=status,completed=completed,frame_max_entries=frame_max,resources=samples,errors=bad,rounds_observed=len(rounds),instances_seen=len(seen_inst))
        s.archive('round-inventories',inventories);s.archive('rounds',rounds)
        # All names retained in archive. Result identifiers intentionally change on restart;
        # compare simultaneous cardinality and normalized completed-job names, never glob-hide dot/tmp files.
        canonical=[normalize(x['job']) for x in inventories if not any('.tmp' in y for y in x['job'])]
        counts={k:[len(x[k]) for x in inventories] for k in ('job','slots','aosd')}
        r['inventory']={'first':inventories[0] if inventories else {},'last':inventories[-1] if inventories else {},'max_counts':{k:max(v,default=0) for k,v in counts.items()},'last_half_max_counts':{k:max(v[len(v)//2:],default=0) for k,v in counts.items()},'max_tmp_simultaneous':max((sum('.tmp' in n for k in ('job','slots','aosd') for n in x[k]) for x in inventories),default=0),'normalization':'Only instance/attempt id and writer PID; raw names including dot/tmp preserved.'}
        s.check('round 450 closed; no sampled round omitted',closed.get('round')==450 and closed.get('open') is False and [x['round'] for x in rounds]==list(range(1,451)),{'closed_round':closed.get('round'),'open':closed.get('open'),'observed':len(rounds)})
        s.check('every completed snapshot correct; attempts all one; no halted/error',bool(completed) and not bad and all(x['report_ok'] and x['result_ok'] and x['attempt1'] for x in completed),{'completed':len(completed),'instances_seen':len(seen_inst),'unfinished_final':fr.get('phase')!='ended','errors':bad})
        s.check('frame dictionaries bounded and resends remains empty',frame_max.get('resends')==0 and frame_max.get('tries',99)<=2 and frame_max.get('accepted',99)<=2,frame_max)
        s.check('job/slot/daemon filename counts bounded throughout (including dot/tmp)',bool(inventories) and max(counts['job'])<=20 and max(counts['slots'])<=45 and max(counts['aosd'])<=15,r['inventory'])
        stable_daemon=[set(x['aosd']) for x in inventories if x['round']>=10]
        daemon_names=set().union(*stable_daemon) if stable_daemon else set()
        daemon_non_tmp={x for x in daemon_names if '.tmp.' not in x}
        s.check('daemon persistent filename set unchanged after r10',bool(stable_daemon) and all({n for n in names if '.tmp.' not in n}==daemon_non_tmp for names in stable_daemon),{'names':sorted(daemon_non_tmp),'observations':len(stable_daemon),'transient_tmp_names':sorted(daemon_names-daemon_non_tmp)})
        s.check('nodes no reaping; countdown exhausted and qa paused',not nodes.get('reaping') and paused=={'paused':{'a':['qa']},'steps':{}},{'nodes':nodes,'paused':paused})
        s.check('RSS growth <4MiB; fd tail <= head+3',samples[-1]['rss_kb']-samples[0]['rss_kb']<4096 and samples[-1]['fd']<=samples[0]['fd']+3,{'head':samples[0],'tail':samples[-1],'rss_ratio':round(samples[-1]['rss_kb']/samples[0]['rss_kb'],4),'fd_ratio':round(samples[-1]['fd']/samples[0]['fd'],4),'note':'measurement thresholds, not a contractual memory ceiling'})
    except Exception as e:
        s.check('probe completed',False,{'error':repr(e),'traceback':traceback.format_exc()});raise
    finally:s.finish()

def adapt():
    s=Space('adapt');start=time.monotonic();rows=[];base=None;bad=[]
    try:
        src=s.root/'src';dst=s.root/'dst';reg=dst/'in/temp.json';slot=dst/'.aos/tasks/adapter'
        decl={'sense':'temp','src':'src/out/temp.json','src_clock':'src/.aos/round.json','max_age':None,'patience':2,'stall':None,'steps':[{'select':'value.x'},{'scale':{'mul':.1,'q':.05,'round':1,'as':'c'}},{'threshold':{'ge':80,'as':'hot'}}],'need':['c']}
        save(dst/'adapt/temp.json',decl)
        save(src/'.aos/tasks.json',{'tasks':[]})
        save(dst/'.aos/tasks.json',{'tasks':[{'name':'adapter','mode':'keep','max_live':1,'argv':[PY,str(P/'packs/adapt/bin/aos7-adapt'),'run','adapt/temp.json'],'mounts':{'data':'src/out','clock':'src/.aos'}}]})
        for n in range(1,322):
            for action in ('tick','tock'):cli(P/('bin/aos7-'+action),s.root,'src')
            source={'v':1,'seq':n,'round':n,'value':{'x':801,'other':'omitted'}};save(src/'out/temp.json',source)
            for action in ('tick','tock'):cli(P/('bin/aos7-'+action),s.root,'dst')
            z=wait(lambda:read(reg) if read(reg).get('my_round')==n else None)
            frame=read(slot/'state.json');inv=files(s.root);closed=read(dst/'.aos/round.json')
            sha=hashlib.sha256(json.dumps(source,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            okay=(z.get('state')=='ok' and z.get('value')=={'c':80.1,'hot':True} and z.get('err')=={'c':.05} and z.get('basis')=={'src':'src/out/temp.json','sha':sha,'seq':n,'src_round':n} and z.get('skipped')==0 and z.get('held')==0 and z.get('age_src_rounds')==0 and z.get('omitted')==['value.other'] and closed.get('round')==n and closed.get('open') is False)
            # All filesystem names exact, including hidden and temporary files, at each settled round.
            if base is None:base=inv
            same=inv==base
            row={'round':n,'register_ok':okay,'filenames_equal_r1':same,'files':len(inv),'state_keys':sorted(frame),'register_keys':sorted(z)}
            rows.append(row);s.archive('rounds/'+str(n),{'register':z,'frame':frame,'files':inv,'closed':closed,'source':source,'expected_sha':sha})
            if not okay or not same:bad.append({'row':row,'register':z,'sha':sha,'extra':sorted(set(inv)-set(base)),'missing':sorted(set(base)-set(inv))})
            if n%40==0:print('adapt closed',n,flush=True)
        s.report.update(seconds=round(time.monotonic()-start,3),rounds=321,additional_rounds=320,first=rows[0],last=rows[-1],filenames=base,errors=bad,register_final=z,frame_final=frame)
        s.archive('per-round-checks',rows)
        s.check('r1 plus 320 rounds; each register and closed round independently checked',len(rows)==321 and not bad,{'rounds':len(rows),'bad':bad})
        s.check('exact full filename set unchanged each settled round, including hidden/tmp',all(x['filenames_equal_r1'] for x in rows),{'baseline':base,'count':len(base),'samples':len(rows)})
        s.check('register/frame key sets unchanged on all 321 rounds',all(x['state_keys']==rows[0]['state_keys'] and x['register_keys']==rows[0]['register_keys'] for x in rows),{'frame_keys':rows[-1]['state_keys'],'register_keys':rows[-1]['register_keys']})
    except Exception as e:
        s.check('probe completed',False,{'error':repr(e),'traceback':traceback.format_exc()});raise
    finally:s.finish()

if __name__=='__main__':globals()[MODE]()
