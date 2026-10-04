import hashlib,json,os,pathlib,re,subprocess
E=pathlib.Path(__file__).resolve().parent
R=E.parents[3]
b=json.loads((E/'baseline.json').read_text())
changed=[]
for name,digest in b['tracked_sha256'].items():
 p=R/name
 if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:changed.append(name)
anc=set();p=os.getpid()
while p>1 and p not in anc:
 anc.add(p)
 try:p=int(pathlib.Path(f'/proc/{p}/stat').read_text().rsplit(')',1)[1].split()[1])
 except (OSError,ValueError):break
remaining=[]
for d in pathlib.Path('/proc').iterdir():
 if not d.name.isdigit() or int(d.name) in anc:continue
 try:
  cmd=(d/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
  env=(d/'environ').read_bytes().replace(b'\0',b' ').decode(errors='replace')
  if any(s in cmd+' '+env for s in ['/tmp/astra5-','/tmp/astra-5-','/tmp/aos72-test-']):
   remaining.append({'pid':int(d.name),'cmd':cmd})
 except (OSError,PermissionError):pass
ps=subprocess.check_output(['ps','-eo','pid,ppid,pgid,stat,args'],text=True)
(E/'ps-final.txt').write_text(ps)
report=E.parent/'2026-10-04-astra-5-infra.md'
broken=[]
if report.exists():
 for target in re.findall(r'\]\(([^)]+)\)',report.read_text()):
  if '://' not in target:
   dest=report.parent/target.split('#')[0]
   if dest != E/'final-audit.json' and not dest.exists():broken.append(target)
x={'head_before':b['head'],'head_after':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'tracked_count':len(b['tracked_sha256']),'changed_tracked_proto7_2':changed,'remaining_test_processes':remaining,'report_broken_relative_links':broken,'git_status':subprocess.check_output(['git','status','--short'],text=True),'ps_file':'ps-final.txt'}
(E/'final-audit.json').write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(x,ensure_ascii=False,indent=2))
assert not changed and not remaining and not broken
