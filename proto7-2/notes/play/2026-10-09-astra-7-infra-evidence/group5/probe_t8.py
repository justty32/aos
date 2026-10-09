"""T8 green/red controls in disposable source copies; no tracked edits.
Re-run: systemd-run --user --scope -q -p TasksMax=800 -p RuntimeMaxSec=1800 python3 proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/group5/probe_t8.py
"""
from common import *
import re, hashlib
h=Harness('t8')

# Mutations remove injection in a copied TEST file, preserving its assertions.
CASES=[
 ('T8-01','tests/core','test_matrix_once.TestLaunchCrash.test_once_runner_before_exit','tests/core/test_matrix_once.py',
  'env={"AOS7_TEST_RUNNER_CRASH": point}', 'env={}'),
 ('T8-02','packs/step/tests','test_step.TestStepProbes.test_crash_points_advance_once','packs/step/tests/test_step.py',
  'self.crash_at(node, job, point)', 'pass  # group5: omit crash marker'),
 ('T8-03','modules/subd/tests','test_subd_recover.TestInterrupted.test_killed_after_reaped_before_new_gen','modules/subd/tests/test_subd_recover.py',
  'p2 = self.run_subd(run=2, env={"AOS7_TEST_CRASH": point})','p2 = self.run_subd(run=2, env={})'),
 ('T8-04','packs/budget/tests','test_budget_ledger.TestCrash.test_ledger_points','packs/budget/tests/test_budget_ledger.py',
  'self.crash_at(bd, point)\n                p = self.popen', 'pass  # group5: omit crash marker\n                p = self.popen'),
 ('T8-05','tests/core','test_matrix_faults.TestFileUnknown.test_last_round_readback_U','tests/core/test_matrix_faults.py',
  'if reads == 2:', 'if reads == -1:  # group5: disable injected readback'),
 ('T8-06','tests/core','test_matrix_docs.TestLastRoundJson.test_ended_once_replay_finish_tock_seen_round','tests/core/test_matrix_docs.py',
  'self.crash("aos7-tock", point)','self.tock()  # group5: no crash'),
 ('T8-07','modules/diag/tests','test_diag.TestDiag.test_unsure_listed','modules/diag/tests/test_diag.py',
  'self.diag("a", env=f.env)', 'self.diag("a", env=dict(f.env, AOS7_TEST_FAULT=f.env["AOS7_TEST_FAULT"].split(";")[0]))'),
 ('T8-08','modules/once_retry/tests','test_once_retry.TestRetryLost.test_retry_lost_value_false','modules/once_retry/tests/test_once_retry.py',
  'self.crash("aos7-tick", "after-birth")\n        sums = []','self.tick()  # group5: no after-birth crash\n        sums = []'),
]

def run_test(top,folder,pattern,tag):
    start=time.monotonic();cmd=[sys.executable,str(top/'tests/run_all.py'),folder,'-k',pattern,'-v']
    p=subprocess.run(cmd,cwd=REPO,env=h.env,capture_output=True,text=True,timeout=240)
    log=p.stdout+p.stderr;(OUT/(tag+'.log')).write_text(log)
    ran=re.search(r'Ran (\d+) tests?',log)
    return {'rc':p.returncode,'ran':int(ran.group(1)) if ran else 0,'elapsed_s':round(time.monotonic()-start,3),'command':cmd,'log':tag+'.log','tail':log[-5500:]}

def one(case):
    ident,folder,pattern,file,old,new=case
    copy=h.root/ident/'proto7-2'
    shutil.copytree(TOP,copy,ignore=shutil.ignore_patterns('notes','__pycache__','*.pyc'))
    p=copy/file;source=p.read_text();assert source.count(old)==1,(file,source.count(old))
    p.write_text(source.replace(old,new))
    # Red FIRST, then original green, as requested. Original file hashes remain equal.
    before=hashlib.sha256((TOP/file).read_bytes()).hexdigest()
    red=run_test(copy,folder,pattern,ident+'-red')
    green=run_test(TOP,folder,pattern,ident+'-green')
    after=hashlib.sha256((TOP/file).read_bytes()).hexdigest()
    result={'injection':{'removed_from':file,'old':old,'new':new,'original_sha256_before':before,'original_sha256_after':after},'assertion':'same test red without injection, original green, selected >=1 test','red':red,'green':green}
    # Persist the raw result before assertion, including failed expectations.
    write(OUT/(ident+'-pair.json'),result)
    assert before==after and red['ran']>=1 and green['ran']>=1 and red['rc']!=0 and green['rc']==0,result
    return result

if __name__=='__main__':
    selected=set(sys.argv[1:])
    if selected:h.results=[r for r in read(OUT/'t8.json',[]) if r['id'] not in selected]
    try:
        for case in CASES:
            if selected and case[0] not in selected:continue
            h.case(case[0],'removed-injection negative control and original',lambda c=case:one(c))
        if not selected:h.case('ported-interval','original migrated test once',lambda:run_test(TOP,'tests/core','test_errors.TestTimelineConfig.test_interval_huge_int','ported-interval'))
    finally:h.finish()
