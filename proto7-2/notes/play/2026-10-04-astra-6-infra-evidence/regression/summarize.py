#!/usr/bin/env python3
import json,pathlib,re,statistics,subprocess,os,tarfile
OUT=pathlib.Path(__file__).resolve().parent
load=lambda p:json.loads((OUT/p).read_text())
core=load('core/results.json'); step=load('step/step-probes.json'); f47=load('step/f47-step.json'); long=load('step/longrun.json')
assert len(core)==17 and all(x['status']=='passed' for x in core)
assert len(step)==9 and not any('probe_error' in x for x in step)
assert len(f47)==2 and not any('probe_error' in x for x in f47)
by={x['probe']:x for x in step}
assert by['entered_wait_patience']['frames'][-1]['halt']['kind']=='timeout'
assert by['delayed_intent_unknown']['after']['halt']['kind']=='unknown' and by['delayed_intent_unknown']['runs_a']==0
r=by['resend_at_most_once'];assert r['runs_a']==2 and r['after']['halt']['kind']=='unknown' and r['snapshots'][0]['pending']['request']==r['snapshots'][1]['pending']['request']
assert by['close_active_refused']['returncode']==3 and by['close_active_refused']['phase']=='running'
assert long['observed_closed_round']['round']>=450 and long['observed_closed_round']['open'] is False
assert not long['errors'] and long['completed'] and all(x['report_ok'] and x['tries']==[1,1] for x in long['completed'])
summary={'core_pass':17,'step_pass':8,'f47_step_pass':2,'longrun':{'closed_round':long['observed_closed_round']['round'],'seconds':long['elapsed_s'],'samples':len(long['samples']),'completed_snapshots':len(long['completed']),'completed_job_files':sorted({x['job']['files'] for x in long['completed']}),'completed_job_bytes':[min(x['job']['bytes'] for x in long['completed']),max(x['job']['bytes'] for x in long['completed'])],'phases':{k:{'files':[min(x[k]['files'] for x in long['samples']),max(x[k]['files'] for x in long['samples'])]} for k in ('job','node','root')},'errors':len(long['errors'])}}
suites=load('suites.json')
for s in suites:
 if 'cases_count' in s:s['timed_single_line_cases_count']=s.pop('cases_count')
 text=(OUT/('suite-%s.log'%s['run'])).read_text()
 s['tests']=int(re.search(r'Ran (\d+) tests',text).group(1))
 s['unittest_seconds']=float(re.search(r'Ran \d+ tests in ([0-9.]+)s',text).group(1))
 s['overall_ok']=bool(re.search(r'\nOK\s*$',text))
 names=re.findall(r'^(test\w+ \(test_adapt[^\n]+\))(.*?)(?=^test\w+ \(|\n----------------------------------------------------------------------)',text,re.M|re.S)
 s['adapt']=[{'test':n,'ok':bool(re.search(r'\.\.\. ok\s*$',body))} for n,body in names]
 assert s['rc']==0 and s['tests']==363 and s['overall_ok'] and len(s['adapt'])==28 and all(x['ok'] for x in s['adapt']),s
(OUT/'suites.json').write_text(json.dumps(suites,ensure_ascii=False,indent=2)+'\n')
summary['suites']=suites
summary['partial_per_case_timing_note']='suite-*-cases.json 僅包含沒有額外 docstring 行的 unittest verbose 案，耗時從輸出開始標記到結尾量；完整每案 pass/fail 以 suite-*.log 為準。'
(OUT/'results.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
with tarfile.open(OUT/'longrun-snapshots.tar.gz','w:gz') as tar:tar.add(OUT/'step/longrun.json',arcname='step/longrun.json')
print(json.dumps({k:v for k,v in summary.items() if k!='suites'},ensure_ascii=False,indent=2))
print('suites',[(s['run'],s['tests'],s['seconds'],len(s['adapt'])) for s in suites])
