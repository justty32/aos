#!/usr/bin/env python3
"""A5 學徒一題：propose --llm（學徒）＋--review-llm（審查）→ 不過就帶 feedback 重問（≤2 次）→ 過了 publish 到 apprentice/。
用法：drive.py TASK(usage|diag) MODEL REVIEW_MODEL OUTDIR [--gotchas F]
在學徒 node 下跑（cwd）。"""
import json, os, subprocess, sys, time
from pathlib import Path

P = Path(__file__).resolve().parents[5]  # proto7-2/
AUTHOR = P / 'packs/author/bin/aos7-author'
EX = P / 'packs/author/examples'
TASKS = {
    'usage': (EX / 'aos-tool-usage/request.json', [
        P / 'tests/run_all.py', P / 'packs/prompt/bin/aos7-prompt',
        EX / 'aos-tool-usage/fixture/llmcall/llm/c1/request.json',
        EX / 'aos-tool-usage/fixture/llmcall/llm/c1/raw.json',
        EX / 'aos-tool-usage/fixture/llmcall/llm/c1/receipt.json',
        EX / 'aos-tool-usage/fixture/budget/llm/ledger.json']),
    'diag': (EX / 'aos-module-diag/request.json', [
        P / 'tests/run_all.py', P / 'modules/metrics/aos7-metrics',
        EX / 'aos-module-diag/fixture/llmcall/llm/pendingraw/request.json',
        EX / 'aos-module-diag/fixture/jobs/a_req_89abcdef/frame.json',
        EX / 'aos-module-diag/fixture/budget/busy/ledger.json']),
}


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


def main():
    task, model, rmodel, outdir = sys.argv[1:5]
    gotchas = sys.argv[sys.argv.index('--gotchas') + 1] if '--gotchas' in sys.argv else None
    tag = sys.argv[sys.argv.index('--tag') + 1] if '--tag' in sys.argv else model.split('-')[-2]
    req, ctx = TASKS[task]
    out = Path(outdir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    rows, prev, fb = [], None, None
    for r in (1, 2, 3):
        cand = out / f'cand-r{r}.json'
        argv = ['python3', str(AUTHOR), 'propose', str(req), '--llm', model, '--budget', 'budget/llm',
                '--review-llm', rmodel, '--deadline', '600', '--out', str(cand),
                '--call', f'{task}-{tag}-r{r}-{int(time.time())}']
        for c in ctx:
            argv += ['--context', str(c)]
        if gotchas:
            argv += ['--gotchas', gotchas]
        if prev:
            argv += ['--previous', str(prev), '--feedback', str(fb)]
        code, doc, secs = run(argv, out / f'propose-r{r}.json')
        chk = doc.get('check') or {}
        fb = out / f'feedback-r{r}.json'
        fb.write_text(json.dumps(chk, ensure_ascii=False, indent=1))
        u = (doc.get('llm') or {}).get('usage') or {}
        ru = ((doc.get('review') or {}).get('llm') or {}).get('usage') or {}
        row = dict(round=r, exit=code, ok=doc.get('ok'), failed_gate=chk.get('failed_gate'),
                   rules_failed=(doc.get('rules_check') or {}).get('failed_gate'),
                   tokens=u.get('total_tokens'), review_tokens=ru.get('total_tokens'), secs=secs,
                   job=doc.get('job'), issues=[i for g in (chk.get('gates') or {}).values() for i in (g.get('issues') or [])][:6])
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
        if doc.get('ok'):
            rv = (doc.get('review') or {}).get('path')
            pargv = ['python3', str(AUTHOR), 'publish', str(req), '--candidate', str(cand),
                     '--reviewer', 'file:' + rv if rv else 'rules', '--ref', 'main']
            pc, pd, ps = run(pargv, out / 'publish.json')
            rows.append(dict(publish_exit=pc, branch=pd.get('branch'), commit=pd.get('commit'), dup=pd.get('dup'), secs=ps))
            print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
            break
        if not cand.exists():
            break
        prev = cand
    (out / 'summary.json').write_text(json.dumps(dict(task=task, model=model, review=rmodel, gotchas=gotchas, rows=rows), ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
