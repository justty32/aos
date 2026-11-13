# Verify index_check does not go quietly green: paths outside the root, untracked folders, skipped folder names, no index at all, index fields that are not an index, JSON too deep to read.
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


# a small tree: one planted gone entry, one file there but not listed (sub/y.md)
TREE = {'a.md': '# a\n', 'sub/x.md': '# x\n', 'sub/y.md': '# y\n',
        '_index.json': {'a.md': {'description': 'a'}, 'sub': {'description': 's', 'index': 'sub/_index.json'}},
        'sub/_index.json': {'x.md': {'description': 'x'}}}


class EdgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.t = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        subprocess.run(['git', '-C', str(self.t / 'outer'), '-c', 'user.email=t@t', '-c', 'user.name=t', *args],
                       check=True, capture_output=True)

    def test_path_outside_the_root_is_refused(self):
        put(self.t / 'other', TREE)
        put(self.t / 'root', {'r.md': '# r\n'})
        for p in (str(self.t / 'other'), '../other'):
            r = check(self.t / 'root', '--fs', p)
            self.assertEqual(r.returncode, 1, p)
            self.assertIn('PathBad', r.stderr, p)

    def test_untracked_folder_inside_git_counts_the_disk(self):
        (self.t / 'outer').mkdir()
        subprocess.run(['git', 'init', '-q', str(self.t / 'outer')], check=True)
        put(self.t / 'outer', {'top.txt': 't\n'})
        self.git('add', 'top.txt')
        self.git('commit', '-qm', 't')
        put(self.t / 'outer/content', TREE)                     # an unpacked snapshot, not added to git
        for args in ((self.t / 'outer/content',), (self.t / 'outer', 'content')):
            r = check(*args)
            self.assertEqual(r.returncode, 1, args)
            self.assertIn('EntryMissing', r.stderr, args)
            self.assertIn('y.md is there but not listed', r.stderr, args)
            self.assertIn('warning', r.stderr, args)

    def test_skipped_folder_with_an_index_is_told(self):
        put(self.t, {'build/b.md': '# b\n', 'build/_index.json': {'zzz': {'description': 'planted'}},
                     '_index.json': {'build': {'description': 'b', 'index': 'build/_index.json'}}})
        r = check(self.t, '--fs')
        self.assertIn('warning', r.stderr)
        self.assertIn('build', r.stderr)
        self.assertIn('1 skipped', r.stdout)

    def test_archive_is_not_checked_but_told(self):
        # user 11-13 15:18 "都按照推薦": archive keeps no inner links, so its indexes are skipped and counted, not checked
        put(self.t, {'live.md': '# l\n', 'archive/old/o.md': '# o\n',
                     'archive/_index.json': {'gone.md': {'description': 'stale'}},
                     'archive/old/_index.json': {'gone.md': {'description': 'moved away later'},
                                                 'live': {'description': 'x', 'index': '../../live/_index.json'}},
                     '_index.json': {'live.md': {'description': 'l'}, 'archive': {'description': 'old things'}}})
        r = check(self.t, '--fs')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('warning: archive/_index.json is not checked', r.stderr)
        self.assertIn('warning: archive/old/_index.json is not checked', r.stderr)
        self.assertIn('1 index files, 2 entries, 0 problems; 2 skipped', r.stdout)

    def test_no_index_at_all_is_told(self):
        put(self.t, {'x/f.md': 'hi\n'})
        for args in (('--fs',), ('--fs', '--quiet')):
            r = check(self.t, *args)
            self.assertEqual(r.returncode, 0)
            self.assertIn('warning: no _index.json under .', r.stderr, args)

    def test_index_field_must_point_to_an_index(self):
        put(self.t, {'decisions.json': {'a': 1}, '_description.json': '"just text"', 'sub/s.md': '# s\n',
                     'sub/_index.json': {'s.md': {'description': 's'}},
                     'obj.json': {'k': 1, '_index': {'k': {'description': 'k'}}},
                     'm/_metainfo.json': {'index': {'n.md': {'description': 'n'}}}, 'm/n.md': '# n\n',
                     'str/_index.json': '"sub/_index.json"', 'str/t.md': '# t\n'})
        good = {'sub': {'description': 's', 'index': 'sub/_index.json'},
                'obj.json': {'description': 'o', 'index': 'obj.json#/_index'},
                'm': {'description': 'm', 'index': 'm/_metainfo.json#/index'}}
        bad = {'decisions.json': {'description': 'd', 'index': 'decisions.json'},
               '_description.json': {'description': 't', 'index': '_description.json'},
               'str': {'description': 'a whole _index.json must be a table', 'index': 'str/_index.json'}}
        put(self.t, {'_index.json': dict(good, **bad)})
        r = check(self.t, '--fs', '--view')
        for k in bad:
            self.assertIn('LinkBad _index.json: %s: index' % k, r.stderr)
        for k in good:
            self.assertNotIn('LinkBad _index.json: %s:' % k, r.stderr)
        self.assertNotIn('EntryGone m/_metainfo.json', r.stderr)            # a folder's _metainfo index lists the folder

    def test_json_too_deep_does_not_crash(self):
        put(self.t, {'deep.json': '[' * 200000 + ']' * 200000, 'x/_index.json': '{"a":' * 200000 + '1' + '}' * 200000,
                     '_index.json': {'deep.json#/0': {'description': 'deep'}, 'x': {'description': 'x'}}})
        r = check(self.t, '--fs', '--view')
        self.assertNotIn('Traceback', r.stderr)
        self.assertIn('IndexBad x/_index.json: cannot be read as JSON', r.stderr)
        self.assertIn('EntryGone _index.json: deep.json#/0', r.stderr)


if __name__ == '__main__':
    unittest.main()
