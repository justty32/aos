"""Package only pack4-owned snapshots, record process/temp cleanup and tracked-file status.
Rerun: python3 proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/pack4/finalize.py
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess as sp
import sys
import tarfile
HERE=Path(__file__).resolve().parent
TOP=next(p for p in HERE.parents if p.name=='proto7-2')
def write(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=1)+'\n')
def main():
    if os.environ.get('PACK4_SCOPED')!='1':
        return sp.call(['systemd-run','--user','--scope','-q','-p','TasksMax=800','-p','RuntimeMaxSec=1800',
          '/usr/bin/env','PACK4_SCOPED=1','PYTHONDONTWRITEBYTECODE=1',sys.executable,str(Path(__file__).resolve())],cwd=TOP.parent)
    archives=[]
    for folder in [HERE/'snapshots',HERE/'cases',HERE/'harness-initial',HERE/'crash/verified/snapshots',HERE/'crash/extra/snapshots']:
        archive=folder.with_name(folder.name+'.tar.gz')
        if folder.exists():
            with tarfile.open(archive,'w:gz') as t:t.add(folder,arcname=folder.name)
            with tarfile.open(archive) as t:entries=len(t.getmembers())
            assert archive.stat().st_size<=300*1024,archive
            archives.append(dict(file=str(archive.relative_to(HERE)),bytes=archive.stat().st_size,
                sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),entries=entries))
            shutil.rmtree(folder)
        elif archive.exists():
            archives.append(dict(file=str(archive.relative_to(HERE)),bytes=archive.stat().st_size,
                sha256=hashlib.sha256(archive.read_bytes()).hexdigest()))
    write(HERE/'archives.json',archives)
    roots=set(); tracked=set();reaped=[]
    def collect(v):
        if isinstance(v,dict):
            if isinstance(v.get('root'),str) and v['root'].startswith('/tmp/astra7-pack4-'):roots.add(v['root'])
            for p in v.get('tracked_pids',[]):tracked.add(p)
            for p in v.get('direct_children',[]):tracked.add(p['pid'])
            for p in v.get('killed',[]):tracked.add(p['pid'])
            for x in v.values():collect(x)
        elif isinstance(v,list):
            for x in v:collect(x)
    for p in HERE.rglob('*cleanup*.json'):
        if p.name=='cleanup.json' and p.parent==HERE:continue
        collect(json.loads(p.read_text()))
    # Inspect all recorded temp roots and all surviving processes without touching other teams.
    live=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:
            env=(p/'environ').read_bytes().split(b'\0')
            owned=[e.decode(errors='replace') for e in env if e.startswith(b'AOS7_ROOT=/tmp/astra7-pack4-')]
            if owned:
                stat=(p/'stat').read_text().rsplit(')',1)[1].split()
                live.append(dict(pid=int(p.name),state=stat[0],identity=owned))
        except OSError:pass
    ps=sp.run(['ps','-eo','pid,ppid,pgid,lstart,args'],capture_output=True,text=True,check=True).stdout
    (HERE/'ps-final.txt').write_text(ps)
    diff=sp.run(['git','diff','--name-only','HEAD'],cwd=TOP.parent,capture_output=True,text=True,check=True).stdout.splitlines()
    leftovers=[str(p) for p in Path('/tmp').glob('astra7-pack4-*') if p.is_dir()]
    outside_files=[str(p) for p in Path('/tmp').glob('astra7-pack4-*') if not p.is_dir()]
    pid_remnants=[p for p in sorted(tracked) if Path('/proc/%d'%p).exists()]
    oversized=[dict(file=str(p.relative_to(HERE)),bytes=p.stat().st_size) for p in HERE.rglob('*') if p.is_file() and p.stat().st_size>300*1024]
    result=dict(roots=[dict(path=r,exists=Path(r).exists()) for r in sorted(roots)],
        own_tmp_leftovers=leftovers,own_aos_processes=live,tracked_pid_count=len(tracked),tracked_pids_still_exist=pid_remnants,
        launcher_files_not_created_or_modified_by_probe=outside_files,
        tracked_changes=diff,oversized_files=oversized,ps_before='ps-before.txt',ps_final='ps-final.txt',
        pass_=not (leftovers or live or pid_remnants or diff or oversized))
    write(HERE/'cleanup.json',result);print(json.dumps(result,ensure_ascii=False))
    return int(not result['pass_'])
if __name__=='__main__':sys.exit(main())
