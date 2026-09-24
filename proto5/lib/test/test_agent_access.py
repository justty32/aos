"""權限牆（spec/agent/access.md、spec/aos-agent/access.md）：解析、信任資料重疊、送件包牢、access CLI、check／status。

不起 daemon／kernel：送件用假 K 家（照 test_agent_tick 的做法）；bwrap 真的跑只在 check 那兩條（沒 bwrap 就 skip）。
"""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import aos_agent as agent
import aos_agent_access as acc
import aos_agent_batch as batch_api
import aos_agent_check
import aos_agent_cli
import aos_agent_info as info_api
import aos_agent_status
import aos_inst
from aos_agent_home import AgentError

TOOL_CALL = {'id': 'c1', 'type': 'function', 'function': {'name': 'sh', 'arguments': '{"x": 1}'}}
ASSISTANT = {'role': 'assistant', 'content': None, 'tool_calls': [TOOL_CALL]}
HAS_BWRAP = aos_agent_check.bwrap_probe(os.environ)[0]      # 跟 test_jail 一樣：真的開得起來才算


class Home(unittest.TestCase):
    """一個 agent 家 self.base（有 info.json、workspace/）、假 K 家 self.k。"""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(os.path.realpath(temp.name))
        self.base, self.k = self.root / 'amy', self.root / 'K'
        (self.base / 'workspace').mkdir(parents=True)
        (self.k / 'requests').mkdir(parents=True)
        (self.k / 'responses').mkdir()
        self.env = {'AOS_KERNEL_HOME': str(self.k), 'PATH': os.environ.get('PATH', os.defpath)}
        self.info = {'_metainfo': {'_type': 'llm_agent', '_version': 1}, 'llm': {'model': 'small'}}
        self.put(self.base / 'info.json', self.info)
        self.put(self.k / 'info.json', {})
        self.put(self.k / 'state.json', {'procs': {}, 'replies': []})

    def put(self, path, value):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False),
                        encoding='utf-8')
        return path

    def read(self, path):
        return json.loads(Path(path).read_text(encoding='utf-8'))

    def access(self, value):
        return self.put(self.base / 'access.json', value)

    def load(self, env=None):
        return acc.load(self.base, env=self.env if env is None else env)

    def error(self, code, env=None):
        with self.assertRaises(AgentError) as cm:
            self.load(env)
        self.assertEqual(cm.exception.code, code, cm.exception)
        return str(cm.exception)


