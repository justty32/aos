from common import *
from unittest import mock
import aos7_fs as fs, aos7_tick as tick, aos7_tock as tock

def unknown_owner(s):
    n=s.node(action_timeout_s=.2);write(s.root/'.aosd/gen.json',{'gen':1})
    code="import os,sys,time;sys.path.insert(0,sys.argv[1]);import aos7_fs as fs\nwith fs.action_lock(sys.argv[2],sys.argv[3]):\n open(sys.argv[4],'w').write('held')\n time.sleep(60)\n"
    p=s.start(args=[sys.executable,'-c',code,str(LIB),str(s.root),str(n),str(s.root/'held')],env={'AOS7_GEN':'1'})
    wait(lambda:(s.root/'held').exists());ow=read(n/'.aos/action.owner.json');write(n/'.aos/action.owner.json',dict(ow,starttime=None))
    d=s.start();time.sleep(1.1);before=read(n/'.aos/round.json');logs=rows(s.root/'.aosd/log.jsonl');holder_alive=task.pid_alive(p.pid)
    # Restore recorded identity and verify bounded recovery, without releasing the lock ourselves.
    write(n/'.aos/action.owner.json',ow);wait(lambda:(read(n/'.aos/round.json',{}) or {}).get('round',0)>=2)
    return {'holder_alive_before_repair':holder_alive,'round_before_repair':before,'timeouts':[x for x in logs if x.get('incomplete')],'after_repair':read(n/'.aos/round.json'),'holder_alive_after_repair':task.pid_alive(p.pid),'note':'starttime null simulates unavailable identity at owner write; separate stale-unreadable.json tests live /proc lookup returning None'}

def cleanup_atexit(s):
    helper=s.root/'helper.py';parent=s.root/'parent.py';ready=s.root/'ready.json'
    parent.write_text("import json,os,signal,time,sys\nsignal.signal(signal.SIGTERM,signal.SIG_IGN)\nk=os.fork()\nif k==0:\n time.sleep(60)\nelse:\n open(sys.argv[1],'w').write(json.dumps({'parent':os.getpid(),'child':k}))\n time.sleep(60)\n")
    helper.write_text("import subprocess,sys,time,os\nsys.path.insert(0,sys.argv[1]);import _proc\np=_proc.track(None,subprocess.Popen([sys.executable,sys.argv[2],sys.argv[3]],start_new_session=True),grace=.1,group=True)\nwhile not os.path.exists(sys.argv[3]):time.sleep(.01)\n# Normal interpreter exit invokes the same atexit fallback used after KeyboardInterrupt.\n")
    p=s.start(args=[sys.executable,str(helper),str(PRODUCT/'tests'),str(parent),str(ready)]);ids=wait(lambda:read(ready));t=time.monotonic();p.wait(8);time.sleep(.05)
    return {'helper_rc':p.returncode,'registered':{'group':True,'grace':.1},'atexit_elapsed_s':round(time.monotonic()-t,3),'pids':ids,'parent_alive':task.pid_alive(ids['parent']),'child_alive_before_harness_cleanup':task.pid_alive(ids['child'])}

def owner_collision(s):
    sub=s.root/'n/inner/sub';n=s.node(items=[{'name':'first','mode':'keep','argv':['aos7-daemon','$AOS7_SUBROOT'],'subroot':'n/inner/sub','allow_stop':False}]);p=s.start()
    st=wait(lambda:read(sub/'.aosd/status.json'));before=read(sub/'.aosd/owner.json')
    s.node('n/inner',items=[{'name':'second','mode':'keep','argv':['aos7-daemon','$AOS7_SUBROOT'],'subroot':'n/inner/sub','allow_stop':True}])
    ow=wait(lambda:(x if (x:=read(sub/'.aosd/owner.json',{})).get('node')=='n/inner' else None))
    exitfile=s.root/'n/inner/.aos/tasks'/ow['tid']/'exit.json';wait(lambda:read(exitfile));current=read(sub/'.aosd/status.json')
    write(sub/'.aosd/ctl/stop.json',{'op':'stop','kill':True});receipt=wait(lambda:read(sub/'.aosd/ctl-done/stop.json'))
    return {'old_owner':before,'new_owner':ow,'actual_pid_before':st['pid'],'actual_pid_after':current['pid'],'failed_claimant_exit':read(exitfile),'receipt':receipt}

if __name__=='__main__':
    case('owner-starttime-missing-lock',unknown_owner);case('cleanup-atexit-group',cleanup_atexit);case('owner-cross-node-collision',owner_collision)
