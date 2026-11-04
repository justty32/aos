#!/usr/bin/env python3
"""讀各組 summary.json，印 A／B 對照表。用法：compare4.py DIR...（每個 DIR 是一組的 OUTDIR）。
沒過的題：輪數照實際用掉的（＝上限）。token＝學徒 propose；審查、learn 另列。"""
import json, sys
from pathlib import Path
from statistics import mean

rows = [json.loads((Path(d) / 'summary.json').read_text()) for d in sys.argv[1:]]
by = {}
for s in rows:
    for r in s['results']:
        by.setdefault((s['variant'], r['order'], r['task']), []).append(r)
print('| 組 | 題 | 次數 | 通過 | 平均輪數 | ①擋 | ②擋 | ③擋 | 學徒 token 平均 | 審查 token 平均 | 帶技能 |')
print('|---|---|---|---|---|---|---|---|---|---|---|')
for (v, o, t), rs in sorted(by.items()):
    print(f"| {v} | {o} {t} | {len(rs)} | {sum(r['passed'] for r in rs)}/{len(rs)} | {mean(r['rounds'] for r in rs):.2f} | "
          f"{sum(r['fails']['1'] for r in rs)} | {sum(r['fails']['2'] for r in rs)} | {sum(r['fails']['3'] for r in rs)} | "
          f"{mean(r['tokens'] for r in rs):,.0f} | {mean(r['review_tokens'] for r in rs):,.0f} | "
          f"{sum(1 for r in rs if r.get('skill_in_prompt'))}/{len(rs)} |")
print()
print('| 組 | 題 2＋3 通過 | 題 2＋3 輪數合計（每次平均） | 題 2＋3 三關失敗（每次平均） | 題 2＋3 學徒 token（每次平均） | learn token（每次平均） | 全部 token（每次平均） |')
print('|---|---|---|---|---|---|---|')
for v in sorted({s['variant'] for s in rows}):
    ss = [s for s in rows if s['variant'] == v]
    late = [[r for r in s['results'] if r['order'] >= 2] for s in ss]
    fails = lambda r: sum(r['fails'].values())
    learn = [sum(((r.get('learn') or {}).get('tokens') or 0) for r in s['results']) for s in ss]
    total = [sum(r['tokens'] + r['review_tokens'] + (((r.get('learn') or {}).get('tokens')) or 0) for r in s['results']) for s in ss]
    print(f"| {v} | {sum(r['passed'] for l in late for r in l)}/{sum(len(l) for l in late)} | "
          f"{mean(sum(r['rounds'] for r in l) for l in late):.2f} | {mean(sum(fails(r) for r in l) for l in late):.2f} | "
          f"{mean(sum(r['tokens'] for r in l) for l in late):,.0f} | {mean(learn):,.0f} | {mean(total):,.0f} |")
