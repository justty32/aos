"""MN2 核心小修：提示、圍欄容錯、選單診斷與 CLI 說明。"""
import copy
import unittest
from menucase import MenuCase, TOOLS, simple
from aos7_menu import MenuError, load, new_state, render, step
from aos7_menu_check import parse_reply


class MenuMN2Core(unittest.TestCase):
    def pair(self, obj):
        menu = load(obj, TOOLS)
        state = new_state(menu, 'test', {'node': '/node', 'run_dir': '/node/menu/test', 'to': '小明'}, '', 'hash')
        return menu, state

    def test_render_slot_reply_and_human_limits(self):
        slot = {'max_bytes': 8192, 'max_lines': 30, 'prefix': '給 {to}：',
                'sections': ['甲：', '乙：{to}'], 'tool': 'check'}
        menu, state = self.pair(simple(slot))
        saved = copy.deepcopy((menu, state))
        self.assertEqual(render(menu, state).splitlines()[-3:], [
            '回法：第一行 選：N',
            '第二行起：先寫「格：」，後面（同一行或下一行起）到結尾放全文，原樣、不加 ``` 圍欄，全文後面不要再寫任何字',
            '這格的限制（只是說明，不要抄進格子）：最多 8192 bytes、最多 30 行、第一行以「給 小明：」開頭、要有一行以「甲：」開頭、要有一行以「乙：小明」開頭、會再用工具檢查'])
        self.assertEqual((menu, state), saved)

    def test_render_without_slot_has_only_selection_reply(self):
        menu, state = self.pair(simple())
        text = render(menu, state)
        self.assertTrue(text.endswith('回法：第一行 選：N'))
        self.assertNotIn('這格的限制', text)
        self.assertNotIn('第二行起', text)

    def test_paired_fence_with_copied_limit_tail(self):
        body = 'def main():\n    print("hello")'
        for marker in ('格：\n', '格：'):
            for closing in ('```', '``` \t', '```；這格限制：max_bytes=8192',
                            '```這格的限制：max_bytes=8192', '``` ; 這格限制：max_bytes=8192',
                            '```；這格限制：max_bytes=8192、tool=python-check'):
                with self.subTest(marker=marker, closing=closing):
                    reply = '選：1\n' + marker + '```python\n' + body + '\n' + closing
                    self.assertEqual(parse_reply(reply, True), (1, body + '\n', True, None))
                    compile(parse_reply(reply, True)[1], '<slot>', 'exec')
                    menu, state = self.pair(simple({'max_bytes': 8192}))
                    result, nxt = step(menu, state, reply)
                    self.assertTrue(result['fence'])
                    self.assertEqual(nxt['act']['text'], body + '\n')

    def test_literal_fence_tail_is_preserved(self):
        reviewed = '```python\nprint("hello")\n```\n保留這段說明\n```這是合法原文尾行'
        for body in (reviewed, '```python\nprint("hello")\n```其他文字',
                     '```python\nprint("hello")\n```；限制：max_bytes=8192',
                     '```python\nprint("hello")\n```😀這格的合法原文'):
            with self.subTest(body=body):
                reply = '選：1\n格：' + body
                self.assertEqual(parse_reply(reply, True), (1, body + '\n', False, None))
                menu, state = self.pair(simple({'max_bytes': 8192}))
                result, nxt = step(menu, state, reply)
                self.assertFalse(result['fence'])
                self.assertEqual(nxt['act']['text'], body + '\n')

    def test_unpaired_or_nonfinal_fence_tail_is_preserved(self):
        for body in ('print("hello")\n```；這格限制：max_bytes=8192',
                     '```python\nprint("hello")',
                     '```python\nprint("hello")\n```；限制\n後面還有全文'):
            with self.subTest(body=body):
                self.assertEqual(parse_reply('選：1\n格：' + body, True),
                                 (1, body + '\n', False, None))

    def test_static_options_error_reports_count(self):
        for count in (0, 5):
            obj = simple()
            obj['layers']['one']['options'] *= count
            with self.subTest(count=count), self.assertRaisesRegex(MenuError,
                    '層 one options 含出口要 2～5 個，現在 %s 個' % (count + 1)):
                load(obj, TOOLS)

    def test_dynamic_options_error_reports_count(self):
        obj = simple()
        obj['layers']['one']['options'] = {'from': 'done'}
        menu, state = self.pair(obj)
        for done in ([], ['a', 'b', 'c', 'd', 'e']):
            state['done'] = done
            with self.subTest(done=done), self.assertRaisesRegex(MenuError,
                    '層 one options 含出口要 2～5 個，現在 %s 個' % (len(done) + 1)):
                render(menu, state)

    def test_missing_target_reports_field_and_name(self):
        for field in ('next', 'options.next', 'start'):
            obj = simple()
            if field == 'options.next':
                obj['layers']['one']['options'][0]['next'] = 'missing-layer'
            elif field == 'start':
                obj['start'] = 'missing-layer'
            else:
                obj['layers']['one']['next'] = 'missing-layer'
            with self.subTest(field=field), self.assertRaisesRegex(MenuError,
                    field + ' 指不到層：missing-layer'):
                load(obj, TOOLS)

    def test_missing_exit_explains_custom_text(self):
        obj = simple()
        del obj['layers']['one']['exit']
        with self.assertRaisesRegex(MenuError,
                '出口字由你定，例如 "exit": {"text": "缺少判斷先回誰的必要資訊，請人補充"}'):
            load(obj, TOOLS)


