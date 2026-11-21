# Verify kb_md (turn long-article knowledge pages into .md, rewrite old paths by the map, verify every article reads back) on a small fake knowledge folder.
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).parents[1] / 'kb_md.py'


def run(*args):
    return subprocess.run([sys.executable, str(TOOL), *map(str, args)], capture_output=True, text=True)


def put(root, files):
    for rel, doc in files.items():
        p = Path(root) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        raw = not rel.endswith('.json')
        p.write_text(doc if raw else json.dumps(doc, ensure_ascii=False, indent=None if isinstance(doc, str) else 1) + '\n', encoding='utf-8')


KB = {
    'aos/_description.json': '# aos in one page\n\nStart with `aos/me.json`, then aos/me.json#/stack.',
    'aos/me.json': {'_description': '# Who am I\n\nFinding your name.', 'stack': '# What is in your stack\n\nSee `aos/me.json#/self_tools` and `aos/me.json#/nope`.\n\n\n',
                    'self_tools': {'$ref': 'me/self_tools.json'}},
    'aos/me/self_tools.json': {'_description': '# self_tools\n\nYour tool list.'},
    'aos/me/_description.json': 'Long sections of aos/me.json.',                        # one sentence, no heading: stays json
    'aos/clock.json': {'_description': 'Timers in one line.', 'wake': ['# Wake me', '', 'Use `aos/clock.json#/wake`.']},
    'aos/packs.json': {'_description': 'Packs.', '_index': {'look': {'description': 'l'}}, 'look': 'Pack look: read.'},
    'aos/dup.json': {'a': '# Same\n\nx', 'b': '# Same\n\ny'},
    'aos/under.json': {'a': '# _\n\nx'},
    'aos/plain.json': {'a': '# A\n\nx', 'b': 'no heading here'},
    'aos/rec.json': {'a': '# A\n\nx', 'n': 3},
    'aos/_index.json': {'me.json': {'description': 'Who: see aos/me.json'}, 'me': {'description': 'm'}, 'packs.json': 'p',
                        'clock.json#/wake': 'w'},
    'aos/me/_index.json': {'../me.json#/stack': 's', 'self_tools.json': 't', '_description.json': 'd'},
    'README.md': 'Paths: `aos/me.json#/stack`, knowledge/aos/me.json stays, aos/me.json.bak too, and aos/packs.json#/look.\n',
}


class KbMdTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.t = Path(self.tmp.name)
        put(self.t / 'src', KB)
        self.dst, self.map = self.t / 'out' / 'knowledge', self.t / 'out' / 'kb_md_map.json'
        (self.t / 'out').mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def convert(self, *more):
        r = run('convert', self.t / 'src', self.dst, *more)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def test_convert(self):
        r = self.convert()
        self.assertIn('aos/ 4 pages to md, 6 kept as json', r.stdout)
        for rel, why in (('aos/packs.json', 'it has _index'), ('aos/dup.json', 'same heading twice'), ('aos/under.json', 'a heading named _'),
                         ('aos/plain.json', 'b is text without a heading'), ('aos/rec.json', 'n is a number'),
                         ('aos/me/_description.json', 'the whole page is text without a heading')):
            self.assertIn('kept %s: %s' % (rel, why), r.stdout)
        self.assertIn('warning: aos/dup.json stays json', r.stderr)
        aos = self.dst / 'aos'
        self.assertFalse((aos / 'me.json').exists())
        self.assertEqual((aos / '_description.md').read_text(), KB['aos/_description.json'])            # a whole page: as it is
        self.assertEqual((aos / 'me.md').read_text(), '# Who am I\n\nFinding your name.\n\n# What is in your stack\n\nSee `aos/me.json#/self_tools` and `aos/me.json#/nope`.\n')
        self.assertEqual((aos / 'clock.md').read_text(), 'Timers in one line.\n\n# Wake me\n\nUse `aos/clock.json#/wake`.\n')
        self.assertEqual((aos / 'packs.json').read_text(), (self.t / 'src/aos/packs.json').read_text())
        table = json.loads(self.map.read_text())
        self.assertEqual(table['aos/me.json'], 'aos/me.md')
        self.assertEqual(table['aos/me.json#/stack'], 'aos/me.md#/What is in your stack')
        self.assertEqual(table['aos/me.json#/_description'], 'aos/me.md#/Who am I')
        self.assertEqual(table['aos/me.json#/self_tools'], 'aos/me/self_tools.md')                  # a $ref: the new path of that file
        self.assertEqual(table['aos/clock.json#/_description'], 'aos/clock.md#/_')
        self.assertNotIn('aos/packs.json', table)
        self.assertEqual(list(json.loads((aos / '_index.json').read_text())), ['me.md', 'me', 'packs.json', 'clock.md#/Wake me'])
        self.assertEqual(list(json.loads((aos / 'me/_index.json').read_text())), ['../me.md#/What is in your stack', 'self_tools.md', '_description.json'])
        self.assertIn('PathBad', run('convert', self.t / 'src', self.dst).stderr)                     # DST must be new

    def test_keep_and_force(self):
        r = self.convert('--keep', 'aos/clock.json', '--force-md', 'aos/plain.json', '--force-md', 'aos/rec.json')
        self.assertTrue((self.dst / 'aos/clock.json').exists())
        self.assertEqual((self.dst / 'aos/plain.md').read_text(), '# A\n\nx\n\nno heading here\n')
        self.assertIn('aos/rec.json cannot be forced to md', r.stderr)

    def test_rewrite_and_verify(self):
        self.convert()
        before = (self.dst / 'aos/packs.json').read_bytes()
        dry = run('rewrite', self.map, self.dst, '--dry-run')
        self.assertIn('(dry run, nothing written)', dry.stdout)
        self.assertIn('`aos/me.json#/self_tools`', (self.dst / 'aos/me.md').read_text())
        r = run('rewrite', self.map, self.dst)
        self.assertEqual(r.returncode, 0, r.stderr)
        me = (self.dst / 'aos/me.md').read_text()
        self.assertIn('See `aos/me/self_tools.md` and `aos/me.md#/nope`.', me)                     # longest first; unknown key: file name only
        self.assertIn('aos/me.json#/nope: the map has no such key', r.stderr)
        self.assertIn('Start with `aos/me.md`, then aos/me.md#/What is in your stack.', (self.dst / 'aos/_description.md').read_text())
        self.assertIn('has a space but is not inside backticks', r.stderr)
        readme = (self.dst / 'README.md').read_text()
        self.assertIn('`aos/me.md#/What is in your stack`', readme)
        self.assertIn('knowledge/aos/me.json stays, aos/me.json.bak too, and aos/packs.json#/look', readme)   # not a whole path: untouched
        idx = (self.dst / 'aos/_index.json').read_text()
        self.assertIn('"Who: see aos/me.md"', idx)
        self.assertTrue(idx.startswith('{\n "me.md"'))                                              # the file's own indent kept
        self.assertEqual((self.dst / 'aos/packs.json').read_bytes(), before)                        # nothing to change: not rewritten
        first = run('verify', self.t / 'src', self.dst, self.map)                                  # the planted #/nope is really broken
        self.assertEqual(first.returncode, 1)
        self.assertIn('path not found: aos/me.md: aos/me.md#/nope', first.stdout)
        (self.dst / 'aos/me.md').write_text(me.replace('`aos/me.md#/nope`', '`aos/me.md#/Who am I`'))
        src_me = json.loads((self.t / 'src/aos/me.json').read_text())                               # the same fix in the old text, so the article still compares
        src_me['stack'] = src_me['stack'].replace('`aos/me.json#/nope`', '`aos/me.json#/_description`')
        (self.t / 'src/aos/me.json').write_text(json.dumps(src_me))
        ok = run('verify', self.t / 'src', self.dst, self.map)
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertIn('articles: 1 same, 5 only a trailing newline, 0 different, 0 not found; 0 json pages changed; 0 paths not found', ok.stdout)
        (self.dst / 'aos/clock.md').write_text('Timers in one line.\n\n# Wake me\n\nchanged\n')
        (self.dst / 'aos/me/self_tools.md').unlink()
        (self.dst / 'aos/rec.json').write_text('{"a": "# A\\n\\nx", "n": 4}\n')
        bad = run('verify', self.t / 'src', self.dst, self.map)
        self.assertEqual(bad.returncode, 1)
        self.assertIn('different: aos/clock.json#/wake', bad.stdout)
        self.assertIn('not found: aos/me/self_tools.json#/_description', bad.stdout)
        self.assertIn('a page kept as json changed beyond the rewritten paths: aos/rec.json', bad.stdout)
        self.assertIn('path not found: aos/me.md: aos/me/self_tools.md', bad.stdout)

    def test_arguments(self):
        self.assertIn('ArgumentsBad', run().stderr)
        self.assertIn('CommandUnknown', run('nope', 'a').stderr)
        self.assertIn('FlagUnknown', run('verify', '--x').stderr)
        self.assertIn('ArgumentsBad', run('verify', 'a').stderr)


if __name__ == '__main__':
    unittest.main()
