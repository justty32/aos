"""Real history task, SIGKILL after summary commit but before notification, then healthy replay."""
import os,sys,pathlib,tempfile,json,subprocess,time
E=pathlib.Path(__file__).resolve().parent;TOP=E.parents[2]
sys.dont_write_bytecode=True;os.environ['PYTHONDONTWRITEBYTECODE']='1';tempfile.tempdir=str(E)
sys.path.insert(0,str(TOP/'tests'))
from base import CoreCase
from aos7_fs import read_json,read_jsonl
c=CoreCase();c.setUp();root=c.root;out={}
child='''import os,sys,signal
sys.path.insert(0,sys.argv[1]);import aos7_tock
orig=aos7_tock.write_json
def cut(path,obj):
 orig(path,obj)
 if str(path).endswith('/last-round.json'):os.kill(os.getpid(),signal.SIGKILL)
aos7_tock.write_json=cut
aos7_tock.tock(sys.argv[2],'a')
'''
try:
    n=c.mknode('a',[{'name':'history','mode':'keep','argv':[sys.executable,str(TOP/'modules/history.py')]}])
    c.itick();c.wait_pid(n,'history');hp=pathlib.Path(n)/'history/a.jsonl'
    p=subprocess.run([sys.executable,'-B','-c',child,str(TOP/'lib'),root],capture_output=True,timeout=15)
    time.sleep(.2)
    out['crash_returncode']=p.returncode
    out['after_crash']={'round':c.round_json(n),'summary_round':c.last_round(n).get('round'),'notification':read_json(pathlib.Path(c.slot(n,'history'))/'tock.json'),'history_rows':len(read_jsonl(hp))}
    replay=c.itock()
    c.wait_for(lambda:len(read_jsonl(hp))==1)
    out['after_replay']={'replayed':replay.get('replayed'),'round_open':c.round_json(n).get('open'),'history_rounds':[r.get('round') for r in read_jsonl(hp)]}
finally:
    c.doCleanups();out['cleanup_root_removed']=not pathlib.Path(root).exists()
(E/'history-replay.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(out))
