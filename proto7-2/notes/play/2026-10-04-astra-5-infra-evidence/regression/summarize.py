#!/usr/bin/env python3
"""Collect regression evidence after run_suites and probes finish; never edits product files."""
import json,pathlib,hashlib,re,subprocess,datetime
P=pathlib.Path(__file__).resolve().parent
load=lambda p:json.loads((P/p).read_text())
suites=load('suites.json')
assert len(suites)==3,suites
for row in suites:
 text=(P/f"suite-{row['run']}.log").read_text()
 m=re.search(r'Ran (\d+) tests in ([\d.]+)s',text)
 row.update(tests=int(m[1]),unittest_seconds=float(m[2]),ok=bool(re.search(r'^OK$',text,re.M)),failures=re.findall(r'^(?:FAIL|ERROR): (.+)$',text,re.M))
 assert row['tests']==322 and row['rc']==0 and row['ok'],row
core=load('core/results.json');step=load('step/step-probes.json');f47=load('step/f47-step.json');long=load('step/longrun.json')
assert all(r['status']=='passed' for r in core)
assert all('probe_error' not in r for r in step+f47)
assert long['observed_closed_round']['open'] is False and long['observed_closed_round']['round']>=450
stats={'closed_round':long['observed_closed_round']['round'],'seconds':long['elapsed_s'],'samples':len(long['samples']),'completed':len(long['completed']),'report_ok':sum(x['report_ok'] for x in long['completed']),'all_first_attempt':all(x['tries']==[1,1] for x in long['completed']),'errors':len(long['errors']),'ended_job_files':sorted(set(x['job']['files'] for x in long['completed'])),'ended_job_bytes':[min(x['job']['bytes'] for x in long['completed']),max(x['job']['bytes'] for x in long['completed'])], 'all_phase_file_ranges':{k:[min(x[k]['files'] for x in long['samples']),max(x[k]['files'] for x in long['samples'])] for k in ['job','node','root']}}
assert stats['ended_job_files']==[10]
before=load('source-hashes-before.json');after={p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest() for p in before};assert before==after
(P/'source-hashes-after.json').write_text(json.dumps(after,indent=2))
roots=[x['root'] for x in core]+step[-1]['roots']+[x['cleanup']['root'] for x in f47]+[long['cleanup']['root']]
ps=subprocess.run(['ps','-eo','pid,ppid,pgid,stat,args'],capture_output=True,text=True,check=True).stdout
(P/'ps-final.txt').write_text(ps)
rows=[]
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:env=(p/'environ').read_bytes().split(b'\0')
 except OSError:continue
 if any(any(e==('AOS7_ROOT='+r).encode() or e.startswith(('AOS7_ROOT='+r+'/').encode()) for r in roots) for e in env):rows.append(int(p.name))
cleanup={'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'known_case_roots':roots,'roots_remaining':[r for r in roots if pathlib.Path(r).exists()],'matching_pids':rows,'ps_root_matches':[s for s in ps.splitlines() if any(r in s for r in roots)],'suite_pids':[r['pid'] for r in suites],'suite_pids_remaining':[r['pid'] for r in suites if pathlib.Path('/proc',str(r['pid'])).exists()]}
assert not any(cleanup[k] for k in ['roots_remaining','matching_pids','ps_root_matches','suite_pids_remaining']),cleanup
(P/'cleanup.json').write_text(json.dumps(cleanup,indent=2))
result={'suites':suites,'unstable_cases':[],'core_probe_count':len(core),'step_probe_count':len(step)-1,'f47_step_probe_count':len(f47),'core_lines':load('core-lines.json'),'longrun':stats,'new_B_or_G':[],'source_files_unchanged':len(before),'harness_notes':load('harness-notes.json'),'cleanup':cleanup}
(P/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in result.items() if k not in ['cleanup','core_lines']},ensure_ascii=False,indent=2))
