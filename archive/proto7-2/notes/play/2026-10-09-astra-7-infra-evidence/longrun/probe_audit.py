#!/usr/bin/env python3
"""Reproduce: python3 proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/longrun/probe_audit.py
Replay the independent longrun snapshots; no product imports or execution.
"""
import copy, hashlib, json, pathlib, re, subprocess, sys, tarfile
E=pathlib.Path(__file__).resolve().parent;ROOT=E.parents[4]
if '--scoped' not in sys.argv:
    raise SystemExit(subprocess.call(['systemd-run','--user','--scope','-q','-p','TasksMax=800','-p','RuntimeMaxSec=1800',sys.executable,str(__file__),'--scoped'],cwd=ROOT))
def normal(names):
    return sorted(re.sub(r'[0-9a-f]{8}-(convert|stats)-\d+-a\d+',r'<inst>-\1-1-a1',re.sub(r'\.tmp\.\d+',r'.tmp.<pid>',n)) for n in names)
def load(t,n):return json.load(t.extractfile(n))
rows=[]
def check(name,yes,actual):rows.append({'scenario':'snapshot replay','injection':{'kind':'none; post-run evidence analysis'},'assertion':name,'actual':actual,'pass':bool(yes)})
with tarfile.open(E/'step-snapshots.tar.gz') as t:
    inv=load(t,'round-inventories.json');cs=[load(t,n) for n in t.getnames() if n.startswith('completed/') and n.endswith('.json')]
    names=[normal(c['files']['job']) for c in cs]
    check('completed job filename set stable after replacing only instance id',bool(names) and all(n==names[0] for n in names),{'snapshots':len(names),'first':names[0] if names else [],'variants':len({tuple(n) for n in names})})
    leftover=[]
    for c in cs:
        inst=c['frame']['inst']
        for n in c['files']['job']:
            if n.startswith('results/') and not pathlib.Path(n).name.startswith(inst+'-'):leftover.append({'inst':inst,'file':n})
    check('no previous instance result file at any completion',not leftover,{'checked':len(cs),'leftover':leftover})
    fr=load(t,'final-root/a/jobs/csv/frame.json')
    all_ids=[c['frame']['inst'] for c in cs]
    check('final ended instance included in completed snapshots',fr['phase']!='ended' or fr['inst'] in all_ids,{'phase':fr['phase'],'inst':fr['inst'],'captured':fr['inst'] in all_ids})
    unions={k:sorted({n for v in inv for n in normal(v[k])}) for k in ('job','slots','aosd')}
    check('observed names stay within finite reused product layout',len(unions['job'])<=24 and len(unions['slots'])<=55 and len(unions['aosd'])<=18,{'normalized_union':unions,'counts':{k:len(v) for k,v in unions.items()}})
    def completed_ok(c):
        f=c['frame'];a=f['accepted'];report=c['report'];rs=list(c['results'].values())
        return f['end']=='ok' and f.get('resends')=={} and len(f['tries'])==2 and all(v==1 for v in f['tries'].values()) and report['from']==a['convert']['request'] and len(rs)==2 and all(v['ok'] and v['code']==0 and v['attempt'].endswith('-a1') and v['inst']==f['inst'] for v in rs)
    good=all(completed_ok(c) for c in cs)
    neg=[]
    for field in ('resends','attempt','request'):
        c=copy.deepcopy(cs[0])
        if field=='resends':c['frame']['resends']['bogus']=1
        if field=='attempt':next(iter(c['results'].values()))['attempt']='bogus-a2'
        if field=='request':c['report']['from']='wrong-request'
        neg.append({'mutation':field,'rejected':not completed_ok(c)})
    check('independent completion checker accepts observed snapshots and rejects three corruptions',good and all(n['rejected'] for n in neg),{'observed':len(cs),'negative_controls':neg})
with tarfile.open(E/'adapt-snapshots.tar.gz') as t:
    rs=[load(t,'rounds/'+str(n)+'.json') for n in range(1,322)]
    def valid(o):
        z=o['register'];n=o['closed']['round'];src=o['source']
        sha=hashlib.sha256(json.dumps(src,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        return z['my_round']==n and not o['closed']['open'] and z['state']=='ok' and z['value']=={'c':80.1,'hot':True} and z['basis']['sha']==sha and z['basis']['seq']==n and z['basis']['src_round']==n and z['skipped']==0
    neg=[]
    for field in ('value','basis','round'):
        o=copy.deepcopy(rs[-1])
        if field=='value':o['register']['value']['c']=80.2
        if field=='basis':o['register']['basis']['seq']=1
        if field=='round':o['closed']['open']=True
        neg.append({'mutation':field,'rejected':not valid(o)})
    check('independent adapt replay accepts 321 rounds and rejects three corruptions',all(valid(o) for o in rs) and all(n['rejected'] for n in neg),{'rounds':len(rs),'negative_controls':neg})
out={'checks':rows,'pass':all(x['pass'] for x in rows)}
(E/'snapshot-audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'pass':out['pass'],'checks':len(rows)}))
