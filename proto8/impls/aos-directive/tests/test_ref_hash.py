# Check {"$ref": "#/..."} takes the file that holds the $ref (11-12), and that ./ and ../ work in the file part of $ref.
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

BIN = Path(__file__).resolve().parents[1] / 'bin' / 'aos-directive'
ENV = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}


class RefHash(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-directive-hash-')
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(os.path.realpath(self.tmp.name))

    def put(self, name, doc):
        p = self.d / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc))
        return p

    def run_dir(self, doc, *flags, cwd=None):
        p = subprocess.run([str(BIN), *flags], input=json.dumps(doc), cwd=cwd or self.d, env=ENV,
                           capture_output=True, text=True, timeout=10)
        out = json.loads(p.stdout) if p.returncode == 0 else None
        return p.returncode, out, p.stderr.strip()

    def run_file(self, name, cwd=None):
        return self.run_dir(json.loads((self.d / name).read_text()), '--file', str(self.d / name), cwd=cwd)

    def test_top_level_with_file(self):
        self.put('m.json', {'defs': {'cmd': ['echo', 'hi']}, 'use': {'$ref': '#/defs/cmd'},
                            'one': {'$ref': '#/defs/cmd/0', '$path': 'x', '$prefix': '--p='}})
        code, out, _ = self.run_file('m.json')
        self.assertEqual(code, 0)
        self.assertEqual(out['use'], ['echo', 'hi'])
        self.assertEqual(out['one'], '--p=echo/x')

    def test_top_level_without_file_is_left_as_is(self):
        doc = {'a': {'$ref': '#/b'}, 'b': 1, 'arr': {'$ref': ['#/b', 'x.json']}}
        code, out, _ = self.run_dir(doc)
        self.assertEqual(code, 0)
        self.assertEqual(out, doc)

    def test_inside_a_reffed_file_means_that_file(self):
        self.put('sub/inc.json', {'mine': {'$ref': '#/local'}, 'local': 'inc', 'deep': {'x': {'$ref': '#/local'}}})
        self.put('m.json', {'local': 'outer', 'inc': {'$ref': 'sub/inc.json'}})
        code, out, _ = self.run_file('m.json')
        self.assertEqual(code, 0)
        self.assertEqual(out['inc'], {'mine': 'inc', 'local': 'inc', 'deep': {'x': 'inc'}})
        code, out, _ = self.run_dir({'$ref': 'sub/inc.json#/deep'})   # pointer into it: #/ still means inc.json
        self.assertEqual((code, out), (0, {'x': 'inc'}))

    def test_taken_value_is_raw_then_resolved(self):
        self.put('m.json', {'a': {'$ref': '#/b'}, 'b': {'$ref': '#/c'}, 'c': 3})
        code, out, _ = self.run_file('m.json')
        self.assertEqual((code, out), (0, {'a': 3, 'b': 3, 'c': 3}))

    def test_array_merges_parts_of_itself(self):
        self.put('m.json', {'p': {'x': 1, 'y': 1}, 'q': {'y': 2}, 'l': [1], 'm': {'$ref': ['#/p', '#/q']},
                            'n': {'$ref': ['#/l', 'o.json#/k']}})
        self.put('o.json', {'k': [2]})
        code, out, _ = self.run_file('m.json')
        self.assertEqual(code, 0)
        self.assertEqual(out['m'], {'x': 1, 'y': 2})
        self.assertEqual(out['n'], [1, 2])

    def test_loop_to_ancestor_and_mutual(self):
        self.put('a.json', {'a': {'b': {'$ref': '#/a'}}})
        code, _, err = self.run_file('a.json')
        self.assertEqual(code, 1)
        self.assertIn('DirectiveBad $ref loop:', err)
        self.put('b.json', {'x': {'$ref': '#/y'}, 'y': {'$ref': '#/x'}})
        code, _, err = self.run_file('b.json')
        self.assertEqual(code, 1)
        self.assertIn('DirectiveBad $ref loop:', err)

    def test_pointer_not_found(self):
        self.put('m.json', {'x': {'$ref': '#/nope'}})
        code, _, err = self.run_file('m.json')
        self.assertEqual(code, 1)
        self.assertIn('DirectiveBad $ref pointer not found: %s#/nope' % (self.d / 'm.json'), err)

    def test_hash_alone_is_the_whole_file_and_not_slash_is_an_error(self):
        self.put('x.json', {'k': 1})
        self.put('m.json', {'a': {'$ref': 'x.json#'}, 'b': {'$ref': 'x.json#/'}})
        code, out, _ = self.run_file('m.json')
        self.assertEqual((code, out), (0, {'a': {'k': 1}, 'b': {'k': 1}}))
        for text in ('#', ['#/c', '#']):                  # this whole file, from inside it: a loop
            self.put('m.json', {'c': {'$ref': text}})
            code, _, err = self.run_file('m.json')
            self.assertEqual(code, 1)
            self.assertIn('DirectiveBad $ref loop', err)
        self.put('m.json', {'b': {'$ref': '#a'}})
        code, _, err = self.run_file('m.json')
        self.assertEqual(code, 1)
        self.assertIn('DirectiveBad $ref #a: after # write /, ./ or ../', err)

    def test_dot_and_dotdot_in_file_part(self):
        self.put('sub/leaf.json', 'leaf')
        self.put('other/o.json', {'k': 'o'})
        self.put('sub/inc.json', {'up': {'$ref': '../other/o.json#/k'}, 'here': {'$ref': './leaf.json'}})
        code, out, _ = self.run_dir({'a': {'$ref': './sub/leaf.json'}, 'b': {'$ref': 'sub/../other/o.json#/k'},
                                     'c': {'$ref': 'sub/inc.json'}})
        self.assertEqual(code, 0)
        self.assertEqual(out, {'a': 'leaf', 'b': 'o', 'c': {'up': 'o', 'here': 'leaf'}})
        code, out, _ = self.run_dir({'$ref': '../other/o.json'}, cwd=self.d / 'sub')
        self.assertEqual((code, out), (0, {'k': 'o'}))


if __name__ == '__main__':
    unittest.main()
