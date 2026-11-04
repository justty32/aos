#!/usr/bin/env python3
"""wrap-py 描述：機械版（描述＝函式名）vs 模型版（套用提案）裝給 agent，同樣的事各跑 N 次。

先跑 setup.sh（開 daemon＋kernel、做兩個包、兩個樣板家 a-mech／a-llm），再：
    python3 proto5/notes/2026-09-24-tool-era/w3b/runs/wrap-py-describe/run.py [--runs 3]
每次從樣板複製一個新家（記憶是空的），start → say --wait → 讀 history／usage → stop。
結果追加到同資料夾 results.jsonl，最後印表。跑完自己 `aos down`（環境變數同 setup.sh）。
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

HERE = Path(__file__).resolve().parent
PROTO = HERE.parents[4]
W = Path(os.environ.get('W', Path.home() / 'tmp' / 'w3b-wrap'))
ENV = dict(os.environ, PATH='%s:%s' % (PROTO / 'cli', os.environ['PATH']), AOS_DAEMON_HOME=str(W / 'D'),
           AOS_KERNEL_HOME=str(W / 'K'), PYTHONDONTWRITEBYTECODE='1')
TASKS = {
    'lines': ('用工具算 notes.txt 有幾行，只回數字。', 'proc', '7'),
    'words': ('用工具算 notes.txt 有幾個英文單字（word），只回數字。', 'proc2', '43'),
}


def agent(*args, check=True):
    r = subprocess.run(['aos-agent', *args], env=ENV, capture_output=True, text=True, timeout=300)
    if check and r.returncode != 0:
        raise RuntimeError('aos-agent %s: %s %s' % (' '.join(args), r.stdout, r.stderr))
    return r


def one(version, task, i):
    text, want_tool, want = TASKS[task]
    home = W / 'runs' / ('%s-%s-%d' % (version, task, i))
    if home.exists():
        shutil.rmtree(home)
    home.parent.mkdir(exist_ok=True)
    shutil.copytree(W / ('a-' + version), home)
    agent('start', '--target', str(home))
    t0 = time.monotonic()
    r = agent('say', text, '--target', str(home), '--wait', '240', check=False)
    secs = round(time.monotonic() - t0, 1)
    agent('stop', '--target', str(home), check=False)
    history = json.loads((home / 'prompts' / 'history.json').read_text(encoding='utf-8'))
    msgs = history if isinstance(history, list) else history.get('messages', [])
    calls = [c for m in msgs if m.get('role') == 'assistant' for c in (m.get('tool_calls') or [])]
    first = calls[0]['function']['name'] if calls else None
    usage = [json.loads(line) for line in (home / 'log' / 'usage.jsonl').read_text().splitlines() if line.strip()] \
        if (home / 'log' / 'usage.jsonl').exists() else []
    tokens = sum((u.get('usage') or u).get('total_tokens', 0) for u in usage)
    answer = r.stdout.strip()
    return {'version': version, 'task': task, 'run': i, 'first_tool': first, 'first_ok': first == want_tool,
            'tools': [c['function']['name'] for c in calls], 'answer': answer[-200:],
            'answer_ok': answer.strip().rstrip('。.').endswith(want), 'model_calls': len(usage), 'tokens': tokens,
            'secs': secs, 'say_exit': r.returncode}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', type=int, default=3)
    ap.add_argument('--only')
    a = ap.parse_args()
    out = (HERE / 'results.jsonl').open('a', encoding='utf-8')
    rows = []
    for task in TASKS:
        for version in ('mech', 'llm'):
            if a.only and version not in a.only.split(','):
                continue
            for i in range(1, a.runs + 1):
                rec = one(version, task, i)
                rec['time'] = time.strftime('%Y-%m-%dT%H:%M:%S')
                out.write(json.dumps(rec, ensure_ascii=False) + '\n')
                out.flush()
                rows.append(rec)
                print(json.dumps(rec, ensure_ascii=False), flush=True)
    print('| 事 | 版本 | 次 | 第一個工具 | 選對 | 答對 | 用了哪些工具 | 模型次數 | token | 秒 |')
    print('|---|---|---|---|---|---|---|---|---|---|')
    for r in rows:
        print('| %s | %s | %d | %s | %s | %s | %s | %d | %d | %s |' % (
            r['task'], '機械' if r['version'] == 'mech' else '模型', r['run'], r['first_tool'],
            '✔' if r['first_ok'] else '✘', '✔' if r['answer_ok'] else '✘', '、'.join(r['tools']), r['model_calls'],
            r['tokens'], r['secs']))


if __name__ == '__main__':
    main()
