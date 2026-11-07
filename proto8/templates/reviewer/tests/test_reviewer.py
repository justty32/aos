# Verify real reviewer, review scripts and shared FSM cells through local fake endpoints.
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

REVIEWER = Path(__file__).resolve().parents[1]
PROTO = REVIEWER.parents[1]


def write(path, value):
    path.write_text(json.dumps(value) + '\n', encoding='utf-8')


def records(stack):
    interface = json.loads((stack / 'interfaces.json').read_text())
    return [json.loads(line) for line in
            (stack / interface['aos-observed']['file']).read_text().splitlines()]


class ReviewerIntegration(unittest.TestCase):
    def test_round_and_prescription_with_fake_brain(self):
        with tempfile.TemporaryDirectory(prefix='aos-reviewer-', dir='/tmp') as tmp:
            root = Path(tmp)
            daemon_stack, kernel_stack = root / 'daemon', root / 'kernel'
            daemon_stack.mkdir()
            kernel_stack.mkdir()
            env = {key: value for key, value in os.environ.items()
                   if not key.startswith('AOS_')}
            bins = [str(path) for group in ('impls', 'cmd')
                    for path in (PROTO / group).glob('*/bin')]
            env['PATH'] = os.pathsep.join(bins + [env['PATH']])
            env['PYTHONPATH'] = os.pathsep.join([str(PROTO / 'lib'), str(PROTO / 'py')])
            env['PYTHONDONTWRITEBYTECODE'] = '1'
            env.update(AOS_STACK=str(daemon_stack), AOS_DAEMON=str(daemon_stack),
                       AOS_LLM_KERNEL=str(kernel_stack), AOS_CD=str(root), AOS_WS=str(root))

            # Preserve the template's relative paths and reuse cells without copying them.
            templates = root / 'templates'
            templates.mkdir()
            (templates / 'agent-fsm').symlink_to(PROTO / 'templates/agent-fsm', target_is_directory=True)
            (root / 'lib').symlink_to(PROTO / 'lib', target_is_directory=True)
            reviewer = templates / 'reviewer'
            shutil.copytree(REVIEWER, reviewer,
                            ignore=shutil.ignore_patterns('tests', '__pycache__'))
            write(reviewer / 'llm.json', {'endpoint': 'reviewer'})
            loop = json.loads((reviewer / 'loop.json').read_text())
            loop['interval_ms'] = 10
            write(reviewer / 'loop.json', loop)
            self.assertFalse(list(reviewer.glob('*.py')))

            defs = root / 'defs'
            defs.mkdir()
            (defs / 'agent-fsm').symlink_to(PROTO / 'templates/agent-fsm', target_is_directory=True)
            worker = defs / 'worker'
            worker.mkdir()
            for name in ('body.json', 'loop.json', 'interfaces.json', 'fsm.json'):
                shutil.copy2(reviewer / name, worker / name)
            write(worker / 'llm.json', {'endpoint': 'worker'})
            write(worker / 'tools.json', {'tools': {}})
            (worker / 'system.txt').write_text('Return the fixed answer.\n')
            initial_llm = (worker / 'llm.json').read_bytes()
            case = root / 'case'
            (case / 'ws').mkdir(parents=True)
            (case / 'expect').mkdir()
            (case / 'say.txt').write_text('Return the fixed answer.\n')
            (case / 'expect/stdout.json').write_text('Fixed answer.\n')
            write(case / 'run.json', {'agent': 'worker', 'say': 'say.txt'})
            ladder = reviewer / 'ladder.json'
            settings = json.loads(ladder.read_text())
            # No cheaper level exists, so real review_round must ask for a prescription.
            settings.update(ladder=['worker'], promote_by='claude')
            write(ladder, settings)
            round_args = {'case': str(case), 'defs': str(defs), 'ladder': str(ladder),
                          'ws': str(root)}
            prescription = {'move': 'split', 'target': 'worker',
                            'why': 'The ladder has no cheaper endpoint.',
                            'how': 'Move deterministic preparation into a script before the model step.'}
            config = root / 'kernel.json'
            write(config, {'exec': str(REVIEWER / 'tests/endpoint.py'),
                           'endpoint': 'reviewer', 'endpoints': {
                               'reviewer': {'role': 'reviewer', 'ws': str(root),
                                            'round_args': round_args, 'prescription': prescription,
                                            'prompt_tokens': 13},
                               'worker': {'script': [{'content': 'Fixed answer.'}], 'prompt_tokens': 7}}})
            daemon_config, kernel_config = root / 'daemon.json', root / 'kernel_daemon.json'
            write(daemon_config, {'interval_ms': 10, 'procs': {}})
            write(kernel_config, {'interval_ms': 10, 'exec': {'argv': [
                str(PROTO / 'impls/aos-llm-kernel/bin/aos-llm-kernel'), str(config)]}})

            def agent(*args):
                result = subprocess.run(['aos-agent', '--daemon', str(daemon_stack), *args],
                    cwd=root, env=env, capture_output=True, text=True, timeout=45)
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                return result.stdout

            with (root / 'daemon.log').open('w+') as log:
                processes = []
                try:
                    for conf, stack in ((daemon_config, daemon_stack), (kernel_config, kernel_stack)):
                        processes.append(subprocess.Popen(['aos-daemon', str(conf)], cwd=root,
                            env=dict(env, AOS_STACK=str(stack)), stdout=log, stderr=log))
                    deadline = time.monotonic() + 5
                    while not (daemon_stack / 'procs_state.json').exists():
                        self.assertTrue(all(process.poll() is None for process in processes))
                        self.assertLess(time.monotonic(), deadline, 'Daemon startup timed out')
                        time.sleep(.02)
                    agent('ctl', 'add', '--name', 'reviewer', '--ws', str(root), str(reviewer))
                    agent('say', '--target', 'reviewer', json.dumps(round_args))
                    answer = agent('listen', '--target', 'reviewer', '--timeout-s', '35')
                    self.assertIn('Review complete; one split prescription is ready.', answer)
                    stack = Path(agent('ctl', 'where', '--target', 'reviewer').strip())
                    history = [json.loads(line) for line in (stack / 'history.jsonl').read_text().splitlines()]
                    tool_messages = [row for row in history if row.get('role') == 'tool']
                    self.assertEqual(len(tool_messages), 2)
                    result = json.loads(tool_messages[0]['content'])
                    self.assertEqual(result['action'], 'prescribe', result)
                    review = json.loads(Path(result['review']).read_text())
                    self.assertEqual(review['prescriptions'], [prescription])
                    self.assertEqual(len(review['steps']), 7)
                    self.assertTrue(review['steps']['measure']['pass'])
                    self.assertTrue(review['consistency']['pass'])
                    self.assertEqual(review['before']['token']['in'], 7)
                    self.assertEqual((worker / 'llm.json').read_bytes(), initial_llm)
                    self.assertFalse((defs / '.prev').exists())
                    rows = records(stack)
                    self.assertEqual(rows[0]['def'], str(reviewer))
                    self.assertEqual(rows[0]['ws'], str(root))
                    thinks = [row for row in rows if row['kind'] == 'think']
                    self.assertEqual(len(thinks), 3)
                    self.assertEqual([row['endpoint'] for row in thinks], ['reviewer'] * 3)
                    self.assertEqual([row['usage']['prompt_tokens'] for row in thinks], [13] * 3)
                    tools = [row for row in rows if row['kind'] == 'tool']
                    self.assertEqual([row['name'] for row in tools], ['review_round', 'json_edit'])
                    self.assertTrue(all(row['code'] == 0 for row in tools))
                    round_rows = records(stack / tools[0]['stack'])
                    self.assertTrue(any(row.get('name', '').startswith('measure_') and row['code'] == 0
                                        for row in round_rows))
                    request = json.loads((stack / 'think/request.json').read_text())
                    self.assertEqual(request['request']['messages'][0]['content'],
                                     (reviewer / 'system.txt').read_text())
                    self.assertEqual({tool['function']['name'] for tool in request['request']['tools']},
                                     set(json.loads((reviewer / 'tools.json').read_text())['tools']))
                    agent('ctl', 'rm', 'reviewer')
                    self.assertEqual(json.loads(agent('ctl', 'ls', '--json')), [])
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
