# Check aos-json add / ls / search (the json tools' Python logic moved into C++, 11-12): output formats and error codes.
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

BIN = str(Path(__file__).resolve().parents[1] / 'bin' / 'aos-json')
BASE = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-json-als-')
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)

    def run_(self, *argv, stdin=None):
        return subprocess.run([BIN, *argv], env=BASE, cwd=self.d, input=stdin, capture_output=True, text=True, timeout=20)

    def ok(self, *argv):
        p = self.run_(*argv)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stderr, '')
        return p.stdout

    def err(self, code, *argv):
        p = self.run_(*argv)
        self.assertEqual(p.returncode, 1, p.stdout)
        self.assertIn('aos-json: error: %s ' % code, p.stderr)
        return p.stderr

    def put(self, name, text):
        (self.d / name).write_text(text)

    def text(self, name):
        return (self.d / name).read_text()

    def doc(self, name):
        return json.loads(self.text(name))


class Add(Base):
    def setUp(self):
        super().setUp()
        self.put('c.json', '{\n  "a": 1,\n  "list": [\n    "x",\n    "y",\n    "z"\n  ]\n}\n')

    def test_object_new_key(self):
        self.assertEqual(self.ok('add', 'c.json#/b', '2'), 'c.json#/b\n')
        self.assertEqual(list(self.doc('c.json')), ['a', 'list', 'b'])

    def test_object_key_exists(self):
        e = self.err('KeyExists', 'add', 'c.json#/a', '5')
        self.assertIn('c.json#/a already exists; use set to change it', e)
        e = self.err('KeyExists', 'add', 'c.json#/list', '5')
        self.assertIn('to add an item to that array write c.json#/list/-', e)
        self.assertEqual(self.doc('c.json')['a'], 1)

    def test_array_insert_middle_only_that_line(self):
        self.assertEqual(self.ok('add', 'c.json#/list/1', '"new"'), 'c.json#/list/1\n')
        self.assertEqual(self.text('c.json'), '{\n  "a": 1,\n  "list": [\n    "x",\n    "new",\n    "y",\n    "z"\n  ]\n}\n')

    def test_array_insert_front_one_line(self):
        self.put('f.json', '{"l": [1, 2], "z": 0}\n')
        self.assertEqual(self.ok('add', 'f.json#/l/0', '9'), 'f.json#/l/0\n')
        self.assertEqual(self.text('f.json'), '{"l": [9, 1, 2], "z": 0}\n')

    def test_array_tail_and_dash(self):
        self.assertEqual(self.ok('add', 'c.json#/list/3', '"t"'), 'c.json#/list/3\n')
        self.assertEqual(self.ok('add', 'c.json#/list/-', '"u"'), 'c.json#/list/4\n')
        self.assertEqual(self.doc('c.json')['list'], ['x', 'y', 'z', 't', 'u'])

    def test_array_out_of_range(self):
        for bad in ('4', '01', 'x'):
            e = self.err('PointerMissing', 'add', 'c.json#/list/' + bad, '1')
            self.assertIn('array has 3 items; insert at 0..3 or write /- to append', e)

    def test_dash_on_object(self):
        self.err('TargetBad', 'add', 'c.json#/-', '1')

    def test_whole_file(self):
        self.err('KeyExists', 'add', 'c.json', '{}')
        self.assertEqual(self.ok('add', 'n.json', '{"k": 1}'), 'n.json\n')
        self.assertEqual(self.doc('n.json'), {'k': 1})
        self.err('FileMissing', 'add', 'm.json#/k', '1')

    def test_parents(self):
        e = self.err('PointerMissing', 'add', 'c.json#/p/q/r', '1')
        self.assertIn('add --parents', e)
        self.assertEqual(self.ok('add', '--parents', 'c.json#/p/q/r', '1'), 'c.json#/p/q/r\n')
        self.assertEqual(self.doc('c.json')['p'], {'q': {'r': 1}})

    def test_raw_follow_and_stdin(self):
        self.put('r.json', '{"r": {"$ref": "lib.json"}}')
        self.put('lib.json', '{"x": 1}')
        self.err('FollowMissing', 'add', 'r.json#/r/k', '1')
        self.err('ArgumentsBad', 'add', '--raw', '--follow', 'r.json#/r/k', '1')
        self.assertEqual(self.ok('add', '--follow', 'r.json#/r/k', '2'), 'r.json#/r/k\n')
        self.assertEqual(self.doc('lib.json'), {'x': 1, 'k': 2})
        p = self.run_('add', '--raw', 'r.json#/r/k', stdin='3')
        self.assertEqual((p.returncode, p.stdout), (0, 'r.json#/r/k\n'), p.stderr)
        self.assertEqual(self.doc('r.json'), {'r': {'$ref': 'lib.json', 'k': 3}})


