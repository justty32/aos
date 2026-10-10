"""學徒工具：正式選單整圈、每種已交集合、AP5 葉子工具契約。"""
import copy
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from menucase import MenuCase, PACK, TOP, read_json
from aos7_menu import load, new_state, options, render
from aos7_menu_run import prompt

EXAMPLE = PACK / 'examples/aos-tool'
MENU = EXAMPLE / 'menu.json'
BUILD = EXAMPLE / 'build.py'
AUTHOR = TOP / 'packs/author'
REQUEST = AUTHOR / 'examples/aos-tool-mailcount/request.json'
VALID = AUTHOR / 'examples/aos-tool-mailcount/valid.json'


class MenuAos(MenuCase):
    def build(self, *args, rc=0, env=None):
        p = subprocess.run([sys.executable, '-B', str(BUILD), *map(str, args)],
                           cwd=self.node, text=True, capture_output=True, timeout=150,
                           env=dict(os.environ, **(env or {})))
        self.assertEqual(p.returncode, rc, p.stdout + p.stderr)
        self.assertLessEqual(len(p.stderr.splitlines()), 1, p.stderr)
        if rc:
            self.assertEqual(len(p.stderr.splitlines()), 1, p.stderr)
        if rc == 3:
            self.assertIn('不確定：', p.stderr)
        return p

    def result(self, *args, **kw):
        p = self.build(*args, **kw)
        self.assertEqual(len(p.stdout.splitlines()), 1, p.stdout)
        value = json.loads(p.stdout)
        self.assertEqual(set(value), {'ok', 'gate', 'issues', 'candidate'})
        return value

    def materialize(self):
        candidate = read_json(str(VALID))
        run = self.node / 'run'
        for rel, text in dict(candidate['files'], row=candidate['row'], report=candidate['report']).items():
            file = run / 'out' / rel
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(text)
        return run, candidate

    def fake(self, value=None, rc=0, raw=None, author=False):
        file = self.node / ('author.py' if author else 'gates.py')
        file.write_text('import json,sys\n' +
                       ('print(' + repr(raw) + ')\n' if raw is not None else
                        'print(json.dumps(' + repr(value) + ', ensure_ascii=False, indent=' +
                        ('1' if author else 'None') + '))\n') +
                       'sys.exit(' + repr(rc) + ')\n')
        return {'AOS7_AOS_TOOL_AUTHOR' if author else 'AOS7_AOS_TOOL_GATES': str(file)}

    def pair(self):
        menu = load(read_json(str(MENU)), read_json(str(PACK / 'tools.json')))
        state = new_state(menu, 'aos-tool', {'name': 'mailcount', 'request': str(REQUEST),
                    'review': 'rules', 'issues': '第2關：answer：答案不同',
                    'file': 'packs/mailcount/aos7_mailcount.py',
                    'node': str(self.node), 'run_dir': str(self.node / 'run')}, '', 'hash')
        return menu, state

    def test_practice_complete_failure_fix_retry_and_shape(self):
        # Author tests likewise use --no-scope: bwrap remains the actual sandbox.
        env = {'AOS7_AOS_TOOL_NO_SCOPE': '1'}
        brief = self.node / 'brief.txt'
        brief.write_text(self.build('brief', REQUEST).stdout)
        p = self.run_menu('--var', 'name=mailcount', '--var', 'request=' + str(REQUEST),
                          '--var', 'review=rules', '--brief', brief, menu=MENU, env=env, wait=240)
        self.assertIn('做完', p.stdout)
        state = self.state('aos-tool')
        self.assertEqual(state['status'], 'done')
        logs = self.logs('aos-tool')
        self.assertEqual([row['step'] for row in logs], list(range(1, len(logs) + 1)))
        bad = [row for row in logs if row['kind'] == 'bad']
        self.assertEqual(len(bad), 1)
        gates = [row for row in logs if row['kind'] == 'tool' and row['layer'] == 'gates']
        self.assertEqual([row['rc'] for row in gates], [1, 0])
        middle = logs[logs.index(gates[0]) + 1:logs.index(gates[1])]
        self.assertTrue({'fix', 'fixcode'}.issubset({row['layer'] for row in middle}))
        run = self.node / 'menu/aos-tool'
        replies = read_json(str(EXAMPLE / 'practice.json'))['replies']
        names = [name.replace('{name}', 'mailcount') for name in read_json(str(MENU))['required']]
        expected = dict(zip(names + ['row', 'report'],
                            [replies[i].split('格：', 1)[1] for i in (2, 4, 13, 8, 10, 11)]))
        self.assertEqual(set(state['done']), set(expected))
        for rel, content in expected.items():
            self.assertEqual((run / 'out' / rel).read_text(), content.rstrip() + '\n')
        text = (run / 'candidate.txt').read_text()
        self.assertEqual(re.findall(r'^=== (.+) ===$', text, re.M), sorted(names) + ['row', 'report'])
        chars = [row['prompt_chars'] for row in logs if row['kind'] == 'ask']
        self.assertEqual(len(chars), len(state['calls']))
        print('MN2 aos-tool prompt_chars mean=%.2f calls=%d' % (sum(chars) / len(chars), len(chars)))
        self.assertIn('做完', self.cli('status', self.node, '--run', 'aos-tool').stdout)
        before = copy.deepcopy(state)
        self.run_menu(menu=MENU, env=env)
        self.assertEqual(self.state('aos-tool'), before)

    def test_all_sixteen_done_sets_and_fix_menus(self):
        menu, state = self.pair()
        files = [name.replace('{name}', 'mailcount') for name in menu['required']]
        for mask in range(16):
            state['done'] = [name for bit, name in enumerate(files) if mask & (1 << bit)]
            for layer in ('which', 'fix', 'fixdoc', 'fixtail', 'fixcode', 'fixdocw', 'fixrow', 'fixreport'):
                with self.subTest(mask=mask, layer=layer):
                    state['layer'] = layer
                    saved = copy.deepcopy(state)
                    text = render(menu, state)
                    numbers = [int(x) for x in re.findall(r'^(\d+)\. ', text, re.M)]
                    self.assertEqual(numbers, list(range(1, len(options(menu, state)) + 2)))
                    self.assertTrue(2 <= len(numbers) <= 5)
                    self.assertEqual(state, saved)
                    if layer in ('fixdoc', 'fixtail'):
                        self.assertEqual(options(menu, state)[-1]['next'], 'fix')
                        self.assertEqual(len(numbers), 4)
                    if layer == 'which':
                        self.assertEqual(len(numbers), max(1, 4 - len(state['done'])) + 1)

    def test_prompts_only_attach_the_selected_fix_content(self):
        menu, state = self.pair()
        directory = self.node / 'run'
        names = [name.replace('{name}', 'mailcount') for name in menu['required']] + ['row', 'report']
        contents = {name: 'UNIQUE_CONTENT_%d_SECRET' % i for i, name in enumerate(names)}
        for name, content in contents.items():
            file = directory / 'out' / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(content)
        state['done'] = names
        for layer, spec in menu['layers'].items():
            if 'ask' not in spec:
                continue
            choices = names[2:4] if layer == 'fixcode' else names[:2] if layer == 'fixdocw' else [names[2]]
            for chosen in choices:
                with self.subTest(layer=layer, file=chosen):
                    state['layer'], state['vars']['file'] = layer, chosen
                    text = prompt(menu, state, directory)
                    attached = {'fixcode': chosen, 'fixdocw': chosen, 'fixrow': 'row', 'fixreport': 'report'}.get(layer)
                    self.assertEqual('目前的內容：' in text, attached is not None)
                    for name, content in contents.items():
                        self.assertEqual(content in text, name == attached)

    def test_candidate_sorted_newlines_row_report_and_rerun(self):
        run, candidate = self.materialize()
        additions = {'packs/mailcount/z.txt': 'last\n\n', 'packs/mailcount/a.txt': 'first',
                     'packs/another/x.txt': 'other\n\n'}
        for rel, text in additions.items():
            file = run / 'out' / rel
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(text)
        cache = run / 'out/packs/mailcount/__pycache__'
        cache.mkdir()
        (cache / 'ignore.pyc').write_text('cache')
        (run / 'out/packs/mailcount/link').symlink_to(run / 'out/row')
        (run / 'out/packs/mailcount/linked-directory').symlink_to(cache, target_is_directory=True)
        env = self.fake({'ok': True, 'failed_gate': None,
                         'gates': {str(n): {'ok': True, 'issues': []} for n in (1, 2, 3)}})
        result = self.result('check', run, REQUEST, env=env)
        self.assertIs(result['ok'], True)
        self.assertEqual(result['issues'], '')
        self.assertEqual(result['candidate'], str(run / 'candidate.txt'))
        all_files = dict(candidate['files'], **additions)
        expected = ''.join('=== %s ===\n%s\n' % (name, all_files[name].rstrip('\n')) for name in sorted(all_files))
        expected += '=== row ===\n' + candidate['row'].rstrip('\n') + '\n=== report ===\n' + candidate['report'].rstrip('\n') + '\n'
        self.assertEqual((run / 'candidate.txt').read_text(), expected)
        self.assertEqual(self.result('check', run, REQUEST, env=env), result)
        self.assertEqual((run / 'candidate.txt').read_text(), expected)

    def test_missing_row_bad_request_and_bad_gates_output(self):
        run, _ = self.materialize()
        env = self.fake(raw='not JSON')
        result = self.result('check', run, REQUEST, rc=3, env=env)
        self.assertIs(result['ok'], False)
        self.result('check', run, REQUEST, rc=3, env=self.fake({'ok': True}))
        (run / 'out/row').unlink()
        result = self.result('check', run, REQUEST, rc=1)
        self.assertIn('row', result['issues'])
        self.assertTrue(result['issues'].startswith('第1關：'))
        bad = self.node / 'request.json'
        for data in ('{bad', json.dumps({'kind': 'other'})):
            bad.write_text(data)
            self.build('check', run, bad, rc=2)
        self.build('check', run, self.node / 'absent', rc=2)
        self.build('check', self.node / 'absent', REQUEST, rc=2)
        help_result = self.build('--help')
        self.assertIn('build.py check RUN_DIR REQUEST', help_result.stdout)
        self.assertIn('build.py brief REQUEST', help_result.stdout)
        self.assertEqual(help_result.stderr, '')
        self.build('--unknown', rc=2)
        self.build('check', run, REQUEST, '--unknown', rc=2)

    def test_failure_issues_are_bounded_and_review_reasons_survive(self):
        run, _ = self.materialize()
        issues = [{'rule': 'answer', 'why': 'wrong.py：' + '答案不同' * 200},
                  {'rule': 'test', 'why': 'tests.py：失敗'}]
        failure = {'ok': False, 'failed_gate': 2, 'gates': {'2': {'ok': False, 'issues': issues}}}
        value = self.result('check', run, REQUEST, rc=1, env=self.fake(failure, rc=1))
        self.assertEqual(value['gate'], 2)
        self.assertTrue(value['issues'].startswith('第2關：'))
        self.assertLessEqual(len(value['issues']), 580)
        self.assertIn('…', value['issues'])
        self.assertIn('answer', value['issues'])
        self.result('check', run, REQUEST, '--review', 'fake-model', rc=3,
                    env=self.fake({'ok': False, 'why': 'unknown'}, rc=3, author=True))

    def test_model_review_accepts_multiline_author_success_and_rejects_extra_json(self):
        run, _ = self.materialize()
        check = {'ok': True, 'failed_gate': None,
                 'gates': {str(n): {'ok': True, 'issues': []} for n in (1, 2, 3)}}
        receipt = {'ok': True, 'why': None, 'llm': None, 'review': None,
                   'rules_check': check, 'check': check}
        value = self.result('check', run, REQUEST, '--review', 'fake-model',
                            env=self.fake(receipt, author=True))
        self.assertTrue(value['ok'])
        self.assertIsNone(value['gate'])
        self.assertEqual(value['issues'], '')
        self.result('check', run, REQUEST, '--review', 'fake-model', rc=3,
                    env=self.fake(raw=json.dumps(receipt, indent=1) + '\n{}', author=True))

    def test_real_author_second_gate_stops_before_model_review(self):
        run, _ = self.materialize()
        # Same answer-checker failure as practice; no ledger or model is called.
        source = run / 'out/packs/mailcount/aos7_mailcount.py'
        broken = read_json(str(EXAMPLE / 'practice.json'))['replies'][6].split('格：', 1)[1]
        self.assertIn('v=True', broken)
        source.write_text(broken)
        value = self.result('check', run, REQUEST, '--review', 'must-not-be-called', rc=1,
                            env={'AOS7_AOS_TOOL_NO_SCOPE': '1'})
        self.assertFalse(value['ok'])
        self.assertEqual(value['gate'], 2)
        self.assertTrue(value['issues'].startswith('第2關：'))
        self.assertFalse((self.node / 'budget').exists())

    def test_real_author_file_reviewer_rejection_reasons_survive(self):
        run, _ = self.materialize()
        review = self.node / 'review.json'
        reasons = ['缺少邊界處理', '需求要求的失敗訊息不完整']
        review.write_text(json.dumps({'verdict': 'reject', 'reasons': reasons}))
        p = subprocess.run([sys.executable, '-B', str(AUTHOR / 'bin/aos7-author'),
                            'propose', str(REQUEST), '--candidate', str(VALID),
                            '--reviewer', 'file:' + str(review), '--no-scope'],
                           cwd=self.node, capture_output=True, text=True, timeout=150)
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertGreater(len(p.stdout.splitlines()), 1)
        receipt = json.loads(p.stdout)
        self.assertEqual(receipt['why'], 'invalid')
        self.assertTrue(receipt['rules_check']['ok'])
        self.assertEqual(receipt['check']['failed_gate'], 3)
        self.assertEqual(receipt['check']['gates']['3']['issues'],
                         [{'rule': 'review', 'why': reasons}])
        # LLM review uses the same file: checker; review stores call metadata,
        # while the rejection reasons are in check.gates["3"].issues[].why.
        self.assertIsNone(receipt['review'])
        value = self.result('check', run, REQUEST, '--review', 'fake-model', rc=1,
                            env=self.fake(raw=p.stdout, rc=p.returncode, author=True))
        self.assertFalse(value['ok'])
        self.assertEqual(value['gate'], 3)
        self.assertTrue(value['issues'].startswith('第3關：'))
        for reason in reasons:
            self.assertIn(reason, value['issues'])

    def test_brief_contains_every_requested_clause_and_gap_is_too_long(self):
        text = self.build('brief', REQUEST).stdout
        self.assertLessEqual(len(text), 1500)
        req = read_json(str(REQUEST))
        for item in [req['task'], req['goal'], *req['scope']['only'], *req['scope']['not'],
                     *req['work'], *req['accept']]:
            self.assertIn(item, text)
        for tool in req['tools']:
            self.assertIn(tool['tool'], text)
            self.assertIn(tool['use'], text)
        p = self.build('brief', AUTHOR / 'examples/aos-tool-gap/request.json', rc=2)
        self.assertEqual(p.stdout, '')
        self.assertIn('1500', p.stderr)
