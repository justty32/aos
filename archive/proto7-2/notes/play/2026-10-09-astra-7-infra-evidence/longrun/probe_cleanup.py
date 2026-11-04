#!/usr/bin/env python3
"""Reproduce: python3 proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/longrun/probe_cleanup.py
Read-only final process/working-tree audit; checks only roots recorded by this lane.
"""
import json, os, pathlib, subprocess, sys
E=pathlib.Path(__file__).resolve().parent;REPO=E.parents[4]
if '--scoped' not in sys.argv:
    raise SystemExit(subprocess.call(['systemd-run','--user','--scope','-q','-p','TasksMax=800','-p','RuntimeMaxSec=1800',sys.executable,str(__file__),'--scoped'],cwd=REPO))
roots=[];known=set()
for name in ['suite-cleanup.json','step-cleanup.json','adapt-cleanup.json','core-cleanup.json']:
    o=json.loads((E/name).read_text());roots.append(o['root'])
    for row in o.get('owned_before',[])+o.get('signalled',[]):known.add(row['pid'])
remaining=[];unreadable=[];scanned=0
for p in pathlib.Path('/proc').iterdir():
    if not p.name.isdigit() or int(p.name)==os.getpid():continue
    try:
        cmd=(p/'cmdline').read_bytes().split(b'\0');env=(p/'environ').read_bytes().split(b'\0');stat=(p/'stat').read_bytes().rsplit(b')',1)[1].split();scanned+=1
        for root in roots:
            want=root.encode()
            if any(x==want or x.startswith(want+b'/') for x in cmd) or any(x.partition(b'=')[2]==want or x.partition(b'=')[2].startswith(want+b'/') for x in env):
                remaining.append({'pid':int(p.name),'state':stat[0].decode(),'starttime':stat[19].decode(),'root':root,'command':[x.decode(errors='replace') for x in cmd if x]})
    except PermissionError:unreadable.append(int(p.name))
    except (FileNotFoundError,ProcessLookupError):pass
known_remaining=[pid for pid in sorted(known) if pathlib.Path('/proc',str(pid)).exists()]
ps=subprocess.check_output(['ps','-eo','pid,ppid,pgid,lstart,args'],text=True)
(E/'ps-final.txt').write_text(ps)
diff=subprocess.run(['git','diff','--exit-code','--quiet','HEAD','--'],cwd=REPO)
changed=subprocess.check_output(['git','diff','--name-only','HEAD','--'],cwd=REPO,text=True).splitlines()
sizes={p.name:p.stat().st_size for p in E.iterdir() if p.is_file()}
out={'scenario':'final cleanup and write-boundary audit','injection':{'kind':'none'},'assertion':'all recorded owned roots removed; no own process remains; tracked files unchanged; evidence files <300KiB','roots':roots,'roots_remaining':[r for r in roots if pathlib.Path(r).exists()],'owned_processes_remaining':remaining,'known_owned_pids':sorted(known),'known_owned_pids_remaining':known_remaining,'scanned_processes':scanned,'unreadable_other_processes':unreadable,'tracked_diff_rc':diff.returncode,'tracked_changed':changed,'evidence_sizes':sizes,'oversize':[n for n,s in sizes.items() if s>300*1024]}
out['pass']=not out['roots_remaining'] and not remaining and not known_remaining and diff.returncode==0 and not out['oversize']
(E/'cleanup.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k!='evidence_sizes'},ensure_ascii=False))
