# Check a bad used.json is kept aside and recounted from ledger.jsonl (not zeroed), and UsedBad stays when there is no ledger (11-19 audit P5).
import json
import subprocess
import time
import unittest

import test_ledger


class UsedRecount(unittest.TestCase):
    setUp = test_ledger.LedgerTests.setUp

    def ledger_rows(self, rows, extra=b''):
        text = b''.join(json.dumps(r).encode() + b'\n' for r in rows) + extra
        (self.stack / 'ledger.jsonl').write_bytes(text)

    def row(self, name, tokens, finished=None, endpoint='fake', sender=None):
        return {'id': name, 'endpoint': endpoint, 'sender': sender or str(self.stack / 'agents/a'),
                'usage': {'total_tokens': tokens}, 'finished_at': time.time() if finished is None else finished}

    def letter(self):
        box = self.stack / 'replies'
        for part in ('new', 'tmp', 'cur'):
            (box / part).mkdir(parents=True, exist_ok=True)
        folder = self.stack / 'requests/new/L1'
        folder.mkdir()
        (folder / 'letter.json').write_text(json.dumps({'sender': str(self.stack / 'agents/a'),
            'sent_at': '2026-11-19T00:00:00+08:00', 'reply_to': str(box), 'body': {'request': {'messages': []}}}))
        return box

    def run_kernel(self, cfg=None):
        self.config.write_text(json.dumps(dict({'exec': str(test_ledger.FAKE.parent), 'endpoints': {'fake': {}},
                                                'endpoint': 'fake'}, **(cfg or {}))))
        return subprocess.run([str(test_ledger.KERNEL), str(self.config)], env=self.env,
                              capture_output=True, text=True, timeout=10)

    def used(self):
        return json.loads((self.stack / 'used.json').read_text())

    def test_recounts_from_ledger_and_keeps_the_bad_file(self):
        (self.stack / 'used.json').write_text('{oops')
        self.ledger_rows([self.row('a', 5), self.row('b', 7), self.row('a', 5),        # a twice: counted once
                          self.row('old', 100, finished=time.time() - 3 * 86400)],    # outside this day window
                         extra=b'{"id": "half\n')                                      # a half line: skipped
        p = self.run_kernel()
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('kernel_llm: warning: %s was bad' % (self.stack / 'used.json'), p.stderr)
        self.assertIn('recounted from ledger.jsonl: 2 calls, 12 tokens in this window (1 bad ledger lines skipped', p.stderr)
        used = self.used()
        self.assertEqual((used['counter_calls'], used['counter_tokens']), (2, 12))
        self.assertEqual((used['counter_all_calls'], used['counter_all_tokens']), (3, 112))
        self.assertEqual(used['packs'], {'fake': {'counter_calls': 2, 'counter_tokens': 12}})
        self.assertEqual(used['senders'], {'agents/a': {'counter_calls': 2, 'counter_tokens': 12}})
        info = used['recounted']
        self.assertEqual((info['from'], info['ledger_lines_skipped']), ('ledger.jsonl', 1))
        self.assertTrue(info['bad_file'].startswith('used.json.bad-'))
        self.assertEqual((self.stack / info['bad_file']).read_text(), '{oops')
        p = self.run_kernel()                          # next round: no second recount, no warning
        self.assertEqual((p.returncode, p.stderr), (0, ''))
        self.assertEqual(self.used()['recounted'], info)

    def test_recounted_budget_still_refuses(self):
        (self.stack / 'used.json').write_text('[]')
        self.ledger_rows([self.row('a', 1), self.row('b', 1)])
        box = self.letter()
        p = self.run_kernel({'budget': {'max_calls': 2}})
        self.assertEqual(p.returncode, 0, p.stderr)
        (reply,) = [json.loads(path.read_text()) for path in (box / 'new').glob('*/letter.json')]
        self.assertEqual(reply['body']['error']['code'], 'BudgetMissing')   # not zeroed: the two calls still count

    def test_counts_go_on_after_recount(self):
        (self.stack / 'used.json').write_text('{"window": 3}')
        self.ledger_rows([self.row('a', 4)])
        self.prepare('first', self.reply)
        p = self.run_kernel()
        self.assertEqual(p.returncode, 0, p.stderr)
        used = self.used()
        self.assertEqual(used['counter_calls'], 2)
        self.assertIn('recounted', used)

    def test_no_ledger_is_still_used_bad(self):
        (self.stack / 'used.json').write_text('{oops')
        p = self.run_kernel()
        self.assertEqual(p.returncode, 1)
        self.assertIn('kernel_llm: error: UsedBad', p.stderr)
        self.assertIn('ledger.jsonl is missing or unreadable, so the usage cannot be recounted', p.stderr)
        self.assertEqual((self.stack / 'used.json').read_text(), '{oops')   # left as it was
        self.assertEqual(sorted(x.name for x in self.stack.glob('used.json*')), ['used.json'])

    prepare = test_ledger.LedgerTests.prepare


if __name__ == '__main__':
    unittest.main()
