"""Only evidence and owned temporary roots are written. No LLM calls.
The harness alone is a Linux subreaper; this is not a product modification.
"""
import ctypes, importlib.util, json, os, pathlib, shutil, signal, subprocess, sys, tempfile, time, uuid
OUT = pathlib.Path(__file__).resolve().parent
PRODUCT = OUT.parents[2]
REPO = PRODUCT.parent
LIB = PRODUCT/'lib'
BIN = PRODUCT/'bin'
OLD = OUT.parent/'2026-10-03-astra-5-infra-evidence'
sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
sys.path[:0] = [str(LIB), str(PRODUCT/'tests')]
import aos7_fs as fs, aos7_task as task
ctypes.CDLL(None).prctl(36, 1, 0, 0, 0)
def write(p,v): fs.write_json(str(p),v)
def read(p,default=None): return fs.read_json(str(p),default)
def rows(p): return fs.read_jsonl(str(p))
def save(n,v): (OUT/(n+'.json')).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def wait(fn,seconds=8):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        v=fn()
        if v:return v
        time.sleep(.01)
    raise TimeoutError('wait expired')
def load(name,p):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def proc_table():
    out={}
    for p in pathlib.Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:
            st=(p/'stat').read_text().rsplit(')',1)[1].split()
            out[int(p.name)]={'state':st[0],'ppid':int(st[1]),'start':st[19]}
        except (OSError,ValueError):pass
    return out
def descendants():
    table=proc_table();keep={os.getpid()}
    while True:
        new={p for p,s in table.items() if s['ppid'] in keep}-keep
        if not new:break
        keep|=new
    return {p:s for p,s in table.items() if p in keep and p!=os.getpid()}
def drain():
    for _ in range(100):
        for pid,st in descendants().items():
            try:os.kill(pid,signal.SIGKILL)
            except ProcessLookupError:pass
        while True:
            try:
                if os.waitpid(-1,os.WNOHANG)[0]==0:break
            except ChildProcessError:break
        if not descendants():return []
        time.sleep(.01)
    return list(descendants())
class Space:
    def __init__(self,label):
        self.root=pathlib.Path(tempfile.mkdtemp(prefix='astra7-'+label+'-'));self.ps=[];self.cleanup={}
    def __enter__(self):return self
    def start(self,prog='aos7-daemon',nid=None,env=None,args=None):
        command=args or [sys.executable,str(BIN/prog),str(self.root)]+([] if nid is None else [nid])
        p=subprocess.Popen(command,env=dict(os.environ,**(env or {})),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        self.ps.append(p);return p
    def run(self,prog,nid='n',env=None):
        p=subprocess.run([sys.executable,str(BIN/prog),str(self.root),nid],env=dict(os.environ,**(env or {})),capture_output=True,text=True,timeout=15)
        return {'rc':p.returncode,'out':json.loads(p.stdout) if p.stdout.strip() else None,'err':p.stderr[-1500:]}
    def node(self,nid='n',items=(),**config):
        n=self.root/nid if nid!='.' else self.root
        write(n/'.aos/timeline.json',dict(interval_ms=100,**config));write(n/'.aos/tasks.json',{'tasks':list(items)});return n
    def __exit__(self,*exc):
        for p in self.ps:
            if p.poll() is None:
                try:p.terminate();os.kill(p.pid,signal.SIGCONT)
                except ProcessLookupError:pass
        for p in self.ps:
            try:p.wait(timeout=4)
            except subprocess.TimeoutExpired:pass
        remain=drain()
        self.cleanup={'remaining_children_before_delete':remain,'root':str(self.root)}
        if remain:raise RuntimeError('refusing to delete space with live children')
        shutil.rmtree(self.root)
        self.cleanup['root_exists']=self.root.exists()
SLEEP=[sys.executable,'-c','import time;time.sleep(60)']

def case(name,fn):
    t=time.monotonic();s=Space(name);r={'case':name}
    try:
        with s:r.update(fn(s) or {})
    except Exception as e:
        import traceback
        r['harness_error']=repr(e);r['trace']=traceback.format_exc()[-2500:]
    r['seconds']=round(time.monotonic()-t,3);r['cleanup']=s.cleanup
    save(name,r);print(name, r.get('harness_error','recorded'),flush=True);return r
