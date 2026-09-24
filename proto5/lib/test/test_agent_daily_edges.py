"""等待條件、暫態損壞與錯誤訊息的邊界。"""
import io
import os
import unittest
from unittest.mock import patch

import aos_agent as agent
import aos_agent_pause as pause_api
import aos_agent_say as say
import aos_agent_status as status
import aos_llm_call as llm
from aos_agent_home import AgentError
import test_agent_tick as fixture


class DailyEdgeTests(unittest.TestCase):
    for _name in ('setUp', 'put', 'read'):
        locals()[_name] = getattr(fixture.AgentTickTests, _name)

    def test_default_directory_all_daily_commands(self):
        old = os.getcwd()
        os.chdir(self.base)
        self.addCleanup(os.chdir, old)
        with patch.dict(os.environ, {}, clear=True), patch('sys.stdout', new_callable=io.StringIO):
            self.assertEqual(agent.main(['status']), 0)
            self.assertEqual(agent.main(['continue']), 0)
            self.assertEqual(agent.main(['say', '你好']), 0)
            self.put(self.base / 'prompts/history.json', [fixture.MESSAGE])
            self.assertEqual(agent.main(['listen']), 0)
            (self.base / 'info.json').unlink()
            self.assertEqual(agent.main(['init']), 0)

    def test_help_all_commands(self):
        with patch('sys.stdout', new_callable=io.StringIO) as out, self.assertRaises(SystemExit) as cm:
            agent.main(['--help'])
        self.assertEqual(cm.exception.code, 0)
        for word in ('tick', 'start', 'stop', 'listen', 'init', 'say', 'status', 'pause', 'continue', '解除手動暫停與連敗暫停'):
            self.assertIn(word, out.getvalue())

    def registered(self):
        """fix-r4（astra 審查）：先登記、kernel 健康，等待條件的反例才會真的走到「等」而不是「沒登記」。"""
        self.put(self.base / 'tick.json', {'envs': self.env})
        self.put(self.k / 'state.json', {'procs': {'agent-bob': {'status': 'idle', 'fails': 0}}, 'replies': []})
        health = patch('aos_kernel_health.health', return_value=('ok', 'ok'))
        health.start()
        self.addCleanup(health.stop)

    def test_wait_retries_partial_state_and_history(self):
        self.registered()
        self.put(self.base / 'input.json', {'role': 'user', 'content': '舊的'})
        loops = []
        def advance(_):
            loops.append(True)
            if len(loops) == 1:
                (self.base / 'input.json').rename(self.base / 'old.done')
                (self.base / 'state.json').write_text('{')
                self.put(self.base / 'prompts/history.json', [])
            elif len(loops) == 2:
                self.put(self.base / 'state.json', {})
                (self.base / 'prompts/history.json').write_text('{')
            else:
                self.put(self.base / 'prompts/history.json',
                         [{'role': 'user', 'content': '你好'}, fixture.MESSAGE])
        def deliver(base, value, text):
            return self.base / 'input.json'
        with patch.object(say.time, 'sleep', side_effect=advance), patch.object(say, 'deliver', side_effect=deliver), \
                patch('sys.stdout', new_callable=io.StringIO) as out:
            self.assertEqual(say.say(self.base, '你好', wait=True, timeout_ms=5000, env={}), 0)
        self.assertEqual(out.getvalue(), '完成\n')
        self.assertEqual(len(loops), 3)

    def test_wait_requires_every_completion_condition(self):
        self.registered()
        user = {'role': 'user', 'content': '你好'}
        cases = [({'state': 'think'}, [user, fixture.MESSAGE], True),
                 ({'intake': {'id': 'x', 'base_len': 0, 'files': []}}, [user, fixture.MESSAGE], True),
                 ({}, [dict(user, content='別題'), fixture.MESSAGE], True),
                 ({}, [fixture.MESSAGE, user], True),
                 ({}, [user, fixture.MESSAGE], False),
                 ({'batch': {'kind': 'act', 'kernel': str(self.k), 'base_len': 0, 'sent': True,
                             'calls': []}}, [user, fixture.MESSAGE], True)]
        for state, history, consumed in cases:
            with self.subTest(state=state, history=history, consumed=consumed):
                self.put(self.base / 'state.json', {})
                self.put(self.base / 'prompts/history.json', [])
                def posted(*args):
                    target = self.base / 'input.json'
                    if consumed:
                        target.unlink(missing_ok=True)
                    else:
                        self.put(target, user)
                    self.put(self.base / 'state.json', state)
                    self.put(self.base / 'prompts/history.json', history)
                    return target
                self.err.truncate(0), self.err.seek(0)
                with patch.object(say, 'deliver', side_effect=posted), patch('sys.stdout', new_callable=io.StringIO):
                    self.assertEqual(say.say(self.base, '你好', wait=True, timeout_ms=0, env={}), 101)
                self.assertIn('Timeout:', self.err.getvalue())
                self.assertNotIn('unregistered', self.err.getvalue())
        # 對照組：條件全齊就成功，證明上面每一例是被那一個條件擋住。
        consumed_state, history = {}, [user, fixture.MESSAGE]
        def complete(*args):
            self.put(self.base / 'state.json', consumed_state)
            self.put(self.base / 'prompts/history.json', history)
            return self.base / 'input.json'
        self.put(self.base / 'prompts/history.json', [])
        with patch.object(say, 'deliver', side_effect=complete), patch('sys.stdout', new_callable=io.StringIO):
            self.assertEqual(say.say(self.base, '你好', wait=True, timeout_ms=0, env={}), 0)

    def test_wait_does_not_match_user_before_initial_length(self):
        self.registered()
        self.put(self.base / 'prompts/history.json', [{'role': 'user', 'content': '你好'}, fixture.MESSAGE])
        def posted(*args):
            return self.base / 'already-consumed.json'
        with patch.object(say, 'deliver', side_effect=posted), patch('sys.stdout', new_callable=io.StringIO):
            self.assertEqual(say.say(self.base, '你好', wait=True, timeout_ms=0, env={}), 101)
        self.assertIn('Timeout:', self.err.getvalue())

    def test_wait_arrived_pause_with_other_closed_gate_is_timeout(self):
        self.put(self.base / 'continue-ok.json', {})
        self.put(self.base / 'state.json', {'waits': [{'$opt': 'consume', '$val': ['continue-ok.json', 'external']}]})
        with patch('sys.stdout', new_callable=io.StringIO):
            self.assertEqual(say.say(self.base, '你好', wait=True, timeout_ms=0, env={}), 101)
        self.assertIn('unregistered:', self.err.getvalue())
        self.assertNotIn('stuck:', self.err.getvalue())

    def test_input_directive_and_existing_directory(self):
        (self.base / 'inbox').mkdir()
        self.put(self.base / 'state.json', {'input': {'$env': 'DROP'}})
        with patch('sys.stdout', new_callable=io.StringIO):
            self.assertEqual(say.say(self.base, '你好', env={'DROP': 'inbox'}), 0)
        self.assertEqual(len(list((self.base / 'inbox').glob('*.json'))), 1)

    def test_status_batch_counts(self):
        self.put(self.base / 'state.json', {'batch': {'kind': 'act', 'kernel': str(self.k),
            'sent': True, 'base_len': 0, 'calls': [
                {'name': None, 'done': {'content': '失敗'}, 'acked': True, 'tool': 'x', 'tool_call_id': 'a'},
                {'name': 'b', 'done': None, 'acked': False, 'tool': 'x', 'tool_call_id': 'b'}]}})
        self.assertEqual(status.collect(self.base, {})['batch'],
                         dict(kind='act', sent=True, total=2, sent_n=1, done_n=1))

    def test_continue_multiple_resolved_paths(self):
        self.put(self.base / 'state.json', {'waits': {'$opt': 'consume', '$val': {'$env': 'GO'}}})
        with patch('sys.stdout', new_callable=io.StringIO):
            self.assertEqual(pause_api.resume(self.base, {'GO': 'continue-one.json'}), 0)
        self.assertTrue((self.base / 'continue-one.json').exists())

    def test_last_bad_fallback_preserves_original_error(self):
        (self.base / 'info.json').write_text('{')
        self.put(self.base / 'prompts/history.json', {})
        with patch('sys.stdout', new_callable=io.StringIO):
            self.assertEqual(agent.main(['listen', '--target', str(self.base)]), 1)
        self.assertIn('JsonSyntax', self.err.getvalue())

    def test_engine_error_redacts_echoed_key(self):
        entry = dict(endpoint='http://localhost/v1', model='real', api_key='secret-key', timeout_ms=1)
        for code in ('EngineFailed', 'Timeout'):
            with self.subTest(code=code), patch.object(llm, '_post_http', side_effect=AgentError(code, 'secret-key 失敗')):
                with self.assertRaises(AgentError) as cm:
                    llm._post({'model': 'real'}, entry, 'default')
            self.assertNotIn('secret-key', str(cm.exception))
            self.assertIn('（endpoint http://localhost/v1，模型 default→real）', str(cm.exception))
