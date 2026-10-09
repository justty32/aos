"""進門不寫檔、既有回條與一行錯誤契約。"""
import json
import os
import time
from pathlib import Path
from unittest.mock import patch

from llmcallcase import LlmcallCase, R, bg, tree


class TestLlmcallErrors(LlmcallCase):
    def line(self, p, rc, prefix='aos7-llmcall: '):
        self.assertEqual(p.returncode, rc, p.stdout + p.stderr)
        self.assertEqual(len(p.stderr.splitlines()), 1)
        self.assertTrue(p.stderr.startswith(prefix), p.stderr)
        self.assertIn('。', p.stderr)

    def stop_ledger(self):
        # setUp 啟動的帳是本 node 唯一 ledger 子程序。
        import _proc
        for p, _, _ in list(_proc._live):
            if p.args[2:4] == ['ledger', 'budget/llm'] and Path(p.args[1]).name == 'aos7-budget':
                p.terminate()
                p.wait(timeout=3)
        self.assertFalse(bg.ledger_running(bg.Bud(str(self.bd)), wait=0))

    def test_absent_and_dead_ledger_no_write(self):
        self.stop_ledger()
        for stale in (False, True):
            with self.subTest(stale=stale):
                lock = self.bd / 'ledger.lock'
                if stale:
                    lock.touch()
                else:
                    lock.unlink(missing_ok=True)
                before = tree(self.bd)
                start = time.monotonic()
                p = self.call(extra=('--out', 'result.json'))
                self.assertLess(time.monotonic() - start, 2)
                self.line(p, 1, 'aos7-llmcall: 帳任務沒在跑')
                self.assertEqual(json.loads(p.stdout), {'outcome': 'refused', 'stage': 'ledger', 'why': '帳任務沒在跑'})
                self.assertFalse((self.node / 'llmcall').exists())
                self.assertFalse((self.node / 'result.json').exists())
                self.assertEqual(tree(self.bd), before)

    def test_receipt_replay_without_ledger(self):
        first = self.call()
        self.assert_receipt(first)
        self.stop_ledger()
        p = self.call()
        self.assertEqual((p.returncode, p.stdout, p.stderr), (0, first.stdout, ''))

    def test_bad_arguments_and_help(self):
        bad = self.node / 'bad.json'
        bad.write_text('not json')
        for args in ([], ['call'], self.args(c='bad!'), self.args(req=str(bad)),
                     self.args(extra=('--reserve', 'oops')), ['nonesuch']):
            self.line(self.cli(*args), 2)
        for args in (['--help'], ['call', '--help']):
            p = self.cli(*args)
            self.assertEqual((p.returncode, p.stderr), (0, ''))
        self.stop_ledger()
        self.line(self.cli(*self.args(req=str(bad))), 2)

    def test_uncertain_intent_and_billing(self):
        self.intent()
        self.line(self.call(), 3, 'aos7-llmcall: 不確定：')
        for mode, usage in (('no_usage', R), ('over', R + 1)):
            p = self.call(c=mode, req=self.request(mode + '.json', mode=mode, usage=usage))
            self.line(p, 4, 'aos7-llmcall: 已交付但帳沒清')

    def test_busy_is_uncertain(self):
        from aos7_fs import locked
        with locked(str(self.cd() / 'request.json')):
            self.line(self.call(), 3, 'aos7-llmcall: 不確定：')

    def test_lock_probe_io_and_fd_close(self):
        with patch.object(bg.os, 'open', side_effect=OSError('broken')):
            with self.assertRaises(OSError):
                bg.ledger_running(bg.Bud(str(self.bd)), wait=0)
        before = len(os.listdir('/proc/self/fd'))
        for _ in range(30):
            self.assertTrue(bg.ledger_running(bg.Bud(str(self.bd)), wait=0))
        self.assertEqual(len(os.listdir('/proc/self/fd')), before)
