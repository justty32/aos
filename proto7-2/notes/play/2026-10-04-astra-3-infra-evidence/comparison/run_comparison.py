"""Run from repo root; only outputs under this evidence directory, workspaces in /tmp."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
TOP = HERE.parents[3]
sys.path.insert(0, str(TOP / 'packs/step/tests'))
from test_step import StepCase, read_json
from csv_worker import save

os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
os.environ.pop('AOS7_TEST_HOOKS', None)
WORKER = str(HERE / 'csv_worker.py')
PY = sys.executable


def wait(pred, timeout=60):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = pred()
        if value:
            return value
        time.sleep(.01)
    raise AssertionError('timeout: ' + str(pred))


def own_processes(root):
    result = []
    wanted = ('AOS7_ROOT=' + str(root)).encode()
    for p in Path('/proc').iterdir():
        if not p.name.isdigit() or int(p.name) == os.getpid():
            continue
        try:
            env_match = wanted in (p / 'environ').read_bytes().split(b'\0')
            command_match = str(root).encode() in (p / 'cmdline').read_bytes().split(b'\0')
            if env_match or command_match:
                result.append(int(p.name))
        except OSError:
            pass
    return result


def clean(case):
    root = case.root
    before = sorted(set(own_processes(root) + [p.pid for p in case.procs]))
    case.doCleanups()
    after = own_processes(root)
    ps = subprocess.run(['ps', '-o', 'pid,ppid,pgid,stat,args', '-p', ','.join(map(str, before))], capture_output=True, text=True)
    return {'root': root, 'root_removed': not Path(root).exists(), 'tracked_before_cleanup': before,
            'matching_after_cleanup': after, 'ps_after': ps.stdout.strip()}


def data(job, kill):
    job.mkdir(parents=True, exist_ok=True)
    with (job / 'data.csv').open('w') as f:
        f.write('name,dept,amount\n')
        for n in range(10000):
            f.write(f'p{n},d{n % 4},{n % 101}\n')
    if kill:
        (job / 'gate-target').write_text(kill)


def tally(job):
    records = [json.loads(line) for line in (job / 'events.jsonl').read_text().splitlines()]
    return dict(Counter(r['step'] for r in records if r['kind'] == 'start'))


def step_case(kill=None, auto=False):
    case = StepCase()
    case.setUp()
    result = {'implementation': 'step-auto' if auto else 'step-default', 'kill': kill or 'none'}
    try:
        node = case.mknode('a', interval_ms=30)
        job = Path(node) / 'jobs/csv'
        data(job, kill)
        table = {'job': 'csv', 'start': 'convert', 'steps': {
            step: {'run': [PY, WORKER, step, '${job}'], 'finite': True, 'idempotent': True,
                   'expect': ['${out}/' + ('data.json' if step == 'convert' else 'report.json')],
                   'ok': 'stats' if step == 'convert' else 'done', 'on_unknown': 'resend' if auto else 'stop'}
            for step in ('convert', 'stats')}}
        table['steps']['done'] = {'end': 'ok'}
        case.set_tasks(node, [case.install(node, 'csv', table)])
        start = time.monotonic()
        case.start_daemon(register=['a'])
        result['recovery_actions'] = 0
        if kill:
            wait(lambda: (job / ('entered-' + kill)).exists())
            pending = case.frame(node, 'csv')['pending']
            pid = case.wait_pid(node, 'step-csv-' + kill)
            result['injection'] = {'pgid': pid['pgid'], 'run': pid['run'], 'pending': pending,
                                   'point': '5001 of 10000 rows processed; output not published'}
            os.killpg(pid['pgid'], signal.SIGKILL)
            if not auto:
                wait(lambda: case.frame(node, 'csv').get('phase') == 'halted')
                result['halt_snapshot'] = case.frame(node, 'csv')
                result['diagnostic_files'] = ['frame.json', 'results/', '.aos/tasks/step-csv-' + kill + '/exit.json']
                rc = case.step_cli(node, 'resume', 'jobs/csv', '--resend')
                assert rc.returncode == 0, rc.stderr
                result['recovery_actions'] = 1
        wait(lambda: case.frame(node, 'csv').get('phase') == 'ended')
        result.update(elapsed_s=round(time.monotonic() - start, 3), starts=tally(job),
                      final_frame=case.frame(node, 'csv'), report=read_json(str(job / 'out/report.json')))
    finally:
        result['cleanup'] = clean(case)
    return result


def baseline(kill=None):
    result = {'implementation': 'python-checkpoint', 'kill': kill or 'none', 'recovery_actions': 0}
    p = None
    with tempfile.TemporaryDirectory(prefix='astra3-python-') as root:
        job = Path(root)
        data(job, kill)
        try:
            start = time.monotonic()
            p = subprocess.Popen([PY, WORKER, 'pipeline', root], start_new_session=True)
            first_pid = p.pid
            if kill:
                wait(lambda: (job / ('entered-' + kill)).exists())
                result['halt_snapshot'] = json.loads((job / 'checkpoint.json').read_text())
                result['diagnostic_files'] = ['checkpoint.json', 'out/data.json (only stats kill)']
                os.killpg(p.pid, signal.SIGKILL)
                p.wait(10)
                p = subprocess.Popen([PY, WORKER, 'pipeline', root], start_new_session=True)
                result['recovery_actions'] = 1
            assert p.wait(60) == 0
            result.update(elapsed_s=round(time.monotonic() - start, 3), starts=tally(job),
                          checkpoint=json.loads((job / 'checkpoint.json').read_text()),
                          report=json.loads((job / 'out/report.json').read_text()))
        finally:
            if p and p.poll() is None:
                os.killpg(p.pid, signal.SIGKILL)
                p.wait(10)
        ps = subprocess.run(['ps', '-o', 'pid,ppid,pgid,stat,args', '-p', f'{first_pid},{p.pid}'], capture_output=True, text=True)
        result['cleanup'] = {'pids': [first_pid, p.pid], 'ps_after': ps.stdout.strip()}
    result['cleanup']['root_removed'] = not job.exists()
    return result


def inventory(root):
    files = []
    for path in Path(root).rglob('*'):
        try:
            if path.is_file():
                files.append((str(path.relative_to(root)), path.stat().st_size))
        except FileNotFoundError:
            pass
    return {'files': len(files), 'bytes': sum(n for _, n in files)}


def longrun(rounds):
    case = StepCase()
    case.setUp()
    result = {'target_rounds': rounds, 'samples': [], 'completed': [], 'errors': []}
    try:
        node = case.mknode('a', interval_ms=20)
        job = Path(node) / 'jobs/csv'
        case.set_tasks(node, [case.install(node, 'csv', example='csv', restart_on_end=True)])
        case.start_daemon(register=['a'])
        start = time.monotonic()
        seen, last_sample = set(), -1
        while time.monotonic() - start < 360:
            frame = case.frame(node, 'csv')
            rnd = case.last_round(node).get('round', 0)
            if rnd != last_sample:
                sample = {'round': rnd, 'elapsed_s': round(time.monotonic() - start, 3),
                          'phase': frame.get('phase'), 'inst': frame.get('inst'),
                          'job': inventory(job), 'node': inventory(node), 'root': inventory(case.root)}
                result['samples'].append(sample)
                last_sample = rnd
            if frame.get('phase') == 'halted' or (job / 'error.json').exists():
                result['errors'].append({'frame': frame, 'error': read_json(str(job / 'error.json'))})
                break
            if frame.get('phase') == 'ended' and frame['inst'] not in seen:
                seen.add(frame['inst'])
                report = read_json(str(job / 'out/report.json'))
                snap = {'round': rnd, 'inst': frame['inst'], 'end': frame['end'], 'job': inventory(job),
                        'report_ok': report.get('rows') == 5 and report.get('from') == frame['accepted']['convert']['request'],
                        'tries': list(frame['tries'].values())}
                if case.frame(node, 'csv').get('inst') == frame['inst']:
                    result['completed'].append(snap)
            if rnd >= rounds:
                break
            time.sleep(.01)
        result.update(elapsed_s=round(time.monotonic() - start, 3), final_round=case.last_round(node),
                      final_frame=case.frame(node, 'csv'), status=case.nstat())
        assert last_sample >= rounds, result
        assert not result['errors'], result['errors']
        assert all(v['report_ok'] and v['tries'] == [1, 1] for v in result['completed'])
    finally:
        result['cleanup'] = clean(case)
        save(HERE / 'longrun.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['all', 'comparison', 'longrun'], default='all')
    parser.add_argument('--rounds', type=int, default=450)
    args = parser.parse_args()
    if args.mode in ('all', 'comparison'):
        results = []
        for kind in (None, 'convert', 'stats'):
            for fn in (baseline, step_case):
                results.append(fn(kind))
                print(results[-1]['implementation'], kind, results[-1]['starts'], flush=True)
                save(HERE / 'comparison.json', results)
        for kind in ('convert', 'stats'):
            results.append(step_case(kind, auto=True))
            save(HERE / 'comparison.json', results)
        assert all(r['report'] == results[0]['report'] for r in results)
    if args.mode in ('all', 'longrun'):
        outcome = longrun(args.rounds)
        print('longrun:', outcome['final_round']['round'], 'rounds,', len(outcome['completed']), 'completed', flush=True)
