#!/usr/bin/env python3
"""A6-01 修補驗收：複製自 astra-5 evidence subd/confirm_stop.py（共用同目錄、逐位元組複製的 probe_subd.py），改兩處：
1. 窗口多一個 `subd-stop-seen`（status 已 stopped、還沒寫 stopped.json；loop6 加的測試點）；
2. 重開流程分兩種，都追蹤原任務 /proc pid＋starttime 與槽的 run：
   - blueprint：中斷後先照樣重開（期望 rc 1、stopped.json 在、life 補成 stopped、任務不動），再刪 stopped.json 重開（期望接回、無 run 2）；
   - original：照 astra-5 原探針，中斷後有 stopped.json 就先刪、直接重開；重開若 rc 1 且補寫了 stopped.json（被允許的 stop 停過），
     再刪一次重開。期望任務一直不被收、最後接回、無 run 2。
自己的 /tmp、真 SIGKILL（QA hook）、不用 LLM；收尾清掉所有屬於測試根的程序與 /tmp。"""
import importlib.util, json, subprocess, time, traceback
from pathlib import Path
P = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('probe', P / 'probe_subd.py'); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def identity(pid):
    try:
        p = Path(f'/proc/{pid}'); s = (p / 'stat').read_text().split(') ', 1)[1].split()
        return {'pid': pid, 'state': s[0], 'starttime': int(s[19])}
    except OSError:
        return {'pid': pid, 'state': 'gone'}


def restart(c, sub, d):
    """起一次包：回 ('rc', 退出碼) 或 ('daemon', 新子 daemon pid)。"""
    p = c.start(allow=True)
    end = time.monotonic() + 15
    while time.monotonic() < end:
        if p.poll() is not None:
            return 'rc', p.returncode
        q = m.read(sub / '.aosd/status.json').get('pid')
        if q and q != d and m.live(q):
            return 'daemon', q
        time.sleep(.02)
    raise TimeoutError('重開沒結果')


rows = []
WINDOWS = [('normal', None, 1), ('stop-seen', 'subd-stop-seen', 1), ('stopped-tmp', 'tmp:stopped.json', 1), ('life-tmp', 'tmp:subd-life.json', 3)]
for flow in ('blueprint', 'original'):
    for kind, point, n in WINDOWS:
        for i in range(1, 4):
            c = m.Case(f'astra6-{flow}-{kind}-{i}'); r = {'flow': flow, 'kind': kind, 'repeat': i, 'steps': []}
            try:
                sub = c.space(); p = c.start(allow=True, point=point, n=n); d = c.daemon(sub); old = c.ready(sub)
                r['before'] = identity(old); r['stop_receipt'] = c.ctl(sub, 'stop'); r['wrapper_rc'] = p.wait(15)
                r['hit'] = m.read(c.root / 'hit.json'); r['life_at_crash'] = m.read(sub / '.aosd/subd-life.json').get('state')
                r['stopped_at_crash'] = (sub / '.aosd/stopped.json').exists()
                if flow == 'original' and r['stopped_at_crash']:
                    (sub / '.aosd/stopped.json').unlink(); r['steps'].append('rm stopped.json')
                for _ in range(3):
                    what, v = restart(c, sub, d)
                    step = {what: v, 'stopped_json': (sub / '.aosd/stopped.json').exists(),
                            'life': m.read(sub / '.aosd/subd-life.json').get('state'), 'task': identity(old)}
                    r['steps'].append(step)
                    if what == 'daemon':
                        r['new_daemon'] = v; break
                    (sub / '.aosd/stopped.json').unlink(); r['steps'].append('rm stopped.json')
                time.sleep(.6)
                r['after'] = identity(old); r['slot_run'] = m.read(sub / 'n1/.aos/tasks/w/birth.json').get('run')
                kept = r['after'].get('starttime') == r['before']['starttime'] and r['after']['state'] != 'gone' and r['slot_run'] == 1
                first = next(s for s in r['steps'] if isinstance(s, dict))
                if kind == 'normal':
                    r['pass'] = kept
                elif flow == 'blueprint':
                    r['pass'] = (kept and r['wrapper_rc'] == -9 and r['life_at_crash'] == 'running' and first.get('rc') == 1
                                 and first['stopped_json'] and first['life'] == 'stopped' and first['task'].get('starttime') == r['before']['starttime'])
                else:
                    r['pass'] = kept and r['wrapper_rc'] == -9
            except Exception:
                r['pass'] = False; r['error'] = traceback.format_exc()
            finally:
                r['cleanup'] = c.cleanup(); rows.append(r)
                print(json.dumps({k: v for k, v in r.items() if k not in ('cleanup', 'stop_receipt')}, ensure_ascii=False), flush=True)
result = {'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=m.REPO, text=True).strip(), 'cases': rows,
          'summary': {f'{f}/{k}': '%d/%d' % (sum(1 for r in rows if r['flow'] == f and r['kind'] == k and r['pass']),
                                             sum(1 for r in rows if r['flow'] == f and r['kind'] == k))
                      for f in ('blueprint', 'original') for k, _, _ in WINDOWS},
          'final_proc_remaining': m.belonging(m.TMP), 'tmp': str(m.TMP)}
if not result['final_proc_remaining']:
    m.HOOK.unlink(); m.TMP.rmdir()
result['tmp_removed'] = not m.TMP.exists()
(P / 'confirm-stop.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result['summary'], ensure_ascii=False))
