"""aos-jail（spec/aos-exec/aos-jail.md）：build_argv 單元＋真的跑 bwrap（這台沒 bwrap 就 skip）。

真跑只連自己在測試裡開的 TCP port，不碰任何別人的服務。
"""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

import aos_jail

CLI = Path(__file__).resolve().parents[2] / 'cli' / 'aos-jail'
BASE_TOOLS = Path(__file__).resolve().parents[2] / 'tools' / 'base'


def opts(*argv):
    return aos_jail.parse_args(list(argv))


def pairs(argv, flag):
    """argv 裡 flag 後面跟的兩個值（--setenv K V、--bind SRC DST…）。"""
    return [(argv[i + 1], argv[i + 2]) for i, a in enumerate(argv) if a == flag]


class BuildArgvTests(unittest.TestCase):
    def test_parse_errors(self):
        for argv in ([], ['--', ''], ['--mount', 'ws=rel', '--', 'true'], ['--mount', 'WS=/tmp', '--', 'true'],
                     ['--mount', 'ws=/a', '--mount-ro', 'ws=/b', '--', 'true'], ['--chdir', 'ws', '--', 'true'],
                     ['--net', 'maybe', '--', 'true'], ['--mount', 'ws', '--', 'true'], ['--bogus', '--', 'true'],
                     ['--setenv', '=x', '--', 'true'], ['--', 'rel/prog'], ['--mount']):
            with self.subTest(argv=argv), self.assertRaises(aos_jail.UsageError):
                aos_jail.parse_args(argv)

    def test_net_off_basic_shape(self):
        argv, dropped = aos_jail.build_argv(opts('--mount', 'ws=/w', '--mount-ro', 'ref=/r', '--chdir', 'ws',
                                                 '--', 'sh', '-c', 'x'), environ={'LANG': 'C.UTF-8', 'X': '1'})
        self.assertEqual(argv[:2], ['bwrap', '--unshare-all'])
        self.assertNotIn('--share-net', argv)
        self.assertIn('--die-with-parent', argv)
        self.assertIn('--new-session', argv)
        self.assertIn('--clearenv', argv)
        self.assertIn(('/usr', '/usr'), pairs(argv, '--ro-bind'))
        self.assertIn(('/w', '/work/ws'), pairs(argv, '--bind'))
        self.assertIn(('/r', '/work/ref'), pairs(argv, '--ro-bind'))
        self.assertEqual(argv[argv.index('--chdir') + 1], '/work/ws')
        env = dict(pairs(argv, '--setenv'))
        self.assertEqual(env, {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': '/tmp', 'LANG': 'C.UTF-8',
                               'AOS_TOOL_ROOT': '/work/ws'})
        self.assertNotIn(('/etc/resolv.conf', '/etc/resolv.conf'), pairs(argv, '--ro-bind-try'))
        self.assertNotIn(('/etc', '/etc'), pairs(argv, '--ro-bind'))
        self.assertEqual(argv[-4:], ['--', 'sh', '-c', 'x'])
        self.assertEqual(dropped, [])

    def test_net_on_and_no_cwd(self):
        argv, _ = aos_jail.build_argv(opts('--net', 'on', '--', 'true'), environ={})
        self.assertIn('--share-net', argv)
        self.assertIn(('/etc/resolv.conf', '/etc/resolv.conf'), pairs(argv, '--ro-bind-try'))
        self.assertEqual(argv[argv.index('--chdir') + 1], '/work')
        self.assertEqual(dict(pairs(argv, '--setenv'))['AOS_TOOL_ROOT'], '/work')

    def test_setenv_filters_secrets(self):
        argv, dropped = aos_jail.build_argv(opts(
            '--setenv', 'FOO=a=b', '--setenv', 'AOS_KERNEL_HOME=/K', '--setenv', 'openai_api_key=sk',
            '--setenv', 'GITHUB_TOKEN=t', '--setenv', 'SSH_AUTH_SOCK=/s', '--setenv', 'DB_PASSWORD=p',
            '--setenv', 'AOS_TOOL_ROOT=/host', '--setenv', 'PATH=/usr/bin', '--', 'true'), environ={})
        env = dict(pairs(argv, '--setenv'))
        self.assertEqual(env['FOO'], 'a=b')
        self.assertEqual(env['PATH'], '/usr/bin')
        self.assertEqual(env['AOS_TOOL_ROOT'], '/work')
        self.assertEqual(sorted(dropped), sorted(['AOS_KERNEL_HOME', 'openai_api_key', 'GITHUB_TOKEN',
                                                  'SSH_AUTH_SOCK', 'DB_PASSWORD', 'AOS_TOOL_ROOT']))

    def test_program_with_slash_goes_to_opt_tool(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d)
        (d / 'real').mkdir()
        (d / 'real' / 'prog').write_text('#!/bin/sh\n')
        (d / 'link').symlink_to(d / 'real')
        argv, _ = aos_jail.build_argv(opts('--', str(d / 'link' / 'prog'), 'a'), environ={})
        self.assertIn((str(d / 'real'), '/opt/tool'), pairs(argv, '--ro-bind'))
        self.assertEqual(argv[-3:], ['--', '/opt/tool/prog', 'a'])

    def test_main_usage_and_missing_bwrap(self):
        with patch('sys.stderr') as err:
            self.assertEqual(aos_jail.main(['--net', 'x', '--', 'true']), 2)
        with patch.object(aos_jail.shutil, 'which', return_value=None), patch('sys.stderr') as err:
            self.assertEqual(aos_jail.main(['--', 'true']), 126)
        self.assertIn('pacman -S bubblewrap', ''.join(c.args[0] for c in err.write.call_args_list))


