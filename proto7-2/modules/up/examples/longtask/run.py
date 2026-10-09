"""長任務實跑驅動：起 node、寄 12 封信、中途 SIGKILL brain 一次、邊跑邊記證據、收尾。

從 repo 根跑：python3 -B proto7-2/modules/up/examples/longtask/run.py OUT [--model M] [--kill-step 7]
不給 --model 就是練習用的 AI（離線、不花錢；01 號信標題含「13 回合」，練習用的 AI 照演）。
OUT 是證據資料夾（會建）。房子在 /tmp，跑完停心跳，房子打包進 OUT/house.tar.gz 後刪掉。
"""
import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tarfile
import tempfile
import time

HERE = Path(__file__).resolve().parent
TOP = HERE.parents[3]
UP = TOP / 'modules/up/aos7-up'
MAIL = TOP / 'modules/mail/aos7-mail'
TERMINAL = ('DONE', 'BLOCKED', 'NEEDS-USER', 'FAILED')
# --compact-old：照 2026-10-09 第一次實跑寫 compact.json（6000 bytes／留 3 則、不含 STATE），用來比前後；
# 不給就用 compact 的預設（2048 bytes／留 5 則、含 wf/handoffs/*/STATE.md）。
COMPACT_OLD = {"files": ["wf/SESSION-LOG.md", "notes/journal.jsonl"], "max_bytes": 6000, "keep_recent": 3,
               "on_stage_change": True, "stage_similarity": 0.2, "summary_max_chars": 1200, "llm": None, "events": False}


def sh(*args, **kw):
    return subprocess.run([sys.executable, '-B', *map(str, args)], capture_output=True, text=True, **kw)


def letters_of(house):
    sys.path.insert(0, str(TOP / 'modules/mail'))
    from aos7_mail import letter
    out = []
    for p in (house / 'you/inbox').rglob('*.md'):
        try:
            out.append(letter(p))
        except Exception:
            pass
    return out


def procs():
    for d in Path('/proc').iterdir():
        if not d.name.isdigit():
            continue
        try:
            argv = (d / 'cmdline').read_bytes().split(b'\0')
            ppid = int((d / 'stat').read_text().rsplit(')', 1)[1].split()[1])
        except Exception:
            continue
        yield int(d.name), ppid, [a.decode(errors='replace') for a in argv if a]


def brain_tree(node):
    table = list(procs())
    roots = [pid for pid, _, argv in table if 'brain' in argv and str(node) in argv
             and any(a.endswith('aos7-up') for a in argv)]
    tree, grow = set(roots), True
    while grow:
        grow = False
        for pid, ppid, _ in table:
            if ppid in tree and pid not in tree:
                tree.add(pid)
                grow = True
    llm = [(pid, argv) for pid, _, argv in table if pid in tree and any('aos7-llmcall' in a for a in argv)]
    return roots, sorted(tree), llm


