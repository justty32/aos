# Verify json_text with git: --setup and textconv on a throwaway repo holding copies of json_text.py and json_text_cli.py (never this repo's git config).
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).parents[1]
SCRIPT = TOOLS / 'json_text.py'
CLI = TOOLS / 'json_text_cli.py'


@unittest.skipUnless(shutil.which('git'), 'git not installed')
class GitTests(unittest.TestCase):
    """A throwaway repo with its own copy of the script; never touches this repo's git config."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'repo'
        (self.root / 'tools').mkdir(parents=True)
        shutil.copy(SCRIPT, self.root / 'tools' / 'json_text.py')
        shutil.copy(CLI, self.root / 'tools' / 'json_text_cli.py')
        env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
        env.update(GIT_CONFIG_NOSYSTEM='1', HOME=str(self.root.parent), GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t',
                   GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@t')
        self.env = env
        self.git('init', '-q')
        (self.root / '.gitattributes').write_text('data/*.json diff=json_text\n')
        (self.root / 'data').mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args, cwd=None):
        r = subprocess.run(['git', *args], cwd=cwd or self.root, env=self.env, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def setup_driver(self, *flags):
        return subprocess.run([sys.executable, '-B', str(self.root / 'tools' / 'json_text.py'), '--setup', *flags],
                              cwd='/', env=self.env, capture_output=True, text=True)

    def commit(self, name, obj):
        (self.root / 'data' / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        self.git('add', '-A')
        self.git('commit', '-qm', 'c')

    def changed(self, name, obj, *flags):
        """Write obj, return (added, removed) line counts of `git diff` for that file."""
        (self.root / 'data' / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        out = self.git('diff', *flags, '--', name, cwd=self.root / 'data')   # from a subfolder: textconv still runs at the top
        body = [line for line in out.split('\n') if line and line[0] in '+-' and not line.startswith(('+++', '---'))]
        return sum(1 for line in body if line[0] == '+'), sum(1 for line in body if line[0] == '-')

    def test_setup_is_idempotent_and_check_only_looks(self):
        r = self.setup_driver('--check')
        self.assertEqual(r.returncode, 1)
        self.assertNotIn('json_text', (self.root / '.git' / 'config').read_text())
        r = self.setup_driver()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('was not set', r.stdout)
        value = self.git('config', '--local', '--get', 'diff.json_text.textconv').strip()
        self.assertRegex(value, r'^python3? -B tools/json_text\.py$')
        r = self.setup_driver()
        self.assertIn('already set', r.stdout)
        self.assertEqual(self.setup_driver('--check').returncode, 0)

    def test_one_word_in_a_long_string(self):
        para = '\n'.join('Line %d says something about the topic. It goes on a while.' % i for i in range(40))
        self.commit('k.json', {'a': {'body': para, 'n': 1}})
        edited = {'a': {'body': para.replace('Line 20 says', 'Line 20 tells'), 'n': 1}}
        self.assertEqual(self.changed('k.json', edited), (1, 1))   # before setup: whole value line replaced, too
        self.assertEqual(self.changed('k.json', edited, '--no-textconv'), (1, 1))
        plain = self.git('diff', '--', 'data/k.json')
        self.assertGreater(len(plain), len(para))                   # ...and it shows the whole value
        self.setup_driver()
        self.assertEqual(self.changed('k.json', edited), (1, 1))
        shown = self.git('diff', '--', 'data/k.json')
        self.assertIn('+  Line 20 tells something about the topic.', shown)
        self.assertLess(len(shown), len(para) // 3)       # only the hunk around that line
        self.assertEqual(self.changed('k.json', edited, '--no-textconv'), (1, 1))
        self.assertIn('"body": "Line 0', self.git('diff', '--no-textconv', '--', 'data/k.json'))

    def test_insert_record_and_list_item(self):
        records = [{'date': 'd%d' % i, 'decision': 'Decision %d.' % i, 'why': 'because %d\nand more' % i} for i in range(10)]
        items = ['item %d' % i for i in range(10)]
        self.commit('r.json', {'_description': 'records, newest first', 'records': records, 'items': items})
        self.setup_driver()
        new = {'date': 'd99', 'decision': 'New one.', 'why': 'fresh'}
        added = {'_description': 'records, newest first', 'records': [new] + records,
                 'items': items[:5] + ['item new'] + items[5:]}
        plus, minus = self.changed('r.json', added)
        self.assertEqual(minus, 0)
        self.assertEqual(plus, 6 + 2)          # 3 fields x (header + line), one list item (header + line)
        plus, minus = self.changed('r.json', {**added, 'records': records[:3] + records[4:]})
        self.assertEqual((plus, minus), (2, 7))  # the list item added, record 3 removed (3 headers + 4 lines)


if __name__ == '__main__':
    unittest.main()
