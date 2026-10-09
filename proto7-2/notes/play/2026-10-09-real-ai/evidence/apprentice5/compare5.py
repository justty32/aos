#!/usr/bin/env python3
"""讀各組 summary.json，印 A／B 對照表。用法：compare5.py DIR...（每個 DIR 是一組的 OUTDIR）。
沒過的題：輪數照實際用掉的（＝上限）。token＝學徒 propose；審查、learn 另列。
雜訊＝題 1（兩組條件相同）A、B 平均輪數的差；第 2 題起的差要大於它。"""
import json, sys
from pathlib import Path
from statistics import mean, pstdev

rows = [json.loads((Path(d) / 'summary.json').read_text()) for d in sys.argv[1:]]
by = {}
for s in rows:
    for r in s['results']:
        by.setdefault((s['variant'], r['order'], r['task']), []).append(r)
H = ('done', 'dot', 'teams')
print('| 組 | 題 | 次數 | 通過 | 平均輪數 | 一次過 | ①擋 | ②擋 | ③擋 | 慣例命中 done/dot/teams | 學徒 token 平均 | 審查 token 平均 | 帶技能 |')
print('|---|---|---|---|---|---|---|---|---|---|---|---|---|')
for (v, o, t), rs in sorted(by.items()):
    hid = '/'.join(str(sum(r['hidden'][k] for r in rs)) for k in H)
    print(f"| {v} | {o} {t} | {len(rs)} | {sum(r['passed'] for r in rs)}/{len(rs)} | {mean(r['rounds'] for r in rs):.2f} | "
          f"{sum(1 for r in rs if r['passed'] and r['rounds'] == 1)}/{len(rs)} | "
          f"{sum(r['fails']['1'] for r in rs)} | {sum(r['fails']['2'] for r in rs)} | {sum(r['fails']['3'] for r in rs)} | {hid} | "
          f"{mean(r['tokens'] for r in rs):,.0f} | {mean(r['review_tokens'] for r in rs):,.0f} | "
          f"{sum(1 for r in rs if r.get('skill_in_prompt'))}/{len(rs)} |")
print()
print('| 組 | 次數 | 題 1 平均輪數 | 題 2～4 通過 | 題 2～4 一次過 | 題 2～4 每題平均輪數（±標準差） | 題 2～4 三關失敗（每次） | 題 2～4 慣例命中（每次） | 題 2～4 學徒 token（每次） | learn token（每次） | 全部 token（每次） |')
print('|---|---|---|---|---|---|---|---|---|---|---|')
for v in sorted({s['variant'] for s in rows}):
    ss = [s for s in rows if s['variant'] == v]
    first = [r for s in ss for r in s['results'] if r['order'] == 1]
    late = [[r for r in s['results'] if r['order'] >= 2] for s in ss]
    flat = [r for l in late for r in l]
    fails = lambda r: sum(r['fails'].values())
    learn = [sum(((r.get('learn') or {}).get('tokens') or 0) for r in s['results']) for s in ss]
    total = [sum(r['tokens'] + r['review_tokens'] + (((r.get('learn') or {}).get('tokens')) or 0) for r in s['results']) for s in ss]
    print(f"| {v} | {len(ss)} | {mean(r['rounds'] for r in first):.2f} | {sum(r['passed'] for r in flat)}/{len(flat)} | "
          f"{sum(1 for r in flat if r['passed'] and r['rounds'] == 1)}/{len(flat)} | "
          f"{mean(r['rounds'] for r in flat):.2f}（±{pstdev([r['rounds'] for r in flat]):.2f}） | {mean(sum(fails(r) for r in l) for l in late):.2f} | "
          f"{mean(sum(sum(r['hidden'].values()) for r in l) for l in late):.2f} | "
          f"{mean(sum(r['tokens'] for r in l) for l in late):,.0f} | {mean(learn):,.0f} | {mean(total):,.0f} |")
