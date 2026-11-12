# Check aos-json's own $ref walk follows the same "string -> place" rule as aos-directive: ".." after # steps out
# (out of the root object = the folder of the file), and "$at" walks on from where $ref points.
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

BIN = str(Path(__file__).resolve().parents[1] / 'bin' / 'aos-json')
BASE = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}


class RefAt(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-json-refat-')
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)
        self.put('main.json', {'defs': {'cmd': {'argv': ['echo', 'hi']}},
                               'side': {'$ref': '#/../other.json'},
                               'deep': {'$ref': '#/../other.json#/a'},
                               'at1': {'$ref': 'other.json', '$at': 'a'},
                               'at2': {'$ref': '#/defs', '$at': 'cmd'},
                               'at3': {'$ref': '#/../other.json', '$at': 'a/b'},
                               'bad': {'$ref': 'other.json', '$at': '#/a'}})
        self.put('other.json', {'a': {'b': {'c': 1}}})

    def put(self, name, doc):
        (self.d / name).write_text(json.dumps(doc))

    def doc(self, name):
        return json.loads((self.d / name).read_text())

    def run_(self, *argv):
        return subprocess.run([BIN, *argv], env=BASE, cwd=self.d, capture_output=True, text=True, timeout=20)

    def ok(self, *argv):
        p = self.run_(*argv)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def test_get_follow_goes_through(self):
        self.assertEqual(json.loads(self.ok('get', '--follow', 'main.json#/side/a/b/c')), 1)
        self.assertEqual(json.loads(self.ok('get', '--follow', 'main.json#/deep/b/c')), 1)
        self.assertEqual(json.loads(self.ok('get', '--follow', 'main.json#/at1/b/c')), 1)
        self.assertEqual(json.loads(self.ok('get', '--follow', 'main.json#/at2/argv/0')), 'echo')
        self.assertEqual(json.loads(self.ok('get', '--follow', 'main.json#/at3/c')), 1)

    def test_resolve_matches_aos_directive(self):
        out = json.loads(self.ok('get', '--resolve', 'main.json'))
        self.assertEqual(out['side'], {'a': {'b': {'c': 1}}})
        self.assertEqual(out['at1'], {'b': {'c': 1}})
        self.assertEqual(out['at2'], {'argv': ['echo', 'hi']})
        self.assertEqual(out['at3'], {'c': 1})
        self.assertEqual(out['bad'], {'$ref': 'other.json', '$at': '#/a'})   # $at with # = malformed, left as it is

    def test_set_follow_writes_the_reffed_file(self):
        self.ok('set', '--follow', 'main.json#/at3/c', '2')
        self.assertEqual(self.doc('other.json'), {'a': {'b': {'c': 2}}})
        self.ok('set', '--follow', 'main.json#/at2/argv/1', '"yo"')
        self.assertEqual(self.doc('main.json')['defs']['cmd']['argv'], ['echo', 'yo'])

    def test_check_reports_malformed_at(self):
        p = self.run_('check', 'main.json')
        self.assertIn('DirectiveFormBad', p.stdout + p.stderr)
        self.assertIn('/bad', p.stdout + p.stderr)


if __name__ == '__main__':
    unittest.main()
