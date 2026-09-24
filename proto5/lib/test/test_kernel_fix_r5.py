"""fix-r5：kernel 這一半——boot 印一行、check --probe 與總結行、ls 的恢復中與 agent 標記。"""
import contextlib
import http.server
import io
import json
import os
import signal
import socket
import threading
from unittest.mock import patch

import aos_kernel as kernel
import aos_kernel_check
import aos_kernel_cli
from aos_kernel_health import health
from _daemon_util import read_json, wait_for
from _kernel_util import CLI, KernelCase


class _Handler(http.server.BaseHTTPRequestHandler):
    models = {'data': [{'id': 'm'}]}
    seen = []

    def log_message(self, *args):
        pass

    def _reply(self, code, body):
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self.seen.append(('GET', self.path, self.headers.get('Authorization')))
        if self.models is None:
            self._reply(404, {'error': 'no list'})
        else:
            self._reply(200, self.models)

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        self.seen.append(('POST', self.path, json.loads(self.rfile.read(length))))
        self._reply(200, {'choices': [{'message': {'role': 'assistant', 'content': 'h'}}]})


class Server:
    def __init__(self, models):
        handler = type('H', (_Handler,), {'models': models, 'seen': []})
        self.httpd = http.server.HTTPServer(('127.0.0.1', 0), handler)
        self.seen = handler.seen
        self.url = 'http://127.0.0.1:%d/v1' % self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class ProbeTests(KernelCase):
    def serve(self, models):
        server = Server(models)
        self.addCleanup(server.close)
        return server

    def test_models_ok_and_missing_model_warns(self):
        server = self.serve({'data': [{'id': 'm'}]})
        level, message = aos_kernel_check.probe_endpoint({'endpoint': server.url, 'model': 'm', 'api_key': 'sk-1'})
        self.assertEqual(level, 'ok', message)
        self.assertEqual(server.seen[0], ('GET', '/v1/models', 'Bearer sk-1'))
        level, message = aos_kernel_check.probe_endpoint({'endpoint': server.url, 'model': 'zzz'})
        self.assertEqual(level, 'warn')
        self.assertIn('模型清單裡沒有 zzz', message)

    def test_no_model_list_falls_back_to_one_sentence(self):
        server = self.serve(None)
        level, message = aos_kernel_check.probe_endpoint({'endpoint': server.url, 'model': 'm'})
        self.assertEqual(level, 'ok', message)
        method, path, body = server.seen[-1]
        self.assertEqual((method, path, body['max_tokens'], body['model']), ('POST', '/v1/chat/completions', 1, 'm'))

    def test_closed_port_is_bad(self):
        endpoint = 'http://127.0.0.1:%d/v1' % free_port()
        level, message = aos_kernel_check.probe_endpoint({'endpoint': endpoint, 'model': 'm', 'api_key': 'sk-secret'})
        self.assertEqual(level, 'bad')
        self.assertIn('連不上', message)
        self.assertIn(endpoint, message)
        self.assertNotIn('sk-secret', message)

    def test_empty_model_list_warns(self):
        """astra 審查：空清單也算「清單裡沒有」。"""
        server = self.serve({'data': []})
        level, message = aos_kernel_check.probe_endpoint({'endpoint': server.url, 'model': 'm'})
        self.assertEqual(level, 'warn')
        self.assertIn('模型清單裡沒有 m', message)

    def test_incomplete_read_is_bad(self):
        """astra 審查：回覆宣告 100 bytes 卻只傳一半，要轉成 bad，不噴例外。"""
        class Short(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Length', '100')
                self.end_headers()
                self.wfile.write(b'{"data"')
                self.wfile.flush()
                self.close_connection = True

        httpd = http.server.HTTPServer(('127.0.0.1', 0), Short)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        level, message = aos_kernel_check.probe_endpoint(
            {'endpoint': 'http://127.0.0.1:%d/v1' % httpd.server_address[1], 'model': 'm'})
        self.assertEqual(level, 'bad', message)

    def check_cli(self, *extra, endpoint):
        if (self.home / 'info.json').exists():
            (self.home / 'info.json').unlink()  # 同一條測試第二次跑：K 家補齊重建
        llm = self.write(self.root / 'llm.json', {'_metainfo': {'_type': 'llm_config', '_version': 1},
                                                  'models': {'default': {'endpoint': endpoint, 'model': 'm'},
                                                             'again': {'endpoint': endpoint, 'model': 'm'}}})
        self.initialize(cpus={'k': {'pool': 'kernel'}, '0': {},
                              'llm': {'pool': 'llm', 'envs': {'AOS_LLM_CONFIG': llm}}})
        env = dict(os.environ, PATH='%s:%s' % (CLI, os.environ.get('PATH', '')))
        return self.raw_cli('check', '--target', self.home, '--daemon-target', self.daemon, *extra, env=env)

    def test_check_summary_lines(self):
        server = self.serve({'data': [{'id': 'm'}]})
        plain = self.check_cli(endpoint=server.url)
        self.assertEqual(plain.returncode, 0, plain.stdout)
        self.assertEqual(plain.stdout.splitlines()[-1], '設定檢查通過；未測模型連線（--probe 會測）')
        self.assertFalse(server.seen)  # 不帶 --probe 不連
        probed = self.check_cli('--probe', endpoint=server.url)
        self.assertEqual(probed.returncode, 0, probed.stdout)
        self.assertIn('ok   probe/', probed.stdout)
        self.assertEqual(probed.stdout.count('probe/'), 1)  # 同一個 endpoint＋model 只打一次
        self.assertEqual(probed.stdout.splitlines()[-1], '設定檢查通過；模型連線也測過')

    def test_check_probe_bad_port(self):
        result = self.check_cli('--probe', endpoint='http://127.0.0.1:%d/v1' % free_port())
        self.assertEqual(result.returncode, 1)
        self.assertIn('bad  probe/', result.stdout)
        self.assertEqual(result.stdout.splitlines()[-1], '有 bad，照上面的提示修好再 boot')


class HealthAndLsTests(KernelCase):
    def setUp(self):
        super().setUp()
        self.initialize(daemon=str(self.daemon))
        self.ledger = kernel.new_state(self.info, 'chain', 'k', kernel.CLI)
        self.write(self.home / 'state.json', self.ledger)
        self.children = {name: {'state': 'running', 'alive': True, 'target': ''} for name in self.info['cpus']}
        self.alive = patch('aos_daemon.is_alive', return_value=True).start()
        self.addCleanup(patch.stopall)
        patch('aos_daemon.read_state', return_value={'children': self.children}).start()

    def ls(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(aos_kernel_cli.main(['ls', '--target', str(self.home)]), 0)
        return out.getvalue()

    def test_dead_child_is_recovering(self):
        self.children['llm'].update(state='dead', alive=False)
        self.assertEqual(health(self.home), ('recovering', '恢復中（llm cpu dead，daemon 重拉中）'))
        self.assertTrue(self.ls().startswith('health 恢復中（llm cpu dead，daemon 重拉中）\n'))

    def test_daemon_down_cpu_lines_not_running(self):
        self.alive.return_value = False
        text = self.ls()
        self.assertTrue(text.startswith('health daemon 沒在跑'))
        self.assertNotIn('  running', text)
        self.assertIn('dead（daemon 沒在跑）', text)

    def agent(self, name, state=None, paused=False):
        home = self.root / name
        home.mkdir(exist_ok=True)
        self.write(home / 'info.json', {'_metainfo': {'_type': 'llm_agent', '_version': 1}, 'llm': {'model': 'm'}})
        if state is not None:
            self.write(home / 'state.json', state)
        if paused:
            (home / 'paused').write_text('x')
        self.ledger['procs']['agent-' + name] = {'target': str(home / 'tick.json'), 'once': False, 'status': 'idle',
                                                 'runs': 1, 'fails': 0, 'pending': None, 'not_before': 0}
        self.write(self.home / 'state.json', self.ledger)
        return home

    def test_agent_marks_on_first_line_and_rows(self):
        self.agent('bob', {'state': 'think', 'waits': [{'$opt': 'consume', '$val': 'continue-x.json'}]})
        self.agent('amy', paused=True)
        self.agent('cat', {'errors': 2})
        self.agent('dan')
        text = self.ls()
        self.assertTrue(text.startswith('health agent 暫停中：agent-bob（連敗）、agent-amy（手動）'
                                        '（修好原因後 aos-agent continue --all）\n'), text)
        rows = {line.split()[1]: line for line in text.splitlines() if line.startswith('proc ')}
        self.assertTrue(rows['agent-bob'].endswith('連敗暫停中'))
        self.assertTrue(rows['agent-amy'].endswith('手動暫停中'))
        self.assertTrue(rows['agent-cat'].endswith('重試中（連敗 2/3）'))
        self.assertTrue(rows['agent-dan'].endswith('pending -'))
        data = json.loads(aos_kernel_cli._summary(self.home, kernel.status(self.home), as_json=True))
        self.assertEqual(data['health']['code'], 'agents_paused')

    def test_retrying_and_resuming_first_line(self):
        self.agent('cat', {'errors': 1})
        self.assertTrue(self.ls().startswith('health 重試中：agent-cat（連敗 1/3）\n'))
        del self.ledger['procs']['agent-cat']
        home = self.agent('eve')
        (home / 'resumed').write_text('x')
        self.assertTrue(self.ls().startswith('health 已解除暫停，等下一次成功：agent-eve\n'))

    def test_kernel_problem_wins_over_agents(self):
        self.agent('bob', {'state': 'think', 'waits': [{'$opt': 'consume', '$val': 'continue-x.json'}]})
        self.children['llm'].update(state='dead')
        self.assertTrue(self.ls().startswith('health 恢復中'))


class RealDaemonTests(KernelCase):
    def test_boot_prints_and_kill_llm_shows_recovering(self):
        info = read_json(self.daemon / 'info.json')
        info['restart_delay_ms'] = 3000  # 放慢重拉，才看得到「恢復中」
        self.write(self.daemon / 'info.json', info)
        self.initialize()
        self.start_daemon()
        result = self.good_cli('boot', self.home, '--daemon-target', self.daemon)
        self.assertEqual(result.stdout, 'booted 3 cpus\n')
        wait_for(lambda: self.state().get('last_seq', 0) >= 1)
        pid = self.dstate()['children']['llm']['pid']
        self.groups.update(child['pid'] for child in self.dstate()['children'].values())
        os.kill(pid, signal.SIGKILL)
        wait_for(lambda: self.dstate()['children']['llm']['state'] == 'dead')
        text = self.good_cli('ls', self.home).stdout
        self.assertTrue(text.startswith('health 恢復中（llm cpu dead，daemon 重拉中）\n'), text)
        wait_for(lambda: self.dstate()['children']['llm']['state'] == 'running', timeout=8)
        self.groups.update(child['pid'] for child in self.dstate()['children'].values())
        self.kernel_stop()
        self.daemon_stop()
