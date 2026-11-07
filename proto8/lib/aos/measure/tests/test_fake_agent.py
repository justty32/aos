# Verify measured fake agents, descendant token totals, and real control cleanup.
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

MEASURE = Path(__file__).resolve().parents[1]
PROTO = MEASURE.parents[2]


def write(path, value):
    path.write_text(json.dumps(value), encoding='utf-8')


def public_records(stack):
    interface = stack / 'interfaces.json'
    if not interface.exists():
        return []
    declared = json.loads(interface.read_text()).get('aos-observed', {})
    if not declared.get('file'):
        return []
    return [json.loads(line) for line in (stack / declared['file']).read_text().splitlines()]


def reachable_records(stack, visited=None):
    """Follow only public tool and child edges; count each declared ledger once."""
    visited = set() if visited is None else visited
    stack = stack.resolve()
    if stack in visited:
        return
    visited.add(stack)
    rows = public_records(stack)
    yield from rows
    for row in rows:
        if row.get('kind') == 'tool':
            for field in ('stack', 'child'):
                if row.get(field):
                    yield from reachable_records(stack / row[field], visited)


def nodes(tree):
    yield tree
    for child in tree['children']:
        yield from nodes(child)


class FakeAgentMeasure(unittest.TestCase):
    def test_repeat_child_cost_and_control_cleanup(self):
        with tempfile.TemporaryDirectory(prefix='aos-measure-fake-', dir='/tmp') as tmp:
            root = Path(tmp)
            daemon_stack, kernel_stack, measure_stack = [root / name for name in ('daemon', 'kernel', 'measure')]
            for stack in (daemon_stack, kernel_stack, measure_stack):
                stack.mkdir()
            defs = root / 'defs'
            defs.mkdir()
            bins = [str(path) for group in ('impls', 'cmd') for path in (PROTO / group).glob('*/bin')]
            env = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}
            env['PATH'] = os.pathsep.join(bins + [env['PATH']])
            env['PYTHONPATH'] = os.pathsep.join([str(PROTO / 'lib'), str(PROTO / 'py')])
            env.update(AOS_STACK=str(daemon_stack), AOS_DAEMON=str(daemon_stack),
                       AOS_LLM_KERNEL=str(kernel_stack), AOS_CD=str(root), AOS_WS=str(root))

            def definition(name, tools):
                target = defs / name
                shutil.copytree(PROTO / 'templates/agent-fsm', target,
                                ignore=shutil.ignore_patterns('tests', '__pycache__'))
                write(target / 'llm.json', {'endpoint': name})
                write(target / 'tools.json', {'tools': tools})
                write(target / 'loop.json', {'exec': 'fsm.json', 'interval_ms': 10,
                                             'ctl': 'ctl.json', 'state': 'state.json'})
                return target

            bash = PROTO / 'lib/base/bash'
            child = definition('child', {'bash': {'path': str(bash)}})
            definition('parent', {'bash': {'path': str(bash)},
                                 'thought': {'path': str(PROTO / 'lib/agent/thought')}})
            definition('single', {})
            # Exercise llm_fake itself, changing only its reported usage at the boundary.
            fake = root / 'fake'
            fake.mkdir()
            wrapper = fake / '_entry'
            wrapper.write_text('#!/usr/bin/env python3\n# Supply nonzero usage around the real fake endpoint.\n'
                'import json, subprocess, sys\n'
                f'r = subprocess.run([sys.executable, {str(PROTO / "lib/base/llm_fake/_entry")!r}], '
                'input=sys.stdin.buffer.read(), capture_output=True)\n'
                'if r.returncode:\n sys.stderr.buffer.write(r.stderr); sys.exit(r.returncode)\n'
                'value = json.loads(r.stdout)\n'
                'value["usage"] = {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10}\n'
                'print(json.dumps(value))\n')
            wrapper.chmod(0o755)
            config = root / 'kernel.json'
            write(config, {'exec': str(fake), 'endpoint': 'parent', 'endpoints': {
                'parent': {'script': [
                    {'tool_calls': [{'name': 'bash', 'arguments': {'command': 'printf parent > result.txt'}}]},
                    {'tool_calls': [{'name': 'thought', 'arguments': {
                        'from': str(child), 'goal': 'Run the planned shell and finish.',
                        'endpoint': 'child', 'keep': False, 'timeout_s': 30}}]},
                    {'content': 'Parent complete.'}]},
                'child': {'script': [
                    {'tool_calls': [{'name': 'bash', 'arguments': {'command': 'printf child'}}]},
                    {'content': 'Child complete.'}]},
                'single': {'script': [{'content': 'Single step complete.'}]}}})
            case = root / 'case'
            (case / 'ws').mkdir(parents=True)
            (case / 'say.txt').write_text('Run the planned shell and child calls.')
            write(case / 'run.json', {'agent': 'parent', 'say': 'say.txt'})
            daemon_config = root / 'daemon.json'
            write(daemon_config, {'interval_ms': 10, 'procs': {}})
            kernel_config = root / 'kernel_daemon.json'
            write(kernel_config, {'interval_ms': 10, 'exec': {'argv': [
                str(PROTO / 'impls/aos-llm-kernel/bin/aos-llm-kernel'), str(config)]}})
            # Log actual public API invocations while forwarding every command unchanged.
            shim = root / 'bin'
            shim.mkdir()
            real_agent = str(PROTO / 'cmd/aos-agent/bin/aos-agent')
            control_log = root / 'control.jsonl'
            forwarding = shim / 'aos-agent'
            forwarding.write_text('#!/usr/bin/env python3\n# Forward and record real agent control calls.\n'
                'import json, os, shutil, subprocess, sys\n'
                f'with open({str(control_log)!r}, "a") as out: out.write(json.dumps(sys.argv[1:]) + "\\n")\n'
                'if sys.argv[1:3] == ["ctl", "rm"] and sys.argv[-1].startswith("measure-"):\n'
                f' source = subprocess.check_output([{real_agent!r}, "ctl", "where", "--target", sys.argv[-1]], text=True).strip()\n'
                f' dest = {str(root / "snapshots")!r} + "/" + sys.argv[-1]\n'
                ' shutil.copytree(source, dest)\n'
                f'os.execv({real_agent!r}, [{real_agent!r}] + sys.argv[1:])\n')
            forwarding.chmod(0o755)
            env['PATH'] = str(shim) + os.pathsep + env['PATH']
            with (root / 'daemon.log').open('w+') as log:
                processes = []
                try:
                    for conf, stack in ((daemon_config, daemon_stack), (kernel_config, kernel_stack)):
                        processes.append(subprocess.Popen(['aos-daemon', str(conf)], cwd=root,
                            env=dict(env, AOS_STACK=str(stack)), stdout=log, stderr=log))
                    deadline = time.monotonic() + 5
                    while not (daemon_stack / 'procs_state.json').exists():
                        self.assertTrue(all(p.poll() is None for p in processes))
                        self.assertLess(time.monotonic(), deadline, 'Daemon startup timed out')
                        time.sleep(.02)
                    result = subprocess.run(['aos-exec', str(MEASURE)],
                        input=json.dumps({'case': str(case), 'defs': str(defs), 'repeat': 2}),
                        env=dict(env, AOS_STACK=str(measure_stack)), cwd=root,
                        capture_output=True, text=True, timeout=120)
                    self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                    output = json.loads(result.stdout)
                    self.assertEqual(len(output['samples']), 2)
                    self.assertTrue(output['check']['pass'], output)
                    self.assertIn('cost', output['check'])
                    self.assertEqual(output['consistency']['scores'], [1.0])
                    run_stacks = sorted((root / 'snapshots').iterdir(), key=lambda p: p.stat().st_mtime_ns)
                    self.assertEqual(len(run_stacks), 2)
                    for sample, stack in zip(output['samples'], run_stacks):
                        rows = list(reachable_records(stack))
                        thinks = [row for row in rows if row.get('kind') == 'think']
                        self.assertEqual(len(thinks), 5)
                        token_total = sum(row['usage']['prompt_tokens'] for row in thinks)
                        self.assertEqual(token_total, 35)
                        self.assertEqual(sample['cost']['token']['in'], token_total)
                        self.assertTrue(sample['check']['pass'])
                        self.assertIn('cost', sample['check'])
                        tree_nodes = list(nodes(sample['tree']))
                        self.assertEqual(len([n for n in tree_nodes if n['kind'] == 'agent']), 2)
                        self.assertIn('parent', [n['def'] for n in tree_nodes])
                        self.assertIn('child', [n['def'] for n in tree_nodes])
                        self.assertEqual(sum(n['cost']['token']['in'] for n in tree_nodes), token_total)
                        self.assertTrue(any(row.get('kind') == 'cmd' for row in rows))
                    self.assertEqual(output['cost']['token']['in'], 35)
                    calls = [json.loads(line) for line in control_log.read_text().splitlines()]
                    for operation in ('add', 'stop', 'rm'):
                        measured = [args for args in calls if args[:2] == ['ctl', operation]
                                    and any(arg.startswith('measure-') for arg in args)]
                        self.assertEqual(len(measured), 2, (operation, calls))
                    listing = subprocess.run([real_agent, 'ctl', 'ls', '--json'], env=env,
                                             capture_output=True, text=True, timeout=10)
                    self.assertEqual(listing.returncode, 0, listing.stderr)
                    self.assertEqual(json.loads(listing.stdout), [])
                    # Measure a separate LLM-step case, preserving its endpoint and scores.
                    write(case / 'run.json', {'agent': 'single', 'say': 'say.txt'})
                    single = subprocess.run(['aos-exec', str(MEASURE)],
                        input=json.dumps({'case': str(case), 'defs': str(defs), 'repeat': 3}),
                        env=dict(env, AOS_STACK=str(measure_stack / 'single')),
                        cwd=root, capture_output=True, text=True, timeout=120)
                    self.assertEqual(single.returncode, 0, single.stderr + single.stdout)
                    step = json.loads(single.stdout)
                    self.assertEqual(step['consistency'], {'scores': [1.0, 1.0], 'pass': True})
                    self.assertEqual(step['tree']['endpoint'], 'single')
                    self.assertEqual(step['tree']['children'], [])
                    self.assertEqual(step['cost']['token']['in'], 7)
                    self.assertEqual(step['cost']['counter_calls'], 1)
                    self.assertEqual(len(step['samples']), 3)
                    listing = subprocess.run([real_agent, 'ctl', 'ls', '--json'], env=env,
                                             capture_output=True, text=True, timeout=10)
                    self.assertEqual(listing.returncode, 0, listing.stderr)
                    self.assertEqual(json.loads(listing.stdout), [])
                finally:
                    for process in processes:
                        process.terminate()
                    for process in processes:
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()
