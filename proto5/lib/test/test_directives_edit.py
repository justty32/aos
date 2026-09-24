"""cli/aos-directives（人格分節編輯＋resolve／check）與 cli/aos-json（人用的 JSON Pointer 改檔）。tool-era T3 隊。

都當子行程跑，驗退出碼（0 成功、1 錯、2 用法錯）、錯誤一行 `指令: 代號: 白話`、檔案真的改對。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PROTO5 = os.path.dirname(os.path.dirname(HERE))
CLI = os.path.join(PROTO5, 'cli')

PERSONA = '你是助手。\n\n# 角色\n\n幫人寫程式。\n\n## 規則\n\n- 一次一個工具\n\n# 語氣\n\n白話。\n'


class CliCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix='aos-directives-')
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def cli(self, name, *args, code=0, stdin=''):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', AOSTEST_X='from-env')
        p = subprocess.run([sys.executable, os.path.join(CLI, name), *args], cwd=self.root, env=env,
                           input=stdin, capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, code, p.stdout + p.stderr)
        return p

    def path(self, *parts):
        return os.path.join(self.root, *parts)

    def put(self, rel, text):
        os.makedirs(os.path.dirname(self.path(rel)), exist_ok=True)
        with open(self.path(rel), 'w', encoding='utf-8') as f:
            f.write(text)

    def read(self, rel):
        with open(self.path(rel), encoding='utf-8') as f:
            return f.read()


class PersonaTests(CliCase):
    def setUp(self):
        super().setUp()
        self.cli('aos-agent', 'init', '--target', 'amy')
        self.write_persona(PERSONA)

    def write_persona(self, content, rel='amy/prompts/system.json'):
        self.put(rel, json.dumps({'content': content}, ensure_ascii=False))

    def persona(self, rel='amy/prompts/system.json'):
        return json.loads(self.read(rel))['content']

    def d(self, *args, **kw):
        return self.cli('aos-directives', *args, '--target', 'amy', **kw)

    def test_ls_and_show(self):
        out = self.d('ls').stdout
        self.assertIn('  0  （開頭，沒有標題）', out)
        self.assertIn('  1  # 角色', out)
        self.assertIn('  2    ## 規則', out)
        self.assertIn('  3  # 語氣', out)
        self.assertEqual(self.d('show', '規則').stdout, '## 規則\n\n- 一次一個工具\n\n')
        self.assertEqual(self.d('show', '0').stdout, '你是助手。\n\n')
        self.assertEqual(self.d('show').stdout, PERSONA)

    def test_set_keeps_heading_and_saves_version(self):
        out = self.d('set', '# 語氣', '--text', '簡短、直接。').stdout
        self.assertIn('改了第 3 節 # 語氣的內容', out)
        self.assertIn('下一次問模型就用新的人格', out)
        self.assertTrue(self.persona().endswith('# 語氣\n\n簡短、直接。\n'))
        self.assertIn('存了 1 個舊版本', self.d('ls').stdout)

    def test_set_from_stdin_and_prelude(self):
        self.d('set', '0', '--file', '-', stdin='你是 coding agent。\n')
        self.assertTrue(self.persona().startswith('你是 coding agent。\n\n# 角色'))

    def test_add_and_rm(self):
        self.d('add', '## 工具', '--text', '先讀再改。', '--after', '規則')
        self.assertIn('- 一次一個工具\n\n## 工具\n\n先讀再改。\n\n# 語氣', self.persona())
        self.d('add', '# 結尾')
        self.assertTrue(self.persona().endswith('白話。\n\n# 結尾\n'))
        self.d('add', '## 工具', code=1)
        self.d('rm', '角色')
        self.assertEqual(self.persona(), '你是助手。\n\n# 語氣\n\n白話。\n\n# 結尾\n')

    def test_versions_and_revert(self):
        self.d('set', '語氣', '--text', 'A')
        self.d('set', '語氣', '--text', 'B')
        out = self.d('versions').stdout
        ids = [line.split()[0] for line in out.splitlines()[1:]]
        self.assertEqual(len(ids), 2)
        self.d('revert')
        self.assertTrue(self.persona().endswith('A\n'))
        self.d('revert', ids[-1])
        self.assertEqual(self.persona(), PERSONA)
        self.assertEqual(len(self.d('versions').stdout.splitlines()) - 1, 4)   # 還原本身也存了舊版
        err = self.d('revert', '123', code=1).stderr
        self.assertIn('aos-directives: NotFound:', err)

    def test_export_import_roundtrip(self):
        self.d('export', '--out', 'p.md')
        self.assertEqual(self.read('amy/p.md') if os.path.exists(self.path('amy/p.md')) else self.read('p.md'),
                         PERSONA)
        self.put('p.md', PERSONA.replace('白話。', '白話、簡短。'))
        self.d('import', 'p.md')
        self.assertIn('白話、簡短。', self.persona())
        self.assertIn('白話、簡短。', self.d('export').stdout)

    def test_no_change_no_version(self):
        out = self.d('set', '語氣', '--text', '白話。').stdout
        self.assertTrue(out.startswith('沒改'), out)
        self.assertIn('還沒有舊版本', self.d('ls').stdout)

    def test_errors(self):
        self.put('amy/prompts/dup.json', json.dumps({'content': '# A\n1\n# A\n2\n'}))
        info = json.loads(self.read('amy/info.json'))
        info['system'] = 'prompts/dup.json'
        self.put('amy/info.json', json.dumps(info))
        self.assertIn('NotUnique', self.d('show', 'A', code=1).stderr)
        self.assertIn('NotFound', self.d('show', '9', code=1).stderr)
        self.assertIn('NotFound', self.d('show', 'Z', code=1).stderr)
        self.put('amy/prompts/dup.json', json.dumps({'content': {'$env': 'AOSTEST_X'}}))
        self.assertIn('FieldTypeMismatch', self.d('set', '0', '--text', 'x', code=1).stderr)
        self.assertIn('NotAnAgent', self.cli('aos-directives', 'ls', '--target', 'nobody', code=1).stderr)

    def test_file_errors_are_one_line(self):
        """不存在的家、寫不進的 export 目的地：一行錯、退 1、沒有 Traceback（審查 M6）。"""
        for args in (['set', '0', '--text', 'x', '--target', 'nobody'], ['export', '--out', 'no/such/dir/p.md',
                                                                         '--target', 'amy']):
            err = self.cli('aos-directives', *args, code=1).stderr
            self.assertNotIn('Traceback', err)
            self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.assertFalse(os.path.exists(self.path('nobody')))

    def test_usage(self):
        self.d('set', '語氣', code=2)
        self.d('set', '語氣', '--text', 'a', '--file', 'b', code=2)
        self.d('ls', 'x', code=2)
        self.d('export', '--after', 'x', code=2)
        self.cli('aos-directives', 'zap', code=2)
        self.assertIn('用法', self.cli('aos-directives', '--help').stdout)

    def test_missing_persona_file_then_add(self):
        os.remove(self.path('amy/prompts/system.json'))
        self.assertIn('（0 字）', self.d('ls').stdout)
        self.d('add', '# 角色', '--text', '新的')
        self.assertEqual(self.persona(), '# 角色\n\n新的\n')


class ResolveTests(CliCase):
    def test_resolve_and_check(self):
        self.put('b.json', '{"x": {"y": 7}}')
        self.put('a.json', json.dumps({'env': {'$env': 'AOSTEST_X'}, 'ref': {'$ref': 'b.json#/x'},
                                       'fmt': {'$fmt': {'$val': '${a}-${b}', 'a': 'p', 'b': {'$env': 'AOSTEST_X'}}},
                                       'opt': {'$opt': 'ro', '$val': {'$ref': 'b.json#/x/y'}}}))
        out = json.loads(self.cli('aos-directives', 'resolve', 'a.json').stdout)
        self.assertEqual(out, {'env': 'from-env', 'ref': {'y': 7}, 'fmt': 'p-from-env',
                               'opt': {'$opt': 'ro', '$val': 7}})
        self.assertEqual(self.cli('aos-directives', 'resolve', 'a.json', '--pointer', '/ref').stdout.strip(),
                         '{\n  "y": 7\n}')
        self.assertIn('ok', self.cli('aos-directives', 'check', 'a.json').stdout)
        self.put('bad.json', '{"r": {"$ref": "nope.json"}}')
        err = self.cli('aos-directives', 'check', 'bad.json', code=1).stderr
        self.assertTrue(err.startswith('aos-directives: '), err)
        self.cli('aos-directives', 'check', 'a.json', '--target', 'x', code=2)


class AosJsonTests(CliCase):
    def test_get_set_and_sha(self):
        self.put('c.json', '{\n    "a": [1]\n}\n')
        out = self.cli('aos-json', 'get', 'c.json', '/a').stdout
        sha = out.split('sha=')[1].strip()
        self.cli('aos-json', 'append', 'c.json', '/a', '"名"', '--expect-sha', sha)
        self.assertEqual(self.read('c.json'), '{\n    "a": [\n        1,\n        "名"\n    ]\n}\n')
        self.assertIn('Conflict', self.cli('aos-json', 'del', 'c.json', '/a/0', '--expect-sha', sha, code=1).stderr)
        self.cli('aos-json', 'merge', 'c.json', '', '-', stdin='{"b": {"c": 1}}')
        self.assertEqual(json.loads(self.read('c.json'))['b'], {'c': 1})

    def test_usage_and_errors(self):
        self.put('c.json', '{"a": 1}')
        self.cli('aos-json', 'set', 'c.json', '/a', 'abc', code=2)            # 字串沒引號
        self.cli('aos-json', 'get', 'c.json', '/a', '--check-directives', code=2)
        self.cli('aos-json', 'zap', code=2)
        self.assertIn('PointerNotFound', self.cli('aos-json', 'get', 'c.json', '/b', code=1).stderr)
        self.assertIn('NotFound', self.cli('aos-json', 'get', 'none.json', code=1).stderr)

    def test_write_error_is_one_line(self):
        self.put('f', 'x')
        err = self.cli('aos-json', 'set', 'f/x.json', '', '1', code=1).stderr
        self.assertNotIn('Traceback', err)
        self.assertTrue(err.startswith('aos-json: '), err)

    def test_check_directives(self):
        self.put('i.json', '{"cwd": "."}')
        err = self.cli('aos-json', 'set', 'i.json', '/cwd', '{"$ref": "missing.json"}', '--check-directives',
                       code=1).stderr
        self.assertTrue(err.startswith('aos-json: '), err)
        self.assertEqual(self.read('i.json'), '{"cwd": "."}')
        self.put('p.json', '{"x": "/tmp"}')
        self.cli('aos-json', 'set', 'i.json', '/cwd', '{"$ref": "p.json#/x"}', '--check-directives')
        self.assertEqual(json.loads(self.read('i.json')), {'cwd': {'$ref': 'p.json#/x'}})


if __name__ == '__main__':
    unittest.main()
