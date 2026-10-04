"""矩陣外：owner 編碼碰撞、真 EACCES 與 tock 提交後 SIGKILL 的交集。
所有可寫測試資料只在此 evidence；使用既有 CoreCase 清場，保留精簡結果。
"""
import os, sys, json, pathlib, tempfile, shutil, time
E = pathlib.Path(__file__).resolve().parent
TOP = E.parents[2]
sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
WORK = E / 'matrix-extra-work'
WORK.mkdir(exist_ok=True)
os.environ['TMPDIR'] = tempfile.tempdir = str(WORK)
sys.path.insert(0, str(TOP/'tests'))
from _matrix import MatrixCase
from base import DaemonCase
import aos7_ctl, aos7_proc
from aos7_fs import read_json

results = {}
def run_case(name, cls, body):
    case = cls()
    case.setUp()
    try:
        results[name] = body(case)
    except Exception as ex:
        import traceback
        results[name] = {'error': repr(ex), 'traceback': traceback.format_exc()}
    finally:
        case.doCleanups()

def owners(c):
    c.mknode('a', interval_ms=200)
    variants = [('A/B','A+B'), ('甲','乙'), ('x?','x!')]
    collisions = [{'owners': [a,b], 'same_filename': aos7_ctl.fixed_name('cli','pause','a',a)==aos7_ctl.fixed_name('cli','pause','a',b),
                   'filename': aos7_ctl.fixed_name('cli','pause','a',a)} for a,b in variants]
    a = c.ctl('pause','a','--owner','甲')
    b = c.ctl('pause','a','--owner','乙')
    p = c.start_daemon(register=['a'])
    receipt = c.wait_receipt(b)
    paused = c.wait_for(lambda: (read_json(os.path.join(c.root,'.aosd','paused.json'),{}) or {}).get('paused'))
    c.stop_daemon(p)
    return {'collisions': collisions, 'same_path':a==b, 'paused':paused,'receipt_owner':receipt.get('owner')}

def replay(c, mode):
    node = c.mknode('a',[{'name':'w','mode':'keep','argv':[sys.executable, os.path.join(TOP,'modules','counter.py'),'1']}])
    c.itick()
    pj = c.wait_pid(node,'w')
    c.crash('aos7-tock','tock-summary')
    slot = pathlib.Path(c.slot(node,'w'))
    target = slot/'birth.json' if mode=='read' else slot
    oldmode = target.stat().st_mode & 0o777
    target.chmod(0 if mode=='read' else 0o555)
    try:
        # 系統真的拒絕，而不是 AOS7_TEST_FAULT 掛鉤。
        try:
            if mode=='read': target.read_bytes()
            else: (target/'cannot-write').write_text('x')
            actual_errno = None
        except OSError as ex: actual_errno = ex.errno
        rc,out,err = c.run_prog('aos7-tock')
        during = {'rc':rc,'replayed':(out or {}).get('replayed'), 'round':c.round_json(node),
                  'notification': read_json(str(slot/'tock.json')), 'actual_errno':actual_errno}
    finally:
        target.chmod(oldmode)
    # 恢復檔案權限後重跑相同回合，已關閉便不會再補通知。
    retry = c.itock()
    time.sleep(.15)
    after = {'retry':retry, 'notification':read_json(str(slot/'tock.json')),
             'task_alive':aos7_proc.pid_alive(pj['pid']), 'state':read_json(str(slot/'state.json')),
             'summary_errors':c.last_round(node).get('errors')}
    c.itick(); c.itock()
    c.wait_ended(node,'w',1)
    return {'failure':mode,'during':during,'after_permission_restored':after,
            'next_round_state':read_json(str(slot/'state.json'))}

def fifo_birth(c):
    node=c.mknode('a',[{'name':'k','mode':'keep','argv':['sleep','60']}])
    c.itick(); first=c.wait_pid(node,'k'); c.itock()
    birth=pathlib.Path(c.slot(node,'k'))/'birth.json'
    birth.unlink(); os.mkfifo(birth)
    view=dict(c.view(node,'k',2))
    tick=c.itick(); second=c.wait_pid(node,'k')
    c.itock()
    return {'fault':'真 FIFO 取代 birth.json','view':view,'tick':tick,
            'pids':[first['pid'],second['pid']],
            'both_alive':all(aos7_proc.pid_alive(p) for p in [first['pid'],second['pid']]),
            'live_procs':c.live_procs(node,'k')}

def fifo_round(c):
    node=c.mknode('a')
    c.itick(); c.itock(); c.itick()
    rp=pathlib.Path(node)/'.aos'/'round.json'
    before=read_json(str(rp)); rp.unlink(); os.mkfifo(rp)
    tick=c.itick(); after=read_json(str(rp))
    return {'fault':'真 FIFO 取代開著的 round.json','before':before,'second_tick':tick,'after':after,
            'last_round':c.last_round(node),'same_round_opened_again':before['round']==after['round']}

run_case('owner_encoding_collision',DaemonCase,owners)
run_case('replay_birth_real_eacces',MatrixCase,lambda c: replay(c,'read'))
run_case('replay_notify_real_eacces',MatrixCase,lambda c: replay(c,'write'))
run_case('nonregular_birth_live_task',MatrixCase,fifo_birth)
run_case('nonregular_open_round',MatrixCase,fifo_round)
results['cleanup'] = {'remaining_paths':[str(p.relative_to(WORK)) for p in WORK.rglob('*')]}
if not results['cleanup']['remaining_paths']: shutil.rmtree(WORK)
(E/'matrix-extra.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(results,ensure_ascii=False,indent=2))
