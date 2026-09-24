"""proto5/tools/files/：json_edit、md_section 兩支工具（tool-era T3 隊）。

照 test_tools_base.py 的做法：把工具包複製進假 agent 家、當子行程跑（cwd＝家、stdin＝arguments）。
另外驗：files／wf 包的 _common.py 跟 base 那份逐字一樣（根目錄一律照 base 算，不另外算）；
描述字數（catalog 隊 3 驗收 ⑦）；aos-agent tools add files 裝得起來。
"""
import filecmp
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PROTO5 = os.path.dirname(os.path.dirname(HERE))
TOOLS = os.path.join(PROTO5, 'tools')
PACK = os.path.join(TOOLS, 'files')
CLI = os.path.join(PROTO5, 'cli')


def desc_chars(tools):
    """function.description＋每個參數的 description 字元數。"""
    n = 0
    for t in tools:
        f = t['function']
        n += len(f.get('description', ''))
        for p in f.get('parameters', {}).get('properties', {}).values():
            n += len(p.get('description', ''))
    return n


class FilesCase(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix='aos-tools-files-')
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        shutil.copytree(PACK, os.path.join(self.home, 'tools', 'files'),
                        ignore=shutil.ignore_patterns('__pycache__'))
        self.ws = os.path.join(self.home, 'workspace')
        os.makedirs(self.ws)

    def put(self, rel, content, base=None):
        full = os.path.join(base or self.ws, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, 'w', encoding='utf-8', newline='') as f:
            f.write(content)
        return full

    def get(self, rel, base=None):
        with open(os.path.join(base or self.ws, rel), encoding='utf-8', newline='') as f:
            return f.read()

    def config(self, obj):
        with open(os.path.join(self.home, 'tools', 'files', 'config.json'), 'w') as f:
            json.dump(obj, f)

    def agent_home(self, **info):
        """把 self.home 變成像樣的 agent 家（info.json＋人格＋工具檔登記）。"""
        doc = {'_metainfo': {'_type': 'llm_agent', '_version': 1}, 'llm': {'model': 'm'},
               'tools': ['tools/files.json']}
        doc.update(info)
        self.put('info.json', json.dumps(doc), base=self.home)
        shutil.copy(os.path.join(PACK, 'files.json'), os.path.join(self.home, 'tools', 'files.json'))
        self.put('prompts/system.json', '{"content": "hi"}', base=self.home)

    def run_tool(self, name, args, env=None, raw=None):
        full_env = {k: v for k, v in os.environ.items() if k != 'AOS_TOOL_ROOT'}
        full_env['PYTHONDONTWRITEBYTECODE'] = '1'
        full_env.update(env or {})
        p = subprocess.run([os.path.join(self.home, 'tools', 'files', name)],
                           input=raw if raw is not None else json.dumps(args, ensure_ascii=False),
                           cwd=self.home, capture_output=True, text=True, encoding='utf-8', env=full_env,
                           timeout=20)
        last = None
        if p.stdout.strip():
            try:
                last = json.loads(p.stdout.rstrip('\n').rsplit('\n', 1)[-1])
            except ValueError:
                pass
        return p.returncode, p.stdout, last

    def ok(self, name, args, **kw):
        code, out, _ = self.run_tool(name, args, **kw)
        self.assertEqual(code, 0, out)
        return out

    def err(self, name, args, error, **kw):
        code, out, j = self.run_tool(name, args, **kw)
        self.assertEqual(code, 1, out)
        self.assertIsInstance(j, dict, out)
        self.assertEqual(j.get('error'), error, out)
        self.assertEqual(len(out.rstrip('\n').split('\n')), 1, '錯誤只印一行 JSON：%r' % out)
        return j

    def sha_of(self, out):
        return [w for w in out.split() if w.startswith('sha=')][-1][4:]


