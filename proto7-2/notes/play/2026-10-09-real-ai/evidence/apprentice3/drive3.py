#!/usr/bin/env python3
"""S3 學徒三連題：一組（A 帶踩坑／B 不帶）連做 gap→runs→audit，每題最多 3 輪（2 次重問）。

用法（在學徒 node 下跑，cwd＝node；budget 帳任務要先開著）：
  drive3.py VARIANT OUTDIR [--rep N] [--tasks gap,runs,audit] [--model M] [--review M]
            [--max-calls 200] [--calls FILE] [--compact] [--offline]
VARIANT：A＝帶踩坑（OUTDIR/gotchas.txt 從 gotchas-before 起，每題後 learn 追加，題 2 起 --gotchas 帶上；題 1 與 B 條件相同）；B＝不帶、不 learn。
--offline：不打 AI，用各題 valid.json 當候選跑三關①②（驗管線用）；不發布、不 learn。
真 AI 呼叫數記在 --calls（預設 OUTDIR/../calls.jsonl，各組共用）：每次先持鎖預留（出題＋審查 2、learn 1）再呼叫，
沒走到審查退回 1；預留超過 --max-calls 就停（stop=max-calls）。帳 ≥ 真實送出數。
疑似代理問題＝沒交回候選（空回覆／HTTP 失敗），或 ①json 擋下且回覆 <500 字元；連兩輪（可跨題）→ 整組停，退 5，stop=proxy。
passed＝propose 過三關且 publish 退 0（--repo 預設本 repo 根）。同 rid 已跑過（summary 在或 llmcall 有紀錄）→ 退 2，換 --rep。
rid＝<題><組><rep>（如 gapA1），metrics 以 author/<rid> 分單，A／B 不混。
"""
import argparse, fcntl, json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path

P = Path(__file__).resolve().parents[5]  # proto7-2/
AUTHOR = P / 'packs/author/bin/aos7-author'
COMPACT = P / 'modules/compact/aos7-compact'
EX = P / 'packs/author/examples'
BASE_GOTCHAS = Path(__file__).resolve().parents[1] / 'apprentice/gotchas-before.txt'
TASKS = ('gap', 'runs', 'audit')
COMMON_CTX = [P / 'tests/run_all.py', P / 'packs/usage/aos7_usage.py', P / 'packs/usage/bin/aos7-usage']


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
    """帳＝預留 n 的加總（每行 {"n": ±k}）；先預留再呼叫，所以帳 ≥ 真實送出數。"""
    try:
        return sum(json.loads(line)['n'] for line in Path(path).read_text().splitlines() if line.strip())
    except FileNotFoundError:
        return 0


def ledger(path, n, max_calls=None, **row):
    """持鎖：max_calls 給了就先核 used+n ≤ max_calls，不夠回 False 不寫。多組同跑共用同一檔也不會超。"""
    with open(str(path) + '.lock', 'a') as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        if max_calls is not None and calls_used(path) + n > max_calls:
            return False
        with open(path, 'a') as f:
            f.write(json.dumps(dict(row, n=n, at=round(time.time(), 1)), ensure_ascii=False) + '\n')
        return True


def prepare(task, rid, out):
    """複製題目到 OUTDIR/<task>/req（rid 改成本組的），回 (需求檔, valid 候選, context)。"""
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
    fx = sorted(p for p in (src / 'fixture').rglob('*') if p.is_file() and p.stat().st_size <= 2048)
    return req / 'request.json', out / 'valid-cand.json', COMMON_CTX + fx[:3]


def proxy_suspect(doc, chk, cand):
    if doc.get('why') in ('invalid', 'unknown') and not Path(cand).exists():
        return True              # 沒交回候選（空回覆、HTTP／代理失敗）
    rules = [i.get('rule') for g in (chk.get('gates') or {}).values() for i in (g.get('issues') or [])]
    try:
        size = len(Path(cand).read_text(encoding='utf-8').strip())
    except (OSError, UnicodeError):
        size = 0
    return chk.get('failed_gate') == 1 and 'json' in rules and size < 500


