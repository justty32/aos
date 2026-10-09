#!/usr/bin/env python3
"""S3 比較：讀各組 summary.json＋`aos7-metrics job <node> --json`，印 markdown 表與判準結果。

用法：compare3.py EVDIR [--node 學徒node] [--overhead 1644]
EVDIR 底下每個子夾（如 A1、B1、A2…）有 drive3 的 summary.json。
token 以 metrics 為準（author/<rid>＋author-review/<rid>＋author-learn/<rid>）；沒給 --node 就用 drive3 自記的數。
判準（寫死，報告照抄）：
  G0 有效：A、B 都有、rep 集合相同、每組三題齊全且 stop 為空、非 offline、每題學徒 token 有數（metrics）；
         且疑似代理問題 0 次。不成立就不比，結論「量不到」並列原因。
  沒過的題：重問記 3（＝用完 2 次重問仍沒過，比最壞的過關多 1），token 照實（含失敗輪）。
  G1 自我改進（重問）：Σrep[(題1重問−題3重問)_A] − Σrep[(題1重問−題3重問)_B] ≥ 1。
  G2 自我改進（token）：A 的 (題1−題3)/題1 平均 − B 的同值平均 ≥ 0.20；只在 A、B 每個 rep 的題 1、3 都過時才算，否則不適用。
  G3 A 不輸 B：題 2＋3 學徒 token 合計 A ≤ B。
  結論：G0 且（G1 或 G2）＝「有自我改進證據」；G0 不過＝「量不到（原因 proxy）」；其餘＝「沒看到」。
"""
import argparse, json, subprocess, sys
from collections import Counter
from pathlib import Path

P = Path(__file__).resolve().parents[5]
METRICS = P / 'modules/metrics/aos7-metrics'


def flows(node, overhead):
    p = subprocess.run([sys.executable, str(METRICS), 'job', str(node), '--json', '--overhead', str(overhead)],
                       capture_output=True, text=True)
    doc = json.loads(p.stdout)
    return {f['flow']: f for s in doc.get('scopes', []) for f in s.get('flows', [])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('evdir')
    ap.add_argument('--node')
    ap.add_argument('--overhead', type=int, default=1644)
    a = ap.parse_args()
    fl = flows(a.node, a.overhead) if a.node else {}
    # metrics 自 10-09 LT3 起把審查／學習併進 author/<rid> 那件，分項在 parts（按原 logical）
    tok = lambda kind, rid: (((fl.get(f'author/{rid}') or {}).get('parts') or {}).get(f'{kind}/{rid}') or {}).get('used')
    runs = [json.loads(p.read_text()) for p in sorted(Path(a.evdir).glob('*/summary.json'))]
    invalid = []
    print('| 組 | rep | 題 | rid | 過 | 輪 | 重問 | 學徒 token | 審查 token | learn token | 秒 | 擋下（關:規則） |')
    print('|---|---|---|---|---|---|---|---|---|---|---|---|')
    data, blocks, suspects = {}, Counter(), 0
    for run in runs:
        for r in run['results']:
            at = tok('author', r['rid']) if a.node else r['tokens']
            rt = tok('author-review', r['rid']) or r['review_tokens']
            lt = tok('author-learn', r['rid']) or ((r.get('learn') or {}).get('tokens'))
            blk = []
            for row in r['rows']:
                if 'round' in row and not row.get('ok'):
                    for rule in row.get('rules') or ['?']:
                        blocks[(row.get('failed_gate'), rule)] += 1
                        blk.append(f"{row.get('failed_gate')}:{rule}")
                    suspects += bool(row.get('proxy_suspect'))
            key = (run['variant'], run['rep'], r['order'])
            if key in data:
                invalid.append(f'重複 {key}')
            if not at:
                invalid.append(f"{r['rid']} 沒有 token 數" + ('（metrics 找不到 author/' + r['rid'] + '）' if a.node else ''))
            data[key] = dict(reasks=r['reasks'] if r['passed'] else 3, tokens=at or 0, passed=r['passed'])
            print(f"| {run['variant']} | {run['rep']} | {r['order']} {r['task']} | {r['rid']} | {'是' if r['passed'] else '否'} | "
                  f"{r['rounds']} | {r['reasks']} | {at} | {rt} | {lt or '-'} | {r['secs']} | {' '.join(blk) or '-'} |")
    print('\n| 關 | 規則 | 次數 |\n|---|---|---|')
    for (g, rule), n in sorted(blocks.items(), key=lambda x: (str(x[0][0]), x[0][1])):
        print(f'| {g} | {rule} | {n} |')
    reps = lambda v: sorted({k[1] for k in data if k[0] == v})
    for run in runs:
        if run.get('offline'):
            invalid.append(f"{run['variant']}{run['rep']} 是 offline")
        if run.get('stop'):
            invalid.append(f"{run['variant']}{run['rep']} 停在 {run['stop']}")
        if [r['task'] for r in run['results']] != ['gap', 'runs', 'audit']:
            invalid.append(f"{run['variant']}{run['rep']} 題目不齊或順序不對")
    if len({(run.get('model'), run.get('review'), run.get('compact')) for run in runs}) > 1:
        invalid.append('各組的學徒／審查模型或 compact 設定不同')
    if not reps('A') or reps('A') != reps('B'):
        invalid.append(f"A／B rep 不成對：A={reps('A')} B={reps('B')}")
    def drop_reask(v):
        return sum(data[(v, r, 1)]['reasks'] - data[(v, r, 3)]['reasks'] for r in reps(v) if (v, r, 3) in data and (v, r, 1) in data)
    def drop_tok(v):
        if not all(data[k]['passed'] for k in data if k[2] in (1, 3)):
            return None          # 有題 1／3 沒過：失敗的答案變短不算省 token，G2 不適用
        xs = [(data[(v, r, 1)]['tokens'] - data[(v, r, 3)]['tokens']) / data[(v, r, 1)]['tokens']
              for r in reps(v) if (v, r, 3) in data and data[(v, r, 1)]['tokens']]
        return sum(xs) / len(xs) if xs else None
    t23 = lambda v: sum(data[k]['tokens'] or 0 for k in data if k[0] == v and k[2] in (2, 3)) / max(len(reps(v)), 1)
    if suspects:
        invalid.append(f'疑似代理問題 {suspects} 次')
    g0 = not invalid
    da, db = drop_tok('A'), drop_tok('B')
    g1 = drop_reask('A') - drop_reask('B') >= 1
    g2 = da is not None and db is not None and da - db >= 0.20
    g1, g2, g3 = g0 and g1, g0 and g2, g0 and t23('A') <= t23('B')
    verdict = '有自我改進證據' if g0 and (g1 or g2) else ('量不到：' + '；'.join(invalid) if not g0 else '沒看到')
    summary = dict(G0=g0, invalid=invalid, proxy_suspects=suspects, G1=g1, reask_drop_A=drop_reask('A'), reask_drop_B=drop_reask('B'),
                   G2=g2, token_drop_A=da, token_drop_B=db, G3=g3, t23_A=t23('A'), t23_B=t23('B'), verdict=verdict)
    print('\n' + json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
