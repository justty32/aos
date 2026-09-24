"""C-1～C-9：假 K 與副作用後掛鉤，驗證下一格的持久化恢復。"""
import copy
import unittest
from pathlib import Path
from unittest.mock import patch

import aos_agent as agent
import test_agent_tick as fixture


class AgentCrashTests(unittest.TestCase):
    # 只借建家方法，不繼承既有測試，以免 discovery 重跑整個測試類別。
    for _name in ('setUp', 'put', 'read', 'state', 'tick', 'prepare', 'respond', 'output', 'crash_at'):
        locals()[_name] = getattr(fixture.AgentTickTests, _name)

    def crash(self, step):
        with self.crash_at(step), self.assertRaises(fixture.Crash):
            self.tick()

    def history(self):
        return self.read(self.base / 'prompts/history.json')

    def test_C1_gate_preserves_batch(self):
        """C-1：在途加門保留整批，開門後照常收回。"""
        name = self.prepare()
        self.respond(name)
        self.output(name)
        st = self.state()
        batch = copy.deepcopy(st['batch'])
        st['waits'] = ['go']
        self.put(self.base / 'state.json', st)
        self.assertEqual(self.tick(), 101)
        self.assertEqual(self.state()['batch'], batch)
        self.assertFalse(list((self.k / 'requests').glob('ack-*')))
        (self.base / 'go').touch()
        self.assertEqual(self.tick(), 0)
        self.assertIsNone(self.state()['batch'])
        self.assertEqual(self.history(), [fixture.MESSAGE])

    def recover_result(self, step):
        name = self.prepare()
        self.respond(name)
        self.output(name)
        self.crash(step)
        st = self.state()
        self.assertEqual(st['batch']['calls'][0]['done'], {'ok': True})
        before = list((self.k / 'requests').glob('ack-*'))
        if step == 'state.done':
            self.assertEqual(before, [])
        if step == 'ack.post':
            self.assertEqual(len(before), 1)
            self.assertFalse(st['batch']['calls'][0]['acked'])
            # 模擬第一個 ack 已被 K 消化；恢復不能再依賴回音存在。
            (self.k / 'responses' / (name + '.json')).unlink()
        history_path = self.base / 'prompts/history.json'
        original = history_path.read_bytes() if history_path.exists() else None
        self.assertEqual(self.tick(), 0)
        self.assertEqual(self.history(), [fixture.MESSAGE])
        self.assertIsNone(self.state()['batch'])
        if step == 'history.write':
            self.assertEqual(history_path.read_bytes(), original)
        acks = list((self.k / 'requests').glob('ack-*'))
        self.assertEqual(len(acks), 2 if step == 'ack.post' else 1)
        for ack in acks:
            self.assertEqual(self.read(ack)['params'], {'name': name + '.json'})

    def test_C2_done_before_ack(self):
        """C-2a：done 已落盤、ack 尚未放，下一格補 ack 並結清。"""
        self.recover_result('state.done')

    def test_C2_ack_before_acked(self):
        """C-2b：ack 已放、acked 未記，重 ack 不影響結清。"""
        self.recover_result('ack.post')

    def test_C2_history_before_state(self):
        """C-2c：記憶已寫、結清未記，重寫的位元組完全相同。"""
        self.recover_result('history.write')

    def recover_post(self, location, change_kernel=False):
        self.put(self.base / 'state.json', {'state': 'think'})
        self.crash('request.post')
        batch = self.state()['batch']
        self.assertFalse(batch['sent'])
        name = batch['calls'][0]['name']
        request = self.k / 'requests' / (name + '.json')
        original = request.read_bytes()
        if location != 'requests':
            request.unlink()
        ledger = {'procs': {}, 'replies': []}
        if location == 'procs':
            ledger['procs'][name] = {}
        elif location == 'replies':
            ledger['replies'] = [{'name': name + '.json'}]
        elif location == 'responses':
            self.respond(name)
        self.put(self.k / 'state.json', ledger)
        if change_kernel:
            self.env['AOS_KERNEL_HOME'] = str(self.root / 'other-K')
        with patch.object(agent.aos_client, 'submit', wraps=agent.aos_client.submit) as submit:
            self.assertEqual(self.tick(), 0)
            self.assertEqual(submit.call_count, int(location == 'absent'))
            if location == 'absent':
                self.assertEqual(submit.call_args.args[0], str(self.k))
        self.assertTrue(self.state()['batch']['sent'])
        self.assertEqual(self.state()['batch']['kernel'], str(self.k))
        if location == 'requests':
            self.assertEqual(request.read_bytes(), original)
        self.assertFalse((self.root / 'other-K').exists())

    def test_C3_requests(self):
        """C-3a：link 後崩，原單還在時不重放。"""
        self.recover_post('requests')

    def test_C3_procs(self):
        """C-3a：原單已收進 procs 時不重放。"""
        self.recover_post('procs')

    def test_C3_replies(self):
        """C-3a：回音還在 replies 出貨箱時不重放。"""
        self.recover_post('replies')

    def test_C3_responses(self):
        """C-3a：回音已出貨到 responses 時不重放。"""
        self.recover_post('responses')

    def test_C3_changed_kernel(self):
        """C-3b：換 AOS_KERNEL_HOME 後仍查舊 K；缺單時仍放到舊 K。"""
        self.recover_post('procs', True)
        name = self.state()['batch']['calls'][0]['name']
        st = self.state()
        st['batch']['sent'] = False
        self.put(self.base / 'state.json', st)
        self.put(self.k / 'state.json', {'procs': {}, 'replies': []})
        self.assertEqual(self.tick(), 0)
        self.assertTrue((self.k / 'requests' / (name + '.json')).exists())
        self.assertFalse((self.root / 'other-K').exists())

    def local_failure(self, invalid):
        self.prepare('act')
        if invalid:
            tool = copy.deepcopy(fixture.TOOL)
            tool['_meta'] = {'argv': {'$env': 'DOES_NOT_EXIST'}}
            tool['_jail'] = False       # 測 _meta 解不開；沒 access.json 時要關牢的會先被 NoAccess 擋
            self.put(self.base / 'tools.json', [tool])
        else:
            self.put(self.base / 'tools.json', [])
        self.put(self.base / 'state.json', {'state': 'act'})
        self.crash('state.batch')
        for _ in range(3):
            self.assertEqual(self.tick(), 0)
            if self.state()['batch'] is None:
                break
        self.assertIsNone(self.state()['batch'])
        self.assertEqual(self.state()['state'], 'think')
        self.assertEqual(len(self.history()), 2)
        self.assertIn('跑不起來' if invalid else '沒有這個工具', self.history()[-1]['content'])
        self.assertEqual(list((self.k / 'requests').iterdir()), [])

    def test_C4_missing_tools(self):
        """C-4：全是不認識的工具，建批後崩仍接回本地結果。"""
        self.local_failure(False)

    def test_C4_invalid_meta(self):
        """C-4：工具 _meta 解不開，恢復後本地結清。"""
        self.local_failure(True)

    def test_C5_removed_keeps_work_until_reaped(self):
        """C-5：Removed 後 procs 尚在，工作檔保留到下一次安全清理。"""
        name = self.prepare('act')
        self.respond(name, error={'code': -32000, 'data': {'code': 'Removed'}})
        paths = [self.base / 'work' / (name + s) for s in ('.in', '.out', '.inst.json')]
        for path in paths:
            self.put(path, '仍在跑')
        self.put(self.k / 'state.json', {'procs': {name: {'discard': True}}, 'replies': []})
        self.assertEqual(self.tick(), 0)
        st = self.state()
        st['waits'] = ['hold']
        self.put(self.base / 'state.json', st)
        self.assertEqual(self.tick(), 101)
        self.assertEqual(self.state()['sweep'], [{'kernel': str(self.k), 'name': name}])
        self.assertTrue(all(p.exists() for p in paths))
        self.put(self.k / 'state.json', {'procs': {}, 'replies': []})
        self.assertEqual(self.tick(), 101)
        self.assertEqual(self.state()['sweep'], [])
        self.assertFalse(any(p.exists() for p in paths))

    def consume(self, step, replace):
        self.put(self.base / 'state.json', {'waits': [{'$opt': 'consume', '$val': 'go'}]})
        self.put(self.base / 'go', 'A')
        self.crash(step)
        pair = self.state()['consuming'][0]
        self.assertEqual(self.state()['waits'], [])
        if replace:
            self.put(self.base / 'go', 'B')
        self.assertEqual(self.tick(), 102)  # 09-24 停車：門開了、idle 沒輸入
        self.assertEqual(self.read(Path(pair['dst'])), 'A')
        self.assertEqual(self.state()['consuming'], [])
        if replace:
            self.assertEqual(self.read(self.base / 'go'), 'B')
        else:
            self.assertFalse((self.base / 'go').exists())

    def test_C6_before_rename(self):
        """C-6a：門已劃掉、consuming 已記，恢復補搬。"""
        self.consume('state.gate', False)

    def test_C6_after_rename_new_signal(self):
        """C-6b／E-1：搬完再投同名訊號，新檔不被吞。"""
        self.consume('consume.move', True)

    def failure_count(self, after, initial):
        name = self.prepare(errors=initial)
        self.respond(name, result=dict(fixture.RESULT, code=7))
        if after:
            self.crash('state.settled')
        else:
            # 掛鉤只有寫後；在 write_state 邊界注入寫前崩潰。
            original = agent.Runtime.save
            def save(run, step):
                if step == 'state.settled':
                    raise fixture.Crash(step)
                return original(run, step)
            with patch.object(agent.Runtime, 'save', save), self.assertRaises(fixture.Crash):
                self.tick()
            self.assertEqual(self.state()['errors'], initial)
            self.assertIsNotNone(self.state()['batch'])
        self.assertIn(self.tick(), (0, 101))
        st = self.state()
        self.assertEqual(st['errors'], (initial + 1) % 3)
        self.assertEqual(len(st['waits']), int(initial == 2))
        if initial == 2:
            self.assertEqual(st['waits'][0]['$val'], 'continue-' + name.rsplit('-', 1)[0] + '.json')
            self.assertEqual(self.tick(), 101)
            self.assertEqual(self.state()['waits'], st['waits'])

    def test_C7_before_settle(self):
        """C-7：結清寫前崩，第一敗只算一次。"""
        self.failure_count(False, 0)

    def test_C7_after_settle(self):
        """C-7：結清寫後崩，第一敗不重算。"""
        self.failure_count(True, 0)

    def test_C7_third_before_settle(self):
        """C-7：第三敗寫前崩，恢復只加一道門。"""
        self.failure_count(False, 2)

    def test_C7_third_after_settle(self):
        """C-7：第三敗寫後崩，不重加門。"""
        self.failure_count(True, 2)

    def intake_recovery(self, step, replace=False):
        self.put(self.base / 'input.json', 'A')
        self.crash(step)
        if replace:
            self.put(self.base / 'input.json', 'B')
        path = self.base / 'prompts/history.json'
        before = path.read_bytes() if path.exists() else None
        self.assertEqual(self.tick(), 0)
        self.assertEqual(self.history(), [{'role': 'user', 'content': 'A'}])
        self.assertIsNone(self.state()['intake'])
        if step == 'history.write':
            self.assertEqual(path.read_bytes(), before)
        if replace:
            self.assertEqual(self.read(self.base / 'input.json'), 'B')
            st = self.state()
            st['state'] = 'idle'
            self.put(self.base / 'state.json', st)
            self.assertEqual(self.tick(), 0)
            self.assertEqual([m['content'] for m in self.history()], ['A', 'B'])

    def test_C8_intake_before_move(self):
        """C-8a：intake 已記但未搬，下一格補完。"""
        self.intake_recovery('state.intake')

    def test_C8_move_before_history_new_input(self):
        """C-8b／E-1：封存 A 後投 B，恢復只讀 A，下一輪才收 B。"""
        self.intake_recovery('consume.move', True)

    def test_C8_history_before_state(self):
        """C-8c：收輸入的記憶已寫，重 tick 位元組相同。"""
        self.intake_recovery('history.write')

    def test_C9_think_stopping_retries(self):
        """C-9：Stopping 不算連敗、保留 think，下格使用新批名。"""
        name = self.prepare(errors=1)
        self.respond(name, error={'code': -32000, 'data': {'code': 'Stopping'}})
        self.crash('state.done')
        self.assertFalse(self.state()['batch']['calls'][0]['done']['count'])
        self.assertEqual(self.tick(), 0)
        self.assertEqual((self.state()['state'], self.state()['errors']), ('think', 1))
        self.assertEqual(self.tick(), 0)
        self.assertNotEqual(self.state()['batch']['calls'][0]['name'], name)

    def test_C9_tool_stopping_is_not_run(self):
        """C-9：工具 Stopping 接回確定沒跑的訊息。"""
        name = self.prepare('act')
        self.respond(name, error={'code': -32000, 'data': {'code': 'Stopping'}})
        self.assertEqual(self.tick(), 0)
        self.assertIn('沒跑', self.history()[-1]['content'])
        self.assertEqual(self.state()['state'], 'think')
