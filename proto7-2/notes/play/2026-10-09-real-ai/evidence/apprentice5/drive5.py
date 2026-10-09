#!/usr/bin/env python3
"""AP5 對照實驗：一組連做四題 mail 題，每題最多 R 輪（第一輪＋重問），交件用文字格式（propose --format text）。

用法（cwd＝學徒 node；budget 帳任務要先開著）：
  drive5.py VARIANT OUTDIR --rep N [--tasks mailcount,mailsent,mailopen,mailstatus] [--model M] [--review M] [--rounds 5]
            [--max-calls 600] [--calls FILE] [--offline]
VARIANT：A＝每題全新開始（不帶技能、不寫技能）；B＝連做：每題只要有被擋過（沒一次過）就 learn --skill-into OUTDIR/skillnode
         改寫自己的技能書，下一題 propose --skills OUTDIR/skillnode（aos7-skills 本機挑，挑到才放進提示）。第 1 題兩組條件相同。
慣例命中＝第 2 關答案檢查器訊息提到某條藏起來的慣例（done／dot／teams），每輪每條算一次。
「過」＝propose 三關（含模型審查）都過；不發布分支。
呼叫帳 --calls（預設 OUTDIR/../calls.jsonl，各組共用、持鎖）：每輪先預留 2（出題＋審查），沒走到審查退回 1；learn 預留 1。
疑似代理問題＝沒交回候選，或 ①json 擋下且回覆 <500 字元；連兩輪 → 整組停，退 5。
rid＝<tag><題><組><rep>（例 SmailopenB3），metrics 以 author/<rid> 分單。
"""
import argparse, fcntl, json, shutil, subprocess, sys, time
from pathlib import Path

P = Path(__file__).resolve().parents[5]  # proto7-2/
AUTHOR = P / 'packs/author/bin/aos7-author'
EX = P / 'packs/author/examples'
TASKS = ('mailcount', 'mailsent', 'mailopen', 'mailstatus')
HIDDEN = {'done': 'inbox/done/', 'dot': '. 開頭', 'teams': 'teams/'}
SKILL = 'aos-tool-apprentice'


def run(argv, out):
    t = time.time()
    p = subprocess.run(argv, capture_output=True, text=True)
    Path(out).write_text(p.stdout)
    if p.stderr.strip():
        Path(str(out) + '.stderr').write_text(p.stderr)
    try:
        doc = json.loads(p.stdout)
    except ValueError:
        doc = {'ok': False, 'raw': p.stdout[-2000:]}
    return p.returncode, doc, round(time.time() - t, 1)


def calls_used(path):
    try:
        return sum(json.loads(x)['n'] for x in Path(path).read_text().splitlines() if x.strip())
    except FileNotFoundError:
        return 0


def ledger(path, n, max_calls=None, **row):
    with open(str(path) + '.lock', 'a') as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        if max_calls is not None and calls_used(path) + n > max_calls:
            return False
        with open(path, 'a') as f:
            f.write(json.dumps(dict(row, n=n, at=round(time.time(), 1)), ensure_ascii=False) + '\n')
        return True


