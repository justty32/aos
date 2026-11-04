"""日常 CLI：假家、假回合與原子投遞的正反例。"""
import io
import json
import os
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch

import aos_agent as agent
import aos_agent_info as info
import aos_agent_say as say
import aos_agent_status as status
import aos_home
import test_agent_tick as fixture
import aos_kernel_store


class DailyTests(unittest.TestCase):
    for _name in ('setUp', 'put', 'read', 'prepare', 'kernel_thread'):
        locals()[_name] = getattr(fixture.AgentTickTests, _name)

    def cli(self, *args):
        with patch.dict(os.environ, {}, clear=True), patch('sys.stdout', new_callable=io.StringIO) as out:
            code = agent.main(list(args))
        return code, out.getvalue()

    def state(self, **values):
        self.put(self.base / 'state.json', values)

    def pause(self):
        self.state(waits=[{'$opt': 'consume', '$val': 'continue-test.json'}, 'outside.json'])
        return self.base / 'continue-test.json'

    def test_init_valid(self):
        base = self.root / 'nested/new'
        code, output = self.cli('init', '--target', str(base))
        self.assertEqual(code, 0)
        self.assertEqual(len(output.splitlines()), 3)
        self.assertIn('access.json', output)
        self.assertEqual(info.load(base)['model'], 'default')
        # 09-24 裁決 4：有工具的家一定要有 access.json；init 生的 date 也關牢、只看得到 workspace
        self.assertEqual(json.loads((base / 'access.json').read_text()),
                         {'_metainfo': {'_type': 'agent_access', '_version': 1},
                          'mounts': {'ws': 'workspace'}, 'cwd': 'ws', 'net': False})
        self.assertTrue((base / 'workspace').is_dir())
        import aos_agent_access
        self.assertEqual(aos_agent_access.load(base)['mounts']['ws']['ro'], False)   # 真的過得了權限檢查
        self.assertEqual(info.load_state(base)['input'], ['input'])
        self.assertEqual(info.load(base)['tools'][0]['function']['name'], 'date')
        self.assertTrue((base / 'log').is_dir())
        # proto5-2 run.md 問題 6＋納入審查 P4：提示指到有這段的教程（proto5-2 已納入，README 沒有「第 2 段」）。
        self.assertIn('見 proto5/tutorials/01-daemon-kernel.md', output)
        self.assertNotIn('proto5-2', output)

    def test_init_refuses_without_writes(self):
        before = {p: p.read_bytes() for p in self.base.rglob('*') if p.is_file()}
        self.assertEqual(self.cli('init', '--target', str(self.base))[0], 1)
        self.assertIn('AlreadyExists', self.err.getvalue())
        self.assertEqual(before, {p: p.read_bytes() for p in self.base.rglob('*') if p.is_file()})

    def test_status_json(self):
        data = json.loads(self.cli('status', '--target', str(self.base), '--json')[1])
        self.assertEqual(set(data), {'dir', 'info_error', 'state_error', 'access_error', 'state', 'errors',
                                    'batch', 'waits', 'pending_inputs', 'intake', 'last_error', 'kernel',
                                    'health', 'current_error', 'streak', 'paused', 'last_error_time',
                                    'manual_paused', 'manual_paused_since', 'resumed', 'resumed_since'})
        self.assertEqual(data['state'], 'idle')
        self.assertIsNone(data['kernel']['home'])
        self.assertIn('沒設 AOS_KERNEL_HOME', data['kernel']['note'])

    def test_status_wait_text_and_arrival(self):
        path = self.pause()
        self.assertIn('（連敗暫停，aos-agent continue --target %s）' % self.base, self.cli('status', '--target', str(self.base))[1])
        path.touch()
        self.assertIn('已到，下一格會開', self.cli('status', '--target', str(self.base))[1])
        self.assertEqual(status.collect(self.base, {})['waits'][0],
                         dict(paths=[str(path)], arrived=True, consume=True, pause=True, touch=str(path)))

    def test_status_batch_intake_inputs_error(self):
        self.prepare(sent=False)
        st = self.read(self.base / 'state.json')
        st['intake'] = {'id': 'i', 'base_len': 0, 'files': []}
        self.put(self.base / 'state.json', st)
        self.put(self.base / 'input.json', '你好')
        (self.base / 'log').mkdir()
        (self.base / 'log/agent.err').write_text('舊\n' + '錯' * 350 + '\n\n')
        data = status.collect(self.base, {})
        self.assertEqual(data['batch'], dict(kind='think', sent=False, total=1, sent_n=1, done_n=0))
        self.assertTrue(data['intake'])
        self.assertEqual(len(data['last_error']), 350)  # fix-r5：收原文，一般輸出才縮短
        output = self.cli('status', '--target', str(self.base))[1]
        for word in ('送件中', '收到一半', '1 個檔還沒收'):
            self.assertIn(word, output)

    def test_status_broken_info_and_state(self):
        (self.base / 'info.json').write_text('{')
        (self.base / 'state.json').write_text('{')
        code, output = self.cli('status', '--target', str(self.base))
        self.assertEqual(code, 0)
        self.assertIn('info  bad：JsonSyntax', output)
        self.assertIn('state bad：JsonSyntax', output)
        self.assertIn('kernel ', output)

    def test_status_not_agent(self):
        for value in ({'_metainfo': {'_type': 'cpu', '_version': 1}}, None):
            if value is None:
                (self.base / 'info.json').unlink()
            else:
                self.put(self.base / 'info.json', value)
            self.assertEqual(self.cli('status', '--target', str(self.base))[0], 1)
            self.assertIn('NotAnAgent', self.err.getvalue())

    def test_status_kernel_fallback_and_bad(self):
        self.put(self.base / 'tick.json', {'envs': self.env})
        proc = {'status': 'bad', 'runs': 12, 'fails': 3}
        aos_kernel_store.write(self.k, {'procs': {'agent-bob': proc}, 'replies': []})
        data = status.collect(self.base, {})
        self.assertEqual(data['kernel']['proc'], proc)
        self.assertEqual(data['kernel']['home'], str(self.k))
        self.assertIn(str(self.base / 'log/agent.err'), self.cli('status', '--target', str(self.base))[1])

    def test_status_kernel_missing_and_unreadable(self):
        self.assertIn('沒登記', status.collect(self.base, self.env)['kernel']['note'])
        (self.k / 'ledger.sqlite').write_text('{')  # one-boot：帳本壞掉（不是 sqlite）
        self.assertIn('帳本讀不到', status.collect(self.base, self.env)['kernel']['note'])

    def test_tick_fallback_literal_absolute_only(self):
        for value in ('relative', {'$env': 'K'}, None):
            self.put(self.base / 'tick.json', {'envs': {'AOS_KERNEL_HOME': value}})
            self.assertIsNone(status.collect(self.base, {})['kernel']['home'])
            self.assertEqual(self.cli('stop', '--target', str(self.base))[0], 2)

    def test_continue_three_cases(self):
        self.assertEqual(self.cli('continue', '--target', str(self.base)), (0, '沒有在暫停\n'))
        path = self.pause()
        note = '已解除暫停，等下一次成功（aos-agent status --target %s 看）\n' % self.base
        self.assertEqual(self.cli('continue', '--target', str(self.base)), (0, 'continued: touched %s\n' % path + note))
        self.assertTrue((self.base / 'resumed').exists())  # fix-r5：兩階段的第一段
        self.assertEqual(self.cli('continue', '--target', str(self.base)), (0, '已經 touch 過，等下一格 tick：%s\n' % path + note))
        self.assertFalse((self.base / 'outside.json').exists())

    def test_continue_only_owned_consume_paths(self):
        external = self.root / 'continue-foreign.json'
        self.state(waits=[{'$opt': 'consume', '$val': str(external)}, 'continue-own.json'])
        self.assertEqual(self.cli('continue', '--target', str(self.base)), (0, '沒有在暫停\n'))
        self.assertFalse(external.exists())
        self.assertFalse((self.base / 'continue-own.json').exists())

    def test_continue_bad_state(self):
        self.state(state='invalid')
        self.assertEqual(self.cli('continue', '--target', str(self.base))[0], 1)

    def test_stop_fallback(self):
        self.put(self.base / 'tick.json', {'envs': self.env})
        thread, seen, failures = self.kernel_thread()
        self.assertEqual(self.cli('stop', '--target', str(self.base))[0], 0)
        thread.join(3)
        self.assertFalse(failures)
        self.assertEqual(seen[0]['method'], 'rm')

    def test_stop_no_fallback(self):
        self.assertEqual(self.cli('stop', '--target', str(self.base))[0], 2)
        self.assertIn('沒設 AOS_KERNEL_HOME，tick.json 也沒記', self.err.getvalue())

    def test_say_directory_and_first_input(self):
        self.state(input=['inbox/', 'other.json'])
        for _ in range(2):
            self.assertEqual(self.cli('say', '--target', str(self.base), '你好')[0], 0)
        paths = list((self.base / 'inbox').iterdir())
        self.assertEqual(len(paths), 2)
        self.assertEqual(self.read(paths[0]), {'role': 'user', 'content': '你好'})
        self.assertFalse((self.base / 'other.json').exists())

    def test_say_file_busy(self):
        self.put(self.base / 'input.json', '舊訊息')
        with patch.object(say, 'INPUT_WAIT_SECONDS', .01):
            self.assertEqual(self.cli('say', '--target', str(self.base), '新訊息')[0], 1)
        self.assertEqual(self.read(self.base / 'input.json'), '舊訊息')
        self.assertIn('InputBusy', self.err.getvalue())
        self.assertFalse(list(self.base.glob('.*.tmp')))

    def test_say_file_retry(self):
        self.put(self.base / 'input.json', '舊訊息')
        def consumed(_):
            (self.base / 'input.json').unlink()
        with patch.object(say.time, 'sleep', side_effect=consumed):
            self.assertEqual(self.cli('say', '--target', str(self.base), '新訊息')[0], 0)
        self.assertEqual(self.read(self.base / 'input.json')['content'], '新訊息')

    def test_say_requires_valid_info(self):
        self.put(self.base / 'info.json', {})
        self.assertEqual(self.cli('say', '--target', str(self.base), '你好')[0], 1)
        self.assertFalse((self.base / 'input.json').exists())

    def test_say_wait_fake_agent(self):
        self.put(self.base / 'prompts/history.json', [fixture.MESSAGE])
        errors = []
        def fake():
            try:
                deadline = time.monotonic() + 2
                while not (self.base / 'input.json').exists():
                    if time.monotonic() > deadline:
                        raise AssertionError('沒收到輸入')
                    time.sleep(.005)
                message = self.read(self.base / 'input.json')
                (self.base / 'input.json').rename(self.base / 'received.done')
                aos_home.write_json(self.base / 'prompts/history.json', [fixture.MESSAGE, message, fixture.ASSISTANT])
                aos_home.write_json(self.base / 'state.json', {'state': 'idle'})
            except BaseException as exc:
                errors.append(exc)
        thread = threading.Thread(target=fake)
        thread.start()
        try:
            self.assertEqual(self.cli('say', '--target', str(self.base), '你好', '--wait', '2')[0], 101)
        finally:
            thread.join(3)
        self.assertFalse(errors)
        self.assertFalse(thread.is_alive())

    def test_say_wait_timeout_old_answer(self):
        self.put(self.base / 'prompts/history.json', [fixture.MESSAGE])
        code, output = self.cli('say', '--target', str(self.base), '你好', '--wait', '0.001')
        self.assertEqual(code, 101)
        self.assertIn('agent  ', output)
        self.assertIn('unregistered: 目前沒登記', self.err.getvalue())

    def test_say_wait_stuck(self):
        self.pause()
        code, output = self.cli('say', '--target', str(self.base), '你好', '--wait', '300')
        self.assertEqual(code, 101)
        self.assertIn('（連敗暫停，aos-agent continue --target %s）' % self.base, output)
        self.assertIn('unregistered:', self.err.getvalue())

    def test_usage(self):
        for args in [('say',), ('say', ''), ('say', 'a', 'b', 'c'), ('say', 'x', '--timeout-ms', '2'),
                     ('say', 'x', '--wait', '--timeout-ms', '-1'), ('init', '--json'), ('continue', '--json'),
                     ('say', 'a', 'b'), ('say', 'x', '--wait', '-1'), ('say', 'x', '--wait', 'abc'),
                     ('listen', '--last', '--wait'), ('listen', '--follow', '--wait', '3'),
                     ('listen', '--wait', 'x'), ('pause', '--json'), ('status', '--target', ''),
                     ('tick', '/some/dir')]:
            with self.subTest(args=args), self.assertRaises(SystemExit) as exc:
                self.cli(*args)
            self.assertEqual(exc.exception.code, 2)

    def test_last_fallback_and_gate(self):
        (self.base / 'info.json').write_text('{')
        self.put(self.base / 'prompts/history.json', [fixture.MESSAGE])
        self.pause()
        self.assertEqual(self.cli('listen', '--last', '--target', str(self.base)), (0, '完成\n'))
        self.assertIn('改讀 prompts/history.json', self.err.getvalue())
        self.assertIn('連敗暫停中', self.err.getvalue())

    def test_last_external_gate(self):
        self.put(self.base / 'prompts/history.json', [fixture.MESSAGE])
        self.state(waits='outside.json')
        self.assertEqual(self.cli('listen', '--last', '--target', str(self.base)), (0, '完成\n'))
        self.assertIn('門關著（在等 %s）' % (self.base / 'outside.json'), self.err.getvalue())

    def test_last_missing_info(self):
        self.put(self.base / 'prompts/history.json', [fixture.MESSAGE])
        (self.base / 'info.json').unlink()
        self.assertEqual(self.cli('listen', '--last', '--target', str(self.base))[0], 1)
        self.assertIn('NotAnAgent', self.err.getvalue())
