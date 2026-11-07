# Verify kernel finish records fake-brain costs and tolerates ledger write failures.
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest


PROTO = Path(__file__).resolve().parents[3]
KERNEL = PROTO / 'impls/aos-llm-kernel/bin/aos-llm-kernel'
FAKE = PROTO / 'lib/base/llm_fake/_entry'


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='aos-ledger-')
        self.addCleanup(self.temp.cleanup)
        self.stack = Path(self.temp.name)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}
        self.env.update(AOS_STACK=str(self.stack), AOS_DAEMON=str(self.stack))
        for folder in ('requests/new', 'requests/cur', 'requests/tmp',
                       'procs_ctl_mailbox/new', 'procs_ctl_mailbox/tmp', 'procs_ctl_mailbox/cur'):
            (self.stack / folder).mkdir(parents=True)
        self.config = self.stack / 'kernel.json'
        self.config.write_text(json.dumps({'exec': str(FAKE.parent), 'endpoints': {'fake': {}},
                                          'endpoint': 'fake'}))
        result = subprocess.run([str(FAKE)], input=json.dumps({'endpoint': {}, 'request': {
            'messages': [{'role': 'user', 'content': 'ledger test'}]}}),
            capture_output=True, text=True, env=self.env, check=True)
        self.reply = json.loads(result.stdout)

    def prepare(self, name, reply, ran=True, code=0):
        folder = self.stack / 'requests/cur' / name
        folder.mkdir()
        (folder / 'reply.json').write_text(json.dumps(reply))
        if ran:
            (folder / 'proc.json').write_text(json.dumps({'endpoint': 'fake', 'sender': '/sender',
                'name': 'llm_' + name, 'mounted_at': time.time() - 1, 'retries': 0}))
            (folder / 'state.json').write_text(json.dumps({'phase': 'done', 'code': code}))
        return folder

    def run_kernel(self):
        result = subprocess.run([str(KERNEL), str(self.config)], env=self.env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def ledger(self):
        return [json.loads(line) for line in (self.stack / 'ledger.jsonl').read_text().splitlines()]

    def test_append_raw_usage_and_skip_unrun(self):
        self.prepare('first', self.reply)
        self.run_kernel()
        first = self.ledger()[0]
        self.assertEqual(set(first), {'id', 'endpoint', 'sender', 'model', 'mounted_at',
                                     'finished_at', 'elapsed_ms', 'usage', 'seen_at', 'code', 'child', 'switched'})
        self.assertEqual((first['id'], first['endpoint'], first['sender'], first['model']),
                         ('first', 'fake', '/sender', 'fake'))
        self.assertEqual(first['usage'], self.reply['usage'])
        self.assertIsNone(first['seen_at'])
        self.assertIsNone(first['code'])
        self.assertIsNone(first['child'])
        self.assertIs(first['switched'], False)
        self.assertGreaterEqual(first['elapsed_ms'], 1000)
        self.assertGreaterEqual(first['finished_at'], first['mounted_at'])
        raw = dict(self.reply, usage={'prompt_tokens': 2, 'completion_tokens': 3,
                                     'custom': {'nested': [1, 'kept']}})
        self.prepare('second', raw)
        self.prepare('not_run', self.reply, ran=False)
        self.run_kernel()
        self.assertEqual([row['id'] for row in self.ledger()], ['first', 'second'])
        self.assertEqual(self.ledger()[1]['usage'], raw['usage'])

    def test_missing_usage_counts_zero(self):
        reply = dict(self.reply)
        del reply['usage']
        self.prepare('missing', reply)
        self.run_kernel()
        self.assertIsNone(self.ledger()[0]['usage'])
        used = json.loads((self.stack / 'used.json').read_text())
        self.assertEqual((used['counter_calls'], used['counter_tokens']), (1, 0))

    def test_endpoint_failure_is_recorded(self):
        self.prepare('failed', self.reply, code=1)
        self.run_kernel()
        row = self.ledger()[0]
        self.assertEqual(row['id'], 'failed')
        self.assertEqual(row['code'], 'EndpointFailed')
        self.assertIsNone(row['usage'])
        self.assertIsNone(row['model'])

    def test_write_failure_warns_and_finishes(self):
        (self.stack / 'ledger.jsonl').mkdir()
        folder = self.prepare('blocked', self.reply)
        result = self.run_kernel()
        self.assertIn('aos-llm-kernel: warning: cannot append ledger:', result.stderr)
        self.assertFalse(folder.exists())
        self.assertEqual(json.loads((self.stack / 'used.json').read_text())['counter_calls'], 1)


if __name__ == '__main__':
    unittest.main()
