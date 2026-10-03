"""README -> spec.md only; no prototype imports. Run from any cwd."""
import json, os, pathlib, shutil, subprocess, sys, tempfile, time
HERE = pathlib.Path(__file__).resolve().parent
PROTO = HERE.parents[2]
root = pathlib.Path(tempfile.mkdtemp(prefix='astra-new-space-'))
def write(rel, value):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    tmp.replace(p)
def read(rel, default=None):
    try: return json.loads((root / rel).read_text())
    except (OSError, ValueError): return default
for node, interval in [('lab',180),('lab/agents/ada',140),('lab/agents/ben',160),('ledger',150)]:
    write(f'{node}/.aos/timeline.json', {'interval_ms':interval})
write('lab/.aos/tasks.json', {'tasks':[{'name':'kernel','mode':'keep','argv':['aos7-kernel']}]})
write('lab/kernel.json', {'members':['agents/ada','agents/ben'],'stuck_rounds':8,'budget_tokens':300,'cool_rounds':3})
for name in ['ada','ben']:
    write(f'lab/agents/{name}/.aos/tasks.json', {'tasks':[{'name':'agent','mode':'keep','argv':['aos7-agent']}]})
    write(f'lab/agents/{name}/agent.json', {'name':name,'persona':'交換 ping，完成後留下工作成果。','llm':'fake','max_ping':12})
write('lab/agents/ada/goal.json', {'say_first':{'to':'lab/agents/ben','body':'ping 1'}})
write('ledger/.aos/tasks.json', {'tasks':[{'name':'census','mode':'each','argv':['python3','census.py'],'dirs':['../lab/agents']}]})
(root / 'ledger/census.py').write_text('''import json, os\nfrom pathlib import Path\nroot=Path(os.environ['AOS7_ROOT'])\nnode=Path(os.environ['AOS7_NODE'])\nr=json.loads((node/'.aos/round.json').read_text())['round']\nrow={'round':r,'letters_done':len(list((root/'lab/agents').glob('*/inbox/done/*.json'))),'finished_agents':len(list((root/'lab/agents').glob('*/work/done.txt')))}\np=node/'census.json'\nt=p.with_suffix('.tmp'); t.write_text(json.dumps(row)); t.replace(p)\nwith (node/'census.jsonl').open('a') as f: f.write(json.dumps(row)+'\\n')\nprint(json.dumps(row))\n''')
(root / '.aosd').mkdir(exist_ok=True)
log = (root / 'daemon-output.log').open('w')
p = subprocess.Popen([sys.executable,str(PROTO/'bin/aos7-daemon'),str(root)],stdout=log,stderr=subprocess.STDOUT)
events=[]
try:
    deadline=time.monotonic()+35
    paused=False; resumed=False; restarted=False
    while time.monotonic()<deadline and p.poll() is None:
        r=read('ledger/.aos/round.json',{}).get('round',0)
        if r >= 10 and not paused:
            write('.aosd/ctl/manual-pause.json',{'op':'pause','node':'ledger','by':'reader'})
            paused=True; events.append({'action':'pause ledger','round':r,'at':time.monotonic()})
        if paused and not resumed and time.monotonic()-events[-1]['at'] > .7:
            events.append({'action':'observe paused ledger','round':r,'status':read('.aosd/status.json',{}).get('nodes',{}).get('ledger')})
            write('.aosd/ctl/manual-resume.json',{'op':'resume','node':'ledger','by':'reader'}); resumed=True
        if r >= 25 and not restarted:
            write('lab/agents/ada/.aos/tasks/agent-r1/ctl.json',{'op':'restart','by':'reader','why':'test file-only control'})
            restarted=True; events.append({'action':'restart ada','ledger_round':r})
        if r>=50: break
        time.sleep(.025)
    write('.aosd/ctl/zz-stop.json',{'op':'stop','kill':True,'by':'reader'})
    p.wait(timeout=10)
finally:
    if p.poll() is None: p.terminate(); p.wait(timeout=10)
    log.close()
summary={'root':str(root),'daemon_exit':p.returncode,'events':events,'nodes':{},'census':read('ledger/census.json'),'daemon_controls':{x.name:json.loads(x.read_text()) for x in (root/'.aosd/ctl-done').glob('*.json')}}
for node in ['lab','lab/agents/ada','lab/agents/ben','ledger']:
    base=root/node
    summary['nodes'][node]={'round':read(f'{node}/.aos/round.json'),'task_count':len(list((base/'.aos/tasks').glob('*'))),'work_done':(base/'work/done.txt').read_text() if (base/'work/done.txt').exists() else None,'states':{x.parent.name:json.loads(x.read_text()) for x in (base/'.aos/tasks').glob('*/state.json')},'exits':{x.parent.name:json.loads(x.read_text()) for x in (base/'.aos/tasks').glob('*/exit.json')},'kernel_decisions':[json.loads(line) for x in (base/'.aos/tasks').glob('*/decisions.jsonl') for line in x.read_text().splitlines()]}
(HERE/'new-space-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
shutil.copy(root/'ledger/census.jsonl',HERE/'new-space-census.jsonl')
shutil.copy(root/'daemon-output.log',HERE/'new-space-daemon.log')
print(json.dumps(summary,ensure_ascii=False,indent=2))
