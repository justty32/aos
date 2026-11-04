"""Read-only final verification plus evidence manifests; never kills or removes files.
Re-run: systemd-run --user --scope -q -p TasksMax=800 -p RuntimeMaxSec=1800 python3 proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/group5/finalize.py
"""
from common import *
import hashlib

def main():
    sources={}
    for name in ('core','modules','t8','docs-edges','error-loop'):
        sources[name]=read(OUT/(name+'.json'))
        assert sources[name] is not None,name
    tracked=subprocess.check_output(['git','diff','--name-only'],cwd=REPO,text=True).splitlines()
    indexed=subprocess.check_output(['git','diff','--cached','--name-only'],cwd=REPO,text=True).splitlines()
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    residual=[]
    for d in Path('/proc').iterdir():
        if not d.name.isdigit() or int(d.name)==os.getpid():continue
        try:
            env=(d/'environ').read_bytes().split(b'\0')
            tags=[x.decode(errors='replace') for x in env if x.startswith((b'AOS7_ROOT=/tmp/astra7-group5-',b'TMPDIR=/tmp/astra7-group5-'))]
            stat=(d/'stat').read_bytes().rsplit(b')',1)[1].split()
            if tags and stat[0]!=b'Z':residual.append({'pid':int(d.name),'starttime':stat[19].decode(),'environment':tags})
        except OSError:pass
    roots=[str(p) for p in Path('/tmp').glob('astra7-group5-*') if p.is_dir()]
    cleanups={p.name:read(p) for p in OUT.glob('*-cleanup.json')}
    sizes={p.name:p.stat().st_size for p in OUT.iterdir() if p.is_file()}
    (OUT/'ps-final.txt').write_text(subprocess.check_output(['ps','-eo','pid,ppid,pgid,lstart,args'],text=True))
    write(OUT/'cleanup.json',{'head':head,'tracked_worktree_changes':tracked,'index_changes':indexed,'owned_root_directories_remaining':roots,'owned_active_processes_remaining':residual,'per_probe':cleanups,'all_pass':not(tracked or indexed or roots or residual),'untouched_launcher_log':'/tmp/astra7-group5-codex.log is an external launcher log, not a root created by these probes','maximum_existing_evidence_file_bytes':max(sizes.values())})
    entries=[]
    for p in sorted(OUT.iterdir()):
        if p.is_file() and p.name!='manifest.json':entries.append({'file':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    write(OUT/'manifest.json',{'head':head,'files':entries})
    assert not(tracked or indexed or roots or residual),(tracked,indexed,roots,residual)
    assert all(p.stat().st_size<300000 for p in OUT.iterdir() if p.is_file())
    print(json.dumps({'head':head,'cleanup':'pass','files':len(entries)},ensure_ascii=False))

if __name__=='__main__':main()
