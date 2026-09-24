"""09-24 one-boot：agent 讀 kernel 帳本改走 aos_kernel_store（K/ledger.sqlite）。

- aos-agent start 的相容檢查：只有舊 K/state.json（沒 sqlite）＝KernelIncompatible、叫人 aos up；
  sqlite 帳本有 chain 卻沒 features park＝KernelIncompatible；沒 boot 過不擋。
- aos_agent_runtime.kernel_proc／kernel_knows／kernel_procs 查得到 busy 上 discard 的那格等。
- sweep：K 沒帳本（或還是舊帳本）時不刪 work 檔。
假 K 家、直接呼叫函式，不開 daemon。
"""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import aos_agent as agent
import aos_agent_runtime as runtime
import aos_home
import aos_kernel_store

OLD = {'chain': '1-1', 'procs': {}, 'replies': []}


class LedgerCase(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.base, self.k = self.root / 'bob', self.root / 'K'
        self.base.mkdir()
        (self.k / 'requests').mkdir(parents=True)
        (self.k / 'responses').mkdir()
        self.env = {'AOS_KERNEL_HOME': str(self.k)}
        self.put(self.base / 'info.json', {'_metainfo': {'_type': 'llm_agent', '_version': 1}, 'llm': {'model': 'small'}})
        self.put(self.k / 'info.json', {})
        self.err = io.StringIO()
        self.addCleanup(mock.patch.stopall)
        mock.patch('sys.stderr', self.err).start()

    def put(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')

    def posted(self):
        return sorted(p.name for p in (self.k / 'requests').iterdir())


class StartCompatibility(LedgerCase):
    def test_legacy_state_json_only_refused_says_aos_up(self):
        self.put(self.k / 'state.json', dict(OLD, features=['park']))  # 舊 kernel 就算有 park 也一樣：帳本格式不對
        self.assertFalse((self.k / 'ledger.sqlite').exists())
        with self.assertRaises(agent.AgentError) as ctx:
            agent._compatible(str(self.k), self.env)
        self.assertEqual(ctx.exception.code, 'KernelIncompatible')
        self.assertIn('aos up', ctx.exception.msg)
        self.assertIn('state.json', ctx.exception.msg)
        self.assertEqual(agent.start(self.base, self.env), 1)   # 端到端：start 退 1、什麼都沒登記
        self.assertIn('KernelIncompatible', self.err.getvalue())
        self.assertIn('aos up', self.err.getvalue())
        self.assertEqual(self.posted(), [])

    def test_sqlite_with_chain_without_park_refused(self):
        aos_kernel_store.write(self.k, OLD)
        with self.assertRaises(agent.AgentError) as ctx:
            agent._compatible(str(self.k), self.env)
        self.assertEqual(ctx.exception.code, 'KernelIncompatible')
        self.assertIn('102', ctx.exception.msg)
        aos_kernel_store.write(self.k, dict(OLD, features=['other']))
        with self.assertRaises(agent.AgentError):
            agent._compatible(str(self.k), self.env)
        self.assertEqual(agent.start(self.base, self.env), 1)
        self.assertIn('KernelIncompatible', self.err.getvalue())
        self.assertEqual(self.posted(), [])
        aos_kernel_store.write(self.k, dict(OLD, features=['park']))
        agent._compatible(str(self.k), self.env)   # 有 park：過

    def test_never_booted_not_blocked(self):
        agent._compatible(str(self.k), self.env)                    # 沒有任何帳本
        aos_kernel_store.write(self.k, {'procs': {}, 'replies': []})
        agent._compatible(str(self.k), self.env)                    # sqlite 在、還沒 chain


class KernelProc(LedgerCase):
    def setUp(self):
        super().setUp()
        self.proc = {'status': 'running', 'target': str(self.base / 'tick.json'), 'once': False}

    def test_busy_discard_slot_found(self):
        aos_kernel_store.write(self.k, {'procs': {'agent-bob': self.proc, 'other': {'status': 'queued'}},
                                        'busy': {'default/0': {'proc': 'other', 'req': 'a'},
                                                 'default/1': {'proc': 'agent-bob', 'req': 'b', 'discard': True}},
                                        'replies': []})
        found = runtime.kernel_proc(str(self.k), 'agent-bob')
        self.assertEqual(found, {'name': 'agent-bob', 'proc': self.proc, 'cpu': 'default/1', 'discard': True})
        other = runtime.kernel_proc(str(self.k), 'other')
        self.assertEqual((other['cpu'], other['discard']), ('default/0', False))
        self.assertIsNone(runtime.kernel_proc(str(self.k), 'nobody'))

    def test_not_on_cpu(self):
        aos_kernel_store.write(self.k, {'procs': {'agent-bob': self.proc}, 'replies': []})
        self.assertEqual(runtime.kernel_proc(str(self.k), 'agent-bob'),
                         {'name': 'agent-bob', 'proc': self.proc, 'cpu': None, 'discard': False})

    def test_start_already_exists_discard_says_last_stop_still_running(self):
        aos_kernel_store.write(self.k, {'procs': {'agent-bob': self.proc}, 'replies': [],
                                        'busy': {'llm/0': {'proc': 'agent-bob', 'req': 'b', 'discard': True}}})
        note = agent._already(str(self.k), {'name': 'agent-bob', 'target': self.proc['target']})
        self.assertIn('上次 stop 的那格還在跑', note)
        aos_kernel_store.write(self.k, {'procs': {'agent-bob': self.proc}, 'replies': [],
                                        'busy': {'llm/0': {'proc': 'agent-bob', 'req': 'b'}}})
        self.assertIsNone(agent._already(str(self.k), {'name': 'agent-bob', 'target': self.proc['target']}))

    def test_already_on_legacy_or_broken_ledger_is_unreadable(self):
        params = {'name': 'agent-bob', 'target': self.proc['target']}
        self.put(self.k / 'state.json', dict(OLD, procs={'agent-bob': self.proc}))
        self.assertIn('帳本讀不到', agent._already(str(self.k), params))
        (self.k / 'state.json').unlink()
        (self.k / 'ledger.sqlite').write_text('不是 sqlite')
        self.assertIn('帳本讀不到', agent._already(str(self.k), params))

    def test_not_booted_and_legacy(self):
        self.assertIsNone(runtime.kernel_proc(str(self.k), 'agent-bob'))
        self.assertFalse(runtime.kernel_knows(str(self.k), 'agent-bob'))
        self.assertEqual(runtime.kernel_procs(str(self.k)), {})
        self.put(self.k / 'state.json', dict(OLD, procs={'agent-bob': self.proc}))
        for call in (lambda: runtime.kernel_proc(str(self.k), 'agent-bob'),
                     lambda: runtime.kernel_knows(str(self.k), 'agent-bob'),
                     lambda: runtime.kernel_procs(str(self.k))):
            with self.assertRaises(aos_home.HomeError) as ctx:
                call()
            self.assertEqual(ctx.exception.code, 'LedgerVersion')

    def test_knows_and_procs(self):
        aos_kernel_store.write(self.k, {'procs': {'agent-bob': self.proc},
                                        'replies': [{'name': 'aw-bob-1-1-0.json', 'cpu': 'default/0'}]})
        self.assertTrue(runtime.kernel_knows(str(self.k), 'agent-bob'))       # 帳本有這個行程
        self.assertTrue(runtime.kernel_knows(str(self.k), 'aw-bob-1-1-0'))    # 出貨箱有它的回音
        self.assertFalse(runtime.kernel_knows(str(self.k), 'aw-bob-1-1-1'))
        self.assertEqual(runtime.kernel_procs(str(self.k)), {'agent-bob': self.proc})


class Sweep(LedgerCase):
    NAME = 'B-0'

    def arm(self):
        self.put(self.base / 'state.json', {'sweep': [{'kernel': str(self.k), 'name': self.NAME}]})
        for suffix in ('.in', '.out', '.inst.json'):
            self.put(self.base / 'work' / (self.NAME + suffix), {})

    def swept(self):
        self.assertEqual(agent.tick(self.base, self.env), 102)   # idle 沒輸入：停車
        state = json.loads((self.base / 'state.json').read_text())
        return bool(state['sweep']), len(list((self.base / 'work').iterdir()))

    def test_no_ledger_keeps_work(self):
        self.arm()
        self.assertEqual(self.swept(), (True, 3))
        self.assertFalse((self.k / 'ledger.sqlite').exists())     # 讀的時候不會順手建帳本

    def test_legacy_ledger_keeps_work(self):
        self.put(self.k / 'state.json', OLD)
        self.arm()
        self.assertEqual(self.swept(), (True, 3))

    def test_ledger_forgot_it_clears(self):
        aos_kernel_store.write(self.k, {'procs': {}, 'replies': []})
        self.arm()
        self.assertEqual(self.swept(), (False, 0))

    def test_ledger_still_has_it_keeps(self):
        aos_kernel_store.write(self.k, {'procs': {self.NAME: {'status': 'running'}}, 'replies': []})
        self.arm()
        self.assertEqual(self.swept(), (True, 3))


if __name__ == '__main__':
    unittest.main()
