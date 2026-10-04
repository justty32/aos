#!/usr/bin/env python3
"""New edge probes on real tick/tock/keep/once tasks; inherits fixture helpers only."""
import json, os, sys, time, unittest, subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
TOP=next(p for p in HERE.parents if p.name=='proto7-2')
sys.path[:0]=[str(TOP/'packs/step/tests'),str(TOP/'tests')]
import test_step as t
OUT=HERE/'resends';OUT.mkdir(exist_ok=True);ROWS=[];CLEAN=[]
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2))
class Edges(t.TestStepProbes):
    def doCleanups(self):
        root=self.root;result=super().doCleanups();live=[]
        for p in Path('/proc').iterdir():
            if not p.name.isdigit():continue
            try:
                env=(p/'environ').read_bytes().split(b'\0');target=('AOS7_ROOT='+root).encode()
                if any(e==target or e.startswith(target+b'/') for e in env) and (p/'stat').read_text().split(') ',1)[1].split()[0]!='Z':live.append(int(p.name))
            except OSError:pass
        CLEAN.append(dict(case=self._testMethodName,root=root,root_removed=not Path(root).exists(),live_pids=live));return result
    def edge(self,setting,manual=False):
        start=time.monotonic();limit=1 if setting is None else setting
        a={'on_unknown':'resend'}
        if setting is not None:a['max_resends']=setting
        node=self.setup_job('edge',t.probe_table('edge',a=a,gate=True));Path(self.jd(node,'edge','gate-a')).touch();req=None;frames=[]
        for k in range(1,limit+2):
            self.run_until(node,'edge',lambda:len(self.ran(node,'edge-a'))==k and (self.birth(node,'step-edge-a') or {}).get('run'),limit=25)
            p=self.frame(node,'edge')['pending'];req=req or p['request']
            self.assertEqual((p['request'],p['attempt'],p['resends']),(req,f'{req}-a{k}',k-1))
            self.wait_for(lambda:os.path.exists(self.jd(node,'edge','gate-a.entered')),10,'child gate')
            os.unlink(self.jd(node,'edge','gate-a.entered'))
            frames.append(self.frame(node,'edge'))
            t.aos7_ctl.task_ctl(self.slot(node,'step-edge-a'),why='astra6 max_resends',run=self.birth(node,'step-edge-a')['run'])
            if k<=limit:self.run_until(node,'edge',lambda:(self.frame(node,'edge').get('pending') or {}).get('attempt')==f'{req}-a{k+1}',limit=25)
        self.run_until(node,'edge',lambda:self.frame(node,'edge').get('phase')=='halted',limit=25)
        fr=self.frame(node,'edge');frames.append(fr)
        self.assertEqual((fr['halt']['kind'],fr['tries'][req],len(self.ran(node,'edge-a'))),('unknown',limit+1,limit+1))
        for _ in range(3):self.cycle(node,'edge')
        self.assertEqual(len(self.ran(node,'edge-a')),limit+1)
        if manual:
            os.unlink(self.jd(node,'edge','gate-a'))
            r=self.step_cli(node,'resume','jobs/edge','--resend');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            self.run_until(node,'edge',lambda:self.frame(node,'edge').get('phase')=='ended',limit=25)
            fr=self.frame(node,'edge');frames.append(fr)
            self.assertEqual(fr['accepted']['a']['request'],req);self.assertEqual(fr['accepted']['a']['attempt'],f'{req}-a{limit+2}')
            self.assertEqual(len(self.ran(node,'edge-a')),limit+2)
        row=dict(case=self._testMethodName,configured=setting,automatic_resends=limit,initial_plus_automatic=limit+1,manual_resume=manual,seconds=time.monotonic()-start,frames=frames)
        ROWS.append(row);dump(OUT/(self._testMethodName+'.json'),row)
    def test_edge_zero(self):self.edge(0)
    def test_edge_default(self):self.edge(None)
    def test_edge_three(self):self.edge(3)
    def test_edge_manual_after_zero(self):self.edge(0,True)
start=time.monotonic()
suite=unittest.TestSuite(Edges(x) for x in ['test_edge_zero','test_edge_default','test_edge_three','test_edge_manual_after_zero'])
with (OUT/'run.log').open('w') as f:r=unittest.TextTestRunner(stream=f,verbosity=2).run(suite)
dump(OUT/'results.json',dict(run=r.testsRun,failures=len(r.failures),errors=len(r.errors),seconds=time.monotonic()-start,rows=ROWS,cleanups=CLEAN))
(OUT/'cleanup-ps.txt').write_text(subprocess.run(['ps','-eo','pid,ppid,pgid,stat,args'],capture_output=True,text=True).stdout)
print(json.dumps(dict(run=r.testsRun,success=r.wasSuccessful(),seconds=time.monotonic()-start)))
raise SystemExit(0 if r.wasSuccessful() else 1)
