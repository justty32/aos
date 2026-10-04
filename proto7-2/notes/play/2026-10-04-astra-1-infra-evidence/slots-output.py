#!/usr/bin/env python3
import pathlib,sys,os,tempfile,json,time
HERE=pathlib.Path(__file__).resolve().parent;TOP=HERE.parents[2]
os.environ['PYTHONDONTWRITEBYTECODE']='1';tempfile.tempdir=str(HERE);sys.path.insert(0,str(TOP/'tests'))
from base import CoreCase
from aos7_fs import read_json
c=CoreCase();c.setUp();root=c.root;out={'notes':'Known W10 boundary: a single live run can grow out.log; not per-round historical file leakage.','samples':[]}
try:
 code='import sys,os;sys.path.insert(0,'+repr(str(TOP/'lib'))+');from aos7_fs import wait_tock\nlast=0\nwhile True:\n last=wait_tock(os.environ["AOS7_TASK"],last)\n print("x"*4095,flush=True)\n'
 n=c.mknode('a',[{'name':'chatty','mode':'keep','argv':[sys.executable,'-c',code]}])
 for rnd in range(1,11):
  c.itick();c.wait_pid(n,'chatty');c.itock();p=pathlib.Path(c.slot(n,'chatty'))/'out.log'
  c.wait_for(lambda:p.stat().st_size>=rnd*4096)
  if rnd in [1,5,10]:
   paths=[p for p in (pathlib.Path(n)/'.aos').rglob('*') if p.is_file()]
   out['samples'].append({'round':rnd,'run':c.birth(n,'chatty')['run'],'files':len(paths),'aos_bytes':sum(p.stat().st_size for p in paths),'out_log_bytes':p.stat().st_size})
finally:
 c.doCleanups();out['cleanup_root_removed']=not os.path.exists(root)
(HERE/'slots-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
