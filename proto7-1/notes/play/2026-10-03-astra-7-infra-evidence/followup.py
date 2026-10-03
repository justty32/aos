from common import *
from unittest import mock
import aos7_tick as tick, aos7_tock as tock

def out_poison(s):
    n=s.node(items=[{'name':'x','mode':'keep','argv':['true']}]);real=task.subprocess.Popen;ps=[]
    def spawn(argv,*a,**kw):
        if len(argv)>1 and str(argv[1]).endswith('/aos7-run'):
            pathlib.Path(argv[2],'out.log').mkdir();p=real(argv,*a,**kw);ps.append(p);return p
        return real(argv,*a,**kw)
    with mock.patch.object(task.subprocess,'Popen',spawn):first=tick.tick(str(s.root),'n')
    rc=ps[0].wait(5);tock.tock(str(s.root),'n');next_=tick.tick(str(s.root),'n')
    return {'first':first,'runner_rc':rc,'next_tick':next_,'state':task.task_state(str(n/'.aos/tasks/x-r1')),'exit':read(n/'.aos/tasks/x-r1/exit.json'),'round':read(n/'.aos/round.json')}

def return_observed(s):
    root=s.root/'real';n=root/'n';write(n/'.aos/tasks.json',{'tasks':[{'name':'s','mode':'keep','argv':SLEEP}]});write(n/'.aos/timeline.json',{'interval_ms':100})
    d=s.start(args=[sys.executable,str(BIN/'aos7-daemon'),str(root)]);pid=wait(lambda:read(n/'.aos/tasks/s-r1/pid.json'))['pid'];m=s.root/'moved';root.rename(m)
    wait(lambda:read(m/'.aosd/status.json',{}).get('root_gone'));m.rename(root);rc=d.wait(10)
    return {'rc':rc,'task_alive':task.pid_alive(pid),'status':read(root/'.aosd/status.json'),'events':[r for r in rows(root/'.aosd/log.jsonl') if r.get('ev') in ('root-gone','stop')]}

def bind_daemon(s):
    src=s.root/'src';dst=s.root/'dst';src.mkdir();dst.mkdir()
    code='''import os,sys,subprocess,json,time,pathlib
sys.path.insert(0,sys.argv[1]);import aos7_fs as fs,aos7_task
src,dst=sys.argv[3:5]
fs.write_json(src+'/n/.aos/tasks.json',{'tasks':[{'name':'x','mode':'keep','argv':['sleep','60']}]})
fs.write_json(src+'/n/.aos/timeline.json',{'interval_ms':100})
r={};d=None;mounted=False
try:
 p=subprocess.run(['mount','--bind',src,dst],capture_output=True,text=True);r['mount_rc']=p.returncode;r['mount_err']=p.stderr
 if p.returncode:raise RuntimeError('bind failed')
 mounted=True;d=subprocess.Popen([sys.executable,sys.argv[2],dst],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 limit=time.monotonic()+6;pid=None
 while time.monotonic()<limit:
  pj=fs.read_json(src+'/n/.aos/tasks/x-r1/pid.json')
  if pj:pid=pj['pid'];break
  time.sleep(.01)
 r['task_started']=pid is not None;r['same_inode']=os.path.samestat(os.stat(src),os.stat(dst));time.sleep(.2)
 r['running_round']=fs.read_json(src+'/n/.aos/round.json')
 u=subprocess.run(['umount',dst],capture_output=True,text=True);r['ordinary_umount_rc']=u.returncode;r['ordinary_umount_error']=u.stderr
 r['umount_rc']=subprocess.run(['umount','-l',dst]).returncode if u.returncode else 0;mounted=r['umount_rc']!=0
 r['daemon_rc']=d.wait(timeout=10);r['status']=fs.read_json(src+'/.aosd/status.json');r['task_alive']=aos7_task.pid_alive(pid);r['dst_files']=os.listdir(dst)
finally:
 if d and d.poll() is None:d.terminate();d.wait(timeout=10)
 if mounted:subprocess.run(['umount',dst])
print(json.dumps(r))
'''
    p=subprocess.run(['unshare','--user','--map-root-user','--mount',sys.executable,'-c',code,str(LIB),str(BIN/'aos7-daemon'),str(src),str(dst)],capture_output=True,text=True,timeout=20)
    return {'rc':p.returncode,'result':json.loads(p.stdout) if p.stdout.strip() else None,'stderr':p.stderr,'private_user_mount_namespace':True}

def readback_torn(s):
    n=s.node();write(n/'.aos/spawn/one.json',{'name':'one','argv':['true']});hook=s.root/'hook';hook.mkdir();mark=s.root/'mark'
    (hook/'sitecustomize.py').write_text('''import os,sys,json
if os.path.basename(sys.argv[0])=='aos7-tock':
 sys.path.insert(0,os.environ['EDGE_LIB']);import aos7_fs
 real=aos7_fs.append_jsonl
 def torn(path,obj):
  if str(path).endswith('/rounds.jsonl') and not os.path.exists(os.environ['EDGE_MARK']):
   with open(path,'wb') as f:f.write(json.dumps(obj).encode()[:24])
   open(os.environ['EDGE_MARK'],'w').write('short append returned')
   return 0
  return real(path,obj)
 aos7_fs.append_jsonl=torn
''')
    p=s.start(env={'PYTHONPATH':str(hook),'EDGE_LIB':str(LIB),'EDGE_MARK':str(mark)});wait(mark.exists);wait(lambda:read(n/'.aos/round.json',{}).get('round',0)>=3);p.terminate();p.wait(10)
    return {'injection':'append writes only 24 bytes and returns; readback genuinely finds no committed summary','summaries':rows(n/'.aos/rounds.jsonl'),'round':read(n/'.aos/round.json'),'ended':read(n/'.aos/tasks/one-r1/ended.json'),'log_errors':[r for r in rows(s.root/'.aosd/log.jsonl') if r.get('ev')=='tock' and r.get('rc')]}
if __name__=='__main__':
    for name,fn in [('runner-out-poison',out_poison),('root-return-observed',return_observed),('bind-daemon',bind_daemon),('readback-torn-daemon',readback_torn)]:case(name,fn)
