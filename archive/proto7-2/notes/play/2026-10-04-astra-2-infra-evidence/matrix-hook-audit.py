"""量測 healthy 矩陣指定的故障是否真的命中讀取點；不改產品。
重新執行的12案已包含在219案，不另加總唯一測試數。
"""
import os, sys, json, pathlib, tempfile, shutil, fnmatch
from unittest import mock
E=pathlib.Path(__file__).resolve().parent
TOP=E.parents[2]
sys.dont_write_bytecode=True
os.environ['PYTHONDONTWRITEBYTECODE']='1'
WORK=E/'matrix-hook-work'; WORK.mkdir(exist_ok=True)
os.environ['TMPDIR']=tempfile.tempdir=str(WORK)
sys.path.insert(0,str(TOP/'tests'))
sys.path.insert(0,str(TOP/'lib'))
import aos7_proc, aos7_fs
from test_matrix_faults import TestProcUnknown, PROC_OPS, ERRNOS
original=aos7_fs.inject
rows=[]
for op in PROC_OPS:
    for err in ERRNOS:
        hits=[]
        def count(actual_op,path):
            rules=os.environ.get('AOS7_TEST_FAULT','')
            for rule in rules.split(';'):
                parts=rule.split(':')
                if len(parts)==3 and parts[0]==actual_op and fnmatch.fnmatchcase(str(path),parts[1]):
                    hits.append({'op':actual_op,'path':str(path),'errno':parts[2]})
            return original(actual_op,path)
        c=TestProcUnknown(); c.setUp()
        row={'op':op,'errno':err}
        try:
            with mock.patch.object(aos7_proc,'inject',count), mock.patch.object(aos7_fs,'inject',count):
                c._healthy(op,err)
            row['status']='pass'
        except Exception as ex: row.update(status='error',error=repr(ex))
        finally: c.doCleanups()
        row['matching_injection_calls']=len(hits)
        rows.append(row)
left=[str(p.relative_to(WORK)) for p in WORK.rglob('*')]
if not left: shutil.rmtree(WORK)
out={'healthy_matrix':rows,'zero_hit_cases':sum(r['matching_injection_calls']==0 for r in rows),'temporary_leftovers':left}
(E/'matrix-hook-audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(out,ensure_ascii=False,indent=2))
