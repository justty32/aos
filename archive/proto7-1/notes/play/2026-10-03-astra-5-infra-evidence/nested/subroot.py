#!/usr/bin/env python3
"""Native cold startup with declared subroot but without pre-made .aosd."""
import importlib.util,json,pathlib,sys,tempfile,time
P=pathlib.Path; HERE=P(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('probe',HERE/'reproduce.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
out=[]
for i in range(3):
 root=P(tempfile.mkdtemp(prefix='astra5-nested-subroot-'));ps=[];r={'root':str(root)}
 try:
  child=root/'n/child';child.mkdir(parents=True)
  t=m.task('child',[str(m.BIN/'aos7-daemon'),'$AOS7_TASK/mnt/sub'],{'sub':'n/child'});t['subroot']='n/child'
  m.node(root,'n',[t]);m.node(child,'n',[m.task('leaf',[sys.executable,'-c','import time;time.sleep(90)'])])
  m.launch(root,ps);time.sleep(1.1)
  r['parent_log']=[json.loads(x) for x in (root/'.aosd/log.jsonl').read_text().splitlines()]
  r['child_log']=[json.loads(x) for x in (child/'.aosd/log.jsonl').read_text().splitlines()]
  r['status']=[m.read(q/'.aosd/status.json') for q in [root,child]]
  r['births']={str(p.relative_to(root)):m.read(p) for p in root.rglob('birth.json')}
  r['exits']={str(p.relative_to(root)):m.read(p) for p in root.rglob('exit.json')}
  r['processes']=m.procs(root)
 finally:
  # Freeze all owned processes first: prevent fresh tasks between kill scan and reap.
  for q in m.procs(root):
   try:m.os.kill(q['pid'],m.signal.SIGSTOP)
   except ProcessLookupError:pass
  r['cleanup']=m.clean(root,ps)
 out.append(r)
(HERE/'subroot.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps([{'parent_node_plus':[e['node'] for e in r['parent_log'] if e['ev']=='node+'],'parent_node_minus':[e['node'] for e in r['parent_log'] if e['ev']=='node-'],'birth_node_ids':[v.get('node') for v in r['births'].values()],'exits':r['exits']} for r in out],ensure_ascii=False))
