# Check {"$ref": "#/..."} in loop.json (a config key, the inline exec inst, ctl) takes the file that holds it (11-12).
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

BIN = Path(__file__).resolve().parents[1] / 'bin' / 'aos-loop'
ENV = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}


class RefHash(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-loop-hash-')
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(os.path.realpath(self.tmp.name))
        self.out = self.d / 'out.txt'

    def run_loop(self, spec):
        p = subprocess.run([str(BIN), spec], cwd=self.d, env=dict(ENV, AOS_STACK=str(self.d / 'st') + '/'),
                           capture_output=True, text=True, timeout=15)
        return p.returncode, p.stderr.strip()

    def test_config_keys_and_inline_inst(self):
        (self.d / 'loop.json').write_text(json.dumps({
            'defs': {'argv': ['sh', '-c', 'echo body >> "%s"' % self.out], 'max': 2},
            'exec': {'argv': {'$ref': '#/defs/argv'}}, 'max': {'$ref': '#/defs/max'},
            'ctl': None, 'state': None, 'state_flux': None}))
        self.assertEqual(self.run_loop('loop.json'), (0, ''))
        self.assertEqual(self.out.read_text().split(), ['body', 'body'])

    def test_config_at_pointer_counts_from_file_root(self):
        (self.d / 'big.json').write_text(json.dumps({
            'argv': ['sh', '-c', 'echo deep >> "%s"' % self.out],
            'loops': {'a': {'exec': {'argv': {'$ref': '#/argv'}}, 'max': 1, 'ctl': None, 'state': None, 'state_flux': None}}}))
        self.assertEqual(self.run_loop('big.json#/loops/a'), (0, ''))
        self.assertEqual(self.out.read_text().split(), ['deep'])


if __name__ == '__main__':
    unittest.main()
