"""B 隊補測試（09-24 access-impl 任務書第 5 項）：只補 test_agent_access.py／test_jail.py／test_agent_tools_manage.py
還沒測到的角落，不重複那三份已經涵蓋的案例。

沿用 test_agent_access 的假 K 家（Home）與常數；bwrap 真的跑只在 JailEnvLeakTests（沒 bwrap 就 skip，且很快）。
"""
import contextlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import aos_agent as agent
import aos_agent_batch as batch_api
import aos_agent_check
import aos_agent_cli
import aos_kernel_check
import test_agent_access as fixture
from aos_agent_home import AgentError

JAIL_CLI = Path(__file__).resolve().parents[2] / 'cli' / 'aos-jail'


class TwoCallBatchTests(fixture.Home):
    """走 aos-agent 送件路徑：一批兩件工具，快照只解一次、兩件共用同一份（任務書第 3 項）。"""

    def setUp(self):
        super().setUp()
        self.err = io.StringIO()
        self.addCleanup(patch.stopall)
        patch('sys.stderr', self.err).start()
        self.put(self.base / 'tools/bin/sh-tool', '#!/bin/sh\n')
        self.put(self.base / 'tools/t.json',
                 [{'type': 'function', 'function': {'name': 'sh1'}, '_meta': {'argv': ['tools/bin/sh-tool', '-a']}},
                  {'type': 'function', 'function': {'name': 'sh2'}, '_meta': {'argv': ['tools/bin/sh-tool', '-b']}}])
        self.put(self.base / 'info.json', dict(self.info, tools=['tools/t.json']))
        self.put(self.base / 'prompts/history.json', [{
            'role': 'assistant', 'content': None,
            'tool_calls': [{'id': 'c1', 'type': 'function', 'function': {'name': 'sh1', 'arguments': '{}'}},
                           {'id': 'c2', 'type': 'function', 'function': {'name': 'sh2', 'arguments': '{}'}}]}])
        self.put(self.base / 'state.json', {'state': 'act'})

    def tick(self, **which):
        self.assertEqual(agent.tick(self.base, self.env), 0, self.err.getvalue())
        return self.read(self.base / 'state.json')['batch']

    def test_second_call_in_batch_unaffected_by_mid_batch_edit(self):
        """同批第二件用同一份快照：處理第一件跟第二件之間把 access.json 改掉，第二件的 inst 仍照原表包。"""
        self.access({'mounts': {'ws': 'workspace'}, 'cwd': 'ws'})
        (self.root / 'B').mkdir()
        seen = []

        def hook(step):
            if step == 'work.inst':
                seen.append(1)
                if len(seen) == 1:
                    self.access({'mounts': {'ws': '../B'}, 'cwd': 'ws'})

        with patch.object(agent, '_hook', side_effect=hook), \
                patch.object(batch_api.shutil, 'which', return_value='/usr/bin/bwrap'):
            batch = self.tick()
        self.assertEqual(len(seen), 2)
        ws = str(self.base / 'workspace')
        for call in batch['calls']:
            inst = self.read(self.base / 'work' / (call['name'] + '.inst.json'))
            self.assertIn('ws=%s' % ws, inst['argv'])
            self.assertNotIn('ws=%s' % (self.root / 'B'), inst['argv'])

    def test_bad_table_marks_every_call_in_the_batch(self):
        """壞表那批：每一件都「跑不起來」、訊息各自講哪裡壞，一件都不送給 kernel。"""
        self.access({'mounts': {'ws': 'nope'}})
        batch = self.tick()
        self.assertEqual(len(batch['calls']), 2)
        for call, name in zip(batch['calls'], ('sh1', 'sh2')):
            self.assertTrue(call['acked'])
            # 給模型的話：講被擋、叫它轉告使用者；細節（mounts.ws）留給 check／status
            self.assertTrue(call['done']['content'].startswith('工具 %s 沒有執行：' % name))
            self.assertIn('（AccessInvalid）', call['done']['content'])
            self.assertIn('請告訴使用者', call['done']['content'])
        self.assertFalse(list((self.k / 'requests').iterdir()))


