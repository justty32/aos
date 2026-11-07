"""Verify isolated runs, comparator accounting, failure gates and suites."""
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HERE), str(HERE.parents[1])]
import runner


class MeasureTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = self.root / 'case'
        self.case.mkdir()
        (self.case / 'run.json').write_text(json.dumps({'exec': 'math', 'stdin': 'stdin.json'}))
        (self.case / 'stdin.json').write_text('{"expr":"1+1"}')
        (self.case / 'ws').mkdir()
        (self.case / 'ws/initial').write_text('seed')
        self.env = dict(os.environ)

    def fake_call(self, name, target, data, stack=None):
        self.assertEqual((Path(os.environ['AOS_WS']) / 'initial').read_text(), 'seed')
        self.assertFalse((Path(os.environ['AOS_WS']) / 'pollution').exists())
        (Path(os.environ['AOS_WS']) / 'pollution').write_text('new')
        return 0, b'2\n', b''

    def test_isolation_reference_and_consistency(self):
        with patch.object(runner.observed, 'call', self.fake_call):
            result = runner.measure({'case': str(self.case), 'defs': str(self.root), 'repeat': 3}, self.root / 'stack')
        self.assertTrue(result['check']['pass'])
        self.assertEqual(result['consistency'], {'scores': [1, 1], 'pass': True})
        self.assertEqual(len(result['samples']), 3)
        self.assertEqual(result['size_bytes'], len(b'{"expr":"1+1"}') + 4)
        self.assertEqual(dict(os.environ), self.env)

    def test_nonzero_target_fails_even_identical_output(self):
        with patch.object(runner.observed, 'call', return_value=(7, b'2\n', b'')):
            result = runner.measure({'case': str(self.case), 'defs': str(self.root)}, self.root / 'stack')
        self.assertFalse(result['check']['pass'])
        self.assertEqual(result['samples'][0]['code'], 7)
        self.assertNotIn('consistency', result)

    def test_expected_mismatch(self):
        (self.case / 'expect').mkdir()
        (self.case / 'expect/stdout.json').write_text('3\n')
        with patch.object(runner.observed, 'call', return_value=(0, b'2\n', b'')):
            result = runner.measure({'case': str(self.case), 'defs': str(self.root)}, self.root / 'stack')
        self.assertFalse(result['check']['pass'])
        self.assertEqual(result['check']['diff'], ['stdout.json'])

    def test_suite_preserves_individual_scores(self):
        suite = self.root / 'suite'
        suite.mkdir()
        self.case.rename(suite / 'one')
        with patch.object(runner.observed, 'call', return_value=(0, b'2\n', b'')):
            result = runner.measure({'case': str(suite), 'defs': str(self.root), 'repeat': 2}, self.root / 'stack')
        self.assertEqual(len(result['samples']), 2)
        self.assertEqual(result['consistency']['scores'], [1])
        self.assertEqual(result['tree']['cost']['time_ms'], sum(c['cost']['time_ms'] for c in result['tree']['children']))

    def test_existing_run_is_preserved(self):
        occupied = self.root / 'stack/runs/0'
        occupied.mkdir(parents=True)
        (occupied / 'marker').write_text('keep')
        with patch.object(runner.observed, 'call', return_value=(0, b'2\n', b'')):
            runner.measure({'case': str(self.case), 'defs': str(self.root)}, self.root / 'stack')
        self.assertEqual((occupied / 'marker').read_text(), 'keep')
        self.assertTrue((self.root / 'stack/runs/1/ws/stdout.json').exists())

    def test_invalid_run_and_check(self):
        for run in ([], {'exec': 3, 'stdin': 'stdin.json'}, {'exec': 'math', 'agent': 'math'}):
            (self.case / 'run.json').write_text(json.dumps(run))
            with self.assertRaises(ValueError):
                runner.measure({'case': str(self.case), 'defs': str(self.root)}, self.root / 'stack')
        (self.case / 'run.json').write_text(json.dumps({'exec': 'math', 'stdin': 'stdin.json'}))
        for check in ([], {'compare': []}, {'min_score': False}):
            (self.case / 'check.json').write_text(json.dumps(check))
            with self.assertRaises(ValueError):
                runner.measure({'case': str(self.case), 'defs': str(self.root)}, self.root / 'stack')

    def test_invalid_repeat(self):
        for repeat in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                runner.measure({'case': str(self.case), 'defs': str(self.root), 'repeat': repeat}, self.root / 'stack')

    def test_agent_remove_failure_is_reported(self):
        ok = SimpleNamespace(returncode=0, stdout=b'answer', stderr=b'')
        failed = SimpleNamespace(returncode=9, stdout=b'', stderr=b'')
        with patch.object(runner.subprocess, 'run', side_effect=[ok, ok, ok, ok, failed]), \
                patch.object(runner, 'fold', return_value=({}, {})):
            with self.assertRaisesRegex(ValueError, 'cannot remove measured agent.*9'):
                runner.agent_run(self.root, b'hello', self.root, self.root / 'stack', self.root)


if __name__ == '__main__':
    unittest.main()
