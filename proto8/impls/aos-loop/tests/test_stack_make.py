# Check aos-loop creates a missing $AOS_STACK at start (11-11, make_stack) and writes there as usual.
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

BIN = Path(__file__).resolve().parents[1] / 'bin' / 'aos-loop'
ENV = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}


class StackMake(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-loop-stack-')
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(os.path.realpath(self.tmp.name))
        body = self.d / 'body'
        body.write_text('#!/bin/sh\n# write one file into the stack, then stop\necho hi > "$AOS_STACK/out.txt"\nexit 10\n')
        body.chmod(0o755)

    def run_loop(self, stack, cfg=None):
        p = self.d / 'loop.json'
        p.write_text(json.dumps(dict({'exec': str(self.d / 'body')}, **(cfg or {}))))
        return subprocess.run([str(BIN), str(p)], env=dict(ENV, AOS_STACK=stack), cwd=self.d,
                              capture_output=True, text=True, timeout=15)

    def test_missing_stack_is_created(self):
        st = self.d / 'a' / 'b'
        r = self.run_loop(str(st) + '/')
        self.assertEqual((r.returncode, r.stderr), (0, ''))
        self.assertEqual((st / 'out.txt').read_text(), 'hi\n')
        self.assertEqual(json.loads((st / 'state.json').read_text())['phase'], 'done')
        self.assertTrue((st / 'state_flux.json').is_file())

    def test_relative_stack_from_cwd(self):
        r = self.run_loop('rel/st', {'ctl': None, 'state': None, 'state_flux': None})
        self.assertEqual((r.returncode, r.stderr), (0, ''))
        self.assertEqual((self.d / 'rel' / 'st' / 'out.txt').read_text(), 'hi\n')

    def test_cannot_create(self):
        (self.d / 'f').write_text('')
        r = self.run_loop(str(self.d / 'f' / 'x'))
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr, r'^aos-loop: error: MkdirFailed cannot create AOS_STACK: ')

    def test_bad_config_creates_nothing(self):
        r = self.run_loop(str(self.d / 'st'), {'max': -1})
        self.assertEqual(r.returncode, 1)
        self.assertIn('CfgBad', r.stderr)
        self.assertFalse((self.d / 'st').exists())


if __name__ == '__main__':
    unittest.main()
