# Verify aos-sandbox treats a broken config as not written (runs prog unsandboxed with a warning) and keeps real errors.
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

    @unittest.skipUnless(bwrap_works(), 'bwrap is not usable here')
    def test_good_config_really_runs_inside_bwrap(self):
        secret = self.dir / 'secret.txt'
        secret.write_text('x', encoding='utf-8')
        result = self.run_box(self.cfg({}), 'sh', '-c', 'test -e "$0" && echo seen || echo hidden', str(secret))
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, 'hidden\n', ''))
        result = self.run_box(self.cfg('{bad'), 'sh', '-c', 'test -e "$0" && echo seen || echo hidden', str(secret))
        self.assertEqual((result.returncode, result.stdout), (0, 'seen\n'))
        self.assertIn(WARNING, result.stderr)


if __name__ == '__main__':
    unittest.main()
