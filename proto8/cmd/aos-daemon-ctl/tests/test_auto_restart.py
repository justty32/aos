# Verify --auto-restart: add_letter puts "auto_restart": true on the row for loop, exec and envs types, and both add commands take the switch.
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PROTO8 = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROTO8 / 'py'))
import daemon_ctl as dc  # noqa: E402

DAEMON_CTL = PROTO8 / 'cmd/aos-daemon-ctl/bin/aos-daemon-ctl'
AOS_AGENT = PROTO8 / 'cmd/aos-agent/bin/aos-agent'


class AddLetter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.loop = self.root / 'looper'
        self.loop.mkdir()
        (self.loop / '_entry').write_text(json.dumps({'exec': 'body.json', 'interval_ms': 500}))
        self.job = self.root / 'job'
        self.job.write_text('#!/bin/sh\nexit 0\n')
        self.job.chmod(0o755)

    def spec(self, target, **kw):
        name, body = dc.add_letter(str(target), **kw)
        return body['procs_added'][name]

    def test_loop_type(self):
        off = self.spec(self.loop)
        on = self.spec(self.loop, auto_restart=True)
        self.assertNotIn('auto_restart', off)
        self.assertIs(on.pop('auto_restart'), True)
        self.assertEqual(on, off)
        self.assertEqual(off['interval_ms'], 500)
        self.assertEqual(off['exec'], str(self.loop / 'body.json'))

    def test_loop_with_only_exec_still_gets_interval(self):
        (self.loop / '_entry').write_text(json.dumps({'exec': 'body.json'}))
        on = self.spec(self.loop, auto_restart=True)
        self.assertEqual((on['interval_ms'], on['auto_restart']), (0, True))

    def test_exec_type(self):
        off = self.spec(self.job, extra=['a'])
        on = self.spec(self.job, extra=['a'], auto_restart=True)
        self.assertNotIn('auto_restart', off)
        self.assertEqual(on, dict(off, auto_restart=True))
        self.assertEqual(on['exec'], [str(self.job), 'a'])
        self.assertTrue(set(on) <= {'exec', 'def', 'ws', 'stack', 'limits', 'auto_restart'})   # 仍是 exec 型

    def test_envs_type(self):
        off = self.spec(self.job, envs={'K': 'v'})
        on = self.spec(self.job, envs={'K': 'v'}, auto_restart=True)
        self.assertNotIn('auto_restart', off)
        self.assertEqual(on, dict(off, auto_restart=True))
        self.assertEqual(on['exec'], {'argv': ['aos-exec', '--', str(self.job)], 'envs': {'K': 'v'}})

    def test_loop_with_envs(self):
        on = self.spec(self.loop, envs={'K': 'v'}, auto_restart=True)
        self.assertIs(on['auto_restart'], True)
        self.assertEqual(on['exec']['envs'], {'K': 'v'})
        self.assertNotIn('auto_restart', on['exec'])


class Flags(unittest.TestCase):
    def run_cmd(self, *argv):
        return subprocess.run([sys.executable, *map(str, argv)], capture_output=True, text=True, timeout=20,
                              stdin=subprocess.DEVNULL, env=dict(os.environ, AOS_DAEMON='/nonexistent-aos-daemon'))

    def test_help_mentions_switch(self):
        for argv in ((DAEMON_CTL, 'add', '--help'), (AOS_AGENT, 'ctl', 'add', '--help')):
            with self.subTest(argv=argv):
                r = self.run_cmd(*argv)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn('--auto-restart', r.stdout)
                self.assertIn('3 quick exits', ' '.join(r.stdout.split()))
                self.assertIn('fire-and-forget', r.stdout)

    def test_value_is_an_error(self):
        for argv in ((DAEMON_CTL, 'add', '--auto-restart=yes', 'x'), (AOS_AGENT, 'ctl', 'add', '--auto-restart=yes', 'x')):
            with self.subTest(argv=argv):
                r = self.run_cmd(*argv)
                self.assertEqual(r.returncode, 1)
                self.assertIn('error: ArgumentsBad', r.stderr)
                self.assertIn('--auto-restart', r.stderr)


if __name__ == '__main__':
    unittest.main()
