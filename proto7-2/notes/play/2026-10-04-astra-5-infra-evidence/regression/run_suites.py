#!/usr/bin/env python3
import subprocess,time,json,os,pathlib,datetime
OUT=pathlib.Path(__file__).resolve().parent
rows=[]
for i in range(1,4):
    started=datetime.datetime.now(datetime.timezone.utc).isoformat(); t=time.monotonic()
    with (OUT/f'suite-{i}.log').open('w') as log:
        p=subprocess.Popen(['python3','proto7-2/tests/run_all.py','-v'],stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
        (OUT/'suite-active.json').write_text(json.dumps({'run':i,'pid':p.pid,'started_utc':started}))
        print(f'suite {i} pid={p.pid} started={started}',flush=True)
        rc=p.wait()
    row={'run':i,'pid':p.pid,'started_utc':started,'seconds':round(time.monotonic()-t,3),'rc':rc}
    rows.append(row); (OUT/'suites.json').write_text(json.dumps(rows,indent=2));print(row,flush=True)
