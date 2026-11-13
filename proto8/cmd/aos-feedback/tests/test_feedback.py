# Verify feedback CLI storage, comfort calculations and the real aos-exec tool boundary.
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
CLI = ROOT / 'cmd/aos-feedback/bin/aos-feedback'
EXEC = ROOT / 'impls/aos-exec/bin/aos-exec'


class FeedbackFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='aos-feedback-test-')
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.feedback = self.work / 'feedback'
        self.feedback.mkdir()
        shutil.copyfile(ROOT / 'feedback/raters.json', self.feedback / 'raters.json')
        self.env = os.environ.copy()
        for key in ('AOS_CD', 'AOS_STACK', 'AOS_WS', 'AOS_DAEMON', 'AOS_KERNEL'):
            self.env.pop(key, None)
        self.env.update(AOS_FEEDBACK=str(self.feedback),
                        PATH=str(EXEC.parent) + os.pathsep + str(CLI.parent)
                        + os.pathsep + self.env.get('PATH', ''))

    def run_cli(self, *args, ok=True):
        result = subprocess.run([str(CLI), *args], cwd=self.work, env=self.env,
                                text=True, capture_output=True, timeout=15)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, '')
        return result

    def add(self, command='demo', pain='unclear', *args):
        return json.loads(self.run_cli('add', command, pain, *args, '--json').stdout)

    def score(self, key='demo', *args):
        return json.loads(self.run_cli('score', key, *args).stdout)

    def ledger(self, name, rows):
        path = self.work / name
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        return str(path)

    def tool(self, name='demo', code=0, definition=None):
        return {'kind': 'tool', 'name': name, 'def': definition or '/defs/' + name,
                'code': code, 'stack': 'tools/' + name, 'elapsed_ms': 1,
                'in_bytes': 2, 'out_bytes': 3}

    def assert_empty_ai(self, comfort):
        self.assertEqual(comfort['ai'], dict.fromkeys(('usage', 'help', 'errors', 'args')))
        self.assertIsNone(comfort['user'])


