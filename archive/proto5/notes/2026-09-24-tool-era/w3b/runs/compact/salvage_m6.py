#!/usr/bin/env python3
"""09-25 收尾：撈 09-24 晚被關機中斷的 M6 重跑（~/tmp/w3b-compact/m6，live.py 1～4 次 sum），不叫模型。

每個跑完壓縮的 agent 家：用同一份 archive 重算機械版（aos_agent_compact.plan，純函式），
跟實際寫進記憶的（模型濃縮或退回的）比：封存摘要 bytes、記憶 token（history_tokens 粗估）；
再列壓縮後兩問的端點 prompt_tokens 與回話。結果一行一個 JSON 印到 stdout（寫進 results-m6.jsonl）。

用法（repo 根目錄）：python3 proto5/notes/2026-09-24-tool-era/w3b/runs/compact/salvage_m6.py [資料夾=~/tmp/w3b-compact/m6]
"""
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[5] / 'proto5' / 'lib'))
import aos_agent_compact  # noqa: E402
from aos_agent_context import history_tokens  # noqa: E402

W = Path(os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else '~/tmp/w3b-compact/m6'))


def jsonl(path):
    return [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines() if l.strip()] if path.exists() else []


def sealed(hist):
    return [m['content'] for m in hist if m['role'] == 'user' and str(m.get('content', '')).startswith('[aos 已封存')]


for home in sorted(p for p in W.iterdir() if p.is_dir() and p.name.startswith('sum-')):
    ev = [e for e in jsonl(home / 'log' / 'events.jsonl') if e.get('ev') == 'compact']
    if not ev:
        print(json.dumps({'run': home.name, 'error': '還沒壓縮就中斷'}, ensure_ascii=False))
        continue
    ev = ev[-1]
    archive = home / ev['archive']
    mech = aos_agent_compact.plan(json.loads(archive.read_text(encoding='utf-8')), keep_rounds=ev['keep_rounds'],
                                  max_tokens=ev['max_tokens'], archive=ev['archive'])['history']
    hist = json.loads((home / 'prompts' / 'history.json').read_text(encoding='utf-8'))
    # 壓縮後記憶＝history 裡到封存段之後、第一問之前那幾則（壓縮後又聊了兩問，要扣掉）
    n_after = ev['after']['count']
    real = hist[:n_after]
    usage = jsonl(home / 'log' / 'usage.jsonl')
    i = next(k for k, u in enumerate(usage) if str(u.get('batch') or '').startswith('compact-summarize'))
    asks = [(u.get('usage') or {}).get('prompt_tokens') for u in usage[i + 1:i + 3]]
    answers = [m['content'] for m in hist[n_after:] if m['role'] == 'assistant' and m.get('content')]
    s = ev['summarize']
    print(json.dumps({
        'run': home.name, 'used_model': s['used'] == 1, 'fallback': s['fallback'],
        'summarize_tokens': [s['prompt_tokens'], s['completion_tokens']], 'summarize_ms': s['ms'],
        'digest_bytes_real': [len(x.encode('utf-8')) for x in sealed(real)],
        'digest_bytes_mech': [len(x.encode('utf-8')) for x in sealed(mech)],
        'memory_tokens_real': history_tokens(real), 'memory_tokens_mech': history_tokens(mech),
        'after_prompt_tokens': asks, 'answers': answers[-2:],
        'ok_lines': bool(answers) and '40' in answers[-2], 'ok_fruit': bool(answers) and '芒果' in answers[-1],
    }, ensure_ascii=False))
