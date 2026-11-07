# Verify concurrent feedback writes, CLI argument boundaries and damaged input handling.
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import unittest

from test_feedback import FeedbackFixture, ROOT, EXEC


class FeedbackBoundaries(FeedbackFixture):
    def test_concurrent_append_preserves_every_long_record(self):
        def submit(index):
            pain = str(index) + ':' + ('long content 中文\n' * 1600)
            return self.add('parallel', pain, '--by', 'writer-' + str(index))
        with ThreadPoolExecutor(max_workers=24) as pool:
            expected = list(pool.map(submit, range(24)))
        lines = (self.feedback / 'parallel.jsonl').read_text().splitlines()
        self.assertEqual(len(lines), 24)
        actual = [json.loads(line) for line in lines]
        self.assertEqual({r['by']: r for r in actual}, {r['by']: r for r in expected})

    def test_flags_around_arguments_equals_and_literal_separator(self):
        record = json.loads(self.run_cli('--json', 'add', '--kind=help', 'flags',
                                         '--score=0', 'pain', '--by', 'tester').stdout)
        self.assertEqual(record['score'], 0)
        self.assertEqual(record['kind'], 'help')
        self.assertEqual(record['by'], 'tester')
        record = json.loads(self.run_cli('add', '--json', '--score', '1', '--',
                                         '-literal', '--pain', '--suggest').stdout)
        self.assertEqual(record['command'], '-literal')
        self.assertEqual(record['pain'], '--pain')
        self.assertEqual(record['suggest'], '--suggest')
        self.assertEqual(record['score'], 1)
        self.assertEqual(self.add('flags', 'pain', '--score=0.5')['score'], .5)
        for args in [('add', '--bogus', 'flags', 'pain'),
                     ('add', 'flags', 'pain', '--by'),
                     ('add', 'flags', 'pain', '--score')]:
            result = self.run_cli(*args, ok=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(len(result.stderr.splitlines()), 1)
            self.assertIn('(usage:', result.stderr)
            self.assertNotIn('Traceback', result.stderr)

    def assert_file_error(self, args, code='FileBad'):
        result = self.run_cli(*args, ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        self.assertEqual(len(result.stderr.splitlines()), 1)
        self.assertIn('aos-feedback: error: ' + code, result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_damaged_feedback_observed_and_missing_ledger(self):
        (self.feedback / 'broken.jsonl').write_text('{broken\n')
        for args in [('show', 'broken'), ('score', 'broken'), ('ls',)]:
            self.assert_file_error(args)
        observed = self.ledger('broken_observed.jsonl', [])
        Path(observed).write_text('[not json\n')
        self.assert_file_error(('score', 'demo', '--observed', observed))
        self.assert_file_error(('score', 'demo', '--observed', str(self.work / 'missing')),
                               'FileMissing')

    def test_missing_or_damaged_rater_rules(self):
        # Rename only the temporary copy; the repository rules stay untouched.
        rules = self.feedback / 'raters.json'
        rules.rename(self.feedback / 'saved_rules.json')
        self.assertEqual(self.add('demo', 'x', '--model', 'opus')['rater'],
                         dict(model='opus', family='unknown', tier='unknown'))
        for invalid in ['not json', '[]', '{"rules": {}}',
                        '{"rules": [{"match": "opus", "family": 3, "tier": "high"}]}']:
            rules.write_text(invalid)
            self.assert_file_error(('add', 'demo', 'x', '--model', 'opus'))

    def test_fallback_directory_without_writing_repository(self):
        env = self.env.copy()
        env.pop('AOS_FEEDBACK')
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        script = ('import sys; sys.path[:0] = ' + repr([
            str(ROOT / 'cmd/aos-feedback'), str(ROOT / 'py')]) +
            '; from aos_feedback.storage import directory; print(directory())')
        result = subprocess.run([sys.executable, '-B', '-c', script], env=env,
                                text=True, capture_output=True, cwd=self.work, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(ROOT / 'feedback'))
        self.assertEqual(result.stderr, '')

    def test_thin_tool_explicit_by_and_downstream_failure(self):
        payload = dict(command='explicit', pain='pain', by='named-reviewer')
        result = subprocess.run([str(EXEC), str(ROOT / 'lib/aos/feedback')],
                                input=json.dumps(payload), text=True, capture_output=True,
                                cwd=self.work, env=self.env, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.run_cli('show', 'explicit', '--json').stdout)[0]['by'],
                         'named-reviewer')
        payload['score'] = 2
        result = subprocess.run([str(EXEC), str(ROOT / 'lib/aos/feedback')],
                                input=json.dumps(payload), text=True, capture_output=True,
                                cwd=self.work, env=self.env, timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('Traceback', result.stdout + result.stderr)
        self.assertIn('error:', result.stdout)
        self.assertIn('error:', result.stderr)
        self.assertEqual(len(json.loads(self.run_cli('show', 'explicit', '--json').stdout)), 1)

    def test_thin_tool_optional_nulls_and_invalid_types(self):
        payload = dict(command='nullable', pain='pain', by=None, suggest=None,
                       kind=None, score=None)
        def run(value):
            return subprocess.run([str(EXEC), str(ROOT / 'lib/aos/feedback')],
                                  input=json.dumps(value), text=True, capture_output=True,
                                  cwd=self.work, env=self.env, timeout=15)
        result = run(payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads(self.run_cli('show', 'nullable', '--json').stdout)[0]
        self.assertEqual(record['by'], 'aos-agent')
        self.assertEqual(record['kind'], 'other')
        self.assertNotIn('score', record)
        self.assertNotIn('suggest', record)
        for key, value in [('by', 3), ('suggest', []), ('score', True), ('kind', 'wrong')]:
            with self.subTest(key=key):
                result = run(dict(payload, **{key: value}))
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('Traceback', result.stdout + result.stderr)
                self.assertIn('error:', result.stdout)


if __name__ == '__main__':
    unittest.main()
