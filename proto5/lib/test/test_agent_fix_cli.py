"""fix-r1：登記輸出、免設定停止、最後回話。"""
import copy
import io
import os
import unittest
from unittest.mock import patch

import aos_agent as agent
import test_agent_tick as fixture


class AgentFixCliTests(unittest.TestCase):
    for _name in ('setUp', 'put', 'read', 'kernel_thread', 'register'):
        locals()[_name] = getattr(fixture.AgentTickTests, _name)

    def test_registration_stdout(self):
        for starting, expected in ((True, 'started agent-bob\n'), (False, 'stopped agent-bob\n')):
            with self.subTest(starting=starting), patch('sys.stdout', new_callable=io.StringIO) as out:
                self.assertEqual(self.register(starting)[0], 0)
                self.assertEqual(out.getvalue(), expected)

    def test_stop_broken_info(self):
        for mode in ('llm', 'tools', 'missing_tick', 'folder_only', 'history'):
            with self.subTest(mode=mode):
                info = copy.deepcopy(self.info)
                self.put(self.base / 'tick.json', {'envs': self.env})
                if mode == 'llm':
                    del info['llm']
                elif mode == 'tools':
                    info['tools'] = ['broken.json']
                    (self.base / 'broken.json').write_text('{')
                elif mode == 'history':
                    info['history'] = 'bad-history.json'
                    self.put(self.base / 'bad-history.json', {})
                self.put(self.base / 'info.json', info)
                if mode in ('missing_tick', 'folder_only'):
                    (self.base / 'info.json').unlink()
                if mode == 'folder_only':
                    (self.base / 'tick.json').unlink()
                self.assertEqual(self.register(False)[0], 0)

    def test_stop_ignores_unreadable_tick(self):
        for value in ('{', '[]', '{"envs": []}', '{"envs":{"AOS_KERNEL_HOME":{"$env":"K"}}}'):
            with self.subTest(value=value):
                (self.base / 'tick.json').write_text(value)
                self.assertEqual(self.register(False)[0], 0)

    def test_stop_mismatch(self):
        self.put(self.base / 'tick.json', {'envs': {'AOS_KERNEL_HOME': '/other/K'}})
        self.assertEqual(agent.stop(self.base, self.env), 1)
        self.assertIn('KernelMismatch', self.err.getvalue())
        self.assertIn(str(self.base / 'tick.json') + ' 綁在 /other/K', self.err.getvalue())
        self.assertFalse(list((self.k / 'requests').iterdir()))

    def test_stop_directory_and_environment_required(self):
        for path in (self.root / 'absent', self.base / 'info.json'):
            self.assertEqual(agent.stop(path, self.env), 1)
            self.assertIn('NotAnAgent', self.err.getvalue())
        self.assertEqual(agent.stop(self.base, {}), 2)

    def test_stop_kernel_not_found(self):
        result, _ = self.register(False, {'code': -32602, 'data': {'code': 'NotFound'}, 'message': '不在'})
        self.assertEqual(result, 1)
        self.assertIn('NotFound', self.err.getvalue())

    def test_start_stop_same_path_names(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.base, target_is_directory=True)
        for path in (str(self.base), str(self.base) + '/', os.path.relpath(self.base), '.', str(alias)):
            with self.subTest(path=path):
                previous = os.getcwd()
                if path == '.':
                    os.chdir(self.base)
                try:
                    names = []
                    def response(kernel, name, **kwargs):
                        req = self.read(self.k / 'requests' / name)
                        names.append(req['params']['name'])
                        return {'result': {'name': names[-1]}}
                    with patch('aos_client.wait_response', side_effect=response):
                        self.assertEqual(agent.start(path, self.env), 0)
                        self.assertEqual(agent.stop(path, self.env), 0)
                    self.assertEqual(names, ['agent-' + ('alias' if path == str(alias) else 'bob')] * 2)
                finally:
                    os.chdir(previous)

    def last(self, history, *flags):
        self.info['history'] = 'memory/custom.json'
        self.put(self.base / 'info.json', self.info)
        self.put(self.base / 'memory/custom.json', history)
        with patch.dict(os.environ, {}, clear=True), patch('sys.stdout', new_callable=io.StringIO) as out:
            code = agent.main(['listen', '--target', str(self.base), '--last', *flags])
        return code, out.getvalue()

    def test_last_text(self):
        messages = [dict(fixture.MESSAGE, content='舊'), dict(fixture.MESSAGE, content=' 新\n回話 '),
                    {'role': 'user', 'content': '下一題'}]
        self.assertEqual(self.last(messages), (0, ' 新\n回話 \n'))

    def test_last_tool_calls(self):
        for content in (None, ''):
            message = dict(fixture.ASSISTANT, content=content)
            message['tool_calls'] = [fixture.TOOL_CALL, dict(fixture.TOOL_CALL, id='c2',
                                      function={'name': '另一個', 'arguments': ''})]
            self.assertEqual(self.last([message]), (0, '(tool_calls: sh, 另一個)\n'))

    def test_last_json(self):
        import json
        message = dict(fixture.MESSAGE, reasoning_content='保留')
        code, output = self.last([message], '--json')
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output), message)
        self.assertIn('保留', output)
        self.assertEqual(len(output.splitlines()), 1)

    def test_last_not_found(self):
        for history in ([], [{'role': 'user', 'content': '你好'}]):
            self.assertEqual(self.last(history), (1, ''))
            self.assertIn('aos-agent: NotFound: 記憶裡還沒有 assistant 的回話', self.err.getvalue())

    def test_last_bad_info(self):
        del self.info['llm']
        self.assertEqual(self.last([fixture.MESSAGE]), (1, ''))
        self.assertIn('LlmInvalid', self.err.getvalue())

    def test_json_only_last(self):
        for command in ('tick', 'start', 'stop'):
            with self.assertRaises(SystemExit) as cm:
                agent.main([command, '--target', str(self.base), '--json'])
            self.assertEqual(cm.exception.code, 2)
