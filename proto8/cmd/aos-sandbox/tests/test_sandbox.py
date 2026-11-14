# Verify aos-sandbox: a broken config runs prog unsandboxed with a warning, real errors stay errors, the deeper of ro/rw wins (T32), writes outside rw fail (T36) and the config's folder is visible (T34).
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SANDBOX = Path(__file__).resolve().parents[1] / 'bin/aos-sandbox'
WARNING = 'aos-sandbox: warning: sandbox config ignored, running unsandboxed: '


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
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)
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


if __name__ == '__main__':
    unittest.main()
