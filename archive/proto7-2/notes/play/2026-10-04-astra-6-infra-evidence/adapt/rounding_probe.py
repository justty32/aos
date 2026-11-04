#!/usr/bin/env python3
"""Actual keep-task evidence for scale.round ties; no production/test edits."""
from probe import *
from decimal import Decimal, ROUND_HALF_UP
s=Space('rounding',decl={'steps':[{'select':'value.x'},{'scale':{'mul':1,'q':.5,'round':0,'as':'c'}}]})
rows=[]
try:
    s.boot()
    cli=subprocess.run([PY,str(P/'packs/adapt/bin/aos7-adapt'),'check',str(s.dst/'adapt/temp.json')],capture_output=True,text=True)
    for n,x in enumerate((.5,1.5,2.5,3.5,4.5,5.5,-.5,-1.5,-2.5,-3.5),2):
        s.source(n,x);r=s.cycle()
        rows.append({'source':x,'actual':r['value']['c'],'usual_half_up':float(Decimal(str(x)).quantize(Decimal('1'),rounding=ROUND_HALF_UP)), 'register':r})
    write_json(str(E/'rounding-results.json'),{'contract':'packs/adapt/spec.md §2 scale: 有 round 就四捨五入','check':{'returncode':cli.returncode,'stdout':cli.stdout,'stderr':cli.stderr,'declaration':s.decl},'rows':rows,'note':'實作是 Python ties-to-even；誤差界仍涵蓋原值。正2.5已足以證明文字落差；負值另附對照，不依賴負值四捨五入定義判bug。'})
finally:s.finish()
