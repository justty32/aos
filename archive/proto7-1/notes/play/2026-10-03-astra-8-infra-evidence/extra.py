from common import *
from boundaries import hook,ctl,status
from test_astra7 import FAIL_HOOK

def audit_parallel(s):
    n=s.node();td=n/'.aos/tasks/test-r1';write(td/'birth.json',{'tid':'test-r1','mounts':{}});(td/'writes.jsonl').write_bytes(b'{"broken":"\xe4\xb8')
    env={'AOS7_AUDIT':'1','AOS7_ROOT':str(s.root),'AOS7_NODE':str(n),'AOS7_TASK':str(td),'PYTHONPATH':str(LIB/'audit_site')}
    ps=[]
    for i in range(8):
        code=f"from pathlib import Path\nfor j in range(20):Path({str(n)!r},str({i})+'-'+str(j)).write_text('x')"
        ps.append(s.start(args=[sys.executable,'-c',code],env=env))
    codes=[p.wait(8) for p in ps];recs,bad=fs.read_jsonl(str(td/'writes.jsonl'),with_bad=True)
    return {'workers':8,'writes_per_worker':20,'rcs':codes,'records':len(recs),'unique_paths':len({r['path'] for r in recs}),'bad_lines':bad}

def uncertain_round(s):
    # Product daemon cannot read round.json while its tock persistently cannot append.
    # Other actors can read/write that same file; fixed per-process fault boundary.
    code=FAIL_HOOK+'''
if os.path.basename(sys.argv[0])=='aos7-daemon':
 sys.path.insert(0,os.environ['HOOK_LIB']);import aos7_daemon_timeline as tl
 real=tl.read_json
 def unreadable(path,*a,**kw):
  if str(path).endswith('/round.json') and os.path.exists(os.environ['HOOK_FAIL']):return None
  return real(path,*a,**kw)
 tl.read_json=unreadable
'''
    n=s.node();(s.root/'fail').touch();d=s.start(env=hook(s,code));wait(lambda:read(n/'.aos/round.json',{}).get('round',0)>=3);before=read(n/'.aos/round.json');err=status(s);(s.root/'fail').unlink();wait(lambda:len(rows(n/'.aos/rounds.jsonl'))>=2);ctl(s.root,'stop',kill=True);d.wait(10)
    return {'fault':'daemon-only round.json read returns None (as fs.read_json does on EIO), tock ENOSPC; tick unaffected','before_recovery':before,'status_during_fault':err,'committed_rounds':[r['round'] for r in rows(n/'.aos/rounds.jsonl')]}
if __name__=='__main__':
    case('audit-parallel',audit_parallel);case('round-read-unknown',uncertain_round)