class CommonSyncTests(unittest.TestCase):
    def test_common_is_base_copy(self):
        """files／wf 包的 _common.py 要跟 base 逐字一樣：根目錄照 base 算、跟著 base 變。
        base 那份改了＝這裡失敗：cp proto5/tools/base/_common.py proto5/tools/{files,wf}/。"""
        base = os.path.join(TOOLS, 'base', '_common.py')
        for pack in ('files', 'wf'):
            mine = os.path.join(TOOLS, pack, '_common.py')
            if pack == 'wf' and not os.path.exists(mine):
                continue
            self.assertTrue(filecmp.cmp(base, mine, shallow=False),
                            '%s 跟 base/_common.py 不一樣；照 docstring 複製一份' % mine)

    def test_descriptions_short(self):
        with open(os.path.join(PACK, 'files.json'), encoding='utf-8') as f:
            files = json.load(f)
        self.assertLess(desc_chars(files), 1300)
        wf = os.path.join(TOOLS, 'wf', 'wf.json')
        if os.path.exists(wf):
            with open(wf, encoding='utf-8') as f:
                self.assertLess(desc_chars(files) + desc_chars(json.load(f)), 3000)


class JsonEditTests(FilesCase):
    def test_get_returns_value_and_sha(self):
        self.put('a.json', '{"a": {"b": [1, 2]}}\n')
        out = self.ok('json_edit', {'path': 'a.json', 'pointer': '/a/b/1'})
        self.assertTrue(out.startswith('2\nsha='), out)

    def test_five_ops(self):
        self.put('a.json', '{\n  "a": {"b": [1]},\n  "c": 1\n}\n')
        self.ok('json_edit', {'path': 'a.json', 'op': 'set', 'pointer': '/a/x', 'value': {'y': True}})
        self.ok('json_edit', {'path': 'a.json', 'op': 'append', 'pointer': '/a/b', 'value': 2})
        self.ok('json_edit', {'path': 'a.json', 'op': 'set', 'pointer': '/a/b/-', 'value': 3})
        self.ok('json_edit', {'path': 'a.json', 'op': 'del', 'pointer': '/c'})
        self.ok('json_edit', {'path': 'a.json', 'op': 'merge', 'pointer': '/a',
                              'value': {'x': None, 'n': {'m': 1}}})
        self.assertEqual(json.loads(self.get('a.json')), {'a': {'b': [1, 2, 3], 'n': {'m': 1}}})

    def test_set_whole_document_creates_file(self):
        out = self.ok('json_edit', {'path': 'new/x.json', 'op': 'set', 'pointer': '', 'value': {'名': 1}})
        self.assertIn('sha=', out)
        self.assertEqual(self.get('new/x.json'), '{\n  "名": 1\n}\n')

    def test_missing_file_for_other_ops(self):
        self.err('json_edit', {'path': 'no.json', 'op': 'set', 'pointer': '/a', 'value': 1}, 'NotFound')

    def test_bad_pointers(self):
        self.put('a.json', '{"a": [1], "s": "x"}')
        self.err('json_edit', {'path': 'a.json', 'pointer': 'a'}, 'BadPointer')
        self.err('json_edit', {'path': 'a.json', 'pointer': '/a~2'}, 'BadPointer')
        j = self.err('json_edit', {'path': 'a.json', 'pointer': '/zz'}, 'PointerNotFound')
        self.assertIn('"a"', j['message'])
        self.err('json_edit', {'path': 'a.json', 'pointer': '/a/5'}, 'PointerNotFound')
        self.err('json_edit', {'path': 'a.json', 'pointer': '/a/01'}, 'PointerNotFound')
        self.err('json_edit', {'path': 'a.json', 'pointer': '/s/x'}, 'PointerNotFound')
        self.err('json_edit', {'path': 'a.json', 'op': 'set', 'pointer': '/q/r', 'value': 1}, 'PointerNotFound')

    def test_escaped_pointer_tokens(self):
        self.put('a.json', '{"a/b": {"~t": 1}}')
        self.assertTrue(self.ok('json_edit', {'path': 'a.json', 'pointer': '/a~1b/~0t'}).startswith('1\n'))

    def test_type_mismatch_and_argument_errors(self):
        self.put('a.json', '{"a": {}, "l": []}')
        self.err('json_edit', {'path': 'a.json', 'op': 'append', 'pointer': '/a', 'value': 1}, 'TypeMismatch')
        self.err('json_edit', {'path': 'a.json', 'op': 'merge', 'pointer': '/l', 'value': {}}, 'TypeMismatch')
        self.err('json_edit', {'path': 'a.json', 'op': 'merge', 'pointer': '/a', 'value': 1}, 'TypeMismatch')
        self.err('json_edit', {'path': 'a.json', 'op': 'set', 'pointer': '/a'}, 'BadArguments')
        self.err('json_edit', {'path': 'a.json', 'op': 'get', 'value': 1}, 'BadArguments')
        self.err('json_edit', {'path': 'a.json', 'op': 'del', 'pointer': ''}, 'BadArguments')
        self.err('json_edit', {'path': 'a.json', 'op': 'rename'}, 'BadArguments')
        self.err('json_edit', {'op': 'get'}, 'BadArguments')

    def test_invalid_result_not_written(self):
        """NaN 進得了 arguments（Python 的 json 認），但寫出去不是合法 JSON：拒絕、原檔不動。"""
        self.put('a.json', '{"a": 1}')
        self.err('json_edit', None, 'BadArguments',
                 raw='{"path": "a.json", "op": "set", "pointer": "/a", "value": NaN}')
        self.assertEqual(self.get('a.json'), '{"a": 1}')

    def test_broken_file_refused_untouched(self):
        self.put('a.json', '{"a": 1,}')
        self.err('json_edit', {'path': 'a.json', 'op': 'set', 'pointer': '/a', 'value': 2}, 'JsonSyntax')
        self.assertEqual(self.get('a.json'), '{"a": 1,}')

    def test_expect_sha_conflict_and_retry_does_not_double(self):
        self.put('a.json', '{"l": []}')
        sha = self.sha_of(self.ok('json_edit', {'path': 'a.json'}))
        req = {'path': 'a.json', 'op': 'append', 'pointer': '/l', 'value': 1, 'expect_sha': sha}
        self.ok('json_edit', req)
        j = self.err('json_edit', req, 'Conflict')    # 同一個請求重送：不會多 append 一次
        self.assertEqual(json.loads(self.get('a.json')), {'l': [1]})
        self.ok('json_edit', dict(req, expect_sha=j['sha']))
        self.assertEqual(json.loads(self.get('a.json')), {'l': [1, 1]})

    def test_concurrent_writers_do_not_overwrite(self):
        """兩個寫者拿同一個 sha 同時送：鎖內重讀再比，只有一個成功，另一個 Conflict（審查 M2）。"""
        self.put('a.json', '{"l": []}')
        sha = self.sha_of(self.ok('json_edit', {'path': 'a.json'}))
        exe = os.path.join(self.home, 'tools', 'files', 'json_edit')
        env = {k: v for k, v in os.environ.items() if k != 'AOS_TOOL_ROOT'}
        procs = [subprocess.Popen([exe], stdin=subprocess.PIPE, stdout=subprocess.PIPE, cwd=self.home, env=env,
                                  text=True) for _ in range(6)]
        for i, p in enumerate(procs):
            p.stdin.write(json.dumps({'path': 'a.json', 'op': 'append', 'pointer': '/l', 'value': i,
                                      'expect_sha': sha}))
            p.stdin.close()
        codes = [p.wait(timeout=20) for p in procs]
        for p in procs:
            p.stdout.close()
        self.assertEqual(codes.count(0), 1, codes)
        self.assertEqual(len(json.loads(self.get('a.json'))['l']), 1)

    def test_same_set_twice_is_no_change(self):
        self.put('a.json', '{"a": 1}')
        before = os.stat(os.path.join(self.ws, 'a.json')).st_ino
        out = self.ok('json_edit', {'path': 'a.json', 'op': 'set', 'pointer': '/a', 'value': 1})
        self.assertTrue(out.startswith('no change'), out)
        self.assertEqual(os.stat(os.path.join(self.ws, 'a.json')).st_ino, before)

    def test_style_kept(self):
        cases = {
            'four.json': ('{\n    "a": 1\n}\n', '{\n    "a": 2\n}\n'),
            'tab.json': ('{\n\t"a": 1\n}', '{\n\t"a": 2\n}'),
            'compact.json': ('{"a":1,"b":[1,2]}', '{"a":2,"b":[1,2]}'),
            'spaced.json': ('{"a": 1, "b": [1, 2]}\n', '{"a": 2, "b": [1, 2]}\n'),
            'escaped.json': ('{"a": 1, "n": "\\u540d"}\n', '{"a": 2, "n": "\\u540d"}\n'),
            'raw.json': ('{"a": 1, "n": "名"}\n', '{"a": 2, "n": "名"}\n'),
            'crlf.json': ('{\r\n  "a": 1\r\n}\r\n', '{\r\n  "a": 2\r\n}\r\n'),
        }
        for name, (before, after) in cases.items():
            self.put(name, before)
            self.ok('json_edit', {'path': name, 'op': 'set', 'pointer': '/a', 'value': 2})
            self.assertEqual(self.get(name), after, name)

    def test_outside_root(self):
        self.put('x.json', '{}', base=self.home)
        self.err('json_edit', {'path': '../x.json'}, 'OutsideRoot')
        os.symlink(os.path.join(self.home, 'x.json'), os.path.join(self.ws, 'link.json'))
        self.err('json_edit', {'path': 'link.json'}, 'OutsideRoot')

    def test_leftover_tmp_from_killed_write_is_harmless(self):
        """KILL 在「暫存檔寫好、還沒 rename」的窗口：留下 .a.json.*.aos-tmp，原檔完整；重跑同一行照樣成功。"""
        self.put('a.json', '{"a": 1}')
        self.put('.a.json.xyz.aos-tmp', '{"a": ')
        self.ok('json_edit', {'path': 'a.json', 'op': 'set', 'pointer': '/a', 'value': 2})
        self.assertEqual(json.loads(self.get('a.json')), {'a': 2})


