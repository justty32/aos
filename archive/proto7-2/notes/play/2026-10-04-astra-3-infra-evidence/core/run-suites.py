import os, sys, pathlib, subprocess, time, json, tempfile, re, shutil
OUT=pathlib.Path(__file__).resolve().parent
REPO=OUT.parents[4]
rows=[]
for i in range(1,4):
    tmp=tempfile.mkdtemp(prefix='astra3-core-suite-')
    env=dict(os.environ, TMPDIR=tmp, PYTHONDONTWRITEBYTECODE='1')
    start=time.monotonic()
    p=subprocess.run([sys.executable,'proto7-2/tests/run_all.py'],cwd=REPO,env=env,capture_output=True,text=True)
    elapsed=time.monotonic()-start
    output=p.stdout+p.stderr
    (OUT/f'suite-{i}.log').write_text(output)
    match=re.search(r'Ran (\d+) tests in ([\d.]+)s',output)
    row=dict(run=i,elapsed_s=round(elapsed,3),returncode=p.returncode,test_count=int(match[1]) if match else None,unittest_s=float(match[2]) if match else None,failures=re.findall(r'^FAIL: (.+)$',output,re.M),errors=re.findall(r'^ERROR: (.+)$',output,re.M),tmp=tmp,tmp_remaining_before_cleanup=os.listdir(tmp))
    # Each existing test is responsible for its children; preserve any unexpected residual for inspection.
    if not os.listdir(tmp): os.rmdir(tmp)
    row['tmp_removed']=not os.path.exists(tmp)
    rows.append(row)
    (OUT/'suites.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
    print(json.dumps(row,ensure_ascii=False),flush=True)
