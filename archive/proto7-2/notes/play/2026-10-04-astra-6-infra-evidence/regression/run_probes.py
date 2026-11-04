#!/usr/bin/env python3
import os,sys,time,tempfile,pathlib,json,subprocess,shutil
OUT=pathlib.Path(__file__).resolve().parent
root=pathlib.Path(tempfile.mkdtemp(prefix='astra6-regression-'))
rows=[]
try:
 for name,script,args in [('core','core/probe_core.py',[]),('step','step/probe_step.py',[]),('f47','step/probe_f47.py',[]),('longrun','step/run_comparison.py',['--mode','longrun','--rounds','450'])]:
  start=time.monotonic()
  logpath=OUT/({'core':'core/probe.log','step':'step/probe.log','f47':'step/f47.log','longrun':'step/longrun.log'}[name])
  with logpath.open('w') as log:
   p=subprocess.Popen([sys.executable,str(OUT/script),*args],stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','TMPDIR':str(root)})
   rc=p.wait()
  rows.append({'name':name,'pid':p.pid,'rc':rc,'seconds':round(time.monotonic()-start,3)})
  (OUT/'probes.json').write_text(json.dumps(rows,indent=2));print(rows[-1],flush=True)
finally:
 remaining=[str(p.relative_to(root)) for p in root.rglob('*')]
 shutil.rmtree(root)
 (OUT/'probes-temp-cleanup.json').write_text(json.dumps({'root':str(root),'remaining_before_cleanup':remaining,'root_removed':not root.exists()},indent=2))
