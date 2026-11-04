"""Shared stdlib harness. Re-run: python3 proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/group5/probe_core.py"""
import os, sys, json, time, signal, subprocess, tempfile, shutil, traceback, tarfile
from pathlib import Path
sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[5]
TOP = REPO / 'proto7-2'
OUT = Path(__file__).resolve().parent
BIN = TOP / 'bin'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
os.environ['AOS7_TEST_HOOKS'] = str(TOP/'tests/_hooks.py')
sys.path.insert(0, str(TOP/'lib'))

def write(p, obj):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_name(p.name+'.group5tmp');tmp.write_text(json.dumps(obj,ensure_ascii=False));tmp.replace(p)

def read(p, default=None):
    try:return json.loads(Path(p).read_text())
    except (OSError,ValueError):return default

def wait(fn, timeout=12):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        v=fn()
        if v:return v
        time.sleep(.025)
    raise AssertionError('timeout: '+repr(fn))

def own_pids(root):
    token=str(root).encode();out=[]
    for d in Path('/proc').iterdir():
        if not d.name.isdigit() or int(d.name)==os.getpid():continue
        try:
            env=(d/'environ').read_bytes();cmd=(d/'cmdline').read_bytes()
            if token in env or token in cmd:
                stat=(d/'stat').read_bytes().rsplit(b')',1)[1].split()
                if stat[0]!=b'Z':out.append((int(d.name),stat[19].decode()))
        except OSError:pass
    return out

class Harness:
    def __init__(self, name):
        self.name=name;self.root=Path(tempfile.mkdtemp(prefix='astra7-group5-'+name+'-'));self.results=[];self.ps=[]
        self.env=dict(os.environ,TMPDIR=str(self.root),PYTHONDONTWRITEBYTECODE='1')
    def cli(self, name, *args, env=None, timeout=20):
        p=subprocess.run([sys.executable,str(BIN/name),*map(str,args)],env=dict(self.env,**(env or {})),cwd=REPO,capture_output=True,text=True,timeout=timeout)
        return p
    def start(self,name,*args,env=None):
        log=open(self.root/('proc-%d.log'%len(self.ps)),'w')
        p=subprocess.Popen([sys.executable,str(BIN/name),*map(str,args)],env=dict(self.env,**(env or {})),cwd=REPO,stdout=log,stderr=log,start_new_session=True)
        self.ps.append((p,log));return p
    def node(self,nid='a',tasks=None,interval=100):
        n=self.root/nid;write(n/'.aos/tasks.json',{'tasks':tasks or []});write(n/'.aos/timeline.json',{'interval_ms':interval});return n
    def ctl(self,*args):
        p=self.cli('aos7-ctl','daemon',self.root,*args);assert p.returncode==0,(p.returncode,p.stdout,p.stderr);return p
    def action(self,name,nid='a',env=None,rc=0):
        p=self.cli('aos7-'+name,self.root,nid,env=env)
        assert p.returncode==rc,(name,p.returncode,p.stdout,p.stderr)
        try:return json.loads(p.stdout.strip().splitlines()[-1])
        except (ValueError,IndexError):return {'rc':p.returncode,'stderr':p.stderr}
    def case(self,id,scenario,fn):
        t=time.monotonic()
        try:
            measured=fn();rec=dict(id=id,scenario=scenario,pass_=measured.get('acceptance_pass',True) if isinstance(measured,dict) else True,probe_completed=True,measured=measured)
        except Exception as e:
            rec=dict(id=id,scenario=scenario,pass_=False,error=repr(e),traceback=traceback.format_exc())
        rec['elapsed_s']=round(time.monotonic()-t,3);rec['pass']=rec.pop('pass_');self.results.append(rec)
        write(OUT/(self.name+'.json'),self.results);print(id,rec['pass'],flush=True)
    def finish(self):
        initial=own_pids(self.root)
        for pid,_ in initial:
            try:os.kill(pid,signal.SIGTERM)
            except ProcessLookupError:pass
        time.sleep(.2)
        killed=[]
        for _ in range(4):
            left=own_pids(self.root)
            if not left:break
            for pid,start in left:
                try:os.kill(pid,signal.SIGKILL);killed.append([pid,start])
                except ProcessLookupError:pass
            time.sleep(.15)
        for p,f in self.ps:
            try:p.wait(timeout=2)
            except subprocess.TimeoutExpired:pass
            f.close()
        left=own_pids(self.root)
        # Only archive small factual artifacts; no copied source tree or unrelated files.
        with tarfile.open(OUT/(self.name+'-snapshots.tar.gz'),'w:gz') as tar:
            for p in self.root.rglob('*'):
                if p.is_file() and not p.is_symlink() and p.stat().st_size<60000 and p.suffix in ('.json','.jsonl','.log','.txt'):
                    tar.add(p,arcname=str(p.relative_to(self.root)))
        rec={'root':str(self.root),'initial_owned':initial,'killed':killed,'remaining':left}
        if not left:shutil.rmtree(self.root);rec['root_removed']=not self.root.exists()
        write(OUT/(self.name+'-cleanup.json'),rec)

def slot(node,name):return node/'.aos/tasks'/name
def ended(node,name,run=None):
    return wait(lambda:(lambda x:x if x and (run is None or x.get('run')==run) else None)(read(slot(node,name)/'exit.json')))
