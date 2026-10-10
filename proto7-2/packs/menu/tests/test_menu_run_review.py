"""第二輪：own-state、run 鎖、未結帳與真實動作崩潰窗口。"""
import contextlib
import copy
import fcntl
import io
import signal
import sys
import time
from unittest.mock import patch
from menucase import MenuCase, simple, TOOLS, write_json, read_json
import aos7_menu_run as driver
from aos7_menu import load, new_state
from aos7_menu_io import Stop


class MenuRunReview(MenuCase):
    def walking(self):
        menu = self.fixture(simple())
        reply = self.node / 'reply'
        reply.write_text('不像')
        self.run_menu('--reply', reply, menu=menu)
        return menu, self.node / 'menu/test/state.json'

    def test_bad_state_fields_preserved(self):
        menu, path = self.walking()
        original = self.state('test')
        cases = [dict(initial_vars=[]), dict(pending={'call_id': 'menu/test/other/1', 'layer': 'other'}),
                 dict(pending={'act': {'tool': 'check', 'args': {}}}),
                 dict(pending={'act': {'write': 'out/x', 'text': 'x'}, 'next': 'end'}),
                 dict(pending={'act': {'check': 'check', 'text': 'x'}, 'then': {'next': 'end'}}),
                 dict(vars={}), dict(var_owner={'run': 'check'})]
        for change in cases:
            with self.subTest(change=change):
                write_json(str(path), dict(original, **change))
                raw = path.read_bytes()
                self.run_menu('--var', 'x=y', menu=menu, rc=3)
                self.assertEqual(path.read_bytes(), raw)
        for key in ('pending', 'why', 'var_owner'):
            with self.subTest(missing=key):
                state = copy.deepcopy(original)
                del state[key]
                write_json(str(path), state)
                raw = path.read_bytes()
                self.run_menu(menu=menu, rc=3)
                self.assertEqual(path.read_bytes(), raw)

    def test_pending_write_unsafe_path_rejected_but_frozen_missing_var_resumes(self):
        obj = simple({'max_lines': 1})
        obj['layers']['one']['do']['write'] = 'out/{file}'
        menu = self.fixture(obj)
        reply = self.node / 'reply'
        reply.write_text('不像')
        self.run_menu('--reply', reply, '--var', 'file=reply.txt', menu=menu)
        path = self.node / 'menu/test/state.json'
        original = self.state('test')
        for missing in (False, True):
            state = copy.deepcopy(original)
            state['pending'] = {'act': {'write': 'out/../escape' if not missing else 'out/reply.txt', 'text': 'x'}, 'next': 'end'}
            if missing:
                del state['vars']['file']
            write_json(str(path), state)
            raw = path.read_bytes()
            self.run_menu(menu=menu, rc=0 if missing else 3)
            if missing:
                self.assertEqual(self.state('test')['done'], ['reply.txt'])
            else:
                self.assertEqual(path.read_bytes(), raw)

    def test_checked_slot_keeps_frozen_write_when_vars_change(self):
        obj = simple({'tool': 'check'})
        obj['layers']['one']['do']['write'] = 'out/{file}'
        menu = load(obj, TOOLS)
        state = new_state(menu, 'test', {'file': 'original', 'node': str(self.node), 'run_dir': str(self.node / 'menu/test')}, '', 'hash')
        state.update(initial_vars={'file': 'original'}, journal=[])
        state['vars']['file'] = 'other'
        state['pending'] = {'act': {'write': 'out/original', 'text': 'text'}, 'next': 'end'}
        self.assertTrue(driver.valid_state(state, menu))

    def test_bad_state_json_tells_repair_or_abandon(self):
        menu, path = self.walking()
        path.write_text('{秘密壞檔')
        for command in [('run', self.node, menu), ('status', self.node, '--run', 'test')]:
            p = self.cli(*command, rc=3)
            self.assertIn('test 的 state.json 讀不出來（原檔留著）', p.stderr)
            self.assertIn('要接續就把它修回合法 JSON', p.stderr)
            self.assertIn('要放棄就刪掉 ' + str(path.parent) + '/', p.stderr)
            self.assertIn('或換 --run 重走', p.stderr)
            self.assertEqual(path.read_text(), '{秘密壞檔')

    def test_run_lock_returns_quickly(self):
        menu, path = self.walking()
        raw = path.read_bytes()
        with open(str(path) + '.lock', 'a') as lk:
            fcntl.flock(lk, fcntl.LOCK_EX)
            start = time.monotonic()
            p = self.run_menu(menu=menu, rc=3, wait=2)
            self.assertLess(time.monotonic() - start, 2)
        self.assertIn('另一個 aos7-menu 正在走這個 run。等它結束再跑', p.stderr)
        self.assertEqual(path.read_bytes(), raw)

    def test_unsettled_picks_warn_once_even_when_later_error(self):
        obj = simple()
        obj['layers']['one']['options'][0]['next'] = 'two'
        obj['layers']['two'] = copy.deepcopy(simple()['layers']['one'])
        menu = self.fixture(obj)
        for name, replies, expected in [('ok', [('選：1', 1, 4)] * 2, 0),
                                        ('err', [('選：1', 1, 4), Stop(3, '後來不確定')], 3)]:
            with self.subTest(run=name):
                stderr, stdout = io.StringIO(), io.StringIO()
                with patch.object(driver, 'ai', side_effect=replies), contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(stdout):
                    rc = driver.main(['run', str(self.node), str(menu), '--run', name])
                self.assertEqual(rc, expected)
                self.assertEqual(len(stderr.getvalue().splitlines()), 1)
                self.assertIn('帳還沒結清', stderr.getvalue())
                picks = [r for r in self.logs(name) if r['kind'] == 'pick']
                self.assertTrue(picks)
                self.assertTrue(all(r.get('unsettled') is True for r in picks))

    def counting_tool(self):
        script, counter = self.node / 'count.py', self.node / 'counter'
        script.write_text("import pathlib,sys\np=pathlib.Path(sys.argv[1])\np.write_text(str(int(p.read_text())+1 if p.exists() else 1))\nprint('{}')\n")
        tools = self.node / 'tools.json'
        write_json(str(tools), {'v': 1, 'tools': {'count': {'argv': [sys.executable, '-B', str(script), str(counter)],
                   'args': ['path'], 'out': 'json-line', 'timeout': 3}}})
        return counter, {'AOS7_MENU_TOOLS': str(tools)}

    def action_crash(self, checking):
        counter, env = self.counting_tool()
        obj = simple({'tool': 'count'} if checking else {'max_lines': 1})
        if not checking:
            obj['layers']['one']['next'] = 'send'
            obj['layers']['send'] = {'do': {'tool': 'count', 'args': {'path': 'unused'}}, 'ok': 'end'}
        menu = self.fixture(obj, ['選：1\n格：內容'])
        layer = 'one' if checking else 'send'
        self.ledger()
        pending = None
        for killed in range(1, 4):
            self.run_menu('--llm', 'fake', menu=menu, env=dict(env, AOS7_TEST_CRASH='menu-act:' + layer), rc=-signal.SIGKILL)
            state = self.state('test')
            self.assertEqual(int(counter.read_text()), killed)
            self.assertIsNotNone(state['pending'])
            self.assertEqual(len(state['done']), len(set(state['done'])))
            self.assertEqual(len(state['calls']), 1)
            self.assertIn('check' if checking else 'tool', state['pending']['act'])
            if pending is not None:
                self.assertEqual(state['pending'], pending)
            pending = state['pending']
        self.run_menu('--llm', 'fake', menu=menu, env=env)
        state = self.state('test')
        self.assertEqual(int(counter.read_text()), 4)
        self.assertEqual(state['done'], ['reply.txt'])
        self.assertEqual(state['status'], 'done')
        self.assertEqual(len(state['calls']), 1)
        sends = read_json(str(self.node / 'llmcall/fake-remote.json'))['sends']
        self.assertEqual(list(sends.values()), [1])

    def test_crash_finished_tool_before_state_three(self):
        self.action_crash(False)

    def test_crash_finished_slot_check_before_state_three(self):
        self.action_crash(True)

    def test_prompt_reads_only_show_file(self):
        obj = simple()
        obj['layers']['one']['show'] = 'out/visible.txt'
        obj['layers']['hidden'] = dict(simple()['layers']['one'], show='out/other.txt')
        menu = load(obj, TOOLS)
        state = new_state(menu, 'test', {}, '', 'hash')
        state['done'] = ['secret.txt']
        directory = self.node / 'menu/test'
        out = directory / 'out'
        out.mkdir(parents=True)
        (out / 'secret.txt').write_text('已交秘密內容不可附')
        (out / 'other.txt').write_text('另一個 show 秘密不可附')
        (out / 'visible.txt').write_text('只准附這檔')
        text = driver.prompt(menu, state, directory)
        self.assertIn('已交：secret.txt', text)
        self.assertIn('只准附這檔', text)
        self.assertNotIn('已交秘密內容不可附', text)
        self.assertNotIn('另一個 show 秘密不可附', text)
