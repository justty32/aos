# Check aos-json's own $ref walk follows the same path rule as aos-directive (11-13 ref-path-rules): "#./" counts from the
# object the $ref is in, "#../" one level up; ref --move keeps them pointing at the same place.
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

BIN = str(Path(__file__).resolve().parents[1] / 'bin' / 'aos-json')
BASE = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}


class RefRel(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-json-refrel-')
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)
        self.put('main.json', {'defs': {'cmd': {'argv': ['echo', 'hi']}},
                               'g': {'here': {'k': 'v'}, 'dot': {'$ref': '#./here'}, 'up': {'$ref': '#../defs/cmd'}},
                               'side': {'$ref': 'other.json#/a'},
                               'bad': {'$ref': 'other.json#./a'}})
        self.put('other.json', {'a': {'b': {'c': 1}, 'sib': {'$ref': '#./b'}}})

    def put(self, name, doc):
        (self.d / name).parent.mkdir(parents=True, exist_ok=True)
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
        self.assertEqual(json.loads(self.ok('get', '--follow', 'main.json#/g/dot/k')), 'v')
        self.assertEqual(json.loads(self.ok('get', '--follow', 'main.json#/g/up/argv/0')), 'echo')
        self.assertEqual(json.loads(self.ok('get', '--follow', 'main.json#/side/sib/c')), 1)   # counted from its place in other.json
        self.assertEqual(self.ok('where', 'main.json#/side/sib'), 'main.json#/side\nother.json#/a/sib\nother.json#/a/b\n')

    def test_resolve_matches_aos_directive(self):
        out = json.loads(self.ok('get', '--resolve', 'main.json#/g'))
        self.assertEqual(out, {'here': {'k': 'v'}, 'dot': {'k': 'v'}, 'up': {'argv': ['echo', 'hi']}})
        self.assertEqual(json.loads(self.ok('get', '--resolve', 'main.json#/g/dot')), {'k': 'v'})   # a piece still knows where it is

    def test_set_follow_writes_where_it_points(self):
        self.ok('set', '--follow', 'main.json#/g/up/argv/1', '"yo"')
        self.assertEqual(self.doc('main.json')['defs']['cmd']['argv'], ['echo', 'yo'])

    def test_check_reports_bad_paths(self):
        p = self.run_('check', 'main.json')
        self.assertIn('DirectiveBad', p.stdout + p.stderr)
        self.assertIn('/bad', p.stdout + p.stderr)

    def test_ref_move_keeps_relative_refs(self):
        self.put('m.json', {'a': {'in': {'$ref': '#./v'}, 'v': 1, 'out': {'$ref': '#../b'}}, 'b': 2, 'keep': {}})
        (self.d / 'sub').mkdir()
        self.ok('ref', '--move', 'm.json#/a', 'sub/moved.json')
        self.assertEqual(self.doc('sub/moved.json'), {'in': {'$ref': '#./v'}, 'v': 1, 'out': {'$ref': '../m.json#/b'}})
        self.assertEqual(json.loads(self.ok('get', '--resolve', 'm.json#/a')), {'in': 1, 'v': 1, 'out': 2})
        self.put('n.json', {'a': {'in': {'$ref': '#./v'}, 'v': 1, 'out': {'$ref': '#../b'}}, 'b': 2, 'keep': {}})
        self.ok('ref', '--move', 'n.json#/a', '#./keep/a')                   # into the same file, written from where a was
        self.assertEqual(self.doc('n.json')['keep']['a'], {'in': {'$ref': '#./v'}, 'v': 1, 'out': {'$ref': '#/b'}})
        self.assertEqual(self.doc('n.json')['a'], {'$ref': '#./keep/a'})
        self.assertEqual(json.loads(self.ok('get', '--resolve', 'n.json#/a')), {'in': 1, 'v': 1, 'out': 2})


if __name__ == '__main__':
    unittest.main()
