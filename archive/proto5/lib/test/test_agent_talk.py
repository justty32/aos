"""aos-agent talk（aos-agent.md §1.9）：管線餵 stdin、假 agent 用 thread 回話。"""
import io
import json
import os
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch

import aos_agent as agent
import aos_agent_say
import aos_agent_talk as talk
import aos_home
import test_agent_tick as fixture
import aos_kernel_store

CLI = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'cli', 'aos-agent')
CALL = {'id': 'd1', 'type': 'function', 'function': {'name': 'date', 'arguments': '{"fmt": "%H"}'}}
ASKS = {'role': 'assistant', 'content': None, 'tool_calls': [CALL]}
RESULT = {'role': 'tool', 'tool_call_id': 'd1', 'content': '12:00:00\n'}
REPLY = {'role': 'assistant', 'content': '現在 12 點'}


class TalkTests(unittest.TestCase):
    for _name in ('setUp', 'put', 'read'):
        locals()[_name] = getattr(fixture.AgentTickTests, _name)

    def registered(self):
        self.put(self.base / 'tick.json', {'envs': self.env})
        proc = {'status': 'idle', 'fails': 0, 'target': str(self.base / 'tick.json'), 'once': False}
        aos_kernel_store.write(self.k, {'procs': {'agent-bob': proc}, 'replies': [], 'cpus': {}})
        patch('aos_kernel_health.health', return_value=('ok', 'ok')).start()

    def run_talk(self, lines, *args, env=None):
        with patch.dict(os.environ, env if env is not None else self.env, clear=True), \
                patch('sys.stdin', io.StringIO(lines)), \
                patch('sys.stdout', new_callable=io.StringIO) as out:
            try:
                code = agent.main(['talk', '--target', str(self.base)] + list(args))
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue()

    def answer(self, *messages, delay=0.0):
        """假 agent：收 input.json，照 tick 的樣子把 user＋回話寫進記憶、state 回 idle。"""
        errors = []
        def fake():
            try:
                deadline = time.monotonic() + 3
                while not (self.base / 'input.json').exists():
                    if time.monotonic() > deadline:
                        raise AssertionError('沒收到輸入')
                    time.sleep(.005)
                said = self.read(self.base / 'input.json')
                (self.base / 'input.json').unlink()
                time.sleep(delay)
                history = self._history()
                (self.base / 'prompts').mkdir(exist_ok=True)
                aos_home.write_json(self.base / 'prompts/history.json', history + [said] + list(messages))
                aos_home.write_json(self.base / 'state.json', {'state': 'idle'})
            except BaseException as exc:
                errors.append(exc)
        thread = threading.Thread(target=fake)
        thread.start()
        self.addCleanup(thread.join, 5)
        return errors

    def _history(self):
        path = self.base / 'prompts/history.json'
        return self.read(path) if path.exists() else []

    # ---- 一句問答 --------------------------------------------------------

    def test_one_question_answer(self):
        self.registered()
        errors = self.answer(ASKS, RESULT, REPLY)
        code, out = self.run_talk('現在幾點？\n', '--wait', '3')
        self.assertEqual(code, 0)
        self.assertFalse(errors)
        self.assertEqual(out, '現在 12 點\n')  # 預設不印工具、不回印自己的話
        self.assertIn('health ok', self.err.getvalue())
        self.assertEqual(self._history()[0], {'role': 'user', 'content': '現在幾點？'})

    def test_show_calls(self):
        self.registered()
        self.answer(ASKS, RESULT, REPLY)
        code, out = self.run_talk('現在幾點？\n', '--wait', '3', '--show-calls')
        self.assertEqual(code, 0)
        # 字樣跟 aos_agent_listen_render 共用：[呼叫 名 k=v]、[結果 名：第一行]
        self.assertEqual(out.splitlines(), ['[呼叫 date fmt=%H]', '[結果 date：12:00:00]', '現在 12 點'])

    def test_reply_before_wait_starts_is_not_lost(self):
        """不能踩的坑：回話在開始等之前就到了，也要印出來（H0 在送出前記）。"""
        self.registered()
        real = aos_agent_say.deliver
        def instant(base, value, text, **kw):
            target, inode = real(base, value, text, **kw)
            target.unlink()
            (self.base / 'prompts').mkdir(exist_ok=True)
            aos_home.write_json(self.base / 'prompts/history.json',
                                [{'role': 'user', 'content': text}, REPLY])
            return target, inode
        with patch('aos_agent_talk.deliver', instant):
            code, out = self.run_talk('嗨\n', '--wait', '2')
        self.assertEqual((code, out), (0, '現在 12 點\n'))
        self.assertNotIn('還在想', self.err.getvalue())

    def test_two_turns_no_reprint(self):
        self.registered()
        errors = self.answer(REPLY)
        code, out = self.run_talk('一\n/history 5\n', '--wait', '3')
        self.assertFalse(errors)
        self.assertEqual(out.count('現在 12 點'), 2)  # 一次是回話、一次是 /history
        self.assertIn('user: 一', out)

    # ---- slash -----------------------------------------------------------

    def test_status_one_line_and_unknown_slash(self):
        self.registered()
        code, out = self.run_talk('/status\n/xyz\n/quit\n不會送\n')
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), ['health ok  state idle  batch -  input -'])
        self.assertIn('沒有這個指令，/help 看清單', self.err.getvalue())
        self.assertFalse((self.base / 'input.json').exists())  # 未知 slash 與 /quit 後面都沒送

    def test_double_slash_sends_literal(self):
        self.registered()
        errors = self.answer(REPLY)
        code, out = self.run_talk('//status 是什麼\n', '--wait', '3')
        self.assertFalse(errors)
        self.assertEqual(self._history()[0]['content'], '/status 是什麼')

    def test_context_history_tools(self):
        self.put(self.base / 'prompts/system.json', {'content': '你是助理'})
        self.put(self.base / 'prompts/history.json',
                 [{'role': 'user', 'content': '幾點'}, ASKS, RESULT, REPLY])
        self.put(self.base / 'tools.json', [{'type': 'function', 'function': {'name': 'date', 'description': '看時間'},
                                             '_meta': {'argv': ['date']}}])
        self.put(self.base / 'info.json', dict(self.info, tools=['tools.json']))
        code, out = self.run_talk('/context 2\n/history 2\n/tools\n/help\n', env={})
        self.assertEqual(code, 0)
        self.assertIn('system 4 字', out)
        self.assertIn('history 4 則，', out)
        self.assertIn('（user 1／assistant 2／tool 1）', out)
        self.assertIn('tools  1 個', out)
        self.assertIn('  [結果 date：12:00:00]', out)
        self.assertIn('assistant: 現在 12 點', out)
        self.assertIn('date  看時間', out)
        self.assertIn('/quit', out)

    def test_pause_continue(self):
        code, out = self.run_talk('/pause\n/status\n/continue\n', env={})
        self.assertIn('paused ', out)
        self.assertIn('手動暫停', out)
        self.assertIn('continued: 解除手動暫停', out)
        self.assertFalse((self.base / 'paused').exists())

    # ---- 逾時、晚到、卡住 --------------------------------------------------

    def test_timeout_then_late_reply_on_enter(self):
        self.registered()
        errors = self.answer(REPLY, delay=.6)
        # 第一句 0.2 秒就逾時；空行不送，但會印晚到的回話；/wait 之後不會再印一次。
        lines = ['慢慢來\n']
        stdin = _SlowInput(lines + ['\n', '/wait 0\n'], gap={1: .9})
        with patch.dict(os.environ, self.env, clear=True), patch('sys.stdin', stdin), \
                patch('sys.stdout', new_callable=io.StringIO) as out:
            code = agent.main(['talk', '--target', str(self.base), '--wait', '0.2'])
        self.assertEqual(code, 0)
        self.assertFalse(errors)
        self.assertIn('還在想：等了 0.2 秒', self.err.getvalue())
        self.assertEqual(out.getvalue().count('現在 12 點'), 1)
        self.assertIn('（沒有在等的話）', out.getvalue())
        self.assertNotIn('上一句還沒回', self.err.getvalue())

    def test_unregistered_banner_and_immediate_return(self):
        code, out = self.run_talk('你好\n', '--wait', '30', env={})
        err = self.err.getvalue()
        self.assertEqual(code, 0)
        self.assertEqual(out, '')
        self.assertIn('health 沒登記', err.splitlines()[0])
        self.assertIn('unregistered:', err)
        self.assertIn('已投入，不要再說一次', err)
        self.assertIn('上一句還沒回', err)  # 離開時提醒 listen --last
        self.assertTrue((self.base / 'input.json').exists())

    def test_ctrl_c_exits_zero(self):
        with patch('builtins.input', side_effect=KeyboardInterrupt):
            code, out = self.run_talk('', env={})
        self.assertEqual((code, out), (0, ''))

    def test_usage(self):
        for args in (['--wait'], ['--wait', 'abc'], ['--wait', '-1'], ['--json']):
            with self.subTest(args=args):
                self.assertEqual(self.run_talk('', *args, env={})[0], 2)

    def test_not_agent(self):
        (self.base / 'info.json').unlink()
        self.assertEqual(self.run_talk('', env={})[0], 1)

    def test_result_line(self):
        """talk 的 call_line／result_line 就是 aos_agent_listen_render 那兩個（09-24 talk 微調：跟 listen 對齊字樣）。"""
        self.assertEqual(talk.result_line('date', '工具 date 失敗（exit 1）：壞  掉\n了'),
                         '[結果 date 2 行：工具 date 失敗（exit 1）：壞  掉]')  # 第一行原樣，多行附行數
        self.assertEqual(talk.result_line('date', ''), '[結果 date：（空）]')
        self.assertEqual(talk.result_line('date', '工具箱裡有 3 樣\n'), '[結果 date：工具箱裡有 3 樣]')
        self.assertEqual(talk.call_line({'function': {'name': 'read', 'arguments': '{"path": "hello.py"}'}}),
                         '[呼叫 read path=hello.py]')
        self.assertEqual(talk.call_line({'function': {'name': 'echo', 'arguments': '{"text": "a  b\\nc"}'}}),
                         '[呼叫 echo text=a  b\\nc]')  # 字串空白原樣、換行寫成 \n
        self.assertEqual(talk.call_line({'function': {'name': 'date', 'arguments': ''}}), '[呼叫 date]')

    # ---- astra 審查補的 ----------------------------------------------------

    def test_same_text_twice_not_answered_by_first(self):
        """必修 1：同一句送兩次，第一句的回話不能充當第二句的（第二句還在 input 裡）。"""
        self.registered()
        self.put(self.base / 'prompts/history.json', [])
        session = talk.Talk(self.base, 100, False, self.env)
        path, inode = aos_agent_say.deliver(str(self.base), 'input.json', '同一句', with_inode=True)
        session.pending = talk.Pending(0, '同一句', path, inode)
        # 第一句已經回完（記憶裡），但原路徑上還是第二句自己的檔
        self.put(self.base / 'prompts/history.json', [{'role': 'user', 'content': '同一句'}, REPLY])
        with patch('sys.stdout', new_callable=io.StringIO):
            self.assertFalse(session.check()[1])
            # 我的被收走、別人在同一路徑再投一份：inode 不同＝不是我的
            path.unlink()
            aos_home.write_json(path, {'role': 'user', 'content': '別人的'})
            self.put(self.base / 'prompts/history.json',
                     [{'role': 'user', 'content': '同一句'}, REPLY, {'role': 'user', 'content': '同一句'}, REPLY])
            self.assertTrue(session.check()[1])

    def test_stop_reason_even_if_history_broken(self):
        """必修 7：記憶讀壞時照樣看得到暫停，不乾等到逾時。"""
        self.registered()
        session = talk.Talk(self.base, 5000, False, self.env)
        (self.base / 'paused').write_text('x')
        (self.base / 'prompts').mkdir()
        (self.base / 'prompts/history.json').write_text('[')
        session.pending = talk.Pending(0, 'x', self.base / 'input.json', -1)
        started = time.monotonic()
        session.wait(5000)
        self.assertLess(time.monotonic() - started, 2)
        self.assertIn('paused:', self.err.getvalue())

    def test_history_shortened_drops_pending(self):
        self.registered()
        self.put(self.base / 'prompts/history.json', [REPLY] * 5)
        session = talk.Talk(self.base, 100, False, self.env)
        session.pending = talk.Pending(5, 'x', self.base / 'input.json', -1)
        self.put(self.base / 'prompts/history.json', [REPLY])
        with patch('sys.stdout', new_callable=io.StringIO):
            session.check()
        self.assertIsNone(session.pending)
        self.assertIn('記憶被改短了', self.err.getvalue())

    def test_ctrl_c_during_banner_exits_zero(self):
        with patch('aos_agent_talk.Talk.banner', side_effect=KeyboardInterrupt):
            code, out = self.run_talk('', env={})
        self.assertEqual((code, out), (0, ''))

    def test_slash_arguments_checked(self):
        code, out = self.run_talk('/quit now\n/pause x\n/wait abc\n/continue --all\n/status x\n/history 0\n', env={})
        self.assertEqual(code, 0)
        self.assertEqual(self.err.getvalue().count('aos-agent: Usage:'), 6)
        self.assertFalse((self.base / 'paused').exists())
        self.assertEqual(out, '')

    def test_farewell_prints_late_reply_instead_of_warning(self):
        """必修 6：逾時後回話在打字時到了，離開前補印、不說「還沒回」。"""
        self.registered()
        errors = self.answer(REPLY, delay=.3)
        stdin = _SlowInput(['慢\n', '/quit\n'], gap={1: .8})
        with patch.dict(os.environ, self.env, clear=True), patch('sys.stdin', stdin), \
                patch('sys.stdout', new_callable=io.StringIO) as out, \
                patch('aos_agent_talk.Talk.peek'):  # 不讓提示符前的補印先做掉
            agent.main(['talk', '--target', str(self.base), '--wait', '0.1'])
        self.assertFalse(errors)
        self.assertEqual(out.getvalue(), '現在 12 點\n')
        self.assertNotIn('上一句還沒回', self.err.getvalue())

    def test_prompt_goes_to_stderr_when_stdout_redirected(self):
        stdin = io.StringIO('/tools\n')
        stdin.isatty = lambda: True
        with patch.dict(os.environ, {}, clear=True), patch('sys.stdin', stdin), \
                patch('sys.stdout', new_callable=io.StringIO) as out:
            code = agent.main(['talk', '--target', str(self.base)])
        self.assertEqual(code, 0)
        self.assertEqual(out.getvalue(), '（沒有工具）\n')
        self.assertIn('> ', self.err.getvalue())

    def test_context_line_cut(self):
        self.put(self.base / 'prompts/history.json',
                 [{'role': 'assistant', 'content': '長' * 70, 'tool_calls': [CALL]}])
        code, out = self.run_talk('/context 1\n', env={})
        line = [l for l in out.splitlines() if l.startswith('  assistant')][0]
        self.assertEqual(len(line), 2 + 80 + 1)


