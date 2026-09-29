import json
import os
import selectors
import shutil
import signal
import socket
import subprocess
import time
from pathlib import Path
from support import Case, BIN, ENV, poll, task, write_json
from aosproto.cgroup import FakeCgroup, live
from aosproto.common import MAX_LINE


class DaemonTests(Case):
    def register(self, target, parent, **extra):
        response = self.rpc('node.register', dict(node_id=str(target), parent_id=str(parent),
                                                identity_grant=[os.getuid()], **extra))
        self.assertNotIn('error', response, response)
        return response

    def test_end_to_end_fake(self):
        root = self.new_node(tasks=[task(command='echo hi > out.txt')])
        child = self.new_node('C', [task(command='echo child > result.txt')])
        self.start_daemon(root)
        result = self.completed(root)
        self.assertEqual(result['last_tick']['outcome'], 'completed')
        self.assertEqual(result['last_tick']['exit_code'], 0)
        self.assertEqual(self.git(root, 'show', 'HEAD:out.txt'), 'hi')
        self.assertIn('aos-tick group', self.git(root, 'log', '-1', '--format=%s'))
        grant = self.path / 'grant.json'
        write_json(grant, [os.getuid()])
        self.cli('register', child, '--parent', root, '--identity-grant', grant, '--yes', '--socket', self.socket_path)
        self.assertIsNone(self.show(child)['last_tick'])
        self.cli('wake', child, '--daemon-config', self.config)
        result = self.completed(child)
        self.assertEqual(result['last_tick']['exit_code'], 0)
        self.assertEqual(self.git(child, 'show', 'HEAD:result.txt'), 'child')
        self.assertTrue(Path(result['cgroup']['path']).is_relative_to(Path(self.show(root)['cgroup']['path'])))
        first = self.cli('daemon', 'info', '--socket', self.socket_path).stdout
        self.assertEqual(first, self.cli('daemon', 'info', '--socket', self.socket_path).stdout)
        listing = json.loads(self.cli('ls', '--socket', self.socket_path, '--json').stdout)['result']
        self.assertEqual({n['node_id'] for n in listing['nodes']}, {str(root), str(child)})
        os.kill(self.daemon_pid, signal.SIGTERM)
        self.assertEqual(self.daemon.wait(timeout=5), 0, self.daemon.stderr.read().decode())
        self.assertFalse(Path(self.socket_path).exists())
        self.assertFalse((self.state / 'daemon.pid').exists())
        self.assertFalse((self.state / 'helper.pid').exists())
        self.assertFalse((self.state / 'state.json').exists())

    def test_once_missing_user_error_and_retention(self):
        root = self.new_node()
        self.start_daemon(root)
        self.completed(root)
        missing = self.path / 'missing.json'
        write_json(missing, {'argv': ['true'], 'user': 'aos-no-such-user'})
        # P-104（第十六批 G-11）：登記時帳號就要存在，once 也不放寬。
        response = self.rpc('node.register', dict(node_id=str(missing), parent_id=str(root),
                                                  identity_grant=[os.getuid()], once=True))
        self.assertEqual(response['error']['data']['code'], 'user_invalid')
        self.assertEqual(self.rpc('node.show', {'node_id': str(missing)})['error']['data']['code'], 'not_registered')
        # wake 時仍重新解析：登記後帳號才消失（這裡改寫 inst 模擬），照舊產 .err 並解除。
        inst = self.path / 'once.json'
        write_json(inst, {'argv': ['true']})
        self.register(inst, root, once=True)
        self.assertIsNone(self.show(inst)['last_tick'])
        write_json(inst, {'argv': ['true'], 'user': 'aos-no-such-user'})
        self.rpc('node.wake', {'node_id': str(inst)})
        result = self.completed(inst)
        self.assertFalse(result['registered'])
        self.assertEqual(result['last_tick']['outcome'], 'launch_failed')
        self.assertEqual(result['last_tick']['exit_code'], 125)
        error = json.loads(Path(str(inst) + '.err').read_text())
        self.assertEqual(error['version'], 1)
        self.assertEqual(error['error']['data']['code'], 'user_invalid')
        self.assertIsNone(result['cgroup'])
        self.assertEqual(self.rpc('node.wake', {'node_id': str(inst)})['error']['data']['code'], 'not_registered')
        self.assertIn('已解除 once', self.cli('show', inst, '--socket', self.socket_path).stdout)

    def test_once_success_and_no_second_tick(self):
        root = self.new_node()
        self.start_daemon(root)
        inst = self.path / 'once.json'
        write_json(inst, {'argv': ['sh', '-c', 'echo ran >> result']})
        self.register(inst, root, once=True)
        self.rpc('node.pause', {'node_id': str(inst)})
        for _ in range(3):
            self.rpc('node.wake', {'node_id': str(inst)})
        self.rpc('node.resume', {'node_id': str(inst)})
        result = self.completed(inst)
        self.assertFalse(result['registered'])
        self.assertEqual((self.path / 'result').read_text(), 'ran\n')
        self.assertFalse(Path(str(inst) + '.err').exists())

    def test_blocked_tick_pauses_and_attention(self):
        root = self.new_node()
        (root / '.git/aos').mkdir()
        (root / '.git/aos/tick-blocked').write_text('test')
        self.start_daemon(root)
        result = self.completed(root)
        self.assertTrue(result['paused'])
        self.assertEqual(result['last_tick']['outcome'], 'completed')
        self.assertEqual(result['last_tick']['exit_code'], 125)
        issues = list((root / '.aos/attention').glob('*.json'))
        self.assertEqual(len(issues), 1)
        self.assertEqual(json.loads(issues[0].read_text())['last_tick']['exit_code'], 125)

    def test_pause_pending_resume_idempotence_pagination(self):
        root = self.new_node()
        child = self.new_node('C', [task(command='echo done > result')])
        self.start_daemon(root)
        self.register(child, root)
        self.rpc('node.pause', {'node_id': str(child)})
        self.rpc('node.wake', {'node_id': str(child)})
        self.register(child, root)
        state = self.show(child)
        self.assertTrue(state['paused'])
        self.assertTrue(state['pending'])
        self.assertFalse(state['running'])
        self.assertIsNone(state['last_tick'])
        first = self.rpc('node.ls', {'limit': 1})['result']
        second = self.rpc('node.ls', {'limit': 1, 'after_node_id': first['next_after_node_id']})['result']
        self.assertEqual(len(first['nodes']), 1)
        self.assertEqual(len(second['nodes']), 1)
        self.assertIsNone(second['next_after_node_id'])
        self.cli('resume', child, '--yes', '--socket', self.socket_path)
        self.assertEqual(self.completed(child)['last_tick']['exit_code'], 0)
        self.cli('unregister', child, '--socket', self.socket_path, code=125, input='')
        self.cli('unregister', child, '--yes', '--socket', self.socket_path)
        self.assertEqual(self.rpc('node.show', {'node_id': str(child)})['error']['data']['code'], 'not_registered')

    def test_startup_cleans_old_term_before_first_tick(self):
        root = self.new_node(tasks=[task(command='echo hi > out')])
        cg = self.path / 'cg'
        backend = FakeCgroup(cg)
        backend.create(cg)
        old = cg / 'n-old/tick'
        backend.create(old)
        sleeper = subprocess.Popen(['sleep', '60'])
        self.addCleanup(lambda: sleeper.poll() is None and (sleeper.kill(), sleeper.wait()))
        backend.move(old, sleeper.pid)
        self.start_daemon(root, fake=cg)
        self.assertEqual(sleeper.wait(timeout=3), -signal.SIGTERM)
        self.assertEqual(self.completed(root)['last_tick']['exit_code'], 0)
        self.assertEqual((old / 'cgroup.kill').read_text(), '')

    def test_socket_lock_preserves_live_socket(self):
        root = self.new_node()
        self.start_daemon(root)
        self.cli('daemon', 'start', '--config', self.config, '--x-fake-cgroup', self.path / 'cgroup', code=125)
        self.assertIn('result', self.rpc('daemon.info'))

    def test_protocol_errors_and_multiple_requests(self):
        root = self.new_node()
        self.start_daemon(root)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as stream:
            stream.settimeout(3)
            stream.connect(self.socket_path)
            with stream.makefile('rb') as reader:
                cases = [(b'{\n', -32700, None), (b'{"id":"valid","jsonrpc":"2.0"}\n', -32600, 'valid'),
                         (b'{"jsonrpc":"2.0","id":"abc","method":"node.provision","params":{}}\n', -32601, 'abc'),
                         (b'{"jsonrpc":"2.0","id":"abc","method":"node.ls","params":{"limit":0}}\n', -32602, 'abc')]
                for raw, number, request_id in cases:
                    stream.sendall(raw)
                    response = json.loads(reader.readline())
                    self.assertEqual(response['id'], request_id)
                    self.assertEqual(response['error']['code'], number)
                    self.assertFalse(response['error']['data']['retryable'])
                stream.sendall(b'x' * MAX_LINE)
                self.assertEqual(json.loads(reader.readline())['error']['code'], -32600)
                self.assertEqual(reader.readline(), b'')

    def test_periodic_and_running_wake_coalescing(self):
        root = self.new_node()
        child = self.new_node('C', [task(command='echo run >> count; while test ! -e work/release; do sleep .01; done')])
        (child / 'work').mkdir()
        self.start_daemon(root)
        self.register(child, root)
        self.rpc('node.wake', {'node_id': str(child)})
        poll(lambda: (child / 'count').exists(), description='first task reached')
        for _ in range(5):
            self.rpc('node.wake', {'node_id': str(child)})
        self.assertTrue(self.show(child)['pending'])
        (child / 'work/release').touch()
        poll(lambda: self.git(child, 'rev-list', '--count', 'HEAD') == '3', description='two ticks committed')
        self.cli('pause', child, '--socket', self.socket_path)
        self.assertEqual((child / 'count').read_text(), 'run\nrun\n')

    def test_unregister_running_subtree(self):
        root = self.new_node()
        child = self.new_node('C', [task(command='echo ready > work/ready; exec sleep 60')])
        (child / 'work').mkdir()
        self.start_daemon(root)
        self.register(child, root)
        self.rpc('node.wake', {'node_id': str(child)})
        poll(lambda: (child / 'work/ready').exists())
        result = self.rpc('node.unregister', {'node_id': str(root)})
        self.assertNotIn('error', result)
        self.assertEqual(self.rpc('node.ls')['result']['nodes'], [])

    def test_interval_schedules_from_registration_and_finish(self):
        root = self.new_node()
        child = self.new_node('C', [task(command='echo run >> count')])
        self.start_daemon(root)
        self.register(child, root, interval_ms=50)
        poll(lambda: int(self.git(child, 'rev-list', '--count', 'HEAD')) >= 3, description='periodic ticks')
        self.cli('pause', child, '--socket', self.socket_path)
        self.assertGreaterEqual(len((child / 'count').read_text().splitlines()), 2)

    def test_once_error_does_not_overwrite(self):
        root = self.new_node()
        self.start_daemon(root)
        inst = self.path / 'once.json'
        write_json(inst, {'argv': ['true']})
        error = Path(str(inst) + '.err')
        error.write_text('existing evidence')
        self.register(inst, root, once=True)
        write_json(inst, {'argv': ['true'], 'user': 'aos-no-such-user'})
        self.rpc('node.wake', {'node_id': str(inst)})
        self.assertFalse(self.completed(inst)['registered'])
        self.assertEqual(error.read_text(), 'existing evidence')

    def test_startup_kills_term_ignoring_process(self):
        root = self.new_node()
        cg = self.path / 'cg'
        backend = FakeCgroup(cg)
        backend.create(cg)
        old = cg / 'n-old/tick'
        backend.create(old)
        ready = self.path / 'ready'
        child = subprocess.Popen(['python3', '-c',
            'import signal,time,pathlib,sys; signal.signal(signal.SIGTERM, signal.SIG_IGN); '
            'pathlib.Path(sys.argv[1]).touch(); time.sleep(60)', str(ready)])
        self.addCleanup(lambda: child.poll() is None and (child.kill(), child.wait()))
        poll(ready.exists)
        backend.move(old, child.pid)
        self.start_daemon(root, fake=cg, grace=20)
        self.assertEqual(child.wait(timeout=3), -signal.SIGKILL)
        self.assertEqual((cg / 'n-old/cgroup.kill').read_text(), '1\n')

    def test_omitted_root_leaves_only_branch(self):
        # G-3（第十六批）：省略 cgroup_root 時，原層的其他程序也搬進 daemon 葉框。
        root = self.new_node()
        cg = self.path / 'cg'
        FakeCgroup(cg).create(cg)
        other = subprocess.Popen(['sleep', '60'])
        self.addCleanup(lambda: other.poll() is None and (other.kill(), other.wait()))
        (cg / 'cgroup.procs').write_text('%d\n' % other.pid)
        self.start_daemon(root, fake=cg)
        self.assertEqual((cg / 'cgroup.procs').read_text(), '')
        leaf = {int(p) for p in (cg / 'daemon/cgroup.procs').read_text().split()}
        self.assertLessEqual({other.pid, self.daemon_pid}, leaf)

    def test_registration_constraints(self):
        root = self.new_node()
        child = self.new_node('C')
        self.start_daemon(root)
        base = dict(node_id=str(child), parent_id=str(root), identity_grant=[os.getuid()])
        cases = [(dict(base, once=True, interval_ms=1), 'invalid_params'),
                 (dict(base, identity_grant=[os.getuid() + 1]), 'user_not_granted'),
                 (dict(base, parent_id=str(self.path / 'absent')), 'not_registered'),
                 (dict(base, extra=True), 'invalid_params')]
        for params, code in cases:
            with self.subTest(code=code):
                self.assertEqual(self.rpc('node.register', params)['error']['data']['code'], code)
        self.register(child, root)
        self.assertEqual(self.rpc('node.register', dict(base, interval_ms=1))['error']['data']['code'],
                         'registration_conflict')

    def test_pipelined_requests(self):
        root = self.new_node()
        self.start_daemon(root)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as stream:
            stream.settimeout(3)
            stream.connect(self.socket_path)
            requests = [dict(jsonrpc='2.0', id='request%d' % i, method='daemon.info', params={}) for i in range(200)]
            stream.sendall(b''.join((json.dumps(r) + '\n').encode() for r in requests))
            with stream.makefile('rb') as reader:
                for request in requests:
                    self.assertEqual(json.loads(reader.readline())['id'], request['id'])