def prepare(task, rid, out):
    src, req = EX / f'aos-tool-{task}', out / 'req'
    if req.exists():
        shutil.rmtree(req)
    shutil.copytree(src, req, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    doc = json.loads((req / 'request.json').read_text())
    doc['rid'] = rid
    (req / 'request.json').write_text(json.dumps(doc, ensure_ascii=False, indent=1) + '\n')
    valid = json.loads((req / 'valid.json').read_text())
    valid['rid'] = rid
    (out / 'valid-cand.json').write_text(json.dumps(valid, ensure_ascii=False))
    # 上下文：run_all.py＋信箱頂層的一封 REQUEST、一封有 re 的回信（不從 done/、.tmp/、teams/ 挑，免得洩漏慣例）
    top = sorted(p for p in (src / 'fixture').glob('*/inbox/*.md') if p.parts[-3] != 'teams')
    pick = [next(p for p in top if p.name.endswith('-REQUEST.md')),
            next(p for p in top if p.name.endswith('-DONE.md') or p.name.endswith('-BLOCKED.md'))]
    return req / 'request.json', out / 'valid-cand.json', [P / 'tests/run_all.py'] + pick


def issues_of(chk):
    return [i for g in (chk.get('gates') or {}).values() for i in (g.get('issues') or [])]


def proxy_suspect(doc, chk, cand):
    if doc.get('why') in ('invalid', 'unknown') and not Path(cand).exists():
        return True
    try:
        size = len(Path(cand).read_text(encoding='utf-8').strip())
    except (OSError, UnicodeError):
        size = 0
    return chk.get('failed_gate') == 1 and {'json', 'text'} & {i.get('rule') for i in issues_of(chk)} and size < 500


def do_task(a, task, rid, out, skillnode, use_skill, streak):
    out.mkdir(parents=True, exist_ok=True)
    req, valid, ctx = prepare(task, rid, out)
    rows, prev, fb, feedbacks, t0, stop, last = [], None, None, [], time.time(), None, None
    for r in range(1, a.rounds + 1):
        if not a.offline and not ledger(a.calls, 2, a.max_calls, rid=rid, kind='reserve-propose+review', round=r):
            stop = 'max-calls'
            break
        cand = out / f'cand-r{r}.txt'
        if a.offline:
            argv = ['python3', str(AUTHOR), 'propose', str(req), '--candidate', str(valid), '--reviewer', 'rules']
        else:
            argv = ['python3', str(AUTHOR), 'propose', str(req), '--out', str(cand), '--llm', a.model,
                    '--budget', 'budget/llm', '--review-llm', a.review, '--deadline', '900', '--format', 'text',
                    '--call', f'{rid}-r{r}-{int(time.time())}']
            for c in ctx:
                argv += ['--context', str(c)]
            if use_skill:
                argv += ['--skills', str(skillnode)]
            if prev:
                argv += ['--previous', str(prev), '--feedback', str(fb)]
        code, doc, secs = run(argv, out / f'propose-r{r}.json')
        chk = doc.get('check') or {}
        fb = out / f'feedback-r{r}.json'
        fb.write_text(json.dumps(chk, ensure_ascii=False, indent=1))
        feedbacks.append(fb)
        u = (doc.get('llm') or {}).get('usage') or {}
        rv = doc.get('review') or {}
        ru = (rv.get('llm') or {}).get('usage') or {}
        if not a.offline and not rv.get('llm'):
            ledger(a.calls, -1, rid=rid, kind='release-review', round=r)
        suspect = (not a.offline) and proxy_suspect(doc, chk, cand)
        streak[0] = streak[0] + 1 if suspect else 0
        iss = issues_of(chk)
        blob = json.dumps(iss, ensure_ascii=False)
        row = dict(hidden=sorted(k for k, v in HIDDEN.items() if v in blob), round=r, exit=code, ok=doc.get('ok'), why=doc.get('why'), failed_gate=chk.get('failed_gate'),
                   rules=sorted({i.get('rule') for i in iss} - {None}), tokens=u.get('total_tokens'),
                   review_tokens=ru.get('total_tokens'), secs=secs, skill=doc.get('skill'),
                   proxy_suspect=suspect, issues=[{k: str(v)[:300] for k, v in i.items()} for i in iss][:6])
        rows.append(row)
        print(json.dumps(dict(rid=rid, **row), ensure_ascii=False)[:700], flush=True)
        if cand.exists():
            last = cand
        if streak[0] >= 2:
            stop = 'proxy'
            break
        if doc.get('ok'):
            break
        prev = cand if cand.exists() else prev
    passed = any(x.get('ok') for x in rows)
    learn = None
    clean = len(rows) == 1 and passed
    if a.variant == 'B' and not a.offline and stop is None and not clean and ledger(a.calls, 1, a.max_calls, rid=rid, kind='reserve-learn'):
        argv = ['python3', str(AUTHOR), 'learn', str(req), '--llm', a.learn_model or a.model, '--budget', 'budget/llm',
                '--skill-into', str(skillnode), '--skill', SKILL, '--call', f'{rid}-learn-{int(time.time())}']
        if last:
            argv += ['--candidate', str(last)]
        for f in feedbacks:
            argv += ['--history', str(f)]
        code, doc, secs = run(argv, out / 'learn.json')
        sk = skillnode / 'skills' / SKILL / 'SKILL.md'
        learn = dict(exit=code, ok=doc.get('ok'), why=doc.get('why'), error=doc.get('error'), secs=secs,
                     tokens=((doc.get('llm') or {}).get('usage') or {}).get('total_tokens'),
                     bytes=sk.stat().st_size if sk.exists() else None)
        if sk.exists():
            shutil.copyfile(sk, out / 'SKILL-after.md')
    return dict(task=task, rid=rid, passed=passed, rounds=len(rows), reasks=max(len(rows) - 1, 0),
                fails={g: sum(1 for x in rows if x.get('failed_gate') == g) for g in (1, 2, 3)},
                hidden={k: sum(1 for x in rows if k in x.get('hidden', [])) for k in HIDDEN},
                tokens=sum(x.get('tokens') or 0 for x in rows), review_tokens=sum(x.get('review_tokens') or 0 for x in rows),
                secs=round(time.time() - t0, 1), stop=stop, rows=rows, learn=learn)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('variant', choices=['A', 'B'])
    ap.add_argument('outdir')
    ap.add_argument('--rep', type=int, required=True)
    ap.add_argument('--tasks', default=','.join(TASKS))
    ap.add_argument('--model', default='chatgpt-gpt-6-luna')
    ap.add_argument('--learn-model')
    ap.add_argument('--review', default='chatgpt-gpt-6-astra-high')
    ap.add_argument('--rounds', type=int, default=5)
    ap.add_argument('--max-calls', type=int, default=600)
    ap.add_argument('--calls')
    ap.add_argument('--offline', action='store_true')
    ap.add_argument('--tag', default='', help='rid 前綴（不同模型同時跑時避免 rid／call 撞名），例 L、S')
    a = ap.parse_args()
    out = Path(a.outdir).resolve()
    if (out / 'summary.json').exists():
        print('drive5: 這組已跑過，換 OUTDIR／--rep', file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    a.calls = Path(a.calls).resolve() if a.calls else out.parent / 'calls.jsonl'
    skillnode = out / 'skillnode'
    (skillnode / 'skills').mkdir(parents=True, exist_ok=True)
    results, stop, streak = [], None, [0]
    for i, task in enumerate(a.tasks.split(','), 1):
        use = a.variant == 'B' and (skillnode / 'skills' / SKILL / 'SKILL.md').exists()
        res = do_task(a, task, f'{a.tag}{task}{a.variant}{a.rep}', out / f'{i}-{task}', skillnode, use, streak)
        res.update(order=i, skill_in_prompt=use)
        results.append(res)
        if res['stop']:
            stop = res['stop']
            break
    (out / 'summary.json').write_text(json.dumps(dict(variant=a.variant, rep=a.rep, model=a.model, review=a.review,
        rounds=a.rounds, offline=a.offline, stop=stop, calls_total=calls_used(a.calls), results=results),
        ensure_ascii=False, indent=1))
    print(json.dumps(dict(variant=a.variant, rep=a.rep, stop=stop, passed=[r['passed'] for r in results],
                          rounds=[r['rounds'] for r in results]), ensure_ascii=False))
    return 5 if stop == 'proxy' else 0


if __name__ == '__main__':
    sys.exit(main())