class Ls(Base):
    def setUp(self):
        super().setUp()
        self.put('c.json', json.dumps({'name': 'alice', 'max': 20, 'a/b~c': True, 'tags': ['x', 'yy', 'zzz'],
                                       'zh': '中文字', 'o': {'k': None}}, ensure_ascii=False))

    def test_short(self):
        self.assertEqual(self.ok('ls', 'c.json'), 'object, 6 keys\nname\nmax\na~1b~0c\ntags\nzh\no\n')
        self.assertEqual(self.ok('ls', 'c.json#/tags'), 'array, 3 items (index 0..2)\n0\n1\n2\n')

    def test_long(self):
        self.assertEqual(self.ok('ls', '--long', 'c.json'),
                         'object, 6 keys\nname\tstring\t5 chars\t7 bytes\nmax\tnumber\t20\na~1b~0c\tboolean\ttrue\n'
                         'tags\tarray\t3 items\t16 bytes\nzh\tstring\t3 chars\t11 bytes\no\tobject\t1 key\t10 bytes\n')

    def test_scalars(self):
        self.assertEqual(self.ok('ls', 'c.json#/name'), 'string, 5 chars\n')
        self.assertEqual(self.ok('ls', 'c.json#/max'), 'number 20\n')
        self.assertEqual(self.ok('ls', 'c.json#/o/k'), 'null null\n')
        self.assertEqual(self.ok('ls', 'c.json#/zh'), 'string, 3 chars\n')

    def test_offset_limit_more(self):
        self.assertEqual(self.ok('ls', 'c.json', '--limit', '2'), 'object, 6 keys\nname\nmax\n[more] 0 to 1 of 6 shown; next: --offset 2\n')
        self.assertEqual(self.ok('ls', 'c.json', '--offset', '2', '--limit', '2'),
                         'object, 6 keys\na~1b~0c\ntags\n[more] 2 to 3 of 6 shown; next: --offset 4\n')
        self.assertEqual(self.ok('ls', 'c.json', '--offset', '4', '--limit', '2'), 'object, 6 keys\nzh\no\n')
        self.assertEqual(self.ok('ls', 'c.json', '--offset', '5'), 'object, 6 keys\no\n')
        for bad in (('--offset', '-1'), ('--offset', 'x'), ('--limit', '0'), ('--limit', '1.5')):
            self.err('ArgumentsBad', 'ls', 'c.json', *bad)

    def test_missing(self):
        self.err('PointerMissing', 'ls', 'c.json#/nope')


class Search(Base):
    def setUp(self):
        super().setUp()
        self.put('c.json', json.dumps({'timeout': 5, 'states': {'think': {'next': 'act', 'timeout': 1},
                                                                'act': {'next': 'done', 'n': 1.0}},
                                       'list': [1, '1', True, {'next': 'x'}]}))

    def test_key_down_preorder(self):
        self.assertEqual(self.ok('search', '--key', 'next', 'c.json'),
                         'c.json#/states/think/next\tstring\t3 chars\t5 bytes\n'
                         'c.json#/states/act/next\tstring\t4 chars\t6 bytes\n'
                         'c.json#/list/3/next\tstring\t1 char\t3 bytes\n')
        self.assertEqual(self.ok('search', '--key', 'next', 'c.json#/states/act'), 'c.json#/states/act/next\tstring\t4 chars\t6 bytes\n')

    def test_value_types(self):
        self.assertEqual(self.ok('search', '--value', '1', 'c.json'),
                         'c.json#/states/think/timeout\tnumber\t1\nc.json#/states/act/n\tnumber\t1.0\nc.json#/list/0\tnumber\t1\n')
        self.assertEqual(self.ok('search', '--value', '"1"', 'c.json'), 'c.json#/list/1\tstring\t1 char\t3 bytes\n')
        self.assertEqual(self.ok('search', '--value', '{"next":"x"}', 'c.json'), 'c.json#/list/3\tobject\t1 key\t12 bytes\n')
        self.err('ValueBad', 'search', '--value', 'nope', 'c.json')
        self.err('ArgumentsBad', 'search', 'c.json')

    def test_contains(self):
        self.assertEqual(self.ok('search', '--contains', '--key', 'ex', '--value', '"on"', 'c.json'),
                         'c.json#/states/act/next\tstring\t4 chars\t6 bytes\n')
        self.assertEqual(self.ok('search', '--contains', '--value', '"ct"', 'c.json'), 'c.json#/states/think/next\tstring\t3 chars\t5 bytes\n')

    def test_up(self):
        self.assertEqual(self.ok('search', '--up', '--key', 'timeout', 'c.json#/states/think/next'),
                         'c.json#/states/think/timeout\tnumber\t1\nc.json#/timeout\tnumber\t5\n')
        self.err('ArgumentsBad', 'search', '--up', '--follow', '--key', 'timeout', 'c.json#/states')

    def test_no_match_and_more(self):
        self.assertEqual(self.ok('search', '--key', 'zzz', 'c.json'), '[no match]\n')
        self.assertEqual(self.ok('search', '--key', 'next', '--limit', '1', 'c.json'),
                         'c.json#/states/think/next\tstring\t3 chars\t5 bytes\n'
                         '[more] 0 to 0 of 3 shown; narrow the path or give a bigger --limit\n')

    def test_follow_ref(self):
        self.put('r.json', '{"r": {"$ref": "lib.json"}}')
        self.put('lib.json', '{"deep": {"want": 7}}')
        self.assertEqual(self.ok('search', '--key', 'want', 'r.json#/r'), '[no match]\n')
        self.assertEqual(self.ok('search', '--follow', '--key', 'want', 'r.json#/r/deep'), 'r.json#/r/deep/want\tnumber\t7\n')
        self.assertEqual(self.ok('search', '--resolve', '--key', 'want', 'r.json#/r'), 'r.json#/r/deep/want\tnumber\t7\n')


if __name__ == '__main__':
    unittest.main()
