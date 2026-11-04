"""Read-only final audit except verification.json in the authorized evidence dir."""
from common import *
import hashlib, re, collections

def main():
    docs=[OUT.parent/'2026-10-03-astra-6-infra.md',OUT/'README.md']
    save('verification',{})  # allows link verification of this artifact itself
    results={p.name:json.loads(p.read_text()) for p in OUT.glob('*.json') if p.name!='verification.json'}
    errors={n:r['harness_error'] for n,r in results.items() if 'harness_error' in r}
    cleanups={n:r.get('cleanup') for n,r in results.items()}
    bad_cleanup={n:c for n,c in cleanups.items() if not c or c.get('remaining_children_before_delete') or c.get('root_exists') or pathlib.Path(c['root']).exists()}
    remains=sorted(str(p) for p in pathlib.Path('/tmp').glob('astra6-*'))
    pg=subprocess.run(['pgrep','-af','aos7-'],capture_output=True,text=True)
    matched=pg.stdout.splitlines()
    own_matches=[line for line in matched if str(BIN) in line or '/tmp/astra6-' in line]
    external_matches=[line for line in matched if line not in own_matches]
    owned_env=[]
    for pr in pathlib.Path('/proc').iterdir():
        if not pr.name.isdigit():continue
        try:
            env=(pr/'environ').read_bytes().split(b'\0')
            if any(v.startswith(b'AOS7_ROOT=/tmp/astra6-') for v in env):owned_env.append(int(pr.name))
        except OSError:pass
    checks=[]
    for doc in docs:
        for target in re.findall(r'\]\(([^)]+)\)',doc.read_text()):
            if '://' not in target:
                dest=(doc.parent/target.split('#')[0]).resolve()
                if not dest.exists():checks.append({'document':str(doc.relative_to(REPO)),'missing':target})
    sources=[PRODUCT/'spec.md',PRODUCT/'notes/infra-needs.md',REPO/'proto7/spec/core.md']
    sources+=list((PRODUCT/'lib').glob('*.py'))+list((PRODUCT/'bin').iterdir())+list((PRODUCT/'tests').glob('*.py'))
    fingerprints={str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources if p.is_file()}
    tests=results['regression.json']['tests'];counts=collections.Counter(t['test'].split('.')[0] for t in tests)
    report={'python':sys.version,'platform':os.uname().sysname+' '+os.uname().release,'git_metadata_available':(REPO/'.git').exists(),
            'result_files':len(results),'regression_count':len(tests),'regression_modules':dict(counts),'regression_all_pass':all(t['ok'] for t in tests),
            'harness_errors':errors,'bad_cleanup_records':bad_cleanup,'remaining_tmp_roots':remains,'own_descendants':descendants(),
            'own_pgrep_matches':own_matches,'external_pgrep_matches_not_touched':external_matches,'own_root_environment_pids':owned_env,'global_pgrep_clear':pg.returncode==1 and not pg.stdout,
            'pgrep_command':['pgrep','-af','aos7-'],'pgrep_rc':pg.returncode,'pgrep_stdout':pg.stdout,'pgrep_stderr':pg.stderr,
            'broken_report_links':checks,'source_sha256':fingerprints,
            'evidence_total_bytes':sum(p.stat().st_size for p in OUT.iterdir() if p.is_file()),
            'largest_result_bytes':max((OUT/n).stat().st_size for n in results)}
    report['clean']=not(errors or bad_cleanup or remains or descendants() or checks or own_matches or owned_env or pg.returncode not in (0,1))
    save('verification',report)
    print(json.dumps({k:v for k,v in report.items() if k!='source_sha256'},ensure_ascii=False,indent=2))
    if not report['clean']:raise SystemExit(1)
if __name__=='__main__':main()