class ParseTests(Home):
    def test_no_file_means_no_jail(self):
        self.assertIsNone(acc.access_path(self.base))
        self.assertIsNone(self.load())
        self.assertIsNone(acc.snapshot(self.base, self.env))

    def test_good_table_with_tilde_and_ro(self):
        docs = self.root / 'home' / 'docs'
        docs.mkdir(parents=True)
        self.access({'_metainfo': {'_type': 'agent_access', '_version': 1},
                     'mounts': {'ws': 'workspace', 'ref': {'$opt': 'ro', '$val': '~/docs'}},
                     'cwd': 'ws', 'net': False})
        with patch.dict(os.environ, {'HOME': str(self.root / 'home')}):
            table = self.load()
        self.assertEqual(table, {'mounts': {'ws': {'path': str(self.base / 'workspace'), 'ro': False},
                                            'ref': {'path': str(docs), 'ro': True}},
                                 'cwd': 'ws', 'net': False})

    def test_defaults(self):
        self.access({})
        self.assertEqual(self.load(), {'mounts': {}, 'cwd': None, 'net': False})

    def test_directives_env_ref_fmt(self):
        (self.root / 'A').mkdir()
        (self.root / 'B').mkdir()
        self.put(self.base / 'where.json', {'ws': str(self.root / 'A')})
        self.access({'mounts': {'ws': {'$ref': 'where.json#/ws'},
                                'b': {'$opt': 'ro', '$val': {'$env': 'B_DIR'}},
                                'c': {'$fmt': {'$val': '${r}/B', 'r': str(self.root)}}},
                     'net': {'$env': 'NET_IS'}})
        with self.assertRaises(AgentError) as cm:
            self.load(dict(self.env, B_DIR=str(self.root / 'B')))
        self.assertIn('net', str(cm.exception))          # $env 解出字串，不是 bool
        self.access({'mounts': {'ws': {'$ref': 'where.json#/ws'},
                                'b': {'$opt': 'ro', '$val': {'$env': 'B_DIR'}},
                                'c': {'$fmt': {'$val': '${r}/B', 'r': str(self.root)}}}})
        table = self.load(dict(self.env, B_DIR=str(self.root / 'B')))
        self.assertEqual(table['mounts']['ws']['path'], str(self.root / 'A'))
        self.assertEqual(table['mounts']['b'], {'path': str(self.root / 'B'), 'ro': True})
        self.assertFalse(table['mounts']['c']['ro'])
        text = self.error('AccessInvalid')                 # 沒有 B_DIR
        self.assertIn('mounts.b', text)
        self.assertIn('EnvironmentVariableMissing', text)

    def test_json_syntax_has_line_and_column(self):
        self.access('{\n  "mounts": {"ws": "workspace",}\n}')
        text = self.error('JsonSyntax')
        self.assertIn('第 2 行', text)
        self.assertIn(str(self.base / 'access.json'), text)

    def test_bad_shapes_name_their_position(self):
        cases = [({'mount': {}}, 'mount'), ({'mounts': {'WS': 'workspace'}}, 'mounts.WS'),
                 ({'mounts': {'.': 'workspace'}}, 'mounts..'),
                 ({'mounts': {'ws': 'nope'}}, 'mounts.ws'), ({'mounts': {'ws': 3}}, 'mounts.ws'),
                 ({'mounts': {'ws': {'$opt': 'rw', '$val': 'workspace'}}}, 'mounts.ws'),
                 ({'mounts': {'ws': {'$opt': 'ro'}}}, 'mounts.ws'),
                 ({'mounts': ['workspace']}, 'mounts'),
                 ({'mounts': {'ws': 'workspace'}, 'cwd': 'other'}, 'cwd'),
                 ({'net': 'yes'}, 'net'), ({'_metainfo': {'_type': 'llm_agent', '_version': 1}}, '_metainfo'),
                 ({'_metainfo': {'_type': 'agent_access', '_version': True}}, '_metainfo'), ([], '頂層')]
        for value, where in cases:
            with self.subTest(value=value):
                self.access(value)
                text = self.error('AccessInvalid')
                self.assertIn('access.json 的 %s' % where, text)

    def test_file_not_a_dir(self):
        self.put(self.base / 'workspace' / 'f.txt', 'x')
        self.access({'mounts': {'ws': 'workspace/f.txt'}})
        self.assertIn('不是資料夾', self.error('AccessInvalid'))

    def test_info_access_field_points_elsewhere(self):
        other = self.root / 'shared' / 'amy-access.json'
        self.put(other, {'mounts': {'ws': 'workspace'}, 'cwd': 'ws'})   # 相對的仍算 agent 家
        self.put(self.base / 'info.json', dict(self.info, access={'$fmt': {'$val': '../shared/${n}',
                                                                         'n': 'amy-access.json'}}))
        self.assertEqual(acc.access_path(self.base), other)
        self.assertEqual(self.load()['mounts']['ws']['path'], str(self.base / 'workspace'))
        other.unlink()
        self.assertIsNone(acc.access_path(self.base))
        self.assertIn('檔不在', self.error('AccessInvalid'))

    def test_ensure_default(self):
        shutil.rmtree(self.base / 'workspace')
        message = acc.ensure_default(self.base, 'workspace')
        self.assertIn('寫了', message)
        self.assertIn('access set', message)
        self.assertTrue((self.base / 'workspace').is_dir())
        self.assertEqual(self.read(self.base / 'access.json'),
                         {'_metainfo': {'_type': 'agent_access', '_version': 1},
                          'mounts': {'ws': 'workspace'}, 'cwd': 'ws', 'net': False})
        self.assertIsNone(acc.ensure_default(self.base, 'elsewhere'))
        self.assertFalse((self.base / 'elsewhere').exists())


