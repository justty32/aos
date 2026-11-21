# Check aos-json reads .md files and never writes them: --follow/--resolve through a $ref to md, where, check, get --str, ls --long, peek, search, and every write refused.
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

BIN = str(Path(__file__).resolve().parents[3] / 'bin' / 'aos-json')
BASE = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}

PAGE = ('Intro.\n\n# Who am I\n\nYou are one proc.\n\n## Files\n\n- body.json: your body\n- plain\n\n'
        '# cfg\n\n```json\n{"a": [1, true], "r": {"$ref": "gone.json"}}\n```\n')
REFUSED = 'aos-json: error: TargetBad page.md is markdown: the json tools only read it; change it with a file tool (edit, write)\n'


class MdTools(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-json-md-tools-')
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(os.path.realpath(self.tmp.name))
        (self.d / 'page.md').write_text(PAGE, encoding='utf-8')
        self.put('main.json', {'who': {'$ref': 'page.md#/Who am I'}, 'cfg': {'$ref': 'page.md#/cfg'},
                               'whole': {'$ref': 'page.md'}, 'item': {'$ref': 'page.md#/Files/0'}})

    def put(self, name, doc):
        (self.d / name).write_text(json.dumps(doc))

    def run_(self, *argv, stdin=None):
        return subprocess.run([BIN, *argv], env=BASE, cwd=self.d, capture_output=True, text=True, timeout=20, input=stdin)

    def ok(self, *argv):
        p = self.run_(*argv)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def test_follow_goes_through_a_ref_to_md(self):
        self.assertEqual(json.loads(self.ok('get', '--follow', 'main.json#/who/Files/body.json')), 'your body')
        self.assertEqual(json.loads(self.ok('get', '--follow', 'main.json#/cfg/a/1')), True)
        self.assertEqual(json.loads(self.ok('get', '--follow', 'main.json#/whole/Who am I/_')), 'You are one proc.\n')
        self.assertEqual(json.loads(self.ok('get', 'main.json#/cfg')), {'$ref': 'page.md#/cfg'})   # without --follow: the $ref itself
        p = self.run_('get', '--follow', 'main.json#/who/Nope')
        self.assertEqual(p.returncode, 1)
        self.assertEqual(p.stderr, 'aos-json: error: PointerMissing no such pointer: main.json#/who/Nope '
                                   '(/Who am I has no Nope (it has: _, Files))\n')

    def test_resolve(self):
        self.assertEqual(json.loads(self.ok('get', '--resolve', 'main.json')),
                         {'who': '# Who am I\n\nYou are one proc.\n\n## Files\n\n- body.json: your body\n- plain\n',
                          'cfg': {'a': [1, True], 'r': {'$ref': 'gone.json'}}, 'whole': PAGE, 'item': 'body.json: your body'})
        self.assertEqual(json.loads(self.ok('get', '--resolve', 'page.md#/cfg')), {'a': [1, True], 'r': {'$ref': 'gone.json'}})

    def test_where(self):
        self.assertEqual(self.ok('where', 'main.json#/who/Files/1'), 'main.json#/who\npage.md#/Who am I/Files/1\n')
        self.assertEqual(self.ok('where', 'page.md#/cfg/a'), 'page.md#/cfg/a\n')

    def test_check(self):
        self.assertEqual(self.ok('check', 'main.json', 'page.md'), '')   # fences inside md are not checked
        self.put('bad.json', {'x': {'$ref': 'page.md#/Who am I/Nope'}})
        p = self.run_('check', 'bad.json')
        self.assertEqual(p.returncode, 10)
        self.assertEqual(p.stdout, 'bad.json#/x: DirectiveBad $ref points nowhere: page.md#/Who am I/Nope '
                                   '(/Who am I has no Nope (it has: _, Files))\n')

    def test_get_str_and_whole(self):
        self.assertEqual(self.ok('get', '--str', 'page.md#/Files/body.json'), 'your body\n')
        self.assertEqual(json.loads(self.ok('get', 'page.md')), PAGE)
        p = self.run_('get', '--str', 'page.md#/cfg')
        self.assertEqual(p.returncode, 1)
        self.assertEqual(p.stderr, 'aos-json: error: TargetBad page.md#/cfg is not a string (it is object)\n')
        p = self.run_('get', 'gone.md')
        self.assertEqual((p.returncode, p.stderr), (1, 'aos-json: error: FileMissing file not found: gone.md\n'))

    def test_tree_flag(self):
        self.assertEqual(list(json.loads(self.ok('get', '--tree', 'page.md'))), ['_', 'Who am I', 'cfg'])
        for argv in (['get', '--tree', 'page.md#/cfg'], ['get', '--tree', 'main.json'], ['get', '--tree', '--follow', 'page.md']):
            p = self.run_(*argv)
            self.assertEqual(p.returncode, 1, argv)
            self.assertIn('ArgumentsBad', p.stderr)

    def test_ls(self):
        self.assertEqual(self.ok('ls', 'page.md'), 'object, 3 keys\n_\nWho am I\ncfg\n')
        self.assertEqual(self.ok('ls', '--long', 'page.md#/Files'),
                         'object, 3 keys\n_\tstring\t31 chars\t35 bytes\nbody.json\tstring\t9 chars\t11 bytes\n1\tstring\t5 chars\t7 bytes\n')
        self.assertEqual(self.ok('ls', '--depth', '2', 'page.md#/Who am I'), 'object, 2 keys\n_\nFiles\nFiles/_\nFiles/body.json\nFiles/1\n')
        self.assertEqual(self.ok('ls', '--offset', '1', '--limit', '1', 'page.md'), 'object, 3 keys\nWho am I\n[more] 1 to 1 of 3 shown; next: --offset 2\n')
        self.assertEqual(self.ok('ls', 'page.md#/cfg'), 'object, 2 keys\na\nr\n')
        self.assertEqual(self.ok('ls', 'page.md#/Files/1'), 'string, 5 chars\n')
        self.assertEqual(self.ok('ls', '--follow', 'main.json#/who/Files'), 'object, 3 keys\n_\nbody.json\n1\n')

    def test_peek_and_search_use_the_tree(self):
        self.assertEqual(self.ok('peek', 'page.md'), 'page.md {3} _, Who am I, cfg\n  _: "Intro.\\n"\n  Who am I: {2} _, Files\n  cfg: {2} a, r\n')
        self.assertEqual(self.ok('search', '--key', 'Files', 'page.md'), 'page.md#/Who am I/Files\tstring\t31 chars\t35 bytes\n')
        p = self.run_('search', '--up', '--key', 'a', 'page.md#/cfg')
        self.assertEqual(p.returncode, 1)
        self.assertIn('ArgumentsBad', p.stderr)

    def test_every_write_is_refused_and_md_is_unchanged(self):
        before = (self.d / 'page.md').read_bytes()
        main = (self.d / 'main.json').read_bytes()
        cases = [
            ['set', 'page.md#/x', '1'], ['set', 'page.md', '"t"'], ['set', '--follow', 'main.json#/cfg/a/0', '2'],
            ['set', '--follow', 'main.json#/who', '"t"'], ['set', '--follow', 'main.json#/cfg/new', '1'],
            ['add', 'page.md#/x', '1'], ['add', 'page.md', '"t"'], ['add', '--follow', 'main.json#/cfg/a/-', '3'],
            ['add', '--follow', 'main.json#/cfg/z', '3'],
            ['del', 'page.md#/cfg/a'], ['del', '--follow', 'main.json#/cfg/a'],
            ['append', 'page.md#/cfg/a', '1'], ['append', '--follow', 'main.json#/cfg/a', '1'],
            ['merge', 'page.md#/cfg', '{"b": 1}'], ['merge', '--follow', 'main.json#/cfg', '{"b": 1}'],
            ['env', 'page.md#/x', 'HOME'], ['ref', 'page.md#/x', 'main.json'], ['ref', '--move', 'main.json#/item', 'page.md'],
            ['ref', '--move', 'main.json#/item', 'page.md#/y'],
        ]
        for argv in cases:
            with self.subTest(argv=argv):
                p = self.run_(*argv)
                self.assertEqual((p.returncode, p.stderr), (1, REFUSED))
        for argv, stdin in ((['batch', 'page.md'], '{"/x": 1}'), (['batch', '--follow', 'main.json'], '{"/cfg/a/0": 5}')):
            with self.subTest(argv=argv):
                p = self.run_(*argv, stdin=stdin)
                self.assertEqual((p.returncode, p.stderr), (1, REFUSED))
        p = self.run_('set', 'new.md', '"t"')   # a new md is not made either
        self.assertEqual((p.returncode, p.stderr), (1, REFUSED.replace('page.md', 'new.md')))
        self.assertFalse((self.d / 'new.md').exists())
        self.assertEqual((self.d / 'page.md').read_bytes(), before)
        self.assertEqual((self.d / 'main.json').read_bytes(), main)


if __name__ == '__main__':
    unittest.main()