class NextBatchSnapshotTests(fixture.Home):
    """下一批才生效：批 1 跑完（settle）、access.json 換過之後，批 2 用的是新表（任務書第 3 項）。"""

    def setUp(self):
        super().setUp()
        self.err = io.StringIO()
        self.addCleanup(patch.stopall)
        patch('sys.stderr', self.err).start()
        self.put(self.base / 'tools/bin/sh-tool', '#!/bin/sh\n')
        self.put(self.base / 'tools/t.json', [{'type': 'function', 'function': {'name': 'sh'},
                                                '_meta': {'argv': ['tools/bin/sh-tool']}}])
        self.put(self.base / 'info.json', dict(self.info, tools=['tools/t.json']))
        self.put(self.base / 'prompts/history.json', [{
            'role': 'assistant', 'content': None,
            'tool_calls': [{'id': 'c1', 'type': 'function', 'function': {'name': 'sh', 'arguments': '{}'}}]}])

    def respond(self, name, text='ok'):
        self.put(self.base / 'work' / (name + '.out'), text)
        self.put(self.k / 'responses' / (name + '.json'),
                 {'jsonrpc': '2.0', 'id': name,
                  'result': {'kind': 'child', 'code': 0, 'timed_out': False, 'stopped': False, 'ms': 1}})
        (self.k / 'requests' / (name + '.json')).unlink(missing_ok=True)

    def test_next_batch_rereads_access(self):
        self.access({'mounts': {'ws': 'workspace'}, 'cwd': 'ws'})
        self.put(self.base / 'state.json', {'state': 'act'})
        with patch.object(batch_api.shutil, 'which', return_value='/usr/bin/bwrap'):
            self.assertEqual(agent.tick(self.base, self.env), 0, self.err.getvalue())
        state = self.read(self.base / 'state.json')
        name = state['batch']['calls'][0]['name']
        old_inst = self.read(self.base / 'work' / (name + '.inst.json'))
        self.assertIn('ws=%s' % (self.base / 'workspace'), old_inst['argv'])

        # 批 1 真的跑完（收回音、settle）：state 回 think、batch 清空。
        self.respond(name)
        self.assertEqual(agent.tick(self.base, self.env), 0, self.err.getvalue())
        state = self.read(self.base / 'state.json')
        self.assertIsNone(state['batch'])
        self.assertEqual(state['state'], 'think')

        # 接到下一輪 act（不模擬真的 think 呼叫，只補一句新 assistant，跟 aos-llm 沒關係）＋換 access。
        history = self.read(self.base / 'prompts/history.json')
        history.append({'role': 'assistant', 'content': None,
                         'tool_calls': [{'id': 'c2', 'type': 'function', 'function': {'name': 'sh', 'arguments': '{}'}}]})
        self.put(self.base / 'prompts/history.json', history)
        state['state'] = 'act'
        self.put(self.base / 'state.json', state)
        (self.root / 'B').mkdir()
        self.access({'mounts': {'ws': '../B'}})
        with patch.object(batch_api.shutil, 'which', return_value='/usr/bin/bwrap'):
            self.assertEqual(agent.tick(self.base, self.env), 0, self.err.getvalue())
        state2 = self.read(self.base / 'state.json')
        name2 = state2['batch']['calls'][0]['name']
        self.assertNotEqual(name, name2)
        new_inst = self.read(self.base / 'work' / (name2 + '.inst.json'))
        self.assertIn('ws=%s' % (self.root / 'B'), new_inst['argv'])
        self.assertNotIn('ws=%s' % (self.base / 'workspace'), new_inst['argv'])


class AccessCliEdgeTests(fixture.Home):
    """access CLI 沒被 test_agent_access.py 蓋到的兩個角落：JSON 壞掉時 rm／cwd／net 也要拒絕且不動檔；
    AccessUnsafe（重疊）的既有檔仍然可以用指令修（spec/aos-agent/access.md §3、aos_agent_access_cli.py 開頭註解）。
    """

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

    def test_json_syntax_broken_file_blocks_rm_cwd_net_and_keeps_it_byte_identical(self):
        self.access({'mounts': {'ws': 'workspace'}, 'cwd': 'ws'})
        self.put(self.base / 'access.json', '{\n  "mounts": {"ws": "workspace",}\n}')
        broken = (self.base / 'access.json').read_bytes()
        for args in (('rm', 'ws'), ('cwd', 'ws'), ('net', 'on')):
            with self.subTest(args=args):
                out = self.cli(*args, code=1)
                self.assertIn('JsonSyntax', out)
                self.assertEqual((self.base / 'access.json').read_bytes(), broken)

    def test_unsafe_existing_file_still_fixable_via_rm(self):
        # CLI 本身不會寫出這種表（set 遇到重疊會自動 ro 或拒絕）；這裡直接造一份手寫的重疊表，
        # 確認 rm 修得了它（AccessUnsafe 不算「解不開」，不擋寫入）。
        self.access({'mounts': {'self': '.', 'ws': 'workspace'}, 'cwd': 'ws'})
        with self.assertRaises(AgentError) as cm:
            self.load()
        self.assertEqual(cm.exception.code, 'AccessUnsafe')
        out = self.cli('rm', 'self')                    # 重疊不算「解不開」，指令改得動、改完就乾淨了
        self.assertNotIn('壞了', out)
        self.assertEqual(list(self.raw()['mounts']), ['ws'])
        self.assertEqual(self.load()['mounts'], {'ws': {'path': str(self.base / 'workspace'), 'ro': False}})


class CheckFieldPositionTests(fixture.Home):
    """aos-agent check：壞 access 檔的 bad 訊息要指得到哪一格（不是只講代號）。"""

    def test_bad_access_message_names_the_field(self):
        self.access({'mounts': {'ws': 'nope'}})
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            aos_agent_check.access_checks(aos_kernel_check.Checks(), str(self.base), self.env)
        text = out.getvalue()
        self.assertIn('bad  access: AccessInvalid', text)
        self.assertIn('mounts.ws', text)
        self.assertIn(str(self.base / 'access.json'), text)


@unittest.skipUnless(fixture.HAS_BWRAP, '這台沒有 bwrap')
class JailEnvLeakTests(unittest.TestCase):
    """牢裡看不到 AOS_LLM_CONFIG（外層環境刻意設了；AOS_KERNEL_HOME／OPENAI_API_KEY 已在 test_jail.py 測過）。"""

    def test_aos_llm_config_not_visible(self):
        d = Path(os.path.realpath(tempfile.mkdtemp(prefix='aos-jail-llmcfg-')))
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        (d / 'ws').mkdir()
        env = dict(os.environ, AOS_LLM_CONFIG='/secret/llm.json')
        r = subprocess.run([sys.executable, str(JAIL_CLI), '--mount', 'ws=%s' % (d / 'ws'), '--chdir', 'ws',
                            '--', 'sh', '-c', 'env'], env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn('AOS_LLM_CONFIG', r.stdout)
        self.assertNotIn('/secret/llm.json', r.stdout)


if __name__ == '__main__':
    unittest.main()