class FeedbackAcceptance(FeedbackFixture):
    def test_add_preserves_text_and_appends_with_metadata(self):
        command = '/opt/Bin/My.Cmd ctl add'
        pain = '  unclear\nnext line 中文  '
        suggest = ' keep  spaces\nplease '
        self.env['AOS_CD'] = '/defs/my-agent'
        first = self.add(command, pain, suggest, '--kind', 'help', '--score', '0.4')
        second = self.add(command, 'second', '--by', 'explicit')
        records = [json.loads(line) for line in
                   (self.feedback / 'my_cmd.jsonl').read_text().splitlines()]
        self.assertEqual(records, [first, second])
        self.assertEqual(first['command'], command)
        self.assertEqual(first['pain'], pain)
        self.assertEqual(first['suggest'], suggest)
        self.assertEqual(first['kind'], 'help')
        self.assertEqual(first['score'], 0.4)
        self.assertEqual(first['by'], 'my-agent')
        self.assertEqual(first['cwd'], str(self.work))
        self.assertRegex(first['at'], r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$')
        datetime.datetime.fromisoformat(first['at'].replace('Z', '+00:00'))
        self.assertEqual(second['kind'], 'other')
        self.assertEqual(second['by'], 'explicit')
        self.assertNotIn('score', second)
        self.assertNotIn('suggest', second)
        self.env.pop('AOS_CD')
        self.assertEqual(self.add('lib/base/read')['by'], 'unknown')
        self.assertTrue((self.feedback / 'read.jsonl').is_file())


    def test_add_writes_cwd_without_the_home_prefix(self):
        self.env['HOME'] = str(self.work.parent)
        self.assertEqual(self.add()['cwd'], '~/' + self.work.name)
        self.env['HOME'] = str(self.work)
        self.assertEqual(self.add()['cwd'], '~')
        self.env['HOME'] = str(self.work) + '-other'
        self.assertEqual(self.add()['cwd'], str(self.work))
        text = (self.feedback / 'demo.jsonl').read_text()
        self.assertEqual(text.count(str(self.work)), 1)

    def test_model_rules_and_explicit_free_strings(self):
        for model, family, tier in [('claude-opus', 'claude', 'high'),
                                    ('claude-sonnet', 'claude', 'mid'),
                                    ('codex-sol', 'gpt', 'high'),
                                    ('terra', 'gpt', 'mid'), ('qwen-12b', 'local', 'low'),
                                    ('unlisted', 'unknown', 'unknown')]:
            with self.subTest(model=model):
                self.assertEqual(self.add('demo', 'x', '--model', model)['rater'],
                                 {'model': model, 'family': family, 'tier': tier})
        self.assertEqual(self.add('demo', 'x', '--model', 'opus', '--family', 'new family',
                                  '--tier', 'custom tier')['rater'],
                         {'model': 'opus', 'family': 'new family', 'tier': 'custom tier'})
        self.assertEqual(self.add('demo', 'x', '--model', 'opus', '--family', 'custom')
                         ['rater']['tier'], 'high')
        (self.feedback / 'raters.json').write_text(json.dumps({'rules': [
            {'match': 'same', 'family': 'first', 'tier': 'one'},
            {'match': 'same-model', 'family': 'second', 'tier': 'two'}]}))
        self.assertEqual(self.add('demo', 'x', '--model', 'same-model')['rater']['family'], 'first')

    def test_listing_show_json_and_human_lines(self):
        self.add('one', 'one pain')
        self.add('two', 'two pain')
        latest = self.add('two extra', 'another pain')
        listing = json.loads(self.run_cli('ls', '--json').stdout)
        self.assertEqual([row['key'] for row in listing], ['two', 'one'])
        self.assertEqual(listing[0], {'key': 'two', 'feedback': 2, 'latest': latest['at']})
        human = self.run_cli('ls').stdout.splitlines()
        self.assertRegex(human[0], r'^two\s+2\s+')
        records = json.loads(self.run_cli('show', 'two', '--json').stdout)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[-1], latest)
        shown = self.run_cli('show', 'two').stdout.splitlines()
        self.assertEqual(len(shown), 2)
        self.assertIn('two pain', shown[0])
        self.assertIn('another pain', shown[1])

    def test_published_formula_and_no_rewrite(self):
        self.add('demo', 'x', '--kind', 'help', '--score', '0.4', '--model', 'opus')
        self.add('demo', 'y', '--kind', 'help', '--score', '0.6', '--model', 'terra')
        rows = [self.tool(code=1), self.tool(), self.tool(), self.tool(),
                self.tool(code=2), self.tool('different')] + [self.tool() for _ in range(5)]
        definition = self.work / 'defs/demo'
        definition.mkdir(parents=True)
        (definition / '_metainfo.json').write_text(json.dumps({'comfort': .9}))
        for row in rows:
            if row['name'] == 'demo':
                row['def'] = str(definition)
        observed = self.ledger('observed.jsonl', [{'kind': 'self', 'def': '/defs/demo'}, *rows])
        before = {p: p.read_bytes() for p in self.work.rglob('*') if p.is_file()}
        result = self.score('demo', '--observed', observed)
        self.assertEqual({k: result[k] for k in ('key', 'feedback', 'calls', 'errors', 'retries')},
                         dict(key='demo', feedback=2, calls=10, errors=2, retries=1))
        comfort = result['comfort']
        self.assertEqual(comfort['ai'], dict(usage=None, help=0.5, errors=None, args=None))
        self.assertAlmostEqual(comfort['val'], 0.5 * 10 / 13)
        self.assertIsNone(comfort['user'])
        for group, name, expected in [('family', 'claude', .4), ('family', 'gpt', .6),
                                      ('tier', 'high', .4), ('tier', 'mid', .6)]:
            part = comfort['ai_by'][group][name]
            self.assertEqual(part['help'], expected)
            self.assertAlmostEqual(part['val'], expected * 10 / 13)
        self.assertEqual(result, json.loads(self.run_cli('score', 'demo', '--observed', observed,
                                                         '--json').stdout))
        self.assertEqual(before, {p: p.read_bytes() for p in self.work.rglob('*') if p.is_file()})

    def test_no_scores_no_ledger_and_other_not_a_dimension(self):
        self.add('demo', 'unscored', '--kind', 'help')
        self.add('demo', 'other score', '--kind', 'other', '--score', '1')
        result = self.score()
        self.assertEqual(result['feedback'], 2)
        self.assert_empty_ai(result['comfort'])
        self.assertIsNone(result['comfort']['val'])
        ledger = self.ledger('only.jsonl', [self.tool(code=1), self.tool()])
        result = self.score('demo', '--observed', ledger)
        self.assert_empty_ai(result['comfort'])
        self.assertAlmostEqual(result['comfort']['val'], .5)
        self.assertEqual(result['calls'], 2)
        self.assertEqual(self.score('absent')['comfort']['val'], None)
        self.assertEqual(json.loads(self.run_cli('show', 'absent', '--json').stdout), [])
        only_ledger = self.score('absent', '--observed', self.ledger(
            'absent.jsonl', [self.tool('absent', code=1), self.tool('absent')]))
        self.assertEqual(only_ledger['feedback'], 0)
        self.assert_empty_ai(only_ledger['comfort'])
        self.assertAlmostEqual(only_ledger['comfort']['val'], .5)

    def test_all_dimensions_mean_without_behavior(self):
        for kind, value in [('usage', 0), ('help', .2), ('errors', .6), ('args', 1)]:
            self.add('demo', 'x', '--kind', kind, '--score', str(value))
        result = self.score()
        self.assertEqual(result['comfort']['ai'], dict(usage=0, help=.2, errors=.6, args=1))
        self.assertAlmostEqual(result['comfort']['val'], .45)

    def test_retry_requires_adjacent_same_tool_in_same_file(self):
        first = self.ledger('first.jsonl', [self.tool(code=1), self.tool('other'), self.tool(),
                                                self.tool(code=1)])
        second = self.ledger('second.jsonl', [self.tool(), self.tool('alias', definition='/defs/demo'),
                                                  self.tool('irrelevant')])
        result = self.score('demo', '--observed', first, '--observed', second)
        self.assertEqual(result['calls'], 5)
        self.assertEqual(result['errors'], 2)
        self.assertEqual(result['retries'], 0)

    def test_retry_ignores_non_tool_rows_but_distinguishes_definitions(self):
        ledger = self.ledger('identities.jsonl', [
            self.tool(code=1), {'kind': 'think', 'prompt_tokens': 20}, self.tool(),
            self.tool(code=1), self.tool(definition='/another/demo')])
        result = self.score('demo', '--observed', ledger)
        self.assertEqual(result['calls'], 4)
        self.assertEqual(result['errors'], 2)
        self.assertEqual(result['retries'], 1)

    def test_bad_arguments_are_single_english_error_with_usage(self):
        cases = [(), ('nonesuch',), ('add',), ('add', 'demo'),
                 ('add', 'demo', 'x', '--kind', 'invalid'),
                 ('add', 'demo', 'x', '--score', '-0.1'),
                 ('add', 'demo', 'x', '--score', '1.1'),
                 ('add', 'demo', 'x', '--score', 'nan'),
                 ('add', 'demo', 'x', '--score', 'inf'),
                 ('add', 'demo', 'x', '--score', 'text'),
                 ('add', 'demo', 'x', '--bogus'), ('score',), ('show',),
                 ('ls', 'extra'), ('score', 'demo', '--observed')]
        for args in cases:
            with self.subTest(args=args):
                result = self.run_cli(*args, ok=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, '')
                self.assertEqual(len(result.stderr.splitlines()), 1)
                self.assertRegex(result.stderr, r'^aos-feedback: error: \w+ .+ \(usage: .+\)\n$')
                self.assertTrue(result.stderr.isascii())
        self.assertFalse(list(self.feedback.glob('*.jsonl')))
        self.assertIn('usage', self.run_cli('--help').stdout.lower())

    def test_real_aos_exec_thin_tool(self):
        payload = {'command': 'lib/base/read', 'pain': 'unclear', 'suggest': 'example',
                   'kind': 'args', 'score': .7}
        result = subprocess.run([str(EXEC), str(ROOT / 'lib/aos/feedback')],
                                input=json.dumps(payload), text=True, capture_output=True,
                                cwd=self.work, env=self.env, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        self.assertEqual(result.stdout, f'aos-feedback: recorded {self.feedback / "read.jsonl"}\n')
        records = json.loads(self.run_cli('show', 'read', '--json').stdout)
        self.assertEqual(records[0]['by'], 'aos-agent')
        for key, value in payload.items():
            self.assertEqual(records[0][key], value)


if __name__ == '__main__':
    unittest.main()