class RealCgroupTest(Case):
    def test_real_cgroup_root_tick(self):
        if not shutil.which('systemd-run'):
            self.skipTest('找不到 systemd-run，無法取得真 cgroup 委派')
        try:
            probe = subprocess.run(['systemd-run', '--user', '--scope', '-p', 'Delegate=yes', '--quiet', 'true'],
                                   capture_output=True, text=True, timeout=4)
        except (OSError, subprocess.TimeoutExpired) as exc:
            self.skipTest('systemd user scope 委派探測失敗: ' + str(exc))
        if probe.returncode:
            self.skipTest('systemd user scope 不可用: ' + probe.stderr.strip())
        root = self.new_node(tasks=[task(command='echo real > out.txt')])
        self.start_daemon(root, real=True)
        result = self.completed(root)
        self.assertEqual(result['last_tick']['outcome'], 'completed')
        self.assertEqual(result['last_tick']['exit_code'], 0)
        frame = Path(result['cgroup']['path'])
        self.assertTrue((frame / 'tick/cgroup.procs').exists())
        self.assertEqual(self.git(root, 'show', 'HEAD:out.txt'), 'real')
        os.kill(self.daemon_pid, signal.SIGTERM)
        self.assertEqual(self.daemon.wait(timeout=5), 0)

    def test_real_killed_runner_is_unknown_and_descendants_drained(self):
        if not shutil.which('systemd-run'):
            self.skipTest('找不到 systemd-run，無法取得真 cgroup 委派')
        try:
            probe = subprocess.run(['systemd-run', '--user', '--scope', '-p', 'Delegate=yes', '--quiet', 'true'],
                                   capture_output=True, text=True, timeout=4)
        except (OSError, subprocess.TimeoutExpired) as exc:
            self.skipTest('systemd user scope 委派探測失敗: ' + str(exc))
        if probe.returncode:
            self.skipTest('systemd user scope 不可用: ' + probe.stderr.strip())
        root = self.new_node()
        (root / 'work').mkdir()
        write_json(root / '.aos/inst.json', {'argv': ['sh', '-c', 'echo $$ > work/task.pid; exec sleep 60']})
        self.start_daemon(root, real=True)
        task_file = root / 'work/task.pid'
        poll(lambda: task_file.exists() and task_file.read_text().strip())
        task_pid = int(task_file.read_text())
        runner_pid = int(Path('/proc/%d/stat' % task_pid).read_text().rsplit(')', 1)[1].split()[1])
        os.kill(runner_pid, signal.SIGKILL)
        result = self.completed(root)
        self.assertEqual(result['last_tick']['outcome'], 'unknown')
        self.assertIsNone(result['last_tick']['exit_code'])
        self.assertIsNone(result['last_tick']['started'])
        self.assertTrue(result['paused'])
        self.assertFalse(live(task_pid))
        leaf = Path(result['cgroup']['path']) / 'tick'
        self.assertIn('populated 0', (leaf / 'cgroup.events').read_text())
