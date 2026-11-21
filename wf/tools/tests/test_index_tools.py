# Verify index_gen (build folder indexes from file headers; a .md's own description section) and the four checks of index_check (IndexBad, EntryGone, LinkBad, LinkMissing) on a throwaway git tree.
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

    def test_md_description_section(self):
        # 11-21: a .md's `# _description` (wins) or `# description` gives its first non-empty line; else the first heading, skipping _index / index
        md = index_gen.md_file_desc
        self.assertEqual(md('# Title\n\n# description\n\n\n  The **real** one.\nsecond\n'), 'The real one.')
        self.assertEqual(md('# description\n\nloses\n\n# _description\n\nwins\n'), 'wins')
        self.assertEqual(md('## Description\n\ncase does not matter\n'), 'case does not matter')
        self.assertEqual(md('# _index\n\n- a: b\n\n# index\n\n- c: d\n\n# Who am I\n\ntext\n'), 'Who am I')
        self.assertEqual(md('# Who am I\n\ntext\n'), 'Who am I')                             # no section: the first heading, as before
        self.assertEqual(md('- description: a list key is not a heading\n\n# Head\n'), 'Head')
        self.assertEqual(md('← [入口](x.md)｜涵蓋：甲｜下\n\n# description\n\nfrom the section\n'), 'from the section')
        self.assertEqual(md('```\n# description\n```\n# Real\n'), 'Real')                  # a heading in a code block does not count
        (self.root / 'docs/page.md').write_text('# _index\n\n- x: y\n\n# description\n\nOne line about the page.\n', encoding='utf-8')
        subprocess.run(['git', '-C', str(self.root), 'add', '-A'], check=True)
        tables, _m, _s, _i = self.build({'code': 'the programs', 'docs/archive': 'old things'})
        self.assertEqual(tables['docs/_index.json']['page.md']['description'], 'One line about the page.')

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
        del docs['data.json']                                       # there but not listed: not a problem any more (11-21 第 18 句)
        docs['a.md'] = 'a bare string'                              # a plain string is the description (11-21 第 18 句)
        docs['README.md'] = {'note': 'no description'}
        (self.root / 'docs/_index.json').write_text(json.dumps(docs), encoding='utf-8')
        top = json.loads((self.root / '_index.json').read_text(encoding='utf-8'))
        del top['docs']['index']
        (self.root / '_index.json').write_text(json.dumps(top), encoding='utf-8')
        bad = check(self.root)
        self.assertEqual(bad.returncode, 1)
        for code in ('EntryGone docs/_index.json: gone.md', 'LinkBad docs/_index.json: a:', 'IndexBad docs/_index.json: entry README.md',
                     'LinkMissing _index.json: docs'):
            self.assertIn(code, bad.stderr)
        for gone in ('EntryMissing', 'data.json', 'entry a.md'):
            self.assertNotIn(gone, bad.stderr)
        self.assertIn('FlagUnknown', check(self.root, '--view').stderr)          # --fs / --view are gone with EntryMissing
        self.assertIn('FlagUnknown', check(self.root, '--fs').stderr)

    def test_text_as_lines(self):
        # user 11-13: a piece of text may be one string or an array of strings (one line each); both read the same
        for rel, doc in [('docs/kb/_description.json', ['# kb — the notes', '', 'Body line.']),
                         ('docs/kb/node.json', {'_description': ['# Node one', '', 'More.'], 'x': 1}),
                         ('docs/kb/str.json', {'_description': '# Node two\n\nMore.'}),
                         ('docs/kb/head.json', {'description': ['first line of the header', 'second line'], 'x': 1}),
                         ('docs/kb/argv.json', ['prog', '--flag']),
                         ('docs/one/_description.json', '# one — a single string\n\nBody.')]:
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(doc), encoding='utf-8')
        subprocess.run(['git', '-C', str(self.root), 'add', '-A'], check=True)
        tables, missing, _scopes, _in = self.build({'code': 'the programs', 'docs/archive': 'old things'})
        self.assertEqual(missing, [])
        kb = tables['docs/kb/_index.json']
        self.assertEqual(kb['_description.json']['description'], 'kb — the notes')
        self.assertEqual(kb['node.json']['description'], 'Node one')
        self.assertEqual(kb['str.json']['description'], 'Node two')
        self.assertEqual(kb['head.json']['description'], 'first line of the header')
        self.assertEqual(kb['argv.json']['description'], 'argv：`prog --flag`')              # a string array elsewhere is still an argv file
        self.assertEqual(tables['docs/_index.json']['kb']['description'], 'kb — the notes')  # a folder without README: its _description.json
        self.assertEqual(tables['docs/_index.json']['one']['description'], 'one — a single string')
        self.assertEqual(tables['docs/one/_index.json']['_description.json']['description'], 'one — a single string')

    def test_entry_only_folder(self):
        # ok-astra 11-14 advice: a tool/hook folder with only _entry takes its description from the _entry header
        for rel, text in [('docs/hooks/notify/_entry', '#!/usr/bin/env python3\n# notify - tell the box once。More detail.\n# second comment line\nimport os\n'),
                          ('docs/hooks/noop/_entry', '#!/bin/sh\n\n# noop: do nothing\ncat > /dev/null\n'),
                          ('docs/hooks/code/_entry', '#!/bin/sh\nexit 0\n'),                       # first real line is code: no sentence
                          ('docs/hooks/argv/_entry', '["python3", "x.py"]\n'),                        # JSON argv: no sentence
                          ('docs/hooks/argv2/_entry', '["python3", "y.py"]\n'),
                          ('docs/hooks/both/_entry', '#!/bin/sh\n# both - from the entry\n'),
                          ('docs/hooks/both/README.md', '# both — from the readme\n')]:
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
        subprocess.run(['git', '-C', str(self.root), 'add', '-A'], check=True)
        tables, missing, _scopes, _in = self.build({'code': 'the programs', 'docs/archive': 'old things', 'docs/hooks': 'the hooks', 'docs/hooks/argv': 'hand line'})
        hooks = tables['docs/hooks/_index.json']
        self.assertEqual(hooks['notify']['description'], 'tell the box once。')      # shebang skipped, folder name stripped, cut at the first 。
        self.assertEqual(hooks['noop']['description'], 'do nothing')
        self.assertEqual(hooks['both']['description'], 'both — from the readme')    # README still wins over _entry
        self.assertEqual(hooks['argv']['description'], 'hand line')                  # index_gen_desc.json still wins
        self.assertEqual([m for m in missing if m.endswith('/')], ['docs/hooks/argv2/', 'docs/hooks/code/'])  # _entry with no comment line

    def test_check_description_lines(self):
        (self.root / 'code/_index.json').write_text(json.dumps({'x.py': {'description': ['does x', 'second line']}}), encoding='utf-8')
        ok = check(self.root, 'code')
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertIn('1 index files, 1 entries, 0 problems', ok.stdout)
        for bad in ([], [''], ['  ', ''], ['x', 1], [['x']], 3, None, ''):
            (self.root / 'code/_index.json').write_text(json.dumps({'x.py': {'description': bad}}), encoding='utf-8')
            r = check(self.root, 'code')
            self.assertEqual(r.returncode, 1, repr(bad))
            self.assertIn('IndexBad code/_index.json: entry x.py is not', r.stderr, repr(bad))


if __name__ == '__main__':
    unittest.main()
