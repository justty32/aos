#!/usr/bin/env python3
"""Independent evidence oracle, does not import production modules or test helpers."""
import json, hashlib
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
E=Path(__file__).resolve().parent
failures=[];checked=0;band_checks=0;rounding_differences=[]
for file in sorted(E.glob('*-registers.json')):
    for r in json.loads(file.read_text()):
        if not r.get('trace') or not r.get('basis'):continue
        if r['trace'][0]['step']!='select':continue
        b=r['basis'];x=r['trace'][0]['x']
        doc={'v':1,'seq':b['seq'],'round':b['src_round'],'value':{'x':x,'other':'omitted'}}
        sha=hashlib.sha256(json.dumps(doc,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        if sha!=b['sha']:failures.append([file.name,r['my_round'],'basis_sha'])
        checked+=1
        if r['state']!='ok':
            if r['value'] is not None or r['err'] is not None:failures.append([file.name,r['my_round'],'unknown_exposes_value'])
        if len(r['trace'])<2:continue
        boundary=file.name.startswith('boundary-');rounding=file.name.startswith('rounding-')
        mul=Decimal('1') if boundary or rounding else Decimal('.1')
        q=Decimal('.5') if boundary or rounding else Decimal('.05')
        expected=Decimal(str(x))*mul
        if not boundary:expected=expected.quantize(Decimal('1') if rounding else Decimal('.1'),rounding=ROUND_HALF_UP)
        actual=Decimal(str(r['trace'][1]['x']))
        if expected!=actual:
            row=[file.name,r['my_round'],str(x),str(expected),str(actual)]
            (rounding_differences if rounding else failures).append(row)
        if Decimal(str(r['trace'][1]['err']))!=q:failures.append([file.name,r['my_round'],'err'])
        if len(r['trace'])>2:
            t=r['trace'][2];op=next(k for k in ('ge','gt','le','lt') if k in t);threshold=Decimal(str(t[op]));lo=expected-q;hi=expected+q
            cmp={'ge':lambda v:v>=threshold,'gt':lambda v:v>threshold,'le':lambda v:v<=threshold,'lt':lambda v:v<threshold}[op]
            want=cmp(lo) if cmp(lo)==cmp(hi) else None
            if t['v'] is not want:failures.append([file.name,r['my_round'],'band',str(lo),str(hi),want,t['v']])
            band_checks+=1
out={'basis_hash_checks':checked,'independent_decimal_band_checks':band_checks,'failures':failures,'documented_rounding_differences':rounding_differences,'passed_other_than_A7_01':not failures}
(E/'audit-results.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(out,ensure_ascii=False))
