# Verify complete review rounds against isolated daemons and real fake endpoints.
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest


ROUND = Path(__file__).resolve().parents[1]
PROTO = ROUND.parents[2]
STEPS = {'measure', 'pick', 'try', 'propagate', 'record', 'watch', 'grow'}


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value) + '\n')


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob('*') if p.is_file()}


class ReviewRound(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='aos-review-round-', dir='/tmp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.defs, self.ws, self.stack, self.daemon, self.kernel = [
            self.root / name for name in ('defs', 'ws', 'round', 'daemon', 'kernel')]
        for path in (self.defs, self.ws, self.stack, self.daemon, self.kernel):
            path.mkdir()
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith('AOS_')}
        bins = [str(path) for group in ('impls', 'cmd')
                for path in (PROTO / group).glob('*/bin')]
        self.env.update(PATH=os.pathsep.join(bins + [self.env['PATH']]),
                        PYTHONPATH=os.pathsep.join([str(PROTO / 'lib'), str(PROTO / 'py')]),
                        PYTHONDONTWRITEBYTECODE='1',
                        AOS_DAEMON=str(self.daemon), AOS_LLM_KERNEL=str(self.kernel),
                        AOS_STACK=str(self.stack), AOS_WS=str(self.ws), AOS_CD=str(self.root))
        self.target = self.defs / 'worker'
        shutil.copytree(PROTO / 'templates/agent-fsm', self.target,
                        ignore=shutil.ignore_patterns('tests', '__pycache__'))
        write(self.target / 'llm.json', {'endpoint': 'high'})
        write(self.target / 'tools.json', {'tools': {
            'bash': {'path': str(PROTO / 'lib/base/bash')}}})
        write(self.target / 'loop.json', {'exec': 'fsm.json', 'interval_ms': 10,
                                         'ctl': 'ctl.json', 'state': 'state.json'})
        self.case = self.root / 'case'
        (self.case / 'ws').mkdir(parents=True)
        (self.case / 'expect').mkdir()
        (self.case / 'expect/result.txt').write_text('correct')
        (self.case / 'say.txt').write_text('Write the planned answer and finish.')
        write(self.case / 'run.json', {'agent': 'worker', 'say': 'say.txt', 'timeout_s': 15})
        # A zero case threshold must not allow a failed candidate through the ladder's gate.
        write(self.case / 'check.json', {'min_score': 0})
        fake = self.root / 'fake'
        fake.mkdir()
        entry = fake / '_entry'
        entry.write_text('#!/usr/bin/env python3\n# Invoke the shared test fake endpoint.\n'
                         'import runpy\n'
                         f'runpy.run_path({str(ROUND / "tests/fake_endpoint.py")!r}, run_name="__main__")\n')
        entry.chmod(0o755)
        self.kernel_config = self.root / 'kernel.json'
        self.ladder = self.root / 'ladder.json'
        self.processes = []
        self.log = (self.root / 'daemon.log').open('w+')
        self.addCleanup(self.log.close)
        self.addCleanup(self.stop_daemons)

    def stop_daemons(self):
        for process in self.processes:
            if process.poll() is None:
                process.terminate()
        for process in self.processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    def start(self, levels, *, promote_by='self', repeat=2):
        endpoints = {}
        for name, tokens, answer in levels:
            endpoints[name] = {'prompt_tokens': tokens, 'script': [
                {'tool_calls': [{'name': 'bash', 'arguments': {
                    'command': f'printf {answer} > result.txt'}}]},
                {'content': 'Finished.'}]}
        write(self.kernel_config, {'exec': str(self.root / 'fake'),
                                   'endpoint': 'high', 'endpoints': endpoints})
        write(self.ladder, {'ladder': [name for name, _, _ in levels], 'repeat': repeat,
                            'min_score': 1, 'promote_by': promote_by,
                            'watch': {'window': 3, 'baseline_cases': 3,
                                      'tolerance': .10, 'metric': '/token/in'}})
        daemon_config = self.root / 'daemon.json'
        write(daemon_config, {'interval_ms': 10, 'procs': {}})
        kernel_daemon = self.root / 'kernel_daemon.json'
        write(kernel_daemon, {'interval_ms': 10, 'exec': {'argv': [
            str(PROTO / 'impls/aos-llm-kernel/bin/aos-llm-kernel'), str(self.kernel_config)]}})
        for config, stack in ((daemon_config, self.daemon), (kernel_daemon, self.kernel)):
            self.processes.append(subprocess.Popen(['aos-daemon', str(config)],
                cwd=self.root, env=dict(self.env, AOS_STACK=str(stack)),
                stdout=self.log, stderr=self.log))
        deadline = time.monotonic() + 5
        while not (self.daemon / 'procs_state.json').exists():
            self.assertTrue(all(p.poll() is None for p in self.processes),
                            (self.root / 'daemon.log').read_text())
            self.assertLess(time.monotonic(), deadline, 'Daemon startup timed out')
            time.sleep(.02)

    def run_round(self, tokens, repeat):
        result = subprocess.run(['aos-exec', str(ROUND)], input=json.dumps({
            'case': str(self.case), 'defs': str(self.defs), 'ladder': str(self.ladder)}),
            cwd=self.root, env=self.env, capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        output = json.loads(result.stdout)
        review = read(Path(output['review']))
        self.assertEqual(set(review['steps']), STEPS)
        self.assertTrue(all(step.get('reason') for step in review['steps'].values()))
        self.assertEqual(output['action'], review['action'])
        self.assertEqual(review['target']['def'], 'worker')
        self.assertTrue(review['steps']['measure']['pass'])
        self.assertEqual(review['steps']['measure']['repeat'], repeat)
        # Each real fake agent asks twice. Include every repeat, not the sample median.
        self.assertEqual(review['spent']['token']['in'], 2 * repeat * sum(tokens))
        self.assertEqual(review['spent']['token']['out'], 6 * repeat * len(tokens))
        self.assertEqual(review['spent']['counter_calls'], 2 * repeat * len(tokens))
        # Agent stacks are removed by measure; the kernel retains the actual call ledger.
        ledger = [json.loads(line) for line in (self.kernel / 'ledger.jsonl').read_text().splitlines()]
        actual_tokens = sum(row['usage']['prompt_tokens'] for row in ledger)
        self.assertEqual(review['spent']['token']['in'], actual_tokens)
        self.assertEqual(len(ledger), review['spent']['counter_calls'])
        listing = subprocess.run(['aos-agent', 'ctl', 'ls', '--json'], env=self.env,
                                 capture_output=True, text=True, timeout=10)
        self.assertEqual(listing.returncode, 0, listing.stderr)
        self.assertEqual(json.loads(listing.stdout), [], 'Measured agents must be removed')
        return review

    def test_large_context_produces_specialization_from_real_agent_usage(self):
        self.start([('high', 14000, 'correct')], repeat=2)
        config = read(self.ladder)
        config['max_prompt_tokens_median'] = 10000
        write(self.ladder, config)
        review = self.run_round([14000], 2)
        ledger = [json.loads(line) for line in (self.kernel / 'ledger.jsonl').read_text().splitlines()]
        self.assertEqual([row['usage']['prompt_tokens'] for row in ledger], [14000] * 4)
        self.assertEqual(review['before']['token']['in'], 28000)
        signals = [row for row in review['suggest']['specialize']
                   if row['signal'] == 'context_too_big' and row['from'] == 'worker']
        self.assertTrue(signals, 'Four measured think calls each used 14000 prompt tokens, '
                        'above threshold 10000; suggest is ' + repr(review['suggest']))
        self.assertEqual(signals[0]['evidence']['prompt_tokens_median'], 14000)

    def test_self_promotes_cheaper_passing_endpoint(self):
        self.start([('high', 120, 'correct'), ('low', 40, 'correct')], repeat=3)
        original = snapshot(self.target)
        review = self.run_round([120, 40], 3)
        self.assertEqual(review['action'], 'downgrade')
        self.assertEqual(review['adopted'], {'move': 'downgrade', 'to': 'low'})
        self.assertEqual(review['tried'], [{'move': 'downgrade', 'from': 'high', 'to': 'low',
                                          'scores': [1.0] * 3, 'pass': True}])
        self.assertEqual(read(self.target / 'llm.json')['endpoint'], 'low')
        previous = list((self.defs / '.prev/worker').iterdir())
        self.assertEqual(len(previous), 1)
        self.assertEqual(snapshot(previous[0]), original)
        self.assertEqual(review['before']['token']['in'], 240)
        self.assertEqual(review['after']['token']['in'], 80)
        self.assertNotIn('pending_promote', review)
        windows = read(self.ws / 'reviews/watch.json')['watch']
        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0]['state'], 'watching')
        self.assertEqual(windows[0]['target'], 'worker')
        self.assertEqual(windows[0]['samples'], [])

    def test_claude_leaves_formal_definition_untouched(self):
        self.start([('high', 120, 'correct'), ('low', 40, 'correct')], promote_by='claude')
        original = snapshot(self.defs)
        review = self.run_round([120, 40], 2)
        self.assertEqual(review['action'], 'downgrade')
        self.assertEqual(snapshot(self.defs), original)
        self.assertFalse((self.defs / '.prev').exists())
        self.assertEqual(review['pending_promote'], {
            'defs': str(self.defs), 'target': 'worker', 'from': review['proposed']})
        self.assertEqual(read(Path(review['proposed']) / 'worker/llm.json')['endpoint'], 'low')
        self.assertFalse((self.ws / 'reviews/watch.json').exists())

    def test_failed_lowest_level_prescribes_and_overrides_case_threshold(self):
        self.start([('high', 120, 'correct'), ('low', 10, 'incorrect')])
        original = snapshot(self.defs)
        review = self.run_round([120, 10], 2)
        self.assertEqual(review['action'], 'prescribe')
        self.assertEqual(review['tried'][-1]['scores'], [0.0, 0.0])
        self.assertFalse(review['tried'][-1]['pass'])
        self.assertIsNone(review['adopted'])
        self.assertEqual(snapshot(self.defs), original)
        self.assertEqual(read(Path(review['proposed']) / 'worker/llm.json')['endpoint'], 'high')
        self.assertFalse((self.defs / '.prev').exists())
        self.assertEqual(review['after'], review['before'])

    def test_failure_after_passing_level_retains_last_passing_endpoint(self):
        self.start([('high', 120, 'correct'), ('middle', 40, 'correct'),
                    ('low', 10, 'incorrect')])
        review = self.run_round([120, 40, 10], 2)
        self.assertEqual(review['action'], 'downgrade')
        self.assertEqual([row['pass'] for row in review['tried']], [True, False])
        self.assertEqual([row['from'] for row in review['tried']], ['high', 'middle'])
        self.assertEqual(review['adopted']['to'], 'middle')
        self.assertEqual(read(self.target / 'llm.json')['endpoint'], 'middle')
        self.assertEqual(read(Path(review['proposed']) / 'worker/llm.json')['endpoint'], 'middle')
        self.assertEqual(review['after']['token']['in'], 80)


if __name__ == '__main__':
    unittest.main()
