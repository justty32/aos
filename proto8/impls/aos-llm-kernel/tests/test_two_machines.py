# Check in-flight brain calls never pin this machine's absolute endpoint path (two-machines): mount letters and remounts.
import json
import os
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


if __name__ == '__main__':
    unittest.main()
