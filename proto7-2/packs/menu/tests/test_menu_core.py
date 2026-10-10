"""純函式契約：回法、重問、動態選項、格子與提示。"""
import copy
import unittest
from menucase import TOOLS, simple
from aos7_menu import MenuError, load, new_state, view, render, step, after


class MenuCore(unittest.TestCase):
    def pair(self, obj=None):
        menu = load(obj or simple(), TOOLS)
        state = new_state(menu, 'test', {'node': '/node', 'run_dir': '/node/menu/test'}, '', 'hash')
        return menu, state

    def test_legal_reply_and_purity(self):
        for slot, reply in [(None, '\n 選:１ \n'), ({'max_lines': 1}, '選：1\n格：你好\n')]:
            with self.subTest(slot=slot):
                menu, state = self.pair(simple(slot))
                saved = copy.deepcopy(state)
                got, nxt = step(menu, state, reply)
                self.assertEqual(state, saved)
                self.assertEqual(nxt['kind'], 'done' if slot is None else 'act')
                if slot:
                    self.assertEqual(nxt['act']['text'], '你好\n')
                    got, nxt = after(menu, got, {'ok': True})
                    self.assertEqual(got['done'], ['reply.txt'])
                    self.assertEqual(nxt['kind'], 'done')

    def test_bad_three_and_recovery(self):
        menu, state = self.pair()
        for i in range(3):
            state, nxt = step(menu, state, '不像回法')
            self.assertEqual(nxt['kind'], 'stuck' if i == 2 else 'ask')
            if i < 2:
                self.assertIn('上一次不行', render(menu, state, reminder=nxt['reminder']))
        self.assertEqual(nxt['code'], 1)
        menu, state = self.pair()
        for _ in range(2):
            state, _ = step(menu, state, '錯')
        state, nxt = step(menu, state, '選：1')
        self.assertEqual((state['tries'], nxt['kind']), (0, 'done'))

    def test_exit(self):
        menu, state = self.pair()
        state, nxt = step(menu, state, '選：2')
        self.assertEqual((nxt['kind'], nxt['code']), ('stuck', 1))

    def test_when_and_done_options(self):
        for when, done, visible in [('required_done', ['a'], True), ('required_missing', [], True),
                                    ('new:{file}', ['a'], False)]:
            with self.subTest(when=when):
                obj = simple()
                obj['required'] = ['a']
                obj['layers']['one']['options'] += [{'text': '條件項', 'next': 'end', 'when': when}]
                menu, state = self.pair(obj)
                state['done'], state['vars']['file'] = done, 'a'
                self.assertEqual('條件項' in render(menu, state), visible)
        obj = simple()
        obj['layers']['one']['options'] = {'from': 'done'}
        menu, state = self.pair(obj)
        state['done'] = ['a', 'b']
        state, nxt = step(menu, state, '選：2')
        self.assertEqual((state['vars']['file'], nxt['kind']), ('b', 'done'))

    def test_slot_checks(self):
        for rule, good, bad in [({'max_bytes': 4}, 'a', '中文'), ({'max_lines': 1}, 'a', 'a\nb'),
            ({'prefix': '頭'}, '頭好', '不好'), ({'sections': ['甲:', '乙:']}, '甲:a\n乙:b', '甲:a')]:
            with self.subTest(rule=rule):
                menu, state = self.pair(simple(rule))
                self.assertEqual(step(menu, state, '選：1\n格：' + good)[1]['kind'], 'act')
                self.assertEqual(step(menu, state, '選：1\n格：' + bad)[1]['kind'], 'ask')
        menu, state = self.pair(simple({'tool': 'check'}))
        state, nxt = step(menu, state, '選：1\n格：內容')
        self.assertEqual(nxt['act']['check'], 'check')
        state, nxt = after(menu, state, {'rc': 0, 'out': {}, 'err': ''})
        self.assertEqual(nxt['act']['write'], 'out/reply.txt')

    def test_template_and_render(self):
        obj = simple()
        obj['layers']['one'].update(ask='{{字面}} {to}', show='out/old.txt')
        menu, state = self.pair(obj)
        with self.assertRaises(MenuError):
            render(menu, state)
        state['vars']['to'], state['done'], state['brief'] = '收件人', ['secret.txt'], '需求摘要'
        text = render(menu, state, shown='只顯示這句')
        self.assertIn('{字面} 收件人', text)
        self.assertIn('secret.txt', text)
        self.assertIn('只顯示這句', text)
        self.assertIn('需求摘要', text)

    def test_fence_and_missing_slot(self):
        menu, state = self.pair(simple({'max_lines': 1}))
        self.assertEqual(step(menu, state, '選：1')[1]['kind'], 'ask')
        state, nxt = step(menu, state, '選：1\n格：\n```\n內容\n```')
        self.assertEqual(nxt['act']['text'], '內容\n')
