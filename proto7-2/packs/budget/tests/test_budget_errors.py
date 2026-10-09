"""budget 進門唯讀拒絕與 stderr 一行契約。"""
import json
import os
import time
from pathlib import Path

from budgetcase import BudgetCase, bg


class TestBudgetErrors(BudgetCase):
    def setUp(self):
        super().setUp()
        self.node = os.path.join(self.root, 'a')
        self.bd = self.setup_budget(self.node)

    def line(self, p, rc, prefix='aos7-budget: '):
        self.assertEqual(p.returncode, rc, p.stdout + p.stderr)
        self.assertEqual(len(p.stderr.splitlines()), 1)
        self.assertTrue(p.stderr.startswith(prefix), p.stderr)
        self.assertIn('。', p.stderr)

    def snapshot(self):
        return {str(p.relative_to(self.bd)): p.read_bytes() for p in Path(self.bd).rglob('*') if p.is_file()}

    def test_no_running_call_and_settle(self):
        for stale in (False, True):
            if stale:
                Path(self.bd, 'ledger.lock').touch()
            for cmd in ('call', 'settle'):
                before = self.snapshot()
                start = time.monotonic()
                p = self.cli(self.node, cmd, 'budget/demo', '--holder', 'api', '--request', 'r1')
                self.assertLess(time.monotonic() - start, 2)
                self.line(p, 1, 'aos7-budget: 帳任務沒在跑')
                obj = json.loads(p.stdout)
                self.assertEqual(obj['outcome' if cmd == 'call' else 'result'], 'refused')
                self.assertEqual(list(obj), ['kid', 'key', 'outcome', 'stage', 'why'] if cmd == 'call' else ['result', 'why'])
                self.assertEqual(self.snapshot(), before)

    def test_status_missing_bad_and_io(self):
        ledger = Path(self.bd, 'ledger.json')
        original = ledger.read_bytes()
        for content in (None, b'bad json', b'{}'):
            if content is None:
                ledger.unlink()
            else:
                ledger.write_bytes(content)
            p = self.cli(self.node, 'status', 'budget/demo')
            self.line(p, 1)
            self.assertEqual(list(json.loads(p.stdout)), ['error'])
        ledger.write_bytes(original)
        p = self.cli(self.node, 'status', 'budget/demo', env={'AOS7_TEST_FAULT': 'open:*/ledger.json:EIO'})
        self.line(p, 3, 'aos7-budget: 不確定：')
        self.assertEqual(list(json.loads(p.stdout)), ['error'])
        p = self.cli(self.node, 'status', 'budget/demo')
        self.assertEqual((p.returncode, p.stderr), (0, ''))

    def test_bad_arguments_and_help(self):
        bad = Path(self.node, 'bad.json')
        bad.write_text('not json')
        for args in ([], ['call', 'budget/demo'], ['nonesuch', 'budget/demo'],
                     self.call_args('r1', extra=('--amount', 'oops')),
                     self.call_args('r1', payload=str(bad))):
            self.line(self.cli(self.node, *args), 2)
        p = self.cli(self.node, '--help')
        self.assertEqual((p.returncode, p.stderr), (0, ''))

    def test_uncertain_and_terminal_failures(self):
        self.start_ledger(self.node)
        p = self.cli(self.node, *self.call_args('r1'), env={'AOS7_TEST_FAULT': 'open:*/grant.json:EIO'})
        # fault 只在 call 子程序內生效：預留完成後，入口讀 grant 故障。
        self.line(p, 3, 'aos7-budget: 不確定：')
        p = self.cli(self.node, 'init', 'budget/demo')
        self.line(p, 1)
        payload = self.payload(self.node, 'fail.json', mode='fail')
        self.line(self.cli(self.node, *self.call_args('failed', payload=payload)), 1)
        self.line(self.cli(self.node, 'cancel', 'budget/demo', '--holder', 'api', '--request', 'failed'), 1)
