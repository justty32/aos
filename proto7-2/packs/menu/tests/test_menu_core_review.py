"""審查 4～8、15：資料生命週期、模板與帶層名的錯誤。"""
import copy
import unittest
from menucase import TOOLS, simple
from aos7_menu import load, new_state, options, render, step, after
from aos7_menu_check import MenuError, normalize_out, out_path


class MenuCoreReview(unittest.TestCase):
    def pair(self, obj=None):
        menu = load(obj or simple(), TOOLS)
        return menu, new_state(menu, 'review', {'name': 'demo'}, '', 'sha')

    def test_r4_failure_outputs_clear_previous_tool_keys(self):
        obj = simple()
        obj['layers'] = {'one': {'do': {'tool': 'check', 'args': {'path': 'x'}},
                                'ok': 'one', 'fail': 'one'}}
        menu, s = self.pair(obj)
        s, _ = after(menu, s, {'rc': 0, 'out': {'issues': 'old', 'obsolete': True, 'run': 'bad'}})
        s['vars']['other'] = 'keep'
        s, _ = after(menu, s, {'rc': 1, 'out': {'issues': 'new', 'details': '甲' * 601}})
        self.assertEqual(s['vars']['issues'], 'new')
        self.assertNotIn('obsolete', s['vars'])
        self.assertEqual(s['vars']['details'], '甲' * 600 + '…')
        self.assertEqual(s['vars']['run'], 'review')
        self.assertEqual(s['vars']['other'], 'keep')
        self.assertEqual(s['var_owner'], {'issues': 'check', 'details': 'check'})
        s, _ = after(menu, s, {'rc': 1})
        self.assertNotIn('issues', s['vars'])
        self.assertNotIn('details', s['vars'])
        self.assertEqual(s['var_owner'], {})

    def test_r4_slot_checker_also_merges_and_clears(self):
        menu, s = self.pair(simple({'tool': 'check'}))
        s['vars']['issues'] = 'old'
        s['var_owner']['issues'] = 'check'
        s, _ = step(menu, s, '選：1\n格：ok')
        s, nxt = after(menu, s, {'rc': 1, 'out': {'issues': 'new'}})
        self.assertEqual(s['vars']['issues'], 'new')
        self.assertEqual(nxt['kind'], 'ask')
        s, _ = step(menu, s, '選：1\n格：ok')
        s, nxt = after(menu, s, {'rc': 0, 'out': {}})
        self.assertNotIn('issues', s['vars'])
        self.assertEqual(nxt['kind'], 'act')

    def test_r5_done_only_expands_and_filters(self):
        obj = simple()
        obj['layers']['one']['options'] = {'from': 'done', 'only': ['aos7_{name}.py', 'row.txt']}
        menu, s = self.pair(obj)
        s['done'] = ['aos7_demo.py', 'row.txt', 'third', 'fourth', 'fifth', 'sixth']
        self.assertEqual([x['text'] for x in options(menu, s)], ['aos7_demo.py', 'row.txt'])
        del menu['layers']['one']['options']['only']
        s['done'] = s['done'][:2]
        self.assertEqual(len(options(menu, s)), 2)
        menu['layers']['one']['options']['only'] = ['{missing}']
        with self.assertRaises(MenuError):
            options(menu, s)

    def test_r6_done_names_are_literal(self):
        obj = simple()
        obj['layers']['one']['options'] = {'from': 'done'}
        menu, s = self.pair(obj)
        s['done'] = ['x{unknown}.py', 'y{name}.py']
        prompt = render(menu, s)
        self.assertIn('1. x{unknown}.py', prompt)
        self.assertIn('2. y{name}.py', prompt)
        for i, filename in enumerate(s['done'], 1):
            got, _ = step(menu, s, '選：' + str(i))
            self.assertEqual(got['vars']['file'], filename)

    def test_r7_paths_share_normalization(self):
        for text in ['reply.txt', './reply.txt', 'out/reply.txt', './out/./reply.txt']:
            self.assertEqual(normalize_out(text), 'reply.txt')
            self.assertEqual(out_path(text, {}), 'out/reply.txt')
        obj = simple({'max_lines': 1})
        obj['layers']['one']['do']['write'] = './out/./reply.txt'
        menu, s = self.pair(obj)
        s['done'] = ['./reply.txt']
        s, act = step(menu, s, '選：1\n格：ok')
        self.assertEqual(act['act']['write'], 'out/reply.txt')
        s, _ = after(menu, s, {'ok': True})
        self.assertEqual(s['done'], ['reply.txt'])
        obj = simple()
        obj['layers']['one']['options'].append({'text': 'new', 'next': 'end', 'when': 'new:./out/./reply.txt'})
        menu, s = self.pair(obj)
        s['done'] = ['./reply.txt']
        self.assertEqual(len(options(menu, s)), 1)

    def test_r7_nested_out_directory_stays_relative(self):
        obj = simple({'max_lines': 1})
        obj['layers']['one']['do']['write'] = 'out/out/reply.txt'
        menu, s = self.pair(obj)
        s['done'] = ['out/reply.txt']
        s, _ = step(menu, s, '選：1\n格：ok')
        s, _ = after(menu, s, {'ok': True})
        self.assertEqual(s['done'], ['out/reply.txt'])
        menu['layers']['one']['do']['write'] = 'out/y'
        s.update(layer='one', status='walking')
        s, _ = step(menu, s, '選：1\n格：ok')
        s, _ = after(menu, s, {'ok': True})
        self.assertEqual(s['done'], ['out/reply.txt', 'y'])
        menu, s = self.pair()
        menu['layers']['one']['options'] = {'from': 'done'}
        s['done'] = ['out/reply.txt']
        self.assertEqual(options(menu, s)[0]['text'], 'out/reply.txt')

    def test_r7_reject_parent_and_absolute(self):
        for text in ['out/sub/../reply.txt', '../reply.txt', '/out/reply.txt', 'out/../../x']:
            with self.subTest(text=text), self.assertRaises(MenuError):
                out_path(text, {})
            obj = simple()
            obj['layers']['one']['options'].append({'text': 'new', 'next': 'end', 'when': 'new:' + text})
            menu, s = self.pair(obj)
            with self.assertRaises(MenuError):
                options(menu, s)

    def test_r8_required_templates(self):
        obj = simple()
        obj['required'] = ['aos7_{name}.py']
        obj['layers']['one']['options'].append({'text': '交齊', 'next': 'end', 'when': 'required_done'})
        menu, s = self.pair(obj)
        s['done'] = ['aos7_demo.py']
        self.assertIn('交齊', render(menu, s))
        del s['vars']['name']
        with self.assertRaises(MenuError):
            render(menu, s)

    def test_r8_slot_templates(self):
        menu, s = self.pair(simple({'prefix': '# {name}', 'sections': ['## {name}', '尾 {run}']}))
        self.assertIn('# demo', render(menu, s))
        got, nxt = step(menu, s, '選：1\n格：# demo\n## demo\n尾 review')
        self.assertEqual(nxt['kind'], 'act')
        for field in ['prefix', 'sections']:
            rule = {field: '{missing}' if field == 'prefix' else ['{missing}']}
            menu, s = self.pair(simple(rule))
            with self.subTest(field=field), self.assertRaises(MenuError):
                step(menu, s, '選：1\n格：value')

    def test_r15_missing_exit_help(self):
        obj = simple()
        del obj['layers']['one']['exit']
        with self.assertRaises(MenuError) as got:
            load(obj, TOOLS)
        self.assertIn('層 one 缺出口 exit。每個問的層都要有，出口字由你定，例如 "exit": {"text": "缺少判斷先回誰的必要資訊，請人補充"}', str(got.exception))

    def test_r15_invalid_fields_name_layer_and_field(self):
        changes = [('ask', 1, 'ask'), ('show', 1, 'show'), ('max_rounds', 0, 'max_rounds'),
                   ('next', 'absent', 'next'), ('exit', {'text': 1}, 'exit'),
                   ('slot', {'prefix': 1}, 'prefix'), ('slot', {'sections': [1]}, 'sections'),
                   ('slot', {'tool': 'absent'}, 'slot.tool'), ('do', [], 'do'),
                   ('options', {'from': 'absent'}, 'options.from'),
                   ('options', {'from': 'done', 'only': [1]}, 'options.only'),
                   ('options', [{'text': 1, 'next': 'end'}], 'options.text'),
                   ('options', [{'text': 'x', 'next': 'absent'}], 'options.next'),
                   ('options', [{'text': 'x', 'next': 'end', 'set': []}], 'set'),
                   ('options', [{'text': 'x', 'next': 'end', 'when': 'no'}], 'when')]
        for key, value, field in changes:
            obj = simple()
            obj['layers']['one'][key] = copy.deepcopy(value)
            with self.subTest(field=field):
                with self.assertRaises(MenuError) as got:
                    load(obj, TOOLS)
                self.assertIn('層 one', str(got.exception))
                self.assertIn(field, str(got.exception))
