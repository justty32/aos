"""fix-r5：試玩 r4 兩份報告的共同痛點（agent 這一半）。

health 不再樂觀、continue 兩階段與 --all、listen 講中間句並附時間、已登記的 start 退 0、
沒登記的 say 講別再說一次、say／listen --wait 開始前看 kernel、init 要 --force、NotAnAgent 講是哪種家。
"""
import io
import json
import os
import time
import unittest
from unittest.mock import patch

import aos_agent as agent
import aos_agent_status as status
import test_agent_tick as fixture

MESSAGE = fixture.MESSAGE


class FixR5Tests(unittest.TestCase):
    for _name in ('setUp', 'put', 'read', 'state', 'tick', 'prepare', 'respond', 'output',
                  'kernel_thread', 'register'):
        locals()[_name] = getattr(fixture.AgentTickTests, _name)

    def cli(self, *args, env=None):
        with patch.dict(os.environ, env or {}, clear=True), \
                patch('sys.stdout', new_callable=io.StringIO) as out:
            try:
                code = agent.main(list(args))
            except SystemExit as exc:  # 用法錯走 argparse，退 2
                code = exc.code
        return code, out.getvalue()

    def registered(self, **values):
        self.put(self.base / 'tick.json', {'envs': self.env})
        proc = {'status': 'idle', 'fails': 0, 'target': str(self.base / 'tick.json'), 'once': False, **values}
        # kernel-ledger.md（proto5-2）：忙的格子在 busy（key P/<i>），on 反查行程名 → 格子。
        self.put(self.k / 'state.json', {'procs': {'agent-bob': proc}, 'replies': [], 'busy': {}, 'on': {}})

    def health(self, code='ok', message='ok'):
        return patch('aos_kernel_health.health', return_value=(code, message))

    def stuck(self, name='continue-test.json'):
        self.put(self.base / 'state.json', {'state': 'think', 'errors': 0,
                                            'waits': [{'$opt': 'consume', '$val': name}]})
        log = self.base / 'log/agent.err'
        log.parent.mkdir(exist_ok=True)
        log.write_text('aos-agent: engine: Connection refused（endpoint http://localhost:4999/v1）\n'
                       'aos-agent: stuck: 問模型連敗 3 次，touch %s 繼續\n' % (self.base / name))

    # 1. health 第一行不再樂觀 ------------------------------------------------

    def test_retrying_not_ok(self):
        self.registered()
        self.put(self.base / 'state.json', {'state': 'think', 'errors': 2})
        with self.health():
            data = status.collect(self.base, {})
            _, output = self.cli('status', '--target', str(self.base))
        self.assertEqual(data['health'], {'code': 'retrying', 'message': '重試中（連敗 2/3）'})
        self.assertTrue(output.startswith('health 重試中（連敗 2/3）\n'))

    def test_recovering_from_kernel_and_priority(self):
        self.registered()
        message = '恢復中（llm cpu dead，daemon 重拉中）'
        with self.health('recovering', message):
            self.assertEqual(status.collect(self.base, {})['health'], {'code': 'recovering', 'message': message})
            _, output = self.cli('status', '--target', str(self.base))
            self.assertTrue(output.startswith('health ' + message))
            self.stuck()  # 暫停比恢復中優先：它不會自己好
            self.assertEqual(status.collect(self.base, {})['health']['code'], 'paused')

    # 2. continue 兩階段、舊錯縮短 -----------------------------------------------

    def test_continue_two_phase(self):
        self.registered()
        self.stuck()
        self.assertEqual(self.cli('continue', '--target', str(self.base))[0], 0)
        self.assertTrue((self.base / 'resumed').exists())
        with self.health():
            data = status.collect(self.base, {})
            _, output = self.cli('status', '--target', str(self.base))
        self.assertEqual(data['health']['code'], 'resuming')
        self.assertTrue(data['resumed'])
        self.assertTrue(output.startswith('health 已解除暫停，等下一次成功\n'))
        self.assertRegex(output, r'\nlast-error  （已解除暫停，等下一次成功） \d\d-\d\d ')
        # 門開了、重問成功：tick 結清時刪 resumed，才標「已恢復」。
        self.tick()  # 開門、重問（送一批）
        self.assertFalse(self.state()['waits'])
        self.assertTrue((self.base / 'resumed').exists())  # 還沒成功，照舊等
        name = self.prepare(done={'ok': True}, acked=True)
        self.output(name)
        self.assertEqual(self.tick(), 0)
        self.assertFalse((self.base / 'resumed').exists())
        with self.health():
            _, output = self.cli('status', '--target', str(self.base))
        self.assertTrue(output.startswith('health ok\n'))
        self.assertIn('last-error  （已恢復） ', output)

    def test_failed_think_keeps_resumed(self):
        self.registered()
        (self.base / 'resumed').write_text('resumed at x\n')
        self.prepare(done={'fail': '錯', 'count': True}, acked=True)
        self.assertEqual(self.tick(), 0)
        self.assertTrue((self.base / 'resumed').exists())
        with self.health():
            self.assertEqual(status.collect(self.base, {})['health']['code'], 'retrying')

    def test_manual_only_continue_no_resumed(self):
        self.cli('pause', '--target', str(self.base))
        code, output = self.cli('continue', '--target', str(self.base))
        self.assertEqual((code, output), (0, 'continued: 解除手動暫停\n'))
        self.assertFalse((self.base / 'resumed').exists())

    def test_short_old_error(self):
        self.registered()
        long_name = 'aw-bob-1790000000000000000-4242-0'
        log = self.base / 'log/agent.err'
        log.parent.mkdir(exist_ok=True)
        log.write_text('aos-agent: stuck: 問模型連敗 3 次，touch %s/continue-aw-bob-1-2.json 繼續\n' % self.base)
        with self.health():
            _, output = self.cli('status', '--target', str(self.base))
            _, verbose = self.cli('status', '--target', str(self.base), '-v')
            data = status.collect(self.base, {})
        self.assertIn('last-error  （已恢復） ', output)
        self.assertNotIn('touch ', output)
        self.assertIn('修好原因後 aos-agent continue --target %s' % self.base, output)
        self.assertIn('touch ', verbose)
        self.assertIn('touch ', data['last_error'])  # --json 是原文
        short = status.short_error('aos-agent: engine: 結果不明，看 %s/work/%s.out ' % (self.base, long_name) + 'x' * 200,
                                   str(self.base))
        self.assertIn('aw-…', short)
        self.assertNotIn(long_name, short)
        self.assertTrue(short.endswith('…（-v 看全文）'))

    def test_paused_current_error_not_duplicated(self):
        self.registered()
        self.put(self.base / 'state.json', {'state': 'think', 'waits': [{'$opt': 'consume', '$val': 'continue-x.json'}]})
        log = self.base / 'log/agent.err'
        log.parent.mkdir(exist_ok=True)
        log.write_text('aos-agent: stuck: 問模型連敗 3 次，修好原因後 aos-agent continue --target %s\n' % self.base)
        with self.health():
            _, output = self.cli('status', '--target', str(self.base))
        line = next(l for l in output.splitlines() if l.startswith('error'))
        self.assertEqual(line.count('aos-agent continue'), 1, line)

    # 3. listen --last 講中間句、附時間 --------------------------------------------

    def listen_last(self):
        self.err.truncate(0); self.err.seek(0)
        return self.cli('listen', '--last', '--target', str(self.base))

    def test_listen_last_tool_calls_warns(self):
        self.put(self.base / 'prompts/history.json', [{'role': 'user', 'content': '算'}, fixture.ASSISTANT])
        self.put(self.base / 'state.json', {'state': 'act'})
        code, output = self.listen_last()
        self.assertEqual((code, output), (0, '(tool_calls: sh)\n'))
        self.assertIn('aos-agent: warn: 還在處理中（tool_calls: sh）', self.err.getvalue())
        self.assertRegex(self.err.getvalue(), r'aos-agent: time: \d\d-\d\d \d\d:\d\d:\d\d\n')

    def test_listen_last_pending_input_warns(self):
        self.put(self.base / 'prompts/history.json', [MESSAGE])
        self.put(self.base / 'state.json', {'input': 'input'})
        self.put(self.base / 'input/say-1.json', {'role': 'user', 'content': '新的'})
        self.listen_last()
        self.assertIn('還在處理中（新輸入還沒回）', self.err.getvalue())

    def test_listen_last_done_round_quiet(self):
        self.put(self.base / 'prompts/history.json', [{'role': 'user', 'content': 'hi'}, MESSAGE])
        code, output = self.listen_last()
        self.assertEqual((code, output), (0, '完成\n'))
        self.assertNotIn('還在處理中', self.err.getvalue())
        self.assertIn('aos-agent: time: ', self.err.getvalue())
        self.assertNotIn('這則更早', self.err.getvalue())

    def test_listen_last_older_message_time_note(self):
        self.put(self.base / 'prompts/history.json', [MESSAGE, {'role': 'user', 'content': '下一句'}])
        self.put(self.base / 'state.json', {'state': 'think'})
        self.listen_last()
        self.assertIn('（記憶最後更新，這則更早）', self.err.getvalue())
        self.assertIn('還在處理中（新輸入還沒回）', self.err.getvalue())

    # 4. start 已登記退 0 -------------------------------------------------------

    def test_start_already_started_same_home(self):
        self.put(self.k / 'state.json', {'procs': {'agent-bob': {
            'status': 'idle', 'target': str(self.base / 'tick.json'), 'once': False}}, 'replies': [],
            'busy': {}, 'on': {}})
        with patch('sys.stdout', new_callable=io.StringIO) as out:
            rc, _ = self.register(error={'code': -32000, 'message': '已存在', 'data': {'code': 'AlreadyExists'}})
        self.assertEqual(rc, 0)
        self.assertEqual(out.getvalue(), 'already started agent-bob\n')
        self.assertEqual(self.err.getvalue(), '')

    def test_start_already_exists_other_cases_still_fail(self):
        target = str(self.base / 'tick.json')
        # kernel-ledger.md（proto5-2）：discard 看 on[NAME] 指的那格 busy[...] 的 discard。
        cases = {'discard': ({'target': target}, {'default/0': {'proc': 'agent-bob', 'req': 'x', 'discard': True}},
                              {'agent-bob': 'default/0'}, '上次 stop 的那格還在跑'),
                 'bad': ({'target': target, 'status': 'bad'}, {}, {}, '被判 bad'),
                 'other': ({'target': '/else/bob/tick.json'}, {}, {}, '同名行程是 /else/bob/tick.json')}
        for label, (proc, busy, on, text) in cases.items():
            with self.subTest(label), patch('sys.stdout', new_callable=io.StringIO):
                self.err.truncate(0); self.err.seek(0)
                for leftover in (self.k / 'requests').glob('*'):
                    leftover.unlink()
                self.put(self.k / 'state.json', {'procs': {'agent-bob': {'status': 'idle', 'once': False, **proc}},
                                                 'replies': [], 'busy': busy, 'on': on})
                rc, _ = self.register(error={'code': -32000, 'message': '已存在', 'data': {'code': 'AlreadyExists'}})
                self.assertEqual(rc, 1)
                self.assertIn('AlreadyExists', self.err.getvalue())
                self.assertIn(text, self.err.getvalue())

    # 6. 沒登記的 say、--wait 先看 health ------------------------------------------

    def test_say_unregistered_stdout_says_dont_repeat(self):
        code, output = self.cli('say', 'hi', '--target', str(self.base))
        self.assertEqual(code, 0)
        self.assertIn('已投入，start 後會處理，不要再說一次：aos-agent start --target %s' % self.base, output)
        self.assertTrue((self.base / 'input.json').exists())

    def test_say_wait_kernel_broken_immediate(self):
        self.registered()
        start = time.monotonic()
        with self.health('daemon', 'daemon 沒在跑：/D（先 aos-daemon boot）'):
            code, output = self.cli('say', 'hi', '--target', str(self.base), '--wait', '30', env=self.env)
        self.assertLess(time.monotonic() - start, 2)
        self.assertEqual(code, 101)
        self.assertIn('aos-agent: kernel: kernel 家有問題：daemon 沒在跑', self.err.getvalue())
        self.assertTrue(output.startswith('已投入 %s，不要再說一次' % (self.base / 'input.json')))
        self.assertTrue((self.base / 'input.json').exists())  # 話照投，不丟

    def test_listen_wait_immediate_on_bad_and_manual(self):
        self.put(self.base / 'prompts/history.json', [MESSAGE])
        self.registered(**{'status': 'bad'})
        with self.health():
            start = time.monotonic()
            code, output = self.cli('listen', '--target', str(self.base), '--wait', '30', env=self.env)
            self.assertLess(time.monotonic() - start, 2)
            self.assertEqual(code, 101)
            self.assertIn('aos-agent: bad: kernel 判壞了', self.err.getvalue())
            self.assertNotIn('已投入', output)
            self.registered()
            self.cli('pause', '--target', str(self.base))
            self.assertEqual(self.cli('listen', '--target', str(self.base), '--wait', '30', env=self.env)[0], 101)
            self.assertIn('aos-agent: paused:', self.err.getvalue())

    def test_wait_keeps_waiting_while_recovering(self):
        self.registered()
        self.put(self.base / 'prompts/history.json', [MESSAGE])
        with self.health('recovering', '恢復中（llm cpu dead，daemon 重拉中）'):
            start = time.monotonic()
            code, _ = self.cli('listen', '--target', str(self.base), '--wait', '0.5', env=self.env)
        self.assertGreaterEqual(time.monotonic() - start, .45)
        self.assertEqual(code, 101)
        self.assertIn('Timeout', self.err.getvalue())

    # 7. continue --all -------------------------------------------------------

    def other_agent(self, name):
        home = self.root / name
        self.put(home / 'info.json', self.info)
        return home

    def test_continue_all(self):
        amy, cat = self.other_agent('amy'), self.other_agent('cat')
        self.stuck()
        (amy / 'paused').write_text('paused at x\n')
        procs = {'agent-%s' % h.name: {'status': 'idle', 'once': False, 'target': str(h / 'tick.json')}
                 for h in (self.base, amy, cat)}
        procs['job'] = {'status': 'idle', 'once': True, 'target': '/x.json'}
        self.put(self.k / 'state.json', {'procs': procs, 'replies': []})
        code, output = self.cli('continue', '--all', env=self.env)
        self.assertEqual(code, 0, self.err.getvalue())
        lines = output.splitlines()
        self.assertIn('agent-bob  %s  解除連敗暫停（等下一次成功）' % self.base, lines)
        self.assertIn('agent-amy  %s  解除手動暫停' % amy, lines)
        self.assertIn('agent-cat  %s  沒在暫停' % cat, lines)
        self.assertEqual(lines[-1], 'continued 2／3')
        self.assertTrue((self.base / 'continue-test.json').exists())
        self.assertTrue((self.base / 'resumed').exists())
        self.assertFalse((amy / 'paused').exists())

    def test_continue_all_usage_and_skips(self):
        self.assertEqual(self.cli('continue', '--all')[0], 2)
        self.assertEqual(self.cli('continue', '--all', '--target', str(self.base), env=self.env)[0], 2)
        self.put(self.k / 'state.json', {'procs': {}, 'replies': []})
        self.assertEqual(self.cli('continue', '--all', env=self.env), (0, 'K 帳本裡沒有登記的 agent（%s）\n' % self.k))
        self.put(self.base / 'state.json', {'state': 'bogus'})
        self.put(self.k / 'state.json', {'procs': {'agent-bob': {'status': 'idle', 'once': False,
                                                                 'target': str(self.base / 'tick.json')}}, 'replies': []})
        code, output = self.cli('continue', '--all', env=self.env)
        self.assertEqual(code, 1)
        self.assertIn('agent-bob  %s  跳過：' % self.base, output)

    def test_brief_marks(self):
        self.assertIsNone(status.brief(self.base))
        self.put(self.base / 'state.json', {'errors': 1})
        self.assertEqual(status.brief(self.base), ('retrying', '重試中（連敗 1/3）'))
        self.stuck()
        self.assertEqual(status.brief(self.base), ('paused', '連敗暫停中'))
        (self.base / 'paused').write_text('x')
        self.assertEqual(status.brief(self.base)[0], 'both_paused')
        self.put(self.k / 'info.json', {'_metainfo': {'_type': 'kernel', '_version': 1}})
        self.assertIsNone(status.brief(self.k))

    # 8. NotAnAgent 講是哪種家、init 要 --force --------------------------------------

    def test_status_on_kernel_home(self):
        self.put(self.k / 'info.json', {'_metainfo': {'_type': 'kernel', '_version': 1}, 'cpus': {}})
        self.assertEqual(self.cli('status', '--target', str(self.k))[0], 1)
        self.assertIn('是 kernel 家，不是 agent 家', self.err.getvalue())
        self.err.truncate(0); self.err.seek(0)
        self.assertEqual(agent.tick(self.k, self.env), 1)
        self.assertIn('這是 kernel 家，不是 agent 家', self.err.getvalue())

    def test_init_non_empty_needs_force(self):
        target = self.root / 'notes'
        target.mkdir()
        (target / 'a.txt').write_text('x')
        code, _ = self.cli('init', '--target', str(target))
        self.assertEqual(code, 1)
        self.assertIn('NotEmpty', self.err.getvalue())
        self.assertIn('a.txt', self.err.getvalue())
        self.assertIn('--force', self.err.getvalue())
        self.assertEqual(sorted(p.name for p in target.iterdir()), ['a.txt'])
        self.assertEqual(self.cli('init', '--target', str(target), '--force')[0], 0)
        self.assertTrue((target / 'info.json').exists())
        self.assertEqual((target / 'a.txt').read_text(), 'x')
        self.assertEqual(self.cli('init', '--target', str(self.root / 'fresh'))[0], 0)
        empty = self.root / 'empty'
        empty.mkdir()
        self.assertEqual(self.cli('init', '--target', str(empty))[0], 0)

    # astra 審查挑的 ------------------------------------------------------------

    def test_resumed_written_before_door(self):
        self.stuck()
        import aos_agent_pause
        seen = []
        real = aos_agent_pause._mark
        def spy(base, name):
            seen.append((name, (self.base / 'continue-test.json').exists()))
            real(base, name)
        with patch.object(aos_agent_pause, '_mark', spy):
            self.cli('continue', '--target', str(self.base))
            self.cli('continue', '--target', str(self.base))  # 門已在：不再放 resumed
        self.assertEqual(seen, [('resumed', False)])

    def test_verbose_and_json_keep_full_old_error(self):
        self.registered()
        log = self.base / 'log/agent.err'
        log.parent.mkdir(exist_ok=True)
        log.write_text('aos-agent: engine: ' + 'z' * 400 + 'END\n')
        with self.health():
            _, plain = self.cli('status', '--target', str(self.base))
            _, verbose = self.cli('status', '--target', str(self.base), '-v')
            _, raw = self.cli('status', '--target', str(self.base), '--json')
        self.assertNotIn('END', plain)
        self.assertIn('（-v 看全文）', plain)
        self.assertIn('END', verbose)
        self.assertTrue(json.loads(raw)['last_error'].endswith('END'))

    def test_idle_tool_calls_still_warns(self):
        self.put(self.base / 'prompts/history.json', [{'role': 'user', 'content': '算'}, fixture.ASSISTANT])
        self.put(self.base / 'state.json', {'state': 'idle'})
        self.listen_last()
        self.assertIn('還在處理中（tool_calls: sh）', self.err.getvalue())


if __name__ == '__main__':
    unittest.main()
