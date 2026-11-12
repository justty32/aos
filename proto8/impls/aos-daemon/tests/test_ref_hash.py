# Check {"$ref": "#/..."} in daemon.json means daemon.json itself, also inside an inline inst moved into its cell (11-12).
import json
from pathlib import Path
import unittest

from support import Fixture, read, until, write


class RefHash(unittest.TestCase):
    def setUp(self):
        self.f = Fixture('ref-hash-%s' % self._testMethodName)
        self.addCleanup(self.f.close)

    def test_inline_inst_and_row_take_daemon_json(self):
        out = self.f.root / 'out.txt'
        write(self.f.config, {
            'interval_ms': 20,
            'defs': {'argv': ['sh', '-c', 'echo "$0" >> "%s"; sleep 30' % out, 'from-defs'],
                     'row': {'exec': {'argv': ['sh', '-c', 'echo row >> "%s"; sleep 30' % out]}}},
            'procs': {'job': {'exec': {'argv': {'$ref': '#/defs/argv'}}}, 'two': {'$ref': '#/defs/row'}}})
        self.f.start()
        until(lambda: out.exists() and sorted(out.read_text().split()) == ['from-defs', 'row'])
        rows = read(self.f.stack / 'procs_state.json')['procs']
        self.assertEqual(rows['job']['phase'], 'running')
        self.assertEqual(rows['two']['phase'], 'running')
        # the inline inst written into the cell keeps pointing at daemon.json, not at the cell file
        cell = json.dumps([read(p) for p in Path(self.f.stack / 'procs' / 'job').rglob('*.json')])
        self.assertNotIn('"#/defs/argv"', cell)
        self.assertIn('daemon.json#/defs/argv"', cell)


if __name__ == '__main__':
    unittest.main()
