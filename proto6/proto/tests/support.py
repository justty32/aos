import json
import os
import selectors
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

PROTO = Path(__file__).resolve().parents[1]
BIN = PROTO / 'bin'
ENV = dict(os.environ, PATH=str(BIN) + os.pathsep + os.environ.get('PATH', os.defpath),
           GIT_AUTHOR_NAME='Prototype Test', GIT_AUTHOR_EMAIL='proto@example.invalid',
           GIT_COMMITTER_NAME='Prototype Test', GIT_COMMITTER_EMAIL='proto@example.invalid')


def poll(predicate, timeout=5, description='condition'):
    deadline = time.monotonic() + timeout
    while True:
        value = predicate()
        if value:
            return value
        if time.monotonic() >= deadline:
            raise AssertionError('timeout: ' + description)
        time.sleep(0.01)


def write_json(path, value):
    Path(path).write_text(json.dumps(value))


def task(name='test', command='true', **extra):
    return dict(id=name, kind='custom', argv=['sh', '-c', command], **extra)


def table(tasks):
    return {'_metainfo': {'_type': 'aos-tasks', '_version': 1}, 'tasks': tasks}


class Case(unittest.TestCase):
    def setUp(self):
        (PROTO / '.test-tmp').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=PROTO / '.test-tmp')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)

    def cli(self, *args, code=0, **kwargs):
        result = subprocess.run([str(BIN / 'aos'), *map(str, args)], env=ENV,
                                capture_output=True, text=True, timeout=8, **kwargs)
        self.assertEqual(result.returncode, code, result.stdout + '\n' + result.stderr)
        return result

    def new_node(self, name='R', tasks=None):
        node = self.path / name
        file = self.path / (name + '-tasks.json')
        write_json(file, table([] if tasks is None else tasks))
        self.cli('new', node, '--tasks', file)
        return node

    def git(self, node, *args):
        return subprocess.check_output(['git', '-C', str(node), *args], env=ENV, text=True).strip()

    def inst(self, obj, code=0, **options):
        target = self.path / 'job.json'
        write_json(target, obj)
        argv = ['run', target, '--json']
        for key, value in options.items():
            argv += ['--' + key.replace('_', '-'), str(value)]
        result = self.cli(*argv, code=code)
        return json.loads(result.stdout)

    def start_daemon(self, root, real=False, fake=None, grace=100, extra=None):
        from aosproto.cgroup import FakeCgroup
        # Unix sockaddr_un is only 108 bytes; fixture prefix here is intentionally long.
        # Use Linux /proc/self/fd path through inherited directory fd to shorten bind/connect.
        # Instead test socket under an already-open fixture directory via /proc/<pid>/fd/N.
        self.dirfd = os.open(self.path, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, self.dirfd)
        self.socket_path = '/proc/%d/fd/%d/d.sock' % (os.getpid(), self.dirfd)
        self.state = self.path / 'state'
        self.config = self.path / 'daemon.json'
        write_json(self.config, {'version': 1, 'socket_path': self.socket_path, 'state_dir': str(self.state),
                                'shutdown_grace_ms': grace,
                                'roots': [{'node_id': str(root), 'identity_grant': [os.getuid()]}], **(extra or {})})
        argv = [str(BIN / 'aos'), 'daemon', 'start', '--config', str(self.config)]
        if real:
            argv = ['systemd-run', '--user', '--scope', '-p', 'Delegate=yes', '--quiet', '--'] + argv
        else:
            fake = fake or self.path / 'cgroup'
            FakeCgroup(fake).create(fake)
            argv += ['--x-fake-cgroup', str(fake)]
        self.daemon = subprocess.Popen(argv, env=ENV, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(self.cleanup_daemon)
        selector = selectors.DefaultSelector()
        selector.register(self.daemon.stdout, selectors.EVENT_READ)
        try:
            self.assertTrue(selector.select(5), 'daemon readiness timeout')
            ready = self.daemon.stdout.readline()
            if ready != b'helper_pid=none\n':
                self.daemon.wait(timeout=5)
                diagnostic = self.daemon.stderr.read().decode()
                if real and ('cgroup_unavailable:' in diagnostic or 'dependency_failed:' in diagnostic):
                    self.skipTest('真 cgroup 委派／版本條件不成立: ' + diagnostic.strip())
                self.fail('daemon start: ' + diagnostic)
        finally:
            selector.close()
        self.daemon_pid = int((self.state / 'daemon.pid').read_text())
        return self.daemon

    def cleanup_daemon(self):
        if self.daemon.poll() is None:
            try:
                os.kill(getattr(self, 'daemon_pid', self.daemon.pid), signal.SIGTERM)
                self.daemon.wait(timeout=6)
            except (OSError, subprocess.TimeoutExpired):
                self.daemon.kill()
                self.daemon.wait()
        self.daemon.stdout.close()
        self.daemon.stderr.close()

    def rpc(self, method, params=None):
        from aosproto.cli import rpc
        return rpc(self.socket_path, method, params or {})

    def show(self, target):
        result = self.rpc('node.show', {'node_id': str(target)})
        self.assertNotIn('error', result, result)
        return result['result']

    def completed(self, target):
        return poll(lambda: (lambda v: v if v['last_tick'] and not v['running'] else None)(self.show(target)),
                    description='tick completed')
