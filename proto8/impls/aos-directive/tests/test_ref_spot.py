# Check the "string -> place" rule of $ref: after # a ".." steps out one level, and stepping out of the root object lands in
# the folder of the file ("#/../other.json", "#/../other.json#/k"). The table ref_spot_cases.json is shared with
# lib/tests/test_index_link.py (index paths use the same rule).
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
BIN = HERE.parent / 'bin' / 'aos-directive'
ENV = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}
CASES = json.loads((HERE / 'ref_spot_cases.json').read_text())


def nest(toks, leaf):
    for t in reversed(toks):
        leaf = {t.replace('~1', '/').replace('~0', '~'): leaf}
    return leaf


class RefSpot(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-directive-spot-')
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(os.path.realpath(self.tmp.name)) / 'w'
        self.d.mkdir()

    def put(self, name, doc):
        p = self.d / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc))
        return p

    def run_file(self, name, *more):
        flags = ['--file', str(self.d / name)] if name else []
        p = subprocess.run([str(BIN), *flags, *more], input=(self.d / (name or 'm.json')).read_text(), cwd=self.d, env=ENV,
                           capture_output=True, text=True, timeout=10)
        return p.returncode, json.loads(p.stdout) if p.returncode == 0 else None, p.stderr.strip()

    def test_shared_table(self):
        for n, c in enumerate(CASES):
            with self.subTest(text=c['text']):
                root = self.d / str(n)
                at = root / c['at']
                doc = {'r': {'$ref': c['text']}}
                if c['to'] is not None:
                    f, _, ptr = c['to'].partition('#')
                    hit = nest(ptr.split('/')[1:], 'HIT')
                    if root / f == at:
                        doc.update(hit)
                    else:
                        (root / f).parent.mkdir(parents=True, exist_ok=True)
                        (root / f).write_text(json.dumps(hit))
                at.parent.mkdir(parents=True, exist_ok=True)
                at.write_text(json.dumps(doc))
                p = subprocess.run([str(BIN), '--file', str(at)], input=at.read_text(), cwd=self.d, env=ENV,
                                   capture_output=True, text=True, timeout=10)
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertEqual(json.loads(p.stdout)['r'], doc['r'] if c['to'] is None else 'HIT')

    def test_without_file_is_left_as_is(self):
        self.put('other.json', {'k': 1})
        self.put('m.json', {'a': {'$ref': '#/../other.json'}, 'b': {'$ref': ['other.json', '#/../other.json#/k']}})
        code, out, _ = self.run_file(None)
        self.assertEqual(code, 0)
        self.assertEqual(out, {'a': {'$ref': '#/../other.json'}, 'b': {'$ref': ['other.json', '#/../other.json#/k']}})

    def test_inside_a_reffed_file_means_that_file(self):
        self.put('sub/inc.json', {'side': {'$ref': '#/../side.json#/v'}, 'up': {'$ref': '#/../../top.json'}})
        self.put('sub/side.json', {'v': 'sub-side'})
        self.put('side.json', {'v': 'outer-side'})
        self.put('top.json', 'top')
        self.put('m.json', {'inc': {'$ref': 'sub/inc.json'}, 'part': {'$ref': '#/../sub/inc.json#/side'}})
        code, out, _ = self.run_file('m.json')
        self.assertEqual((code, out), (0, {'inc': {'side': 'sub-side', 'up': 'top'}, 'part': 'sub-side'}))

    def test_array_argv_and_modifiers(self):
        self.put('o.json', {'p': {'y': 2}, 'cmd': ['echo', 'hi'], 'dir': 'bin'})
        self.put('m.json', {'p': {'x': 1}, 'm': {'$ref': ['#/p', '#/../o.json#/p']},
                            'argv': [{'$ref': '#/../o.json#/cmd/0'}, {'$ref': '#/../o.json#/dir', '$path': 'x', '$prefix': '--d='}]})
        code, out, _ = self.run_file('m.json')
        self.assertEqual(code, 0)
        self.assertEqual(out['m'], {'x': 1, 'y': 2})
        self.assertEqual(out['argv'], ['echo', '--d=bin/x'])

    def test_at_walks_on_from_where_ref_points(self):
        self.put('x.json', {'a': {'b': {'c': 'abc'}, 'k/1': {'~': 'esc'}}, 'top': 'x-top'})
        self.put('other.json', {'k': 'other-k'})
        self.put('m.json', {
            'defs': {'argv': ['echo', 'hi'], 'd': 'bin'},
            'r1': {'$ref': 'x.json', '$at': 'a/b'},
            'r2': {'$ref': 'x.json#/a', '$at': 'b/c'},
            'r3': {'$ref': '#/defs', '$at': 'argv'},
            'r4': {'$ref': '#/../other.json', '$at': 'k'},
            'r5': {'$ref': 'x.json', '$at': '/a/./b//c'},                  # leading /, empty and . segments are skipped
            'r6': {'$ref': 'x.json#/a/b', '$at': '../../top'},             # .. steps out one level
            'r7': {'$ref': 'x.json#/a', '$at': '../../other.json'},        # out of the root object: the folder, then a file
            'r8': {'$ref': 'x.json', '$at': 'a/k~11/~0'},
            'r9': {'$ref': 'x.json', '$at': ''},
            'r10': {'$ref': 'x.json#/top', '$at': None},
            'r11': {'$ref': ['x.json#/a', '#/defs'], '$at': 'b'},          # array: each part walks on, then they merge
            'argv': [{'$ref': '#/defs', '$at': 'argv/0'}, {'$ref': '#/defs', '$at': 'd', '$path': 'x', '$prefix': '--d='}]})
        self.put('defs_b.json', {})
        doc = __import__('json').loads((self.d / 'm.json').read_text())
        doc['defs']['b'] = {'z': 1}
        self.put('m.json', doc)
        code, out, err = self.run_file('m.json')
        self.assertEqual(code, 0, err)
        self.assertEqual(out['r1'], {'c': 'abc'})
        self.assertEqual(out['r2'], 'abc')
        self.assertEqual(out['r3'], ['echo', 'hi'])
        self.assertEqual(out['r4'], 'other-k')
        self.assertEqual(out['r5'], 'abc')
        self.assertEqual(out['r6'], 'x-top')
        self.assertEqual(out['r7'], {'k': 'other-k'})
        self.assertEqual(out['r8'], 'esc')
        self.assertEqual(out['r9']['top'], 'x-top')
        self.assertEqual(out['r10'], 'x-top')
        self.assertEqual(out['r11'], {'c': 'abc', 'z': 1})
        self.assertEqual(out['argv'], ['echo', '--d=bin/x'])

    def test_at_malformed_or_alone_is_left_as_is(self):
        self.put('x.json', {'a': 1})
        doc = {'h': {'$ref': 'x.json', '$at': '#/a'}, 'h2': {'$ref': 'x.json', '$at': 'a#b'}, 'n': {'$ref': 'x.json', '$at': 3},
               'alone': {'$at': 'a'}, 'arr': {'$ref': ['x.json'], '$at': ['a']}}
        self.put('m.json', doc)
        code, out, _ = self.run_file('m.json')
        self.assertEqual((code, out), (0, doc))

    def test_at_errors(self):
        self.put('x.json', {'a': 1})
        self.put('m.json', {'r': {'$ref': 'x.json', '$at': 'nope'}})
        code, _, err = self.run_file('m.json')
        self.assertEqual(code, 1)
        self.assertIn('DirectiveBad $ref pointer not found', err)
        self.put('m.json', {'r': {'$ref': '#/r', '$at': 'x/..'}})           # back onto itself
        code, _, err = self.run_file('m.json')
        self.assertEqual(code, 1)
        self.assertIn('DirectiveBad $ref loop:', err)
        self.put('m.json', {'r': {'$ref': 'x.json', '$at': '..'}})          # a folder
        code, _, err = self.run_file('m.json')
        self.assertEqual(code, 1)
        self.assertIn('DirectiveBad $ref cannot read', err)

    def test_loop_through_the_folder(self):
        self.put('m.json', {'r': {'$ref': '#/../m.json#/x/../r'}})
        code, _, err = self.run_file('m.json')
        self.assertEqual(code, 1)
        self.assertIn('DirectiveBad $ref loop:', err)
        self.put('a.json', {'x': {'$ref': '#/../b.json#/y'}})
        self.put('b.json', {'y': {'$ref': '#/../a.json#/x'}})
        code, _, err = self.run_file('a.json')
        self.assertEqual(code, 1)
        self.assertIn('DirectiveBad $ref loop:', err)

    def test_folder_missing_and_pointer_errors(self):
        self.put('sub/x.json', {})
        for text, want in (('#/..', 'DirectiveBad $ref cannot read'), ('#/../sub', 'DirectiveBad $ref cannot read'),
                           ('#/../nope.json', 'DirectiveBad $ref cannot read'),
                           ('#/../sub/x.json#/k', 'DirectiveBad $ref pointer not found')):
            self.put('m.json', {'r': {'$ref': text}})
            code, _, err = self.run_file('m.json')
            self.assertEqual(code, 1, text)
            self.assertIn(want, err)


if __name__ == '__main__':
    unittest.main()
