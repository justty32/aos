# Verify index_gen writes the per-file code map json (wf/knowledge/code-map/proto8/<top>.json) from file headers: one leaf per scanned unit, stable on re-run, stale check on header change.
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).parents[1]
sys.path.insert(0, str(TOOLS))
import codemap_gen  # noqa: E402
import index_gen  # noqa: E402

OUT = 'wf/knowledge/code-map/proto8'


class CodemapJsonTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for rel, text in [('proto8/x.py', '"""x - top file."""\n'),
                          ('proto8/lib/a.py', '# a.py：does a.\n'),
                          ('proto8/lib/sub/b.py', '"""b - 做 b。後面不收。"""\n'),
                          ('proto8/lib/sub/nohead.py', 'import os\n'),
                          ('proto8/lib/pipe.py', '# pipe - a | b.\n'),
                          ('proto8/cmd/tool/_entry', '#!/bin/sh\n# tool - runs the tool.\n'),
                          ('proto8/cmd/tool/_tooldef.json', '{"description": "def"}'),
                          ('proto8/cmd/tool/tests/t.py', '# t - tests tool.\n'),
                          ('proto8/impls/foo/CMakeLists.txt', '# foo build.\ntarget_link_libraries(foo PUBLIC bar PRIVATE baz)\n'),
                          ('proto8/impls/foo/src/f.cpp', '// f.cpp - foo body.\n'),
                          ('proto8/thinking/skip.md', '# skipped\n'),
                          ('proto8/lib/README.md', '# not listed\n')]:
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        subprocess.run(['git', '-C', str(self.root), 'add', '-A'], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def run_gen(self, *args):
        cfg = index_gen.load('index_gen.json')
        cfg = dict(cfg, scopes=[{'path': 'proto8', 'stage': 1}])
        real = index_gen.load
        index_gen.load = lambda name: cfg if name == 'index_gen.json' else {'desc': {}}
        try:
            return index_gen.main(['--root', str(self.root), '--quiet', *args])
        finally:
            index_gen.load = real

    def read(self, name):
        return json.loads((self.root / OUT / name).read_text(encoding='utf-8'))

    def leaves(self, node):
        return sum(self.leaves(v) if isinstance(v, dict) else 1 for v in node.values())

    def test_shape_and_counts(self):
        self.assertEqual(self.run_gen('--apply'), 0)
        names = sorted(p.name for p in (self.root / OUT).iterdir())
        self.assertEqual(names, ['cmd.json', 'impls.json', 'lib.json', 'proto8.json'])
        lib = self.read('lib.json')
        self.assertEqual(lib['generated_by'], 'wf/tools/index_gen.py')
        self.assertEqual(lib['tree']['a.py'], 'does a.')
        self.assertEqual(lib['tree']['sub']['b.py'], '做 b。')
        self.assertEqual(lib['tree']['sub']['nohead.py'], '')          # 沒有一句話：空字串
        self.assertEqual(lib['tree']['pipe.py'], 'a | b.')               # md 的 \| 不帶進 json
        self.assertNotIn('README.md', lib['tree'])
        self.assertEqual(self.read('cmd.json')['tree']['tool/'], 'runs the tool.')   # 工具夾三個契約檔併一格
        self.assertEqual(self.read('cmd.json')['tree']['tool']['tests']['t.py'], 'tests tool.')
        self.assertEqual(self.read('impls.json')['deps'], {'foo': {'public': ['bar'], 'private': ['baz']}})
        self.assertEqual(self.read('proto8.json')['tree'], {'x.py': 'top file.'})
        # 葉子數＝md 冊的列數（同一次掃描）
        proto = str(self.root / 'proto8')
        _books, stats, _n = codemap_gen.books(proto, codemap_gen.tracked(proto))
        total = sum(self.leaves(self.read(n)['tree']) for n in names)
        self.assertEqual(total, stats['rows'])

    def test_rerun_is_stable_and_check_passes(self):
        self.assertEqual(self.run_gen('--apply'), 0)
        before = {p.name: p.read_text(encoding='utf-8') for p in (self.root / OUT).iterdir()}
        self.assertEqual(self.run_gen('--apply'), 0)
        after = {p.name: p.read_text(encoding='utf-8') for p in (self.root / OUT).iterdir()}
        self.assertEqual(before, after)
        self.assertEqual(self.run_gen(), 0)

    def test_header_change_is_stale(self):
        self.assertEqual(self.run_gen('--apply'), 0)
        (self.root / 'proto8/lib/a.py').write_text('# a.py：does something else.\n', encoding='utf-8')
        self.assertEqual(self.run_gen(), 1)

    def test_removed_top_folder_drops_its_book(self):
        self.assertEqual(self.run_gen('--apply'), 0)
        subprocess.run(['git', '-C', str(self.root), 'rm', '-rqf', 'proto8/cmd'], check=True)
        self.assertEqual(self.run_gen(), 1)                               # 多出來的冊＝stale
        self.assertEqual(self.run_gen('--apply'), 0)
        self.assertFalse((self.root / OUT / 'cmd.json').exists())


if __name__ == '__main__':
    unittest.main()