class OverlapTests(Home):
    def test_self_only_read_only(self):
        self.access({'mounts': {'self': '.'}})
        text = self.error('AccessUnsafe')
        self.assertIn('mounts.self 可寫、但包含', text)
        self.access({'mounts': {'self': {'$opt': 'ro', '$val': '.'}, 'ws': 'workspace'}, 'cwd': 'ws'})
        self.assertTrue(self.load()['mounts']['self']['ro'])

    def test_home_control_folders(self):
        for sub in ('tools', 'work', 'log', 'prompts'):
            with self.subTest(sub=sub):
                (self.base / sub / 'inner').mkdir(parents=True, exist_ok=True)
                self.access({'mounts': {'x': sub + '/inner'}})
                self.assertIn('裡面', self.error('AccessUnsafe'))

    def test_symlink_to_home_is_resolved(self):
        (self.root / 'sneaky').symlink_to(self.base)
        self.access({'mounts': {'ws': '../sneaky'}})
        self.error('AccessUnsafe')

    def test_shared_tool_folder_and_program(self):
        util = self.root / 'util-tools'
        self.put(util / 'bin' / 'edit', '#!/bin/sh\n')
        self.put(util / 'x.json', [{'type': 'function', 'function': {'name': 'edit'},
                                    '_meta': {'argv': [str(util / 'bin' / 'edit')]}}])
        self.put(self.base / 'info.json', dict(self.info, tools=['../util-tools/x.json']))
        self.access({'mounts': {'u': '../util-tools'}})
        self.assertIn('x.json', self.error('AccessUnsafe'))
        self.access({'mounts': {'u': '../util-tools/bin'}})
        self.assertIn('工具程式', self.error('AccessUnsafe'))
        self.access({'mounts': {'u': {'$opt': 'ro', '$val': '../util-tools'}}})
        self.assertTrue(self.load()['mounts']['u']['ro'])

    def test_ref_target_of_access_is_trusted(self):
        ws = self.root / 'ws'
        self.put(ws / 'current.json', {'ws': str(ws)})
        self.access({'mounts': {'ws': {'$ref': '../ws/current.json#/ws'}}})
        self.assertIn('access 設定', self.error('AccessUnsafe'))

    def test_ref_target_of_info_is_trusted(self):
        ws = self.root / 'ws'
        self.put(ws / 'llm.json', {'model': 'small'})
        self.put(self.base / 'info.json', dict(self.info, llm={'model': {'$ref': '../ws/llm.json#/model'}}))
        self.access({'mounts': {'ws': '../ws'}})
        self.assertIn('info.json 引用的檔', self.error('AccessUnsafe'))

    def test_input_and_waits_are_trusted(self):
        self.put(self.base / 'state.json', {'input': 'workspace/in.json', 'waits': ['workspace/go.json']})
        self.access({'mounts': {'ws': 'workspace'}})
        self.assertIn('輸入檔', self.error('AccessUnsafe'))


class SendBase(Home):
    """act 批：快照存 state、inst 包 aos-jail、壞表／沒 bwrap 那件不送、_jail:false 照舊。"""

    def setUp(self):
        super().setUp()
        self.err = io.StringIO()
        self.addCleanup(patch.stopall)
        patch('sys.stderr', self.err).start()
        self.put(self.base / 'prompts/history.json', [ASSISTANT])
        self.tool({'argv': ['tools/bin/sh-tool', '-v'], 'envs': {'FOO': 'bar'}})

    def tool(self, meta, **extra):
        self.put(self.base / 'tools/bin/sh-tool', '#!/bin/sh\n')
        self.put(self.base / 'tools/t.json', [dict({'type': 'function', 'function': {'name': 'sh'},
                                                    '_meta': meta}, **extra)])
        self.put(self.base / 'info.json', dict(self.info, tools=['tools/t.json']))

    def tick(self):
        self.put(self.base / 'state.json', {'state': 'act'})
        self.assertEqual(agent.tick(self.base, self.env), 0, self.err.getvalue())
        return self.read(self.base / 'state.json')['batch']

    def inst(self, batch):
        return self.read(self.base / 'work' / (batch['calls'][0]['name'] + '.inst.json'))


