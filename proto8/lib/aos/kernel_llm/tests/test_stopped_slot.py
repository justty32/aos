# Check a brain call someone stopped on the daemon frees its slot after STOPPED_GIVE_UP_S (設計-56).
import json
import time
import unittest

import test_ledger


class StoppedSlot(unittest.TestCase):
    setUp = test_ledger.LedgerTests.setUp
    run_kernel = test_ledger.LedgerTests.run_kernel

    def stopped_call(self, name):
        box = self.stack / 'replies'
        for part in ('new', 'tmp', 'cur'):
            (box / part).mkdir(parents=True, exist_ok=True)
        folder = self.stack / 'requests/cur' / name
        folder.mkdir()
        (folder / 'letter.json').write_text(json.dumps({'reply_to': str(box), 'body': {'request': {'messages': []}}}))
        (folder / 'request.json').write_text('{}')
        (folder / 'proc.json').write_text(json.dumps({'endpoint': 'fake', 'name': 'llm_' + name,
            'mounted_at': time.time() - 1, 'retries': 0, 'mount_letter': 'm'}))
        (folder / 'state.json').write_text('{"phase":"stopped","code":0}')   # 有人 stop：退了但沒跑完
        (self.stack / 'procs_state.json').write_text(json.dumps({'procs_requests': 'procs_requests', 'procs': {
            'llm_' + name: {'phase': 'stopped', 'pid': None, 'reason': None}}}))
        return folder, box

    def proc(self, folder):
        return json.loads((folder / 'proc.json').read_text())

    def replies(self, box):
        return [json.loads(p.read_text()) for p in (box / 'new').glob('*/letter.json')]

    def test_waits_then_gives_up(self):
        folder, box = self.stopped_call('held')
        self.run_kernel()
        seen = self.proc(folder)['stopped_seen_at']
        self.assertEqual(self.replies(box), [])
        self.run_kernel()
        self.assertEqual(self.proc(folder)['stopped_seen_at'], seen)   # 還在等：不重算
        p = self.proc(folder)
        p['stopped_seen_at'] = time.time() - 301
        (folder / 'proc.json').write_text(json.dumps(p))
        self.run_kernel()
        (reply,) = self.replies(box)
        self.assertEqual(reply['body']['error']['code'], 'EndpointFailed')
        self.assertIn('was stopped on the daemon', reply['body']['error']['msg'])
        removed = [json.loads(p.read_text())['body'] for p in (self.stack / 'procs_requests/new').glob('*/letter.json')]
        self.assertIn({'procs_removed': ['llm_held']}, removed)

    def test_restarted_call_resets_the_clock(self):
        folder, box = self.stopped_call('back')
        self.run_kernel()
        self.assertIn('stopped_seen_at', self.proc(folder))
        (self.stack / 'procs_state.json').write_text(json.dumps({'procs_requests': 'procs_requests', 'procs': {
            'llm_back': {'phase': 'running', 'pid': 1, 'reason': None}}}))
        (folder / 'state.json').write_text('{"phase":"running","code":null}')
        self.run_kernel()
        self.assertNotIn('stopped_seen_at', self.proc(folder))
        self.assertEqual(self.replies(box), [])


if __name__ == '__main__':
    unittest.main()
