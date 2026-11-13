# Verify json_text (expand JSON into line-oriented text for git textconv): shapes, escapes, bad input, arguments, and the core working without json_text_cli.py (git side: test_json_text_git.py).
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
        self.assertEqual(run('--setup', '--nope').returncode, 2)

    def test_core_alone_still_expands(self):
        alone = self.dir / 'json_text.py'           # copied without json_text_cli.py
        shutil.copy(SCRIPT, alone)
        (self.dir / 'g.json').write_text('{"a": "x"}')
        r = subprocess.run([sys.executable, '-B', str(alone), str(self.dir / 'g.json')], capture_output=True)
        self.assertEqual((r.returncode, r.stdout), (0, b'#/a\n  x\n'))
        r = subprocess.run([sys.executable, '-B', str(alone), '--help'], capture_output=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn(b'CliMissing', r.stderr)


if __name__ == '__main__':
    unittest.main()