class SendTests(SendBase):
    def test_no_access_file_keeps_old_inst(self):
        batch = self.tick()
        self.assertIsNone(batch['access'])
        inst = self.inst(batch)
        self.assertEqual(inst['argv'], ['tools/bin/sh-tool', '-v'])
        self.assertEqual(inst['envs'], {'FOO': 'bar'})

    def test_snapshot_and_jail_inst(self):
        self.access({'mounts': {'ws': 'workspace', 'ref': {'$opt': 'ro', '$val': 'tools'}}, 'cwd': 'ws'})
        with patch.object(batch_api.shutil, 'which', return_value='/usr/bin/bwrap'):
            batch = self.tick()
        ws = str(self.base / 'workspace')
        self.assertEqual(batch['access'], {'mounts': {'ws': {'path': ws, 'ro': False},
                                                      'ref': {'path': str(self.base / 'tools'), 'ro': True}},
                                           'cwd': 'ws', 'net': False})
        inst = self.inst(batch)
        name = batch['calls'][0]['name']
        self.assertEqual(inst['argv'], [acc.JAIL, '--mount', 'ws=' + ws, '--mount-ro', 'ref=%s/tools' % self.base,
                                        '--chdir', 'ws', '--net', 'off', '--setenv', 'FOO=bar', '--',
                                        str(self.base / 'tools/bin/sh-tool'), '-v'])
        self.assertNotIn('envs', inst)
        self.assertEqual(inst['cwd'], str(self.base))
        self.assertEqual(inst['stdin'], str(self.base / 'work' / (name + '.in')))
        aos_inst.load_obj(inst, str(self.base))
        self.assertTrue((self.k / 'requests' / (name + '.json')).exists())

    def test_meta_cwd_only_affects_outside(self):
        (self.base / 'sub').mkdir()
        self.tool({'argv': ['../tools/bin/sh-tool'], 'cwd': 'sub', 'envs': {'$opt': 'clear', '$val': {}}})
        self.access({'mounts': {'ws': 'workspace'}, 'net': True})
        with patch.object(batch_api.shutil, 'which', return_value='/usr/bin/bwrap'):
            inst = self.inst(self.tick())
        self.assertEqual(inst['cwd'], str(self.base / 'sub'))
        self.assertEqual(inst['argv'][-1], str(self.base / 'sub/../tools/bin/sh-tool'))
        self.assertIn('on', inst['argv'])
        self.assertNotIn('--chdir', inst['argv'])
        self.assertNotIn('envs', inst)

    def test_bad_table_that_batch_does_not_run(self):
        self.access({'mounts': {'ws': 'nope'}})
        batch = self.tick()
        self.assertTrue(batch['access']['error'].startswith('AccessInvalid: '))
        call = batch['calls'][0]
        self.assertTrue(call['acked'])
        self.assertTrue(call['done']['content'].startswith('工具 sh 跑不起來：AccessInvalid: '))
        self.assertIn('mounts.ws', call['done']['content'])
        self.assertFalse(list((self.k / 'requests').iterdir()))

    def test_unsafe_table_that_batch_does_not_run(self):
        self.access({'mounts': {'self': '.'}})
        batch = self.tick()
        self.assertIn('AccessUnsafe', batch['calls'][0]['done']['content'])
        self.assertFalse(list((self.k / 'requests').iterdir()))

    def test_no_bwrap(self):
        self.access({'mounts': {'ws': 'workspace'}})
        with patch.object(batch_api.shutil, 'which', return_value=None):
            batch = self.tick()
        self.assertIn('工具 sh 跑不起來：NoBwrap: 找不到 bwrap', batch['calls'][0]['done']['content'])
        self.assertFalse(list((self.k / 'requests').iterdir()))

    def test_jail_false_runs_as_before(self):
        self.tool({'argv': ['tools/bin/sh-tool']}, _jail=False)
        self.access({'mounts': {'ws': 'nope'}})                   # 壞表也不影響不關牢的那支
        with patch.object(batch_api.shutil, 'which', return_value=None):
            batch = self.tick()
        self.assertEqual(self.inst(batch)['argv'], ['tools/bin/sh-tool'])

    def test_resend_uses_stored_snapshot(self):
        self.access({'mounts': {'ws': 'workspace'}})
        with patch.object(batch_api.shutil, 'which', return_value='/usr/bin/bwrap'), \
                patch.object(agent, '_hook', side_effect=lambda step: (_ for _ in ()).throw(
                    RuntimeError(step)) if step == 'state.batch' else None):
            self.put(self.base / 'state.json', {'state': 'act'})
            with self.assertRaises(RuntimeError):
                agent.tick(self.base, self.env)
        stored = self.read(self.base / 'state.json')['batch']
        self.assertFalse(stored['sent'])
        (self.root / 'B').mkdir()
        self.access({'mounts': {'ws': '../B'}})                    # 批建好之後才改表
        with patch.object(batch_api.shutil, 'which', return_value='/usr/bin/bwrap'):
            self.assertEqual(agent.tick(self.base, self.env), 0, self.err.getvalue())
        batch = self.read(self.base / 'state.json')['batch']
        self.assertIn('ws=%s/workspace' % self.base, self.inst(batch)['argv'])

    def test_think_batch_has_no_access(self):
        self.access({'mounts': {'ws': 'workspace'}})
        self.put(self.base / 'state.json', {'state': 'think'})
        self.assertEqual(agent.tick(self.base, self.env), 0)
        self.assertNotIn('access', self.read(self.base / 'state.json')['batch'])

    def test_state_access_shape(self):
        base = {'kind': 'act', 'kernel': '/K', 'base_len': 1, 'sent': True, 'calls': []}
        good = [None, {'error': 'AccessInvalid: x'},
                {'mounts': {'ws': {'path': '/w', 'ro': False}}, 'cwd': 'ws', 'net': False},
                {'mounts': {}, 'cwd': None, 'net': True}]
        for value in good:
            info_api.check_batch(dict(base, access=value))
        info_api.check_batch(base)                                 # 舊 state 沒這鍵
        bad = [{'error': 3}, {'mounts': {}, 'cwd': 'ws', 'net': False},
               {'mounts': {'ws': {'path': 'rel', 'ro': False}}, 'cwd': None, 'net': False},
               {'mounts': {}, 'cwd': None, 'net': 'no'}, {'mounts': {}, 'cwd': None}, 'x']
        for value in bad:
            with self.subTest(value=value), self.assertRaises(AgentError):
                info_api.check_batch(dict(base, access=value))


