#!/usr/bin/env python3
"""Read-only audit after per-case cleanup; never kill broad matches."""
import pathlib,json,subprocess,os
OUT=pathlib.Path(__file__).resolve().parent
roots=set();pids=set()
def walk(v):
 if isinstance(v,dict):
  for k,x in v.items():
   if k in ('root','roots'):
    for r in (x if isinstance(x,list) else [x]):
     if isinstance(r,str) and r.startswith('/tmp/'):roots.add(r)
   if k=='pid' and isinstance(x,int):pids.add(x)
   walk(x)
 elif isinstance(v,list):
  for x in v:walk(x)
for p in OUT.rglob('*.json'):
 if p.name=='cleanup.json' and p.parent==OUT:continue
 try:walk(json.loads(p.read_text()))
 except (ValueError,OSError):pass
live=[]
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit() or int(p.name)==os.getpid():continue
 try:
  env=(p/'environ').read_bytes().split(b'\0');cmd=(p/'cmdline').read_bytes().split(b'\0')
  matches=[r for r in roots if any(e.startswith(('AOS7_ROOT='+r).encode()) for e in env) or any(r.encode() in c for c in cmd)]
  if matches:live.append({'pid':int(p.name),'roots':matches,'cmdline':' '.join(c.decode(errors='replace') for c in cmd)})
 except OSError:pass
ps=subprocess.run(['ps','-eo','pid,ppid,pgid,stat,args'],capture_output=True,text=True,check=True).stdout
(OUT/'ps-final.txt').write_text(ps)
state={'roots':sorted(roots),'roots_remaining':[r for r in roots if pathlib.Path(r).exists()],'known_pids':sorted(pids),'known_pids_remaining':[p for p in pids if pathlib.Path('/proc',str(p)).exists()],'root_matching_processes':live}
(OUT/'cleanup.json').write_text(json.dumps(state,indent=2))
assert not state['roots_remaining'] and not state['known_pids_remaining'] and not live,state
print({'roots_checked':len(roots),'pids_checked':len(pids),'remaining':0})
