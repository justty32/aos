"""fix-r4：--target、listen 三態、手動暫停、tick 鎖（真的兩個程序）、舊版 tick.json。"""
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch

import aos_agent as agent
import aos_agent_listen as listen_api
import aos_agent_status as status
import test_agent_tick as fixture

CLI = Path(__file__).resolve().parents[2] / 'cli' / 'aos-agent'


class FixR4Tests(unittest.TestCase):
    for _name in ('setUp', 'put', 'read', 'kernel_thread', 'register'):
        locals()[_name] = getattr(fixture.AgentTickTests, _name)

    def cli(self, *args, env=None):
        with patch.dict(os.environ, env or {}, clear=True), \
                patch('sys.stdout', new_callable=io.StringIO) as out:
            code = agent.main(list(args))
        return code, out.getvalue()

    def registered(self):
        self.put(self.base / 'tick.json', {'envs': self.env})
        self.put(self.k / 'state.json', {'procs': {'agent-bob': {'status': 'idle', 'fails': 0}}, 'replies': []})

    def healthy(self):
        return patch('aos_kernel_health.health', return_value=('ok', 'ok'))

    def snapshot(self):
        return {str(p.relative_to(self.base)): (p.stat().st_mtime_ns, p.read_bytes() if p.is_file() else None)
                for p in self.base.rglob('*')}

    def proc_env(self):
        return dict(os.environ, AOS_KERNEL_HOME=str(self.k), PYTHONDONTWRITEBYTECODE='1')

    # --target 與來源 ------------------------------------------------------

    def test_not_an_agent_names_source(self):
        old = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, old)
        self.assertEqual(self.cli('status')[0], 1)
        self.assertIn('取自 目前資料夾（沒給 --target）', self.err.getvalue())
        self.assertEqual(self.cli('listen', '--target', str(self.root / 'nope'))[0], 1)
        self.assertIn('取自 --target', self.err.getvalue())
        self.assertIn('NotAnAgent', self.err.getvalue())

    def test_target_every_command(self):
        with patch('sys.stdout', new_callable=io.StringIO):
            for command in ('status', 'pause', 'continue', 'listen'):
                with self.subTest(command=command):
                    self.put(self.base / 'prompts/history.json', [fixture.MESSAGE])
                    self.assertEqual(agent.main([command, '--target', str(self.base)]), 0)

    def test_say_wait_word_is_text(self):
        code, _ = self.cli('say', '--wait', '你好', '--target', str(self.base))
        self.assertEqual(code, 101)  # 沒登記：立刻退
        self.assertEqual(self.read(self.base / 'input.json')['content'], '你好')

    # listen ---------------------------------------------------------------

    def test_listen_default_is_last(self):
        self.put(self.base / 'prompts/history.json', [fixture.MESSAGE])
        self.assertEqual(self.cli('listen', '--target', str(self.base)), (0, '完成\n'))
        self.assertEqual(self.cli('listen', '--target', str(self.base), '--last'), (0, '完成\n'))

    def test_listen_wait_prints_next_reply(self):
        self.registered()
        self.put(self.base / 'prompts/history.json', [fixture.MESSAGE])
        def reply(_):
            self.put(self.base / 'prompts/history.json',
                     [fixture.MESSAGE, {'role': 'user', 'content': 'q'}, {'role': 'assistant', 'content': '新回話'}])
        with self.healthy(), patch.object(listen_api.time, 'sleep', side_effect=reply):
            self.assertEqual(self.cli('listen', '--target', str(self.base), '--wait', '5', env=self.env),
                             (0, '新回話\n'))

    def test_listen_wait_ignores_old_and_mid_turn(self):
        self.registered()
        self.put(self.base / 'prompts/history.json', [fixture.MESSAGE])
        steps = []
        def advance(_):
            steps.append(1)
            if len(steps) == 1:  # 還在輪中：只有 tool_calls、state 不是 idle
                self.put(self.base / 'state.json', {'state': 'act'})
                self.put(self.base / 'prompts/history.json', [fixture.MESSAGE, fixture.ASSISTANT])
            else:
                self.put(self.base / 'state.json', {'state': 'idle'})
                self.put(self.base / 'prompts/history.json', [fixture.MESSAGE, fixture.ASSISTANT,
                         {'role': 'tool', 'tool_call_id': 'c1', 'content': 'x'},
                         {'role': 'assistant', 'content': '輪完'}])
        with self.healthy(), patch.object(listen_api.time, 'sleep', side_effect=advance):
            self.assertEqual(self.cli('listen', '--target', str(self.base), '--wait', env=self.env),
                             (0, '輪完\n'))
        self.assertEqual(len(steps), 2)

    def test_listen_wait_timeout(self):
        self.registered()
        self.put(self.base / 'prompts/history.json', [fixture.MESSAGE])
        with self.healthy():
            code, output = self.cli('listen', '--target', str(self.base), '--wait', '0', env=self.env)
        self.assertEqual(code, 101)
        self.assertIn('Timeout: 等了 0 秒沒有新回話', self.err.getvalue())
        self.assertTrue(output.startswith('health ok'))

    def test_listen_wait_unregistered_and_paused(self):
        code, _ = self.cli('listen', '--target', str(self.base), '--wait')
        self.assertEqual(code, 101)
        self.assertIn('unregistered:', self.err.getvalue())
        self.registered()
        (self.base / 'paused').write_text('x')
        with self.healthy():
            self.assertEqual(self.cli('listen', '--target', str(self.base), '--wait', env=self.env)[0], 101)
        self.assertIn('aos-agent: paused: 已手動暫停', self.err.getvalue())

    def test_listen_follow_real_process(self):
        """--follow 是阻塞程式：真的開一支，一則一則印，Ctrl-C 退 0。"""
        self.put(self.base / 'prompts/history.json', [fixture.MESSAGE])
        proc = subprocess.Popen([sys.executable, str(CLI), 'listen', '--follow', '--target', str(self.base)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=self.proc_env())
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        time.sleep(.5)
        history = [fixture.MESSAGE, {'role': 'user', 'content': 'q'}, fixture.ASSISTANT]
        self.put(self.base / 'prompts/history.json', history)
        time.sleep(.5)
        history += [{'role': 'tool', 'tool_call_id': 'c1', 'content': 'x'}, {'role': 'assistant', 'content': '第二則'}]
        self.put(self.base / 'prompts/history.json', history)
        time.sleep(.5)
        proc.send_signal(signal.SIGINT)
        out, err = proc.communicate(timeout=5)
        self.assertEqual(proc.returncode, 0, err)
        self.assertEqual(out, '(tool_calls: sh)\n第二則\n')

    # pause／continue --------------------------------------------------------

    def test_pause_tick_does_nothing(self):
        self.put(self.base / 'input.json', 'hi')
        self.assertEqual(self.cli('pause', '--target', str(self.base))[0], 0)
        self.assertTrue((self.base / 'paused').exists())
        before = self.snapshot()
        self.assertEqual(agent.tick(self.base, self.env), 0)
        after = self.snapshot()
        before.pop('.tick.lock', None), after.pop('.tick.lock', None)
        self.assertEqual(after, before)
        self.assertEqual(self.cli('pause', '--target', str(self.base))[1], '已經暫停了（aos-agent continue --target %s 解除）\n' % self.base)
        self.assertEqual(self.cli('continue', '--target', str(self.base)), (0, 'continued: 解除手動暫停\n'))
        self.assertEqual(agent.tick(self.base, self.env), 0)
        self.assertEqual(self.read(self.base / 'state.json')['state'], 'think')

    def test_pause_needs_agent_and_works_with_broken_info(self):
        self.assertEqual(self.cli('pause', '--target', str(self.root))[0], 1)
        (self.base / 'info.json').write_text('{')
        self.assertEqual(self.cli('pause', '--target', str(self.base))[0], 0)

    def test_continue_clears_both(self):
        self.put(self.base / 'state.json', {'waits': [{'$opt': 'consume', '$val': 'continue-x.json'}]})
        (self.base / 'paused').write_text('x')
        code, output = self.cli('continue', '--target', str(self.base))
        self.assertEqual(code, 0)
        self.assertEqual(output, 'continued: 解除手動暫停\ncontinued: touched %s\n' % (self.base / 'continue-x.json')
                         + '已解除暫停，等下一次成功（aos-agent status --target %s 看）\n' % self.base)
        self.assertFalse((self.base / 'paused').exists())

    def test_status_distinguishes_pauses(self):
        self.registered()
        (self.base / 'paused').write_text('x')
        with self.healthy():
            data = status.collect(self.base, self.env)
            self.assertEqual(data['health']['code'], 'manual_paused')
            self.assertTrue(data['manual_paused'] and data['manual_paused_since'])
            self.assertFalse(data['paused'])
            _, output = self.cli('status', '--target', str(self.base), env=self.env)
        self.assertTrue(output.startswith('health 手動暫停（aos-agent continue --target %s）' % self.base))
        self.assertIn('手動暫停中（', output.splitlines()[2])
        self.put(self.base / 'state.json', {'waits': [{'$opt': 'consume', '$val': 'continue-x.json'}]})
        with self.healthy():
            self.assertTrue(status.collect(self.base, self.env)['health']['message'].startswith('手動暫停＋連敗暫停'))
            (self.base / 'paused').unlink()
            self.assertEqual(status.collect(self.base, self.env)['health']['code'], 'paused')

    def test_say_while_paused_accepts(self):
        self.registered()
        (self.base / 'paused').write_text('x')
        with self.healthy():
            code, output = self.cli('say', 'hi', '--target', str(self.base), env=self.env)
        self.assertEqual(code, 0)
        self.assertIn('said -> ', output)
        self.assertIn('warn: 已暫停，continue 後才會處理', self.err.getvalue())
        self.assertTrue((self.base / 'input.json').exists())
        (self.base / 'input.json').unlink()
        with self.healthy():
            self.assertEqual(self.cli('say', 'hi', '--target', str(self.base), '--wait', env=self.env)[0], 101)
        self.assertIn('paused: 已手動暫停', self.err.getvalue())

    # tick 鎖：真的兩個程序 --------------------------------------------------

    def test_tick_lock_second_process_yields(self):
        """history 換成 FIFO：第一個 tick 讀記憶時卡住（持鎖），第二個 tick 要立刻退 101、不動檔。"""
        history = self.base / 'prompts/history.json'
        history.parent.mkdir()
        os.mkfifo(history)
        self.put(self.base / 'input.json', 'hi')
        first = subprocess.Popen([sys.executable, str(CLI), 'tick', '--target', str(self.base)],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=self.proc_env())
        self.addCleanup(lambda: first.poll() is None and first.kill())
        lock = self.base / '.tick.lock'
        deadline = time.monotonic() + 5
        while (not lock.exists() or not lock.read_text().strip()) and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertEqual(lock.read_text().strip(), str(first.pid))
        before = self.snapshot()
        second = subprocess.run([sys.executable, str(CLI), 'tick', '--target', str(self.base)],
                                capture_output=True, text=True, env=self.proc_env(), timeout=10)
        self.assertEqual(second.returncode, 101, second.stderr)
        self.assertEqual(second.stderr, 'aos-agent: busy: 另一個 tick 正在跑（pid %d），這格不做事\n' % first.pid)
        self.assertEqual(self.snapshot(), before)
        with open(history, 'w') as fifo:  # 放第一個走
            fifo.write('[]')
        out, err = first.communicate(timeout=10)
        self.assertEqual(first.returncode, 0, err)
        self.assertEqual(self.read(self.base / 'state.json')['state'], 'think')
        third = subprocess.run([sys.executable, str(CLI), 'tick', '--target', str(self.base)],
                               capture_output=True, text=True, env=self.proc_env(), timeout=10)
        self.assertNotIn('busy', third.stderr)

    def test_tick_lock_held_by_other_process(self):
        """別的程序（例如人用 flock 手改 state）持鎖時，tick 讓掉；對方一退就能跑。"""
        holder = subprocess.Popen([sys.executable, '-c', (
            'import fcntl, os, sys, time\n'
            'fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT)\n'
            'fcntl.flock(fd, fcntl.LOCK_EX)\n'
            'os.write(fd, b"4242\\n")\n'
            'print("held", flush=True)\n'
            'sys.stdin.read()\n'), str(self.base / '.tick.lock')],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        self.addCleanup(lambda: holder.poll() is None and holder.kill())
        self.assertEqual(holder.stdout.readline(), 'held\n')
        self.put(self.base / 'input.json', 'hi')
        self.assertEqual(agent.tick(self.base, self.env), 101)
        self.assertIn('另一個 tick 正在跑（pid 4242）', self.err.getvalue())
        self.assertFalse((self.base / 'state.json').exists())
        holder.communicate('', timeout=5)
        self.assertEqual(agent.tick(self.base, self.env), 0)

    def test_tick_no_lock_file_for_non_agent(self):
        self.assertEqual(agent.tick(self.root, self.env), 1)
        self.assertFalse((self.root / '.tick.lock').exists())

    def test_tick_other_home_no_lock_no_pause(self):
        """astra 審查：info.json 字面是別種家（例如 kernel）就不建鎖、不看 paused，直接 NotAnAgent。"""
        self.put(self.root / 'kk/info.json', {'_metainfo': {'_type': 'kernel', '_version': 1}})
        (self.root / 'kk/paused').write_text('x')
        self.assertEqual(agent.tick(self.root / 'kk', self.env), 1)
        self.assertIn('NotAnAgent', self.err.getvalue())
        self.assertFalse((self.root / 'kk/.tick.lock').exists())
        self.assertEqual(self.cli('pause', '--target', str(self.root / 'kk'))[0], 1)

    def test_tick_lock_io_failure_closes_fd(self):
        """astra 審查：鎖檔寫 pid 失敗時也要關 fd，同一行程下一次 tick 不會被自己擋住。"""
        self.put(self.base / 'input.json', 'hi')
        with patch('aos_agent_runtime.os.ftruncate', side_effect=OSError(28, 'No space left')):
            self.assertEqual(agent.tick(self.base, self.env), 1)
        self.assertEqual(agent.tick(self.base, self.env), 0)
        self.assertNotIn('busy', self.err.getvalue())

    def test_tick_not_agent_names_source(self):
        with patch.dict(os.environ, {'AOS_KERNEL_HOME': str(self.k)}, clear=True):
            self.assertEqual(agent.main(['tick', '--target', str(self.root)]), 1)
        self.assertIn('取自 --target', self.err.getvalue())

    def test_wait_seconds_bounds(self):
        for value in ('inf', '1e309', 'nan', '604801'):
            with self.subTest(value=value), self.assertRaises(SystemExit) as cm:
                self.cli('listen', '--target', str(self.base), '--wait', value)
            self.assertEqual(cm.exception.code, 2)

    # 舊版 tick.json（fix-r4 前：位置參數＋AOS_K）------------------------------

    def test_start_rewrites_legacy_tick(self):
        self.put(self.base / 'tick.json', {'argv': ['aos-agent', 'tick', str(self.base)],
                                           'envs': {'AOS_K': str(self.k)}})
        rc, _ = self.register()
        self.assertEqual(rc, 0)
        tick = self.read(self.base / 'tick.json')
        self.assertEqual(tick['argv'], ['aos-agent', 'tick', '--target', str(self.base)])
        self.assertEqual(tick['envs'], {'AOS_KERNEL_HOME': str(self.k)})

    def test_legacy_tick_other_kernel_mismatch(self):
        self.put(self.base / 'tick.json', {'envs': {'AOS_K': '/other/K'}})
        self.assertEqual(agent.start(self.base, self.env), 1)
        self.assertIn('KernelMismatch', self.err.getvalue())

    def test_legacy_tick_is_read_by_status_and_stop(self):
        self.put(self.base / 'tick.json', {'envs': {'AOS_K': str(self.k)}})
        self.assertEqual(status.tick_kernel(self.base), str(self.k))
        self.assertEqual(status.collect(self.base, {})['kernel']['home'], str(self.k))


if __name__ == '__main__':
    unittest.main()