class CliBase(Home):
    def cli(self, *args, code=0):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                result = aos_agent_cli.main(['access', *map(str, args), '--target', str(self.base)])
            except SystemExit as exc:
                result = exc.code
        self.assertEqual(result, code, out.getvalue() + err.getvalue())
        return out.getvalue() + err.getvalue()

    def raw(self):
        return self.read(self.base / 'access.json')


class CliTests(CliBase):
    def test_ls_without_file(self):
        out = self.cli('ls')
        self.assertIn('沒有 access.json', out)
        self.assertIn('aos-agent access set ws workspace --cwd', out)
        self.assertIn('bwrap: ', out)
        data = json.loads(self.cli('ls', '--json'))
        self.assertEqual(set(data), {'file', 'exists', 'mounts', 'cwd', 'net', 'bwrap', 'error'})
        self.assertFalse(data['exists'])

    def test_set_relative_to_shell_cwd(self):
        old = os.getcwd()
        self.addCleanup(os.chdir, old)
        os.chdir(self.base)
        out = self.cli('set', 'ws', 'workspace', '--cwd')
        self.assertEqual(out.strip().splitlines()[-1], '下一批工具生效，不用重 start')
        self.assertEqual(self.raw()['mounts'], {'ws': str(self.base / 'workspace')})
        self.assertEqual(self.raw()['cwd'], 'ws')
        self.assertEqual(self.raw()['_metainfo'], {'_type': 'agent_access', '_version': 1})

    def test_set_modes(self):
        self.cli('set', 'ws', self.base / 'workspace', '--cwd')
        out = self.cli('set', 'self', self.base)                  # 新名字＋重疊＝自動 ro
        self.assertIn('所以設成唯讀', out)
        self.assertEqual(self.raw()['mounts']['self'], {'$opt': 'ro', '$val': str(self.base)})
        before = self.raw()
        out = self.cli('set', 'self2', self.base, '--rw', code=1)
        self.assertIn('AccessUnsafe', out)
        self.assertEqual(self.raw(), before)
        (self.root / 'B').mkdir()
        self.cli('set', 'ref', self.root / 'B', '--ro')
        self.cli('set', 'ref', self.root / 'B')                    # 沒給 --ro/--rw＝保留原模式
        self.assertEqual(self.raw()['mounts']['ref'], {'$opt': 'ro', '$val': str(self.root / 'B')})
        self.cli('set', 'ref', self.root / 'B', '--rw')
        self.assertEqual(self.raw()['mounts']['ref'], str(self.root / 'B'))
        self.cli('set', 'ghost', self.root / 'nope', code=1)

    def test_directive_replaced_with_literal(self):
        self.access({'mounts': {'ws': {'$env': 'WS'}}, 'keep': 1})
        self.cli('set', 'ws', self.base / 'workspace', code=1)     # 壞檔（不認得的 keep）：拒絕、不蓋
        self.assertEqual(self.raw()['keep'], 1)
        self.access({'mounts': {'ws': {'$fmt': {'$val': '${a}/workspace', 'a': str(self.base)}}}})
        out = self.cli('set', 'ws', self.base / 'workspace')
        self.assertIn('原本是指示詞', out)
        self.assertEqual(self.raw()['mounts']['ws'], str(self.base / 'workspace'))

    def test_rm_cwd_net(self):
        (self.root / 'B').mkdir()
        self.cli('set', 'ws', self.base / 'workspace', '--cwd')
        self.cli('set', 'b', self.root / 'B')
        self.assertIn('先 aos-agent access cwd', self.cli('rm', 'ws', code=1))
        self.cli('cwd', 'b')
        self.cli('rm', 'ws')
        self.assertEqual(list(self.raw()['mounts']), ['b'])
        self.cli('rm', 'ws', code=1)
        self.cli('cwd', 'zz', code=1)
        self.cli('net', 'on')
        self.assertIs(self.raw()['net'], True)
        self.cli('net', 'off')
        self.assertIs(self.raw()['net'], False)

    def test_missing_mount_can_still_be_removed(self):
        (self.root / 'B').mkdir()
        self.cli('set', 'ws', self.base / 'workspace', '--cwd')
        self.cli('set', 'b', self.root / 'B')
        (self.root / 'B').rmdir()
        out = self.cli('ls', code=1)
        self.assertIn('不在', out)
        self.assertIn('壞了：AccessInvalid', out)
        self.cli('rm', 'b')
        self.assertEqual(self.cli('ls').count('壞了'), 0)

    def test_usage_errors(self):
        for args in (['set', 'ws'], ['net', 'maybe'], ['rm'], ['ls', 'x'], ['rm', 'ws', '--ro'],
                     ['set', 'WS', '/tmp'], ['set', 'ws', '/tmp', '--ro', '--rw'], ['net', 'on', '--json']):
            with self.subTest(args=args):
                self.assertIn('Usage', self.cli(*args, code=2))


