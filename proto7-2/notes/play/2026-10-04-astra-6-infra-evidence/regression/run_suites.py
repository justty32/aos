#!/usr/bin/env python3
"""Unmodified run_all.py three times. Per-case wall time is observed verbose-output duration."""
import subprocess,time,json,os,pathlib,datetime,re,tempfile,shutil
OUT=pathlib.Path(__file__).resolve().parent
rows=[]
root=pathlib.Path(tempfile.mkdtemp(prefix='astra6-suites-'))
(OUT/'suite-temp.json').write_text(json.dumps({'root':str(root)}))
try:
 for i in range(1,4):
    started=datetime.datetime.now(datetime.timezone.utc).isoformat(); t=time.monotonic(); cases=[]; line=''; case_start=None
    with (OUT/f'suite-{i}.log').open('w') as log:
        p=subprocess.Popen(['python3','proto7-2/tests/run_all.py','-v'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','TMPDIR':str(root)})
        (OUT/'suite-active.json').write_text(json.dumps({'run':i,'pid':p.pid,'started_utc':started}))
        print(f'suite {i} pid={p.pid} started={started}',flush=True)
        while True:
            char=p.stdout.read(1)
            if not char:break
            log.write(char);line+=char
            if line.endswith(' ... ') and re.match(r'test\w* \(',line): case_start=time.monotonic()
            if char=='\n':
                if case_start is not None:
                    cases.append({'line':line.strip(),'seconds_observed':round(time.monotonic()-case_start,6)});case_start=None
                line='';log.flush()
        rc=p.wait()
    row={'run':i,'pid':p.pid,'started_utc':started,'ended_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'seconds':round(time.monotonic()-t,3),'rc':rc,'timed_single_line_cases_count':len(cases)}
    (OUT/f'suite-{i}-cases.json').write_text(json.dumps(cases,indent=2))
    rows.append(row); (OUT/'suites.json').write_text(json.dumps(rows,indent=2));print(row,flush=True)
finally:
 remaining=[str(x.relative_to(root)) for x in root.rglob('*')]
 shutil.rmtree(root)
 (OUT/'suite-cleanup.json').write_text(json.dumps({'root':str(root),'remaining_before_cleanup':remaining,'root_removed':not root.exists()},indent=2))
