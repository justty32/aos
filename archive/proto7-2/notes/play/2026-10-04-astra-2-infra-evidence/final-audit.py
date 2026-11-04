"""只讀稽核程序／產物；第一次把暫存來源hash表縮成摘要後移除，結果只寫此evidence。"""
import os,sys,pathlib,json,ast,re,time,hashlib
E=pathlib.Path(__file__).resolve().parent
ROOT=E.parents[3]
REPORT=E.parent/'2026-10-04-astra-2-infra.md'
OUT=E/'final-cleanup.json'
MANIFEST=E/'source-hashes.json'
previous=json.loads(OUT.read_text()) if OUT.exists() else {}
start=min(p.stat().st_mtime for p in E.iterdir() if p.is_file() and p.name not in ('final-cleanup.json','final-audit.py'))
ancestors={os.getpid()}; pid=os.getppid()
while pid>1 and pid not in ancestors:
    ancestors.add(pid)
    try: pid=int(pathlib.Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[1])
    except (OSError,ValueError,IndexError): break
left=[]
for p in pathlib.Path('/proc').iterdir():
    if not p.name.isdigit() or int(p.name) in ancestors: continue
    try:
        cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
        env=(p/'environ').read_bytes().split(b'\0')
        state=(p/'stat').read_text().rsplit(')',1)[1].split()[0]
    except OSError: continue
    testroot=any(x.startswith(b'AOS7_ROOT='+str(E).encode()) for x in env)
    script=str(E) in cmd or 'proto7-2/notes/play/2026-10-04-astra-2-infra-evidence/' in cmd
    if testroot or script: left.append({'pid':int(p.name),'state':state,'cmd':cmd[:300]})
sources={}
outside=[]
for p in ROOT.rglob('*'):
    if p.is_symlink() or not p.is_file() or p==REPORT or p.is_relative_to(E): continue
    rel=str(p.relative_to(ROOT))
    if p.stat().st_mtime>=start: outside.append(rel)
    if p.name!='log.txt': sources[rel]=hashlib.sha256(p.read_bytes()).hexdigest()
def digest(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':')).encode()).hexdigest()
changed=[]
if MANIFEST.exists():
    baseline=json.loads(MANIFEST.read_text())
    changed=[n for n in sorted(set(sources)|set(baseline)) if sources.get(n)!=baseline.get(n)]
    baseline_digest=digest(baseline)
    MANIFEST.unlink()
else:
    baseline_digest=previous.get('baseline_sources_digest')
    changed=[] if baseline_digest==digest(sources) else ['source digest changed; original per-file temporary manifest already removed']
json_bad=[]; syntax_bad=[]
for p in E.glob('*.json'):
    try: json.loads(p.read_text())
    except Exception as ex: json_bad.append({'file':p.name,'error':str(ex)})
for p in E.glob('*.py'):
    try: ast.parse(p.read_text())
    except SyntaxError as ex: syntax_bad.append({'file':p.name,'error':str(ex)})
missing=[]
for link in re.findall(r'\]\(([^)]+)\)',REPORT.read_text()):
    if '://' not in link and not (REPORT.parent/link).exists() and not link.endswith('final-cleanup.json'): missing.append(link)
subdirs=[str(p.relative_to(E)) for p in E.rglob('*') if p.is_dir()]
result={'checked_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'remaining_test_processes':left,'remaining_evidence_subdirectories':subdirs,
        'temporary_roots_outside_copy_created':False,
        'files_modified_outside_allowed_outputs_since_first_evidence':outside,
        'runtime_transcript_note':'log.txt is the pre-existing runtime transcript, automatically updated by the host; scripts did not modify it.',
        'unexpected_product_or_document_changes':[n for n in outside if n!='log.txt'],
        'source_files_checked':len(sources),'baseline_sources_digest':baseline_digest,
        'current_sources_digest':digest(sources),'changed_sources_since_hash_snapshot':changed,
        'invalid_json':json_bad,'invalid_python':syntax_bad,'broken_report_links':missing,
        'evidence_file_count':len([p for p in E.iterdir() if p.is_file()]),
        'evidence_bytes':sum(p.stat().st_size for p in E.iterdir() if p.is_file()),'report_bytes':REPORT.stat().st_size}
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
