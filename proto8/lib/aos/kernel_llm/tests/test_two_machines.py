# Check two-machines kernel fixes: in-flight brain calls never pin an absolute endpoint path; budget.senders keys that are not folders warn, and sender BudgetMissing names the key.
import json
import os
import subprocess
from pathlib import Path
import unittest

import test_ledger


class InFlightPaths(unittest.TestCase):
    setUp = test_ledger.LedgerTests.setUp
    run_kernel = test_ledger.LedgerTests.run_kernel

    def letters(self):
        out = []
        for p in sorted((self.stack / 'procs_requests/new').glob('*/letter.json')):
            out.append(json.loads(p.read_text())['body'])
        return out

    def target_of(self, body):
        (spec,) = body['procs_added'].values()
        return spec['exec']['argv'][1]

    def send(self, name):
        folder = self.stack / 'requests/new' / name
        folder.mkdir()
        (folder / 'letter.json').write_text(json.dumps({'body': {'request': {'messages': []}}}))

    def test_mount_letter_writes_endpoint_relative_to_daemon(self):
        self.send('one')
        self.run_kernel()
        (body,) = self.letters()
        t = self.target_of(body)
        self.assertEqual(set(t), {'$env', '$path'})
        self.assertEqual(t['$env'], 'AOS_DAEMON')
        self.assertFalse(t['$path'].startswith('/'))
        base = str(self.stack) + '/'
        self.assertEqual(os.path.normpath(base + t['$path']), str(test_ledger.FAKE.parent))

    def test_remount_takes_endpoint_from_current_kernel_json(self):
        # proc.json 記的是上一次的位置；重掛時照 endpoint 代號從現在的 kernel.json 再算
        self.send('two')
        self.run_kernel()
        folder = self.stack / 'requests/cur/two'
        proc = json.loads((folder / 'proc.json').read_text())
        proc['exec'] = '/gone/old/place/llm_fake'
        (folder / 'proc.json').write_text(json.dumps(proc))
        for p in (self.stack / 'procs_requests/new').iterdir():
            (p / 'letter.json').unlink()
            p.rmdir()
        (folder / 'state.json').write_text('{"phase":"running","code":null}')   # 跑到一半死了（不在表上）＝重掛
        self.run_kernel()
        (body,) = self.letters()
        t = self.target_of(body)
        self.assertEqual(os.path.normpath(str(self.stack) + '/' + t['$path']), str(test_ledger.FAKE.parent))
        self.assertEqual(json.loads((folder / 'proc.json').read_text())['retries'], 1)


class BudgetSenders(unittest.TestCase):
    """B09／B10：budget.senders 的 key 不是資料夾＝提醒（變了才印）；寄件人到頂的 BudgetMissing 印 key。"""
    setUp = test_ledger.LedgerTests.setUp

    def kernel(self, senders):
        self.config.write_text(json.dumps({'exec': str(test_ledger.FAKE.parent), 'endpoints': {'fake': {}},
                                           'endpoint': 'fake', 'budget': {'senders': senders}}))
        p = subprocess.run([str(test_ledger.KERNEL), str(self.config)], env=self.env,
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stderr

    def test_missing_sender_folder_warns_once(self):
        err = self.kernel({'agents/gone': {'max_calls': 5}})
        self.assertIn('kernel_llm: warning: budget.senders key "agents/gone" is not a folder: %s/agents/gone' % self.stack, err)
        self.assertIn('relative keys count from %s' % self.stack, err)
        self.assertEqual(self.kernel({'agents/gone': {'max_calls': 5}}), '')   # 下一拍同樣的不重印
        (self.stack / 'agents/here').mkdir(parents=True)
        (self.stack / 'agents/here/state.json').write_text('{}')   # 起過的 proc 的 stack
        self.assertEqual(self.kernel({'agents/here': {'max_calls': 5}}), '')
        self.assertFalse((self.stack / 'budget_warned.txt').exists())
        self.assertIn('agents/gone', self.kernel({'agents/gone': {'max_calls': 5}}))   # 又壞＝再印

    def test_missing_absolute_sender_folder_warns_once(self):
        sender = str(self.stack / 'agents/gone')
        err = self.kernel({sender: {'max_calls': 5}})
        self.assertIn('kernel_llm: warning: budget.senders key "%s" is not a folder yet: %s '
                      '(no proc has run with this stack yet; the limit applies once one does)' % (sender, sender), err)
        self.assertNotIn('avoids the mix-up', err)
        self.assertNotIn('relative keys count from', err)
        self.assertNotIn('counted from the kernel stack', err)
        self.assertEqual(self.kernel({sender: {'max_calls': 5}}), '')

    def test_folder_that_is_not_a_proc_stack_warns(self):
        # 11-13 線修 T39：寄件人是 proc 的 stack；寫成工作區（有資料夾、沒 state.json）的 key 對不上任何腦請求
        (self.stack / 'teams/t1').mkdir(parents=True)
        err = self.kernel({'teams/t1': {'max_calls': 5}})
        self.assertIn('kernel_llm: warning: budget.senders key "teams/t1" is a folder but not a proc stack '
                      '(no state.json): %s/teams/t1' % self.stack, err)
        self.assertIn("the asking proc's stack ($AOS_STACK), not its workspace", err)

    def test_key_counted_from_the_stack_gets_a_hint(self):
        # 11-13 線修 T39：used.json 的 key 相對 kernel stack；照抄進另一夾的 kernel.json 會錯位，提醒寫出對的路徑
        (self.stack / 'procs/lead').mkdir(parents=True)
        (self.stack / 'procs/lead/state.json').write_text('{}')
        (self.stack / 'def').mkdir()
        self.config = self.stack / 'def/kernel.json'
        err = self.kernel({'procs/lead': {'max_calls': 5}})
        self.assertIn('budget.senders key "procs/lead" is not a folder: %s/def/procs/lead' % self.stack, err)
        self.assertIn('counted from the kernel stack (as used.json keys are) it would be %s/procs/lead' % self.stack, err)
        self.assertEqual(self.kernel({str(self.stack / 'procs/lead'): {'max_calls': 5}}), '')   # 絕對路徑＝對上、不提醒

    def test_sender_budget_missing_names_the_key(self):
        ws = self.stack / 'agents/a'
        ws.mkdir(parents=True)
        box = self.stack / 'replies'
        for part in ('new', 'tmp', 'cur'):
            (box / part).mkdir(parents=True)
        folder = self.stack / 'requests/new/L1'
        folder.mkdir()
        (folder / 'letter.json').write_text(json.dumps({'sender': str(ws), 'sent_at': '2026-11-10T00:00:00+08:00',
            'reply_to': str(box), 'body': {'request': {'messages': []}}}))
        self.kernel({'agents/a': {'max_calls': 0}})
        (reply,) = [json.loads(p.read_text()) for p in (box / 'new').glob('*/letter.json')]
        err = reply['body']['error']
        self.assertEqual(err['code'], 'BudgetMissing')
        self.assertEqual(err['msg'], 'budget.senders key "agents/a" (sender %s): max_calls 0 reached in this window (day); not run' % ws)


if __name__ == '__main__':
    unittest.main()
