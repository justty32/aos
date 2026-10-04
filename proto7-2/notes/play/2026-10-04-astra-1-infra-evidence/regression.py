"""Run existing tests with bytecode disabled and temporary data confined to evidence."""
import os,sys,json,time,pathlib,tempfile,unittest,io,shutil
E=pathlib.Path(__file__).resolve().parent
TOP=E.parents[2]
os.environ['PYTHONDONTWRITEBYTECODE']='1'
sys.dont_write_bytecode=True
scratch=E/'regression-work'
scratch.mkdir(exist_ok=True)
os.environ['TMPDIR']=str(scratch)
tempfile.tempdir=str(scratch)
sys.path.insert(0,str(TOP/'tests'))
class Result(unittest.TextTestResult):
    def __init__(self,*a,**k):super().__init__(*a,**k);self.rows=[]
    def addSuccess(self,t):super().addSuccess(t);self.rows.append({'test':t.id(),'status':'pass'})
    def addFailure(self,t,e):super().addFailure(t,e);self.rows.append({'test':t.id(),'status':'fail','detail':self._exc_info_to_string(e,t)})
    def addError(self,t,e):super().addError(t,e);self.rows.append({'test':t.id(),'status':'error','detail':self._exc_info_to_string(e,t)})
suite=unittest.defaultTestLoader.discover(str(TOP/'tests'))
start=time.monotonic();stream=io.StringIO()
r=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=Result).run(suite)
left=list(scratch.rglob('*'))
out={'command':'PYTHONDONTWRITEBYTECODE=1 python3 '+str(pathlib.Path(__file__).relative_to(E.parents[3])), 'tests':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'seconds':round(time.monotonic()-start,3),'results':r.rows,'temporary_leftovers':[str(p.relative_to(scratch)) for p in left]}
(E/'regression.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
if not left:shutil.rmtree(scratch)
print(json.dumps({k:v for k,v in out.items() if k!='results'},ensure_ascii=False))
sys.exit(not r.wasSuccessful())