class _SlowInput(io.StringIO):
    """第 i 行讀之前先睡 gap[i] 秒（模擬人隔一陣子才按 Enter）。"""

    def __init__(self, lines, gap):
        super().__init__(''.join(lines))
        self.gap, self.n = gap, 0

    def readline(self, *args):
        time.sleep(self.gap.get(self.n, 0))
        self.n += 1
        return super().readline(*args)


class TalkPipeTests(unittest.TestCase):
    """真的開一個進程、stdin 走管線（不是 tty：沒有提示符、沒有等待提示）。"""

    def test_pipe_eof(self):
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            home = os.path.join(root, 'amy')
            env = {k: v for k, v in os.environ.items() if k != 'AOS_KERNEL_HOME'}
            subprocess.run([sys.executable, CLI, 'init', '--target', home], env=env,
                           check=True, capture_output=True)
            run = subprocess.run([sys.executable, CLI, 'talk', '--target', home], env=env,
                                 input='/tools\n/nope\n', capture_output=True, text=True, timeout=30)
            self.assertEqual(run.returncode, 0)
            self.assertEqual(run.stdout, 'date  取得現在的本機日期與時間\n')
            self.assertIn('沒有這個指令', run.stderr)
            self.assertNotIn('> ', run.stdout)


if __name__ == '__main__':
    unittest.main()
