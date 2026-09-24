"""aos-agent tools add（aos-agent.md §1.8）與 base 工具包裝進真 agent 的整合往返。"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest

from _kernel_util import KernelCase, CLI, PY, read_json, wait_for

PACKAGE = Path(__file__).resolve().parents[2] / 'tools' / 'base'
NAMES = ['read', 'write', 'edit', 'bash', 'grep', 'find', 'ls']


def run_agent(*args, cwd=None):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    return subprocess.run([PY, str(CLI / 'aos-agent'), *map(str, args)], cwd=cwd, env=env,
                          stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=20)


class ToolsAddTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='aos-tools-add-'))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.bob = self.root / 'bob'
        result = run_agent('init', '--target', self.bob)
        self.assertEqual(result.returncode, 0, result.stderr)

    def add(self, *extra, target=None, code=0):
        result = run_agent('tools', 'add', *extra, '--target', target or self.bob)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return result

    def info(self, base=None):
        return read_json((base or self.bob) / 'info.json')

    def test_install_into_init_home(self):
        """init 的家 tools 是整個資料夾：複製程式、寫 base.json、建 workspace，info.json 不動。"""
        before = self.info()
        out = self.add('base').stdout
        self.assertIn('installed base', out)
        self.assertIn('read、write、edit、bash、grep、find、ls', out)
        self.assertIn('下一批工具生效，不用重 start', out)  # 09-24 access-impl 改句
        self.assertEqual(self.info(), before)
        tools = read_json(self.bob / 'tools/base.json')
        self.assertEqual([t['function']['name'] for t in tools], NAMES)
        for name in NAMES:
            self.assertTrue(os.access(self.bob / 'tools/base' / name, os.X_OK), name)
        self.assertFalse((self.bob / 'tools/base/base.json').exists())
        self.assertTrue((self.bob / 'workspace').is_dir())
        self.assertEqual(read_json(self.bob / 'tools/base/config.json'), {'root': 'workspace'})
        hidden = [p.name for p in (self.bob / 'tools').iterdir() if p.name.startswith('.')]
        self.assertEqual(len(hidden), 1)
        self.assertTrue((self.bob / 'tools/base').is_symlink())
        self.assertEqual(os.readlink(self.bob / 'tools/base'), hidden[0])

    def test_installed_tools_run_from_agent_home(self):
        """裝好的工具以 agent 家為 cwd 跑得起來，檔案落在 workspace/。"""
        self.add('base')
        result = subprocess.run(['tools/base/write'], cwd=self.bob, capture_output=True, text=True,
                                input=json.dumps({'path': 'x/y.txt', 'content': 'hi\n'}))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual((self.bob / 'workspace/x/y.txt').read_text(), 'hi\n')

    def test_already_installed_and_force_keeps_config(self):
        self.add('base')
        (self.bob / 'tools/base/config.json').write_text('{"root": "elsewhere"}')
        (self.bob / 'elsewhere').mkdir()
        err = self.add('base', code=1).stderr
        self.assertIn('AlreadyExists', err)
        self.assertIn('--force', err)
        (self.bob / 'tools/base/read').write_text('broken')
        out = self.add('base', '--force').stdout
        self.assertIn(str(self.bob / 'elsewhere'), out)
        self.assertEqual(read_json(self.bob / 'tools/base/config.json'), {'root': 'elsewhere'})
        self.assertNotEqual((self.bob / 'tools/base/read').read_text(), 'broken')

    def test_root_option_writes_absolute(self):
        project = self.root / 'proj'
        project.mkdir()
        result = run_agent('tools', 'add', 'base', '--target', self.bob, '--root', 'proj', cwd=self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(read_json(self.bob / 'tools/base/config.json'), {'root': str(project)})
        self.assertFalse((self.bob / 'workspace').exists())
        self.assertEqual(result.stderr, '')

    def test_root_missing_refused(self):
        err = self.add('base', '--root', str(self.root / 'nope'), code=1).stderr
        self.assertIn('NotFound', err)
        self.assertFalse((self.bob / 'tools/base.json').exists())

    def test_root_containing_home_warns(self):
        result = self.add('base', '--root', str(self.root))
        self.assertIn('包含 agent 家', result.stderr)

    def test_appends_entry_for_manual_home(self):
        amy = self.root / 'amy'
        amy.mkdir()
        (amy / 'info.json').write_text(json.dumps({'_metainfo': {'_type': 'llm_agent', '_version': 1},
                                                   'llm': {'model': 'm'}, 'tools': ['t.json']}))
        (amy / 't.json').write_text('[]')
        out = self.add('base', target=amy).stdout
        self.assertIn('補了 "tools/base.json"', out)
        self.assertEqual(self.info(amy)['tools'], ['t.json', 'tools/base.json'])
        self.add('base', '--force', target=amy)
        self.assertEqual(self.info(amy)['tools'], ['t.json', 'tools/base.json'])

    def test_no_tools_key_gets_one(self):
        amy = self.root / 'amy'
        amy.mkdir()
        (amy / 'info.json').write_text(json.dumps({'_metainfo': {'_type': 'llm_agent', '_version': 1},
                                                   'llm': {'model': 'm'}}))
        self.add('base', target=amy)
        self.assertEqual(self.info(amy)['tools'], ['tools/base.json'])

    def test_directive_tools_refused(self):
        amy = self.root / 'amy'
        amy.mkdir()
        (amy / 'list.json').write_text('[]')
        (amy / 'info.json').write_text(json.dumps({'_metainfo': {'_type': 'llm_agent', '_version': 1},
                                                   'llm': {'model': 'm'}, 'tools': {'$ref': 'list.json'}}))
        err = self.add('base', target=amy, code=1).stderr
        self.assertIn('字面陣列', err)
        self.assertFalse((amy / 'tools').exists())

    def test_name_clash_refused(self):
        (self.bob / 'tools/mine.json').write_text(json.dumps([
            {'type': 'function', 'function': {'name': 'bash'}, '_meta': {'argv': ['true']}}]))
        err = self.add('base', code=1).stderr
        self.assertIn('ToolInvalid', err)
        self.assertIn('bash', err)
        self.assertFalse((self.bob / 'tools/base').exists())
        self.assertFalse((self.bob / 'tools/base.json').exists())

    def test_unknown_package_and_bad_package(self):
        err = self.add('nope', code=1).stderr
        self.assertIn('NotFound', err)
        self.assertIn('base', err)
        pkg = self.root / 'pkg'
        pkg.mkdir()
        err = self.add(str(pkg), code=1).stderr
        self.assertIn('pkg.json', err)
        (pkg / 'pkg.json').write_text(json.dumps([{'type': 'function', 'function': {'name': 'x'}}]))
        self.assertIn('ToolInvalid', self.add(str(pkg), code=1).stderr)
        self.assertFalse((self.bob / 'tools/pkg').exists())

    def test_custom_package_by_path(self):
        pkg = self.root / 'hello'
        pkg.mkdir()
        (pkg / 'hello.json').write_text(json.dumps([{'type': 'function', 'function': {'name': 'hello'},
                                                     '_meta': {'argv': ['tools/hello/run']}}]))
        (pkg / 'run').write_text('#!/bin/sh\necho hello\n')
        (pkg / 'run').chmod(0o755)
        out = self.add(str(pkg)).stdout
        self.assertIn('installed hello', out)
        self.assertNotIn('工作根目錄', out)
        self.assertTrue(os.access(self.bob / 'tools/hello/run', os.X_OK))

    def test_not_an_agent_and_usage(self):
        self.assertIn('NotAnAgent', self.add('base', target=self.root, code=1).stderr)
        result = run_agent('tools', 'remove', 'base', '--target', self.bob)
        self.assertEqual(result.returncode, 2)
        result = run_agent('tools', '--target', self.bob)
        self.assertEqual(result.returncode, 2)


# 假模型照劇本叫工具：write → bash → edit → bash → 收尾（每一步看它收到幾則 tool 訊息）。
SCRIPT = [('write', {'path': 'hello.py', 'content': 'print("hello")\n'}),
          ('bash', {'command': 'python3 hello.py'}),
          ('edit', {'path': 'hello.py', 'old_string': 'hello', 'new_string': 'hi'}),
          ('bash', {'command': 'python3 hello.py'})]


class ToolsBaseIntegrationTests(KernelCase):
    def setUp(self):
        super().setUp()
        self.requests = []
        records = self.requests

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                records.append(body)
                step = sum(1 for m in body['messages'] if m['role'] == 'tool')
                if step < len(SCRIPT):
                    name, args = SCRIPT[step]
                    message = {'role': 'assistant', 'content': None, 'tool_calls': [
                        {'id': 'c%d' % step, 'type': 'function',
                         'function': {'name': name, 'arguments': json.dumps(args)}}]}
                else:
                    message = {'role': 'assistant', 'content': '完成'}
                raw = json.dumps({'choices': [{'message': message}]}).encode()
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
        config = self.root / 'llm.json'
        self.write(config, {'_metainfo': {'_type': 'llm_config', '_version': 1}, 'models': {
            'default': {'endpoint': 'http://127.0.0.1:%d/v1' % self.server.server_port,
                        'model': 'local-test', 'timeout_ms': 3000}}})
        path = str(CLI) + os.pathsep + os.environ.get('PATH', '/usr/bin:/bin')
        self.env = dict(os.environ, AOS_KERNEL_HOME=str(self.home), PATH=path, PYTHONDONTWRITEBYTECODE='1')
        self.cpus = {'k': {'pool': 'kernel'}, '0': {'envs': {'PATH': path}},
                     'llm': {'pool': 'llm', 'envs': {'PATH': path, 'AOS_LLM_CONFIG': str(config)}}}
        self.base = self.root / 'coder'
        self.addCleanup(self.orderly_stop)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def orderly_stop(self):
        if self.daemon_process is not None and self.daemon_process.poll() is None:
            if self.state().get('phase') != 'stopped':
                self.kernel_stop()
            self.daemon_stop()

    def agent(self, *args):
        result = subprocess.run([PY, str(CLI / 'aos-agent'), *map(str, args)], env=self.env,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_write_bash_edit_bash_round_trip(self):
        """真 daemon＋kernel＋agent：模型依序叫 write→bash→edit→bash，檔案與記憶都對。"""
        self.setup_running(cpus=self.cpus)
        self.agent('init', '--target', self.base)
        self.agent('tools', 'add', 'base', '--target', self.base)
        info = read_json(self.base / 'info.json')
        info['tick']['interval_ms'] = 5
        self.write(self.base / 'info.json', info)
        self.agent('start', '--target', self.base)
        self.agent('say', '建 hello.py、跑、改成 hi、再跑', '--target', self.base)

        def done():
            history = read_json(self.base / 'prompts/history.json', [])
            return bool(history) and history[-1].get('content') == '完成'
        wait_for(done, timeout=40)
        self.agent('stop', '--target', self.base)
        history = read_json(self.base / 'prompts/history.json')
        results = [m['content'] for m in history if m['role'] == 'tool']
        self.assertEqual(len(results), 4, history)
        self.assertIn('created hello.py', results[0])
        self.assertEqual(results[1].strip(), 'hello')
        self.assertIn('edited hello.py', results[2])
        self.assertEqual(results[3].strip(), 'hi')
        self.assertEqual((self.base / 'workspace/hello.py').read_text(), 'print("hi")\n')
        sent = {t['function']['name'] for t in self.requests[0]['tools']}
        self.assertTrue(set(NAMES) <= sent)
        self.assertNotIn('_meta', self.requests[0]['tools'][0])


if __name__ == '__main__':
    unittest.main()
