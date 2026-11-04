"""Read-only verification of protected files and owned runtime residue; writes only evidence JSON."""
from common import *
import hashlib,platform
REPORT=OUT.with_name('2026-10-03-astra-8-infra.md')
def digest(items):
    return hashlib.sha256(json.dumps(items,sort_keys=True,separators=(',',':')).encode()).hexdigest()
before=json.loads((OUT/'baseline.json').read_text())
after={str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for top in ('proto7','proto7-1') for p in (REPO/top).rglob('*') if p.is_file() and OUT not in p.parents and p!=REPORT}
if 'protected_sha256' in before:
    changed=[] if digest(after)==before['protected_sha256'] else ['aggregate mismatch']
    baseline=before
else:
    changed=[k for k in sorted(set(before)|set(after)) if before.get(k)!=after.get(k)]
    selected={k:v for k,v in before.items() if '/lib/' in k or '/tests/test_astra' in k or k in ('proto7/spec/core.md','proto7-1/spec.md','proto7-1/README.md','proto7-1/probes/llm_card.md','proto7-1/notes/infra-needs.md')}
    baseline={'protected_count':len(before),'protected_sha256':digest(before),'selected_sources':selected}
cleanups=[];harness_errors=[]
for p in sorted(OUT.glob('*.json')):
    if p.name in ('baseline.json','verification.json'):continue
    d=json.loads(p.read_text())
    if 'cleanup' in d:cleanups.append({'file':p.name,**d['cleanup']})
    if 'harness_error' in d:harness_errors.append({'file':p.name,'error':d['harness_error']})
roots=sorted(str(p) for p in pathlib.Path('/tmp').glob('astra8-*'))
procs=[]
for p in pathlib.Path('/proc').iterdir():
    if not p.name.isdigit() or int(p.name)==os.getpid():continue
    try:
        env=(p/'environ').read_bytes().split(b'\0');cmd=(p/'cmdline').read_bytes().split(b'\0')
        hit=any(x.startswith((b'AOS7_ROOT=/tmp/astra8-',b'AOS7_NODE=/tmp/astra8-',b'HOOK_FAIL=/tmp/astra8-')) for x in env) or any(x.startswith(b'/tmp/astra8-') for x in cmd)
        if hit:procs.append({'pid':int(p.name),'cmd':[x.decode(errors='replace') for x in cmd if x][:4]})
    except OSError:pass
r={'protected_files_unchanged':not changed,'changed_protected_files':changed,'protected_count':len(after),'current_sha256':digest(after),'python':sys.version,'platform':platform.platform(),'git_present':(REPO/'.git').exists(),'wf_present':(REPO/'wf').exists(),'cmake_present':(REPO/'CMakeLists.txt').exists(),'cases_with_cleanup':len(cleanups),'cleanup_failures':[x for x in cleanups if x.get('remaining_children_before_delete') or x.get('root_exists') is not False or pathlib.Path(x['root']).exists()],'harness_errors':harness_errors,'remaining_tmp_roots':roots,'remaining_product_processes':procs,'evidence_files':len(list(OUT.iterdir())),'evidence_bytes':sum(p.stat().st_size for p in OUT.iterdir() if p.is_file() and p.name!='baseline.json')}
save('verification',r);save('baseline',baseline);print(json.dumps(r,ensure_ascii=False,indent=2))
