# Run the get/missing cases of tests/data/md_path_cases.json (copied from proto8 py/tests) through {"$ref": "x.md#/..."} in build/bin/resolve-check.
# Adapted from proto8 aos-json tests/test_md_cases.py: the ls and tree cases are dropped (md_ls / md_tree were not brought in),
# and a miss is only checked to be DirectiveBad (the exact reason text came from proto8's Python mdpath, which is not here).
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from common import CHECK, DATA, ENV

TABLE = json.loads((DATA / 'md_path_cases.json').read_text(encoding='utf-8'))


class MdCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='aos-exec-md-cases-')
        cls.d = Path(os.path.realpath(cls.tmp.name))
        for name, text in TABLE['docs'].items():
            (cls.d / (name + '.md')).write_bytes(text.encode('utf-8'))   # as is: no newline translation (crlf doc)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def get(self, spec):
        p = subprocess.run([CHECK], input=json.dumps({'v': {'$ref': spec}}), env=ENV, cwd=self.d,
                           capture_output=True, text=True, timeout=20)
        return p.returncode, (json.loads(p.stdout)['v'] if p.returncode == 0 else None), p.stderr.strip()

    def test_cases(self):
        self.assertGreater(len(TABLE['cases']), 50)
        for c in TABLE['cases']:
            spec = c['doc'] + '.md' + ('#' + c['ptr'] if c['ptr'] else '')
            with self.subTest(rule=c['rule'], ptr=c['ptr']):
                code, got, err = self.get(spec)
                if c.get('missing'):
                    self.assertEqual(code, 1)
                    self.assertIn('resolve-check: error: DirectiveBad $ref pointer not found: ', err)
                else:
                    self.assertEqual(code, 0, err)
                    self.assertEqual(got, c['get'])
                    self.assertIs(type(got), type(c['get']))


if __name__ == '__main__':
    unittest.main()
