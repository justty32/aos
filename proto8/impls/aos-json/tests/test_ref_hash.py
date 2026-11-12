# Check aos-json's own $ref walk takes "#/..." (no file name) = the file that holds the $ref (ref-hash, 11-12 night), same as aos-directive.
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

BIN = str(Path(__file__).resolve().parents[1] / 'bin' / 'aos-json')
BASE = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}


class RefHash(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-json-refhash-')
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)
        (self.d / 'sub').mkdir()
        self.put('main.json', {'defs': {'cmd': ['echo', 'hi']}, 'use': {'$ref': '#/defs/cmd'},
                               'inc': {'$ref': 'sub/inc.json'}, 'x': {'$ref': 'sub/inc.json#/mine'}})
        self.put('sub/inc.json', {'local': 'L', 'mine': {'$ref': '#/local'}, 'up': {'$ref': '../other.json#/v'},
                                  'dot': {'$ref': './leaf.json'}})
        self.put('other.json', {'v': 'from-other'})
        self.put('sub/leaf.json', 'leaf')
        self.put('loop.json', {'a': {'$ref': '#/b'}, 'b': {'$ref': '#/a'}})
        self.put('nowhere.json', {'a': {'$ref': '#/nope'}})

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

    def err(self, code, *argv):
        p = self.run_(*argv)
        self.assertEqual(p.returncode, 1, p.stdout)
        self.assertIn('aos-json: error: %s ' % code, p.stderr)

    def test_get_follow_and_raw(self):
        self.assertEqual(self.ok('get', '--follow', 'main.json#/use/0'), '"echo"\n')
        self.assertEqual(json.loads(self.ok('get', 'main.json#/use')), {'$ref': '#/defs/cmd'})   # no flags = as written
        self.assertEqual(self.ok('where', 'main.json#/use'), 'main.json#/use\nmain.json#/defs/cmd\n')

    def test_resolve(self):
        self.assertEqual(json.loads(self.ok('get', '--resolve', 'main.json#/use')), ['echo', 'hi'])
        whole = json.loads(self.ok('get', '--resolve', 'main.json'))
        self.assertEqual((whole['use'], whole['inc']['mine'], whole['x']), (['echo', 'hi'], 'L', 'L'))

    def test_hash_inside_a_file_brought_in(self):
        # sub/inc.json's "#/local" means sub/inc.json, not main.json
        self.assertEqual(self.ok('get', '--follow', '--resolve', 'main.json#/inc/mine'), '"L"\n')
        self.assertEqual(self.ok('where', 'main.json#/inc/mine'), 'main.json#/inc\nsub/inc.json#/mine\nsub/inc.json#/local\n')

    def test_cycle_and_nowhere(self):
        self.err('DirectiveBad', 'where', 'loop.json#/a')
        self.err('DirectiveBad', 'get', '--resolve', 'loop.json#/a')
        self.err('DirectiveBad', 'where', 'nowhere.json#/a')
        self.err('DirectiveBad', 'get', '--resolve', 'nowhere.json#/a')
        self.assertEqual(self.run_('check', 'loop.json').returncode, 10)
        self.assertEqual(self.run_('check', 'main.json').returncode, 0)

    def test_hash_alone_still_not_a_ref(self):
        self.put('bad.json', {'r': {'$ref': '#'}, 's': {'$ref': '#x'}})
        self.err('PointerMissing', 'get', '--follow', 'bad.json#/r/k')
        self.assertIn('DirectiveFormBad', self.run_('check', 'bad.json').stdout)

    def test_writes_follow_into_same_file(self):
        self.ok('set', '--follow', 'main.json#/use/1', '"yo"')
        self.assertEqual(self.ok('add', '--follow', 'main.json#/use/-', '"z"'), 'main.json#/use/2\n')
        self.ok('del', '--follow', 'main.json#/use/0')
        d = self.doc('main.json')
        self.assertEqual((d['defs']['cmd'], d['use']), (['yo', 'z'], {'$ref': '#/defs/cmd'}))

    def test_ls_search_follow(self):
        self.assertEqual(self.ok('ls', '--follow', 'main.json#/use/0'), 'string, 4 chars\n')
        self.assertEqual(self.ok('ls', '--resolve', 'main.json#/use'), 'array, 2 items (index 0..1)\n0\n1\n')
        self.assertEqual(self.ok('search', '--resolve', '--value', '"L"', 'main.json#/inc'),
                         'main.json#/inc/local\tstring\t1 char\t3 bytes\nmain.json#/inc/mine\tstring\t1 char\t3 bytes\n')

    def test_dot_and_dotdot(self):
        self.assertEqual(self.ok('where', 'main.json#/inc/up'), 'main.json#/inc\nsub/inc.json#/up\nother.json#/v\n')
        inc = json.loads(self.ok('get', '--resolve', 'main.json#/inc'))
        self.assertEqual((inc['up'], inc['dot']), ('from-other', 'leaf'))
        self.ok('set', '--follow', 'main.json#/inc/local', '"L2"')
        self.assertEqual(self.doc('sub/inc.json')['local'], 'L2')

    def test_ref_move_keeps_hash_pointing_home(self):
        self.put('m.json', {'a': {'x': {'$ref': '#/b'}}, 'b': 1})
        self.ok('ref', '--move', 'm.json#/a', 'sub/moved.json')
        self.assertEqual(self.doc('sub/moved.json'), {'x': {'$ref': '../m.json#/b'}})
        self.assertEqual(json.loads(self.ok('get', '--resolve', 'm.json#/a')), {'x': 1})
        self.put('n.json', {'a': {'x': {'$ref': '#/b'}}, 'b': 1, 'keep': {}})
        self.ok('ref', '--move', 'n.json#/a', '#/keep/a')                  # into the same file: left as written
        self.assertEqual(self.doc('n.json')['keep']['a'], {'x': {'$ref': '#/b'}})
        self.assertEqual(json.loads(self.ok('get', '--resolve', 'n.json#/a')), {'x': 1})


if __name__ == '__main__':
    unittest.main()
