#!/usr/bin/env python3
import sys, pathlib, subprocess,json,os,hashlib
OUT=pathlib.Path(__file__).resolve().parent
TOP=pathlib.Path('proto7-2').resolve()
sys.path.insert(0,str(TOP/'tests/core'))
import test_budget
rows={p.name:test_budget.count(p) for p in sorted((TOP/'lib').glob('aos7_*.py'))}
(OUT/'core-lines.json').write_text(json.dumps({'files':rows,'total':sum(x[0] for x in rows.values()),'code':sum(x[1] for x in rows.values()),'total_max':test_budget.TOTAL_MAX,'code_max':test_budget.CODE_MAX},indent=2))
p=subprocess.run([sys.executable,'proto7-2/tests/core/test_budget.py','-v'],capture_output=True,text=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
(OUT/'core-budget.log').write_text(p.stdout+p.stderr)
def git(*args):return subprocess.run(['git',*args],capture_output=True,text=True,check=True).stdout
base=git('rev-parse','daf8d5cf').strip()
comparison={'base':base,'base_description':git('show','-s','--format=%s',base).strip(),'head':git('rev-parse','HEAD').strip(),'history_since_base':git('log','--format=%H %s',base+'..HEAD','--','proto7-2/lib/'),'committed_diff':git('diff',base,'HEAD','--','proto7-2/lib/'),'worktree_diff':git('diff','HEAD','--','proto7-2/lib/'),'core_budget_rc':p.returncode,'files':{}}
for path in sorted((TOP/'lib').glob('*')):
 if path.is_file():
  rel=path.relative_to(TOP.parent).as_posix()
  old=subprocess.run(['git','show',base+':'+rel],capture_output=True,check=True).stdout
  comparison['files'][rel]={'baseline_sha256':hashlib.sha256(old).hexdigest(),'current_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'same':old==path.read_bytes()}
(OUT/'core-history.json').write_text(json.dumps(comparison,indent=2))
assert p.returncode==0 and not comparison['committed_diff'] and not comparison['worktree_diff'] and all(x['same'] for x in comparison['files'].values())
print({'total':sum(x[0] for x in rows.values()),'code':sum(x[1] for x in rows.values()),'lib_unchanged_files':len(comparison['files']),'base':base,'head':comparison['head']})
