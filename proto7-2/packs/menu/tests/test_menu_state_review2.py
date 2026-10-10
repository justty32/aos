"""第三輪：凍結 pending 結構與純工具關卡的恢復。"""
import copy
from menucase import MenuCase, simple, TOOLS
from aos7_menu import load, new_state, step, after
from aos7_menu_state import valid_state


class MenuStateReview2(MenuCase):
    def frozen(self, tool=False):
        obj = simple({'tool': 'check'})
        obj['layers']['one']['do'] = ({'tool': 'check', 'args': {'path': '{file}'}}
                                     if tool else {'write': 'out/{file}'})
        menu = load(obj, TOOLS)
        state = new_state(menu, 'test', {'file': 'original', 'node': str(self.node),
                          'run_dir': str(self.node / 'menu/test')}, '', 'hash')
        state.update(initial_vars={'file': 'original'}, journal=[])
        state, _ = step(menu, state, '選：1\n格：text')
        state['var_owner']['file'] = 'check'
        state, _ = after(menu, state, {'rc': 0, 'out': {}})
        self.assertNotIn('file', state['vars'])
        return menu, state

    def test_frozen_write_survives_checker_removing_template_var(self):
        menu, state = self.frozen()
        self.assertEqual(state['pending']['act']['write'], 'out/original')
        self.assertTrue(valid_state(state, menu))

    def test_frozen_tool_args_survive_checker_removing_template_var(self):
        menu, state = self.frozen(True)
        self.assertEqual(state['pending']['act']['args'], {'path': 'original'})
        self.assertTrue(valid_state(state, menu))

    def test_pure_tool_pending_rejects_next_and_extra_fields(self):
        menu = load({'v': 1, 'name': 'test', 'start': 'gate', 'layers': {
            'gate': {'do': {'tool': 'check', 'args': {'path': '{file}'}}, 'ok': 'verify'},
            'verify': simple()['layers']['one']}}, TOOLS)
        state = new_state(menu, 'test', {'node': str(self.node),
                          'run_dir': str(self.node / 'menu/test')}, '', 'hash')
        state.update(initial_vars={}, journal=[], pending={'act': {'tool': 'check', 'args': {'path': 'old'}}})
        self.assertTrue(valid_state(state, menu))
        for change in ({'next': 'end'}, {'then': {'next': 'end'}}, {'unknown': 1}):
            with self.subTest(change=change):
                bad = copy.deepcopy(state)
                bad['pending'].update(change)
                self.assertFalse(valid_state(bad, menu))
        bad = copy.deepcopy(state)
        bad['pending']['act']['next'] = 'end'
        self.assertFalse(valid_state(bad, menu))
