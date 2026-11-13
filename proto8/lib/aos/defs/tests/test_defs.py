"""Verify public definition discovery, three-axis identity, references and check failures."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ENTRY = Path(__file__).resolve().parents[1] / '_entry'
PROTO = ENTRY.parents[3]
TOOLS_BIN = PROTO / 'cmd' / 'aos-tools' / 'bin'


class DefinitionsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value) if not isinstance(value, str) else value)

    def definition(self, name, endpoint='terra', tool=None):
        path = self.root / name
        self.write(path / 'interfaces.json', {'aos-agent': {'tools': 'tools.json', 'llm': 'llm.json'}})
        self.write(path / '_metainfo.json', {'summary': 'Example worker', 'lineage': {'from': 'retired/missing'}})
        self.write(path / 'README.md', 'Example worker\n')
        self.write(path / 'system.txt', 'A prompt')
        self.write(path / 'tools.json', {'tools': tool or {}})
        self.write(path / 'llm.json', {'model': endpoint})
        return path

    def call(self, op, entry=ENTRY, path=None, **extra):
        env = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}
        env['PATH'] = '%s:%s' % (TOOLS_BIN, env.get('PATH', '')) if path is None else path     # aos-tools is found on PATH
        result = subprocess.run([sys.executable, str(entry)], input=json.dumps({'op': op, 'root': str(self.root), **extra}), text=True, capture_output=True, env=env)
        return result, json.loads(result.stdout) if result.stdout else None

    def test_prompt_ignored_endpoint_distinct_and_non_agent_excluded(self):
        a = self.definition('category/a')
        b = self.definition('category/b')
        self.write(b / 'system.txt', 'Different prompt')
        self.definition('category/c', endpoint='luna')
        self.write(self.root / 'script/interfaces.json', {})
        self.write(self.root / 'script/_metainfo.json', {'summary': 'Script'})
        result, data = self.call('dup')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([g['members'] for g in data['groups']], [['category/a', 'category/b']])
        self.assertEqual(json.loads(data['groups'][0]['key'])['endpoint'], 'terra')

    def test_tools_use_resolved_set_ignore_names_and_env(self):
        shared = self.root / 'shared'
        shared.mkdir()
        (self.root / 'alias').symlink_to(shared, target_is_directory=True)
        self.definition('a', tool={'one': {'path': '../shared', 'env': {'X': 'a'}}})
        self.definition('b', tool={'two': {'path': '../alias', 'env': {'X': 'b'}}, 'repeat': {'path': '../shared'}})
        self.definition('c', tool={'other': {'path': '../different'}})
        _, data = self.call('dup')
        self.assertEqual(data['groups'][0]['members'], ['a', 'b'])

    def test_directive_tool_paths_kept_as_written(self):
        home = {'$env': 'AOS_HOME', '$path': '/lib/base/peek_now_time'}
        self.definition('a', tool={'clock': {'path': home}})
        self.definition('b', tool={'time': {'path': {'$path': '/lib/base/peek_now_time', '$env': 'AOS_HOME'}}})
        self.definition('c', tool={'clock': {'path': {'$env': 'AOS_HOME', '$path': '/lib/base/read'}}})
        result, data = self.call('dup')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([g['members'] for g in data['groups']], [['a', 'b']])
        result, data = self.call('refs', **{'def': 'c'})
        self.assertEqual((result.returncode, data), (0, {'refs': []}))
        self.definition('d', tool={'x': {'path': {'$path': '/x'}}})
        result, data = self.call('check')
        self.assertIn('each tool must declare a path', json.dumps(data))

    def test_override_packs_are_merged(self):
        """11-10 tool-packs：tools.json 疊 "$override"（範本疊 lib/packs），只帶 env 的格沿用底檔的 path。"""
        pack = {'$env': 'AOS_HOME', '$path': '/lib/packs/gadgets.json'}
        a = self.definition('a')
        self.write(a / 'tools.json', {'$override': [pack], 'tools': {'math': {'env': {'X': '1'}}}})
        b = self.definition('b')
        self.write(b / 'tools.json', {'$override': pack, 'tools': {}})
        result, data = self.call('check')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result, data = self.call('dup')
        self.assertEqual([g['members'] for g in data['groups']], [['a', 'b']])
        self.assertIn('/lib/base/peek_clock', data['groups'][0]['key'])

    def packed(self):
        d = self.definition('a')
        self.write(d / 'tools.json', {'$override': [{'$env': 'AOS_HOME', '$path': '/lib/packs/gadgets.json'}], 'tools': {}})
        return d

    def test_override_merge_from_a_copied_lib_without_cmd(self):
        """11-13: lib copied into a tree that has no cmd/ (an aos home): aos-tools comes from PATH, AOS_HOME defaults to that tree."""
        self.packed()
        home = Path(tempfile.mkdtemp(prefix='defs-home-'))
        self.addCleanup(shutil.rmtree, home, True)
        skip = shutil.ignore_patterns('tests', '__pycache__')
        for part in ('aos/defs', 'packs', 'base'):
            shutil.copytree(PROTO / 'lib' / part, home / 'lib' / part, ignore=skip)
        shutil.copy(PROTO / 'lib' / 'tool_io.py', home / 'lib' / 'tool_io.py')
        self.assertFalse((home / 'cmd').exists())
        result, data = self.call('check', entry=home / 'lib' / 'aos' / 'defs' / '_entry')
        self.assertEqual(data, {'problems': []}, result.stderr)
        self.assertEqual(result.returncode, 0, result.stderr)
        result, data = self.call('ls', entry=home / 'lib' / 'aos' / 'defs' / '_entry')
        self.assertIn('{"$env":"AOS_HOME","$path":"/lib/base/peek_clock"}', data['defs'][0]['tools'])   # the pack was merged; paths stay as written

    def test_override_merge_needs_aos_tools_on_path(self):
        self.packed()
        empty = self.root.parent / (self.root.name + '-bin')
        empty.mkdir()
        self.addCleanup(shutil.rmtree, empty, True)
        result, data = self.call('check', path=str(empty))
        self.assertEqual(result.returncode, 1)
        self.assertEqual([p['path'] for p in data['problems']], ['a'])
        self.assertIn('aos-tools is not on PATH (put it there with proto8/install.sh)', data['problems'][0]['reason'])
        self.assertIn('defs: error: DefBad 1 definition problems found', result.stderr)

    def test_discovery_stops_at_definition_and_skips_hidden(self):
        self.definition('category/a')
        self.definition('category/a/nested')
        self.definition('.prev/old')
        self.definition('retired/old')
        _, data = self.call('ls', match='WORKER')
        self.assertEqual([x['path'] for x in data['defs']], ['category/a', 'retired/old'])
        _, data = self.call('ls', match='CATEGORY')
        self.assertEqual(len(data['defs']), 1)
        _, data = self.call('ls', match='absent')
        self.assertEqual(data, {'defs': []})

    def test_refs_tool(self):
        self.definition('target')
        self.definition('direct', tool={'x': {'path': '../target'}})
        self.definition('env_only', tool={'x': {'path': '../other_tool', 'env': {'SOME_FROM': str(self.root / 'target')}}})
        self.definition('other')
        result, data = self.call('refs', **{'def': 'target'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(data, {'refs': ['direct']})                 # env 裡寫的路徑不算引用（11-11 舊 do_task 的 AOS_DO_TASK_FROM 拿掉）

    def test_nested_tool_table_paths(self):
        self.definition('target')
        caller = self.definition('caller')
        self.write(caller / 'interfaces.json', {'aos-agent': {'tools': 'cfg/tools.json', 'llm': 'llm.json'}})
        self.write(caller / 'cfg/tools.json', {'tools': {'x': {'path': '../../target'}}})
        _, data = self.call('ls', match='caller')
        self.assertEqual(data['defs'][0]['tools'], ['target'])
        _, data = self.call('refs', **{'def': 'target'})
        self.assertEqual(data['refs'], ['caller'])

    def test_check_good_does_not_require_existing_lineage(self):
        self.definition('good')
        result, data = self.call('check')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(data, {'problems': []})

    def test_check_missing_interfaces_json_has_json_stdout(self):
        self.write(self.root / 'bad/_metainfo.json', {'summary': 'Broken'})
        self.write(self.root / 'bad/README.md', 'Broken\n')
        result, data = self.call('check')
        self.assertEqual(result.returncode, 1)
        self.assertIn('defs: error: DefBad', result.stderr)
        self.assertIn('interfaces.json', data['problems'][0]['reason'])

    def test_check_each_required_field(self):
        for field in ('readme', 'summary', 'tools', 'llm', 'name'):
            with self.subTest(field=field):
                root = self.root / field
                root.mkdir()
                old = self.root
                self.root = root
                path = self.definition('Bad!' if field == 'name' else 'bad')
                if field == 'readme':
                    self.write(path / 'README.md', '\ntext')
                elif field == 'summary':
                    self.write(path / '_metainfo.json', {})
                elif field in ('tools', 'llm'):
                    self.write(path / (field + '.json'), 'broken')
                result, data = self.call('check')
                self.assertEqual(result.returncode, 1)
                self.assertTrue(data['problems'])
                self.root = old

    def test_check_system_declaration(self):
        path = self.definition('good')
        for value, ok in (('system.txt', True), ('missing.txt', True), ('/etc/x', False), ('../x', False), ('', False), (3, False), ('.', False)):
            with self.subTest(value=value):
                self.write(path / 'interfaces.json', {'aos-agent': {'tools': 'tools.json', 'llm': 'llm.json', 'system': value}})
                result, data = self.call('check')
                self.assertEqual(result.returncode, 0 if ok else 1, result.stderr)
                if not ok:
                    self.assertIn('aos-agent.system', data['problems'][0]['reason'])

    def test_metadata_only_definition_is_listed_without_brain(self):
        self.write(self.root / 'script/_metainfo.json', {'summary': 'Script'})
        result, data = self.call('ls')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(data['defs'], [{'path': 'script', 'summary': 'Script', 'brain': False}])

    def test_metainfo_with_only_an_index_is_not_a_definition(self):
        """11-12 metainfo M11：只放了 index（N-69 的口子）、沒有入口的 _metainfo.json 不算定義，而且繼續往下找。"""
        self.write(self.root / 'notes/_metainfo.json', {'index': {'a': {'description': 'A folder'}}})
        self.definition('notes/a')
        result, data = self.call('ls')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([x['path'] for x in data['defs']], ['notes/a'])
        result, data = self.call('check')
        self.assertEqual((result.returncode, data), (0, {'problems': []}), result.stderr)
        self.assertNotIn('summary', result.stdout + result.stderr)

    def test_empty_or_other_key_metainfo_is_a_definition(self):
        """使用者 11-12「只有{}的_metainfo.json也算agent定義。」；description 不是 _metainfo 的通用格，帶它的也算定義。"""
        for value in ({}, {'description': 'x'}, {'index': {}, 'summary': 'S'}):
            with self.subTest(value=value):
                root = self.root / str(len(list(self.root.iterdir())))
                self.write(root / 'd/_metainfo.json', value)
                self.write(root / 'd/inner/_metainfo.json', {'summary': 'Inner'})
                old, self.root = self.root, root
                _, data = self.call('ls')
                self.root = old
                self.assertEqual([x['path'] for x in data['defs']], ['d'])      # 停在 d、不往下找

    def test_root_is_one_definition(self):
        """11-12 Q10（使用者裁 a）：root 本身就是定義時 path 照「相對 root」印 "."、它自己的名字照查；沒有定義的夾＝空清單、check 算過。"""
        for name, ok in (('good_one', True), ('Bad!', False)):
            with self.subTest(name=name):
                path = self.definition(name)
                old, self.root = self.root, path
                result, data = self.call('check')
                self.root = old
                self.assertEqual(result.returncode, 0 if ok else 1, result.stdout + result.stderr)
                if not ok:
                    self.assertEqual(data['problems'], [{'path': '.', 'reason': "definition folder name 'Bad!' must match [a-z0-9_-]+"}])
        empty = self.root / 'empty'
        empty.mkdir()
        old, self.root = self.root, empty
        result, data = self.call('check')
        self.root = old
        self.assertEqual((result.returncode, data), (0, {'problems': []}))

    def test_errors_and_empty_tree(self):
        _, data = self.call('dup')
        self.assertEqual(data, {'groups': []})
        for payload, code in (({'op': 'unknown'}, 'CommandUnknown'),
                              ({'op': 'refs'}, 'ArgumentsBad'),
                              ({'op': 'ls', 'root': str(self.root / 'missing')}, 'RootMissing')):
            result = subprocess.run([str(ENTRY)], input=json.dumps({'root': str(self.root), **payload}), text=True, capture_output=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn(code, result.stderr)
            self.assertNotIn('Traceback', result.stderr)

    def test_default_endpoint_and_help(self):
        self.definition('a', endpoint='')
        _, data = self.call('ls')
        self.assertEqual(data['defs'][0]['endpoint'], '')
        self.definition('b', endpoint='default')
        c = self.definition('c')
        self.write(c / 'llm.json', {})
        _, groups = self.call('dup')
        self.assertEqual([g['members'] for g in groups['groups']], [['b', 'c']])
        result = subprocess.run([str(ENTRY), '--help'], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('--root', result.stdout)


if __name__ == '__main__':
    unittest.main()
