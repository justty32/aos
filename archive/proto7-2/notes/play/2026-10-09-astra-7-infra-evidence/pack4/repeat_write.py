"""Confirm pre-write EIO consequence three times, using the independent real tick/tock probe.
Rerun: python3 proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/pack4/repeat_write.py
"""
import ctypes
import os
from pathlib import Path
import shutil
import subprocess as sp
import sys
import tempfile
import probe as h
def main():
    if os.environ.get('PACK4_SCOPED')!='1':
        return sp.call(['systemd-run','--user','--scope','-q','-p','TasksMax=800','-p','RuntimeMaxSec=1800',
          '/usr/bin/env','PACK4_SCOPED=1','PYTHONDONTWRITEBYTECODE=1',sys.executable,str(Path(__file__).resolve())],cwd=h.REPO)
    ctypes.CDLL(None).prctl(36,1,0,0,0)
    h.ROOT=Path(tempfile.mkdtemp(prefix='astra7-pack4-repeat-'));rows=[]
    try:
        for i in range(3):
            os.environ['PACK4_REPEAT']='-repeat'+str(i+1)
            r=h.resends_write_fail('write')
            rows.append(dict(scenario='pre-write EIO repetition '+str(i+1),pass_=r['acceptance_pass'],data=r))
            h.write(h.HERE/'repeat-write-results.json',rows)
            h.clean_procs(h.ROOT)
        print({'reproduced':len(rows),'ran':[r['data']['actual_ran'] for r in rows]})
    finally:
        c=h.clean_procs(h.ROOT);assert not c['remaining'],c
        c['root']=str(h.ROOT);shutil.rmtree(h.ROOT);c['root_removed']=not h.ROOT.exists()
        h.write(h.HERE/'repeat-cleanup.json',c)
    return 0
if __name__=='__main__':sys.exit(main())
