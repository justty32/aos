# Check aos_flags.parse(anywhere=True) and the one-layer commands moved to it (P-44 continued, 11-11 "全部改").
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PROTO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(PROTO / 'py'), str(PROTO / 'lib')]
import aos_flags  # noqa: E402

BASE = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}


def run(prog, *argv, env=None):
    exe = {'aos-eca-screen': PROTO / 'cmd' / 'aos-eca' / 'bin' / 'aos-eca-screen'}.get(prog, PROTO / 'cmd' / prog / 'bin' / prog)
    return subprocess.run([sys.executable, str(exe), *argv], env=dict(BASE, **(env or {})),
                          capture_output=True, text=True, timeout=30)


class Anywhere(unittest.TestCase):
    def test_parse_flags_after_positionals(self):
        opts, rest = aos_flags.parse(['a', '--ws', 'W', 'b', '--one'], {'--ws': 'ws'}, {'--one': 'one'}, anywhere=True)
        self.assertEqual((opts, rest), ({'ws': 'W', 'one': True}, ['a', 'b']))

    def test_parse_keep_dashes_numbers(self):
        opts, rest = aos_flags.parse(['cfg', '--dry', 'prog', '-x', '--dry'], {}, {'--dry': 'dry'}, anywhere=True, keep=2)
        self.assertEqual((opts, rest), ({'dry': True}, ['cfg', 'prog', '-x', '--dry']))
        self.assertEqual(aos_flags.parse(['a', '-3'], {}, anywhere=True)[1], ['a', '-3'])
        self.assertEqual(aos_flags.parse(['a', '--', '-x'], {}, anywhere=True)[1], ['a', '--', '-x'])
        with self.assertRaises(aos_flags.Error) as e:
            aos_flags.parse(['a', '--nope'], {}, anywhere=True)
        self.assertEqual(e.exception.code, 'FlagUnknown')

    def test_without_anywhere_old_rule(self):
        self.assertEqual(aos_flags.parse(['a', '--ws', 'W'], {'--ws': 'ws'}), ({}, ['a', '--ws', 'W']))


class Commands(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-flags-anywhere-')
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)

    def test_sandbox_dry_run_after_config_prog_args_raw(self):
        cfg = self.d / 'box.json'
        cfg.write_text('{}')
        p = run('aos-sandbox', str(cfg), '--dry-run', '/bin/echo', '--dry-run', '-x')
        self.assertEqual(p.returncode, 0, p.stderr)
        argv = json.loads(p.stdout)
        self.assertEqual(argv[-3:], ['/bin/echo', '--dry-run', '-x'])

    def test_clock_unknown_flag_after_file(self):
        f = self.d / 'clock'
        self.assertEqual(run('aos-clock', str(f)).returncode, 0)
        p = run('aos-clock', str(f), '--nope')
        self.assertEqual(p.returncode, 1)
        self.assertIn('FlagUnknown', p.stderr)
        self.assertEqual(f.read_text(), '1\n')

    def test_mcp_flag_after_registry(self):
        p = run('aos-mcp', str(self.d / 'tools.json'), '--nope')
        self.assertEqual(p.returncode, 1)
        self.assertIn('aos-mcp: error: FlagUnknown unknown flag --nope', p.stderr)

    def test_eca_screen_eca_after_subcommand(self):
        p = run('aos-eca-screen', 'close', '--eca', str(self.d))
        self.assertEqual(p.returncode, 1)
        self.assertIn('is not an eca dir (no cli.json)', p.stderr)   # --eca was taken after close

    def test_feedback_flags_both_sides_and_dashes(self):
        env = {'AOS_FEEDBACK': str(self.d / 'fb')}
        p = run('aos-feedback', 'add', 'aos-x', 'slow', '--kind', 'usage', '--json', env=env)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)['kind'], 'usage')
        p = run('aos-feedback', '--json', 'add', 'aos-x', '--', '-weird pain', env=env)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)['pain'], '-weird pain')
        p = run('aos-feedback', 'ls', '-j', env=env)
        self.assertEqual(json.loads(p.stdout)[0]['feedback'], 2)


if __name__ == '__main__':
    unittest.main()
