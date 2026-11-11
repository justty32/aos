# Check aos-fsm creates a missing $AOS_STACK at start (11-11, make_stack), runs the state and writes stage.txt as usual.
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

BIN = Path(__file__).resolve().parents[1] / 'bin' / 'aos-fsm'
ENV = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}


class StackMake(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-fsm-stack-')
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(os.path.realpath(self.tmp.name))
        cell = self.d / 'cell'
        cell.write_text('#!/bin/sh\n# write one file into the stack\necho hi > "$AOS_STACK/out.txt"\n')
        cell.chmod(0o755)
        self.cfg = self.d / 'fsm.json'
        self.cfg.write_text(json.dumps({'start': 'a', 'states': {
            'a': {'exec': str(cell), 'next': 'b'}, 'b': {'exec': str(cell), 'next': 'a'}}}))

    def run_fsm(self, stack, cfg=None):
        return subprocess.run([str(BIN), str(cfg or self.cfg)], env=dict(ENV, AOS_STACK=stack), cwd=self.d,
                              capture_output=True, text=True, timeout=15)

    def test_missing_stack_is_created(self):
        st = self.d / 'a' / 'b'
        r = self.run_fsm(str(st) + '/')
        self.assertEqual((r.returncode, r.stderr), (0, ''))
        self.assertEqual((st / 'out.txt').read_text(), 'hi\n')
        self.assertEqual((st / 'stage.txt').read_text(), 'b\n')

    def test_cannot_create(self):
        (self.d / 'f').write_text('')
        r = self.run_fsm(str(self.d / 'f' / 'x'))
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr, r'^aos-fsm: error: MkdirFailed cannot create AOS_STACK: ')

    def test_bad_table_creates_nothing(self):
        bad = self.d / 'bad.json'
        bad.write_text(json.dumps({'start': 'a', 'states': {}}))
        r = self.run_fsm(str(self.d / 'st'), bad)
        self.assertEqual(r.returncode, 1)
        self.assertFalse((self.d / 'st').exists())


if __name__ == '__main__':
    unittest.main()
