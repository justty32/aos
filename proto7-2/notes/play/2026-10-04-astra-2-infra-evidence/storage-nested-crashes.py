"""SIGKILL at real os.replace, outside built-in fault hooks: nested mount infrastructure tmp."""
import os, sys, pathlib, tempfile, json, subprocess
E=pathlib.Path(__file__).resolve().parent;TOP=E.parents[2]
os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.dont_write_bytecode=True
tempfile.tempdir=str(E);sys.path.insert(0,str(TOP/'tests'))
from base import CoreCase
from aos7_fs import write_json,read_json
c=CoreCase();c.setUp();root=c.root;out={}
child='''import os,sys,signal
sys.path.insert(0,sys.argv[1]);import aos7_tick,aos7_mount
orig=os.replace
def cut(src,dst,*a,**k):
 if sys.argv[4] in str(dst):os.kill(os.getpid(),signal.SIGKILL)
 return orig(src,dst,*a,**k)
os.replace=cut
if sys.argv[4]=="/mount-done/":aos7_tick.tick(sys.argv[2],"a")
else:aos7_mount.request(sys.argv[3],"allowed/other",name="other")
'''
try:
    node=c.mknode('a',[{'name':'keep','mode':'keep','argv':['sleep','3600']}])
    c.itick();c.wait_pid(node,'keep');c.itock();sd=pathlib.Path(c.slot(node,'keep'))
    write_json(sd/'mount-req/x.json',{'name':'x','path':'allowed/x'})
    def tmp():return sorted(str(p.relative_to(sd)) for p in sd.rglob('*') if p.is_file() and '.tmp.' in p.name)
    out['before']=tmp();out['returncodes']={}
    for where in ['/mount-done/','/mount-req/']:
        codes=[]
        for _ in range(5):
            p=subprocess.run([sys.executable,'-B','-c',child,str(TOP/'lib'),root,str(sd),where],capture_output=True,timeout=15)
            codes.append(p.returncode)
            if where=='/mount-done/':c.itock()
        out['returncodes'][where]=codes
    out['after_crashes']=tmp()
    for _ in range(10):c.itick();c.itock()
    out['after_10_healthy_rounds']=tmp()
    out['request_accepted']=read_json(sd/'mount-done/x.json')['result']['ok']
    out['kept_run']=c.birth(node,'keep')['run']
finally:
    c.doCleanups();out['cleanup_root_removed']=not pathlib.Path(root).exists()
(E/'storage-nested-crashes.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(out))