class CheckBase(Home):
    def check(self, env=None):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            aos_agent_check.access_checks(__import__('aos_kernel_check').Checks(), str(self.base),
                                          env or self.env)
        return out.getvalue()


class CheckStatusTests(CheckBase):
    def test_warn_without_access_when_tools(self):
        self.assertEqual(self.check(), '')
        self.put(self.base / 'tools/t.json', [{'type': 'function', 'function': {'name': 'sh'}, '_meta': {'argv': ['sh']}}])
        self.put(self.base / 'info.json', dict(self.info, tools=['tools/t.json']))
        self.assertIn('warn access: 沒有 access.json', self.check())

    def test_bad_access_and_no_bwrap(self):
        self.access({'mounts': {'ws': 'nope'}})
        with patch.object(aos_agent_check.shutil, 'which', return_value=None):
            out = self.check()
        self.assertIn('bad  access: AccessInvalid', out)
        self.assertIn('bad  access/bwrap: NoBwrap', out)
        self.assertIn('ok   access/aos-jail: 送件用 ' + acc.JAIL, out)

    @unittest.skipUnless(HAS_BWRAP, '這台沒有 bwrap')
    def test_good_access_bwrap_probe_and_tool_warns(self):
        self.put(self.base / 'tools/t.json', [
            {'type': 'function', 'function': {'name': 'loose'}, '_meta': {'argv': ['sh']}, '_jail': False},
            {'type': 'function', 'function': {'name': 'far'}, '_meta': {'argv': ['aos-nowhere-xyz']}},
            {'type': 'function', 'function': {'name': 'near'}, '_meta': {'argv': ['sh']}}])
        self.put(self.base / 'info.json', dict(self.info, tools=['tools/t.json']))
        self.access({'mounts': {'ws': 'workspace'}, 'cwd': 'ws'})
        out = self.check()
        self.assertIn('ok   access: ', out)
        self.assertIn('ok   access/bwrap', out)
        self.assertIn('warn agent/tool/loose: _jail: false', out)
        self.assertIn('warn agent/tool/far: aos-nowhere-xyz 不在 /usr 下', out)
        self.assertNotIn('agent/tool/near', out)

    def test_status_names_broken_access(self):
        self.access({'mounts': {'ws': 'nope'}})
        data = aos_agent_status.collect(self.base, self.env)
        self.assertIn('mounts.ws', data['access_error'])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            aos_agent_status.show(data)
        self.assertIn('access bad：AccessInvalid', out.getvalue())
        self.access({'mounts': {'ws': 'workspace'}})
        self.assertIsNone(aos_agent_status.collect(self.base, self.env)['access_error'])