class MenuMN2CLI(MenuCase):
    def test_fence_cleanup_is_written_and_logged(self):
        menu = self.fixture(simple({'max_bytes': 8192}), [
            '選：1\n格：\n```python\ndef main():\n    print("hello")\n```；這格限制：max_bytes=8192'])
        self.run_menu(menu=menu)
        body = (self.node / 'menu/test/out/reply.txt').read_text()
        self.assertEqual(body, 'def main():\n    print("hello")\n')
        compile(body, '<written slot>', 'exec')
        self.assertTrue(next(row for row in self.logs('test') if row['kind'] == 'pick')['fence'])

    def test_invalid_menu_json_reports_location_and_keeps_file(self):
        path = self.node / 'bad-menu.json'
        text = '{\n "v": 1,\n bad\n}'
        path.write_text(text)
        p = self.run_menu(menu=path, rc=2)
        self.assertIn(str(path) + ' 第 3 行第 2 字不是合法 JSON', p.stderr)
        self.assertNotIn('不在', p.stderr)
        self.assertEqual(path.read_text(), text)

    def test_invalid_practice_json_reports_location_and_keeps_file(self):
        menu = self.fixture(simple())
        path = menu.parent / 'practice.json'
        path.write_text('{\n ?\n}')
        p = self.run_menu(menu=menu, rc=2)
        self.assertIn(str(path) + ' 第 2 行第 2 字不是合法 JSON', p.stderr)
        self.assertNotIn('不在', p.stderr)
        self.assertEqual(path.read_text(), '{\n ?\n}')

    def test_missing_menu_file_reports_missing(self):
        path = self.node / 'missing-menu.json'
        p = self.run_menu(menu=path, rc=2)
        self.assertIn(str(path) + ' 不在', p.stderr)
        self.assertNotIn('不是合法 JSON', p.stderr)

    def test_help_options_have_descriptions(self):
        for command, options in [('run', ['--llm', '--reply', '--run', '--var', '--brief']),
                                 ('status', ['--run', '--prompt'])]:
            p = self.cli(command, '--help')
            lines = p.stdout.splitlines()
            for option in options:
                with self.subTest(command=command, option=option):
                    line = next(x for x in lines if x.strip().startswith(option))
                    self.assertRegex(line.strip(), r'\s{2,}\S')

    def test_status_stopped_is_zero_but_run_is_one(self):
        menu = self.fixture(simple(), ['選：2'])
        self.run_menu(menu=menu, rc=1)
        before = self.state('test')
        self.assertIn('停下', self.cli('status', self.node).stdout)
        p = self.cli('status', self.node, '--prompt')
        self.assertIn('停下', p.stdout)
        self.assertIn('這個 run 已停下，沒有正在等回答的提示', p.stdout)
        self.run_menu(menu=menu, rc=1)
        self.assertEqual(self.state('test'), before)

    def test_status_missing_and_broken_state_codes(self):
        self.cli('status', self.node, rc=1)
        menu = self.fixture(simple())
        self.run_menu(menu=menu)
        path = self.node / 'menu/test/state.json'
        path.write_text('{壞掉')
        self.cli('status', self.node, rc=3)
        self.assertEqual(path.read_text(), '{壞掉')
