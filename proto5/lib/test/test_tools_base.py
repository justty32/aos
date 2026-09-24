"""proto5/tools/base/ 七支基礎工具（read／write／edit／grep／find／ls，bash 另見
test_tools_base_bash.py）與共用模組 _common.py：真的把工具複製進一個假 agent 家、當子行程跑，
驗 stdin JSON 進、stdout 文字或錯誤 JSON 出的約定（README：cwd＝agent 家、root＝config.json 的
"root"、失敗＝最後一行 JSON {"ok": false, "error": ...} 退 1）。

ToolCase（本檔）也是 test_tools_base_bash.py 的共用底。
"""
import glob
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PROTO5 = os.path.dirname(os.path.dirname(HERE))
TOOLS_BASE = os.path.join(PROTO5, 'tools', 'base')
TOOL_NAMES = ('read', 'write', 'edit', 'bash', 'grep', 'find', 'ls')


class ToolCase(unittest.TestCase):
    """每個 test 一個假 agent 家：tools/base 複製進去、建 workspace，工具當子行程跑。"""

    def setUp(self):
        self.home = tempfile.mkdtemp(prefix='aos-tools-base-')
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        shutil.copytree(TOOLS_BASE, os.path.join(self.home, 'tools', 'base'))
        self.ws = os.path.join(self.home, 'workspace')
        os.makedirs(self.ws, exist_ok=True)

    # ---- workspace 小工具 ----

    def wpath(self, *parts):
        return os.path.join(self.ws, *parts)

    def wwrite(self, relpath, content, executable=False):
        """在 workspace 底下寫一個檔（父目錄自動建），回絕對路徑。content 可以是 str 或 bytes。"""
        full = self.wpath(relpath)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        if isinstance(content, bytes):
            with open(full, 'wb') as f:
                f.write(content)
        else:
            with open(full, 'w', encoding='utf-8', newline='') as f:
                f.write(content)
        if executable:
            os.chmod(full, os.stat(full).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return full

    def wread(self, relpath, binary=False):
        with open(self.wpath(relpath), 'rb' if binary else 'r') as f:
            return f.read()

    def config_path(self):
        return os.path.join(self.home, 'tools', 'base', 'config.json')

    def set_config(self, obj_or_text):
        """覆寫 tools/base/config.json；字串就照原文寫（給壞 JSON 用），其餘當物件 dump。"""
        with open(self.config_path(), 'w', encoding='utf-8') as f:
            if isinstance(obj_or_text, str):
                f.write(obj_or_text)
            else:
                json.dump(obj_or_text, f)

    # ---- 呼叫工具 ----

    def run_tool(self, name, args=None, env=None, timeout=10):
        """呼叫 tools/base/<name>：stdin 給 args 的 JSON，cwd＝agent 家。
        回 (exit_code, stdout全文, 最後一行解析出的 JSON 或 None)。"""
        exe = os.path.join(self.home, 'tools', 'base', name)
        full_env = dict(os.environ)
        full_env['PYTHONDONTWRITEBYTECODE'] = '1'
        if env:
            full_env.update(env)
        payload = '' if args is None else json.dumps(args, ensure_ascii=False)
        p = subprocess.run([exe], input=payload, cwd=self.home, capture_output=True,
                           text=True, encoding='utf-8', env=full_env, timeout=timeout)
        last = None
        stripped = p.stdout.rstrip('\n')
        if stripped:
            last_line = stripped.rsplit('\n', 1)[-1]
            try:
                last = json.loads(last_line)
            except ValueError:
                last = None
        return p.returncode, p.stdout, last

    def assertOk(self, res):
        code, out, j = res
        self.assertEqual(code, 0, out)
        return out

    def assertErr(self, res, error, **extra):
        code, out, j = res
        self.assertEqual(code, 1, out)
        self.assertIsNotNone(j, 'stdout 最後一行不是 JSON: %r' % out)
        self.assertFalse(j.get('ok'))
        self.assertEqual(j.get('error'), error, out)
        for k, v in extra.items():
            self.assertEqual(j.get(k), v, out)
        return j

    def no_leftover_tmp(self):
        return glob.glob(self.wpath('**/*.aos-tmp-*'), recursive=True)


# =============================================================== _common ====

class TestCommonArguments(ToolCase):
    """arguments 的讀取與型別檢查（read_args／arg），透過任一支工具（這裡用 read／write）驗。"""

    def _raw(self, name, raw, env=None):
        exe = os.path.join(self.home, 'tools', 'base', name)
        full_env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        if env:
            full_env.update(env)
        p = subprocess.run([exe], input=raw, cwd=self.home, capture_output=True,
                           text=True, encoding='utf-8', env=full_env, timeout=10)
        last = None
        stripped = p.stdout.rstrip('\n')
        if stripped:
            try:
                last = json.loads(stripped.rsplit('\n', 1)[-1])
            except ValueError:
                pass
        return p.returncode, p.stdout, last

    def test_arguments_not_valid_json(self):
        self.assertErr(self._raw('read', 'not json at all'), 'BadArguments')

    def test_arguments_not_an_object_array(self):
        self.assertErr(self._raw('read', '[1, 2]'), 'BadArguments')

    def test_arguments_not_an_object_scalar(self):
        self.assertErr(self._raw('read', '"just a string"'), 'BadArguments')

    def test_stdin_empty_defaults_to_empty_object(self):
        # ls 的所有參數都有預設值，空 stdin（＝{}）要能成功
        self.wwrite('f.txt', 'x')
        out = self.assertOk(self.run_tool('ls', args=None))
        self.assertIn('f.txt', out)

    def test_missing_required_argument(self):
        self.assertErr(self.run_tool('read', {}), 'BadArguments')

    def test_type_error_int_given_string(self):
        self.wwrite('f.txt', 'a\nb\n')
        j = self.assertErr(self.run_tool('read', {'path': 'f.txt', 'offset': '1'}), 'BadArguments')
        self.assertIn('offset', j['message'])

    def test_type_error_int_given_bool(self):
        # bool 是 int 的子類別，但工具明確排除
        self.wwrite('f.txt', 'a\nb\n')
        self.assertErr(self.run_tool('read', {'path': 'f.txt', 'offset': True}), 'BadArguments')

    def test_type_error_string_given_int(self):
        self.assertErr(self.run_tool('read', {'path': 5}), 'BadArguments')

    def test_type_error_bool_given_string(self):
        self.wwrite('f.txt', 'x')
        self.assertErr(self.run_tool('edit', {'path': 'f.txt', 'old_string': 'x',
                                              'new_string': 'y', 'replace_all': 'true'}), 'BadArguments')


class TestCommonConfigAndRoot(ToolCase):

    def test_missing_config_file_defaults_to_workspace(self):
        os.unlink(self.config_path())
        self.wwrite('f.txt', 'hi')
        out = self.assertOk(self.run_tool('ls', {}))
        self.assertIn('f.txt', out)

    def test_config_invalid_json(self):
        self.set_config('not json')
        self.assertErr(self.run_tool('ls', {}), 'ConfigInvalid')

    def test_config_not_an_object(self):
        self.set_config('[1, 2]')
        self.assertErr(self.run_tool('ls', {}), 'ConfigInvalid')

    def test_config_root_not_a_string(self):
        self.set_config({'root': 5})
        self.assertErr(self.run_tool('ls', {}), 'ConfigInvalid')

    def test_config_root_empty_string(self):
        self.set_config({'root': ''})
        self.assertErr(self.run_tool('ls', {}), 'ConfigInvalid')

    def test_root_missing(self):
        self.set_config({'root': 'does-not-exist-anywhere'})
        self.assertErr(self.run_tool('ls', {}), 'RootMissing')

    def test_root_absolute_path_works(self):
        outside = tempfile.mkdtemp(prefix='aos-tools-base-absroot-')
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        with open(os.path.join(outside, 'f.txt'), 'w') as f:
            f.write('hi')
        self.set_config({'root': outside})
        out = self.assertOk(self.run_tool('ls', {}))
        self.assertIn('f.txt', out)


class TestCommonOutsideRoot(ToolCase):
    """`../` 逃出、絕對路徑在外、符號連結指到外面：read／write／edit／ls／grep／find 各至少一條。"""

    def setUp(self):
        super().setUp()
        self.outside_dir = os.path.dirname(self.ws)  # agent 家：workspace 的上一層
        with open(os.path.join(self.outside_dir, 'outside.txt'), 'w') as f:
            f.write('secret\n')

    def test_read_dotdot(self):
        self.assertErr(self.run_tool('read', {'path': '../outside.txt'}), 'OutsideRoot')

    def test_write_dotdot(self):
        self.assertErr(self.run_tool('write', {'path': '../evil.txt', 'content': 'x'}), 'OutsideRoot')
        self.assertFalse(os.path.exists(os.path.join(self.outside_dir, 'evil.txt')))

    def test_edit_dotdot(self):
        self.assertErr(self.run_tool('edit', {'path': '../outside.txt', 'old_string': 'secret',
                                              'new_string': 'x'}), 'OutsideRoot')

    def test_ls_dotdot(self):
        self.assertErr(self.run_tool('ls', {'path': '..'}), 'OutsideRoot')

    def test_grep_dotdot(self):
        self.assertErr(self.run_tool('grep', {'pattern': 'secret', 'path': '..'}), 'OutsideRoot')

    def test_find_dotdot(self):
        self.assertErr(self.run_tool('find', {'pattern': '*.txt', 'path': '..'}), 'OutsideRoot')

    def test_read_absolute_path_outside(self):
        self.assertErr(self.run_tool('read', {'path': '/etc/passwd'}), 'OutsideRoot')

    def test_symlink_escape(self):
        outer = tempfile.mkdtemp(prefix='aos-tools-base-outer-')
        self.addCleanup(shutil.rmtree, outer, ignore_errors=True)
        with open(os.path.join(outer, 'secret.txt'), 'w') as f:
            f.write('nope\n')
        os.symlink(outer, self.wpath('link'))
        self.assertErr(self.run_tool('read', {'path': 'link/secret.txt'}), 'OutsideRoot')

    def test_symlink_escape_ls(self):
        outer = tempfile.mkdtemp(prefix='aos-tools-base-outer2-')
        self.addCleanup(shutil.rmtree, outer, ignore_errors=True)
        os.symlink(outer, self.wpath('linkdir'))
        self.assertErr(self.run_tool('ls', {'path': 'linkdir'}), 'OutsideRoot')


# =================================================================== read ====

class TestRead(ToolCase):

    def test_basic(self):
        self.wwrite('f.txt', 'line1\nline2\nline3\n')
        out = self.assertOk(self.run_tool('read', {'path': 'f.txt'}))
        self.assertEqual(out, 'line1\nline2\nline3\n')

    def test_offset_and_limit(self):
        self.wwrite('f.txt', ''.join('l%d\n' % i for i in range(1, 11)))
        out = self.assertOk(self.run_tool('read', {'path': 'f.txt', 'offset': 3, 'limit': 2}))
        self.assertIn('l3\n', out)
        self.assertIn('l4\n', out)
        self.assertNotIn('l5\n', out)
        self.assertIn('[showing lines 3-4 of 10 (limit=2); use offset=5 to continue]', out)

    def test_truncated_at_2000_lines(self):
        self.wwrite('big.txt', ''.join('l%d\n' % i for i in range(2500)))
        out = self.assertOk(self.run_tool('read', {'path': 'big.txt'}))
        self.assertIn('offset=2001', out)
        self.assertNotIn('l2000\n', out)  # 第 2001 行 (0-based l2000) 不該在裡面

    def test_truncated_at_50kb(self):
        self.wwrite('fifty.txt', ''.join(('x' * 30 + '\n') for _ in range(3000)))
        out = self.assertOk(self.run_tool('read', {'path': 'fifty.txt'}))
        self.assertIn('output limit 50 KB', out)

    def test_long_line_is_cut(self):
        self.wwrite('longline.txt', 'a' * 3000 + '\nshort\n')
        out = self.assertOk(self.run_tool('read', {'path': 'longline.txt'}))
        self.assertIn('… [line truncated]', out)
        self.assertIn('1 line(s) longer than 2000 chars were cut', out)

    def test_empty_file(self):
        self.wwrite('empty.txt', '')
        out = self.assertOk(self.run_tool('read', {'path': 'empty.txt'}))
        self.assertEqual(out.strip(), '(empty file)')

    def test_offset_past_end(self):
        self.wwrite('f.txt', 'a\nb\n')
        self.assertErr(self.run_tool('read', {'path': 'f.txt', 'offset': 99}), 'BadArguments')

    def test_offset_below_one(self):
        self.wwrite('f.txt', 'a\n')
        self.assertErr(self.run_tool('read', {'path': 'f.txt', 'offset': 0}), 'BadArguments')

    def test_limit_below_one(self):
        self.wwrite('f.txt', 'a\n')
        self.assertErr(self.run_tool('read', {'path': 'f.txt', 'limit': 0}), 'BadArguments')

    def test_directory_is_error(self):
        self.wwrite('sub/f.txt', 'x')
        self.assertErr(self.run_tool('read', {'path': 'sub'}), 'IsADirectory')

    def test_binary_file(self):
        self.wwrite('bin.dat', b'ab\x00cd')
        self.assertErr(self.run_tool('read', {'path': 'bin.dat'}), 'BinaryFile')

    def test_not_found(self):
        self.assertErr(self.run_tool('read', {'path': 'nope.txt'}), 'NotFound', path='nope.txt')


# ==================================================================== write ==

class TestWrite(ToolCase):

    def test_creates_nested_dirs(self):
        out = self.assertOk(self.run_tool('write', {'path': 'a/b/c.txt', 'content': 'hi\n'}))
        self.assertIn('created', out)
        self.assertEqual(self.wread('a/b/c.txt'), 'hi\n')

    def test_overwrite_reports_overwrote(self):
        self.wwrite('f.txt', 'old')
        out = self.assertOk(self.run_tool('write', {'path': 'f.txt', 'content': 'new'}))
        self.assertIn('overwrote', out)
        self.assertEqual(self.wread('f.txt'), 'new')

    def test_overwrite_preserves_exec_bit(self):
        full = self.wwrite('run.sh', '#!/bin/sh\necho old\n', executable=True)
        self.assertTrue(os.stat(full).st_mode & stat.S_IXUSR)
        self.assertOk(self.run_tool('write', {'path': 'run.sh', 'content': '#!/bin/sh\necho new\n'}))
        self.assertTrue(os.stat(full).st_mode & stat.S_IXUSR)

    def test_write_to_directory_path_fails(self):
        self.wwrite('adir/.keep', 'x')
        self.assertErr(self.run_tool('write', {'path': 'adir', 'content': 'x'}), 'IsADirectory')

    def test_no_leftover_tmp_file(self):
        self.assertOk(self.run_tool('write', {'path': 'f.txt', 'content': 'x'}))
        self.assertEqual(self.no_leftover_tmp(), [])

    def test_utf8_content_roundtrip(self):
        text = '你好，世界\n第二行\n'
        self.assertOk(self.run_tool('write', {'path': 'zh.txt', 'content': text}))
        self.assertEqual(self.wread('zh.txt'), text)

    def test_missing_content_argument(self):
        self.assertErr(self.run_tool('write', {'path': 'f.txt'}), 'BadArguments')

    def test_content_type_error(self):
        self.assertErr(self.run_tool('write', {'path': 'f.txt', 'content': 5}), 'BadArguments')


# ===================================================================== edit ==

class TestEdit(ToolCase):

    def test_unique_replace(self):
        self.wwrite('f.txt', 'foo\nbar\nbaz\n')
        out = self.assertOk(self.run_tool('edit', {'path': 'f.txt', 'old_string': 'bar', 'new_string': 'BAR'}))
        self.assertIn('replaced 1 occurrence', out)
        self.assertEqual(self.wread('f.txt'), 'foo\nBAR\nbaz\n')

    def test_no_match(self):
        self.wwrite('f.txt', 'foo\n')
        self.assertErr(self.run_tool('edit', {'path': 'f.txt', 'old_string': 'zzz', 'new_string': 'y'}), 'NoMatch')

    def test_not_unique_reports_count_and_lines(self):
        self.wwrite('f.txt', 'x\nx\nx\n')
        j = self.assertErr(self.run_tool('edit', {'path': 'f.txt', 'old_string': 'x', 'new_string': 'y'}),
                           'NotUnique', count=3)
        self.assertIn('1, 2, 3', j['message'])

    def test_replace_all(self):
        self.wwrite('f.txt', 'x\nx\nx\n')
        out = self.assertOk(self.run_tool('edit', {'path': 'f.txt', 'old_string': 'x', 'new_string': 'y',
                                                    'replace_all': True}))
        self.assertIn('replaced 3 occurrences', out)
        self.assertEqual(self.wread('f.txt'), 'y\ny\ny\n')

    def test_old_equals_new_is_bad_arguments(self):
        self.wwrite('f.txt', 'hi\n')
        self.assertErr(self.run_tool('edit', {'path': 'f.txt', 'old_string': 'hi', 'new_string': 'hi'}),
                       'BadArguments')

    def test_old_empty_is_bad_arguments(self):
        self.wwrite('f.txt', 'hi\n')
        self.assertErr(self.run_tool('edit', {'path': 'f.txt', 'old_string': '', 'new_string': 'x'}),
                       'BadArguments')

    def test_preserves_crlf_line_endings(self):
        self.wwrite('crlf.txt', 'a\r\nb\r\n')
        self.assertOk(self.run_tool('edit', {'path': 'crlf.txt', 'old_string': 'a', 'new_string': 'A'}))
        self.assertEqual(self.wread('crlf.txt', binary=True), b'A\r\nb\r\n')

    def test_not_found(self):
        self.assertErr(self.run_tool('edit', {'path': 'nope.txt', 'old_string': 'a', 'new_string': 'b'}),
                       'NotFound')

    def test_preserves_permissions(self):
        full = self.wwrite('f.txt', 'hi\n')
        os.chmod(full, 0o640)
        self.assertOk(self.run_tool('edit', {'path': 'f.txt', 'old_string': 'hi', 'new_string': 'bye'}))
        self.assertEqual(stat.S_IMODE(os.stat(full).st_mode), 0o640)


# ===================================================================== grep ==

class TestGrep(ToolCase):

    def setUp(self):
        super().setUp()
        self.wwrite('a.txt', 'hello world\nfoo bar\nHELLO again\n')
        self.wwrite('src/pkg/b.py', 'nested hello\n')

    def _fallback_env(self):
        # 逼工具找不到 rg，走 grep -r 的分支
        return {'AOS_TOOLS_RG': 'definitely-not-a-real-binary-xyz'}

    def test_hits_with_rg(self):
        out = self.assertOk(self.run_tool('grep', {'pattern': 'hello'}))
        lines = out.strip().splitlines()
        self.assertIn('a.txt:1:hello world', lines)
        self.assertIn('src/pkg/b.py:1:nested hello', lines)

    def test_hits_with_fallback_grep(self):
        out = self.assertOk(self.run_tool('grep', {'pattern': 'hello'}, env=self._fallback_env()))
        lines = out.strip().splitlines()
        self.assertIn('a.txt:1:hello world', lines)
        self.assertIn('src/pkg/b.py:1:nested hello', lines)

    def test_glob_filter(self):
        out = self.assertOk(self.run_tool('grep', {'pattern': 'hello', 'glob': '*.py'}))
        self.assertIn('b.py', out)
        self.assertNotIn('a.txt', out)

    def test_glob_filter_fallback(self):
        out = self.assertOk(self.run_tool('grep', {'pattern': 'hello', 'glob': '*.py'}, env=self._fallback_env()))
        self.assertIn('b.py', out)
        self.assertNotIn('a.txt', out)

    def test_ignore_case(self):
        out = self.assertOk(self.run_tool('grep', {'pattern': 'HELLO', 'ignore_case': True}))
        self.assertIn('a.txt:3:HELLO again', out)
        self.assertIn('a.txt:1:hello world', out)

    def test_literal(self):
        self.wwrite('lit.txt', 'a.b(c)\naxbyc\n')
        out = self.assertOk(self.run_tool('grep', {'pattern': 'a.b(c)', 'literal': True}))
        self.assertIn('a.b(c)', out)
        self.assertNotIn('axbyc', out)

    def test_literal_fallback(self):
        self.wwrite('lit.txt', 'a.b(c)\naxbyc\n')
        out = self.assertOk(self.run_tool('grep', {'pattern': 'a.b(c)', 'literal': True}, env=self._fallback_env()))
        self.assertIn('a.b(c)', out)
        self.assertNotIn('axbyc', out)

    def test_context(self):
        out = self.assertOk(self.run_tool('grep', {'pattern': 'foo', 'context': 1}))
        self.assertIn('a.txt-1-hello world', out)
        self.assertIn('a.txt:2:foo bar', out)
        self.assertIn('a.txt-3-HELLO again', out)

    def test_limit_truncation(self):
        self.wwrite('many.txt', ''.join('needle %d\n' % i for i in range(20)))
        out = self.assertOk(self.run_tool('grep', {'pattern': 'needle', 'limit': 5}))
        self.assertEqual(len(out.strip().splitlines()), 6)  # 5 筆 + 提示那行
        self.assertIn('[stopped at limit=5', out)

    def test_no_matches_exits_zero(self):
        code, out, j = self.run_tool('grep', {'pattern': 'zzz_absolutely_not_there'})
        self.assertEqual(code, 0, out)
        self.assertIn('No matches found', out)

    def test_bad_regex_search_failed(self):
        self.assertErr(self.run_tool('grep', {'pattern': '('}), 'SearchFailed', engine='rg')

    def test_bad_regex_search_failed_fallback(self):
        self.assertErr(self.run_tool('grep', {'pattern': '('}, env=self._fallback_env()),
                       'SearchFailed', engine='grep')

    def test_path_single_file(self):
        out = self.assertOk(self.run_tool('grep', {'pattern': 'hello', 'path': 'a.txt'}))
        self.assertIn('a.txt:1:hello world', out)
        self.assertNotIn('b.py', out)


# ===================================================================== find ==

class TestFind(ToolCase):

    def setUp(self):
        super().setUp()
        self.wwrite('a.py', '')
        self.wwrite('b.py', '')
        self.wwrite('src/pkg/c.py', '')
        self.wwrite('.git/ignored.py', '')
        self.wwrite('apple.txt', '')
        self.wwrite('banana.txt', '')

    def test_star_py_any_depth(self):
        out = self.assertOk(self.run_tool('find', {'pattern': '*.py'}))
        found = out.strip().splitlines()
        self.assertEqual(sorted(found), ['a.py', 'b.py', 'src/pkg/c.py'])

    def test_pattern_with_slash(self):
        out = self.assertOk(self.run_tool('find', {'pattern': 'src/**/*.py'}))
        self.assertEqual(out.strip(), 'src/pkg/c.py')

    def test_directory_result_ends_with_slash(self):
        out = self.assertOk(self.run_tool('find', {'pattern': 'pkg'}))
        self.assertEqual(out.strip(), 'src/pkg/')

    def test_skips_dot_git(self):
        out = self.assertOk(self.run_tool('find', {'pattern': '*.py'}))
        self.assertNotIn('.git', out)

    def test_limit_truncation(self):
        out = self.assertOk(self.run_tool('find', {'pattern': '*.py', 'limit': 2}))
        self.assertEqual(len(out.strip().splitlines()), 3)
        self.assertIn('[stopped at limit=2', out)

    def test_not_found_exits_zero(self):
        code, out, j = self.run_tool('find', {'pattern': '*.zzz'})
        self.assertEqual(code, 0, out)
        self.assertIn('No files found', out)

    def test_path_not_a_directory(self):
        self.assertErr(self.run_tool('find', {'pattern': '*.py', 'path': 'a.py'}), 'NotADirectory')

    def test_char_class(self):
        out = self.assertOk(self.run_tool('find', {'pattern': '[ab]*'}))
        found = sorted(out.strip().splitlines())
        self.assertEqual(found, ['a.py', 'apple.txt', 'b.py', 'banana.txt'])


# ======================================================================= ls ==

class TestLs(ToolCase):

    def test_sorted_dirs_end_with_slash_hidden_included(self):
        self.wwrite('b.txt', '')
        self.wwrite('a.txt', '')
        self.wwrite('sub/.keep', '')
        self.wwrite('.hidden', '')
        out = self.assertOk(self.run_tool('ls', {}))
        self.assertEqual(out.strip().splitlines(), ['.hidden', 'a.txt', 'b.txt', 'sub/'])

    def test_empty_directory(self):
        os.makedirs(self.wpath('empty'))
        out = self.assertOk(self.run_tool('ls', {'path': 'empty'}))
        self.assertIn('(empty directory:', out)

    def test_limit_truncation(self):
        for i in range(5):
            self.wwrite('f%d.txt' % i, '')
        out = self.assertOk(self.run_tool('ls', {'limit': 2}))
        lines = out.strip().splitlines()
        self.assertEqual(len(lines), 3)
        self.assertIn('[showing 2 of 5 entries', lines[-1])

    def test_on_file_is_not_a_directory(self):
        self.wwrite('f.txt', 'x')
        self.assertErr(self.run_tool('ls', {'path': 'f.txt'}), 'NotADirectory')

    def test_not_found(self):
        self.assertErr(self.run_tool('ls', {'path': 'nope'}), 'NotFound')


# =================================================================== base.json ==

class TestBaseJson(unittest.TestCase):
    """base.json：合法 JSON 陣列、七個名字、argv[0] 對得上有執行位的檔、required 都在 properties 裡。"""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(TOOLS_BASE, 'base.json'), encoding='utf-8') as f:
            cls.spec = json.load(f)

    def test_is_a_list(self):
        self.assertIsInstance(self.spec, list)

    def test_seven_tools_with_expected_names(self):
        names = [entry['function']['name'] for entry in self.spec]
        self.assertEqual(sorted(names), sorted(TOOL_NAMES))

    def test_argv0_matches_an_executable_file(self):
        for entry in self.spec:
            name = entry['function']['name']
            argv0 = entry['_meta']['argv'][0]
            with self.subTest(tool=name):
                self.assertEqual(argv0, 'tools/base/%s' % name)
                full = os.path.join(PROTO5, argv0)
                self.assertTrue(os.path.isfile(full), full)
                self.assertTrue(os.stat(full).st_mode & stat.S_IXUSR, '%s not executable' % full)

    def test_required_names_are_in_properties(self):
        for entry in self.spec:
            params = entry['function']['parameters']
            props = params.get('properties', {})
            for req in params.get('required', []):
                with self.subTest(tool=entry['function']['name'], required=req):
                    self.assertIn(req, props)

    def test_bash_timeout_meta_above_600000ms(self):
        bash_entry = next(e for e in self.spec if e['function']['name'] == 'bash')
        self.assertGreater(bash_entry['_timeout_ms'], 600000)


if __name__ == '__main__':
    unittest.main()
