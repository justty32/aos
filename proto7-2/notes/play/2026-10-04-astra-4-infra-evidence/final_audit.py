#!/usr/bin/env python3
"""Read-only astra-4 final audit; writes only final-audit.json beside this file."""
import ast
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import time
from urllib.parse import unquote

sys.dont_write_bytecode=True
HERE=pathlib.Path(__file__).resolve().parent
REPO=HERE.parents[3]
TOP=REPO/'proto7-2'
REPORT=HERE.parent/'2026-10-04-astra-4-infra.md'
OUTPUT=HERE/'final-audit.json'
BASELINE=json.loads((HERE/'baseline.json').read_text())
# Materialize this audit's own link target before checking report links.
if not OUTPUT.exists():OUTPUT.write_text('{}\n')

def rel(p): return str(p.relative_to(REPO))
def git(*args):
    return subprocess.run(['git',*args],cwd=REPO,capture_output=True,text=True,check=True).stdout

out={'at_epoch':time.time(),'scope':'Read-only final verification; no product tests rerun; no process signals sent.','baseline_file_count':len(BASELINE['files']),'hash_changed':[],'missing_baseline_files':[]}
for name,digest in BASELINE['files'].items():
    p=REPO/name
    if not p.is_file():out['missing_baseline_files'].append(name)
    elif hashlib.sha256(p.read_bytes()).hexdigest()!=digest:out['hash_changed'].append(name)
new=[]; caches=[]; unexpected=[]
for p in sorted(TOP.rglob('*')):
    if not p.is_file() or rel(p) in BASELINE['files']:continue
    if p.is_relative_to(HERE) or p==REPORT:new.append(rel(p));continue
    st=p.stat()
    if '__pycache__' in p.parts and p.suffix=='.pyc':
        caches.append({'path':rel(p),'mtime':st.st_mtime,'ctime':st.st_ctime,'predates_baseline':max(st.st_mtime,st.st_ctime)<BASELINE['time']})
        if caches[-1]['predates_baseline']:continue
    unexpected.append(rel(p))
out.update(new_files=new,unexpected_new_files=unexpected,existing_unhashed_cache_count=len(caches),existing_unhashed_caches=caches,cache_scope_note='Baseline omitted existing bytecode. Their filesystem mtime and ctime precede baseline; this checks no new/modified cache, not historical byte-for-byte cache identity.')
out['head']=git('rev-parse','HEAD').strip();out['head_matches_baseline']=out['head']==BASELINE['head']
out['git_status']=git('status','--short','--untracked-files=all')
out['baseline_git_status']=BASELINE['status']
baseline_status_lines=set(BASELINE['status'].splitlines())
out['unexpected_git_status']=[line for line in out['git_status'].splitlines() if line not in baseline_status_lines and not (line.startswith('?? '+rel(HERE)+'/') or line=='?? '+rel(REPORT))]

syntax=[]; json_results=[]; docs={}; all_json={}
for p in sorted(HERE.rglob('*')):
    if not p.is_file() or p==OUTPUT:continue
    try:
        if p.suffix=='.py':ast.parse(p.read_text(),filename=str(p));syntax.append({'path':rel(p),'ok':True})
        elif p.suffix=='.json':
            all_json[p]=json.loads(p.read_text());json_results.append({'path':rel(p),'ok':True})
    except Exception as e:
        row={'path':rel(p),'ok':False,'error':repr(e)}
        (syntax if p.suffix=='.py' else json_results).append(row)
out['python_ast']=syntax;out['json_parse']=json_results
out['report_exists']=REPORT.is_file()
out['report_sha256']=hashlib.sha256(REPORT.read_bytes()).hexdigest() if REPORT.is_file() else None
mds=list(HERE.rglob('*summary*.md'))+([REPORT] if REPORT.is_file() else [])
missing_links=[]; checked_links=[]
for p in sorted(mds):
    text=p.read_text();text=re.sub(r'```[\s\S]*?```','',text)
    for raw in re.findall(r'\[[^\]]*\]\(([^\n)]+)\)',text):
        target=raw.strip().strip('<>')
        if target.startswith(('#','http://','https://','mailto:')):continue
        target=unquote(target.split('#',1)[0]);target=target.split(' "',1)[0]
        if not target:continue
        resolved=(p.parent/target).resolve();ok=resolved.exists()
        row={'source':rel(p),'target':raw,'exists':ok};checked_links.append(row)
        if not ok:missing_links.append(row)
