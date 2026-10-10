"""分段 brief 模板錯誤：首次、接續、status 保持同一個參數錯誤。"""
import copy
from menucase import MenuCase, simple


class MenuBriefTemplateErrors(MenuCase):
    expected = ('aos7-menu: 層 one brief：模板變數 missing 不在，請用 --var missing=值'
                '。請改好選單再跑，例如參考 examples/hello/menu.json\n')

    def broken_menu(self, intro=False):
        obj = simple()
        obj['layers']['one']['brief'] = ['{missing}']
        if intro:
            obj['start'] = 'intro'
            obj['layers']['intro'] = copy.deepcopy(simple()['layers']['one'])
            obj['layers']['intro']['options'][0]['next'] = 'one'
        return self.fixture(obj)

    def brief(self):
        path = self.node / 'brief'
        path.write_text('=== work1 ===\n第一段原文\n')
        return path

    def reach_broken_layer(self):
        menu = self.broken_menu(intro=True)
        reply = self.node / 'reply'
        reply.write_text('選：1')
        got = self.run_menu('--brief', self.brief(), '--reply', reply, menu=menu, rc=2)
        self.assertEqual(got.stderr, self.expected)
        self.assertEqual(self.state('test')['layer'], 'one')
        self.assertIsNone(self.state('test')['pending'])
        return menu, reply

    def test_missing_brief_template_first_run_is_code_two(self):
        got = self.run_menu('--brief', self.brief(), menu=self.broken_menu(), rc=2)
        self.assertEqual(got.stderr, self.expected)
        self.assertFalse((self.node / 'menu/test/state.json').exists())

    def test_missing_brief_template_resume_is_code_two(self):
        menu, reply = self.reach_broken_layer()
        state_path = self.node / 'menu/test/state.json'
        before = state_path.read_bytes()
        got = self.run_menu('--reply', reply, menu=menu, rc=2)
        self.assertEqual(got.stderr, self.expected)
        self.assertEqual(state_path.read_bytes(), before)

    def test_missing_brief_template_status_prompt_is_code_two(self):
        self.reach_broken_layer()
        state_path = self.node / 'menu/test/state.json'
        before = state_path.read_bytes()
        got = self.cli('status', self.node, '--run', 'test', '--prompt', rc=2)
        self.assertEqual(got.stderr, self.expected)
        self.assertEqual(state_path.read_bytes(), before)
