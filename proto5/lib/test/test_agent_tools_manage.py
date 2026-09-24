"""09-24 access-impl A1：tools 元素 $opt（as／only）與 tools ls／add／rm／alias／unalias。"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import aos_agent_home as home
import aos_llm_call
from _kernel_util import CLI, PY, read_json

META = {'_type': 'llm_agent', '_version': 1}


def tool(name, **extra):
    return dict({'type': 'function', 'function': {'name': name}, '_meta': {'argv': ['true']}}, **extra)


def run_agent(*args, cwd=None):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    return subprocess.run([PY, str(CLI / 'aos-agent'), *map(str, args)], cwd=cwd, env=env,
                          stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=20)


class Base(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='aos-tools-manage-'))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.amy = self.root / 'amy'
        self.shared = self.root / 'util-tools'
        self.write(self.shared / 'edit.json', [tool('bash-edit-a'), tool('bash-edit-b')])
        self.write(self.shared / 'grep.json', [tool('bash-grep')])
        self.write(self.amy / 'tools/mine.json', [tool('read'), tool('write')])
        self.set_tools(['tools/mine.json'])

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
        return path

    def set_tools(self, tools):
        self.write(self.amy / 'info.json', {'_metainfo': META, 'llm': {'model': 'm'}, 'tools': tools})

    def info(self):
        return read_json(self.amy / 'info.json')

    def view(self):
        return home.load_llm_view(self.amy, env={})

    def names(self):
        return [t['function']['name'] for t in self.view()['tools_raw']]

    def error(self, code, text=None):
        with self.assertRaises(home.AgentError) as cm:
            self.view()
        self.assertEqual(cm.exception.code, code, cm.exception.msg)
        if text:
            self.assertIn(text, cm.exception.msg)
        return cm.exception.msg

    def cli(self, *args, code=0):
        result = run_agent('tools', *args, '--target', self.amy)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return result


class ToolOptionTests(Base):
    def test_as_renames_and_source_kept_private(self):
        self.set_tools(['tools/mine.json', {'$opt': {'as': {'bash-edit-a': 'edit-a'}},
                                            '$val': str(self.shared / 'edit.json')}])
        view = self.view()
        self.assertEqual(self.names(), ['read', 'write', 'edit-a', 'bash-edit-b'])
        src = view['tools_raw'][2]['_source']
        self.assertEqual(src, {'file': str(self.shared / 'edit.json'), 'index': 0, 'name': 'bash-edit-a', 'entry': 1})
        self.assertTrue(all('_source' not in t for t in view['tools']))
        self.assertEqual(view['tools'][2]['function']['name'], 'edit-a')
        self.assertIn(str(self.shared / 'edit.json'), view['tool_paths'])
        # 工具檔本身沒被改到
        self.assertEqual(read_json(self.shared / 'edit.json')[0]['function']['name'], 'bash-edit-a')

    def test_only_on_folder_then_as(self):
        self.set_tools([{'$opt': {'only': ['bash-edit-b', 'bash-grep'], 'as': {'bash-grep': 'grep'}},
                         '$val': str(self.shared)}])
        self.assertEqual(self.names(), ['bash-edit-b', 'grep'])
        self.assertEqual(len(self.view()['tool_paths']), 2)

    def test_same_file_twice_with_different_only(self):
        path = str(self.shared / 'edit.json')
        self.set_tools([{'$opt': {'only': ['bash-edit-a']}, '$val': path},
                        {'$opt': {'only': ['bash-edit-b'], 'as': {'bash-edit-b': 'b'}}, '$val': path}])
        self.assertEqual(self.names(), ['bash-edit-a', 'b'])
        self.assertEqual(self.view()['tool_paths'], [path])

    def test_unknown_names(self):
        path = str(self.shared / 'edit.json')
        self.set_tools([{'$opt': {'only': ['nope']}, '$val': path}])
        self.error('ToolInvalid', 'nope')
        self.set_tools([{'$opt': {'as': {'nope': 'x'}}, '$val': path}])
        self.error('ToolInvalid', 'nope')
        self.set_tools([{'$opt': {'only': ['bash-edit-a'], 'as': {'bash-edit-b': 'x'}}, '$val': path}])
        self.error('ToolInvalid', 'only 挑完後')

    def test_rename_clash_names_both_sides(self):
        self.set_tools(['tools/mine.json', {'$opt': {'as': {'bash-grep': 'read'}},
                                            '$val': str(self.shared / 'grep.json')}])
        msg = self.error('ToolInvalid', '改名')
        self.assertIn(str(self.amy / 'tools/mine.json'), msg)
        self.assertIn(str(self.shared / 'grep.json'), msg)
        self.assertIn('bash-grep', msg)
        self.set_tools([{'$opt': {'as': {'bash-edit-a': 'x', 'bash-edit-b': 'x'}}, '$val': str(self.shared / 'edit.json')}])
        self.error('ToolInvalid', '改名')

    def test_plain_clash_message_unchanged(self):
        self.set_tools(['tools/mine.json', 'tools/mine.json'])
        self.error('ToolInvalid', '合併後工具同名')

    def test_shape_errors(self):
        path = str(self.shared / 'edit.json')
        for opt, code in (('as', 'FieldTypeMismatch'), (['as'], 'FieldTypeMismatch'), (None, 'FieldTypeMismatch'),
                          ({}, 'OptionConflict'), ({'rename': {}}, 'UnknownOption'),
                          ({'as': []}, 'FieldTypeMismatch'), ({'as': {}}, 'FieldTypeMismatch'),
                          ({'as': {'bash-edit-a': ''}}, 'FieldTypeMismatch'),
                          ({'only': []}, 'FieldTypeMismatch'), ({'only': 'bash-edit-a'}, 'FieldTypeMismatch'),
                          ({'only': ['bash-edit-a', 'bash-edit-a']}, 'FieldTypeMismatch')):
            with self.subTest(opt=opt):
                self.set_tools([{'$opt': opt, '$val': path}])
                self.error(code)
        self.set_tools([{'$opt': {'only': ['bash-edit-a']}}])
        self.error('OptionConflict', '$val')

    def test_val_directive_and_nested_opt(self):
        self.set_tools([{'$opt': {'as': {'bash-grep': 'g'}}, '$val': {'$env': 'GREP'}}])
        view = home.load_llm_view(self.amy, env={'GREP': str(self.shared / 'grep.json')})
        self.assertEqual([t['function']['name'] for t in view['tools']], ['g'])
        self.set_tools([{'$opt': {'as': {'bash-grep': 'g'}}, '$val': {'$opt': 'x', '$val': 'y'}}])
        self.error('UnknownOption')
        self.write(self.amy / 'entry.json', {'$opt': {'as': {'bash-grep': 'g'}}, '$val': 'x'})
        self.set_tools([{'$ref': 'entry.json'}])
        self.error('UnknownOption')

    def test_opt_inside_referenced_list(self):
        self.write(self.amy / 'list.json', [{'$opt': {'only': ['bash-grep']}, '$val': str(self.shared)}])
        self.set_tools({'$ref': 'list.json'})
        self.assertEqual(self.names(), ['bash-grep'])

    def test_jail_field(self):
        self.write(self.amy / 'tools/mine.json', [tool('read', _jail=False), tool('write', _jail=True)])
        self.assertEqual(self.view()['tools_raw'][0]['_jail'], False)
        self.assertNotIn('_jail', self.view()['tools'][0])
        for bad in (0, 'no', None):
            self.write(self.amy / 'tools/mine.json', [tool('read', _jail=bad)])
            self.error('ToolInvalid', '_jail')

    def test_llm_call_sees_new_name(self):
        self.set_tools([{'$opt': {'as': {'bash-grep': 'grep'}}, '$val': str(self.shared / 'grep.json')}])
        config = {'models': {'m': {'model': 'real', 'endpoint': 'http://x', 'api_key': None, 'timeout_ms': 1}}}
        body, _ = aos_llm_call.build_request(self.amy, config, env={})
        self.assertEqual(body['tools'], [{'type': 'function', 'function': {'name': 'grep'}}])


class ToolsCliTests(Base):
    def test_add_file_reference_with_as(self):
        out = self.cli('add', self.shared / 'grep.json', '--as', 'grep').stdout
        self.assertIn('referenced', out)
        self.assertTrue(out.rstrip().endswith('下一批工具生效，不用重 start'))
        self.assertEqual(self.info()['tools'][-1],
                         {'$opt': {'as': {'bash-grep': 'grep'}}, '$val': str(self.shared / 'grep.json')})
        self.assertEqual(self.names(), ['read', 'write', 'grep'])
        self.assertFalse((self.amy / 'access.json').exists())
        self.assertIn('AlreadyExists', self.cli('add', self.shared / 'grep.json', code=1).stderr)

    def test_add_folder_reference_in_home_is_relative(self):
        shutil.copytree(self.shared, self.amy / 'shared')
        self.cli('add', self.amy / 'shared', '--only', 'bash-edit-a,bash-grep', '--as', 'bash-grep=g,bash-edit-a=e')
        self.assertEqual(self.info()['tools'][-1],
                         {'$opt': {'as': {'bash-grep': 'g', 'bash-edit-a': 'e'}, 'only': ['bash-edit-a', 'bash-grep']},
                          '$val': 'shared'})
        self.assertEqual(self.names(), ['read', 'write', 'e', 'g'])

    def test_add_reference_errors_write_nothing(self):
        before = (self.amy / 'info.json').read_bytes()
        self.write(self.root / 'clash.json', [tool('read')])
        self.assertIn('ToolInvalid', self.cli('add', self.root / 'clash.json', code=1).stderr)
        self.assertEqual(self.cli('add', self.shared, '--as', 'x', code=2).stderr.count('3 支'), 1)
        self.assertIn('--root', self.cli('add', self.shared, '--root', self.root, code=2).stderr)
        self.assertIn('ToolInvalid', self.cli('add', self.shared, '--only', 'nope', code=1).stderr)
        self.assertIn('找不到 %s' % (self.root / 'missing.json'), self.cli('add', self.root / 'missing.json', code=1).stderr)
        self.assertEqual((self.amy / 'info.json').read_bytes(), before)

    def test_add_package_with_as_and_only(self):
        pkg = self.root / 'hello'
        self.write(pkg / 'hello.json', [tool('hello'), tool('bye')])
        self.cli('add', pkg, '--only', 'hello', '--as', 'hi')
        self.assertEqual(self.info()['tools'][-1],
                         {'$opt': {'as': {'hello': 'hi'}, 'only': ['hello']}, '$val': 'tools/hello.json'})
        self.assertEqual(self.names(), ['read', 'write', 'hi'])
        self.assertTrue((self.amy / 'tools/hello.json').is_file())
        self.cli('add', pkg, '--force', '--as', 'hello=h,bye=b')
        self.assertEqual(self.info()['tools'][-1], {'$opt': {'as': {'hello': 'h', 'bye': 'b'}}, '$val': 'tools/hello.json'})
        self.assertEqual(self.names(), ['read', 'write', 'h', 'b'])

    def test_add_package_into_folder_entry_merges_options(self):
        self.set_tools(['tools'])
        pkg = self.root / 'hello'
        self.write(pkg / 'hello.json', [tool('hello'), tool('bye')])
        self.cli('add', pkg, '--only', 'bye', '--as', 'bye=ciao')
        self.assertEqual(self.info()['tools'], [{'$opt': {'as': {'bye': 'ciao'}, 'only': ['read', 'write', 'bye']},
                                                 '$val': 'tools'}])
        self.assertEqual(self.names(), ['ciao', 'read', 'write'])

    def test_add_package_clash_after_rename_refused(self):
        pkg = self.root / 'hello'
        self.write(pkg / 'hello.json', [tool('hello')])
        before = (self.amy / 'info.json').read_bytes()
        self.assertIn('改名', self.cli('add', pkg, '--as', 'read', code=1).stderr)
        self.assertEqual((self.amy / 'info.json').read_bytes(), before)
        self.assertFalse((self.amy / 'tools/hello.json').exists())
        self.assertFalse((self.amy / 'tools/hello').exists())

    def test_ls_text_and_json(self):
        self.set_tools(['tools/mine.json', {'$opt': {'as': {'bash-grep': 'grep'}}, '$val': str(self.shared / 'grep.json')}])
        out = self.cli('ls').stdout.splitlines()
        self.assertEqual(out[0].split(), ['名字', '原名', '來源檔', '關牢', '池'])
        self.assertEqual(out[1].split(), ['read', '-', 'tools/mine.json', '-', 'default'])
        self.assertEqual(out[3].split(), ['grep', 'bash-grep', str(self.shared / 'grep.json'), '-', 'default'])
        self.assertIn('沒有 access 檔', out[-1])
        data = json.loads(self.cli('ls', '--json').stdout)
        self.assertEqual((data['_type'], data['_version'], data['access']), ('aos_agent_tools_ls', 1, None))
        self.assertEqual(data['tools'][2], {'name': 'grep', 'original': 'bash-grep', 'file': str(self.shared / 'grep.json'),
                                            'index': 0, 'entry': 1, 'jail': None, 'pool': 'default'})

    def test_ls_jail_column(self):
        self.write(self.amy / 'tools/mine.json', [tool('read', _jail=False), tool('write')])
        self.write(self.amy / 'access.json', {'mounts': {}})
        rows = [line.split() for line in self.cli('ls').stdout.splitlines()[1:3]]
        self.assertEqual([r[3] for r in rows], ['no', 'jail'])
        data = json.loads(self.cli('ls', '--json').stdout)
        self.assertEqual([t['jail'] for t in data['tools']], [False, True])
        self.assertEqual(data['access'], str(self.amy / 'access.json'))

    def test_ls_empty(self):
        self.set_tools([])
        self.assertIn('沒有工具', self.cli('ls').stdout)

    def test_rm_whole_entry_and_partial(self):
        self.set_tools(['tools/mine.json', {'$opt': {'as': {'bash-edit-a': 'ea'}}, '$val': str(self.shared / 'edit.json')}])
        out = self.cli('rm', 'ea').stdout
        self.assertIn('檔還在 %s' % (self.shared / 'edit.json'), out)
        self.assertEqual(self.info()['tools'][1], {'$opt': {'only': ['bash-edit-b']}, '$val': str(self.shared / 'edit.json')})
        self.cli('rm', 'bash-edit-b')
        self.assertEqual(self.info()['tools'], ['tools/mine.json'])
        self.assertTrue((self.shared / 'edit.json').is_file())
        self.assertIn('NotFound', self.cli('rm', 'nope', code=1).stderr)

    def test_rm_from_folder_entry_warns(self):
        self.set_tools(['tools'])
        out = self.cli('rm', 'read').stdout
        self.assertIn('整個資料夾', out)
        self.assertEqual(self.info()['tools'], [{'$opt': {'only': ['write']}, '$val': 'tools'}])
        self.assertTrue((self.amy / 'tools/mine.json').is_file())

    def test_alias_and_unalias_round_trip(self):
        self.cli('alias', 'read', 'cat')
        self.assertEqual(self.info()['tools'], [{'$opt': {'as': {'read': 'cat'}}, '$val': 'tools/mine.json'}])
        self.cli('alias', 'read', 'look')                  # 用原名也找得到
        self.assertEqual(self.names(), ['look', 'write'])
        self.cli('alias', 'write', 'put')
        self.cli('unalias', 'look')
        self.assertEqual(self.info()['tools'], [{'$opt': {'as': {'write': 'put'}}, '$val': 'tools/mine.json'}])
        out = self.cli('unalias', 'put').stdout
        self.assertIn('收回成 "tools/mine.json"', out)
        self.assertEqual(self.info()['tools'], ['tools/mine.json'])
        self.assertIn('NotFound', self.cli('unalias', 'read', code=1).stderr)

    def test_alias_clash_and_non_literal_refused(self):
        before = (self.amy / 'info.json').read_bytes()
        self.assertIn('ToolInvalid', self.cli('alias', 'read', 'write', code=1).stderr)
        self.assertEqual((self.amy / 'info.json').read_bytes(), before)
        self.write(self.amy / 'list.json', ['tools/mine.json'])
        self.set_tools({'$ref': 'list.json'})
        self.assertIn('字面陣列', self.cli('alias', 'read', 'cat', code=1).stderr)
        self.set_tools([{'$ref': 'list.json#/0'}])
        self.assertIn('FieldTypeMismatch', self.cli('rm', 'read', code=1).stderr)

    def test_usage_errors(self):
        for args in (('rm',), ('ls', 'x'), ('alias', 'read'), ('ls', '--as', 'x'), ('rm', 'read', '--json'),
                     ('add', 'base', '--as', 'a='), ('add', 'base', '--only', 'a,,b'), ('add', 'base', '--only', 'a,a'),
                     ('unalias', 'x', '--root', '/'), ('remove', 'x')):
            with self.subTest(args=args):
                self.assertEqual(run_agent('tools', *args, '--target', self.amy).returncode, 2)

    def test_concurrent_edits_all_land(self):
        names = ['t%d' % i for i in range(6)]
        self.write(self.amy / 'tools/mine.json', [tool(n) for n in names])
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        procs = [subprocess.Popen([PY, str(CLI / 'aos-agent'), 'tools', 'alias', n, n.upper(), '--target', str(self.amy)],
                                  env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True) for n in names]
        for p in procs:
            err = p.communicate(timeout=30)[1]
            self.assertEqual(p.returncode, 0, err)
        self.assertEqual(self.info()['tools'][0]['$opt']['as'], {n: n.upper() for n in names})



class AstraFixTests(Base):
    """09-24 access-impl astra #4、#7 與隊長煙霧測試的修正。"""

    def test_ls_explicit_access_missing_is_error(self):
        info = self.info()
        info['access'] = 'missing.json'
        self.write(self.amy / 'info.json', info)
        lines = self.cli('ls').stdout.splitlines()
        self.assertEqual([line.split()[3] for line in lines[1:3]], ['錯', '錯'])
        self.assertIn('missing.json', lines[-1])
        self.assertIn('AccessInvalid', lines[-1])
        data = json.loads(self.cli('ls', '--json').stdout)
        self.assertIsNone(data['access'])
        self.assertIn('missing.json', data['access_error'])
        self.assertEqual([t['jail'] for t in data['tools']], [None, None])

    def test_default_access_missing_is_not_error(self):
        data = json.loads(self.cli('ls', '--json').stdout)
        self.assertIsNone(data['access_error'])
        self.assertIn('沒有 access 檔', self.cli('ls').stdout)

    def test_info_written_indented(self):
        self.cli('alias', 'read', 'cat')
        text = (self.amy / 'info.json').read_text(encoding='utf-8')
        self.assertTrue(text.startswith('{\n  "'), text[:20])
        bob = self.root / 'bob'
        self.assertEqual(run_agent('init', '--target', bob).returncode, 0)
        self.assertTrue((bob / 'info.json').read_text(encoding='utf-8').startswith('{\n  "'))
        self.assertEqual(sorted(p.name for p in self.amy.iterdir() if p.name.endswith('.tmp')), [])

    def test_add_package_with_access_explains_jail_root(self):
        pkg = self.root / 'hello'
        self.write(pkg / 'hello.json', [tool('hello')])
        self.write(pkg / 'config.json', {'root': 'somewhere'})
        out = self.cli('add', pkg).stdout
        self.assertIn('關牢：工具的工作根目錄＝牢裡的 /work/ws（對到 %s）' % (self.amy / 'workspace'), out)
        self.assertIn('只在不關牢時用', out)
        self.assertNotIn('（改 ', out)

    def test_lock_file_serialises_tools_and_access_writers(self):
        """測試自己先拿 .admin.lock 當 barrier：tools 與 access 兩個寫者都要排隊，放開後兩邊都生效。"""
        from aos_agent_tools_edit import LOCK_NAME, info_lock
        (self.amy / 'workspace').mkdir()
        (self.root / 'data').mkdir()
        self.write(self.amy / 'access.json', {'mounts': {'ws': 'workspace'}, 'cwd': 'ws', 'net': False})
        before = (self.amy / 'info.json').read_bytes()
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        agent = [PY, str(CLI / 'aos-agent')]
        with info_lock(self.amy):
            procs = [subprocess.Popen(agent + ['tools', 'alias', 'read', 'cat', '--target', str(self.amy)], env=env,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True),
                     subprocess.Popen(agent + ['access', 'set', 'data', str(self.root / 'data'), '--target', str(self.amy)],
                                      env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)]
            try:
                for p in procs:
                    with self.assertRaises(subprocess.TimeoutExpired):
                        p.wait(timeout=1.5)           # 兩個寫者都卡在鎖上
                self.assertEqual((self.amy / 'info.json').read_bytes(), before)
                self.assertEqual(read_json(self.amy / 'access.json')['mounts'], {'ws': 'workspace'})
            except BaseException:
                for p in procs:
                    p.kill()
                    p.communicate()
                raise
        for p in procs:
            out, err = p.communicate(timeout=30)
            self.assertEqual(p.returncode, 0, out + err)
        self.assertTrue((self.amy / LOCK_NAME).is_file())
        self.assertEqual(self.info()['tools'], [{'$opt': {'as': {'read': 'cat'}}, '$val': 'tools/mine.json'}])
        self.assertEqual(read_json(self.amy / 'access.json')['mounts']['data'], str(self.root / 'data'))


if __name__ == '__main__':
    unittest.main()