def snap(node, house, t0):
    def size(rel):
        p = node / rel
        return p.stat().st_size if p.exists() else 0
    log = (node / 'wf/SESSION-LOG.md').read_text() if (node / 'wf/SESSION-LOG.md').exists() else ''
    task = None
    try:
        task = json.loads((node / 'brain/task.json').read_text())
    except Exception:
        pass
    states = sum(len(p.read_text().splitlines()) for p in (node / 'wf/handoffs').glob('*/STATE.md'))
    receipts = list(node.glob('llmcall/*/*/receipt.json'))
    mails = letters_of(house)
    by = {}
    for m in mails:
        by[m['status']] = by.get(m['status'], 0) + 1
    roots, _, llm = brain_tree(node)
    return dict(t=round(time.time() - t0, 1), task=task and dict(id=task['id'][-12:], step=task['step'], stall=task['stall']),
                open=sum(r.startswith('- [brain]') for r in log.splitlines()), session_log=size('wf/SESSION-LOG.md'),
                journal=size('notes/journal.jsonl'), state_lines=states, receipts=len(receipts), you=by,
                brain=roots, llm_inflight=[a[a.index('--call') + 1] for _, a in llm if '--call' in a])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--model')
    ap.add_argument('--fake-delay', type=float, default=0)
    ap.add_argument('--deadline', type=float)
    ap.add_argument('--kill-step', type=int, default=7)
    # tree：brain 連同正在問 AI 的 llmcall 子程序一起殺（傳輸中途）；brain：只殺 brain，子程序留著；
    # idle：等 brain 沒在問 AI 時才殺 brain。
    ap.add_argument('--kill-mode', choices=['tree', 'brain', 'idle'], default='tree')
    ap.add_argument('--max-calls', type=int, default=90)
    ap.add_argument('--max-minutes', type=float, default=45)
    ap.add_argument('--compact-old', action='store_true', help='用第一次實跑的 compact.json（比前後用）')
    ap.add_argument('--stuck-minutes', type=float, default=5, help='這麼久沒有任何變化就停')
    a = ap.parse_args()
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    house = Path(tempfile.mkdtemp(prefix='aos-longtask.'))
    node = house / 'bob'
    events = (out / 'events.log').open('a', encoding='utf-8')

    def note(msg):
        line = time.strftime('%H:%M:%S ') + msg
        print(line, flush=True)
        events.write(line + '\n')
        events.flush()

    up = sh(UP, node, '-d', *(['--model', a.model] if a.model else []))
    note('up rc=%d %s' % (up.returncode, up.stdout.strip().replace('\n', ' / ')))
    if up.returncode:
        note(up.stderr)
        return 1
    if not a.model and a.fake_delay > 0:
        path = node / '.aos/up.json'
        cfg = json.loads(path.read_text())
        cfg['fake_delay'] = a.fake_delay
        if a.deadline is not None:
            cfg['deadline'] = a.deadline
        path.write_text(json.dumps(cfg, ensure_ascii=False))
    if a.compact_old:
        (node / 'compact.json').write_text(json.dumps(COMPACT_OLD))
    t0 = time.time()
    sent = []
    first = None
    st8 = dict(killed=None, status_at=0, last=None, changed=time.time())
    tl = (out / 'timeline.jsonl').open('a', encoding='utf-8')

    def tick():
        s = snap(node, house, t0)
        key = json.dumps({k: v for k, v in s.items() if k != 't'}, sort_keys=True)
        if key != st8['last']:
            tl.write(json.dumps(s, ensure_ascii=False) + '\n')
            tl.flush()
            st8['last'] = key
            st8['changed'] = time.time()
        if (st8['killed'] is None and first and s['task'] and s['task']['id'] == first[-12:]
                and s['task']['step'] >= a.kill_step and bool(s['llm_inflight']) == (a.kill_mode != 'idle')):
            roots, tree, llm = brain_tree(node)
            if a.kill_mode != 'tree':
                tree = roots
            for pid in tree:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            st8['killed'] = dict(mode=a.kill_mode, t=s['t'], step=s['task']['step'], pids=tree, inflight=s['llm_inflight'])
            note('SIGKILL（' + a.kill_mode + '）%s（第 %d 回合，進行中的 call %s）' % (tree, s['task']['step'], s['llm_inflight']))
            (out / 'kill.json').write_text(json.dumps(st8['killed'], ensure_ascii=False))
        if time.time() - st8['status_at'] > 60:
            st = subprocess.run([sys.executable, '-B', str(UP), 'status', str(node)], capture_output=True, text=True)
            with (out / 'status.log').open('a', encoding='utf-8') as f:
                f.write(f'--- t={s["t"]}\n' + st.stdout + st.stderr)
            st8['status_at'] = time.time()
        return s
    for f in sorted((HERE / 'letters').glob('*.txt')):
        title, body = f.read_text().split('\n', 1)
        bodyf = house / ('body-' + f.name)
        bodyf.write_text(body.strip() + '\n')
        p = sh(MAIL, 'send', 'you', 'bob', 'REQUEST', title.lstrip('# ').strip(), bodyf, '--root', house)
        sent.append(dict(n=f.stem, id=json.loads(p.stdout)['id'] if p.returncode == 0 else None, title=title[2:]))
        note('寄 %s rc=%d %s' % (f.stem, p.returncode, title[2:40]))
        first = first or sent[0]['id']
        tick()
        time.sleep(1.1)
    (out / 'sent.json').write_text(json.dumps(sent, ensure_ascii=False, indent=1))
    ids = {s['id'] for s in sent}
    while True:
        s = tick()
        done = {m['re'] for m in letters_of(house) if m['status'] in TERMINAL}
        if ids <= done:
            note('12 封都有終局回信')
            break
        if s['receipts'] >= a.max_calls:
            note('呼叫數到 %d，停' % s['receipts'])
            break
        if time.time() - st8['changed'] > a.stuck_minutes * 60:
            note('%g 分鐘沒有任何變化（卡住），停' % a.stuck_minutes)
            break
        if time.time() - t0 > a.max_minutes * 60:
            note('超過 %g 分鐘，停' % a.max_minutes)
            break
        time.sleep(1)
    note('總秒數 %.1f' % (time.time() - t0))
    time.sleep(3)
    st = subprocess.run([sys.executable, '-B', str(UP), 'status', str(node)], capture_output=True, text=True)
    (out / 'status-final.txt').write_text(st.stdout + st.stderr)
    stop = sh(UP, 'stop', node)
    note('stop rc=%d %s' % (stop.returncode, stop.stdout.strip().replace('\n', ' / ')))
    with tarfile.open(out / 'house.tar.gz', 'w:gz') as tar:
        tar.add(house, arcname='house', filter=lambda ti: ti if (ti.isfile() or ti.isdir() or ti.issym()) else None)
    note('房子打包好：%s（原房子 %s）' % (out / 'house.tar.gz', house))
    return 0


if __name__ == '__main__':
    sys.exit(main())
