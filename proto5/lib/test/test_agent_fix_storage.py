"""fix-r1：封存相容性及可定位的診斷。"""
import copy
import unittest
from unittest.mock import patch

import aos_agent_home as home
import test_agent_tick as fixture


class AgentFixStorageTests(unittest.TestCase):
    for _name in ('setUp', 'put', 'read', 'state', 'tick', 'prepare', 'respond', 'output', 'crash_at'):
        locals()[_name] = getattr(fixture.AgentTickTests, _name)

    def test_input_done_directory_created_or_existing(self):
        for existing in (False, True):
            with self.subTest(existing=existing):
                if existing:
                    self.assertTrue((self.base / 'done').is_dir())
                self.put(self.base / 'state.json', {})
                self.put(self.base / 'input.json', '新訊息')
                self.assertEqual(self.tick(), 0)
                self.assertEqual(len(list((self.base / 'done').glob('input.json.*.done'))), 1 + existing)
                self.assertFalse((self.base / 'input.json').exists())

    def test_directory_input_archives_locally_and_ignores_subdirs(self):
        for directory in ('inbox', 'other'):
            self.put(self.base / directory / 'a.json', directory)
            self.put(self.base / directory / 'done/old.json', '不收')
            self.put(self.base / directory / 'sub.json/hidden.json', '不收')
        self.put(self.base / 'state.json', {'input': ['inbox', 'other']})
        self.assertEqual(self.tick(), 0)
        for directory in ('inbox', 'other'):
            self.assertEqual(len(list((self.base / directory / 'done').glob('a.json.*.done'))), 1)
        self.assertEqual([m['content'] for m in self.read(self.base / 'prompts/history.json')], ['inbox', 'other'])
        self.put(self.base / 'state.json', {'input': 'inbox', 'waits': ['inbox']})
        self.assertEqual(self.tick(), 101)
        self.assertEqual(self.state()['waits'], ['inbox'])

    def test_continue_consumed_into_done(self):
        self.prepare(done={'fail': '錯', 'count': True}, acked=True, errors=2)
        self.assertEqual(self.tick(), 0)
        signal = self.state()['waits'][0]['$val']
        self.assertIn('touch %s 繼續' % (self.base / signal), self.err.getvalue())
        self.assertNotIn('/', signal)
        (self.base / signal).touch()
        self.assertEqual(self.tick(), 0)
        self.assertEqual(len(list((self.base / 'done').glob(signal + '.*.done'))), 1)

    def test_legacy_intake_move_and_read(self):
        src, dst = self.base / 'input.json', self.base / 'input.json.old.done'
        self.put(src, '舊格式恢復')
        self.put(self.base / 'state.json', {'intake': {'id': 'old', 'base_len': 0,
                 'files': [{'src': str(src), 'dst': str(dst)}]}})
        self.assertEqual(self.tick(), 0)
        self.assertTrue(dst.exists())
        self.assertFalse((self.base / 'done').exists())
        self.assertEqual(self.read(self.base / 'prompts/history.json')[0]['content'], '舊格式恢復')

    def test_tool_directory_ignores_done_and_subdirs(self):
        self.put(self.base / 'tools/a.json', [fixture.TOOL])
        self.put(self.base / 'tools/done/invalid.json', {})
        self.put(self.base / 'tools/sub.json/invalid.json', {})
        self.assertEqual(home.read_tools(home._expand_tools([str(self.base / 'tools')])), [fixture.TOOL])

    def failure(self, **change):
        name = self.prepare()
        self.respond(name, result=dict(fixture.RESULT, **change))
        with self.crash_at('state.done'), self.assertRaises(fixture.Crash):
            self.tick()
        fail = self.state()['batch']['calls'][0]['done']['fail']
        self.assertEqual(self.tick(), 0)
        self.assertIn('aos-agent: engine: ' + fail, self.err.getvalue())
        return fail

    def test_llm_exit_log_last_nonempty_and_limit(self):
        path = self.base / 'log/llm.err'
        path.parent.mkdir()
        path.write_text('舊錯誤\n\n' + '錯' * 350 + '\n \n')
        self.assertEqual(self.failure(code=7), 'aos-llm call exit 7，看 %s：%s' % (path, '錯' * 300))

    def test_llm_timeout_log_path_and_tail(self):
        path = self.base / 'log/llm.err'
        path.parent.mkdir()
        path.write_text('連線失敗\n\n')
        self.assertEqual(self.failure(timed_out=True), '逾時（125000 ms，是 info.llm.timeout_ms；要更久就改 agent 的 info.json；llm.err 在 %s）' % path)

    def test_llm_log_empty_missing_unreadable(self):
        path = self.base / 'log/llm.err'
        for mode in ('missing', 'empty', 'unreadable'):
            with self.subTest(mode=mode):
                if mode == 'empty':
                    path.parent.mkdir()
                    path.write_text(' \n')
                elif mode == 'unreadable':
                    path.unlink()
                    path.mkdir()
                self.assertEqual(self.failure(code=1), 'aos-llm call exit 1，看 %s' % path)

    def test_llm_aos_pool_cpu_paths_use_batch_kernel(self):
        self.put(self.k / 'info.json', {'cpus': {'l1': {'pool': 'llm'}, 'l2': {'pool': 'llm'}, 'x': {}}})
        self.env['AOS_KERNEL_HOME'] = str(self.root / 'otherK')
        fail = self.failure(kind='aos', code=125)
        self.assertIn(str(self.k / 'cpus/l1/cpu.log'), fail)
        self.assertIn(str(self.k / 'cpus/l2/cpu.log'), fail)
        self.assertNotIn('/cpus/x/', fail)
        self.assertNotIn('/otherK/', fail)

    def test_llm_aos_cpu_fallback(self):
        for raw in ('{}', '{', '[]', '{"cpus": []}'):
            (self.k / 'info.json').write_text(raw)
            self.assertIn(str(self.k / 'cpus/*/cpu.log'), self.failure(kind='aos', code=125))

    def test_tool_exec_failure_argv_and_cwd(self):
        for code in (126, 127):
            for argv0 in ('./bin/tool', 'tool', '/abs/bin/tool', None):
                with self.subTest(code=code, argv0=argv0):
                    name = self.prepare('act')
                    path = self.base / 'work' / (name + '.inst.json')
                    path.unlink(missing_ok=True)
                    if argv0 is not None:
                        self.put(path, {'argv': [argv0], 'cwd': {'$opt': 'mkdir', '$val': str(self.base / 'sub')}})
                    self.respond(name, result=dict(fixture.RESULT, code=code))
                    self.output(name, '輸出')
                    with self.crash_at('state.done'), self.assertRaises(fixture.Crash):
                        self.tick()
                    content = self.state()['batch']['calls'][0]['done']['content']
                    self.assertIn('argv[0]=' + (argv0 or '?'), content)
                    self.assertIn('找不到程式' if code == 127 else '看有沒有執行權限、是不是可執行檔', content)
                    self.assertIn('輸出', content)
                    if argv0 and not argv0.startswith('/'):
                        self.assertIn('相對 cwd ' + str(self.base / 'sub'), content)
                        self.assertIn('PATH', content)
                    else:
                        self.assertNotIn('相對 cwd', content)

    def test_toolinvalid_element_paths(self):
        invalid = [None, {}, dict(fixture.TOOL, function={}),
                   dict(fixture.TOOL, function={'name': 'x', 'description': 1}),
                   dict(fixture.TOOL, function={'name': 'x', 'parameters': []}),
                   dict(fixture.TOOL, _meta=None), dict(fixture.TOOL, _meta={'stdout': 'x'}),
                   dict(fixture.TOOL, _timeout_ms=True)]
        path = self.base / 'tools.json'
        for tool in invalid:
            with self.subTest(tool=tool):
                self.put(path, [fixture.TOOL, tool])
                with self.assertRaises(home.AgentError) as cm:
                    home.read_tools([str(path)])
                self.assertEqual(cm.exception.code, 'ToolInvalid')
                self.assertIn('%s 第 1 個元素：' % path, cm.exception.msg)

    def test_toolinvalid_duplicate_both_origins(self):
        a, b = self.base / 'a.json', self.base / 'b.json'
        self.put(a, [fixture.TOOL])
        self.put(b, [dict(fixture.TOOL, function={'name': 'other'}), fixture.TOOL])
        with self.assertRaises(home.AgentError) as cm:
            home.read_tools([str(a), str(b)])
        self.assertEqual(cm.exception.msg, '合併後工具同名：sh（%s 第 0 個、%s 第 1 個）' % (a, b))
