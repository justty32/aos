# Verify index_gen (build folder indexes from file headers) and index_check (listed-but-gone, there-but-unlisted, bad links) on a throwaway git tree.
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).parents[1]
sys.path.insert(0, str(TOOLS))
import index_gen  # noqa: E402


def check(root, *args):
    return subprocess.run([sys.executable, str(TOOLS / 'index_check.py'), '--root', str(root), *args],
                          capture_output=True, text=True)


class IndexToolsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for rel, text in [('README.md', '# top — the root\n'),
                          ('docs/README.md', '# docs — the rules\n'),
                          ('docs/a.md', '← [入口](../a.md)｜涵蓋：甲、乙｜下一份\n\n## 甲\n'),
                          ('docs/a/01.md', '# part one of **a**, see [x](y.md)\n'),
                          ('docs/data.json', json.dumps({'contract': 'wf-table/1', 'source': 'a.md', 'columns': ['id'], 'rows': [{'id': '1'}]})),
                          ('docs/archive/old.md', '# old\n'),
                          ('code/x.py', '"""x - does x."""\n')]:
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        subprocess.run(['git', '-C', str(self.root), 'add', '-A'], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, hand=None, more_than=0):
        cfg = {'more_than': more_than, 'scopes': [{'path': '.', 'stage': 1}, {'path': 'docs', 'deep': True, 'stage': 1}],
               'skip_dir_names': ['archive'], 'skip_dirs': []}
        real = index_gen.load
        index_gen.load = lambda name: cfg if name == 'index_gen.json' else {'desc': hand or {}}
        try:
            return index_gen.build(str(self.root))
        finally:
            index_gen.load = real

    def test_generated_tables(self):
        tables, missing, _scopes, _in = self.build({'code': 'the programs', 'docs/archive': 'old things'})
        self.assertEqual(missing, [])
        self.assertEqual(sorted(tables), ['_index.json', 'docs/_index.json', 'docs/a/_index.json'])
        self.assertEqual(tables['_index.json']['docs'], {'description': 'docs — the rules', 'index': 'docs/_index.json'})
        self.assertEqual(tables['_index.json']['code'], {'description': 'the programs'})      # out of scope: no link
        docs = tables['docs/_index.json']
        self.assertEqual(docs['a.md']['description'], '涵蓋：甲、乙')
        self.assertEqual(docs['a'], {'description': '分檔夾：涵蓋：甲、乙', 'index': 'a/_index.json'})
        self.assertNotIn('index', docs['archive'])                                            # archive: entry only
        self.assertIn('抽自 a.md', docs['data.json']['description'])
        self.assertEqual(tables['docs/a/_index.json']['01.md']['description'], 'part one of a, see x')

    def test_threshold_keeps_only_big_folders(self):
        hand = {'code': 'the programs', 'docs/archive': 'old things'}
        tables, _m, _s, _i = self.build(hand, more_than=3)          # docs has 5 things, the root 3, docs/a 1
        self.assertEqual(sorted(tables), ['docs/_index.json'])
        self.assertEqual(tables['docs/_index.json']['a'], {'description': '分檔夾：涵蓋：甲、乙'})     # small child: no link
        tables, _m, _s, _i = self.build(hand, more_than=2)          # now the root too; it links to docs
        self.assertEqual(sorted(tables), ['_index.json', 'docs/_index.json'])
        self.assertEqual(tables['_index.json']['docs']['index'], 'docs/_index.json')

    def test_missing_description_is_reported(self):
        _tables, missing, _scopes, _in = self.build()
        self.assertEqual(missing, ['code/', 'docs/archive/'])

    def test_check_finds_each_kind(self):
        tables, _m, _s, _i = self.build({'code': 'the programs', 'docs/archive': 'old things'})
        for rel, table in tables.items():
            (self.root / rel).write_text(index_gen.dump(table), encoding='utf-8')
        ok = check(self.root)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertIn('3 index files, 9 entries, 0 problems', ok.stdout)
        docs = json.loads((self.root / 'docs/_index.json').read_text(encoding='utf-8'))
        docs['gone.md'] = {'description': 'not there'}
        docs['a']['index'] = 'a/nowhere.json'
        del docs['data.json']
        docs['a.md'] = 'a bare string'
        (self.root / 'docs/_index.json').write_text(json.dumps(docs), encoding='utf-8')
        top = json.loads((self.root / '_index.json').read_text(encoding='utf-8'))
        del top['docs']['index']
        (self.root / '_index.json').write_text(json.dumps(top), encoding='utf-8')
        bad = check(self.root)
        self.assertEqual(bad.returncode, 1)
        for code in ('EntryGone docs/_index.json: gone.md', 'LinkBad docs/_index.json: a:', 'EntryMissing docs/_index.json: data.json',
                     'IndexBad docs/_index.json: entry a.md', 'LinkMissing _index.json: docs'):
            self.assertIn(code, bad.stderr)
        self.assertNotIn('EntryMissing', check(self.root, '--view').stderr)


if __name__ == '__main__':
    unittest.main()
