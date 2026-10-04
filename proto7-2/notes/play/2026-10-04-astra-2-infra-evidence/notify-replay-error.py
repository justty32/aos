"""Real filesystem notification failure (directory at tock.json), normal vs replay path."""
import os,sys,pathlib,tempfile,json,subprocess
E=pathlib.Path(__file__).resolve().parent;TOP=E.parents[2]
sys.dont_write_bytecode=True;os.environ['PYTHONDONTWRITEBYTECODE']='1';tempfile.tempdir=str(E)
sys.path.insert(0,str(TOP/'tests'))
from base import CoreCase
c=CoreCase();c.setUp();root=c.root;out={}
try:
    for nid,replay in [('normal',False),('replay',True)]:
        n=c.mknode(nid,[{'name':'keep','mode':'keep','argv':['sleep','60']}])
        c.itick(nid);c.wait_pid(n,'keep')
        if replay:
            p=subprocess.run([sys.executable,'-B',str(TOP/'bin/aos7-tock'),root,nid],env=dict(os.environ,AOS7_TEST_CRASH='tock-summary'),capture_output=True,timeout=15)
            out['crash_returncode']=p.returncode
        (pathlib.Path(c.slot(n,'keep'))/'tock.json').mkdir()
        summary=c.itock(nid);r=c.round_json(n)
        out[nid]={'round_open':r['open'],'notify_errors':r.get('notify_errors'),'summary_errors':summary.get('errors'),'replayed':summary.get('replayed',False)}
finally:
    c.doCleanups();out['cleanup_root_removed']=not pathlib.Path(root).exists()
(E/'notify-replay-error.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(out))
