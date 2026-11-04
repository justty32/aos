"""Shared deterministic workload; pipeline is a single-process checkpoint baseline."""
import csv
import json
import os
from pathlib import Path
import sys
import time


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(value, sort_keys=True))
    tmp.replace(path)


def event(job, step, kind):
    with (job / 'events.jsonl').open('a') as f:
        f.write(json.dumps({'step': step, 'kind': kind, 'pid': os.getpid()}) + '\n')


def gate(job, step):
    if (job / 'gate-target').exists() and (job / 'gate-target').read_text() == step:
        entered = job / ('entered-' + step)
        if not entered.exists():
            entered.write_text(str(os.getpid()))
            while True:
                time.sleep(.01)


def work(job, step):
    event(job, step, 'start')
    if step == 'convert':
        with (job / 'data.csv').open() as f:
            source = list(csv.DictReader(f))
        rows = []
        for i, row in enumerate(source):
            rows.append(dict(row, amount=float(row['amount'])))
            if i == len(source) // 2:
                gate(job, step)
        save(job / 'out/data.json', {'rows': rows})
    else:
        rows = json.loads((job / 'out/data.json').read_text())['rows']
        by = {}
        for i, row in enumerate(rows):
            item = by.setdefault(row['dept'], {'n': 0, 'sum': 0.0})
            item['n'] += 1
            item['sum'] += row['amount']
            if i == len(rows) // 2:
                gate(job, step)
        for item in by.values():
            item['avg'] = round(item['sum'] / item['n'], 2)
        save(job / 'out/report.json', {'rows': len(rows), 'by_dept': by})
    event(job, step, 'complete')


if __name__ == '__main__':
    mode, location = sys.argv[1:3]
    job = Path(location)
    if mode != 'pipeline':
        work(job, mode)
    else:
        checkpoint = job / 'checkpoint.json'
        state = json.loads(checkpoint.read_text()) if checkpoint.exists() else {'done': [], 'pc': 'convert'}
        for step in ('convert', 'stats'):
            if step in state['done']:
                continue
            state['pc'] = step
            save(checkpoint, state)
            work(job, step)
            state['done'].append(step)
            save(checkpoint, state)
        state['pc'] = 'ended'
        save(checkpoint, state)
