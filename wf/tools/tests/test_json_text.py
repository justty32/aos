# Verify json_text (expand JSON into line-oriented text for git textconv): shapes, escapes, bad input, --setup, and a real git diff on a throwaway repo.
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


def run(*args, data=None, cwd=None):
    return subprocess.run([sys.executable, '-B', str(SCRIPT), *args], input=data, capture_output=True, cwd=cwd)


class JsonTextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def text(self, obj_or_raw, *flags):
        raw = obj_or_raw if isinstance(obj_or_raw, (bytes, str)) else json.dumps(obj_or_raw, ensure_ascii=False, indent=1)
        path = self.dir / 'f.json'
        path.write_bytes(raw.encode('utf-8') if isinstance(raw, str) else raw)
        r = run(*flags, str(path), cwd='/')
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.decode('utf-8'), r.stderr.decode('utf-8')

    def test_nested_order_and_scalars(self):
        out, err = self.text('{"z": {"b": "x", "a": [1, 2.50, true, null]}, "e": "", "o": {}, "l": [], "n": -0.0}')
        self.assertEqual(err, '')
        self.assertEqual(out, '#/z/b\n  x\n#/z/a/- = 1\n#/z/a/- = 2.50\n#/z/a/- = true\n#/z/a/- = null\n'
                              '#/e = ""\n#/o = {}\n#/l = []\n#/n = -0.0\n')

    def test_objects_in_arrays_and_multiline(self):
        out, _ = self.text({'records': [{'date': 'd1', 'note': 'a\nb\n'}, {'date': 'd2'}]})
        self.assertEqual(out, '#/records/-/date\n  d1\n#/records/-/note\n  a\n  b\n  \n#/records/-/date\n  d2\n')

    def test_pointer_escapes_and_non_ascii(self):
        out, _ = self.text({'a/b': {'~x': 'v'}, '中文': '使用者「好」'})
        self.assertIn('#/a~1b/~0x\n  v\n', out)
        self.assertIn('#/中文\n  使用者「好」\n', out)

    def test_control_chars_crlf_tab(self):
        out, _ = self.text({'s': 'a\r\nb\tc', 'k\n': 1})
        self.assertIn('#/s\n  a\\u000d\n  b\tc\n', out)
        self.assertIn('#/k\\u000a = 1\n', out)
        self.assertTrue(out.endswith('\n') and not out.endswith('\n\n'))

    def test_directive_objects_one_line(self):
        out, _ = self.text({'x': {'$ref': 'a.json#/b'}, 'y': {'$env': 'HOME', 'path': 'p'}})
        self.assertEqual(out, '#/x = {"$ref": "a.json#/b"}\n#/y = {"$env": "HOME", "path": "p"}\n')

    def test_long_line_folds_at_sentence_ends(self):
        line = ' '.join('Sentence number %d is here.' % i for i in range(8))
        out, _ = self.text({'s': line + '\n第一句。第二句很長' + '字' * 100 + '。第三句'})
        lines = out.split('\n')
        self.assertEqual(lines[1], '  Sentence number 0 is here.')
        self.assertEqual(lines[2], '  ↪ Sentence number 1 is here.')
        self.assertIn('  第一句。', lines)
        self.assertIn('  ↪ 第三句', lines)

    def test_long_line_keeps_list_number_with_its_text(self):
        tail = ' '.join('Sentence number %d is here.' % i for i in range(5))
        lines = ['1. First item is here. ' + tail, '12. Twelfth item. ' + tail, '   3. Indented item. ' + tail,
                 '1.2. Nested item. ' + tail, '4) Paren item. ' + tail]
        out, _ = self.text({'s': '\n'.join(lines)})
        got = out.split('\n')
        for head in ['  1. First item is here.', '  12. Twelfth item.', '     3. Indented item.',
                     '  1.2. Nested item.', '  4) Paren item.']:
            self.assertIn(head, got)
        for bad in ['  1.', '  12.', '     3.', '  1.2.', '  ↪ First item is here.', '  ↪ Twelfth item.',
                    '  ↪ Indented item.', '  ↪ Nested item.']:
            self.assertNotIn(bad, got)
        self.assertIn('  ↪ Sentence number 0 is here.', got)    # the rest of the line still folds

    def test_whole_file_is_a_string_and_duplicates_and_bom(self):
        out, _ = self.text('"one\\ntwo"')
        self.assertEqual(out, '#\n  one\n  two\n')
        out, _ = self.text('﻿{"a": 1, "a": 2}')
        self.assertEqual(out, '#/a = 1\n#/a = 2\n')

    def test_md(self):
        out, _ = self.text({'a': 'x\ny', 'n': 1}, '--md')
        self.assertEqual(out, '## `#/a`\n\nx\ny\n\n- `#/n = 1`\n')

    def test_bad_json_passes_raw_through(self):
        path = self.dir / 'f.json'
        for raw in (b'{"a": 1,', b'', b'\xff\xfe not utf8', b'[' * 100000):
            path.write_bytes(raw)
            r = run(str(path))
            self.assertEqual((r.returncode, r.stdout), (0, raw))
            self.assertEqual(r.stderr, b'json_text: warning: not valid JSON, showing raw text\n')

    def test_arguments(self):
        self.assertEqual(run().returncode, 2)
        self.assertIn(b'FlagUnknown', run('--nope').stderr)
        self.assertEqual(run(str(self.dir / 'missing.json')).returncode, 1)
        self.assertIn(b'usage', run('--help').stdout)
        self.assertEqual(run('-', data=b'{"a": true}').stdout, b'#/a = true\n')


@unittest.skipUnless(shutil.which('git'), 'git not installed')
class GitTests(unittest.TestCase):
    """A throwaway repo with its own copy of the script; never touches this repo's git config."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'repo'
        (self.root / 'tools').mkdir(parents=True)
        shutil.copy(SCRIPT, self.root / 'tools' / 'json_text.py')
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
