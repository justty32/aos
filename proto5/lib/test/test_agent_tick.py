"""假 K 家測試：直接呼叫函式，start／stop 只以 thread 模擬回音。"""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import aos_agent as agent
import aos_agent_batch as batch_api
import aos_agent_info as info_api
import aos_home
import aos_inst
from aos_agent_results import UNKNOWN

MESSAGE = {'role': 'assistant', 'content': '完成'}
TOOL_CALL = {'id': 'c1', 'type': 'function', 'function': {'name': 'sh', 'arguments': '{不驗 JSON}\n'}}
ASSISTANT = {'role': 'assistant', 'content': None, 'tool_calls': [TOOL_CALL]}
TOOL = {'type': 'function', 'function': {'name': 'sh'}, '_meta': {'argv': ['sh']}}
RESULT = {'kind': 'child', 'code': 0, 'timed_out': False, 'stopped': False, 'ms': 1}


class Crash(RuntimeError):
    pass


class AgentTickTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.base, self.k = self.root / 'bob', self.root / 'K'
        self.base.mkdir()
        (self.k / 'requests').mkdir(parents=True)
        (self.k / 'responses').mkdir()
        self.env = {'AOS_KERNEL_HOME': str(self.k)}
        self.info = {'_metainfo': {'_type': 'llm_agent', '_version': 1}, 'llm': {'model': 'small'}}
        self.put(self.base / 'info.json', self.info)
        self.put(self.k / 'info.json', {})
        self.put(self.k / 'state.json', {'procs': {}, 'replies': []})
        self.err = io.StringIO()
        self.addCleanup(patch.stopall)
        patch('sys.stderr', self.err).start()

    def put(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')

    def read(self, path):
        return json.loads(path.read_text(encoding='utf-8'))

    def state(self):
        return self.read(self.base / 'state.json')

    def tick(self):
        return agent.tick(self.base, self.env)

    def prepare(self, kind='think', sent=True, done=None, acked=False, errors=0):
        name = 'aw-bob-123-77-0'
        call = {'name': name, 'done': done, 'acked': acked}
        if kind == 'act':
            self.put(self.base / 'prompts/history.json', [ASSISTANT])
            self.info['tools'] = ['tools.json']
            self.put(self.base / 'tools.json', [TOOL])
            self.put(self.base / 'info.json', self.info)
            call.update(tool='sh', tool_call_id='c1')
        batch = {'kind': kind, 'kernel': str(self.k), 'base_len': int(kind == 'act'),
                 'sent': sent, 'calls': [call]}
        self.put(self.base / 'state.json', {'state': kind, 'batch': batch, 'errors': errors})
        return name

    def respond(self, name, result=None, error=None):
        body = {'jsonrpc': '2.0', 'id': name}
        body['error' if error else 'result'] = error or (RESULT if result is None else result)
        self.put(self.k / 'responses' / (name + '.json'), body)
        (self.k / 'requests' / (name + '.json')).unlink(missing_ok=True)

    def output(self, name, value=MESSAGE):
        self.put(self.base / 'work' / (name + '.out'), value)

    def crash_at(self, step):
        def hook(actual):
            if actual == step:
                raise Crash(step)
        return patch.object(agent, '_hook', hook)

    def test_idle_empty(self):
        self.assertEqual(self.tick(), 101)
        self.assertFalse((self.base / 'state.json').exists())

    def test_idle_input(self):
        self.put(self.base / 'input.json', '你好')
        self.assertEqual(self.tick(), 0)
        self.assertEqual(self.state()['state'], 'think')
        self.assertEqual(self.read(self.base / 'prompts/history.json'), [{'role': 'user', 'content': '你好'}])
        self.assertEqual(len(list((self.base / 'done').glob('input.json.*.done'))), 1)

    def test_think_build_and_inst(self):
        self.put(self.base / 'state.json', {'state': 'think'})
        self.assertEqual(self.tick(), 0)
        batch = self.state()['batch']
        name = batch['calls'][0]['name']
        self.assertRegex(name, r'^aw-bob-\d+-\d+-0$')
        self.assertTrue(batch['sent'])
        req = self.read(self.k / 'requests' / (name + '.json'))
        self.assertEqual(req['id'], name)
        self.assertEqual(req['params'], {'name': name, 'target': str(self.base / 'work' / (name + '.inst.json')),
                                         'once': True, 'pool': 'llm', 'timeout_ms': 125000})
        inst = self.read(self.base / 'work' / (name + '.inst.json'))
        self.assertEqual(inst, batch_api.think_inst(self.base, name))
        aos_inst.load_obj(inst, str(self.base))

    def test_act_valid_build(self):
        self.prepare('act')
        self.put(self.base / 'state.json', {'state': 'act'})
        self.assertEqual(self.tick(), 0)
        self.assertEqual(self.state()['batch']['calls'][0]['tool_call_id'], 'c1')

    def test_act_missing_tool_local_done(self):
        self.put(self.base / 'prompts/history.json', [ASSISTANT])
        self.put(self.base / 'state.json', {'state': 'act'})
        self.assertEqual(self.tick(), 0)
        call = self.state()['batch']['calls'][0]
        self.assertEqual(call, {'name': None, 'tool_call_id': 'c1', 'tool': 'sh',
                                'done': {'content': '沒有這個工具：sh'}, 'acked': True})
        self.assertFalse(list((self.k / 'requests').iterdir()))
        self.assertEqual(self.tick(), 0)
        self.assertEqual(self.state()['state'], 'think')

    def test_act_empty(self):
        self.put(self.base / 'state.json', {'state': 'act'})
        self.assertEqual(self.tick(), 0)
        self.assertEqual(self.state()['state'], 'think')
        self.assertIsNone(self.state()['batch'])

    def test_gate_closed_blocks_batch(self):
        name = self.prepare()
        st = self.state(); st['waits'] = ['go.json']; self.put(self.base / 'state.json', st)
        self.respond(name); self.output(name)
        self.assertEqual(self.tick(), 101)
        self.assertIsNone(self.state()['batch']['calls'][0]['done'])

    def test_gate_partial_persists(self):
        self.put(self.base / 'state.json', {'waits': ['a.json', 'b.json']})
        self.put(self.base / 'a.json', {})
        self.assertEqual(self.tick(), 101)
        self.assertEqual(self.state()['waits'], ['b.json'])
        self.assertTrue((self.base / 'a.json').exists())

    def test_gate_consume_file(self):
        self.put(self.base / 'state.json', {'waits': {'$opt': 'consume', '$val': 'go.json'}})
        self.put(self.base / 'go.json', {})
        self.assertEqual(self.tick(), 101)
        self.assertEqual(self.state()['waits'], [])
        self.assertEqual(self.state()['consuming'], [])
        self.assertRegex(next((self.base / 'done').glob('go.json.*.done')).name, r'go.json.\d+-\d+.done')

    def test_gate_consume_directory(self):
        self.put(self.base / 'state.json', {'waits': {'$opt': 'consume', '$val': 'signals'}})
        for name in ('b.json', 'a.json', 'keep.done'):
            self.put(self.base / 'signals' / name, {})
        self.assertEqual(self.tick(), 101)
        self.assertEqual(len(list((self.base / 'signals/done').glob('*.done'))), 2)
        self.assertFalse(list((self.base / 'signals').glob('*.json')))

    def test_gate_array_requires_all(self):
        self.put(self.base / 'state.json', {'waits': {'$opt': 'all', '$val': ['a', 'b']}})
        self.put(self.base / 'a', {})
        self.assertEqual(self.tick(), 101)
        self.assertFalse(list(self.base.glob('a.*.done')))

    def test_consuming_existing_dst_keeps_new_src(self):
        src, dst = self.base / 'go', self.base / 'go.id.done'
        self.put(src, '新'); self.put(dst, '舊')
        self.put(self.base / 'state.json', {'consuming': [{'src': str(src), 'dst': str(dst)}]})
        self.assertEqual(self.tick(), 101)
        self.assertEqual(self.read(src), '新')
        self.assertEqual(self.read(dst), '舊')
        self.assertEqual(self.state()['consuming'], [])

    def test_gate_records_before_move(self):
        self.put(self.base / 'go', {})
        self.put(self.base / 'state.json', {'waits': {'$opt': 'consume', '$val': 'go'}})
        with self.crash_at('state.gate'), self.assertRaises(Crash):
            self.tick()
        self.assertEqual(self.state()['waits'], [])
        self.assertTrue(self.state()['consuming'])
        self.assertTrue((self.base / 'go').exists())
        self.assertEqual(self.tick(), 101)
        self.assertFalse((self.base / 'go').exists())

    def test_sent_false_recovery(self):
        name = self.prepare(sent=False)
        self.assertEqual(self.tick(), 0)
        self.assertTrue((self.k / 'requests' / (name + '.json')).exists())
        self.assertTrue(self.state()['batch']['sent'])

    def test_post_eexist_success(self):
        self.prepare(sent=False)
        with patch('aos_client.submit', side_effect=aos_home.RequestExists('x')):
            self.assertEqual(self.tick(), 0)
        self.assertTrue(self.state()['batch']['sent'])

    def test_batch_kernel_fixed(self):
        name = self.prepare(sent=False)
        self.env['AOS_KERNEL_HOME'] = str(self.root / 'other')
        self.assertEqual(self.tick(), 0)
        self.assertTrue((self.k / 'requests' / (name + '.json')).exists())
        self.assertFalse((self.root / 'other').exists())

    def test_meta_failure_done(self):
        self.prepare('act', sent=False)
        bad = copy.deepcopy(TOOL); bad['_meta'] = {'argv': [{'$env': 'MISSING'}]}
        bad['_jail'] = False            # 測的是 _meta 解不開；沒 access.json 時要關牢的會先被 NoAccess 擋
        self.put(self.base / 'tools.json', [bad])
        self.assertEqual(self.tick(), 0)
        call = self.state()['batch']['calls'][0]
        self.assertIn('EnvironmentVariableMissing', call['done']['content'])
        self.assertTrue(call['acked'])
        self.assertFalse(list((self.k / 'requests').iterdir()))

    def test_tool_inst_all_fields(self):
        name = self.prepare('act', sent=False)
        tool = copy.deepcopy(TOOL)
        tool['_meta'].update(cwd={'$opt': 'mkdir', '$val': 'sub'}, envs={'$opt': 'clear', '$val': {}},
                             stderr={'$opt': ['append', 'mkdir'], '$val': 'err'},
                             exit={'$opt': ['append', 'mkdir'], '$val': 'exit'})
        tool['_jail'] = False           # 測的是不包牢時 inst 的每一格（包牢的在 test_agent_access）
        self.put(self.base / 'tools.json', [tool])
        self.assertEqual(self.tick(), 0)
        raw = self.read(self.base / 'work' / (name + '.inst.json'))
        self.assertEqual(raw['cwd'], {'$opt': 'mkdir', '$val': str(self.base / 'sub')})
        self.assertEqual(raw['envs'], {'$opt': 'clear', '$val': {}})
        self.assertEqual(raw['stderr'], {'$opt': ['append', 'mkdir'], '$val': str(self.base / 'sub/err')})
        self.assertEqual(raw['exit'], {'$opt': ['append', 'mkdir'], '$val': str(self.base / 'sub/exit')})
        self.assertEqual(raw['argv'], ['sh'])
        self.assertEqual(raw['_metainfo'], {'_type': 'posix', '_version': 1})
        self.assertEqual(raw['stdin'], str(self.base / 'work' / (name + '.in')))
        self.assertEqual(raw['stdout'], {'$opt': 'mkdir', '$val': str(self.base / 'work' / (name + '.out'))})
        self.assertEqual((self.base / 'work' / (name + '.in')).read_text(), TOOL_CALL['function']['arguments'])
        decoded = aos_inst.load_obj(raw, str(self.base))
        self.assertTrue(decoded['envs_clear'])
        self.assertTrue(decoded['cwd_mkdir'])

    def test_tool_inst_merge_and_env(self):
        raw = batch_api.tool_inst({'argv': ['sh'], 'stderr': {'$opt': 'merge'},
                                   'envs': {'X': {'$env': 'VALUE'}}}, self.base, 'n', {'VALUE': 'v'})
        self.assertEqual(raw['stderr'], {'$opt': 'merge'})
        self.assertEqual(raw['envs'], {'X': 'v'})
        self.assertTrue(aos_inst.load_obj(raw, str(self.base))['stderr']['merge'])

    def test_tool_inst_inherit_and_empty_env_omitted(self):
        raw = batch_api.tool_inst({'argv': ['sh'], 'stderr': {'$opt': 'inherit'}}, self.base, 'n', {})
        self.assertEqual(raw['stderr'], {'$opt': 'inherit'})
        self.assertNotIn('envs', raw)
        self.assertNotIn('exit', raw)

    def test_collect_original_request_before_response(self):
        name = self.prepare()
        self.respond(name); self.output(name)
        self.put(self.k / 'requests' / (name + '.json'), {})
        self.assertEqual(self.tick(), 101)
        self.assertIsNone(self.state()['batch']['calls'][0]['done'])

    def test_collect_no_response(self):
        self.prepare()
        self.assertEqual(self.tick(), 101)

    def test_collect_bad_json_preserves_state(self):
        name = self.prepare()
        path = self.k / 'responses' / (name + '.json'); path.write_text('{')
        before = self.state()
        self.assertEqual(self.tick(), 1)
        self.assertEqual(self.state(), before)
        self.assertFalse(list((self.k / 'requests').glob('ack-*')))

    def test_done_ack_acked_order(self):
        name = self.prepare()
        self.respond(name); self.output(name)
        seen = []
        def hook(step):
            if step in ('state.done', 'ack.post', 'state.acked'):
                st = self.state()['batch']['calls'][0]
                acks = list((self.k / 'requests').glob('ack-*'))
                seen.append((step, st['done'], st['acked'], len(acks)))
        with patch.object(agent, '_hook', hook):
            self.assertEqual(self.tick(), 0)
        self.assertEqual(seen, [('state.done', {'ok': True}, False, 0),
                                ('ack.post', {'ok': True}, False, 1),
                                ('state.acked', {'ok': True}, True, 1)])
        ack = next((self.k / 'requests').glob('ack-*'))
        self.assertRegex(ack.name, r'^ack-\d+-\d+-0.json$')
        self.assertEqual(self.read(ack), {'jsonrpc': '2.0', 'method': 'ack', 'params': {'name': name + '.json'}})

    def test_pending_ack_before_resend(self):
        name = self.prepare(sent=False, done={'fail': '停', 'count': False})
        seen = []
        with patch.object(agent, '_hook', seen.append):
            self.assertEqual(self.tick(), 0)
        self.assertLess(seen.index('ack.post'), seen.index('state.sent'))
        self.assertTrue(self.state()['batch']['calls'][0]['acked'])
        self.assertEqual(self.read(next((self.k / 'requests').glob('ack-*')))['params']['name'], name + '.json')

    def test_ack_eexist_retries_new_ns(self):
        self.prepare(done={'fail': '停', 'count': False})
        original = aos_home.post_request
        seen = []
        def post(home, name, obj):
            seen.append(name)
            if len(seen) == 1:
                raise aos_home.RequestExists(name)
            return original(home, name, obj)
        with patch('aos_home.post_request', post):
            self.assertEqual(self.tick(), 0)
        self.assertEqual(len(seen), 2)
        self.assertNotEqual(*seen)

    def test_think_success_settles(self):
        name = self.prepare(errors=2)
        self.respond(name); self.output(name)
        self.assertEqual(self.tick(), 0)
        st = self.state()
        self.assertEqual((st['state'], st['errors'], st['batch']), ('idle', 0, None))
        self.assertEqual(st['sweep'], [{'kernel': str(self.k), 'name': name}])
        self.assertEqual(self.read(self.base / 'prompts/history.json'), [MESSAGE])

    def test_think_tools_enters_act(self):
        name = self.prepare(); self.respond(name); self.output(name, ASSISTANT)
        self.assertEqual(self.tick(), 0)
        self.assertEqual(self.state()['state'], 'act')

    def test_think_count_true(self):
        self.prepare(done={'fail': '錯', 'count': True}, acked=True, errors=1)
        self.assertEqual(self.tick(), 0)
        self.assertEqual(self.state()['errors'], 2)
        self.assertEqual(self.state()['state'], 'think')
        self.assertIn('aos-agent: engine: 錯', self.err.getvalue())
        self.assertFalse((self.base / 'prompts/history.json').exists())

    def test_think_count_false(self):
        self.prepare(done={'fail': '停', 'count': False}, acked=True, errors=2)
        self.assertEqual(self.tick(), 0)
        self.assertEqual(self.state()['errors'], 2)
        self.assertEqual(self.err.getvalue(), '')

    def test_act_settles_order(self):
        name = self.prepare('act', done={'content': '一'}, acked=True)
        st = self.state()
        c = copy.deepcopy(TOOL_CALL); c['id'] = 'c2'
        self.put(self.base / 'prompts/history.json', [dict(ASSISTANT, tool_calls=[TOOL_CALL, c])])
        st['batch']['calls'].append({'name': None, 'tool': 'sh', 'tool_call_id': 'c2',
                                    'done': {'content': '二'}, 'acked': True})
        self.put(self.base / 'state.json', st)
        self.assertEqual(self.tick(), 0)
        messages = self.read(self.base / 'prompts/history.json')
        self.assertEqual(messages[1:], [{'role': 'tool', 'tool_call_id': 'c1', 'content': '一'},
                                       {'role': 'tool', 'tool_call_id': 'c2', 'content': '二'}])
        self.assertEqual(self.state()['sweep'], [{'kernel': str(self.k), 'name': name}])

    def test_history_crash_redo_same(self):
        name = self.prepare(done={'ok': True}, acked=True); self.output(name)
        with self.crash_at('history.write'), self.assertRaises(Crash):
            self.tick()
        first = (self.base / 'prompts/history.json').read_bytes()
        self.assertIsNotNone(self.state()['batch'])
        self.assertEqual(self.tick(), 0)
        self.assertEqual((self.base / 'prompts/history.json').read_bytes(), first)

    def test_history_equal_length_prefix_edit_retained(self):
        name = self.prepare(done={'ok': True}, acked=True); self.output(name)
        st = self.state(); st['batch']['base_len'] = 1; self.put(self.base / 'state.json', st)
        prefix = {'role': 'user', 'content': '人改的'}
        self.put(self.base / 'prompts/history.json', [prefix])
        self.assertEqual(self.tick(), 0)
        self.assertEqual(self.read(self.base / 'prompts/history.json'), [prefix, MESSAGE])

    def test_intake_bad_retained(self):
        (self.base / 'input.json').write_text('{')
        self.assertEqual(self.tick(), 1)
        record = self.state()['intake']
        self.assertTrue(Path(record['files'][0]['dst']).exists())
        self.assertFalse((self.base / 'input.json').exists())
        self.assertEqual(self.tick(), 1)
        self.assertEqual(self.state()['intake'], record)

    def test_intake_empty_array(self):
        self.put(self.base / 'input.json', [])
        self.assertEqual(self.tick(), 101)
        self.assertIsNone(self.state()['intake'])

    def test_intake_missing_both_skips(self):
        self.put(self.base / 'state.json', {'intake': {'id': 'x', 'base_len': 0,
                 'files': [{'src': str(self.base / 'gone'), 'dst': str(self.base / 'gone.x.done')}]}})
        self.assertEqual(self.tick(), 101)
        self.assertIsNone(self.state()['intake'])

    def test_intake_new_same_name_preserved(self):
        self.put(self.base / 'input.json', '舊')
        with self.crash_at('consume.move'), self.assertRaises(Crash):
            self.tick()
        self.put(self.base / 'input.json', '新')
        self.assertEqual(self.tick(), 0)
        self.assertEqual(self.read(self.base / 'input.json'), '新')
        self.assertEqual(self.read(self.base / 'prompts/history.json'), [{'role': 'user', 'content': '舊'}])

    def test_intake_history_crash_redo(self):
        self.put(self.base / 'input.json', [dict(MESSAGE), {'role': 'user', 'content': '問'}])
        with self.crash_at('history.write'), self.assertRaises(Crash):
            self.tick()
        first = self.read(self.base / 'prompts/history.json')
        self.assertEqual(self.tick(), 0)
        self.assertEqual(self.read(self.base / 'prompts/history.json'), first)

    def test_intake_history_changed(self):
        self.put(self.base / 'input.json', '舊')
        with self.crash_at('state.intake'), self.assertRaises(Crash):
            self.tick()
        self.put(self.base / 'prompts/history.json', [MESSAGE, MESSAGE])
        self.assertEqual(self.tick(), 1)
        self.assertIn('HistoryChanged', self.err.getvalue())
        self.assertIsNotNone(self.state()['intake'])

    def test_intake_directory_order(self):
        self.put(self.base / 'state.json', {'input': 'in'})
        self.put(self.base / 'in/b.json', '二'); self.put(self.base / 'in/a.json', '一')
        self.put(self.base / 'in/ignore.done', '忽略')
        self.assertEqual(self.tick(), 0)
        self.assertEqual([m['content'] for m in self.read(self.base / 'prompts/history.json')], ['一', '二'])

    def test_three_failures_gate(self):
        self.prepare(done={'fail': '錯', 'count': True}, acked=True, errors=2)
        self.assertEqual(self.tick(), 0)
        self.assertEqual(self.state()['errors'], 0)
        self.assertEqual(self.state()['waits'], [{'$opt': 'consume', '$val': 'continue-aw-bob-123-77.json'}])
        self.assertIn('aos-agent: stuck: 問模型連敗 3 次，修好原因後 aos-agent continue --target %s\n' % self.base, self.err.getvalue())
        self.assertEqual(self.tick(), 101)

    def test_continue_name_each_batch_unique(self):
        signals = []
        for _ in range(2):
            self.put(self.base / 'state.json', {'state': 'think', 'errors': 2})
            self.assertEqual(self.tick(), 0)
            name = self.state()['batch']['calls'][0]['name']
            self.respond(name, result=dict(RESULT, code=1))
            self.assertEqual(self.tick(), 0)
            signals.append(self.state()['waits'][0]['$val'])
        self.assertNotEqual(*signals)

    def snapshot(self):
        # tick 鎖檔（aos-agent.md §2.1）是第 0 步唯一允許建的檔；家本身的 mtime 會因它變動。
        return {str(p.relative_to(self.base)): (None if p == self.base else p.stat().st_mtime_ns,
                                                p.read_bytes() if p.is_file() else None)
                for p in [self.base, *self.base.rglob('*')] if p.name != '.tick.lock'}

    def kernel_thread(self, error=None):
        seen, failures = [], []
        def kernel():
            try:
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    requests = list((self.k / 'requests').glob('aa-*.json'))
                    if requests:
                        path = requests[0]; request = self.read(path); seen.append(request)
                        body = {'jsonrpc': '2.0', 'id': request['id']}
                        body['error' if error else 'result'] = error or {'name': request['params']['name']}
                        aos_home.write_json(self.k / 'responses' / path.name, body)
                        path.unlink()
                        return
                    time.sleep(.001)
                raise AssertionError('未收到 request')
            except BaseException as exc:
                failures.append(exc)
        thread = threading.Thread(target=kernel)
        thread.start()
        self.addCleanup(thread.join, 3)
        return thread, seen, failures

    def register(self, starting=True, error=None):
        thread, seen, failures = self.kernel_thread(error)
        with patch.object(agent, 'WAIT_TIMEOUT_MS', 1500):
            result = (agent.start if starting else agent.stop)(self.base, self.env)
        thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertFalse(failures, failures)
        self.assertTrue(seen)
        self.assertRegex(seen[0]['id'], r'^aa-bob-\d+-\d+$')
        ack = self.read(next((self.k / 'requests').glob('ack-*')))
        self.assertEqual(ack['params']['name'], seen[0]['id'] + '.json')
        return result, seen[0]

    def test_start_tick_inst_and_request(self):
        self.info['tick'] = {'pool': 'agents', 'interval_ms': 42}; self.put(self.base / 'info.json', self.info)
        rc, request = self.register()
        self.assertEqual(rc, 0)
        self.assertEqual(request['method'], 'add')
        self.assertEqual(request['params'], {'name': 'agent-bob', 'target': str(self.base / 'tick.json'),
                                              'pool': 'agents', 'interval_ms': 42})
        self.assertEqual(self.read(self.base / 'tick.json'), {'_metainfo': {'_type': 'posix', '_version': 1},
                         'argv': ['aos-agent', 'tick', '--target', str(self.base)], 'cwd': str(self.base),
                         'envs': self.env, 'stderr': {'$opt': ['append', 'mkdir'],
                                                    '$val': str(self.base / 'log/agent.err')}})

    def test_start_default_omits_interval(self):
        rc, request = self.register()
        self.assertEqual(rc, 0)
        self.assertNotIn('interval_ms', request['params'])
        self.assertNotIn('timeout_ms', request['params'])
        self.assertNotIn('once', request['params'])

    def test_start_kernel_ref_only_two_fields(self):
        self.put(self.k / 'info.json', {'done_exit': {'$ref': '', '$at': '../values/done'},
                    'bad_after': {'$ref': '', '$at': '/values/bad'}, 'values': {'done': 0, 'bad': 0},
                    'cpus': {'$env': 'UNSET'}, 'daemon': {'$ref': 'missing'}})
        self.assertEqual(self.register()[0], 0)

    def test_start_tick_existing_same_untouched(self):
        value = {'envs': self.env, 'custom': '保留'}; self.put(self.base / 'tick.json', value)
        self.assertEqual(self.register()[0], 0)
        self.assertEqual(self.read(self.base / 'tick.json'), value)

    def test_stop_request(self):
        self.put(self.k / 'info.json', {'done_exit': 1})
        self.put(self.base / 'tick.json', {'envs': self.env})
        rc, request = self.register(False)
        self.assertEqual(rc, 0)
        self.assertEqual(request['method'], 'rm')
        self.assertEqual(request['params'], {'name': 'agent-bob'})

    def test_kernel_error_ack_and_one_line(self):
        rc, _ = self.register(error={'code': -32000, 'message': '已經\n登記', 'data': {'code': 'AlreadyExists'}})
        self.assertEqual(rc, 1)
        self.assertEqual(self.err.getvalue(), 'aos-agent: AlreadyExists: 已經 登記；帳本裡沒這筆（可能剛被 stop），等一下再 start\n')

    def test_main_argparse_error(self):
        with self.assertRaises(SystemExit) as exc:
            agent.main(['unknown'])
        self.assertEqual(exc.exception.code, 2)


    def test_tool_output_crlf_preserved(self):
        name = self.prepare('act'); self.respond(name)
        path = self.base / 'work' / (name + '.out'); path.parent.mkdir()
        path.write_bytes(b'a\r\nb\r\n')
        self.assertEqual(self.tick(), 0)
        self.assertEqual(self.read(self.base / 'prompts/history.json')[-1]['content'], 'a\r\nb\r\n')

    def test_tool_output_missing_is_empty(self):
        name = self.prepare('act'); self.respond(name)
        self.assertEqual(self.tick(), 0)
        self.assertEqual(self.read(self.base / 'prompts/history.json')[-1]['content'], '')

    def test_start_missing_kernel_info(self):
        (self.k / 'info.json').unlink()
        self.assertEqual(agent.start(self.base, self.env), 1)
        self.assertIn('NotAHome', self.err.getvalue())
        self.assertFalse(list((self.k / 'requests').iterdir()))

    def test_start_broken_tick_inst(self):
        (self.base / 'tick.json').write_text('{')
        self.assertEqual(agent.start(self.base, self.env), 1)
        self.assertIn('KernelMismatch', self.err.getvalue())

    def test_send_write_failure_keeps_unsent(self):
        self.prepare(sent=False)
        with patch('aos_client.submit', side_effect=aos_home.HomeError('WriteFailed', '磁碟滿')):
            self.assertEqual(self.tick(), 1)
        self.assertFalse(self.state()['batch']['sent'])
        self.assertEqual(self.err.getvalue(), 'aos-agent: io: 磁碟滿\n')

    def test_ack_crash_recovers(self):
        name = self.prepare(); self.respond(name); self.output(name)
        with self.crash_at('ack.post'), self.assertRaises(Crash):
            self.tick()
        self.assertEqual(self.state()['batch']['calls'][0]['done'], {'ok': True})
        self.assertFalse(self.state()['batch']['calls'][0]['acked'])
        self.assertEqual(self.tick(), 0)
        self.assertIsNone(self.state()['batch'])
        self.assertEqual(len(list((self.k / 'requests').glob('ack-*'))), 2)

    def test_batch_takes_precedence_over_idle(self):
        name = self.prepare(); self.respond(name); self.output(name)
        st = self.state(); st['state'] = 'idle'; self.put(self.base / 'state.json', st)
        self.put(self.base / 'input.json', '下次才收')
        self.assertEqual(self.tick(), 0)
        self.assertTrue((self.base / 'input.json').exists())
        self.assertEqual(self.read(self.base / 'prompts/history.json'), [MESSAGE])

    def test_tick_unknown_fields_not_resolved(self):
        self.info['tick'] = {'unused': {'$env': 'MISSING'}}
        self.put(self.base / 'info.json', self.info)
        self.assertEqual(self.tick(), 101)


def posting_case(where):
    def test(self):
        name = self.prepare(sent=False)
        kp = self.k / 'state.json'
        if where == 'requests':
            self.put(self.k / 'requests' / (name + '.json'), {'原單': True})
            kp.write_text('{')  # 第一步命中後，不得去讀壞帳本。
        elif where == 'procs':
            self.put(kp, {'procs': {name: {}}, 'replies': []})
        elif where == 'replies':
            self.put(kp, {'procs': {}, 'replies': [{'name': name + '.json'}]})
        elif where == 'responses':
            self.respond(name)
        elif where == 'missing':
            kp.unlink()
        elif where == 'broken':
            kp.write_text('{'); self.respond(name)  # 不准越過帳本先看回音。
        elif where == 'shape':
            self.put(kp, {'procs': [], 'replies': []})
        with patch('aos_client.submit', wraps=agent.aos_client.submit) as submit:
            self.assertEqual(self.tick(), 1 if where in ('broken', 'shape') else 0)
            self.assertEqual(submit.call_count, int(where in ('none', 'missing')))
        self.assertEqual(self.state()['batch']['sent'], where not in ('broken', 'shape'))
    return test


for where in ('requests', 'procs', 'replies', 'responses', 'none', 'missing', 'broken', 'shape'):
    setattr(AgentTickTests, 'test_post_check_' + where, posting_case(where))


def result_case(kind, change, code, expected):
    def test(self):
        name = self.prepare(kind)
        if kind == 'think':
            self.output(name)
        else:
            path = self.base / 'work' / (name + '.out'); path.parent.mkdir(exist_ok=True)
            path.write_bytes(b'out\xff\n')
        if code is not None:
            error = {'code': -32602, 'message': '退件'}
            if code != 'numeric':
                error['data'] = {'code': code}
            self.respond(name, error=error)
        else:
            self.respond(name, result=dict(RESULT, **change))
        with self.crash_at('state.done'), self.assertRaises(Crash):
            self.tick()
        done = self.state()['batch']['calls'][0]['done']
        wanted = copy.deepcopy(expected)
        if kind == 'think' and 'fail' in wanted:
            wanted['fail'] = wanted['fail'].replace('log/llm.err', str(self.base / 'log/llm.err'))
            wanted['fail'] = wanted['fail'].replace('llm 池 cpu 的 cpu.log', str(self.k / 'cpus/*/cpu.log'))
            if wanted['fail'] == '逾時（125000 ms）':
                wanted['fail'] = ('逾時（125000 ms，是 info.llm.timeout_ms；要更久就改 agent 的 info.json；'
                                  'llm.err 在 %s）' % (self.base / 'log/llm.err'))
        self.assertEqual(done, wanted)
        self.assertFalse(self.state()['batch']['calls'][0]['acked'])
        self.assertFalse(list((self.k / 'requests').glob('ack-*')))
    return test


think_rows = [
    ('success', {}, None, {'ok': True}),
    ('stopped', {'stopped': True, 'timed_out': True, 'kind': 'aos', 'code': 9}, None,
     {'fail': '被強制停', 'count': False}),
    ('timeout', {'timed_out': True, 'kind': 'aos', 'code': 9}, None, {'fail': '逾時（125000 ms）', 'count': True}),
    ('aos', {'kind': 'aos', 'code': 125}, None,
     {'fail': 'aos-llm call 沒跑起來（kind=aos），看 llm 池 cpu 的 cpu.log', 'count': True}),
    ('exit', {'code': 7}, None, {'fail': 'aos-llm call exit 7，看 log/llm.err', 'count': True}),
    ('stopping', {}, 'Stopping', {'fail': 'kernel 停機時取消，沒跑', 'count': False}),
    ('interrupted', {}, 'Interrupted', {'fail': '結果不明（Interrupted）', 'count': True}),
    ('removed', {}, 'Removed', {'fail': '結果不明（Removed）', 'count': True}),
    ('other', {}, 'Other', {'fail': 'kernel 退件：Other', 'count': True}),
    ('numeric', {}, 'numeric', {'fail': 'kernel 退件：-32602', 'count': True})]
act_rows = [
    ('success', {}, None, {'content': 'out\ufffd\n'}),
    ('stopped', {'stopped': True, 'timed_out': True, 'kind': 'aos', 'code': 9}, None, {'content': UNKNOWN}),
    ('timeout', {'timed_out': True, 'kind': 'aos', 'code': 9}, None, {'content': '工具 sh 逾時（60000 ms）：out\ufffd\n'}),
    ('aos', {'kind': 'aos', 'code': 125}, None, {'content': '工具 sh 無法執行（kind=aos），詳情在跑它那顆 cpu 的 cpu.log'}),
    ('exit', {'code': 7}, None, {'content': '工具 sh 失敗（exit 7）：out\ufffd\n'}),
    ('interrupted', {}, 'Interrupted', {'content': UNKNOWN}),
    ('removed', {}, 'Removed', {'content': UNKNOWN}),
    ('stopping', {}, 'Stopping', {'content': '工具 sh 沒跑：kernel 停機時取消'}),
    ('other', {}, 'Other', {'content': '工具 sh 沒跑：kernel 退件（Other）'}),
    ('numeric', {}, 'numeric', {'content': '工具 sh 沒跑：kernel 退件（-32602）'})]
for kind, rows in [('think', think_rows), ('act', act_rows)]:
    for label, change, code, expected in rows:
        setattr(AgentTickTests, 'test_result_%s_%s' % (kind, label), result_case(kind, change, code, expected))


def bad_model_case(raw):
    def test(self):
        name = self.prepare(); self.respond(name)
        path = self.base / 'work' / (name + '.out'); path.parent.mkdir()
        if raw is not None:
            path.write_bytes(raw)
        with self.crash_at('state.done'), self.assertRaises(Crash):
            self.tick()
        done = self.state()['batch']['calls'][0]['done']
        self.assertTrue(done['count'])
        self.assertTrue(done['fail'].startswith('MessageInvalid:'))
    return test


for label, raw in [('json', b'{'), ('extra_json', b'{}\n{}'), ('array', b'[]'), ('utf8', b'\xff'),
                   ('missing', None), ('user', b'{"role":"user","content":"x"}')]:
    setattr(AgentTickTests, 'test_model_invalid_' + label, bad_model_case(raw))


def history_changed_case(mode):
    def test(self):
        name = self.prepare('act' if mode == 'ids' else 'think', done={'content': 'x'} if mode == 'ids' else {'ok': True}, acked=True)
        if mode == 'ids':
            other = copy.deepcopy(ASSISTANT); other['tool_calls'][0]['id'] = 'changed'
            history = [other]
        else:
            self.output(name)
            history = [MESSAGE, MESSAGE] if mode == 'length' else [dict(MESSAGE, content='別的')]
        self.put(self.base / 'prompts/history.json', history)
        before = self.snapshot()
        self.assertEqual(self.tick(), 1)
        self.assertIn('HistoryChanged', self.err.getvalue())
        self.assertEqual(before, self.snapshot())
    return test


for mode in ('length', 'tail', 'ids'):
    setattr(AgentTickTests, 'test_history_changed_' + mode, history_changed_case(mode))


def sweep_case(mode):
    def test(self):
        name = 'B-0'
        self.put(self.base / 'state.json', {'sweep': [{'kernel': str(self.k), 'name': name}]})
        for suffix in ('.in', '.out', '.inst.json'):
            self.put(self.base / 'work' / (name + suffix), {})
        if mode == 'procs':
            self.put(self.k / 'state.json', {'procs': {name: {'discard': True}}, 'replies': []})
        elif mode == 'requests':
            self.put(self.k / 'requests' / (name + '.json'), {})
        elif mode == 'missing':
            (self.k / 'state.json').unlink()
        elif mode == 'broken':
            (self.k / 'state.json').write_text('{')
        self.assertEqual(self.tick(), 101)
        self.assertEqual(bool(self.state()['sweep']), mode != 'clear')
        self.assertEqual(len(list((self.base / 'work').iterdir())), 0 if mode == 'clear' else 3)
    return test


for mode in ('procs', 'requests', 'clear', 'missing', 'broken'):
    setattr(AgentTickTests, 'test_sweep_' + mode, sweep_case(mode))


def initial_invalid_case(mode):
    def test(self):
        src, dst = self.base / 'go', self.base / 'go.id.done'
        self.put(src, '保持原樣')
        self.put(self.base / 'state.json', {'consuming': [{'src': str(src), 'dst': str(dst)}],
                                           'sweep': [{'kernel': str(self.k), 'name': 'B-0'}]})
        self.put(self.base / 'work/B-0.out', '不可刪')
        if mode == 'info':
            self.put(self.base / 'info.json', {})
        elif mode == 'state':
            self.put(self.base / 'state.json', {'state': 'wait'})
        elif mode == 'history':
            self.put(self.base / 'prompts/history.json', [{}])
        elif mode == 'tools':
            self.info['tools'] = ['tools.json']; self.put(self.base / 'info.json', self.info)
            self.put(self.base / 'tools.json', [{}])
        elif mode == 'waits':
            st = self.state(); st['waits'] = [{'$opt': 'bad', '$val': 'go'}]
            self.put(self.base / 'state.json', st)
        before = self.snapshot()
        self.assertEqual(self.tick(), 1)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(len(self.err.getvalue().splitlines()), 1)
    return test


for mode in ('info', 'state', 'history', 'tools', 'waits'):
    setattr(AgentTickTests, 'test_initial_zero_writes_' + mode, initial_invalid_case(mode))


def incompatible_case(code):
    def test(self):
        self.put(self.k / 'info.json', {'done_exit': code})
        self.assertEqual(agent.start(self.base, self.env), 1)
        self.assertIn('KernelIncompatible', self.err.getvalue())
        self.assertFalse((self.base / 'tick.json').exists())
        self.assertFalse(list((self.k / 'requests').iterdir()))
    return test


for code in (1, 101):
    setattr(AgentTickTests, 'test_start_incompatible_' + str(code), incompatible_case(code))


def mismatch_case(value):
    def test(self):
        self.put(self.base / 'tick.json', value)
        self.assertEqual(agent.start(self.base, self.env), 1)
        self.assertIn('tick.json 綁在另一個 K，要換就刪掉 tick.json 再 start', self.err.getvalue())
        self.assertFalse(list((self.k / 'requests').iterdir()))
    return test


for label, value in [('other', {'envs': {'AOS_KERNEL_HOME': '/other'}}), ('directive', {'envs': {'AOS_KERNEL_HOME': {'$env': 'AOS_KERNEL_HOME'}}}),
                     ('type', {'envs': []}), ('nonobject', [])]:
    setattr(AgentTickTests, 'test_start_mismatch_' + label, mismatch_case(value))


def timeout_case(starting):
    def test(self):
        with patch.object(agent, 'WAIT_TIMEOUT_MS', 1):
            self.assertEqual((agent.start if starting else agent.stop)(self.base, self.env), 1)
        request = next((self.k / 'requests').glob('aa-*'))
        self.assertEqual(self.err.getvalue(), 'aos-agent: ReadFailed: 等回音逾時，回音會出現在 %s/responses/%s，讀完自己放 ack（cpu.md §3.3）\n' % (self.k, request.name))
        self.assertFalse(list((self.k / 'requests').glob('ack-*')))
    return test


setattr(AgentTickTests, 'test_start_timeout', timeout_case(True))
setattr(AgentTickTests, 'test_stop_timeout', timeout_case(False))


def main_env_case(env):
    def test(self):
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(agent.main(['tick', '--target', str(self.base)]), 2)
        self.assertFalse((self.base / 'state.json').exists())
    return test


setattr(AgentTickTests, 'test_main_missing_kernel', main_env_case({}))
setattr(AgentTickTests, 'test_main_relative_kernel', main_env_case({'AOS_KERNEL_HOME': 'relative'}))


def kernel_field_case(key, value):
    def test(self):
        self.put(self.k / 'info.json', {key: value})
        self.assertEqual(agent.start(self.base, self.env), 1)
        self.assertIn('FieldTypeMismatch', self.err.getvalue())
        self.assertFalse(list((self.k / 'requests').iterdir()))
    return test


for label, key, value in [('done_bool', 'done_exit', True), ('done_large', 'done_exit', 256),
                         ('bad_negative', 'bad_after', -1), ('bad_null', 'bad_after', None)]:
    setattr(AgentTickTests, 'test_kernel_field_' + label, kernel_field_case(key, value))


if __name__ == '__main__':
    unittest.main()
