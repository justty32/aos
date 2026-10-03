from common import *
import hashlib,platform
REPORT=OUT.parent/'2026-10-03-astra-7-infra.md'
def digest(files):return hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def source_files():
    return {str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for base in (REPO/'proto7',PRODUCT) for p in base.rglob('*') if p.is_file() and OUT not in p.parents and p!=REPORT}
def main():
    baseline=read(OUT/'baseline.json');current=source_files();changed=[];added=[];missing=[]
    if baseline.get('schema')=='astra7-baseline/1':
        before_hash=baseline['tree_sha256'];count_before=baseline['count'];selected=baseline['sources'];matches=digest(current)==before_hash and len(current)==count_before
    else:
        before_hash=digest(baseline);count_before=len(baseline)
        changed=[k for k in baseline.keys()&current.keys() if baseline[k]!=current[k]];added=sorted(current.keys()-baseline.keys());missing=sorted(baseline.keys()-current.keys())
        selected={k:v for k,v in baseline.items() if k.startswith(('proto7-1/lib/','proto7-1/bin/','proto7-1/tests/test_astra','proto7-1/tests/test_owner_reload')) or k in ('proto7/spec/core.md','proto7-1/spec.md','proto7-1/notes/infra-needs.md')}
        matches=not(changed or added or missing)
        if matches:save('baseline',{'schema':'astra7-baseline/1','tree_sha256':before_hash,'count':count_before,'sources':selected})
    cases=[];roots=set();harness_errors=[]
    for path in OUT.glob('*.json'):
        if path.name=='verification.json':continue
        r=read(path)
        if not isinstance(r,dict):continue
        c=r.get('cleanup')
        if c:
            cases.append({'file':path.name,'clean':c.get('remaining_children_before_delete')==[] and c.get('root_exists') is False});roots.add(c['root'])
        if 'harness_error' in r:harness_errors.append({'file':path.name,'error':r['harness_error']})
        if isinstance(r.get('root'),str) and r['root'].startswith('/tmp/astra7-'):roots.add(r['root'])
    processes=[]
    for p in pathlib.Path('/proc').iterdir():
        if not p.name.isdigit() or int(p.name)==os.getpid():continue
        try:
            args=(p/'cmdline').read_bytes().split(b'\0');env=(p/'environ').read_bytes().split(b'\0')
            owned=any(a.decode(errors='replace').startswith(str(BIN)+'/') for a in args)
            eroot=next((a[10:].decode(errors='replace') for a in env if a.startswith(b'AOS7_ROOT=')),None)
            if owned or (eroot and any(eroot==r or eroot.startswith(r+'/') for r in roots)):
                processes.append({'pid':int(p.name),'args':[a.decode(errors='replace') for a in args if a],'root':eroot})
        except OSError:pass
    existing=[r for r in sorted(roots) if pathlib.Path(r).exists()]
    prefix_dirs=[str(p) for p in pathlib.Path('/tmp').glob('astra7-*') if p.is_dir()]
    inv=read(OUT/'longrun-invariants.json',{});bad_invariants=[x for x in inv.get('nodes',[]) if x['duplicate_rounds'] or x['missing_rounds'] or x['duplicate_ended'] or x['summary_errors']]
    result={'python':platform.python_version(),'kernel':platform.release(),'protected_files_before':count_before,'protected_files_after':len(current),'tree_sha256_before':before_hash,'tree_sha256_after':digest(current),'source_unchanged':matches,'changed':changed,'added_outside_deliverables':added,'missing':missing,'case_cleanup_count':len(cases),'bad_case_cleanup':[r for r in cases if not r['clean']],'harness_errors':harness_errors,'owned_temp_roots_count':len(roots),'owned_temp_roots_remaining':existing,'astra7_prefix_dirs_remaining':prefix_dirs,'owned_product_processes_remaining':processes,'longrun_invariant_failures':bad_invariants,'clean':matches and not(existing or prefix_dirs or processes or harness_errors or [r for r in cases if not r['clean']])}
    save('verification',result);print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
