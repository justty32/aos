"""Run isolated function or agent cases and summarize repeated measurements."""
import contextlib
import datetime
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import time
import uuid

import observed
from compare import compare
from ledger import add_costs, fold


@contextlib.contextmanager
def environment(**values):
    old = {key: os.environ.get(key) for key in values}
    os.environ.update({key: str(value) for key, value in values.items()})
    try:
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def median_cost(costs):
    keys = set().union(*(cost.keys() for cost in costs))
    return {key: median_cost([cost.get(key, {}) for cost in costs]) if
            any(isinstance(cost.get(key), dict) for cost in costs) else
            statistics.median(cost.get(key, 0) for cost in costs) for key in keys}


def agent_run(target, payload, ws, stack, defs, timeout=60):
    name = 'measure-' + uuid.uuid4().hex
    def ctl(*args, data=None):
        return subprocess.run(['aos-agent', *map(str, args)], input=data,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    added = False
    started = time.monotonic_ns()
    try:
        result = ctl('ctl', 'add', '--name', name, '--ws', ws, '--stack', stack, target)
        if result.returncode:
            return result.returncode, result.stdout, None, None
        added = True
        result = ctl('say', '--target', name, '-', data=payload)
        if result.returncode == 0:
            result = ctl('listen', '--target', name, '--timeout-s', timeout)
        stopped = ctl('ctl', 'stop', '--target', name)
        tree, cost = fold(stack, defs, target=target,
                          elapsed_ms=(time.monotonic_ns() - started) / 1_000_000)
        return result.returncode or stopped.returncode, result.stdout, tree, cost
    finally:
        if added:
            removed = ctl('ctl', 'rm', '--yes', name)
            if removed.returncode:
                raise ValueError('cannot remove measured agent (exit code %s)' % removed.returncode)


def run_case(case, defs, repeat, root, override=None):
    run = json.loads((case / 'run.json').read_text())
    if not isinstance(run, dict) or sum(key in run for key in ('exec', 'agent')) != 1:
        raise ValueError('run.json must declare exactly one exec or agent target')
    kind = 'exec' if 'exec' in run else 'agent'
    if not isinstance(run[kind], str) or not isinstance(run.get('stdin' if kind == 'exec' else 'say'), str):
        raise ValueError('run target and input filename must be strings')
    target = (defs / run[kind]).resolve()
    input_path = case / run['stdin' if kind == 'exec' else 'say']
    timeout = run.get('timeout_s', 60)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('timeout_s must be a positive finite number')
    payload = input_path.read_bytes()
    check = json.loads((case / 'check.json').read_text()) if (case / 'check.json').exists() else {}
    if not isinstance(check, dict) or override is not None and not isinstance(override, dict):
        raise ValueError('check must be an object')
    check.update(override or {})
    if check.get('compare') is not None and not isinstance(check['compare'], str):
        raise ValueError('compare must be a string')
    threshold = check.get('min_score', 1.0)
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not 0 <= threshold <= 1:
        raise ValueError('min_score must be between 0 and 1')
    samples, workspaces, checks = [], [], []
    size = len(payload) + sum(p.stat().st_size for p in (case / 'ws').rglob('*') if p.is_file())
    for index in range(repeat):
        number = index
        while (root / 'runs' / str(number)).exists():
            number += 1
        folder = root / 'runs' / str(number)
        folder.mkdir(parents=True, exist_ok=False)
        ws, stack = folder / 'ws', folder / 'stack'
        shutil.copytree(case / 'ws', ws) if (case / 'ws').exists() else ws.mkdir()
        stack.mkdir()
        started = time.monotonic_ns()
        with environment(AOS_WS=ws, AOS_STACK=stack):
            if kind == 'exec':
                code, out, _ = observed.call('target', target, payload, stack=stack)
                tree, cost = fold(stack / 'tools/target', defs, target=target,
                                  elapsed_ms=(time.monotonic_ns() - started) / 1_000_000)
            else:
                code, out, tree, cost = agent_run(target, payload, ws, stack, defs, timeout)
                if tree is None:
                    tree, cost = fold(stack, defs, target=target)
        tree['in_bytes'] = len(payload)
        (ws / 'stdout.json').write_bytes(out)
        workspaces.append(ws)
        expect = case / 'expect' if (case / 'expect').is_dir() else workspaces[0]
        with environment(AOS_WS=folder, AOS_STACK=stack):
            result = compare(expect, ws, case, check, folder / 'check', defs)
        result['pass'] = code == 0 and result.get('code', 0) == 0 and result['score'] >= threshold
        samples.append({'cost': cost, 'tree': tree, 'check': result, 'code': code, 'in_bytes': len(payload)})
        checks.append(result)
    output = {'case': str(case), 'defs': str(defs), 'repeat': repeat,
              'size_bytes': size, 'cost': median_cost([s['cost'] for s in samples]),
              'tree': samples[0]['tree'], 'samples': samples,
              'check': {'pass': all(c['pass'] for c in checks),
                        'scores': [c['score'] for c in checks],
                        'diff': sorted(set(d for c in checks for d in c.get('diff', []))),
                        'cost': add_costs(c['cost'] for c in checks)},
              'measured_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')}
    if repeat >= 2:
        comparisons = []
        for index, ws in enumerate(workspaces[1:], 1):
            with environment(AOS_WS=ws.parent):
                comparisons.append(compare(workspaces[0], ws, case, check, ws.parent / 'consistency', defs))
        output['consistency'] = {'scores': [c['score'] for c in comparisons],
                                 'pass': all(c.get('code', 0) == 0 and c['score'] >= threshold for c in comparisons)}
        output['check']['cost'] = add_costs([output['check']['cost'], *(c['cost'] for c in comparisons)])
    return output


