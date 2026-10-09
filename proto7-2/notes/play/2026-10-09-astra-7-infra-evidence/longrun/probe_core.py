#!/usr/bin/env python3
"""Reproduce: python3 proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/longrun/probe_core.py
D7 print-only budget test plus independent AST/token counts and tracked lib history.
"""
import ast, io, json, os, pathlib, shutil, subprocess, sys, tempfile, tokenize
E=pathlib.Path(__file__).resolve().parent;ROOT=E.parents[4];P=ROOT/'proto7-2'
if '--scoped' not in sys.argv:
    raise SystemExit(subprocess.call(['systemd-run','--user','--scope','-q','-p','TasksMax=800','-p','RuntimeMaxSec=1800',sys.executable,str(__file__),'--scoped'],cwd=ROOT))
sys.dont_write_bytecode=True
scratch=pathlib.Path(tempfile.mkdtemp(prefix='astra7-longrun-core-'))
def git(*a):return subprocess.check_output(['git',*a],cwd=ROOT,text=True)
def count(src):
    docs=set()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n,(ast.Module,ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)) and n.body:
            b=n.body[0]
            if isinstance(b,ast.Expr) and isinstance(b.value,ast.Constant) and isinstance(b.value.value,str):docs.update(range(b.lineno,b.end_lineno+1))
    lines=set()
    skip={tokenize.COMMENT,tokenize.NL,tokenize.NEWLINE,tokenize.INDENT,tokenize.DEDENT,tokenize.ENDMARKER}
    for t in tokenize.generate_tokens(io.StringIO(src).readline):
        if t.type not in skip:lines.update(set(range(t.start[0],t.end[0]+1))-docs)
    return {'total':len(src.splitlines()),'code':len(lines)}
try:
    cmd=[sys.executable,'proto7-2/tests/run_all.py','-v','-k','test_core_line_budget','tests/core']
    r=subprocess.run(cmd,cwd=ROOT,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','TMPDIR':str(scratch)},capture_output=True,text=True,timeout=60)
    (E/'core-budget.log').write_text(r.stdout+r.stderr)
    rows=[]
    for p in sorted((P/'lib').glob('*.py')):
        rel=str(p.relative_to(ROOT)); old=git('show','510dd134:'+rel)
        before=count(old);after=count(p.read_text())
        rows.append({'file':rel,'in_core_budget':p.name.startswith('aos7_'),'baseline_510dd134':before,'head':after,'delta':{k:after[k]-before[k] for k in before}})
    totals={k:sum(x['head'][k] for x in rows if x['in_core_budget']) for k in ('total','code')}
    out={'scenario':'D7 core line count and lib history','injection':{'kind':'none; static evidence'},'head':git('rev-parse','HEAD').strip(),'budget_rc':r.returncode,'totals':totals,'astra6_reported':{'total':2757,'code':2123},'vs_astra6':{'total':totals['total']-2757,'code':totals['code']-2123},'rows':rows,'assertion':'budget CLI rc0; printed counts agree with independent measurement; no enforcement under D7','pass':r.returncode==0 and ('總行 %d／'%totals['total']) in r.stderr and ('實際程式 %d／'%totals['code']) in r.stderr}
    (E/'core-lines.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    (E/'lib-diff-stat.txt').write_text(git('diff','--stat','510dd134..HEAD','--','proto7-2/lib'))
    (E/'lib-history.txt').write_text(git('log','--oneline','510dd134..HEAD','--','proto7-2/lib'))
    print(json.dumps({k:v for k,v in out.items() if k!='rows'},ensure_ascii=False))
finally:
    shutil.rmtree(scratch)
    (E/'core-cleanup.json').write_text(json.dumps({'root':str(scratch),'removed':not scratch.exists()}))
