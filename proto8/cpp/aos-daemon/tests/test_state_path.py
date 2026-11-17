# Check the procs_state_path query letter (11-13, K-F27): the reply carries the absolute path of procs_state.json, null without that window, BodyBad when not true.
# AOS_TEST_DAEMON_BIN_DIR=<folder holding another aos-daemon> puts that folder first on PATH (to test a build outside the repo).
import json
import os
from pathlib import Path
import subprocess
import unittest

import support
from support import ENV, Fixture, read, until, write

if os.environ.get('AOS_TEST_DAEMON_BIN_DIR'):
    ENV['PATH'] = os.environ['AOS_TEST_DAEMON_BIN_DIR'] + ':' + ENV['PATH']


class StatePath(unittest.TestCase):
    def fixture(self, name, **cfg):
        f = Fixture(name)
        if cfg:
            write(f.config, dict(read(f.config), **cfg))
        self.addCleanup(f.close)
        return f

    def box(self, f):
        box = f.root / 'replies'
        subprocess.run(['aos-post', 'init', str(box)], env=ENV, check=True)
        return box

    def ask(self, f, box, body):
        args = ['aos-post', 'send', '--reply-to', str(box), str(f.stack / 'procs_requests')]
        letter = subprocess.run(args, input=json.dumps(body), env=ENV, capture_output=True, text=True, check=True).stdout.strip()
        got = until(lambda: [r for r in (read(p / 'letter.json') for p in sorted((box / 'new').iterdir()))
                             if r and r['in_reply_to'] == letter])
        return got[0]['body']

    def test_reply_has_absolute_path_of_the_table(self):
        f = self.fixture('state_path_ok').start()
        body = self.ask(f, self.box(f), {'procs_state_path': True})
        self.assertEqual(body, {'applied': True, 'procs_state_path': str(f.stack / 'procs_state.json')})
        self.assertTrue(os.path.isabs(body['procs_state_path']))
        table = json.loads(Path(body['procs_state_path']).read_text())
        self.assertEqual(table['pid'], f.proc.pid)
        self.assertIn('procs', table)

    def test_not_true_is_body_bad(self):
        f = self.fixture('state_path_bad').start()
        box = self.box(f)
        for value in (False, 'yes', 1, None):
            with self.subTest(value=value):
                body = self.ask(f, box, {'procs_state_path': value, 'procs_added': {'job': str(f.body('script', 'stop'))}})
                self.assertEqual(body['applied'], False)
                self.assertEqual(body['error']['code'], 'BodyBad')
                self.assertIn('procs_state_path must be true', body['error']['msg'])
                self.assertNotIn('procs_state_path', body)
        self.assertEqual(f.rows(), {})          # 壞信整封不套
        self.assertEqual(self.ask(f, box, {'ping': True}), {'applied': True})   # 沒問的信不帶路徑

    def test_together_with_procs_added_does_both(self):
        f = self.fixture('state_path_both').start()
        body = self.ask(f, self.box(f), {'procs_state_path': True, 'procs_added': {'job': str(f.body('script', 'stop'))}})
        self.assertEqual(body, {'applied': True, 'procs_state_path': str(f.stack / 'procs_state.json')})
        self.assertIn('job', read(body['procs_state_path'])['procs'])

    def test_window_closed_is_null(self):
        f = self.fixture('state_path_null', procs_state=None)
        f.log = open(f.root / 'daemon.log', 'a')
        f.err = open(f.root / 'daemon.err', 'a')
        f.proc = subprocess.Popen(['aos-daemon', '--enable-logs', str(f.config)], cwd=f.root,
                                  env=dict(ENV, AOS_STACK=str(f.stack)), stdout=f.log, stderr=f.err)
        until(lambda: read(f.stack / 'state_flux.json'))    # 沒有 procs_state 窗，Fixture.start 等不到它
        body = self.ask(f, self.box(f), {'procs_state_path': True})
        self.assertEqual(body, {'applied': True, 'procs_state_path': None})
        self.assertFalse((f.stack / 'procs_state.json').exists())


if __name__ == '__main__':
    unittest.main()