def measure(arguments, stack):
    case, defs = Path(arguments['case']).resolve(), Path(arguments['defs']).resolve()
    repeat = arguments.get('repeat', 1)
    if type(repeat) is not int or repeat < 1:
        raise ValueError('repeat must be a positive integer')
    root = Path(stack)
    if (case / 'run.json').exists():
        return run_case(case, defs, repeat, root, arguments.get('check'))
    cases = sorted(p for p in case.iterdir() if p.is_dir() and (p / 'run.json').is_file())
    if not cases:
        raise ValueError('case must contain run.json or child cases')
    results = [run_case(p, defs, repeat, root / 'cases' / p.name, arguments.get('check')) for p in cases]
    samples = []
    for index in range(repeat):
        children = [r['samples'][index]['tree'] for r in results]
        cost = add_costs(r['samples'][index]['cost'] for r in results)
        tree_cost = add_costs([{'time_ms': sum(c['cost']['time_ms'] for c in children)}])
        tree = {'def': str(case), 'kind': 'script', 'counter_calls': 1,
                'cost': tree_cost, 'children': children, 'prompt_tokens_median': None}
        samples.append({'cost': cost, 'tree': tree, 'in_bytes': sum(r['samples'][index]['in_bytes'] for r in results),
                        'code': next((r['samples'][index]['code'] for r in results if r['samples'][index]['code']), 0),
                        'check': {'pass': all(r['samples'][index]['check']['pass'] for r in results),
                                  'scores': [r['samples'][index]['check']['score'] for r in results]}})
    output = {'case': str(case), 'defs': str(defs), 'repeat': repeat, 'cases': results,
              'size_bytes': sum(r['size_bytes'] for r in results),
              'samples': samples, 'tree': samples[0]['tree'],
              'cost': median_cost([s['cost'] for s in samples]),
              'measured_at': results[0]['measured_at'],
              'check': {'pass': all(r['check']['pass'] for r in results),
                        'scores': [score for r in results for score in r['check']['scores']],
                        'diff': [Path(r['case']).name + '/' + d for r in results for d in r['check']['diff']],
                        'cost': add_costs(r['check']['cost'] for r in results)}}
    if repeat >= 2:
        output['consistency'] = {'scores': [statistics.mean(r['consistency']['scores'][i] for r in results) for i in range(repeat - 1)],
                                 'pass': all(r['consistency']['pass'] for r in results)}
    return output
