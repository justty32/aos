"""驅動契約：練習十圈、人手接續、故障退出與 SIGKILL 恢復。"""
import copy
import json
import signal
import sys
from menucase import MenuCase, HELLO, PACK, read_json, write_json, simple


class MenuRun(MenuCase):
    def setUp(self):
        super().setUp()
        obj = simple({'max_lines': 1})
        obj.update(name='hello', start='who')
        obj['layers']['line'] = obj['layers'].pop('one')
        obj['layers']['line'].update(ask='{to} 的回信', next='send')
        obj['layers']['who'] = {'ask': '收件人', 'exit': {'text': '交回'}, 'options': [
            {'text': '甲', 'set': {'to': '甲'}, 'next': 'line'},
            {'text': '乙', 'set': {'to': '乙'}, 'next': 'line'}]}
        obj['layers']['send'] = {'do': {'tool': 'hello-send', 'args': {'to': '{to}'}}, 'ok': 'end'}
        self.menu = self.fixture(obj, ['選：1', '不像回法', '選：1\n格：收到了'])

    def run_menu(self, *extra, menu=None, **kw):
        return super().run_menu(*extra, menu=menu or self.menu, **kw)

    def assert_finished(self, name='hello'):
        state = self.state(name)
        self.assertEqual(state['status'], 'done')
        self.assertEqual(len(state['done']), len(set(state['done'])))
        run = self.node / 'menu' / name
        reply = (run / 'out/reply.txt').read_text().rstrip()
        self.assertEqual((run / 'out/sent.txt').read_text().rstrip(), '給 %s：%s' % (state['vars']['to'], reply))
        log = self.logs(name)
        self.assertEqual([x['step'] for x in log], list(range(1, len(log) + 1)))
        self.assertIn('bad', [x['kind'] for x in log])
        self.assertEqual(log[-1]['kind'], 'done')
        self.assertTrue({'ask', 'pick', 'write', 'tool'}.issubset({x['kind'] for x in log}))

    def test_practice_example_reads_current_files(self):
        obj = read_json(str(HELLO))
        practice = read_json(str(HELLO.parent / 'practice.json'))
        self.assertIsInstance(obj, dict)
        self.assertIsInstance(practice['replies'], list)
        self.run_menu('--run', 'example', menu=HELLO)
        state = self.state('example')
        self.assertEqual(state['status'], 'done')
        self.assertLessEqual(len(state['calls']), len(practice['replies']))
        self.assertEqual(len(state['done']), len(set(state['done'])))
        out = self.node / 'menu/example/out'
        self.assertTrue(all((out / name).is_file() for name in state['done']))
        self.assertEqual((out / 'sent.txt').read_text().rstrip(),
                         '給 %s：%s' % (state['vars']['to'], (out / 'reply.txt').read_text().rstrip()))

    def test_practice_ten_runs_and_done_no_call(self):
        for i in range(10):
            name = 'hello%d' % i
            with self.subTest(run=name):
                self.run_menu('--run', name)
                self.assert_finished(name)
                before = (self.state(name), self.logs(name))
                p = self.run_menu('--run', name)
                self.assertIn('做完', p.stdout)
                self.assertEqual((self.state(name), self.logs(name)), before)

    def test_reply_status_walking_done_stuck(self):
        reply = self.node / 'reply'
        reply.write_text('選：1')
        p = self.run_menu('--reply', reply)
        self.assertIn(read_json(str(self.menu))['layers']['line']['ask'].split('{')[0], p.stdout)
        self.assertEqual(self.state()['layer'], 'line')
        p = self.cli('status', self.node)
        self.assertEqual(len(p.stdout.splitlines()), 1)
        self.assertIn('走到', p.stdout)
        self.run_menu()
        self.assertIn('做完', self.cli('status', self.node).stdout)
        reply.write_text('選：3')
        self.run_menu('--run', 'exit', '--reply', reply, rc=1)
        self.assertIn('停下', self.cli('status', self.node, '--run', 'exit').stdout)

    def test_invalid_menus_code_two(self):
        base = read_json(str(self.menu))
        edits = [lambda m: m['layers']['who'].update(options=m['layers']['who']['options'] * 3),
                 lambda m: m['layers']['who'].pop('exit'),
                 lambda m: m['layers']['who']['options'][0].update(next='missing'),
                 lambda m: m['layers']['line'].update(do={'shell': 'echo x'}),
                 lambda m: m['layers']['send']['do'].update(tool='unregistered')]
        for edit in edits:
            with self.subTest(edit=edits.index(edit)):
                obj = copy.deepcopy(base)
                edit(obj)
                self.run_menu('--run', 'invalid%d' % edits.index(edit), menu=self.fixture(obj), rc=2)

    def test_changed_menu_and_corrupt_state(self):
        menu = self.fixture(simple())
        reply = self.node / 'reply'
        reply.write_text('不像')
        self.run_menu('--reply', reply, menu=menu)
        saved = self.state('test')
        obj = read_json(str(menu))
        obj['layers']['one']['ask'] += '改過'
        write_json(str(menu), obj)
        self.run_menu(menu=menu, rc=2)
        self.assertEqual(self.state('test'), saved)
        write_json(str(menu), simple())
        path = self.node / 'menu/test/state.json'
        path.write_text('{壞掉')
        self.run_menu(menu=menu, rc=3)
        self.assertEqual(path.read_text(), '{壞掉')
        saved['pending'] = {'act': None}
        write_json(str(path), saved)
        raw = path.read_bytes()
        self.run_menu(menu=menu, rc=3)
        self.assertEqual(path.read_bytes(), raw)

    def test_tool_uncertain_then_resume(self):
        script = self.node / 'tool.py'
        marker = self.node / 'retry'
        script.write_text("import pathlib,sys,json\np=pathlib.Path(sys.argv[1])\n"
                          "if not p.exists():\n p.write_text('1');sys.exit(3)\nprint('{}')\n")
        tool = self.node / 'tools.json'
        write_json(str(tool), {'v': 1, 'tools': {'retry': {'argv': [sys.executable, str(script), str(marker)],
                   'args': [], 'out': 'json-line', 'timeout': 3}}})
        obj = simple()
        obj['layers']['one']['options'][0]['next'] = 'act'
        obj['layers']['act'] = {'do': {'tool': 'retry', 'args': {}}, 'ok': 'end'}
        menu = self.fixture(obj)
        env = {'AOS7_MENU_TOOLS': str(tool)}
        self.run_menu(menu=menu, env=env, rc=3)
        self.assertIsNotNone(self.state('test')['pending'])
        self.run_menu(menu=menu, env=env)
        self.assertEqual(self.state('test')['status'], 'done')

    def test_tool_bad_json_timeout_and_bad_args(self):
        for name, code, timeout, rc in [('badjson', "print('bad')", 3, 3),
                ('timeout', 'import time;time.sleep(1)', 0.02, 3), ('badargs', 'import sys;sys.exit(2)', 3, 2)]:
            with self.subTest(tool=name):
                tools = self.node / 'tools.json'
                write_json(str(tools), {'v': 1, 'tools': {name: {'argv': [sys.executable, '-c', code],
                    'args': [], 'out': 'json-line', 'timeout': timeout}}})
                obj = simple()
                obj['layers']['one']['options'][0]['next'] = 'act'
                obj['layers']['act'] = {'do': {'tool': name, 'args': {}}, 'ok': 'end'}
                self.run_menu('--run', name, menu=self.fixture(obj), rc=rc, env={'AOS7_MENU_TOOLS': str(tools)})

    def test_llm_fake_and_missing_ledger(self):
        self.run_menu('--llm', 'fake', rc=1)
        self.assertEqual(self.state()['status'], 'walking')   # 帳任務沒跑不算停下，起好後同一個 run 接續
        self.ledger()
        self.run_menu('--llm', 'fake')
        self.assert_finished()
        sends = read_json(str(self.node / 'llmcall/fake-remote.json'))['sends']
        self.assertTrue(sends)
        self.assertEqual(set(sends.values()), {1})
        self.assertEqual(sum(sends.values()), len(self.state()['calls']))

    def crash(self, point):
        self.ledger()
        pending = None
        for _ in range(3):
            self.run_menu('--llm', 'fake', rc=-signal.SIGKILL, env={'AOS7_TEST_CRASH': point})
            state = self.state()
            self.assertIsNotNone(state['pending'])
            if pending is not None:
                self.assertEqual(state['pending'], pending)
            pending = state['pending']
        self.run_menu('--llm', 'fake')
        self.assert_finished()
        sends = read_json(str(self.node / 'llmcall/fake-remote.json'))['sends']
        self.assertTrue(sends)
        self.assertEqual(set(sends.values()), {1})
        self.assertEqual(sum(sends.values()), len(self.state()['calls']))

    def test_crash_pending_three(self):
        self.crash('menu-pending')

    def test_crash_ai_three(self):
        self.crash('menu-ai')

    def test_crash_act_three(self):
        self.crash('menu-act')