def do_task(a, task, rid, out, gotchas, use_gotchas, streak):
    out.mkdir(parents=True, exist_ok=True)
    req, valid, ctx = prepare(task, rid, out)
    rows, prev, fb, feedbacks, t0 = [], None, None, [], time.time()
    stop = None
    for r in (1, 2, 3):
        if not a.offline and not ledger(a.calls, 2, a.max_calls, rid=rid, kind='reserve-propose+review', round=r):
            stop = 'max-calls'
            break
        cand = out / f'cand-r{r}.json'
        argv = ['python3', str(AUTHOR), 'propose', str(req), '--out', str(cand)]
        if a.offline:
            argv = ['python3', str(AUTHOR), 'propose', str(req), '--candidate', str(valid), '--reviewer', 'rules']
        else:
            argv += ['--llm', a.model, '--budget', 'budget/llm', '--review-llm', a.review, '--deadline', '600',
                     '--call', f'{rid}-r{r}-{int(time.time())}']
            for c in ctx:
                argv += ['--context', str(c)]
            if gotchas and use_gotchas:
                argv += ['--gotchas', str(gotchas)]
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
            ledger(a.calls, -1, rid=rid, kind='release-review', round=r)   # 沒走到審查，退回預留
        suspect = (not a.offline) and proxy_suspect(doc, chk, cand)
        streak[0] = streak[0] + 1 if suspect else 0
        row = dict(round=r, exit=code, ok=doc.get('ok'), why=doc.get('why'), failed_gate=chk.get('failed_gate'),
                   rules=sorted({i.get('rule') for g in (chk.get('gates') or {}).values() for i in (g.get('issues') or [])} - {None}),
                   tokens=u.get('total_tokens'), review_tokens=ru.get('total_tokens'), secs=secs,
                   job=doc.get('job'), proxy_suspect=suspect,
                   issues=[i for g in (chk.get('gates') or {}).values() for i in (g.get('issues') or [])][:6])
        rows.append(row)
        print(json.dumps(dict(rid=rid, **row), ensure_ascii=False)[:600], flush=True)
        if streak[0] >= 2:       # 連兩輪（可跨題）疑似代理問題 → 整組停
            stop = 'proxy'
            break
        if doc.get('ok'):
            if not a.offline:
                rvp = rv.get('path')
                pargv = ['python3', str(AUTHOR), 'publish', str(req), '--candidate', str(cand),
                         '--reviewer', 'file:' + rvp if rvp else 'rules', '--ref', 'main', '--repo', str(a.repo)]
                pc, pd, ps = run(pargv, out / 'publish.json')
                rows.append(dict(publish_exit=pc, branch=pd.get('branch'), commit=pd.get('commit'), dup=pd.get('dup'), secs=ps))
            break
        prev = cand if cand.exists() else prev
    learn = None
    if gotchas and not a.offline and stop is None and ledger(a.calls, 1, a.max_calls, rid=rid, kind='reserve-learn'):
        before = gotchas.stat().st_size
        argv = ['python3', str(AUTHOR), 'learn', str(req), '--llm', a.model, '--budget', 'budget/llm',
                '--into', str(gotchas)]
        for f in feedbacks:
            argv += ['--history', str(f)]
        code, doc, secs = run(argv, out / 'learn.json')
        learn = dict(exit=code, ok=doc.get('ok'), added=doc.get('added'), secs=secs,
                     tokens=((doc.get('llm') or {}).get('usage') or {}).get('total_tokens'),
                     bytes_before=before, bytes_after=gotchas.stat().st_size)
        if a.compact:
            learn['compact'] = compact(gotchas, out)
        shutil.copyfile(gotchas, out / 'gotchas-after.txt')
    proposed = any(x.get('ok') for x in rows if 'round' in x)
    published = any(x.get('publish_exit') == 0 for x in rows)
    passed = proposed and (a.offline or published)
    rounds = [x for x in rows if 'round' in x]
    return dict(task=task, rid=rid, passed=passed, proposed=proposed, published=published, rounds=len(rounds), reasks=max(len(rounds) - 1, 0),
                tokens=sum(x.get('tokens') or 0 for x in rounds), review_tokens=sum(x.get('review_tokens') or 0 for x in rounds),
                secs=round(time.time() - t0, 1), stop=stop, rows=rows, learn=learn)


