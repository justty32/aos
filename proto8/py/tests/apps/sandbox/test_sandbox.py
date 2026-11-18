# Verify aos-sandbox: a broken config runs prog unsandboxed with a warning, real errors stay errors, the deeper of ro/rw wins (T32), writes outside rw fail (T36), the config's folder is visible (T34) and aos commands bring the whole home read-only (path rule 7; the home is AOS_HOME when set, a non-home there is EnvBad).
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace
import subprocess
import tempfile
import unittest
from unittest import mock

PROTO = Path(__file__).resolve().parents[4]
SANDBOX = PROTO / 'bin/aos-sandbox'                      # the entry install.py writes
SOURCE = PROTO / 'py/aos/apps/sandbox/main.py'
WARNING = 'aos-sandbox: warning: sandbox config ignored, running unsandboxed: '
SUDO_SETUIDGID = '/usr/local/bin/s6-setuidgid'


def sandbox_module():
    if str(PROTO / 'py') not in sys.path:
        sys.path.insert(0, str(PROTO / 'py'))
    loader = importlib.machinery.SourceFileLoader('sandbox_under_test', str(SOURCE))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def bwrap_works():
    found = shutil.which('bwrap')
    if not found:
        return False
    try:
        return subprocess.run([found, '--ro-bind', '/', '/', 'true'], capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


class SandboxTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(dir=os.environ.get('KERNEL_TEST_TMP')))
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}

    def cfg(self, text, name='sandbox.json'):
        path = self.dir / name
        path.write_text(text if isinstance(text, str) else json.dumps(text), encoding='utf-8')
        return str(path)

    def run_box(self, *args):
        return subprocess.run([str(SANDBOX), *args], capture_output=True, text=True, env=self.env,
                              cwd=self.dir, timeout=60)

    def assert_unsandboxed(self, spec, reason):
        result = self.run_box(spec, 'echo', 'ran')
        self.assertEqual((result.returncode, result.stdout), (0, 'ran\n'), result.stderr)
        lines = result.stderr.splitlines()
        self.assertEqual(len(lines), 1, result.stderr)
        self.assertTrue(lines[0].startswith(WARNING), lines[0])
        self.assertIn(reason, lines[0])
        self.assertNotIn('error:', result.stderr)

    def test_broken_config_runs_unsandboxed_with_one_warning(self):
        meta = self.cfg({'sandbox': 'strict', 'box': {'net': 'no'}, 'ref': {'ro': [{'$ref': 'x.json'}]},
                         'env': {'rw': [{'$env': 'AOS_SANDBOX_TEST_UNSET'}]}}, '_metainfo.json')
        cases = [
            (self.cfg('{not json', 'broken.json'), 'is not JSON'),
            (self.cfg([1, 2], 'list.json'), 'must be a JSON object'),
            (meta + '#/sandbox', 'must be a JSON object'),
            (meta + '#/box', 'net must be true or false'),
            (meta + '#/ref', 'not $ref'),
            (meta + '#/env', 'is not set'),
            (meta + '#box', 'must start with /'),
            (self.cfg({'mem_mb': '64'}, 'mem.json'), 'mem_mb must be a positive integer'),
            (self.cfg({'ro': '/usr'}, 'ro.json'), 'ro must be an array'),
            (self.cfg({'env': ['A=B']}, 'envs.json'), 'env must be an array'),
            (self.cfg({'commands': [1]}, 'cmds.json'), 'commands must be an array'),
            (self.cfg({'user': 7}, 'user.json'), 'user must be a non-empty string'),
        ]
        for spec, reason in cases:
            with self.subTest(spec=spec):
                self.assert_unsandboxed(spec, reason)

    def test_broken_config_keeps_prog_exit_code_and_stdin(self):
        result = subprocess.run([str(SANDBOX), self.cfg('nope'), 'sh', '-c', 'cat; exit 7'], input='in\n',
                                capture_output=True, text=True, env=self.env, cwd=self.dir, timeout=60)
        self.assertEqual((result.returncode, result.stdout), (7, 'in\n'), result.stderr)
        self.assertIn(WARNING, result.stderr)

    def test_broken_config_dry_run_prints_only_prog(self):
        result = self.run_box('--dry-run', self.cfg('[]'), 'echo', 'ran')
        self.assertEqual(result.returncode, 0, result.stderr)
        argv = json.loads(result.stdout)
        self.assertEqual(argv[1:], ['ran'])
        self.assertEqual(os.path.basename(argv[0]), 'echo')
        self.assertNotIn('bwrap', ' '.join(argv))
        self.assertIn(WARNING, result.stderr)

    def test_broken_config_with_missing_prog_is_an_error(self):
        result = self.run_box(self.cfg('[]'), 'aos-sandbox-test-no-such-prog')
        self.assertEqual(result.returncode, 1)
        self.assertIn('aos-sandbox: error: CommandMissing', result.stderr)

    def test_absent_config_is_still_an_error(self):
        meta = self.cfg({'summary': 'no sandbox key'}, '_metainfo.json')
        for spec in (str(self.dir / 'none.json'), meta + '#/sandbox'):
            with self.subTest(spec=spec):
                result = self.run_box(spec, 'echo', 'ran')
                self.assertEqual((result.returncode, result.stdout), (1, ''))
                self.assertIn('aos-sandbox: error: CfgMissing', result.stderr)
                self.assertNotIn('warning', result.stderr)

    def test_listed_path_that_does_not_exist_is_still_an_error(self):
        result = self.run_box(self.cfg({'ro': [str(self.dir / 'gone')]}), 'echo', 'ran')
        self.assertEqual((result.returncode, result.stdout), (1, ''))
        self.assertIn('aos-sandbox: error: PathMissing', result.stderr)

    def test_good_config_dry_run_builds_a_bwrap_chain(self):
        result = self.run_box('--dry-run', self.cfg({'net': False, 'ro': [str(self.dir)]}), 'echo', 'ran')
        self.assertEqual((result.returncode, result.stderr), (0, ''))
        argv = json.loads(result.stdout)
        self.assertEqual(os.path.basename(argv[0]), 'bwrap')
        self.assertEqual(argv[-3:], ['--', 'echo', 'ran'])

    def test_subuser_dry_run_prepends_asuser_before_limits_and_bwrap(self):
        fake = self.dir / 'aos-asuser'
        fake.write_text('#!/bin/sh\n# 這是乾跑測試用的 aos-asuser 替身。\nexit 0\n', encoding='utf-8')
        fake.chmod(0o755)
        self.env['PATH'] = str(self.dir) + os.pathsep + self.env.get('PATH', os.defpath)
        for cfg in ({'user': 'sub:5'}, {'user': 'sub:5', 'procs': 12}, {'user': 'sub:60000'}):
            with self.subTest(cfg=cfg):
                result = self.run_box('--dry-run', self.cfg(cfg), 'echo', 'ran')
                self.assertEqual((result.returncode, result.stderr), (0, ''))
                argv = json.loads(result.stdout)
                self.assertEqual(argv[:4], [str(fake), '--env-all', cfg['user'], '--'])
                bwrap = next(i for i, arg in enumerate(argv) if os.path.basename(arg) == 'bwrap')
                if 'procs' in cfg:
                    self.assertEqual(os.path.basename(argv[4]), 's6-softlimit')
                    self.assertEqual(argv[5:7], ['-p', '12'])
                    self.assertEqual(bwrap, 7)
                else:
                    self.assertEqual(bwrap, 4)
                self.assertFalse(any(os.path.basename(arg) in ('s6-setuidgid', 's6-applyuidgid') for arg in argv))
                self.assertIn('--clearenv', argv[bwrap + 1:])

    def test_invalid_subuser_dry_run_ignores_config_with_one_warning(self):
        for user in ('sub:0', 'sub:60001', 'sub:05', 'sub:', 'sub:-1', 'sub:+5', 'sub:5.0', 'sub:five',
                     'sub: 5', 'sub:\u0665'):
            with self.subTest(user=user):
                result = self.run_box('--dry-run', self.cfg({'user': user}), 'echo', 'ran')
                self.assertEqual(result.returncode, 0, result.stderr)
                argv = json.loads(result.stdout)
                self.assertEqual(os.path.basename(argv[0]), 'echo')
                self.assertEqual(argv[1:], ['ran'])
                self.assertEqual(result.stderr, WARNING + 'user sub:N needs N from 1 to 60000\n')

    def fake_sudo(self, refuse=False):
        path = self.dir / 'sudo'
        path.write_text('#!/bin/sh\n# sudo 測試替身只略過身分層，不真的換身分。\n'
                        'test "$1" = -n && test "$2" = -k || exit 99\n'
                        'case "$5" in /usr/bin/true|/bin/true)\n' +
                        ('echo "sudo: a password is required" >&2; exit 1;;\n' if refuse else 'exit 0;;\n') +
                        'esac\nshift 4\nexec "$@"\n', encoding='utf-8')
        path.chmod(0o755)
        self.env['PATH'] = str(self.dir) + os.pathsep + self.env.get('PATH', os.defpath)
        return str(path)

    def require_sudo_fixture(self):
        if os.geteuid() == 0:
            self.skipTest('requires a non-root caller')
        if not (os.path.isfile(SUDO_SETUIDGID) and os.access(SUDO_SETUIDGID, os.X_OK)):
            self.skipTest('fixed s6-setuidgid executable is not installed')

    def test_sudo_and_root_dry_run_chains(self):
        module = sandbox_module()
        sudo = self.fake_sudo()
        with mock.patch.object(module, 'euid', return_value=1000), \
                mock.patch.object(module.pwd, 'getpwnam', return_value=SimpleNamespace(pw_uid=951, pw_gid=951)), \
                mock.patch.object(module, 'SUDO_SETUIDGID', SUDO_SETUIDGID), \
                mock.patch.dict(os.environ, self.env), mock.patch.object(module.subprocess, 'run') as precheck:
            for cfg in ({'user': 'aos-run'}, {'user': 'aos-run', 'cpu_s': 3}):
                argv = module.build(cfg, ['id', '-un'], True)
                self.assertEqual(argv[:5], [sudo, '-n', '-k', SUDO_SETUIDGID, 'aos-run'])
                self.assertEqual(os.path.basename(argv[5]), 's6-softlimit' if 'cpu_s' in cfg else 'bwrap')
                if 'cpu_s' in cfg:
                    self.assertEqual(argv[6:8], ['-t', '3'])
            precheck.assert_not_called()
        with mock.patch.object(module, 'euid', return_value=0):
            argv = module.build({'user': 'root', 'cpu_s': 3}, ['id'], True)
            self.assertEqual(os.path.basename(argv[0]), 's6-softlimit')
            self.assertEqual(argv[1:3], ['-t', '3'])
            self.assertEqual(os.path.basename(argv[3]), 's6-setuidgid')
            self.assertEqual(argv[4], 'root')
            self.assertEqual(os.path.basename(argv[5]), 'bwrap')
            self.assertNotIn('-k', argv)

    def test_user_format_rejection_is_one_warning(self):
        for user in ('--', '-x', 'a\nb', 'Upper', 'has space', 'x' * 33):
            result = self.run_box('--dry-run', self.cfg({'user': user}), 'echo', 'ran')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, WARNING + 'user must be an account name, uid:gid or sub:N\n')
            self.assertEqual(os.path.basename(json.loads(result.stdout)[0]), 'echo')

    def test_nonroot_user_identity_checks_even_when_dry(self):
        module = sandbox_module()
        cases = [('951:951', None, 'uid:gid needs root; give an account name to go through sudo'),
                 ('root', SimpleNamespace(pw_uid=0, pw_gid=0), 'refusing to switch to root through sudo (uid or gid 0)'),
                 ('zero_gid', SimpleNamespace(pw_uid=951, pw_gid=0), 'refusing to switch to zero_gid through sudo (uid or gid 0)'),
                 ('missing_account', None, 'unknown account missing_account')]
        for user, account, expected in cases:
            with self.subTest(user=user), mock.patch.object(module, 'euid', return_value=1000), \
                    mock.patch.object(module.pwd, 'getpwnam', **({'return_value': account} if account else {'side_effect': KeyError(user)})), \
                    mock.patch('sys.stderr') as err:
                with self.assertRaises(SystemExit) as raised:
                    module.build({'user': user}, ['id'], True)
                self.assertEqual(raised.exception.code, 1)
                self.assertIn('aos-sandbox: error: UserBad ' + expected, ''.join(call.args[0] for call in err.write.call_args_list))

    def test_sudo_checks_after_other_config_and_paths(self):
        module = sandbox_module()
        with mock.patch.object(module, 'euid', return_value=1000), \
                mock.patch.object(module.pwd, 'getpwnam', return_value=SimpleNamespace(pw_uid=951, pw_gid=951)), \
                mock.patch.object(module.shutil, 'which', side_effect=lambda name: '/usr/bin/' + name if name != 'sudo' else None) as find:
            with self.assertRaises(module.CfgBad):
                module.build({'user': 'aos-run', 'env': 'bad'}, ['id'], False)
            with mock.patch('sys.stderr'):
                with self.assertRaises(SystemExit):
                    module.build({'user': 'aos-run', 'ro': [str(self.dir / 'gone')]}, ['id'], False)
            self.assertNotIn(mock.call('sudo'), find.call_args_list)
            self.assertNotIn(mock.call('s6-applyuidgid'), find.call_args_list)

    def test_missing_sudo_and_fixed_identity_executable(self):
        if os.geteuid() == 0:
            self.skipTest('requires a non-root caller')
        module = sandbox_module()
        for missing in ('sudo', 'identity'):
            with self.subTest(missing=missing), \
                    mock.patch.object(module.shutil, 'which', side_effect=lambda name: None if name == 'sudo' and missing == 'sudo' else '/usr/bin/' + name), \
                    mock.patch.object(module, 'SUDO_SETUIDGID', str(self.dir / 'missing-identity')), \
                    mock.patch.object(module.pwd, 'getpwnam', return_value=SimpleNamespace(pw_uid=951, pw_gid=951)), \
                    mock.patch('sys.stderr') as err:
                with self.assertRaises(SystemExit) as raised:
                    module.build({'user': 'aos-run'}, ['id'], False)
                self.assertEqual(raised.exception.code, 1)
                text = ''.join(call.args[0] for call in err.write.call_args_list)
                self.assertIn('error: CommandMissing', text)
                self.assertIn('sudo not found on PATH' if missing == 'sudo' else 'install it with root/setup.sh', text)

    def test_fake_sudo_precheck_refusal_does_not_run_prog(self):
        self.require_sudo_fixture()
        self.fake_sudo(refuse=True)
        marker = self.dir / 'marker'
        result = self.run_box(self.cfg({'user': 'aos-run'}), 'sh', '-c', 'touch "$0"', str(marker))
        self.assertEqual((result.returncode, result.stdout), (1, ''))
        self.assertEqual(result.stderr, 'aos-sandbox: error: UserBad sudo -n -k /usr/local/bin/s6-setuidgid aos-run refused or failed (sudo: a password is required); this needs the NOPASSWD sudoers rule and the account from root/setup.sh, or run as root\n')
        self.assertFalse(marker.exists())

    @unittest.skipUnless(bwrap_works(), 'bwrap is not usable here')
    def test_fake_sudo_precheck_success_runs_prog(self):
        self.require_sudo_fixture()
        self.fake_sudo()
        prog = self.dir / 'prog'
        prog.write_text('#!/bin/sh\n# 測試程式寫標記，確認預檢後才執行。\necho ran > "$1"\n')
        prog.chmod(0o755)
        marker = self.dir / 'marker'
        result = self.run_box(self.cfg({'user': 'aos-run', 'rw': [str(self.dir)]}), str(prog), str(marker))
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, '', ''))
        self.assertEqual(marker.read_text(), 'ran\n')

    def test_precheck_failures_and_trusted_true(self):
        module = sandbox_module()
        cases = [(mock.Mock(returncode=1, stderr='\n  denied  \nsecond\n'), None, 'denied'),
                 (mock.Mock(returncode=4, stderr=' \n'), None, 'exit 4'),
                 (None, subprocess.TimeoutExpired('sudo', 10), 'sudo timed out'),
                 (None, OSError(13, 'denied'), 'cannot run sudo: denied')]
        for response, failure, expected in cases:
            with self.subTest(expected=expected), mock.patch.object(module, 'euid', return_value=1000), \
                    mock.patch.object(module.os.path, 'isfile', return_value=True), \
                    mock.patch.object(module.os, 'access', return_value=True), \
                    mock.patch.object(module.subprocess, 'run', return_value=response, side_effect=failure) as run, \
                    mock.patch('sys.stderr') as err:
                with self.assertRaises(SystemExit):
                    module.precheck_sudo('/fake/sudo', 'aos-run')
                self.assertIn('refused or failed (' + expected + ')', ''.join(call.args[0] for call in err.write.call_args_list))
                self.assertEqual(run.call_args.args[0], ['/fake/sudo', '-n', '-k', SUDO_SETUIDGID, 'aos-run', '/usr/bin/true'])
                self.assertEqual(run.call_args.kwargs, dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                                           stderr=subprocess.PIPE, text=True, errors='replace', timeout=10))
        with mock.patch.object(module, 'euid', return_value=1000), \
                mock.patch.object(module.os.path, 'isfile', side_effect=lambda path: path == '/bin/true'), \
                mock.patch.object(module.os, 'access', return_value=True), \
                mock.patch.object(module.subprocess, 'run', return_value=mock.Mock(returncode=0)) as run:
            module.precheck_sudo('/fake/sudo', 'aos-run')
            self.assertEqual(run.call_args.args[0][-1], '/bin/true')
        with mock.patch.object(module, 'euid', return_value=1000), \
                mock.patch.object(module.os.path, 'isfile', return_value=False), \
                mock.patch.object(module.subprocess, 'run') as run, mock.patch('sys.stderr') as err:
            with self.assertRaises(SystemExit):
                module.precheck_sudo('/fake/sudo', 'aos-run')
            run.assert_not_called()
            self.assertIn('CommandMissing true not found in /usr/bin or /bin', ''.join(call.args[0] for call in err.write.call_args_list))

    def test_real_sudo_identity_and_refusals(self):
        self.require_sudo_fixture()
        sudo = shutil.which('sudo')
        if not sudo:
            self.skipTest('sudo is not installed')
        probe = subprocess.run([sudo, '-n', '-k', SUDO_SETUIDGID, 'aos-run', '/usr/bin/true'],
                               stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=10)
        if probe.returncode:
            self.skipTest('NOPASSWD identity rule is not available: ' + probe.stderr.strip())
        directory = tempfile.mkdtemp(dir='/tmp', prefix='aos-sandbox-sudo-')
        self.addCleanup(shutil.rmtree, directory)
        os.chmod(directory, 0o755)
        spec = Path(directory) / 'sandbox.json'

        def run_identity(user):
            spec.write_text(json.dumps({'user': user}), encoding='utf-8')
            spec.chmod(0o644)
            return subprocess.run([str(SANDBOX), str(spec), 'id', '-un'],
                                  capture_output=True, text=True, env=self.env, cwd=directory, timeout=60)

        result = run_identity('aos-run')
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, 'aos-run\n', ''))
        print('real sudo identity: stdout=' + repr(result.stdout) + ' exit=' + str(result.returncode))
        for user in ('root', 'nobody'):
            result = run_identity(user)
            self.assertEqual((result.returncode, result.stdout), (1, ''))
            self.assertEqual(len(result.stderr.splitlines()), 1)
            self.assertTrue(result.stderr.startswith('aos-sandbox: error: UserBad '), result.stderr)
            if user == 'nobody':
                self.assertIn('a password is required', result.stderr)

    @unittest.skipUnless(bwrap_works(), 'bwrap is not usable here')
    def test_good_config_really_runs_inside_bwrap(self):
        secret = self.dir / 'secret.txt'
        secret.write_text('x', encoding='utf-8')
        (self.dir / 'box').mkdir()     # 設定檔所在的夾會被唯讀綁（T34）；設定放自己的夾，祕密不在裡面
        result = self.run_box(self.cfg({}, 'box/sandbox.json'), 'sh', '-c', 'test -e "$0" && echo seen || echo hidden', str(secret))
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, 'hidden\n', ''))
        result = self.run_box(self.cfg('{bad'), 'sh', '-c', 'test -e "$0" && echo seen || echo hidden', str(secret))
        self.assertEqual((result.returncode, result.stdout), (0, 'seen\n'))
        self.assertIn(WARNING, result.stderr)

    def test_dry_run_orders_binds_by_depth_and_ends_read_only(self):
        repo = self.dir / 'repo'
        (repo / '.git').mkdir(parents=True)
        result = self.run_box('--dry-run', self.cfg({'ro': [str(repo / '.git')], 'rw': [str(repo)]}), 'echo', 'ran')
        self.assertEqual((result.returncode, result.stderr), (0, ''))
        argv = json.loads(result.stdout)
        i_rw = argv.index(str(repo)) - 1
        i_ro = argv.index(str(repo / '.git')) - 1
        self.assertEqual((argv[i_rw], argv[i_ro]), ('--bind', '--ro-bind'))
        self.assertLess(i_rw, i_ro)                                  # 深的（.git）後綁＝說了算
        self.assertEqual(argv[argv.index('--remount-ro') + 1], '/')
        self.assertGreater(argv.index('--remount-ro'), i_ro)          # 根唯讀放在所有綁定之後

    def test_dry_run_binds_the_config_folder_only_when_not_listed(self):
        tool = self.dir / 'tool'
        tool.mkdir()
        spec = str(tool / 'sandbox.json')
        Path(spec).write_text('{}', encoding='utf-8')
        argv = json.loads(self.run_box('--dry-run', spec, 'echo', 'ran').stdout)
        self.assertEqual(argv[argv.index(str(tool)) - 1], '--ro-bind')
        Path(spec).write_text(json.dumps({'rw': [str(self.dir)]}), encoding='utf-8')
        argv = json.loads(self.run_box('--dry-run', spec, 'echo', 'ran').stdout)
        self.assertNotIn(str(tool), argv)                             # 已在 rw 裡＝不另綁（不會把它變唯讀）

    @unittest.skipUnless(bwrap_works(), 'bwrap is not usable here')
    def test_ro_inside_rw_stays_read_only(self):
        repo = self.dir / 'repo'
        (repo / '.git').mkdir(parents=True)
        (repo / 'sub').mkdir()
        script = 'touch "$0/a" && echo a-ok; touch "$0/.git/b" 2>/dev/null && echo git-written || echo git-ro'
        result = self.run_box(self.cfg({'ro': [str(repo / '.git')], 'rw': [str(repo)]}), 'sh', '-c', script, str(repo))
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, 'a-ok\ngit-ro\n', ''))
        self.assertFalse((repo / '.git/b').exists())
        # 反過來：repo 唯讀、裡面的 sub 可寫
        script = 'touch "$0/c" 2>/dev/null && echo c-written || echo c-ro; touch "$0/sub/d" && echo d-ok'
        result = self.run_box(self.cfg({'rw': [str(repo / 'sub')], 'ro': [str(repo)]}), 'sh', '-c', script, str(repo))
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, 'c-ro\nd-ok\n', ''))
        self.assertTrue((repo / 'sub/d').exists())

    @unittest.skipUnless(bwrap_works(), 'bwrap is not usable here')
    def test_write_outside_rw_fails_loudly(self):
        # 以前寫進沙箱的暫存根、退 0、主機上沒檔；現在根唯讀＝失敗、看得到錯
        result = self.run_box(self.cfg({}), 'sh', '-c', 'mkdir -p /aos-sandbox-t36/x')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Read-only file system', result.stderr)
        result = self.run_box(self.cfg({}), 'sh', '-c', 'echo y > /tmp/scratch && cat /tmp/scratch')
        self.assertEqual((result.returncode, result.stdout), (0, 'y\n'), result.stderr)   # /tmp 照舊可寫（空的、跑完就沒了）

    @unittest.skipUnless(bwrap_works(), 'bwrap is not usable here')
    def test_config_folder_is_visible_so_relative_entries_work(self):
        tool = self.dir / 'tool'
        tool.mkdir()
        (tool / 'inner').write_text('hello\n', encoding='utf-8')
        spec = tool / '_metainfo.json'
        spec.write_text(json.dumps({'sandbox': {'ro': []}}), encoding='utf-8')
        result = subprocess.run([str(SANDBOX), '_metainfo.json#/sandbox', 'cat', 'inner'], capture_output=True, text=True,
                                env=self.env, cwd=tool, timeout=60)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, 'hello\n', ''))

    def fake_home(self, name='home', package=True):
        home = self.dir / name
        (home / 'bin').mkdir(parents=True)
        for command in ('aos-fake-a', 'aos-fake-b'):
            (home / 'bin' / command).write_text('#!/bin/sh\nexit 0\n', encoding='utf-8')
            (home / 'bin' / command).chmod(0o755)
        if package:
            (home / 'lib/aos').mkdir(parents=True)
            (home / 'lib/aos/__init__.py').write_text('', encoding='utf-8')
        return home

    @staticmethod
    def ro_binds(argv):
        return [argv[i + 1] for i, arg in enumerate(argv[:-2]) if arg == '--ro-bind' and argv[i + 1] == argv[i + 2]]

    def test_aos_commands_bind_the_whole_home_once(self):
        # 路徑規則路-7：命令真位置在 <家>/bin、旁邊有 <家>/lib/aos＝整個家唯讀綁一次，不再只綁 <家>/lib、也不另綁 <家>/bin。
        home = self.fake_home()
        self.env['PATH'] = str(home / 'bin') + os.pathsep + self.env.get('PATH', os.defpath)
        result = self.run_box('--dry-run', self.cfg({'commands': ['aos-fake-a', 'aos-fake-b']}), 'echo', 'ran')
        self.assertEqual((result.returncode, result.stderr), (0, ''))
        binds = self.ro_binds(json.loads(result.stdout))
        self.assertEqual(binds.count(str(home)), 1, binds)
        self.assertNotIn(str(home / 'lib'), binds)
        self.assertNotIn(str(home / 'bin'), binds)

    def test_linked_aos_command_binds_the_link_folder_and_the_home(self):
        home = self.fake_home()
        links = self.dir / 'links'
        links.mkdir()
        (links / 'aos-fake-a').symlink_to(home / 'bin/aos-fake-a')
        self.env['PATH'] = str(links) + os.pathsep + self.env.get('PATH', os.defpath)
        result = self.run_box('--dry-run', self.cfg({'commands': ['aos-fake-a']}), 'echo', 'ran')
        self.assertEqual((result.returncode, result.stderr), (0, ''))
        binds = self.ro_binds(json.loads(result.stdout))
        self.assertEqual((binds.count(str(links)), binds.count(str(home))), (1, 1), binds)
        self.assertNotIn(str(home / 'bin'), binds)

    def test_command_outside_a_home_binds_only_its_folder(self):
        home = self.fake_home('plain', package=False)
        self.env['PATH'] = str(home / 'bin') + os.pathsep + self.env.get('PATH', os.defpath)
        result = self.run_box('--dry-run', self.cfg({'commands': ['aos-fake-a']}), 'echo', 'ran')
        self.assertEqual((result.returncode, result.stderr), (0, ''))
        binds = self.ro_binds(json.loads(result.stdout))
        self.assertIn(str(home / 'bin'), binds)
        self.assertNotIn(str(home), binds)

    def real_home(self, name):
        home = self.fake_home(name)
        (home / 'install.py').write_text('', encoding='utf-8')
        return home

    def test_aos_home_set_is_the_home_that_gets_bound(self):
        # 使用者 11-18 選項框「AOS_HOME 有設就用它」：命令在 AOS_HOME 的 bin＝綁 AOS_HOME 一次、不另綁 bin、沒有警告。
        home = self.real_home('set')
        self.env['AOS_HOME'] = str(home)
        self.env['PATH'] = str(home / 'bin') + os.pathsep + self.env.get('PATH', os.defpath)
        result = self.run_box('--dry-run', self.cfg({'commands': ['aos-fake-a', 'aos-fake-b']}), 'echo', 'ran')
        self.assertEqual((result.returncode, result.stderr), (0, ''))
        binds = self.ro_binds(json.loads(result.stdout))
        self.assertEqual(binds.count(str(home)), 1, binds)
        self.assertNotIn(str(home / 'bin'), binds)

    def test_aos_home_set_wins_over_the_command_location(self):
        # 命令來自另一個家：綁 AOS_HOME、只綁那個命令自己的資料夾（不綁它的家），stderr 一行警告。
        home, other = self.real_home('set'), self.real_home('other')
        self.env['AOS_HOME'] = str(home)
        self.env['PATH'] = str(other / 'bin') + os.pathsep + self.env.get('PATH', os.defpath)
        result = self.run_box('--dry-run', self.cfg({'commands': ['aos-fake-a']}), 'echo', 'ran')
        self.assertEqual(result.returncode, 0, result.stderr)
        binds = self.ro_binds(json.loads(result.stdout))
        self.assertEqual((binds.count(str(home)), binds.count(str(other / 'bin'))), (1, 1), binds)
        self.assertNotIn(str(other), binds)
        lines = result.stderr.splitlines()
        self.assertEqual(len(lines), 1, result.stderr)
        self.assertTrue(lines[0].startswith('aos-sandbox: warning: aos-fake-a is from the aos home '), lines[0])

    def test_aos_home_unset_falls_back_to_the_command_location(self):
        home = self.real_home('unset')
        self.assertNotIn('AOS_HOME', self.env)
        self.env['PATH'] = str(home / 'bin') + os.pathsep + self.env.get('PATH', os.defpath)
        result = self.run_box('--dry-run', self.cfg({'commands': ['aos-fake-a']}), 'echo', 'ran')
        self.assertEqual((result.returncode, result.stderr), (0, ''))
        self.assertEqual(self.ro_binds(json.loads(result.stdout)).count(str(home)), 1)

    def test_aos_home_set_to_a_non_home_is_env_bad(self):
        # 不像家（沒 install.py、或沒 bin/；判準比照 env.sh）＝EnvBad 一行、退 1，不默默退回認命令位置。
        home = self.real_home('good')
        self.env['PATH'] = str(home / 'bin') + os.pathsep + self.env.get('PATH', os.defpath)
        no_install = self.dir / 'no-install'
        (no_install / 'bin').mkdir(parents=True)
        no_bin = self.dir / 'no-bin'
        no_bin.mkdir()
        (no_bin / 'install.py').write_text('', encoding='utf-8')
        spec = self.cfg({'commands': ['aos-fake-a']})
        for bad in (no_install, no_bin, self.dir / 'missing'):
            with self.subTest(bad=bad.name):
                self.env['AOS_HOME'] = str(bad)
                for args in (('--dry-run', spec), (spec,)):
                    result = self.run_box(*args, 'echo', 'ran')
                    self.assertEqual((result.returncode, result.stdout), (1, ''), result.stderr)
                    lines = result.stderr.splitlines()
                    self.assertEqual(len(lines), 1, result.stderr)
                    self.assertTrue(lines[0].startswith('aos-sandbox: error: EnvBad AOS_HOME=%s is not an aos home' % bad),
                                    lines[0])
        # 沒列 aos 的命令＝不綁家、也不檢查 AOS_HOME。
        self.env['AOS_HOME'] = str(no_install)
        result = self.run_box('--dry-run', self.cfg({'commands': []}, 'plain.json'), 'echo', 'ran')
        self.assertEqual((result.returncode, result.stderr), (0, ''))

    def test_default_env_passes_aos_home_and_an_env_list_replaces_it(self):
        self.env['AOS_HOME'] = str(self.dir)
        argv = json.loads(self.run_box('--dry-run', self.cfg({}), 'echo', 'ran').stdout)
        i = argv.index('AOS_HOME')
        self.assertEqual((argv[i - 1], argv[i + 1]), ('--setenv', str(self.dir)))
        argv = json.loads(self.run_box('--dry-run', self.cfg({'env': ['PATH']}), 'echo', 'ran').stdout)
        self.assertNotIn('AOS_HOME', argv)


if __name__ == '__main__':
    unittest.main()
