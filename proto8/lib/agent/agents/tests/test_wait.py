# Verify segmented agent waits, argument checks and cleanup.
import ast
import json
import os
import sys
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock

SOURCE = Path(__file__).resolve().parents[1] / '_entry'


class WaitTests(unittest.TestCase):
    def scope(self, times):
        tree = ast.parse(SOURCE.read_text())
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'agent')
        proc = Mock(returncode=0)
        proc.poll.return_value = 0
        proc.communicate.side_effect = [subprocess.TimeoutExpired('fake', 1), (b'answer', b'')]
        ns = dict(STEP_S=90, child=None, daemon='fake', subprocess=Mock(Popen=Mock(return_value=proc), TimeoutExpired=subprocess.TimeoutExpired),
                  tool_io=Mock(Error=type('ToolError', (Exception,), {})), time=Mock(monotonic=Mock(side_effect=times)), sys=Mock(), kill_group=Mock(),
                  ERR_RE=__import__('re').compile(r'never'))
        def die(*args):
            raise RuntimeError(args)
        ns['die'] = die
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(SOURCE), 'exec'), ns)
        return ns, proc

    def test_large_seconds_wait_in_segments(self):
        ns, proc = self.scope([0, 0, 86400, 86400])
        self.assertEqual(ns['agent'](['listen'], timeout_s=1e9), ('answer', None))
        self.assertTrue(all(c.kwargs['timeout'] <= 86400 for c in proc.communicate.call_args_list))
        self.assertIsNone(ns['child'])
        proc.wait.assert_called_once()

    def test_expired_wait_cleans_up(self):
        ns, proc = self.scope([0, 0, 2])
        proc.poll.return_value = None
        with self.assertRaises(RuntimeError):
            ns['agent'](['listen'], timeout_s=1)
        ns['kill_group'].assert_called_once_with(proc)
        proc.wait.assert_called_once()
        self.assertIsNone(ns['child'])

    def test_entry_seconds_validation(self):
        env = os.environ.copy()
        env.pop('AOS_DAEMON', None)
        for value, code in [(1e9, 'DaemonMissing'), (0, 'ArgumentsBad'),
                            (-1, 'ArgumentsBad'), (float('inf'), 'ArgumentsBad'),
                            (float('-inf'), 'ArgumentsBad'), (float('nan'), 'ArgumentsBad')]:
            with self.subTest(timeout_s=value):
                result = subprocess.run(
                    [sys.executable, str(SOURCE)],
                    input=json.dumps(dict(op='ask', name='kid', text='hello', timeout_s=value)),
                    text=True, capture_output=True, env=env, timeout=5)
                self.assertEqual(result.returncode, 1)
                self.assertIn('error: ' + code + ' ', result.stdout)
                self.assertNotIn('Traceback', result.stderr)

    def test_tick_wait_keeps_short_poll(self):
        ns, proc = self.scope([0])
        ns['tool_io'].expired.return_value = False
        self.assertEqual(ns['agent'](['listen'], timeout_ticks=10), ('answer', None))
        self.assertTrue(all(c.kwargs['timeout'] == .2 for c in proc.communicate.call_args_list))


if __name__ == '__main__':
    unittest.main()
