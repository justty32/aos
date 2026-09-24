"""r3：健康摘要、當前根因與未登記投遞；只用假家及 patch。"""
import io
import json
import os
import time
import unittest
from unittest.mock import patch

import aos_agent as agent
import aos_agent_say as say
import aos_agent_status as status
import test_agent_tick as fixture


class StatusR3Tests(unittest.TestCase):
    for _name in ('setUp', 'put', 'read'):
        locals()[_name] = getattr(fixture.AgentTickTests, _name)

    def registered(self, **values):
        self.put(self.base / 'tick.json', {'envs': self.env})
        self.put(self.k / 'state.json', {'procs': {'agent-bob': dict(status='idle', fails=0, **values)},
                                         'replies': []})

    def healthy(self):
        return patch('aos_kernel_health.health', return_value=('ok', 'ok'))

    def cli(self, *args):
        with patch.dict(os.environ, {}, clear=True), patch('sys.stdout', new_callable=io.StringIO) as out:
            code = agent.main(list(args))
        return code, out.getvalue()

    def log(self, content=None):
        path = self.base / 'log/agent.err'
        path.parent.mkdir(exist_ok=True)
        path.write_text(content or ('aos-agent: engine: Connection refused endpoint http://localhost:1234\n'
                                  'aos-agent: stuck: 問模型連敗 3 次，touch /long/continue-test.json 繼續\n'))
        return path

    def pause(self):
        self.put(self.base / 'state.json', {'state': 'think', 'errors': 0,
                 'waits': [{'$opt': 'consume', '$val': 'continue-test.json'}]})
        self.log()

    def test_pause_root_cause_and_verbose(self):
        self.registered()
        self.pause()
        with self.healthy():
            _, output = self.cli('status', '--target', str(self.base))
            _, verbose = self.cli('status', '--target', str(self.base), '-v')
        self.assertTrue(output.startswith('health 連敗暫停'))
        self.assertIn('error  Connection refused endpoint http://localhost:1234', output)
        self.assertIn('已連敗 3 次', output)
        self.assertNotIn('touch ', output)
        self.assertNotIn('errors 0', output)
        self.assertIn('touch ', verbose)
        self.assertIn('aos-agent: stuck: 問模型連敗 3 次', verbose)

    def test_recovered_history_and_timestamp(self):
        self.registered()
        path = self.log()
        os.utime(path, (1700000000, 1700000000))
        with self.healthy():
            _, output = self.cli('status', '--target', str(self.base))
            data = status.collect(self.base, {})
        self.assertTrue(output.startswith('health ok\n'))
        self.assertIn('error  （無）\n', output)
        self.assertRegex(output, r'last-error  （已恢復） \d\d-\d\d \d\d:\d\d:\d\d  stuck: ')  # fix-r5：標記在最前
        self.assertIsNone(data['current_error'])
        self.assertIsNotNone(data['last_error_time'])

    def test_streak_one_uses_latest_engine(self):
        self.put(self.base / 'state.json', {'errors': 1})
        self.log('aos-agent: engine: old\naos-agent: engine: new\n')
        _, output = self.cli('status', '--target', str(self.base))
        self.assertIn('error  new\n', output)
        self.assertIn('已連敗 1 次（3 次會暫停）', output)

    def test_stuck_uses_preceding_engine(self):
        self.pause()
        with self.log().open('a') as log:
            log.write('aos-agent: engine: later\n')
        self.assertIn('Connection refused', status.collect(self.base, {})['current_error'])

    def test_stuck_without_engine(self):
        self.pause()
        self.log('aos-agent: stuck: 問模型連敗 3 次，touch /x 繼續\n')
        data = status.collect(self.base, {})
        self.assertTrue(data['current_error'].startswith('aos-agent: stuck:'))
        self.assertNotIn('touch ', self.cli('status', '--target', str(self.base))[1])

    def test_health_unregistered_and_no_kernel(self):
        data = status.collect(self.base, {})
        self.assertEqual(data['health']['code'], 'unregistered')
        self.assertIn('kernel 從沒 start 過（沒設 AOS_KERNEL_HOME、也沒 tick.json）',
                      self.cli('status', '--target', str(self.base))[1])
        with self.healthy():
            self.assertEqual(status.collect(self.base, self.env)['health']['code'], 'unregistered')

    def test_health_priority_and_codes(self):
        self.registered()
        self.pause()
        for code in ('daemon', 'dirs', 'cpus', 'stall', 'broken', 'stopped'):
            with self.subTest(code=code), patch('aos_kernel_health.health', return_value=(code, '停機中' if code == 'stopped' else '原因')):
                data = status.collect(self.base, {})
                self.assertEqual(data['health']['code'], 'kernel')
                self.assertIn('kernel 停機中' if code == 'stopped' else 'kernel 家有問題', data['health']['message'])
        with self.healthy():
            self.assertEqual(status.collect(self.base, {})['health']['code'], 'paused')
            self.put(self.k / 'state.json', {'procs': {}, 'replies': []})
            self.assertEqual(status.collect(self.base, {})['health']['code'], 'unregistered')

    def test_bad_and_config(self):
        self.registered()
        self.put(self.k / 'state.json', {'procs': {'agent-bob': {'status': 'bad', 'fails': 2}}, 'replies': []})
        self.log('tick failed\n')
        with self.healthy():
            data = status.collect(self.base, {})
            self.assertEqual(data['health']['code'], 'bad')
            self.assertEqual(data['current_error'], 'tick failed')
            self.registered()
            for name in ('state.json', 'info.json'):
                (self.base / name).write_text('{')
                self.assertEqual(status.collect(self.base, {})['health']['code'], 'config')

    def test_tick_fails_are_current(self):
        self.registered()
        self.put(self.k / 'state.json', {'procs': {'agent-bob': {'status': 'idle', 'fails': 1}}, 'replies': []})
        self.log('tick failed\n')
        with self.healthy():
            self.assertIn('error  tick failed', self.cli('status', '--target', str(self.base))[1])

    def test_real_kernel_health_missing_directory(self):
        self.registered()
        # proto5-2：info.json 第 2 版是 pools 表（kernel-info.md），不是 cpus 表。
        self.put(self.k / 'info.json', {'_metainfo': {'_type': 'kernel', '_version': 2},
                 'pools': {'kernel': {'count': 1}}})
        (self.k / 'pools').mkdir()
        (self.k / 'requests').rmdir()
        data = status.collect(self.base, {})
        self.assertEqual(data['health']['code'], 'kernel')
        self.assertIn('K 家缺目錄', data['health']['message'])
        self.assertIn(str(self.k / 'requests'), data['health']['message'])

    def test_json_new_keys_and_old_last_error(self):
        self.pause()
        data = json.loads(self.cli('status', '--target', str(self.base), '--json')[1])
        self.assertTrue({'health', 'current_error', 'streak', 'paused', 'last_error_time'} <= data.keys())
        self.assertEqual(data['streak'], 3)
        self.assertTrue(data['paused'])
        self.assertIn('aos-agent: stuck:', data['last_error'])
        self.assertIn('touch', data['waits'][0])

    def test_say_warn_and_delivery(self):
        code, output = self.cli('say', '--target', str(self.base), 'hello')
        self.assertEqual(code, 0)
        self.assertIn('said -> ', output)
        self.assertIn('aos-agent: warn: 目前沒登記、沒人處理', self.err.getvalue())
        self.assertEqual(self.read(self.base / 'input.json')['content'], 'hello')

    def test_say_wait_unregistered_immediate(self):
        start = time.monotonic()
        code, output = self.cli('say', '--target', str(self.base), 'hello', '--wait')
        self.assertLess(time.monotonic() - start, 2)
        self.assertEqual(code, 101)
        self.assertIn('aos-agent: unregistered:', self.err.getvalue())
        # fix-r5：stdout 先說話已投入、別再說一次，再印 status。
        self.assertTrue(output.startswith('已投入，start 後會處理，不要再說一次'))
        self.assertIn('\nhealth 沒登記', output)
        self.assertTrue((self.base / 'input.json').exists())

    def test_unreadable_ledger_does_not_warn(self):
        self.registered()
        (self.k / 'state.json').write_text('{')
        self.assertEqual(self.cli('say', '--target', str(self.base), 'hello')[0], 0)
        self.assertNotIn('warn:', self.err.getvalue())

    def test_stop_during_wait(self):
        self.registered()
        def stopped(_):
            self.put(self.k / 'state.json', {'procs': {}, 'replies': []})
        with self.healthy(), patch.object(say.time, 'sleep', side_effect=stopped):
            self.assertEqual(self.cli('say', '--target', str(self.base), 'hello', '--wait')[0], 101)
        self.assertIn('unregistered:', self.err.getvalue())

    def test_registered_wait_reply(self):
        self.registered()
        def reply(_):
            message = self.read(self.base / 'input.json')
            (self.base / 'input.json').unlink()
            self.put(self.base / 'prompts/history.json', [message, fixture.MESSAGE])
        with self.healthy(), patch.object(say.time, 'sleep', side_effect=reply):
            self.assertEqual(self.cli('say', '--target', str(self.base), 'hello', '--wait'), (0, '完成\n'))

    def test_registered_wait_paused(self):
        self.registered()
        self.pause()
        with self.healthy():
            code, output = self.cli('say', '--target', str(self.base), 'hello', '--wait')
        self.assertEqual(code, 101)
        self.assertIn('stuck:', self.err.getvalue())
        self.assertIn('error  Connection refused', output)

    def test_arrived_pause_is_not_paused(self):
        self.registered()
        self.pause()
        (self.base / 'continue-test.json').touch()
        self.put(self.base / 'state.json', {'waits': [{'$opt': 'consume', '$val': ['continue-test.json', 'external']}]})
        with self.healthy():
            self.assertFalse(status.collect(self.base, {})['paused'])
            self.assertEqual(self.cli('say', '--target', str(self.base), 'hello', '--wait', '0')[0], 101)
        self.assertIn('Timeout:', self.err.getvalue())

    def test_say_help(self):
        with patch('sys.stdout', new_callable=io.StringIO) as out, self.assertRaises(SystemExit):
            agent.main(['say', '-h'])
        for text in ('cd 家 && aos-agent say "現在幾點？" --wait',
                     'aos-agent say "現在幾點？" --target ~/agents/amy --wait 60',
                     '不帶數字＝等 300 秒', '--target DIR', '暫停中照收'):
            self.assertIn(text, out.getvalue())

    def test_registered_wait_retries_partial_files(self):
        self.registered()
        loops = []
        def advance(_):
            loops.append(True)
            if len(loops) == 1:
                (self.base / 'input.json').unlink()
                (self.base / 'state.json').write_text('{')
            elif len(loops) == 2:
                self.put(self.base / 'state.json', {})
                (self.base / 'prompts').mkdir(exist_ok=True)
                (self.base / 'prompts/history.json').write_text('{')
            else:
                self.put(self.base / 'prompts/history.json',
                         [{'role': 'user', 'content': 'hello'}, fixture.MESSAGE])
        with self.healthy(), patch.object(say.time, 'sleep', side_effect=advance):
            self.assertEqual(self.cli('say', '--target', str(self.base), 'hello', '--wait'), (0, '完成\n'))
        self.assertEqual(len(loops), 3)
