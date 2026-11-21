# Verify index_check's edges: no quiet green (paths outside the root, skipped folder names, archive, no index at all, JSON too deep), the four checks on md (_index.md, FILE.md#/place keys, index fields into md), plain-string and $ref entries.
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).parents[1] / 'index_check.py'


def check(root, *args):
    return subprocess.run([sys.executable, str(TOOL), '--root', str(root), *args], capture_output=True, text=True)


def put(root, files):
    for rel, text in files.items():
        p = Path(root) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text if isinstance(text, str) else json.dumps(text), encoding='utf-8')


TREE = {'a.md': '# a\n', 'sub/x.md': '# x\n', 'sub/y.md': '# y\n',
        '_index.json': {'a.md': {'description': 'a'}, 'sub': {'description': 's', 'index': 'sub/_index.json'}},
        'sub/_index.json': {'x.md': {'description': 'x'}}}

PAGE = """# Who am I

Finding your own name.

# index

- Who am I: finding your own name

# Data

```json
{"k": {"description": "from a json block"}}
```

# Prose

Just words.

- a list item without a key
"""


class EdgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.t = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_path_outside_the_root_is_refused(self):
        put(self.t / 'other', TREE)
        put(self.t / 'root', {'r.md': '# r\n'})
        for p in (str(self.t / 'other'), '../other'):
            r = check(self.t / 'root', p)
            self.assertEqual(r.returncode, 1, p)
            self.assertIn('PathBad', r.stderr, p)

    def test_partial_index_is_fine(self):
        # 11-21 第 18 句「誰說index格式要列出所有東西了？……這個規則刪掉」: sub/y.md is there but not listed
        put(self.t, TREE)
        r = check(self.t)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('2 index files, 3 entries, 0 problems', r.stdout)

    def test_skipped_folder_with_an_index_is_told(self):
        put(self.t, {'build/b.md': '# b\n', 'build/_index.json': {'zzz': {'description': 'planted'}},
                     '_index.json': {'build': {'description': 'b', 'index': 'build/_index.json'}}})
        r = check(self.t)
        self.assertIn('warning', r.stderr)
        self.assertIn('build', r.stderr)
        self.assertIn('1 skipped', r.stdout)

    def test_archive_is_not_checked_but_told(self):
        # user 11-13 15:18 "都按照推薦": archive keeps no inner links, so its indexes are skipped and counted, not checked
        put(self.t, {'live.md': '# l\n', 'archive/old/o.md': '# o\n',
                     'archive/_index.json': {'gone.md': {'description': 'stale'}},
                     'archive/old/_index.md': '- gone.md: moved away later\n',
                     '_index.json': {'live.md': {'description': 'l'}, 'archive': {'description': 'old things'}}})
        r = check(self.t)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('warning: archive/_index.json is not checked', r.stderr)
        self.assertIn('warning: archive/old/_index.md is not checked', r.stderr)
        self.assertIn('1 index files, 2 entries, 0 problems; 2 skipped', r.stdout)

    def test_no_index_at_all_is_told(self):
        put(self.t, {'x/f.md': 'hi\n'})
        for args in ((), ('--quiet',)):
            r = check(self.t, *args)
            self.assertEqual(r.returncode, 0)
            self.assertIn('warning: no _index.json or _index.md under .', r.stderr, args)

    def test_json_too_deep_does_not_crash(self):
        put(self.t, {'deep.json': '[' * 200000 + ']' * 200000, 'x/_index.json': '{"a":' * 200000 + '1' + '}' * 200000,
                     '_index.json': {'deep.json#/0': {'description': 'deep'}, 'x': {'description': 'x'}}})
        r = check(self.t)
        self.assertNotIn('Traceback', r.stderr)
        self.assertIn('IndexBad x/_index.json: cannot be read', r.stderr)
        self.assertIn('EntryGone _index.json: deep.json#/0', r.stderr)

    def test_entry_shapes(self):
        put(self.t, {'a.md': '# a\n', 'b.json': {'who': 'w'}, 'sub/_index.json': {}, 'sub/s.md': '# s\n',
                     '_index.json': {'a.md': 'a plain string is the description',
                                     'b.json': {'$ref': 'b.json#/who'},                          # $ref: not looked into
                                     'sub': {'$ref': 'nowhere.json'},                             # $ref entries are not asked for an index
                                     'blank': '  ', 'num': 3, 'obj': {'index': 'sub/_index.json'},
                                     'ref_desc': {'description': {'$ref': 'b.json#/who'}},
                                     'badlink': {'description': 'x', 'index': 5}}})
        r = check(self.t)
        for k in ('blank', 'num', 'obj'):
            self.assertIn('IndexBad _index.json: entry %s is not' % k, r.stderr)
        self.assertIn('IndexBad _index.json: entry badlink: index is not a non-empty string', r.stderr)
        for k in ('a.md', 'b.json', 'ref_desc'):
            self.assertNotIn('IndexBad _index.json: entry %s ' % k, r.stderr)
        self.assertNotIn('LinkMissing', r.stderr)
        self.assertIn('EntryGone _index.json: blank', r.stderr)                                    # keys are still names of things

    def test_index_md_of_a_folder(self):
        # 第 18 句「整隻只認_index.json……如果沒有_index.json，那才去看_index.md」
        put(self.t, {'a.md': '# a\n', 'kb/me.md': PAGE, '_index.md': '- a.md: the a page\n- gone.md: not there\n- no key\n',
                     'kb/_index.md': 'Just words.\n',
                     'j/_index.json': {'x.md': {'description': 'json wins'}}, 'j/_index.md': '- nothing.md: never read\n', 'j/x.md': '# x\n'})
        r = check(self.t)
        self.assertIn('3 index files', r.stdout)
        self.assertIn('EntryGone _index.md: gone.md is listed but not there', r.stderr)
        self.assertIn('IndexBad kb/_index.md: has no `key: value` list items', r.stderr)
        self.assertNotIn('nothing.md', r.stderr)
        self.assertNotIn('a.md', r.stderr)

    def test_md_place_keys(self):
        # 第 18 句「xxx.md#/yyy，他也可以當json讀啊」
        put(self.t, {'me.md': PAGE, '_index.json': {'me.md#/Who am I': 'ok', 'me.md#/index/Who am I': 'a list key',
                                                    'me.md#/Data/k/description': 'into the json block',
                                                    'me.md#/Nope': 'not there', 'me.md#Who': 'no slash'}})
        r = check(self.t)
        self.assertEqual(r.stderr.count('EntryGone'), 2, r.stderr)
        self.assertIn('EntryGone _index.json: me.md#/Nope is listed but that place cannot be read', r.stderr)
        self.assertIn('EntryGone _index.json: me.md#Who', r.stderr)

    def test_index_field_targets(self):
        # 第 14～17 句: an index field may point to any FILE#/PATH that reads as an index (json: an object; md: a json block object or a key: value list)
        put(self.t, {'me.md': PAGE, 'any.json': {'a': 1}, 'str.json': '"just text"', 'arr.json': [1],
                     'sub/_index.json': {}, 'sub/s.md': '# s\n', 'other/_index.json': '"sub/_index.json"'})
        good = {'sub': {'description': 's', 'index': 'sub/_index.json'},
                'any.json': {'description': 'a whole .json object', 'index': 'any.json'},
                'me.md': {'description': 'm', 'index': 'me.md#/index'},
                'me.md#/Data': {'description': 'd', 'index': 'me.md#/Data'},
                'me.md#/Who am I': {'description': 'w', 'index': '#/sub'}}                       # #/ = this _index.json, an object
        bad = {'str.json': {'description': 's', 'index': 'str.json'},
               'arr.json': {'description': 'a', 'index': 'arr.json'},
               'me.md#/Prose': {'description': 'p', 'index': 'me.md#/Prose'},                   # a list without keys is not an index
               'a': {'description': 'x', 'index': 'me.md#/Nope'},
               'b': {'description': 'x', 'index': 'nowhere.json'},
               'c': {'description': 'x', 'index': 'x.json#abc'},
               'd': {'description': 'x', 'index': 'sub'}}
        put(self.t, {'_index.json': dict(good, **bad), 'a': '', 'b': '', 'c': '', 'd': ''})
        r = check(self.t)
        for k in bad:
            self.assertIn('LinkBad _index.json: %s: index' % k, r.stderr)
        for k in good:
            self.assertNotIn('LinkBad _index.json: %s:' % k, r.stderr)
        self.assertIn('IndexBad other/_index.json: is not a JSON object', r.stderr)


if __name__ == '__main__':
    unittest.main()