out['markdown_links']={'documents':[rel(p) for p in sorted(mds)],'checked_count':len(checked_links),'missing':missing_links,'links':checked_links}

# Extract only this round's private roots from evidence JSON, including embedded
# AOS7_ROOT strings and dictionary keys. Do not scan arbitrary /tmp or scratchpad.
root_pattern=re.compile(r'/tmp/((?:astra4-[A-Za-z0-9_.-]+|aos72-test-[A-Za-z0-9_.-]+))')
roots=set();known_pids=set();cleanup_reports={}
for p,value in all_json.items():
    if p.name=='baseline.json':continue
    encoded=json.dumps(value,ensure_ascii=False)
    roots.update('/tmp/'+s for s in root_pattern.findall(encoded))
    if 'cleanup' in p.name:
        cleanup_reports[rel(p)]=value
        if isinstance(value,dict):known_pids.update(x for x in value.get('known_pids',[]) if isinstance(x,int))
remaining=[r for r in sorted(roots) if os.path.lexists(r)]
out['cleanup_reports']=cleanup_reports
out['temporary_roots']={'count':len(roots),'paths':sorted(roots),'remaining':remaining}

def belongs(path):
    return any(path==root or path.startswith(root+'/') for root in roots)

matches=[]; unreadable=[]; scanned=0
for p in pathlib.Path('/proc').iterdir():
    if not p.name.isdigit() or int(p.name)==os.getpid():continue
    try:
        args=[v.decode(errors='replace') for v in (p/'cmdline').read_bytes().split(b'\0') if v]
        scanned+=1
    except FileNotFoundError:continue
    except PermissionError:
        unreadable.append(int(p.name));continue
    except OSError:continue
    try:environ=(p/'environ').read_bytes().split(b'\0')
    except FileNotFoundError:continue
    except OSError:
        unreadable.append(int(p.name));environ=[]
    identity=[x.decode(errors='replace') for x in environ if x.startswith(b'AOS7_ROOT=') or x.startswith(b'AOS7_SUBROOT=')]
    hit_env=[x for x in identity if belongs(x.partition('=')[2])]
    # Whole argv entries only: a Codex task prompt may quote /tmp roots in prose.
    hit_args=[x for x in args if x.startswith('/tmp/') and belongs(x)]
    if hit_env or hit_args:
        try:stat=(p/'stat').read_text().rsplit(')',1)[1].split();state=stat[0];ppid=int(stat[1])
        except OSError:continue
        matches.append({'pid':int(p.name),'state':state,'ppid':ppid,'argv':args,'identity':identity,'matched_arguments':hit_args})
ps=subprocess.run(['ps','-eo','pid,ppid,pgid,stat,args'],capture_output=True,text=True,check=True)
matched_pids={m['pid'] for m in matches}
ps_matching=[]
for line in ps.stdout.splitlines()[1:]:
    cols=line.strip().split(None,4)
    if cols and cols[0].isdigit() and int(cols[0]) in matched_pids:ps_matching.append(line)
known_ps=subprocess.run(['ps','-p',','.join(map(str,sorted(known_pids))) or str(os.getpid()),'-o','pid,ppid,pgid,stat,args'],capture_output=True,text=True)
out['process_audit']={'method':'/proc AOS7_ROOT/AOS7_SUBROOT boundary match or entire /tmp path argv entries; ps cross-check; no substring prompt matches and no killing.','proc_scanned':scanned,'unreadable_pids':unreadable,'matching_processes':matches,'ps_matching':ps_matching,'known_cleanup_pids':sorted(known_pids),'known_cleanup_pids_ps_rc':known_ps.returncode,'known_cleanup_pids_ps':known_ps.stdout,'known_cleanup_pids_ps_stderr':known_ps.stderr}
out['passed']=all([not out['hash_changed'],not out['missing_baseline_files'],not unexpected,not out['unexpected_git_status'],out['head_matches_baseline'],out['report_exists'],all(x['ok'] for x in syntax+json_results),not missing_links,not remaining,not matches])
OUTPUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
# Verify the artifact we just wrote parses as JSON as well.
json.loads(OUTPUT.read_text())
print(json.dumps({'passed':out['passed'],'baseline_files':len(BASELINE['files']),'new_files':len(new),'changed':out['hash_changed'],'missing':out['missing_baseline_files'],'unexpected_new':unexpected,'ast_files':len(syntax),'json_files':len(json_results),'missing_links':missing_links,'root_count':len(roots),'remaining_roots':remaining,'matching_processes':matches},ensure_ascii=False))
sys.exit(0 if out['passed'] else 1)
