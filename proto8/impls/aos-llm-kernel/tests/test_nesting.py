# Verify nested-kernel error boundaries, ledger fields, and remount invariants with prepared mailboxes.
import json
import time
import unittest

import test_ledger


class NestingFixtures(unittest.TestCase):
    setUp = test_ledger.LedgerTests.setUp
    prepare = test_ledger.LedgerTests.prepare
    run_kernel = test_ledger.LedgerTests.run_kernel
    ledger = test_ledger.LedgerTests.ledger

    def reply_body(self, name):
        box = self.stack / 'replies'
        for part in ('new', 'tmp', 'cur'):
            (box / part).mkdir(parents=True, exist_ok=True)
        folder = self.stack / 'requests/cur' / name
        (folder / 'letter.json').write_text(json.dumps({'reply_to': str(box)}))
        self.run_kernel()
        replies = [json.loads(p.read_text()) for p in (box / 'new').glob('*/letter.json')]
        return next(reply['body'] for reply in replies if reply['in_reply_to'] == name)

    def test_daemon_rejection_comes_from_state_flux_without_table(self):
        name = 'rejected'
        folder = self.prepare(name, {}, ran=False)
        (folder / 'proc.json').write_text(json.dumps({
            'endpoint': 'fake', 'name': 'llm_' + name,
            'mounted_at': time.time(), 'retries': 0, 'mount_letter': 'add-rejected'}))
        (self.stack / 'state_flux.json').write_text(json.dumps({
            'mailbox_warning': 'letter add-rejected rejected: bad launch'}))
        body = self.reply_body(name)
        self.assertEqual(body['error']['code'], 'LaunchFailed')
        self.assertIn('add-rejected', body['error']['msg'])

    def test_strict_error_shape(self):
        error = {'error': {'code': 'X', 'msg': 'y', 'details': {'kept': [1, 'two']}}}
        valid = json.dumps(error)
        cases = [
            (valid, 'X'),
            (valid + '\n', 'X'),
            (valid + '\r\n', 'X'),
            (json.dumps({'error': {'code': 'X', 'msg': 'escaped\nnewline'}}), 'X'),
            (json.dumps(dict(error, extra=True)), 'EndpointFailed'),
            ('{"error":{"code":2,"msg":"y"}}', 'EndpointFailed'),
            ('{"error":{"code":"X","msg":null}}', 'EndpointFailed'),
            ('{"error":"y"}', 'EndpointFailed'),
            (json.dumps([error]), 'EndpointFailed'),
            (json.dumps(error, indent=2), 'EndpointFailed'),
            (valid + '\n\n', 'EndpointFailed'),
            (valid + '\ntrailing', 'EndpointFailed'),
            (valid + valid, 'EndpointFailed'),
            ('plain failure\nignored second line', 'EndpointFailed'),
            ('', 'EndpointFailed'),
        ]
        for index, (stdout, code) in enumerate(cases):
            with self.subTest(stdout=stdout):
                name = 'shape-' + str(index)
                folder = self.prepare(name, {}, code=2)
                (folder / 'reply.json').write_text(stdout)
                (folder / 'stderr.txt').write_text('stderr fallback\nignored')
                body = self.reply_body(name)
                self.assertEqual(body['error']['code'], code)
                row = self.ledger()[-1]
                self.assertEqual(row['code'], code)
                self.assertIsNone(row['child'])
                self.assertIs(row['switched'], False)
                if code == 'X':
                    self.assertEqual(body, json.loads(stdout))
                elif stdout.startswith('plain'):
                    self.assertEqual(body['error']['msg'], 'endpoint function exited with code 2: plain failure')
                elif not stdout:
                    self.assertEqual(body['error']['msg'], 'endpoint function exited with code 2: stderr fallback')

    def test_zero_exit_error_is_reply_bad(self):
        self.prepare('zero-error', {'error': {'code': 'X', 'msg': 'y'}})
        body = self.reply_body('zero-error')
        self.assertEqual(body['error']['code'], 'ReplyBad')
        self.assertEqual(self.ledger()[0]['code'], 'ReplyBad')

    def test_timeout_precedes_transparent_error(self):
        cfg = json.loads(self.config.read_text())
        cfg['timeout_ms'] = 1
        self.config.write_text(json.dumps(cfg))
        for code in (143, 137):
            with self.subTest(code=code):
                name = 'timeout-' + str(code)
                self.prepare(name, {'error': {'code': 'X', 'msg': 'y'}}, code=code)
                body = self.reply_body(name)
                self.assertEqual(body, {'error': {'code': 'EndpointFailed',
                                                'msg': 'endpoint function timed out (1 ms)'}})
                self.assertEqual(self.ledger()[-1]['code'], 'EndpointFailed')

    def test_non_timeout_term_can_forward_valid_error(self):
        self.prepare('term', {'error': {'code': 'X', 'msg': 'y'}}, code=143)
        self.assertEqual(self.reply_body('term'), {'error': {'code': 'X', 'msg': 'y'}})

    def test_remount_preserves_first_request_and_seen_at(self):
        cfg = json.loads(self.config.read_text())
        cfg['timeout_ms'] = 1000
        self.config.write_text(json.dumps(cfg))
        for deferred in (False, True):
            with self.subTest(deferred=deferred):
                name = 'remount-' + str(deferred)
                folder = self.prepare(name, {}, code=143)
                proc = json.loads((folder / 'proc.json').read_text())
                seen_at = time.time() - 10
                proc.update(exec=str(test_ledger.FAKE.parent), seen_at=seen_at)
                if deferred:
                    proc.update(remount=True, retries=1)
                (folder / 'proc.json').write_text(json.dumps(proc))
                (folder / 'state.json').write_text('{"phase":"running","code":null}')
                request = '{"endpoint":{},"request":{"messages":[]},"priority":{"level":-7.5,"deadline":1.0}}\n'
                (folder / 'request.json').write_text(request)
                self.run_kernel()
                after = json.loads((folder / 'proc.json').read_text())
                self.assertEqual(after['seen_at'], seen_at)
                self.assertEqual(after['retries'], 1)
                self.assertGreater(after['mounted_at'], proc['mounted_at'])
                self.assertEqual((folder / 'request.json').read_text(), request)
                (folder / 'state.json').write_text('{"phase":"done","code":0}')
                (folder / 'reply.json').write_text(json.dumps(self.reply))
                self.run_kernel()
                self.assertEqual(self.ledger()[-1]['seen_at'], seen_at)

    def test_aging_does_not_change_declared_level(self):
        name = 'aged'
        folder = self.stack / 'requests/new' / name
        folder.mkdir()
        (folder / 'letter.json').write_text(json.dumps({'body': {
            'priority': 'low', 'request': {'messages': []}}}))
        seen_ms = int(time.time() * 1000) - 60000
        (self.stack / 'queue.json').write_text(json.dumps({'counter_runs': 1, 'seen_at_ms': {name: seen_ms}}))
        self.run_kernel()
        folder = self.stack / 'requests/cur' / name
        proc = json.loads((folder / 'proc.json').read_text())
        request = json.loads((folder / 'request.json').read_text())
        self.assertEqual(proc['seen_at'], seen_ms / 1000)
        self.assertEqual(request['priority'], {'level': 'low'})
        self.assertNotIn(name, json.loads((self.stack / 'queue.json').read_text())['seen_at_ms'])


if __name__ == '__main__':
    unittest.main()
