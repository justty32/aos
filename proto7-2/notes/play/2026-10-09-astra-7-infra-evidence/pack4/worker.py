"""Offline child workload; invoked by probe.py via real step-result and aos7-run.
Rerun: python3 proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/pack4/probe.py
"""
import json
import os
from pathlib import Path
import sys
import time
job,req,att,mode=sys.argv[1:]
with open(Path(job)/'ran.jsonl','a') as f:
    f.write(json.dumps(dict(request=req,attempt=att,pid=os.getpid(),run=os.environ.get('AOS7_RUN')))+'\n')
if mode=='gate':
    while not (Path(job)/'release').exists(): time.sleep(.1)
    mode='0'
sys.exit(int(mode))
