from common import *
from unittest import mock
import aos7_daemon as daemon, aos7_kernel as kernel, aos7_agent_tools as agenttools, aos7_audit as audit

def inspect(path):
    raw=path.read_bytes();out={'bytes':len(raw),'prefix_hex':raw[:40].hex(),'physical_lines':len(raw.splitlines())}
    for name,fn in [('read',lambda:fs.read_jsonl(str(path))),('tail',lambda:fs.tail_jsonl(str(path),10))]:
        try:out[name]=fn()
        except Exception as e:out[name+'_error']=repr(e)
    return out

def logs(s):
    n=s.node();td=n/'.aos/tasks/a-r1';write(td/'birth.json',{'tid':'a-r1','mounts':{}});results={}
    for binary in (False,True):
        tail=b'{"broken":' if not binary else b'{"text":"\xe4\xb8'
        label='utf8' if binary else 'ascii'
        d=daemon.Daemon(str(s.root));log=s.root/'.aosd/log.jsonl';log.parent.mkdir(exist_ok=True);log.write_bytes(tail)
        try:d.log(ev='recovered');results[label+'-log']=inspect(log)
        finally:os.close(d.rfd)
        sent=n/'sent.jsonl';sent.write_bytes(tail)
        ctx={'node':str(n),'node_id':'n','root':str(s.root),'task':str(td),'tid':'a-r1'}
        message=agenttools.do_tool(ctx,{'tool':'send','to':'n','body':'local test'},1);results[label+'-sent']={**inspect(sent),'tool_result':message}
        decisions=td/'decisions.jsonl';decisions.write_bytes(tail)
        # Exercise real one_round writer while replacing only the pure rule output.
        with mock.patch.object(kernel,'run_rules',return_value=([{'round':1,'rule':'test','target':'n','op':'pause','why':'probe'}],{})):
            kernel.one_round(ctx,1)
        results[label+'-decisions']=inspect(decisions)
        writes=td/'writes.jsonl';writes.write_bytes(tail)
        code="import os;open(os.path.join(os.environ['AOS7_NODE'],'first.txt'),'w').write('one');open(os.path.join(os.environ['AOS7_NODE'],'second.txt'),'w').write('two')"
        env=dict(os.environ,AOS7_ROOT=str(s.root),AOS7_NODE=str(n),AOS7_TASK=str(td),AOS7_TID='a-r1',AOS7_AUDIT='1',PYTHONPATH=str(LIB/'audit_site'))
        p=subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True,timeout=5)
        results[label+'-writes']={**inspect(writes),'worker_rc':p.returncode,'stderr':p.stderr}
        try:results[label+'-audit-scan']=audit.scan(str(s.root))
        except Exception as e:results[label+'-audit-scan']={'error':repr(e)}
    return results

def runner_io(s):
    n=s.node();out=[]
    for kind in ('out-dir','exit-dir','birth-invalid'):
        td=n/'.aos/tasks'/kind;write(td/'birth.json',{'tid':kind,'argv':['true']})
        if kind=='out-dir':(td/'out.log').mkdir()
        if kind=='exit-dir':(td/'exit.json').mkdir()
        if kind=='birth-invalid':write(td/'birth.json',['nonobject'])
        fd=os.open(td,os.O_RDONLY|os.O_DIRECTORY)
        try:p=subprocess.run([sys.executable,str(BIN/'aos7-run'),str(td),str(fd)],cwd=n,pass_fds=(fd,),capture_output=True,text=True,timeout=4)
        finally:os.close(fd)
        out.append({'kind':kind,'rc':p.returncode,'stderr':p.stderr,'state':task.task_state(str(td)),'exit':read(td/'exit.json'),'files':sorted(x.name for x in td.iterdir())})
    return {'cases':out}

def late_move(s):
    import aos7_tick as tick,aos7_task as task
    n=s.node();other=s.root/'moved';body="import os,json;from pathlib import Path;p=Path(os.environ['AOS7_TASK']);p.mkdir(parents=True,exist_ok=True);(p/'progress.json').write_text(json.dumps({'cwd':os.getcwd(),'node':os.environ['AOS7_NODE'],'task':os.environ['AOS7_TASK']}))"
    write(n/'.aos/tasks.json',{'tasks':[{'name':'x','mode':'keep','argv':[sys.executable,'-c',body]}]})
    real=task.subprocess.Popen;hit=[]
    def move(args,*a,**kw):
        if len(args)>1 and str(args[1]).endswith('/aos7-run') and not hit:n.rename(other);hit.append(True)
        return real(args,*a,**kw)
    with mock.patch.object(task.subprocess,'Popen',move):res=tick.tick(str(s.root),'n')
    wait(lambda:read(other/'.aos/tasks/x-r1/exit.json'))
    return {'barrier':'immediately before runner Popen, after same_dir check','tick':res,'moved_exit':read(other/'.aos/tasks/x-r1/exit.json'),'ghost_progress':read(n/'.aos/tasks/x-r1/progress.json'),'old_node_recreated':n.exists(),'moved_progress':read(other/'.aos/tasks/x-r1/progress.json')}
if __name__=='__main__':
    case('jsonl-writers',logs);case('runner-io',runner_io);case('late-node-move',late_move)