class ReviewFixTests(Home):
    """astra 審查必修：aos 自己的程式、符號連結本身、環境變數、access 指令驗候選、明寫不在、state 形狀。"""

    def setUp(self):
        super().setUp()
        self.err = io.StringIO()
        self.addCleanup(patch.stopall)
        patch('sys.stderr', self.err).start()

    def test_aos_programs_are_trusted(self):
        self.access({'mounts': {'repo': acc.CLI_DIR}})
        self.assertIn('aos 的指令', self.error('AccessUnsafe'))
        self.access({'mounts': {'lib': acc.LIB_DIR}})
        self.assertIn('aos 的程式庫', self.error('AccessUnsafe'))
        self.access({'mounts': {'lib': {'$opt': 'ro', '$val': acc.LIB_DIR}}})
        self.assertTrue(self.load()['mounts']['lib']['ro'])

    def test_path_chain_keeps_links(self):
        (self.root / 'real').mkdir()
        (self.root / 'real' / 'f').write_text('x')
        (self.root / 'l1').symlink_to('real')
        (self.root / 'l2').symlink_to(self.root / 'l1')
        self.assertEqual(acc.path_chain(self.root / 'l2' / 'f'),
                         [str(self.root / 'l2'), str(self.root / 'l1'), str(self.root / 'real' / 'f')])

    def test_symlinked_tool_file_in_writable_folder(self):
        self.put(self.root / 'outside' / 'tool.json', [{'type': 'function', 'function': {'name': 'sh'},
                                                         '_meta': {'argv': ['sh']}}])
        (self.base / 'workspace' / 'tool.json').symlink_to(self.root / 'outside' / 'tool.json')
        self.put(self.base / 'info.json', dict(self.info, tools=['workspace/tool.json']))
        self.access({'mounts': {'ws': 'workspace'}})
        text = self.error('AccessUnsafe')
        self.assertIn(str(self.base / 'workspace' / 'tool.json'), text)

    def test_access_lookup_states(self):
        self.assertEqual(acc.access_lookup(self.base), (self.base / 'access.json', 'absent'))
        self.access({})
        self.assertEqual(acc.access_lookup(self.base)[1], 'present')
        self.put(self.base / 'info.json', dict(self.info, access='gone.json'))
        self.assertEqual(acc.access_lookup(self.base), (self.base / 'gone.json', 'missing'))

    def test_state_access_shape_errors_are_field_type(self):
        base = {'kind': 'act', 'kernel': '/K', 'base_len': 1, 'sent': True, 'calls': []}
        for value, where in (({'mounts': {'ws': {'path': '/w', 'ro': False}}, 'cwd': [], 'net': False}, 'batch.access.cwd'),
                             ({'mounts': {'ws': {'path': '/w', 'ro': False}}, 'cwd': {}, 'net': False}, 'batch.access.cwd'),
                             ({'mounts': {'WS': {'path': '/w', 'ro': False}}, 'cwd': None, 'net': False},
                              'batch.access.mounts.WS')):
            with self.subTest(value=value), self.assertRaises(AgentError) as cm:
                info_api.check_batch(dict(base, access=value))
            self.assertEqual(cm.exception.code, 'FieldTypeMismatch')
            self.assertIn(where, str(cm.exception))


class EnvTests(SendBase):
    """jailed 工具的 _meta.envs：敏感來源整件不跑、敏感名字在寫 inst 前就丟，inst 落盤不帶值。"""

    def jailed(self, meta, env_extra):
        self.tool(meta)
        self.access({'mounts': {'ws': 'workspace'}})
        self.env.update(env_extra)
        with patch.object(batch_api.shutil, 'which', return_value='/usr/bin/bwrap'):
            return self.tick()

    def on_disk(self):
        return ''.join(p.read_text(errors='replace') for p in (self.base / 'work').glob('*')
                       ) if (self.base / 'work').exists() else ''

    def test_renamed_secret_env_is_refused(self):
        base_env = dict(self.env)
        for key in ('OPENAI_API_KEY', 'AOS_KERNEL_HOME', 'AOS_LLM_CONFIG', 'SSH_AUTH_SOCK', 'db_password'):
            with self.subTest(key=key):
                shutil.rmtree(self.base / 'work', ignore_errors=True)
                self.env = dict(base_env)
                value = str(self.k) if key == 'AOS_KERNEL_HOME' else 'sk-secret-value'
                batch = self.jailed({'argv': ['tools/bin/sh-tool'], 'envs': {'FOO': {'$env': key}}},
                                    {key: value})
                call = batch['calls'][0]
                self.assertIn('跑不起來：EnvUnsafe: ', call['done']['content'])
                self.assertIn(key, call['done']['content'])
                self.assertNotIn(value, self.on_disk())
                self.assertFalse(list((self.k / 'requests').iterdir()))

    def test_secret_env_in_argv_or_fmt_is_refused(self):
        batch = self.jailed({'argv': ['tools/bin/sh-tool', {'$fmt': {'$val': 'k=${k}', 'k': {'$env': 'MY_TOKEN'}}}]},
                            {'MY_TOKEN': 'tok-value'})
        self.assertIn('EnvUnsafe', batch['calls'][0]['done']['content'])
        self.assertNotIn('tok-value', self.on_disk())

    def test_sensitive_names_dropped_before_inst(self):
        batch = self.jailed({'argv': ['tools/bin/sh-tool'],
                             'envs': {'GITHUB_TOKEN': 'literal-tok', 'OK_VAR': {'$env': 'PLAIN'}}},
                            {'PLAIN': 'plain-value'})
        argv = self.inst(batch)['argv']
        self.assertIn('--setenv', argv)
        self.assertIn('OK_VAR=plain-value', argv)
        self.assertNotIn('literal-tok', self.on_disk())

    def test_unjailed_tool_keeps_env(self):
        self.tool({'argv': ['tools/bin/sh-tool'], 'envs': {'FOO': {'$env': 'OPENAI_API_KEY'}}}, _jail=False)
        self.access({'mounts': {'ws': 'workspace'}})
        self.env['OPENAI_API_KEY'] = 'sk-x'
        batch = self.tick()
        self.assertEqual(self.inst(batch)['envs'], {'FOO': 'sk-x'})