class TrustTests(FilesCase):
    """沒關牢時（沒 AOS_TOOL_ROOT）照 info.json 的實際設定擋信任資料；根目錄故意設成整個家。"""

    def setUp(self):
        super().setUp()
        self.config({'root': '.'})

    def test_fixed_trusted_files(self):
        self.agent_home()
        for path in ('info.json', 'prompts/system.json', 'tools/files.json', 'state.json', 'access.json'):
            self.put(path, '{}', base=self.home) if not os.path.exists(os.path.join(self.home, path)) else None
            self.err('json_edit', {'path': path, 'op': 'set', 'pointer': '/x', 'value': 1}, 'TrustedData')
        self.err('json_edit', {'path': 'tools/files/config.json', 'op': 'set', 'pointer': '/root', 'value': '/'},
                 'TrustedData')

    def test_ref_and_custom_paths(self):
        """人格用 $ref 指到 workspace 裡的檔、記憶用自訂路徑、工具列一個家外的資料夾：都擋。"""
        self.put('persona.json', '{"content": "p"}')
        self.put('mem/h.json', '[]')
        self.put('extra/t.json', json.dumps([{'type': 'function', 'function': {'name': 'z', 'parameters': {}},
                                              '_meta': {'argv': ['workspace/bin/z']}}]))
        self.put('bin/z', '#!/bin/sh\n')
        self.put('bin/helper.json', '{}')
        self.put('free.json', '{"a": 1}')
        self.agent_home(system={'$ref': 'workspace/persona.json'}, history='workspace/mem/h.json',
                        tools=['tools/files.json', {'$opt': {'only': ['z']}, '$val': 'workspace/extra'}])
        for path in ('workspace/persona.json', 'workspace/mem/h.json', 'workspace/extra/t.json',
                     'workspace/bin/helper.json'):
            j = self.err('json_edit', {'path': path, 'op': 'set', 'pointer': '/x', 'value': 1}, 'TrustedData')
            self.assertIn('not something you can fix', j['message'])
        self.ok('json_edit', {'path': 'workspace/free.json', 'op': 'set', 'pointer': '/a', 'value': 2})

    def test_nested_ref_and_symlink(self):
        self.put('p2.json', '{"content": "deep"}')
        self.put('p1.json', '{"content": {"$ref": "p2.json#/content"}}')
        self.agent_home(system={'$ref': 'workspace/p1.json'})
        self.err('json_edit', {'path': 'workspace/p2.json', 'op': 'set', 'pointer': '/content', 'value': 1},
                 'TrustedData')
        os.symlink(os.path.join(self.home, 'info.json'), os.path.join(self.ws, 'alias.json'))
        self.err('json_edit', {'path': 'workspace/alias.json', 'op': 'set', 'pointer': '/x', 'value': 1},
                 'TrustedData')

    def test_indirect_settings(self):
        """system 用 $ref 指到別檔裡的路徑字串、記憶是字面路徑但內容再 $ref：解出來的目標都擋（審查 M1）。"""
        self.put('paths.json', '{"system": "workspace/real-persona.json"}')
        self.put('real-persona.json', '{"content": "p"}')
        self.put('mem.json', '{"$ref": "workspace/mem2.json"}')
        self.put('mem2.json', '[]')
        self.agent_home(system={'$ref': 'workspace/paths.json#/system'}, history='workspace/mem.json')
        for path in ('workspace/real-persona.json', 'workspace/paths.json', 'workspace/mem2.json'):
            self.err('json_edit', {'path': path, 'op': 'set', 'pointer': '/x', 'value': 1}, 'TrustedData')

    def test_unresolvable_settings_fail_closed(self):
        self.put('free.json', '{"a": 1}')
        self.agent_home(system={'$env': 'PERSONA_PATH'})
        j = self.err('json_edit', {'path': 'workspace/free.json', 'op': 'set', 'pointer': '/a', 'value': 2},
                     'TrustedData')
        self.assertIn('system', j['message'])

    def test_hardlink_to_persona(self):
        self.agent_home()
        os.link(os.path.join(self.home, 'prompts', 'system.json'), os.path.join(self.ws, 'hl.json'))
        self.err('json_edit', {'path': 'workspace/hl.json', 'op': 'set', 'pointer': '/content', 'value': 'x'},
                 'TrustedData')

    def test_md_section_also_guarded(self):
        self.put('notes.md', '# A\n\nx\n')
        self.agent_home(system={'$ref': 'workspace/notes.md'})
        self.err('md_section', {'path': 'workspace/notes.md', 'op': 'replace', 'heading': 'A', 'text': 'y'},
                 'TrustedData')

    def test_not_an_agent_home_no_trust_check(self):
        self.put('info.json', '{"a": 1}', base=self.home)
        os.remove(os.path.join(self.home, 'info.json'))
        self.put('x.json', '{"a": 1}')
        self.ok('json_edit', {'path': 'workspace/x.json', 'op': 'set', 'pointer': '/a', 'value': 2})

    def test_jailed_leaves_it_to_the_wall(self):
        """關牢時（AOS_TOOL_ROOT）不另外擋：牆本來就不准可寫資料夾蓋到信任資料。"""
        self.agent_home(system='workspace/persona.json')
        self.put('persona.json', '{"content": "p"}')
        self.ok('json_edit', {'path': 'persona.json', 'op': 'set', 'pointer': '/content', 'value': 'x'},
                env={'AOS_TOOL_ROOT': self.ws})


