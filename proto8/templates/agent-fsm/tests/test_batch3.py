# Verify daemon-managed fake-brain parent and child observations through public interfaces.
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

CELLS = Path(__file__).resolve().parents[1]
PROTO = CELLS.parents[1]


def write(path, value):
    path.write_text(json.dumps(value), encoding='utf-8')


def records(stack):
    """Find each ledger exclusively through its declared public interface."""
    interface = json.loads((stack / 'interfaces.json').read_text())
    ledger = stack / interface['aos-observed']['file']
    return [json.loads(line) for line in ledger.read_text().splitlines()]


class Batch3Integration(unittest.TestCase):
    def test_parent_thought_child_shell_ledgers(self):
        with tempfile.TemporaryDirectory(prefix='aos-batch3-') as tmp:
            root = Path(tmp)
            daemon_stack = root / 'daemon'
            daemon_stack.mkdir()
            kernel_stack = root / 'kernel'
            kernel_stack.mkdir()
            env = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}
            bins = [str(path) for path in (PROTO / 'impls').glob('*/bin')]
            bins += [str(path) for path in (PROTO / 'cmd').glob('*/bin')]
            env['PATH'] = os.pathsep.join(bins + [env['PATH']])
            env['PYTHONPATH'] = os.pathsep.join([str(PROTO / 'lib'), str(PROTO / 'py')])
            env.update(AOS_STACK=str(daemon_stack), AOS_CD=str(root), AOS_WS=str(root),
                       AOS_DAEMON=str(daemon_stack), AOS_LLM_KERNEL=str(kernel_stack))

            def definition(name, endpoint, tools):
                target = root / name
                shutil.copytree(CELLS, target, ignore=shutil.ignore_patterns('tests', '__pycache__'))
                write(target / 'llm.json', {'model': endpoint})
                write(target / 'tools.json', {'tools': tools})
                write(target / 'loop.json', {'exec': 'fsm.json', 'interval_ms': 10,
                                             'ctl': 'ctl.json', 'state': 'state.json',
                                             'state_flux': 'state_flux.json'})
                return target

            bash = PROTO / 'lib/base/shell'
            child_def = definition('child_def', 'child', {'shell': {'path': str(bash)}})
            parent_def = definition('parent_def', 'parent', {
                'shell': {'path': str(bash)},
                'thought': {'path': str(PROTO / 'lib/agent/thought')}})
            kernel_config = root / 'kernel.json'
            write(kernel_config, {'exec': str(PROTO / 'lib/base/llm_fake'), 'endpoint': 'parent',
                'endpoints': {
                    'parent': {'script': [
                        {'tool_calls': [{'name': 'shell', 'arguments': {'command': 'printf parent; exit 7'}}]},
                        {'tool_calls': [{'name': 'thought', 'arguments': {
                            'from': str(child_def), 'goal': 'Run the shell and report completion.',
                            'model': 'child', 'keep': False, 'timeout_s': 30}}]},
                        {'content': 'Parent complete.'}]},
                    'child': {'script': [
                        {'tool_calls': [{'name': 'shell', 'arguments': {'command': 'printf child; exit 3'}}]},
                        {'content': 'Child complete.'}]}}})
            daemon_config = root / 'daemon.json'
            write(daemon_config, {'interval_ms': 10, 'procs': {}})

            def agent(*args):
                result = subprocess.run(['aos-agent', '--daemon', str(daemon_stack), *args],
                    cwd=root, env=env, capture_output=True, text=True, timeout=45)
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                return result.stdout

            with (root / 'daemon.log').open('w+') as log:
                daemon = subprocess.Popen(['aos-daemon', str(daemon_config)], cwd=root,
                                           env=env, stdout=log, stderr=log)
                # The kernel has its own stack and lifetime, just like the existing cell test.
                kernel_env = dict(env, AOS_STACK=str(kernel_stack))
                kernel_daemon_config = root / 'kernel_daemon.json'
                write(kernel_daemon_config, {'interval_ms': 10, 'exec': {'argv': [
                    str(PROTO / 'impls/aos-llm-kernel/bin/aos-llm-kernel'), str(kernel_config)]}})
                kernel = subprocess.Popen(['aos-daemon', str(kernel_daemon_config)], cwd=root,
                                          env=kernel_env, stdout=log, stderr=log)
                try:
                    deadline = time.monotonic() + 5
                    while not (daemon_stack / 'procs_state.json').exists():
                        self.assertIsNone(daemon.poll(), 'Agent daemon exited during startup')
                        self.assertLess(time.monotonic(), deadline, 'Agent daemon did not become ready')
                        time.sleep(.02)
                    agent('ctl', 'add', '--name', 'parent', '--ws', str(root), str(parent_def))
                    agent('say', '--target', 'parent', 'Run the planned shell and child calls.')
                    answer = agent('listen', '--target', 'parent', '--timeout-s', '40')
                    self.assertIn('Parent complete.', answer)
                    stack = Path(agent('ctl', 'where', '--target', 'parent').strip())
                    rows = records(stack)
                    self.assertEqual(rows[0]['kind'], 'self')
                    self.assertEqual(rows[0]['llm_kernel'], str(kernel_stack))
                    self.assertEqual(rows[0]['def'], str(parent_def))
                    self.assertEqual(rows[0]['ws'], str(root))
                    self.assertRegex(rows[0]['started_at'], r'^\d{4}-.*\.\d{3}Z$')
                    tools = [row for row in rows if row['kind'] == 'tool']
                    self.assertEqual([row['name'] for row in tools], ['shell', 'thought'])
                    shell, thought = tools
                    self.assertEqual(shell['def'], str(bash))
                    self.assertEqual(shell['code'], 0)
                    self.assertEqual(shell['stack'], 'tools/shell')
                    for tool in tools:
                        self.assertTrue(Path(tool['def']).is_absolute())
                        for field in ('elapsed_ms', 'in_bytes', 'out_bytes'):
                            self.assertGreaterEqual(tool[field], 0)
                    self.assertEqual(thought['code'], 0)
                    self.assertTrue(thought['child'].startswith('tools/thought/observed/'))
                    shell_rows = records(stack / shell['stack'])
                    self.assertEqual([row['exit'] for row in shell_rows if row['kind'] == 'cmd'], [7])
                    child_stack = stack / thought['child']
                    child_rows = records(child_stack)
                    self.assertEqual(child_rows[0]['kind'], 'self')
                    self.assertEqual(child_rows[0]['llm_kernel'], str(kernel_stack))
                    self.assertEqual(child_rows[0]['def'], str(child_def))
                    self.assertTrue(any(row['kind'] == 'think' for row in child_rows))
                    child_shell = next(row for row in child_rows if row['kind'] == 'tool')
                    self.assertEqual(child_shell['name'], 'shell')
                    copied_shell = records(child_stack / child_shell['stack'])
                    self.assertEqual([row['exit'] for row in copied_shell if row['kind'] == 'cmd'], [3])
                    self.assertFalse((daemon_stack / 'procs' / child_stack.name).exists())
                    agent('ctl', 'rm', 'parent')
                finally:
                    for process in (daemon, kernel):
                        process.terminate()
                    for process in (daemon, kernel):
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()
