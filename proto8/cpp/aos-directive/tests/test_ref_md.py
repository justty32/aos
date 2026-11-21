# Check aos-directive reads a $ref to a .md file by the markdown rules (whole text, a heading, a json fence) and that a miss is DirectiveBad.
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

BIN = Path(__file__).resolve().parents[3] / 'bin' / 'aos-directive'
ENV = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}

PAGE = ('Intro.\n\n# Who am I\n\nYou are one proc.\n\n## Files\n\n- body.json: your body\n- plain\n\n'
        '# cfg\n\n```json\n{"a": [1, true], "r": {"$ref": "other.json"}}\n```\n\n# 規劃 A/B\n\n中文\n')


class RefMd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-directive-md-')
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(os.path.realpath(self.tmp.name))
        (self.d / 'page.md').write_text(PAGE, encoding='utf-8')

    def run_(self, doc):
        p = subprocess.run([str(BIN)], input=json.dumps(doc), cwd=self.d, env=ENV, capture_output=True, text=True, timeout=10)
        return p.returncode, json.loads(p.stdout) if p.returncode == 0 else None, p.stderr.strip()

    def test_whole_file_is_its_text(self):
        self.assertEqual(self.run_({'x': {'$ref': 'page.md'}}), (0, {'x': PAGE}, ''))
        self.assertEqual(self.run_({'x': {'$ref': 'page.md#'}}), (0, {'x': PAGE}, ''))

    def test_heading_list_item_and_key(self):
        code, out, _ = self.run_({'w': {'$ref': 'page.md#/Who am I'}, 'f': {'$ref': 'page.md#/Files/body.json'},
                                  'i': {'$ref': 'page.md#/Files/1'}, 'o': {'$ref': 'page.md#/_'}, 'z': {'$ref': 'page.md#/規劃 A~1B'}})
        self.assertEqual(code, 0)
        self.assertEqual(out['w'], '# Who am I\n\nYou are one proc.\n\n## Files\n\n- body.json: your body\n- plain\n')
        self.assertEqual(out['f'], 'your body')
        self.assertEqual(out['i'], 'plain')
        self.assertEqual(out['o'], 'Intro.\n')
        self.assertEqual(out['z'], '# 規劃 A/B\n\n中文\n')

    def test_json_fence_gives_the_value_as_is(self):
        code, out, _ = self.run_({'c': {'$ref': 'page.md#/cfg'}, 'b': {'$ref': 'page.md#/cfg/a/1'}})
        self.assertEqual(code, 0)
        self.assertEqual(out['c'], {'a': [1, True], 'r': {'$ref': 'other.json'}})   # no directives resolved inside md values
        self.assertIs(out['b'], True)

    def test_path_and_prefix_still_apply_to_a_string(self):
        code, out, _ = self.run_({'p': {'$ref': 'page.md#/Files/body.json', '$prefix': '>'}})
        self.assertEqual((code, out), (0, {'p': '>your body'}))

    def test_miss_is_directive_bad(self):
        code, _, err = self.run_({'x': {'$ref': 'page.md#/Who am I/Nope'}})
        self.assertEqual(code, 1)
        self.assertTrue(err.startswith('aos-directive: error: DirectiveBad $ref pointer not found: '), err)
        self.assertIn('(/Who am I has no Nope (it has: _, Files))', err)
        code, _, err = self.run_({'x': {'$ref': 'gone.md'}})
        self.assertEqual(code, 1)
        self.assertIn('DirectiveBad $ref cannot read', err)

    def test_md_reached_from_a_json_file(self):
        (self.d / 'sub').mkdir()
        (self.d / 'sub' / 'conf.json').write_text(json.dumps({'who': {'$ref': '../page.md#/Files/0'}}))
        code, out, _ = self.run_({'$ref': 'sub/conf.json'})
        self.assertEqual((code, out), (0, {'who': 'body.json: your body'}))


if __name__ == '__main__':
    unittest.main()
