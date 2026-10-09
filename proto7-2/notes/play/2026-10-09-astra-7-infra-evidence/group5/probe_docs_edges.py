"""Document inventory and additional independent regression boundaries.
Re-run: systemd-run --user --scope -q -p TasksMax=800 -p RuntimeMaxSec=1800 python3 proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/group5/probe_docs_edges.py
"""
from common import *
from types import SimpleNamespace
import hashlib
sys.path.insert(0,str(TOP/'modules'))
import history
from aos_directives import resolve, Context, Document, DirectiveError
h=Harness('docs-edges')

def documents():
    checks=[('spec §2.3','spec.md','kill 意圖先寫進'),('spec §2.6','spec.md','回收前先把意圖寫進'),('spec §4.3','spec.md','帶 `launch` 的 once 改了排程欄'),('spec §5.5','spec.md','任務或包寫在槽外的'),('spec §6','spec.md','kill 回成功的條件'),('契約卡 2.1','notes/component-contracts.md','**保證**：回收意圖落盤')]
    checks += [(x,'notes/problems.md',x) for x in ['A8-05','A8-06','A8-07','A8-08','A8-09','A8-10','A8-11','C8-01','C8-02','C8-03']]
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip();rows=[]
    for label,file,needle in checks:
        matches=[{'line':i,'text':s} for i,s in enumerate((TOP/file).read_text().splitlines(),1) if needle in s]
        rows.append({'item':label,'file':'proto7-2/'+file,'present':bool(matches),'matches':matches,'absent_note':None if matches else '未見，HEAD='+head})
    return {'injection':'none: tracked text inventory at pinned HEAD','assertion':'report existence, not invent missing entries','head':head,'rows':rows}

def actual_history_upgrade():
    oldsource=subprocess.check_output(['git','show','510dd134:proto7-2/modules/history.py'],cwd=REPO,text=True)
    # Execute exact historical producer, no repository writes; __file__ preserves import layout.
    ns={'__name__':'history_before_loop7','__file__':str(TOP/'modules/history.py')};exec(compile(oldsource,'git:510dd134/history.py','exec'),ns)
    out=h.root/'history';me={'root':str(h.root),'node_id':'observer'};st={}
    write(h.root/'a+b/.aos/last-round.json',{'round':1,'ended':[{'run':'plus-only#1','code':0}]})
    args=SimpleNamespace(src=['a+b'],out=str(out),max_lines=0,status=False)
    ns['once'](me,args,lambda p:None,st)
    before={p.name:p.read_text() for p in out.glob('*.jsonl')}
    write(h.root/'a+b/.aos/last-round.json',{'round':2,'ended':[{'run':'plus-only#2','code':0}]})
    write(h.root/'a/b/.aos/last-round.json',{'round':1,'ended':[{'run':'slash-only#1','code':0}]})
    args.src=['a+b','a/b'];history.once(me,args,lambda p:None,st)
    after={p.name:[json.loads(x) for x in p.read_text().splitlines()] for p in out.glob('*.jsonl')}
    mixed=[x['ended'][0]['run'] for x in after['a+b.jsonl']]
    assert mixed==['plus-only#1','slash-only#1'] and after['a%2Bb.jsonl'][0]['round']==2
    return {'injection':{'old_commit':'510dd134','old_source_sha256':hashlib.sha256(oldsource.encode()).hexdigest(),'old_src':['a+b'],'new_src':args.src},'assertion':'reproduce legacy ambiguity using actual old and new product writers','before':before,'after':after,'state':st,'finding':'NEW-group5-1','acceptance_pass':False,'classification':'G','known_decision_extension':'M 舊檔名不變：同 node 分檔，另加 a/b 後還會混來源；不是新編碼自身碰撞'}

def giant_pointer():
    ctx=Context(Document(None,{'array':[0]}));records=[]
    for size in (4300,4301,5000):
        inp={'$ref':'#/array/'+'9'*size}
        try:resolve(inp,ctx,['value']);actual={'class':'accepted'}
        except Exception as e:actual={'class':type(e).__name__,'code':getattr(e,'code',None),'message':str(e)[:220]}
        records.append({'digits':size,'actual':actual,'pass':actual.get('code')=='ReferencePointerInvalid'})
    # CLI also gets the malformed reference as a target argument; verify structured error boundary.
    inst=h.root/'huge-inst.json';write(inst,{'array':[0],'argv':[{'$ref':'#/array/'+'9'*5000}]})
    p=h.cli('aos-exec',inst)
    write(OUT/'giant-pointer-cli.json',{'rc':p.returncode,'stdout':p.stdout[:6000],'stderr':p.stderr[:6000]})
    return {'injection':'ASCII decimal pointer beyond CPython int conversion limit','assertion':'invalid pointer should raise DirectiveError ReferencePointerInvalid','records':records,'cli':{'rc':p.returncode,'stdout':p.stdout[:1000],'stderr':p.stderr[:1000]},'acceptance_pass':all(r['pass'] for r in records),'finding':'NEW-group5-2' if not all(r['pass'] for r in records) else None}

if __name__=='__main__':
    try:
        h.case('documents','required loop7 documentation sentences and problem rows',documents)
        h.case('history-upgrade','real historical producer then current producer',actual_history_upgrade)
        h.case('giant-pointer','additional R8-28 boundary',giant_pointer)
    finally:h.finish()