class MdSectionTests(FilesCase):
    DOC = ('intro\n\n# Title\n\ntext\n\n## Status\n\n- [a] doing → next\n\n### Sub\n\nsub body\n\n'
           '## Next\n\n```\n## not a heading\n```\n\nend\n')

    def setUp(self):
        super().setUp()
        self.put('d.md', self.DOC)

    def test_list_and_get(self):
        out = self.ok('md_section', {'path': 'd.md', 'op': 'list'})
        self.assertIn('line 3: # Title', out)
        self.assertIn('line 7:   ## Status', out)
        self.assertNotIn('not a heading', out)
        got = self.ok('md_section', {'path': 'd.md', 'heading': '## Status'})
        self.assertTrue(got.startswith('## Status\n\n- [a] doing → next\n\n### Sub\n\nsub body\nsha='), got)

    def test_replace_keeps_heading_and_neighbours(self):
        self.ok('md_section', {'path': 'd.md', 'op': 'replace', 'heading': 'Next', 'text': 'new\nbody\n'})
        self.assertTrue(self.get('d.md').endswith('## Next\n\nnew\nbody\n'))
        self.ok('md_section', {'path': 'd.md', 'op': 'replace', 'heading': '### Sub', 'text': 'S'})
        self.assertIn('### Sub\n\nS\n\n## Next', self.get('d.md'))

    def test_delete_takes_subsections(self):
        self.ok('md_section', {'path': 'd.md', 'op': 'delete', 'heading': 'Status'})
        text = self.get('d.md')
        self.assertNotIn('Sub', text)
        self.assertIn('text\n\n## Next', text)

    def test_not_unique_and_not_found(self):
        self.put('u.md', '# A\n## X\n1\n### X\n2\n## X\n3\n')
        j = self.err('md_section', {'path': 'u.md', 'heading': 'X'}, 'NotUnique')
        self.assertEqual(j['lines'], [2, 4, 6])
        self.assertIn('### X\n2', self.ok('md_section', {'path': 'u.md', 'heading': '### X'}))
        j = self.err('md_section', {'path': 'u.md', 'heading': 'Nope'}, 'HeadingNotFound')
        self.assertIn("'## X'", j['message'])

    def test_append_item_format(self):
        self.err('md_section', {'path': 'd.md', 'op': 'append_item', 'heading': 'Status', 'text': 'plain'},
                 'BadItem')
        self.err('md_section', {'path': 'd.md', 'op': 'append_item', 'heading': 'Status', 'text': '- a\n- b'},
                 'BadItem')
        j = self.err('md_section', {'path': 'd.md', 'op': 'append_item', 'heading': 'Status',
                                    'text': '- no arrow'}, 'BadItem')
        self.assertIn('→', j['message'])
        self.err('md_section', {'path': 'd.md', 'op': 'append_item', 'heading': 'Next', 'text': '- plain'},
                 'BadItem')      # 空節也照格式驗
        self.ok('md_section', {'path': 'd.md', 'op': 'append_item', 'heading': 'Status',
                               'text': '- [b] wait → ask'})
        self.assertIn('- [a] doing → next\n- [b] wait → ask\n\n### Sub', self.get('d.md'))

    def test_append_item_into_empty_section(self):
        self.ok('md_section', {'path': 'd.md', 'op': 'append_item', 'heading': 'Title', 'text': '- [w] a → b'})
        self.assertIn('# Title\n\ntext\n\n- [w] a → b\n\n## Status', self.get('d.md'))
        self.put('e.md', '# E\n## F\n')
        self.ok('md_section', {'path': 'e.md', 'op': 'append_item', 'heading': 'E', 'text': '- [w] x → y'})
        self.assertEqual(self.get('e.md'), '# E\n- [w] x → y\n\n## F\n')

    def test_remove_item(self):
        a, b = '- [w] a → n', '- [w] b → n'
        self.put('r.md', '## L\n\n%s\n%s\n%s\n' % (a, b, a))
        self.err('md_section', {'path': 'r.md', 'op': 'remove_item', 'heading': 'L', 'text': a}, 'NotUnique')
        self.err('md_section', {'path': 'r.md', 'op': 'remove_item', 'heading': 'L', 'text': '- [w] z → n'},
                 'NoMatch')
        self.err('md_section', {'path': 'r.md', 'op': 'remove_item', 'heading': 'L', 'text': 'zz'}, 'BadItem')
        self.ok('md_section', {'path': 'r.md', 'op': 'remove_item', 'heading': 'L', 'text': b[2:]})
        self.assertEqual(self.get('r.md'), '## L\n\n%s\n%s\n' % (a, a))

    def test_crlf_kept(self):
        self.put('c.md', '# A\r\n\r\nx\r\n\r\n# B\r\ny\r\n')
        self.ok('md_section', {'path': 'c.md', 'op': 'replace', 'heading': 'A', 'text': 'z\nw'})
        self.assertEqual(self.get('c.md'), '# A\r\n\r\nz\r\nw\r\n\r\n# B\r\ny\r\n')

    def test_conflict_protected_and_args(self):
        out = self.ok('md_section', {'path': 'd.md', 'heading': 'Next'})
        sha = self.sha_of(out)
        self.put('d.md', self.DOC + 'more\n')
        self.err('md_section', {'path': 'd.md', 'op': 'delete', 'heading': 'Next', 'expect_sha': sha}, 'Conflict')
        self.put('SESSION-LOG.md', '# S\n')
        self.err('md_section', {'path': 'SESSION-LOG.md', 'op': 'append_item', 'heading': 'S',
                                'text': '- [w] x → y'}, 'Protected')
        self.ok('md_section', {'path': 'SESSION-LOG.md', 'heading': 'S'})      # 讀可以
        self.err('md_section', {'path': 'd.md', 'op': 'get'}, 'BadArguments')
        self.err('md_section', {'path': 'd.md', 'op': 'replace', 'heading': 'Next'}, 'BadArguments')
        self.err('md_section', {'path': 'd.md', 'op': 'zap', 'heading': 'Next'}, 'BadArguments')
        self.config({'root': 'workspace', 'protected': []})
        self.ok('md_section', {'path': 'SESSION-LOG.md', 'op': 'append_item', 'heading': 'S',
                               'text': '- [w] x → y'})


