#!/usr/bin/env python3
"""F1 入口完成前的最小可重跑佈置。"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

TOP = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(TOP / 'lib'))
from aos7_fs import write_json


def setup(node, model='fake', interval_ms=1000):
    node = Path(node).resolve()
    def call(tool, *args):
        p = subprocess.run([sys.executable, str(TOP / tool), *map(str, args)],
                           capture_output=True, text=True, cwd=node, timeout=60)
        if p.returncode:
            raise ValueError(p.stdout + p.stderr)
    node.mkdir(parents=True, exist_ok=True)
    call('modules/wfnode/aos7-wfnode', 'init', node)
    aos = node / '.aos'
    aos.mkdir(exist_ok=True)
    write_json(str(aos / 'timeline.json'), dict(interval_ms=interval_ms))
    budget = node / 'budget/llm'
    budget.mkdir(parents=True, exist_ok=True)
    if not (budget / 'grant.json').exists():
        write_json(str(budget / 'grant.json'), dict(v=1, grant='up-llm', budget='llm', holder='brain',
                   resource='llm.tokens', gateway='llm.fake' if model in (None, 'fake', '') else 'llm.litellm',
                   amount=10000000, clock='completed_tock', **{'from': 0}, until=100000000, delegate=False))
    if not (budget / 'ledger.json').exists():
        call('packs/budget/bin/aos7-budget', 'init', 'budget/llm')
    path = aos / 'tasks.json'
    obj = json.loads(path.read_text()) if path.exists() else {'tasks': []}
    names = {t['name'] for t in obj['tasks']}
    for name, argv in [('budget-llm', ['packs/budget/bin/aos7-budget', 'ledger', 'budget/llm']),
                       ('brain', ['modules/up/aos7_up_brain.py', 'brain', str(node)])]:
        if name not in names:
            obj['tasks'].append(dict(name=name, mode='keep', argv=[sys.executable, str(TOP / argv[0]), *argv[1:]]))
    write_json(str(path), obj)
    if not (aos / 'up.json').exists():
        write_json(str(aos / 'up.json'), dict(model=model, budget='budget/llm', holder='brain'))
    (node.parent / 'you').mkdir(exist_ok=True)
    return node


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('node')
    ap.add_argument('--model', default='fake')
    ap.add_argument('--interval-ms', type=int, default=1000)
    a = ap.parse_args()
    try:
        print(setup(a.node, a.model, a.interval_ms))
    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)
