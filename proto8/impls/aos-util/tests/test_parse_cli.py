# Check aos::parse_cli takes flags before or after positionals (P-44 continued, 11-11) through the C++ parts that use it.
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

IMPLS = Path(__file__).resolve().parents[2]
BASE = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}


def bin_of(name):
    return str(IMPLS / name / 'bin' / name)


def run(name, *argv, env=None, stdin=None):
    return subprocess.run([bin_of(name), *argv], env=dict(BASE, **(env or {})), input=stdin,
                          capture_output=True, text=True, timeout=20)


class ParseCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-util-cli-')
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)
        self.j = self.d / 'j.json'
        self.j.write_text('{"a": "x", "n": 1}')

    def test_flag_after_positional(self):
        p = run('aos-json', 'get', '%s#/a' % self.j, '--str')
        self.assertEqual((p.returncode, p.stdout), (0, 'x\n'), p.stderr)
        self.assertEqual(run('aos-json', 'get', '--str', '%s#/a' % self.j).stdout, 'x\n')   # old order still works

    def test_unknown_flag_after_positional(self):
        p = run('aos-json', 'get', '%s#/a' % self.j, '--bogus')
        self.assertEqual(p.returncode, 1)
        self.assertIn('aos-json: error: FlagUnknown unknown flag --bogus', p.stderr)

    def test_help_after_positional(self):
        p = run('aos-json', 'get', '%s#/a' % self.j, '--help')
        self.assertEqual(p.returncode, 0)
        self.assertIn('usage: aos-json get', p.stdout)

    def test_set_value_kept_as_written(self):
        # set / append / merge keep the old rule: the value may be any word, even one that looks like a flag
        self.assertEqual(run('aos-json', 'set', '--str', '%s#/b' % self.j, '-x').returncode, 0)
        self.assertEqual(run('aos-json', 'set', '--str', '%s#/c' % self.j, '--check').returncode, 0)
        self.assertEqual(run('aos-json', 'set', '%s#/d' % self.j, '-5').returncode, 0)
        doc = json.loads(self.j.read_text())
        self.assertEqual((doc['b'], doc['c'], doc['d']), ('-x', '--check', -5))

    def test_negative_number_stays_positional(self):
        lock = self.d / 'data'
        lock.write_text('{}')
        p = run('aos-lock', 'acquire', str(lock), '--lease-cycles', '3', env={'AOS_WS': str(self.d)})
        self.assertEqual(p.returncode, 0, p.stderr)
        p = run('aos-lock', 'release', str(lock), '-5', env={'AOS_WS': str(self.d)})
        self.assertNotIn('FlagUnknown', p.stderr)   # "-5" is a (bad) extra positional, not an unknown flag

    def test_subcommand_program_top_stops_at_subcommand(self):
        p = run('aos-json', '--str', 'get', '%s#/a' % self.j)
        self.assertEqual(p.returncode, 1)
        self.assertIn('FlagUnknown', p.stderr)   # the top layer has no flags; get's flags belong after get

    def test_exec_args_stay_raw(self):
        p = run('aos-exec', '/bin/echo', '-w', 'x', '--stack', 'y')
        self.assertEqual((p.returncode, p.stdout), (0, '-w x --stack y\n'), p.stderr)

    def test_loop_flag_after_config_and_args_after_dashes(self):
        body = self.d / 'body.sh'
        body.write_text('#!/bin/sh\n# print args\necho "$@" >> "$AOS_STACK/args.txt"\n')
        body.chmod(0o755)
        cfg = self.d / 'loop.json'
        cfg.write_text(json.dumps({'exec': str(body), 'interval_ms': 10}))
        stack = self.d / 'stack'
        p = run('aos-loop', str(cfg), '--max', '2', '--', 'a', '-b', env={'AOS_STACK': str(stack)})
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual((stack / 'args.txt').read_text().splitlines(), ['a -b', 'a -b'])
        p = run('aos-loop', str(cfg), 'extra', env={'AOS_STACK': str(stack)})
        self.assertEqual(p.returncode, 1)
        self.assertIn('only one config file allowed, got extra extra', p.stderr)


if __name__ == '__main__':
    unittest.main()
