# Check {"$ref": "#/..."} in fsm.json (a whole state, an inline exec inst) takes fsm.json itself (11-12).
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

BIN = Path(__file__).resolve().parents[1] / 'bin' / 'aos-fsm'
ENV = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}


class RefHash(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-fsm-hash-')
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(os.path.realpath(self.tmp.name))

    def test_state_and_inline_inst(self):
        out = self.d / 'out.txt'
        (self.d / 'fsm.json').write_text(json.dumps({
            'cells': {'a': {'exec': {'argv': ['sh', '-c', 'echo a >> "%s"' % out]}, 'next': 'b'}},
            'argvs': {'b': ['sh', '-c', 'echo b >> "%s"' % out]},
            'start': 'a',
            'states': {'a': {'$ref': '#/cells/a'}, 'b': {'exec': {'argv': {'$ref': '#/argvs/b'}}, 'next': 'a'}}}))
        for _ in range(3):
            p = subprocess.run([str(BIN), 'fsm.json'], cwd=self.d, env=dict(ENV, AOS_STACK=str(self.d / 'st') + '/'),
                               capture_output=True, text=True, timeout=15)
            self.assertEqual((p.returncode, p.stderr), (0, ''))
        self.assertEqual(out.read_text().split(), ['a', 'b', 'a'])


if __name__ == '__main__':
    unittest.main()
