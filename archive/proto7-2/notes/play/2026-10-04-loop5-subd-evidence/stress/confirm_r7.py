#!/usr/bin/env python3
"""補查（不計入 ×10）：同 G3 負載、不配全套。父 kill 後追到新代子 daemon 關完 round 7，確認原三任務與原三 runner（birth.json 的
runner pid＋starttime）都不在、last-round.json 的 alive 不列原 run。只用自己的 /tmp 根，結束照 PID 收、刪根。"""
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_stress as rs  # noqa: E402  （import 只建空的暫存根，不跑 main）

OUT = Path(__file__).resolve().parent


def main():
    root = rs.TMP / 'r7'
    parent, sub = root / 'a', root / 'a/sub'
    node = sub / 'n1'
    pslot = parent / '.aos/tasks/sub'
    cslots = [node / '.aos/tasks' / f's{i}' for i in range(3)]
    for n in (parent, node):
        (n / '.aos').mkdir(parents=True, exist_ok=True)
        rs.write_json(str(n / '.aos/timeline.json'), {'interval_ms': 100})
    worker = root / 'ignore_term.py'
    worker.write_text("import json, os, pathlib, signal, time\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\np=pathlib.Path(os.environ['AOS7_TASK']) / 'ready.json'\np.write_text(json.dumps({'pid':os.getpid(), 'run':int(os.environ['AOS7_RUN'])}))\nwhile True: time.sleep(.02)\n")
    boot = ['sh', '-c', 'aos7-ctl daemon "$AOS7_SUBROOT" register n1 --by boot > /dev/null && exec aos7-daemon "$AOS7_SUBROOT"']
    rs.write_json(str(parent / '.aos/tasks.json'), {'tasks': [{'name': 'sub', 'mode': 'keep', 'argv': [sys.executable, str(rs.TOP / 'modules/subd/aos7-subd'), 'a/sub', '--', *boot]}]})
    rs.write_json(str(node / '.aos/tasks.json'), {'tasks': [{'name': f's{i}', 'mode': 'keep', 'argv': [sys.executable, str(worker)]} for i in range(3)]})
    rs.ctl(root, 'register', 'a')
    daemon = rs.subprocess.Popen([sys.executable, str(rs.TOP / 'bin/aos7-daemon'), str(root)], cwd=rs.REPO,
                                 stdout=rs.subprocess.DEVNULL, stderr=rs.subprocess.DEVNULL)
    known = {daemon.pid}
    row = {}
    try:
        rs.wait(lambda: all(rs.read(s / 'ready.json').get('run') == rs.read(s / 'birth.json').get('run') and rs.read(s / 'ready.json').get('pid') for s in cslots))
        old_daemon = rs.read(sub / '.aosd/status.json')['pid']
        births = [rs.read(s / 'birth.json') for s in cslots]
        old_tasks = [rs.proc(rs.read(s / 'ready.json')['pid']) for s in cslots]
        old_runners = [rs.proc(b['runner']['pid']) for b in births]
        old_runs = ['s%d#%d' % (i, b['run']) for i, b in enumerate(births)]
        known.update([p['pid'] for p in old_tasks + old_runners] + [old_daemon])
        row.update(old_daemon=old_daemon, old_tasks=old_tasks, old_runners=old_runners, old_runs=old_runs)
        rs.write_json(str(pslot / 'ctl.json'), {'op': 'kill', 'run': rs.read(pslot / 'birth.json')['run'], 'by': 'loop5-r7'})

        def r7():
            st = rs.read(sub / '.aosd/status.json')
            last = rs.read(node / '.aos/last-round.json')
            return st.get('pid') not in (None, old_daemon) and isinstance(last.get('round'), int) and last['round'] >= 7 and (st, last)
        st, last = rs.wait(r7, 30)

        def same(p):   # 同一 pid＋starttime 還在才算原程序活著（pid 重用不算）
            q = rs.proc(p['pid'])
            return q['state'] not in ('gone', 'Z') and q.get('starttime') == p.get('starttime')
        row.update(new_daemon=st['pid'], new_gen=st.get('gen'), last_round=last.get('round'), last_round_alive=last.get('alive'),
                   old_tasks_alive=[p['pid'] for p in old_tasks if same(p)],
                   old_runners_alive=[p['pid'] for p in old_runners if same(p)],
                   old_runs_in_alive=[r for r in old_runs if r in json.dumps(last.get('alive'))],
                   subd_life=rs.read(sub / '.aosd/subd-life.json'), parent_out_log=(pslot / 'out.log').read_text()[-400:])
        row['pass'] = not (row['old_tasks_alive'] or row['old_runners_alive'] or row['old_runs_in_alive'])
    finally:
        known.update(rs.belonging(root))
        row['cleanup'] = rs.cleanup(root, daemon, known)
        if not row['cleanup']['after'] and not row['cleanup']['known_alive']:
            shutil.rmtree(root)
        rs.TMP.rmdir()
        row['tmp_removed'] = not rs.TMP.exists()
    (OUT / 'confirm_r7.json').write_text(json.dumps(row, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: row.get(k) for k in ('pass', 'new_gen', 'last_round', 'old_tasks_alive', 'old_runners_alive', 'old_runs_in_alive', 'tmp_removed')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