class InstallTests(unittest.TestCase):
    def test_tools_add_and_check(self):
        root = tempfile.mkdtemp(prefix='aos-files-add-')
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')

        def agent(*args):
            return subprocess.run([sys.executable, os.path.join(CLI, 'aos-agent'), *args], env=env, cwd=root,
                                  capture_output=True, text=True, timeout=30)
        self.assertEqual(agent('init', '--target', 'amy').returncode, 0)
        r = agent('tools', 'add', 'files', '--target', 'amy')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('json_edit、md_section', r.stdout)
        r = agent('tools', 'ls', '--target', 'amy', '--json')
        names = [t['name'] for t in json.loads(r.stdout)['tools']]
        self.assertIn('json_edit', names)
        self.assertIn('md_section', names)
        exe = os.path.join(root, 'amy', 'tools', 'files', 'json_edit')
        with open(os.path.join(root, 'amy', 'workspace', 'a.json'), 'w') as f:
            f.write('{"a": 1}')
        p = subprocess.run([exe], input='{"path": "a.json", "pointer": "/a"}', cwd=os.path.join(root, 'amy'),
                           capture_output=True, text=True, env={k: v for k, v in env.items() if k != 'AOS_TOOL_ROOT'})
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertTrue(p.stdout.startswith('1\n'))


if __name__ == '__main__':
    unittest.main()
