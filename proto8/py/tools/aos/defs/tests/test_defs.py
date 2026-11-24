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
PROTO = ENTRY.parents[4]
TOOLS_BIN = PROTO / 'bin'


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
        self.write(path / '_metainfo.json', {'summary': 'Example worker'})
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
        home = {'$env': 'AOS_HOME', '$path': '/lib/tools/base/peek_now_time'}
        self.definition('a', tool={'clock': {'path': home}})
        self.definition('b', tool={'time': {'path': {'$path': '/lib/tools/base/peek_now_time', '$env': 'AOS_HOME'}}})
        self.definition('c', tool={'clock': {'path': {'$env': 'AOS_HOME', '$path': '/lib/tools/base/read'}}})
        result, data = self.call('dup')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([g['members'] for g in data['groups']], [['a', 'b']])
        result, data = self.call('refs', **{'def': 'c'})
        self.assertEqual((result.returncode, data), (0, {'refs': []}))
        self.definition('d', tool={'x': {'path': {'$path': '/x'}}})
        result, data = self.call('check')
        self.assertIn('each tool must declare a path', json.dumps(data))

    def test_override_packs_are_merged(self):
        """11-10 tool-packs：tools.json 疊 "$override"（範本疊 py/packs），只帶 env 的格沿用底檔的 path。"""
        pack = {'$env': 'AOS_HOME', '$path': '/lib/packs/gadgets.json'}
        a = self.definition('a')
        self.write(a / 'tools.json', {'$override': [pack], 'tools': {'math': {'env': {'X': '1'}}}})
        b = self.definition('b')
        self.write(b / 'tools.json', {'$override': pack, 'tools': {}})
        result, data = self.call('check')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result, data = self.call('dup')
        self.assertEqual([g['members'] for g in data['groups']], [['a', 'b']])
        self.assertIn('/lib/tools/base/peek_clock', data['groups'][0]['key'])

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
        for part in ('tools/aos/defs', 'packs', 'tools/base', 'tools/agent/do_task'):   # 11-19：check 也查包裡的工具在不在（gadgets 有 do_task）
            shutil.copytree(PROTO / 'py' / part, home / 'lib' / part, ignore=skip)
        shutil.copytree(PROTO / 'py' / 'aos', home / 'lib' / 'aos', ignore=skip)
        # 11-19：腦設定照 lib/aos/apps/agent_fsm/llm_settings.py 的規則查（隨上面的 lib/aos 抄到）
        self.assertFalse((home / 'cmd').exists())
        result, data = self.call('check', entry=home / 'lib' / 'tools' / 'aos' / 'defs' / '_entry')
        self.assertEqual(data, {'problems': []}, result.stderr)
        self.assertEqual(result.returncode, 0, result.stderr)
        result, data = self.call('ls', entry=home / 'lib' / 'tools' / 'aos' / 'defs' / '_entry')
        self.assertIn('{"$env":"AOS_HOME","$path":"/lib/tools/base/peek_clock"}', data['defs'][0]['tools'])   # the pack was merged; paths stay as written

    def test_override_merge_needs_aos_tools_on_path(self):
        self.packed()
        empty = self.root.parent / (self.root.name + '-bin')
        empty.mkdir()
        self.addCleanup(shutil.rmtree, empty, True)
        result, data = self.call('check', path=str(empty))
        self.assertEqual(result.returncode, 1)
        self.assertEqual([p['path'] for p in data['problems']], ['a'])
        self.assertIn('aos-tools is not on PATH (source $AOS_HOME/env.sh)', data['problems'][0]['reason'])
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

    def test_check_good(self):
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

    def test_check_broken_link_is_one_problem(self):
        """11-20 cut 4 (defs.extern compiles into a link): a link to nothing is one problem, before the checks that read through it."""
        shared = self.root / 'shared-files'
        path = self.definition('good')
        self.write(shared / 'system.txt', 'Shared prompt')
        self.write(shared / 'tools.json', {'tools': {}})
        for name in ('system.txt', 'tools.json'):
            (path / name).unlink()
            (path / name).symlink_to('../shared-files/' + name)
        result, data = self.call('check')
        self.assertEqual((result.returncode, data['problems']), (0, []), result.stderr)     # links that work are fine
        (shared / 'tools.json').unlink()
        result, data = self.call('check')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(data['problems']), 1, data)
        self.assertEqual(data['problems'][0]['path'], 'good')
        self.assertIn('tools.json is a link to ../shared-files/tools.json, which is not there', data['problems'][0]['reason'])

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

    # ---- 11-19 aos-check-refs（使用者選「只放進檢查指令」）：叫的東西在不在、腦設定的型別 ----
    def reasons(self, **env):
        result, data = self.call('check', **env)
        return result, [p['reason'] for p in data['problems']], [w['reason'] for w in data.get('warnings', [])]

    def runnable(self, name='a', fsm=None, loop=None, hooks=None):
        """A definition with an entry → aos-loop loop.json → fsm.json, like the agent-fsm template, and a hookeds list."""
        path = self.definition(name)
        self.write(path / 'interfaces.json', {'aos-agent': {'entry': 'body.json', 'tools': 'tools.json', 'llm': 'llm.json',
                                                            'llm_keys': ['model', 'temperature', 'max_tokens', 'top_p']},
                                                'hookeds': 'hookeds.json'})
        self.write(path / 'body.json', {'argv': ['aos-loop', 'loop.json']})
        self.write(path / 'loop.json', loop or {'exec': 'fsm.json', 'interval_ms': 300})
        self.write(path / 'fsm.json', fsm or {'start': 'idle', 'states': {'idle': {'exec': {'argv': ['python3', 'idle.py']}, 'next': {'0': 'idle'}}}})
        self.write(path / 'idle.py', 'print(1)\n')
        self.write(path / 'hookeds.json', hooks or {})
        return path

    def test_check_tool_path_that_does_not_exist(self):
        """G1：寫錯的工具路徑——執行時被 aos-tools 略過、腦看不到；check 照 aos-tools ls 的讀法報出來。"""
        self.definition('a', tool={'ghost': {'path': {'$env': 'AOS_HOME', '$path': '/lib/tools/base/nope'}},
                                   'rel': {'path': 'not/there'},
                                   'read': {'path': {'$env': 'AOS_HOME', '$path': '/lib/tools/base/read'}}})
        result, problems, warnings = self.reasons()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(len(problems), 2, problems)
        self.assertIn('tool ghost cannot be used (PathMissing', problems[0])
        self.assertIn('/lib/tools/base/nope', problems[0])
        self.assertIn('tools.json#/tools/ghost', problems[0])
        self.assertIn('tool rel cannot be used (PathMissing', problems[1])
        self.assertEqual(warnings, [])

    def test_check_tool_path_with_an_unset_variable_is_a_warning(self):
        """變數這裡沒設：照實說沒查，不當成 problem（執行時那個變數可能有）。"""
        self.definition('a', tool={'lib': {'path': {'$env': 'AOS_CHECK_REFS_NOT_SET', '$path': '/tools/x'}}})
        result, problems, warnings = self.reasons()
        self.assertEqual((result.returncode, problems), (0, []), result.stdout + result.stderr)
        self.assertEqual(len(warnings), 1, warnings)
        self.assertIn('environment variable AOS_CHECK_REFS_NOT_SET is not set here', warnings[0])
        b = self.definition('b')                      # 疊 $override 的也一樣（describe 那邊不再報成 problem）
        self.write(b / 'tools.json', {'$override': {'$env': 'AOS_CHECK_REFS_NOT_SET', '$path': '/packs/x.json'}, 'tools': {}})
        result, problems, warnings = self.reasons()
        self.assertEqual((result.returncode, problems), (0, []), result.stdout + result.stderr)
        self.assertEqual(len(warnings), 2, warnings)

    def test_check_tool_paths_without_aos_tools_is_a_warning(self):
        self.definition('a', tool={'x': {'path': 'not/there'}})
        empty = self.root.parent / (self.root.name + '-bin2')
        empty.mkdir()
        self.addCleanup(shutil.rmtree, empty, True)
        result, problems, warnings = self.reasons(path=str(empty))
        self.assertEqual((result.returncode, problems), (0, []), result.stdout)
        self.assertIn('tool paths not checked: aos-tools is not on PATH', warnings[0])

    def test_check_programs_the_agent_runs(self):
        """G1：狀態格、loop、hook 指到的程式不在——執行時一起來就停；check 找出分得出是檔的位置。"""
        home = {'$env': 'AOS_HOME', '$path': '/lib/tools/agent/nope'}
        self.runnable(fsm={'start': 'idle', 'states': {
            'idle': {'exec': {'argv': ['python3', 'idle.py']}, 'next': {'0': 'think'}},
            'think': {'exec': {'argv': ['python3', '-u', 'nocell.py', 'out.txt']}, 'next': {'0': 'idle'}},
            'mod': {'exec': {'argv': ['python3', '-m', 'json.tool']}, 'next': {'0': 'idle'}},
            'std': {'exec': {'argv': ['python3', {'$env': 'AOS_HOME', '$path': '/templates/agents/agent-fsm/nope.py'}]}, 'next': {'0': 'idle'}},
            'sub': {'exec': {'argv': ['./gone.sh'], 'cwd': 'cells'}, 'next': {'0': 'idle'}},
            'tool': {'exec': 'missing_tool', 'next': {'0': 'idle'}}}},
            loop={'exec': 'fsm.json', 'on_start': {'argv': [home, 'after_start', {'$env': 'AOS_CD'}]}},
            hooks={'description': 'test hooks', 'gone': {'event': 'on_clock', 'handler': 'hookeds/gone'}, 'off': None,
                   'ok': {'event': 'on_clock', 'handler': {'$env': 'AOS_HOME', '$path': '/lib/tools/agent/hook_noop'}}})
        result, problems, warnings = self.reasons()
        self.assertEqual(result.returncode, 1, result.stdout)
        text = '\n'.join(problems)
        for want in ('fsm.json#/states/think/exec/argv/2: script "nocell.py" does not exist',
                     'fsm.json#/states/std/exec/argv/1: script {"$env": "AOS_HOME", "$path": "/templates/agents/agent-fsm/nope.py"} does not exist',
                     'fsm.json#/states/sub/exec/argv/0: program "./gone.sh" does not exist (looked for cells/gone.sh)',
                     'fsm.json#/states/tool/exec: target "missing_tool" does not exist',
                     'loop.json#/on_start/argv/0: program {"$env": "AOS_HOME", "$path": "/lib/tools/agent/nope"} does not exist',
                     'hookeds.json#/gone/handler: handler "hookeds/gone" does not exist'):
            self.assertIn(want, text)
        self.assertEqual(len(problems), 6, text)       # idle.py、-m、out.txt、AOS_CD、null 的 hook、在的 handler 都不報
        self.assertEqual(warnings, [])

    def test_check_follows_the_loop_and_reports_a_missing_table(self):
        path = self.runnable(loop={'exec': 'table.json'})
        result, problems, _ = self.reasons()
        self.assertEqual(problems, ['loop.json#/exec: target "table.json" does not exist (looked for table.json)'])
        self.write(path / 'body.json', {'argv': ['aos-loop', 'nowhere.json']})
        result, problems, _ = self.reasons()
        self.assertEqual(problems, ['body.json#/argv/1: config file "nowhere.json" does not exist (looked for nowhere.json)'])
        self.write(path / 'body.json', ['aos-loop', 'nowhere.json'])          # agent-fsm 的寫法：整份就是 argv
        result, problems, _ = self.reasons()
        self.assertEqual(problems, ['body.json#/1: config file "nowhere.json" does not exist (looked for nowhere.json)'])
        (path / 'body.json').unlink()
        result, problems, _ = self.reasons()
        self.assertEqual(problems, ['aos-agent.entry "body.json" does not exist'])

    def test_check_program_with_an_unset_variable_or_off_path_command(self):
        self.runnable(fsm={'start': 'idle', 'states': {
            'idle': {'exec': {'argv': ['python3', {'$env': 'AOS_CHECK_REFS_NOT_SET', '$path': '/cell.py'}]}, 'next': {'0': 'idle'}},
            'x': {'exec': {'argv': ['aos-check-refs-no-such-command', 'a']}, 'next': {'0': 'idle'}},
            'st': {'exec': {'argv': ['python3', {'$env': 'AOS_STACK', '$path': '/made.py'}]}, 'next': {'0': 'idle'}}}})
        result, problems, warnings = self.reasons()
        self.assertEqual((result.returncode, problems), (0, []), result.stdout)
        self.assertEqual(len(warnings), 2, warnings)
        self.assertIn('fsm.json#/states/idle/exec/argv/1: script {"$env": "AOS_CHECK_REFS_NOT_SET", "$path": "/cell.py"} not checked: '
                      'environment variable AOS_CHECK_REFS_NOT_SET is not set here', warnings[0])
        self.assertIn('command "aos-check-refs-no-such-command" is not on PATH here', warnings[1])

    def test_check_brain_settings_types(self):
        """G1：LLM 值型別錯——執行時 brain.py 報 CfgBad；check 用同一份 llm_settings 轉型。model 名對不對不查（要問 kernel）。"""
        path = self.runnable()
        for cfg, want in (({'model': 'no-such-brain', 'temperature': '0.5', 'max_tokens': 100}, []),
                          ({'model': 'fake', 'temperature': 'hot'}, ['temperature in llm.json must be a number, not "hot"']),
                          ({'max_tokens': -5}, ['llm.json: max_tokens must be at least 1, not -5']),
                          ({'max_tokens': 1.5}, ['max_tokens in llm.json must be an integer, not 1.5']),
                          ({'top_p': 2}, ['llm.json: top_p must be between 0 and 1, not 2']),
                          ({'model': ''}, ['model in llm.json must be a non-empty string (a brain pack name of the llm kernel)']),
                          ({'temperature': True}, ['temperature in llm.json must be a number, not true'])):
            with self.subTest(cfg=cfg):
                self.write(path / 'llm.json', dict(cfg, description='Brain settings'))
                result, problems, warnings = self.reasons()
                self.assertEqual(problems, want)
                self.assertEqual(result.returncode, 1 if want else 0)
                self.assertEqual(warnings, [])
        self.write(path / 'llm.json', {'model': 'fake', 'seed': 'x', 'colour': 'blue'})   # 不在 llm_keys 的：body 不讀＝warning
        result, problems, warnings = self.reasons()
        self.assertEqual((result.returncode, problems), (0, []), result.stdout)
        self.assertEqual(warnings, ['llm.json: key "colour" is not one of llm_keys in interfaces.json (model, temperature, max_tokens, top_p), so the body does not read it',
                                    'llm.json: key "seed" is not one of llm_keys in interfaces.json (model, temperature, max_tokens, top_p), so the body does not read it'])

    def test_check_stock_templates_have_no_findings(self):
        """骨架與範本照抄出去 check：沒有 problem、沒有 warning（範本自己的指令都在 PATH 上、路徑都在）。"""
        for name in ('agent-fsm', 'agent-python', 'reviewer', 'eca-claude'):
            with self.subTest(template=name):
                root = self.root / ('t-' + name)
                shutil.copytree(PROTO / 'templates' / 'agents' / name, root / 'd', ignore=shutil.ignore_patterns('__pycache__'))
                old, self.root = self.root, root / 'd'
                result, data = self.call('check')
                self.root = old
                self.assertEqual((result.returncode, data), (0, {'problems': []}), result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
