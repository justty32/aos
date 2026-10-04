#!/usr/bin/env python3
"""Archive only this evidence's snapshots; validate own temp roots and PIDs are gone."""
import hashlib,json,subprocess,tarfile,shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent
archives=[]
for rel in ('crash/verified','crash/extra','crash/loop6','crash/edges','integration'):
    base=HERE/rel;src=base/'snapshots';dst=base/'snapshots.tar.gz'
    if src.exists():
        with tarfile.open(dst,'w:gz') as tf:tf.add(src,arcname='snapshots')
        with tarfile.open(dst,'r:gz') as tf:
            count=sum(m.isfile() for m in tf.getmembers())
            assert count==sum(p.is_file() for p in src.rglob('*'))
        shutil.rmtree(src)
    else:
        with tarfile.open(dst,'r:gz') as tf:count=sum(m.isfile() for m in tf.getmembers())
    archives.append(dict(path=str(dst.relative_to(HERE)),files=count,bytes=dst.stat().st_size,sha256=hashlib.sha256(dst.read_bytes()).hexdigest()))
roots=[];pids=[]
for name in ('verified','extra','loop6','edges'):
    c=json.loads((HERE/'crash'/name/'cleanup.json').read_text());roots.append(c['root']);pids+=c['tracked_pids'];assert c['all_waited'] and not c['remaining_mentions']
c=json.loads((HERE/'integration/own-cleanup.json').read_text());roots.append(c['root']);pids+=c['pids'];assert c['all_reaped']
for rel in ('integration/results.json','resends/results.json'):
    for c in json.loads((HERE/rel).read_text())['cleanups']:
        roots.append(c['root']);assert c['root_removed'] and not c['live_pids']
ps=subprocess.run(['ps','-eo','pid,ppid,pgid,stat,args'],capture_output=True,text=True).stdout
(HERE/'final-ps.txt').write_text(ps)
live=[p for p in pids if Path('/proc',str(p)).exists()];remaining=[r for r in roots if Path(r).exists()];mentions=[line for line in ps.splitlines() if any(r in line for r in roots)]
result=dict(archives=archives,tracked_pids=len(pids),live_tracked_pids=live,roots=roots,remaining_roots=remaining,remaining_root_mentions=mentions,clean=not(live or remaining or mentions))
(HERE/'cleanup-final.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result))
assert result['clean']