class CliReviewTests(CliBase):
    def test_set_uses_refs_of_access_file(self):
        shared = self.root / 'shared'
        self.put(shared / 'path.json', {'ws': str(self.base / 'workspace')})
        self.access({'mounts': {'ws': {'$ref': '../shared/path.json#/ws'}}, 'cwd': 'ws'})
        before = self.raw()
        self.assertIn('AccessUnsafe', self.cli('set', 'ref', shared, '--rw', code=1))
        self.assertEqual(self.raw(), before)
        self.assertIn('所以設成唯讀', self.cli('set', 'ref', shared))
        self.assertEqual(self.raw()['mounts']['ref'], {'$opt': 'ro', '$val': str(shared)})

    def test_rm_compares_resolved_cwd(self):
        (self.root / 'B').mkdir()
        self.access({'mounts': {'ws': 'workspace', 'b': str(self.root / 'B')}, 'cwd': {'$env': 'START'}})
        with patch.dict(os.environ, {'START': 'ws'}):
            before = self.raw()
            self.assertIn('目前的起點', self.cli('rm', 'ws', code=1))
            self.assertEqual(self.raw(), before)
            self.cli('rm', 'b')
            self.assertEqual(list(self.raw()['mounts']), ['ws'])

    def test_candidate_revalidated_before_write(self):
        (self.root / 'B').mkdir()
        # cwd 用 $ref 指到 mounts 裡的另一格名字：rm 那格後候選壞掉（cwd 不在 mounts）＝不寫
        self.put(self.base / 'start.json', {'n': 'b'})
        self.access({'mounts': {'ws': 'workspace', 'b': str(self.root / 'B')},
                     'cwd': {'$ref': 'start.json#/n'}})
        before = self.raw()
        self.cli('rm', 'b', code=1)
        self.assertEqual(self.raw(), before)

    def test_ls_explicit_missing_is_error(self):
        self.put(self.base / 'info.json', dict(self.info, access='gone.json'))
        out = self.cli('ls', code=1)
        self.assertIn('AccessInvalid', out)
        self.assertNotIn('工具不關牢', out)
        self.assertIn('檔不在', json.loads(self.cli('ls', '--json', code=1))['error'])
        self.cli('net', 'on', code=1)
        self.cli('set', 'ws', self.base / 'workspace', '--cwd')
        self.assertTrue((self.base / 'gone.json').exists())


class OptToolTests(CheckBase):
    def test_program_folder_covering_home_warns(self):
        self.put(self.base / 'mytool', '#!/bin/sh\n')
        os.chmod(self.base / 'mytool', 0o755)
        self.put(self.base / 'tools/t.json', [{'type': 'function', 'function': {'name': 'mine'},
                                               '_meta': {'argv': ['./mytool']}}])
        self.put(self.base / 'info.json', dict(self.info, tools=['tools/t.json']))
        self.access({'mounts': {'ws': 'workspace'}, 'cwd': 'ws'})
        with patch.object(aos_agent_check, 'bwrap_probe', return_value=(True, 'ok')):
            out = self.check()
        self.assertIn('warn agent/tool/mine: 程式資料夾 %s 會整個唯讀掛到 /opt/tool' % self.base, out)


if __name__ == '__main__':
    unittest.main()
