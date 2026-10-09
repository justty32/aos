#!/usr/bin/env python3
"""Reproduce: python3 proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/longrun/probe_suite.py
Runs under a bounded systemd scope, standard library only; no LLM calls.
"""
import json, os, pathlib, re, shutil, subprocess, sys, tempfile, time
E=pathlib.Path(__file__).resolve().parent
ROOT=E.parents[4]
if "--scoped" not in sys.argv:
    raise SystemExit(subprocess.call(["systemd-run","--user","--scope","-q","-p","TasksMax=800","-p","RuntimeMaxSec=1800",sys.executable,str(__file__),"--scoped"],cwd=ROOT))
sys.dont_write_bytecode=True
scratch=pathlib.Path(tempfile.mkdtemp(prefix="astra7-longrun-suite-"))
env={**os.environ,"TMPDIR":str(scratch),"PYTHONDONTWRITEBYTECODE":"1"}
(E/"suite-active.json").write_text(json.dumps({"scratch":str(scratch),"pid":os.getpid()}))
def run(label,extra):
    cmd=[sys.executable,"proto7-2/tests/run_all.py","-v",*extra]
    start=time.monotonic()
    with (E/(label+".log")).open("w") as f:
        p=subprocess.run(cmd,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=1500)
    raw=(E/(label+".log")).read_text()
    ran=re.findall(r"Ran (\d+) tests? in ([\d.]+)s",raw)
    bad=re.findall(r"^(FAIL|ERROR): (.+)$",raw,re.M)
    skips=[s for s in raw.splitlines() if " ... skipped " in s]
    return {"scenario":label,"injection":{"kind":"none; unmodified author suite"},"command":cmd,"rc":p.returncode,"seconds":round(time.monotonic()-start,3),"ran":int(ran[-1][0]) if ran else None,"unittest_seconds":float(ran[-1][1]) if ran else None,"failures_errors":bad,"skips":skips,"assertion":"suite returns zero","pass":p.returncode==0,"raw":label+".log"}
rows=[]
try:
    rows.append(run("suite",[]))
    (E/"suite.json").write_text(json.dumps(rows,indent=2))
    print(json.dumps(rows[-1]),flush=True)
    for kind,name in rows[0]["failures_errors"]:
        method=name.split(" ")[0]
        for i in range(3):
            rows.append(run("retry-"+method+"-"+str(i+1),["-k",method]))
            (E/"suite.json").write_text(json.dumps(rows,indent=2))
            print(json.dumps(rows[-1]),flush=True)
finally:
    remaining=sorted(str(x.relative_to(scratch)) for x in scratch.rglob("*"))
    shutil.rmtree(scratch)
    (E/"suite-cleanup.json").write_text(json.dumps({"root":str(scratch),"remaining_before":remaining,"removed":not scratch.exists()},indent=2))
