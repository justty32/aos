"""讀 run.py 的證據資料夾（含 house.tar.gz），印燈號要的數字，寫 summary.json 與 calls.csv。

python3 -B proto7-2/modules/up/examples/longtask/analyze.py OUT
只讀 OUT，解壓到暫存資料夾，不動原檔。
"""
import csv
import json
from pathlib import Path
import re
import sys
import tarfile
import tempfile

TOP = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(TOP / 'modules/mail'))
from aos7_mail import letter  # noqa: E402


def main():
    out = Path(sys.argv[1]).resolve()
    tmp = Path(tempfile.mkdtemp(prefix='aos-longtask-an.'))
    with tarfile.open(out / 'house.tar.gz') as tar:
        tar.extractall(tmp, filter=lambda m, p: None if m.issym() else tarfile.data_filter(m, p))
    house = tmp / 'house'
    node = house / 'bob'
    sent = json.loads((out / 'sent.json').read_text())
    num = {s['id']: s['n'] for s in sent}
    # 每次呼叫
    calls = []
    for r in sorted(node.glob('llmcall/*/*/receipt.json'), key=lambda p: json.loads(p.read_text())['settle']['at']):
        j = json.loads(r.read_text())
        cid = j['call_id']
        base = re.sub(r'-s\d+$', '', cid)
        step = int(re.search(r'-s(\d+)$', cid)[1]) if re.search(r'-s(\d+)$', cid) else 1
        u = j.get('usage') or {}
        calls.append(dict(letter=num.get(base, '?'), step=step, call=cid, at=j['settle']['at'], outcome=j['outcome'],
                          prompt=u.get('prompt_tokens'), completion=u.get('completion_tokens'), total=u.get('total_tokens'),
                          kind=(j.get('text') or '').lstrip()[:3]))
    with (out / 'calls.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(calls[0]))
        w.writeheader()
        w.writerows(calls)
    # 每回合 STATE
    state = [s for p in sorted((node / 'wf/handoffs').glob('*/STATE.md')) for s in p.read_text().splitlines() if s.startswith('- ')]
    dup = len(state) - len(set(re.sub(r'^- \d\d:\d\d ', '', s) for s in state))
    # 回信
    replies = []
    for p in (house / 'you').rglob('*.md'):
        try:
            l = letter(p)
        except Exception:
            continue
        if l.get('re'):
            replies.append(dict(n=num.get(l['re'], '?'), status=l['status'], title=l['title'], at=l['at'],
                                body=l.get('body', '')))
    replies.sort(key=lambda r: r['at'])
    (out / 'replies.md').write_text(''.join(f"\n## {r['n']} {r['status']}：{r['title']}\n\n{r['body'].strip()}\n" for r in replies),
                                    encoding='utf-8')
    by = {}
    for r in replies:
        by[r['status']] = by.get(r['status'], 0) + 1
    # compact
    clog = [json.loads(s) for s in (node / 'compact/log.jsonl').read_text().splitlines()] if (node / 'compact/log.jsonl').exists() else []
    # skill pick
    picks = [json.loads(s) for s in (node / 'skills/.pick/log.jsonl').read_text().splitlines()] if (node / 'skills/.pick/log.jsonl').exists() else []
    tl = [json.loads(s) for s in (out / 'timeline.jsonl').read_text().splitlines()]
    opens = [t['open'] for t in tl]
    prompts = [c['prompt'] for c in calls if c['prompt']]
    l01 = [c['prompt'] for c in calls if c['letter'] == '01' and c['prompt']]
    summary = dict(
        calls=len(calls), rounds_with_ai=len(calls), by_status=by,
        state_lines=len(state), state_dup=dup,
        open_max=max(opens), open_end=opens[-1], open_curve=[(t['t'], t['open']) for t in tl if True][::1],
        journal_curve=[(t['t'], t['journal']) for t in tl],
        compact=clog, picks=[dict(q=p['q'][:40], picked=p['picked'], via=p['via']) for p in picks],
        prompt_tokens=dict(min=min(prompts), max=max(prompts), mean=round(sum(prompts) / len(prompts)), l01=l01),
        tokens_total=sum(c['total'] or 0 for c in calls),
        kill=json.loads((out / 'kill.json').read_text()) if (out / 'kill.json').exists() else None,
        tmp=str(tmp))
    (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in summary.items() if k not in ('open_curve', 'journal_curve')}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
