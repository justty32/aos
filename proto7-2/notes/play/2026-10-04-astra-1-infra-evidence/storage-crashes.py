"""SIGKILL before atomic rename: count hidden files too, then healthy recovery."""
import os,sys,pathlib,tempfile,json,subprocess
E=pathlib.Path(__file__).resolve().parent; TOP=E.parents[2]
sys.dont_write_bytecode=True;os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.path.insert(0,str(TOP/'lib'))
from aos7_fs import write_json
from aos7_tick import tick
from aos7_tock import tock
child="""import os,sys,signal
sys.path.insert(0,sys.argv[1]);import aos7_fs,aos7_tock
orig=os.replace
def cut(src,dst,*a,**k):
 if str(dst).endswith('/last-round.json'):os.kill(os.getpid(),signal.SIGKILL)
 return orig(src,dst,*a,**k)
os.replace=cut
aos7_tock.tock(sys.argv[2],'a')
"""
with tempfile.TemporaryDirectory(prefix='storage-work-',dir=E) as root:
 n=pathlib.Path(root)/'a';(n/'.aos').mkdir(parents=True);write_json(str(n/'.aos/tasks.json'),{'tasks':[]});tick(root,'a')
 def measure():
  files=[p for p in (n/'.aos').rglob('*') if p.is_file()]
  tmp=[p for p in files if '.tmp.' in p.name]
  return {'files':len(files),'bytes':sum(p.stat().st_size for p in files),'hidden_temporary_files':len(tmp),'hidden_temporary_bytes':sum(p.stat().st_size for p in tmp)}
 before=measure();rc=[]
 for k in range(20):
  p=subprocess.run([sys.executable,'-B','-c',child,str(TOP/'lib'),root],capture_output=True,timeout=10);rc.append(p.returncode)
 after_crashes=measure();tock(root,'a')
 for k in range(10):tick(root,'a');tock(root,'a')
 result={'before':before,'fault':'SIGKILL before last-round.json atomic rename, 20 separate PIDs','returncodes':rc,'after_crashes':after_crashes,'after_10_healthy_rounds':measure()}
(E/'storage-crashes.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result))
