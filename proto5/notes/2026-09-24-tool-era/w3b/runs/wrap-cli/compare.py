#!/usr/bin/env python3
"""wrap-cli 機械版 vs 模型版：同一批 fixture 跟人手寫的標準答案比。

跑法（在 proto5/ 底下）：
    AOS_LLM_CONFIG=/abs/llm.json python3 notes/2026-09-24-tool-era/w3b/runs/wrap-cli/compare.py [--runs 3] [--only a,b]
    --runs 0＝只跑機械版（不叫模型）。
原始結果追加到同資料夾的 results.jsonl（一次一列），最後印一張表。
fixture 與答案：lib/test/fixtures/wrapcli/（answers.json）。模型設定照 AOS_LLM_CONFIG（W3-2 一律 LiteLLM deepseek-chat）。
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
PROTO = HERE.parents[4]
sys.path.insert(0, str(PROTO / 'lib'))

import aos_agent_tools_wrapcli as w  # noqa: E402

FIX = PROTO / 'lib' / 'test' / 'fixtures' / 'wrapcli'


def evidence(key, entry):
    if key == 'csvsum':
        src = (FIX / 'csvsum.py').read_text(encoding='utf-8')
        return 'argparse', src
    return 'help', w.clean_help((FIX / entry['help_file']).read_text(encoding='utf-8'))


def mechanical(mode, text):
    t0 = time.monotonic()
    parsed = w.read_argparse(text, 'csvsum.py') if mode == 'argparse' else w.parse_help(text)
    params, dropped = w.check_params(parsed['params'], text)
    return params, dropped, int((time.monotonic() - t0) * 1000), None


def llm(mode, text, cmd):
    seg = w.argparse_segment(text) if mode == 'argparse' else text
    t0 = time.monotonic()
    _, params, dropped, got = w.llm_table(cmd, mode, seg)
    # argparse：段落的旗標逐字檢查跟整份原始碼一樣（段落是子集）
    return params, dropped, int((time.monotonic() - t0) * 1000), got.get('usage')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', type=int, default=3)
    ap.add_argument('--only')
    a = ap.parse_args()
    answers = json.loads((FIX / 'answers.json').read_text(encoding='utf-8'))
    keys = [k for k in answers if not k.startswith('_')]
    if a.only:
        keys = [k for k in keys if k in a.only.split(',')]
    out = (HERE / 'results.jsonl').open('a', encoding='utf-8')
    rows = []
    for key in keys:
        entry = answers[key]
        mode, text = evidence(key, entry)
        jobs = [('mechanical', 0)] + [('llm', i + 1) for i in range(a.runs)]
        for version, i in jobs:
            try:
                if version == 'mechanical':
                    params, dropped, ms, usage = mechanical(mode, text)
                else:
                    params, dropped, ms, usage = llm(mode, text, entry['cmd'].replace('.py', ''))
                sc = w.score(params, entry['params'])
                err = None
            except Exception as e:  # noqa: BLE001 —— 模型回壞的也要記一列
                params, dropped, ms, usage, sc, err = [], [], 0, None, None, '%s: %s' % (type(e).__name__, e)
            rec = {'time': time.strftime('%Y-%m-%dT%H:%M:%S'), 'fixture': key, 'version': version, 'run': i,
                   'score': sc, 'dropped': [list(d) for d in dropped], 'ms': ms, 'usage': usage, 'error': err,
                   'params': params}
            out.write(json.dumps(rec, ensure_ascii=False) + '\n')
            out.flush()
            rows.append(rec)
    print('| fixture | 版本 | 次 | 答案 | 找對 | 多抓 | 型別對 | 必填對 | choices 對 | 丟掉 | token | 毫秒 |')
    print('|---|---|---|---|---|---|---|---|---|---|---|---|')
    for r in rows:
        s = r['score'] or {}
        u = r['usage'] or {}
        print('| %s | %s | %s | %s | %s | %s | %s | %s | %s | %d | %s | %d |' % (
            r['fixture'], '機械' if r['version'] == 'mechanical' else '模型', r['run'] or '-', s.get('answer', '?'),
            s.get('found', r['error'] or '?'), s.get('extra', '?'), s.get('type_ok', '?'), s.get('required_ok', '?'),
            s.get('choices_ok', '?'), len(r['dropped']), u.get('total_tokens', '-'), r['ms']))


if __name__ == '__main__':
    main()
