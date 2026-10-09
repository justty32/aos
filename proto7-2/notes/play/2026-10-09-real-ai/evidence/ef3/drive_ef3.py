#!/usr/bin/env python3
"""EF3 量測：固定模型 vs `--llm`（不給模型＝先便宜後升級）。
csv MODEL N OUTDIR      跑 N 次 examples/llm-request/run.sh（R1 同題 csv1，一整圈到 close）
aos MODE EXDIR OUTDIR   三題（EF3_TASKS 可只跑幾題）（gap／runs／audit，S3 的需求）各一單：MODE=fixed:<模型>（被拒帶 feedback 重問，≤3 輪，同 A5 drive）或 auto
最後一行印 rows 的 JSON；每單的 rounds（模型、token、why）都存檔。"""
import json, os, subprocess, sys, tempfile, time
from pathlib import Path

P = Path(__file__).resolve().parents[5]  # proto7-2/
AUTHOR = P / 'packs/author/bin/aos7-author'
RUN = P / 'packs/author/examples/llm-request/run.sh'
BUDGET = P / 'packs/budget/bin/aos7-budget'


def csv(model, n, outdir):
    rows = []
    for i in range(1, n + 1):
        out = Path(outdir, '%s-r%d' % (model, i))
        p = subprocess.run(['bash', str(RUN), model, str(out)], capture_output=True, text=True)
        prop = json.loads((out / 'propose.json').read_text() or '{}')
        summ = json.loads((out / 'summary.json').read_text())
        rounds = prop.get('rounds') or [dict(model=model, why=prop.get('why'), usage=(prop.get('llm') or {}).get('usage'))]
        rows.append(dict(i=i, exit=p.returncode, models=[r['model'] for r in rounds],
                         tokens=sum((r.get('usage') or {}).get('total_tokens') or 0 for r in rounds),
                         secs=summ['llm_seconds'], answer_ok=summ['answer_ok'], closed=summ['closed']))
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
    return rows


def node():
    root = Path(tempfile.mkdtemp(prefix='aos7-ef3-'))
    (root / 'llm/.aos').mkdir(parents=True)
    (root / 'llm/budget/llm').mkdir(parents=True)
    (root / 'llm/.aos/round.json').write_text(json.dumps({'round': 5, 'open': False}))
    (root / 'llm/budget/llm/grant.json').write_text(json.dumps({
        'v': 1, 'grant': 'ef3', 'budget': 'llm', 'holder': 'author', 'resource': 'llm.tokens',
        'gateway': 'llm.litellm', 'amount': 100000000, 'clock': 'completed_tock', 'from': 0,
        'until': 1000000, 'delegate': False}))
    subprocess.run(['python3', str(BUDGET), 'init', 'budget/llm'], cwd=root / 'llm', check=True, capture_output=True)
    ledger = subprocess.Popen(['python3', str(BUDGET), 'ledger', 'budget/llm'], cwd=root / 'llm',
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    while not (root / 'llm/budget/llm/ledger.lock').exists():
        time.sleep(.1)
    (root / 'work').mkdir()
    return root, ledger


def propose(req, cwd, out, extra):
    argv = ['python3', str(AUTHOR), 'propose', str(req), '--budget', '../llm/budget/llm', '--deadline', '600',
            '--ref', 'main', '--no-scope', '--context', str(P / 'tests/run_all.py')] + extra
    t = time.time()
    p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
    secs = round(time.time() - t, 3)
    out.write_text(p.stdout)
    if p.stderr.strip():
        Path(str(out) + '.stderr').write_text(p.stderr)
    try:
        return json.loads(p.stdout), secs
    except ValueError:
        return {'ok': False}, secs


def aos(mode, exdir, outdir):
    rows = []
    for task in os.environ.get('EF3_TASKS', 'gap runs audit').split():
        req = Path(exdir, 'aos-tool-' + task, 'request.json')
        out = Path(outdir, task).resolve()  # --out 相對 work node，要絕對路徑
        out.mkdir(parents=True, exist_ok=True)
        root, ledger = node()
        try:
            stamp = str(int(time.time()))
            if mode == 'auto':
                doc, secs = propose(req, root / 'work', out / 'propose.json', ['--llm', '--call', task + '-auto-' + stamp])
                rounds = [dict(model=r['model'], why=r['why'], tokens=(r.get('usage') or {}).get('total_tokens')) for r in doc.get('rounds', [])]
                total = secs
            else:
                model, rounds, total, prev = mode.split(':', 1)[1], [], 0, []
                for r in (1, 2, 3):
                    cand = out / ('cand-r%d.json' % r)
                    doc, secs = propose(req, root / 'work', out / ('propose-r%d.json' % r),
                                        ['--llm', model, '--out', str(cand), '--call', '%s-fixed-r%d-%s' % (task, r, stamp)] + prev)
                    total += secs
                    rounds.append(dict(model=model, why=doc.get('why'), tokens=((doc.get('llm') or {}).get('usage') or {}).get('total_tokens')))
                    if doc.get('ok') or not cand.exists() or not isinstance(doc.get('check'), dict):
                        break
                    fb = out / ('feedback-r%d.json' % r)
                    fb.write_text(json.dumps(doc['check'], ensure_ascii=False))
                    prev = ['--previous', str(cand), '--feedback', str(fb)]
            rows.append(dict(task=task, ok=bool(doc.get('ok')), rounds=rounds, secs=round(total, 3),
                             tokens=sum(r['tokens'] or 0 for r in rounds), root=str(root)))
            print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
        finally:
            ledger.terminate()
    return rows


if __name__ == '__main__':
    cmd = sys.argv[1]
    rows = csv(sys.argv[2], int(sys.argv[3]), sys.argv[4]) if cmd == 'csv' else aos(*sys.argv[2:5])
    Path(sys.argv[-1]).mkdir(parents=True, exist_ok=True)
    Path(sys.argv[-1], 'rows.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    print(json.dumps(rows, ensure_ascii=False))
