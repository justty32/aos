"""真 daemon／kernel／aos-llm-call 與本機 HTTP 假模型的完整往返。"""
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import subprocess
import threading
from unittest.mock import patch

import aos_agent
from _kernel_util import KernelCase, CLI, PY, read_json, wait_for

ARGUMENTS = '{"文字":"原樣往返"}\n'
CALL = {'id': 'echo-1', 'type': 'function',
        'function': {'name': 'echo', 'arguments': ARGUMENTS}}
ASK_TOOL = {'role': 'assistant', 'content': None, 'tool_calls': [CALL]}
ANSWER = {'role': 'assistant', 'content': '已收到工具結果'}


class AgentIntegrationTests(KernelCase):
    def setUp(self):
        super().setUp()
        self.requests = []
        records = self.requests

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                records.append((self.path, body))
                message = ANSWER if any(m['role'] == 'tool' for m in body['messages']) else ASK_TOOL
                raw = json.dumps({'choices': [{'message': message}]}, ensure_ascii=False).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .01})
        self.thread.start()
        self.addCleanup(self.close_server)
        self.base = self.root / 'bob'
        self.base.mkdir()
        self.agent_info = {'_metainfo': {'_type': 'llm_agent', '_version': 1},
                           'llm': {'model': 'fake'}, 'tools': ['tools.json'],
                           'tick': {'interval_ms': 5}}
        self.write(self.base / 'info.json', self.agent_info)
        self.write(self.base / 'tools.json', [{'type': 'function', 'function': {'name': 'echo'},
                                             '_meta': {'argv': ['sh', '-c', 'cat']}}])
        config = self.root / 'llm.json'
        self.write(config, {'_metainfo': {'_type': 'llm_config', '_version': 1}, 'models': {
            'fake': {'endpoint': 'http://127.0.0.1:%d/v1' % self.server.server_port,
                     'model': 'local-test', 'timeout_ms': 3000}}})
        path = str(CLI) + os.pathsep + os.environ.get('PATH', '/usr/bin:/bin')
        self.env = dict(os.environ, AOS_K=str(self.home), PATH=path, PYTHONDONTWRITEBYTECODE='1')
        self.cpus = {'k': {'pool': 'kernel'}, '0': {'envs': {'PATH': path}},
                     'llm': {'pool': 'llm', 'envs': {'PATH': path, 'AOS_LLM_CONFIG': str(config)}}}
        # 即使測試 assertion 失敗，也先正常停 kernel，再停 daemon，最後才由基底兜底。
        self.addCleanup(self.orderly_stop)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.assertFalse(self.thread.is_alive())

    def orderly_stop(self):
        if self.daemon_process is not None and self.daemon_process.poll() is None:
            if self.state().get('phase') != 'stopped':
                self.kernel_stop()
            self.daemon_stop()

    def astate(self):
        return read_json(self.base / 'state.json', {})

    def history(self):
        return read_json(self.base / 'prompts/history.json', [])

    def agent_cli(self, command):
        return subprocess.run([PY, str(CLI / 'aos-agent'), command, str(self.base)],
                              env=self.env, capture_output=True, text=True, timeout=12)

    def tick(self):
        code = aos_agent.tick(self.base, self.env)
        self.assertIn(code, (0, 101))
        return code

    def finished(self):
        st = self.astate()
        return len(self.history()) == 4 and st.get('state') == 'idle' and st.get('batch') is None

    def drive(self):
        def step():
            self.tick()
            return self.finished()
        wait_for(step, timeout=15)

    def assert_conversation(self):
        self.assertEqual(self.history(), [{'role': 'user', 'content': '開始'}, ASK_TOOL,
                                         {'role': 'tool', 'tool_call_id': 'echo-1', 'content': ARGUMENTS}, ANSWER])
        self.assertEqual(len(self.requests), 2)
        self.assertTrue(all(path == '/v1/chat/completions' for path, _ in self.requests))
        self.assertEqual(self.requests[-1][1]['messages'][-1]['content'], ARGUMENTS)
        self.assertNotIn('_meta', self.requests[0][1]['tools'][0])

    def assert_clean_work(self):
        wait_for(lambda: not list((self.home / 'responses').glob('aw-*')), timeout=5)
        self.assertEqual(self.astate()['sweep'], [])
        self.assertEqual(list((self.base / 'work').iterdir()), [])

    def test_manual_round_trip(self):
        """手動 tick 走完 idle→think→act→think→idle 並清空回音與工作檔。"""
        self.setup_running(cpus=self.cpus)
        self.assertEqual(self.tick(), 101)
        self.write(self.base / 'input.json', '開始')
        states = ['idle']
        def step():
            self.tick()
            value = self.astate()['state']
            if value != states[-1]:
                states.append(value)
            return self.finished()
        wait_for(step, timeout=15)
        self.assertEqual(states, ['idle', 'think', 'act', 'think', 'idle'])
        self.assert_conversation()
        self.tick()
        self.assert_clean_work()

    def test_start_kernel_drives_and_stop_unregisters(self):
        """start 登記後由 kernel 驅動，stop 後 ls 不再列出 agent。"""
        self.setup_running(cpus=self.cpus)
        result = self.agent_cli('start')
        self.assertEqual(result.returncode, 0, result.stderr)
        inst = read_json(self.base / 'tick.json')
        self.assertEqual(inst, {'_metainfo': {'_type': 'posix', '_version': 1},
                               'argv': ['aos-agent', 'tick', str(self.base)], 'cwd': str(self.base),
                               'envs': {'AOS_K': str(self.home)},
                               'stderr': {'$opt': ['append', 'mkdir'],
                                          '$val': str(self.base / 'log/agent.err')}})
        self.write(self.base / 'input.json', '開始')
        wait_for(self.finished, timeout=15)
        wait_for(lambda: self.astate().get('sweep') == [], timeout=5)
        result = self.agent_cli('stop')
        self.assertEqual(result.returncode, 0, result.stderr)
        wait_for(lambda: 'agent-bob' not in self.state().get('procs', {}))
        self.assertNotIn('agent-bob', self.good_cli('ls', self.home).stdout)
        self.assert_conversation()
        self.assert_clean_work()
        log = self.base / 'log/agent.err'
        self.assertTrue(log.exists())
        self.assertNotIn('io:', log.read_text())
        self.assertNotIn('Traceback', log.read_text())

    def test_C9_queued_think_stop_boot_retry(self):
        """C-9 真版：llm cpu 被佔住時 stop 產生 Stopping，boot 後新批完成。"""
        self.setup_running(cpus=self.cpus)
        ready, release = self.root / 'ready', self.root / 'release'
        target = self.job('from pathlib import Path\nimport time\n'
                          'Path(%r).touch()\ndeadline = time.monotonic() + 10\n'
                          'while not Path(%r).exists() and time.monotonic() < deadline: time.sleep(.005)\n'
                          % (str(ready), str(release)), name='occupy')
        self.add(target, name='occupy', pool='llm', interval_ms=60000)
        wait_for(ready.exists)
        self.write(self.base / 'input.json', '開始')
        self.tick()
        self.tick()
        name = self.astate()['batch']['calls'][0]['name']
        wait_for(lambda: self.state().get('procs', {}).get(name, {}).get('status') == 'queued')
        self.assertEqual(self.requests, [])
        self.good_cli('stop', self.home, '--no-wait')
        wait_for(lambda: self.state().get('phase') in ('stopping', 'stopped'))
        release.touch()
        wait_for(lambda: self.state().get('phase') == 'stopped', timeout=8)
        wait_for(lambda: not self.dstate().get('children'), timeout=8)
        response = read_json(self.home / 'responses' / (name + '.json'))
        self.assertEqual(response['error']['data']['code'], 'Stopping')
        self.boot()
        captured = []
        def observe(step):
            if step == 'state.done':
                captured.append(copy.deepcopy(self.astate()['batch']['calls'][0]['done']))
        with patch.object(aos_agent, '_hook', observe):
            self.tick()
        self.assertFalse(captured[0]['count'])
        self.assertEqual((self.astate()['state'], self.astate()['errors']), ('think', 0))
        self.assertIsNone(self.astate()['batch'])
        self.tick()
        self.assertNotEqual(self.astate()['batch']['calls'][0]['name'], name)
        self.drive()
        self.tick()
        self.assert_conversation()
        self.assert_clean_work()

    def test_start_kernel_incompatible(self):
        """done_exit=101 的真 K 家讓 start 拒絕登記。"""
        self.setup_running(cpus=self.cpus, done_exit=101)
        result = self.agent_cli('start')
        self.assertEqual(result.returncode, 1)
        self.assertIn('KernelIncompatible', result.stderr)
        self.assertFalse((self.base / 'tick.json').exists())
        self.assertNotIn('agent-bob', self.state().get('procs', {}))

    def test_duplicate_start_already_exists(self):
        """重複 start 由真 kernel 回 AlreadyExists，CLI 退 1。"""
        self.setup_running(cpus=self.cpus)
        first = self.agent_cli('start')
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self.agent_cli('start')
        self.assertEqual(second.returncode, 1)
        self.assertIn('AlreadyExists', second.stderr)
        result = self.agent_cli('stop')
        self.assertEqual(result.returncode, 0, result.stderr)
        wait_for(lambda: 'agent-bob' not in self.state().get('procs', {}))

    def test_stop_unregisters_with_broken_or_missing_info(self):
        self.setup_running(cpus=self.cpus)
        for mode in ('llm', 'tools', 'missing', 'folder_only'):
            with self.subTest(mode=mode):
                self.write(self.base / 'info.json', self.agent_info)
                self.write(self.base / 'tools.json', [])
                self.assertEqual(self.agent_cli('start').returncode, 0)
                if mode == 'llm':
                    info = copy.deepcopy(self.agent_info)
                    del info['llm']
                    self.write(self.base / 'info.json', info)
                elif mode == 'tools':
                    (self.base / 'tools.json').write_text('{')
                else:
                    (self.base / 'info.json').unlink()
                    if mode == 'folder_only':
                        (self.base / 'tick.json').unlink()
                result = self.agent_cli('stop')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, 'stopped agent-bob\n')
                wait_for(lambda: 'agent-bob' not in self.state().get('procs', {}))
