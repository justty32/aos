"""Static exit-code/unit contract crosscheck with source excerpts and measured-case links.
Rerun: python3 proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/pack4/doc_probe.py
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess as sp
import sys
HERE=Path(__file__).resolve().parent
TOP=next(p for p in HERE.parents if p.name=='proto7-2')
def evidence(path,needle):
    text=path.read_text();lines=text.splitlines()
    matches=[dict(line=i+1,text=line) for i,line in enumerate(lines) if needle in line]
    return dict(file=str(path.relative_to(TOP.parent)),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),matches=matches)
def main():
    if os.environ.get('PACK4_SCOPED')!='1':
        return sp.call(['systemd-run','--user','--scope','-q','-p','TasksMax=800','-p','RuntimeMaxSec=1800',
          '/usr/bin/env','PACK4_SCOPED=1','PYTHONDONTWRITEBYTECODE=1',sys.executable,str(Path(__file__).resolve())],cwd=TOP.parent)
    sources=[TOP/'packs/budget/README.md',TOP/'packs/budget/spec.md',TOP/'packs/budget/aos7_budget_gate.py']
    tables=[]
    for p in sources:
        if p.suffix=='.py':
            tree=ast.parse(p.read_text());txt=ast.get_docstring(next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='call'))
        else:txt='\n'.join(l for l in p.read_text().splitlines() if re.match(r'- [0-3]＝',l))
        txt=txt.replace('**','').replace('`','')
        parts=re.split(r'(?:^|\n)\s*-?\s*([0-3])＝',txt)
        table={int(parts[i]):re.sub(r'\s+','',parts[i+1]) for i in range(1,len(parts),2)}
        assert set(table)=={0,1,2,3},table
        requirements={0:['受理成功','已結算','終局結果已交付','stdout','--out'],
         1:['終局但不成功','failed／rejected','denied／cancelled','已結算','denied／conflict／bad','入口conflict'],
         2:['壞輸入','參數不合','payload不存在或不是JSON','沒送任何請求'],
         3:['未完整交付終局結果','還沒預留','intent','已結算但--out寫入失敗','status','同K重送','冪等','不重扣']}
        checks={str(code):all(word in table[code] for word in words) for code,words in requirements.items()}
        assert all(checks.values()),(p,checks,table)
        tables.append(dict(source=str(p.relative_to(TOP.parent)),table=table,assertions=checks,
                           references=[evidence(p,str(c)+'＝') for c in range(4)]))
    assert tables[0]['table']==tables[1]['table'],'README/spec tables differ'
    units=[evidence(p,'加權成本') for p in sources[:2]]
    assert all(x['matches'] for x in units)
    step=TOP/'packs/step/spec.md'
    clauses=[evidence(step,s) for s in ['unknown_codes','過期 intent','額度屬於 request','歸零','attempt 號照加']]
    assert all(x['matches'] for x in clauses)
    result=dict(scenario='documentation consistency',injection='none; read-only source parsing',pass_=True,
      assertions='0/1/2/3 tables semantically agree at all three locations; README/spec exact normalized equality; weighted units and step rules present',
      budget_tables=tables,unit_references=units,step_references=clauses,
      behavior_evidence={'unknown_codes':'results.json: unknown-recover, unknown-exhaust, unknown-default, validation',
       'expired_intent':'results.json: intent-receipt/resend/stop/same-round','resends':'results.json: resend-open-fail, unknown-exhaust',
       'units':'results.json: weighted'},
      caveats=['User task says no a3, but step spec §5.4 explicitly increments attempt number after refused table write: actual a1+a3 executions, ran=2.',
               'Physical pre-write EIO retains intent; covered separately as an extension of R8-22, results.json:resend-write-fail.'])
    (HERE/'doc-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=1)+'\n')
    print(json.dumps({'pass':True,'exit_code_tables':3,'step_clauses':len(clauses)}))
if __name__=='__main__':sys.exit(main())
