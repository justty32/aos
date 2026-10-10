"""第二次審查：每鍵來源與 required 的按需展開。"""
import unittest
from menucase import TOOLS, simple
from aos7_menu import load, new_state, options, render, step, after


class MenuCoreReview2(unittest.TestCase):
    def pair(self, obj, tools=TOOLS):
        menu = load(obj, tools)
        return menu, new_state(menu, 'review2', {}, '', 'sha')

    def tool_menu(self):
        obj = simple()
        obj['layers']['one'] = {'do': {'tool': 'check', 'args': {'path': 'x'}}, 'ok': 'choose', 'fail': 'choose'}
        obj['layers']['choose'] = {'ask': '選檔名', 'exit': {'text': '離開'},
                                  'options': [{'text': '改名', 'set': {'file': 'final.txt'}, 'next': 'one'}]}
        return obj

    def test_r1_set_releases_tool_ownership(self):
        menu, state = self.pair(self.tool_menu())
        original = state.copy()
        state, _ = after(menu, state, {'rc': 0, 'out': {'file': 'initial.txt', 'obsolete': True}})
        self.assertEqual(state['var_owner']['file'], 'check')
        state, _ = step(menu, state, '選：1')
        state, _ = after(menu, state, {'rc': 1, 'out': {}})
        self.assertEqual(state['vars']['file'], 'final.txt')
        self.assertNotIn('obsolete', state['vars'])
        self.assertEqual(state['var_owner'], {})
        self.assertEqual(original['var_owner'], {})

    def test_r1_other_tool_takes_ownership(self):
        obj = self.tool_menu()
        obj['layers']['one']['ok'] = 'other'
        obj['layers']['other'] = {'do': {'tool': 'other'}, 'ok': 'one', 'fail': 'one'}
        tools = {'v': 1, 'tools': dict(TOOLS['tools'], other={'argv': ['true'], 'args': [], 'out': 'code'})}
        menu, state = self.pair(obj, tools)
        state, _ = after(menu, state, {'rc': 0, 'out': {'file': 'initial.txt', 'obsolete': True}})
        state, _ = after(menu, state, {'rc': 0, 'out': {'file': 'other.txt'}})
        state, _ = after(menu, state, {'rc': 1, 'out': {}})
        self.assertEqual(state['vars']['file'], 'other.txt')
        self.assertNotIn('obsolete', state['vars'])
        self.assertEqual(state['var_owner'], {'file': 'other'})

    def test_r2_set_provides_required_variable_after_first_question(self):
        obj = simple()
        obj['required'] = ['aos7_{name}.py']
        obj['layers']['one']['options'] = [{'text': '選 demo', 'set': {'name': 'demo'}, 'next': 'check'}]
        obj['layers']['check'] = {'ask': '交齊了嗎', 'exit': {'text': '離開'}, 'options': [
            {'text': '齊了', 'when': 'required_done', 'next': 'end'},
            {'text': '未齊', 'when': 'required_missing', 'next': 'check'}]}
        menu, state = self.pair(obj)
        self.assertIn('選 demo', render(menu, state))
        state, _ = step(menu, state, '選：1')
        self.assertEqual([x['text'] for x in options(menu, state)], ['未齊'])
        state['done'] = ['aos7_demo.py']
        self.assertEqual([x['text'] for x in options(menu, state)], ['齊了'])

    def test_r2_dynamic_done_options_do_not_expand_required(self):
        obj = simple()
        obj['required'] = ['aos7_{name}.py']
        obj['layers']['one']['options'] = {'from': 'done'}
        menu, state = self.pair(obj)
        state['done'] = ['reply.txt']
        self.assertIn('1. reply.txt', render(menu, state))
        state, _ = step(menu, state, '選：1')
        self.assertEqual(state['vars']['file'], 'reply.txt')

    def test_r7_new_state_nonce_is_fresh_fixed_hex(self):
        menu = load(simple(), TOOLS)
        states = [new_state(menu, 'same', {}, '', 'sha') for _ in range(2)]
        for state in states:
            self.assertRegex(state['nonce'], r'^[0-9a-f]{16}$')
        self.assertNotEqual(states[0]['nonce'], states[1]['nonce'])