def bwrap_works():
    if shutil.which('bwrap') is None:
        return False
    argv, _ = aos_jail.build_argv(opts('--', 'true'), environ={}, bwrap=shutil.which('bwrap'))
    return subprocess.run(argv, capture_output=True).returncode == 0


@unittest.skipUnless(bwrap_works(), '這台沒有可用的 bwrap')
class RealJailTests(unittest.TestCase):
    """擺設：amy/（info.json 有祕密）、ws/（a.txt、sneaky -> ../amy）、tool/（一支程式）。"""

    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix='aos-jail-')))
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        (self.d / 'amy').mkdir()
        (self.d / 'amy' / 'info.json').write_text('{"secret": "amy-secret"}')
        (self.d / 'ws').mkdir()
        (self.d / 'ws' / 'a.txt').write_text('hello')
        (self.d / 'ws' / 'sneaky').symlink_to('../amy')
        (self.d / 'ro').mkdir()
        self.env = dict(os.environ, AOS_KERNEL_HOME='/x/K', OPENAI_API_KEY='sk-demo')

    def jail(self, *flags, cmd, prog=('sh', '-c')):
        argv = [sys.executable, str(CLI), '--mount', 'ws=%s' % (self.d / 'ws'), '--mount-ro', 'ro=%s' % (self.d / 'ro'),
                '--chdir', 'ws', *flags, '--', *prog, cmd]
        return subprocess.run(argv, env=self.env, cwd=self.d / 'amy', capture_output=True, text=True, timeout=30)

    def test_escapes_fail(self):
        for cmd in ('cat ../amy/info.json', 'cat %s/amy/info.json' % self.d, 'cat sneaky/info.json',
                    'ls /home', 'cat /etc/shadow'):
            with self.subTest(cmd=cmd):
                r = self.jail(cmd=cmd)
                self.assertNotEqual(r.returncode, 0, r.stdout)
                self.assertNotIn('amy-secret', r.stdout)

    def test_inside_works(self):
        r = self.jail(cmd='pwd; cat a.txt; echo; echo new > b.txt; echo $AOS_TOOL_ROOT $HOME')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.split(), ['/work/ws', 'hello', '/work/ws', '/tmp'])
        self.assertEqual((self.d / 'ws' / 'b.txt').read_text(), 'new\n')
        r = self.jail(cmd='echo x > /work/ro/c.txt')
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((self.d / 'ro' / 'c.txt').exists())

    def test_env_is_clean(self):
        r = self.jail('--setenv', 'OPENAI_API_KEY=sk-demo', '--setenv', 'FOO=bar', cmd='env')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn('AOS_KERNEL_HOME', r.stdout)
        self.assertNotIn('OPENAI_API_KEY', r.stdout)
        self.assertNotIn('sk-demo', r.stdout)
        self.assertIn('FOO=bar', r.stdout)
        self.assertIn('丟掉環境變數 OPENAI_API_KEY', r.stderr)

    def _server(self):
        srv = socket.socket()
        srv.bind(('127.0.0.1', 0))
        srv.listen(4)
        srv.settimeout(10)
        self.addCleanup(srv.close)

        def serve():
            try:
                while True:
                    conn, _ = srv.accept()
                    conn.sendall(b'pong')
                    conn.close()
            except OSError:
                pass
        threading.Thread(target=serve, daemon=True).start()
        return srv.getsockname()[1]

    def test_net_off_and_on(self):
        port = self._server()
        code = ('import socket,sys\ns=socket.create_connection(("127.0.0.1",%d),timeout=3)\n'
                'sys.stdout.write(s.recv(4).decode())' % port)
        off = self.jail('--net', 'off', cmd=code, prog=('python3', '-c'))
        self.assertNotEqual(off.returncode, 0)
        self.assertNotIn('pong', off.stdout)
        on = self.jail('--net', 'on', cmd=code, prog=('python3', '-c'))
        self.assertEqual(on.returncode, 0, on.stderr)
        self.assertEqual(on.stdout, 'pong')

    def test_program_path_and_base_read_tool(self):
        tool = self.d / 'tool'
        tool.mkdir()
        (tool / 'where').write_text('#!/bin/sh\necho "$0 $AOS_TOOL_ROOT $(pwd)"\n')
        os.chmod(tool / 'where', 0o755)
        r = subprocess.run([sys.executable, str(CLI), '--mount', 'ws=%s' % (self.d / 'ws'), '--chdir', 'ws',
                            '--', str(tool / 'where')], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.stdout.split(), ['/opt/tool/where', '/work/ws', '/work/ws'], r.stderr)
        read = [sys.executable, str(CLI), '--mount', 'ws=%s' % (self.d / 'ws'), '--chdir', 'ws',
                '--', str(BASE_TOOLS / 'read')]
        ok = subprocess.run(read, input='{"path": "a.txt"}', capture_output=True, text=True, timeout=30)
        self.assertIn('hello', ok.stdout, ok.stderr)
        bad = subprocess.run(read, input='{"path": "../amy/info.json"}', capture_output=True, text=True, timeout=30)
        last = json.loads(bad.stdout.strip().splitlines()[-1])
        self.assertIn(last['error'], ('OutsideRoot', 'NotFound'))
        self.assertNotIn(str(self.d), bad.stdout)                 # 錯誤訊息只帶牢裡路徑

    def test_agent_inst_through_aos_exec(self):
        """aos-agent 包出來的 inst 交給真的 aos-exec：base 的 bash 在牢裡、看不到 amy。"""
        import aos_agent_batch
        home = self.d / 'amy'
        shutil.copytree(BASE_TOOLS, home / 'tools' / 'base')
        (home / 'work').mkdir()
        name = 'aw-amy-1-0'
        (home / 'work' / (name + '.in')).write_text(json.dumps(
            {'command': 'pwd; cat a.txt; echo; cat ../amy/info.json; echo K=$AOS_KERNEL_HOME'}))
        access = {'mounts': {'ws': {'path': str(self.d / 'ws'), 'ro': False}}, 'cwd': 'ws', 'net': False}
        inst = aos_agent_batch.tool_inst({'argv': ['tools/base/bash']}, home, name, self.env, access=access)
        path = home / 'work' / (name + '.inst.json')
        path.write_text(json.dumps(inst))
        env = dict(self.env, PATH='%s:%s' % (CLI.parent, os.environ['PATH']))
        r = subprocess.run([sys.executable, str(CLI.parent / 'aos-exec'), str(path)], env=env,
                           capture_output=True, text=True, timeout=60)
        out = (home / 'work' / (name + '.out')).read_text()
        self.assertEqual(r.returncode, 0, r.stderr + out)
        self.assertIn('No such file', out)
        self.assertIn('/work/ws', out)
        self.assertIn('hello', out)
        self.assertNotIn('amy-secret', out)
        self.assertIn('K=\n', out)


class WorkRootEnvTests(unittest.TestCase):
    """base 工具：AOS_TOOL_ROOT 有值就用它，不看 config.json（不用 bwrap）。"""

    def test_env_root_wins(self):
        d = Path(os.path.realpath(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, d)
        (d / 'ws').mkdir()
        (d / 'ws' / 'a.txt').write_text('from-env-root')
        env = dict(os.environ, AOS_TOOL_ROOT=str(d / 'ws'))
        r = subprocess.run([sys.executable, str(BASE_TOOLS / 'read')], input='{"path": "a.txt"}', cwd=d, env=env,
                           capture_output=True, text=True, timeout=30)
        self.assertIn('from-env-root', r.stdout)
        env['AOS_TOOL_ROOT'] = str(d / 'nope')
        r = subprocess.run([sys.executable, str(BASE_TOOLS / 'read')], input='{"path": "a.txt"}', cwd=d, env=env,
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(json.loads(r.stdout.strip().splitlines()[-1])['error'], 'RootMissing')


if __name__ == '__main__':
    unittest.main()