def compact(gotchas, out):
    """在暫存 node 上壓 gotchas（本機摘要、不打 AI），≤2 KiB；不碰學徒 node 的 compact 設定。"""
    with tempfile.TemporaryDirectory() as tmp:
        n = Path(tmp)
        shutil.copyfile(gotchas, n / 'gotchas.md')
        (n / 'compact.json').write_text(json.dumps({'files': ['gotchas.md'], 'max_bytes': 2048, 'keep_recent': 3, 'llm': None}))
        p = subprocess.run(['python3', str(COMPACT), 'now', str(n)], capture_output=True, text=True)
        (out / 'compact.txt').write_text(p.stdout + p.stderr)
        shutil.copyfile(n / 'gotchas.md', gotchas)
    size = gotchas.stat().st_size
    return dict(exit=p.returncode, bytes=size, over_2k=size > 2048)   # max_bytes 是觸發門檻不是上限，超了照記


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('variant', choices=['A', 'B'])
    ap.add_argument('outdir')
    ap.add_argument('--rep', type=int, default=1)
    ap.add_argument('--tasks', default=','.join(TASKS))
    ap.add_argument('--model', default='chatgpt-gpt-6-sol-high')
    ap.add_argument('--review', default='chatgpt-gpt-6-astra-high')
    ap.add_argument('--max-calls', type=int, default=200)
    ap.add_argument('--calls')
    ap.add_argument('--compact', action='store_true')
    ap.add_argument('--offline', action='store_true')
    ap.add_argument('--repo', default=str(P.parent), help='publish 建 apprentice/ 分支的 repo（預設本 repo 根）')
    a = ap.parse_args()
    out = Path(a.outdir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    a.calls = Path(a.calls).resolve() if a.calls else out.parent / 'calls.jsonl'
    if not a.offline:
        # 同 rid 重跑會讓 metrics 把新舊呼叫加在一起 → 拒跑；換 --rep。
        used = [t for t in a.tasks.split(',') if (out / 'summary.json').exists()
                or any(Path('llmcall').glob(f'*/{t}{a.variant}{a.rep}-r*'))]
        if used:
            print(f'drive3: rid 已用過（{a.variant}{a.rep}：{used}），換 --rep', file=sys.stderr)
            return 2
    gotchas = None
    if a.variant == 'A':
        gotchas = out / 'gotchas.txt'
        shutil.copyfile(BASE_GOTCHAS, gotchas)
    results, stop, streak = [], None, [0]
    for i, task in enumerate(a.tasks.split(','), 1):
        res = do_task(a, task, f'{task}{a.variant}{a.rep}', out / f'{i}-{task}', gotchas, i > 1, streak)
        res['order'] = i
        results.append(res)
        if res['stop']:
            stop = res['stop']
            break
    (out / 'summary.json').write_text(json.dumps(dict(variant=a.variant, rep=a.rep, model=a.model, review=a.review,
        offline=a.offline, compact=a.compact, stop=stop, calls_total=calls_used(a.calls), results=results),
        ensure_ascii=False, indent=1))
    print(json.dumps(dict(variant=a.variant, rep=a.rep, stop=stop,
                          passed=[r['passed'] for r in results], reasks=[r['reasks'] for r in results]), ensure_ascii=False))
    return 5 if stop == 'proxy' else 0


if __name__ == '__main__':
    sys.exit(main())
