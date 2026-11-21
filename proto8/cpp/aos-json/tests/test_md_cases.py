# Run the shared table py/tests/md_path_cases.json (markdown read as JSON) through the built aos-json: get, ls, get --tree on x.md files.
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
BIN = str(ROOT / 'bin' / 'aos-json')
BASE = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}
TABLE = json.loads((ROOT / 'py' / 'tests' / 'md_path_cases.json').read_text(encoding='utf-8'))
sys.path.insert(0, str(ROOT / 'py'))
from aos import mdpath  # noqa: E402  (only to compare the reason text of a miss)


def unesc(seg):
    return seg.replace('~1', '/').replace('~0', '~')


class MdCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='aos-json-md-cases-')
        cls.d = Path(cls.tmp.name)
        for name, text in TABLE['docs'].items():
            (cls.d / (name + '.md')).write_bytes(text.encode('utf-8'))   # as is: no newline translation (crlf doc)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_(self, *argv):
        return subprocess.run([BIN, *argv], env=BASE, cwd=self.d, capture_output=True, text=True, timeout=20)

    def test_cases(self):
        for c in TABLE['cases']:
            spec = c['doc'] + '.md' + ('#' + c['ptr'] if c['ptr'] else '')
            with self.subTest(rule=c['rule'], ptr=c['ptr']):
                if 'ls' in c:
                    p = self.run_('ls', spec)
                    self.assertEqual(p.returncode, 0, p.stderr)
                    rows = p.stdout.splitlines()[1:]
                    self.assertEqual([unesc(r) for r in rows], c['ls'])
                elif c.get('missing'):
                    p = self.run_('get', spec)
                    self.assertEqual(p.returncode, 1)
                    self.assertIn('PointerMissing', p.stderr)
                    text, toks = TABLE['docs'][c['doc']], mdpath.split('x.md#' + c['ptr'])[1]
                    with self.assertRaises(mdpath.Missing) as e:
                        mdpath.get(text, toks)
                    self.assertEqual(p.stderr.strip(), 'aos-json: error: PointerMissing no such pointer: %s (%s)' % (spec, e.exception.reason))
                else:
                    p = self.run_('get', spec)
                    self.assertEqual(p.returncode, 0, p.stderr)
                    got = json.loads(p.stdout)
                    self.assertEqual(got, c['get'])
                    self.assertIs(type(got), type(c['get']))

    def test_trees(self):
        for c in TABLE['trees']:
            with self.subTest(rule=c['rule']):
                p = self.run_('get', '--tree', c['doc'] + '.md')
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertEqual(json.loads(p.stdout), c['tree'])
                self.assertEqual(list(json.loads(p.stdout)), list(c['tree']))   # heading order kept


if __name__ == '__main__':
    unittest.main()
