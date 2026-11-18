# Verify kernel retry flags, transparent error fields, and non-retryable refusals.
import json
import sys
from types import SimpleNamespace
import unittest

import test_hooks
import test_ledger
import test_nesting

for folder in ('py', 'py/tools/aos/kernel', 'py/tools/aos/kernel_llm'):
    sys.path.insert(0, str(test_ledger.PROTO / folder))
import llm_rules  # noqa: E402


class RetryFlags(unittest.TestCase):
    setUp = test_ledger.LedgerTests.setUp
    prepare = test_ledger.LedgerTests.prepare
    run_kernel = test_ledger.LedgerTests.run_kernel
    ledger = test_ledger.LedgerTests.ledger
    reply_body = test_nesting.NestingFixtures.reply_body
    configure = test_hooks.HookTests.configure
    send = test_hooks.HookTests.send
    replies = test_hooks.HookTests.replies

    def test_structured_error_fields_and_types_are_forwarded_and_recorded(self):
        for index, retry in enumerate((True, False, 'true', 1, None)):
            with self.subTest(retry=retry):
                name = 'structured-' + str(index)
                error = {'code': 'EndpointFailed', 'msg': 'HTTP 503: unavailable',
                         'retry': retry, 'status': 503, 'retry_after_s': 20.5, 'tries': 1}
                body = {'error': error}
                self.prepare(name, body, code=1)
                received = self.reply_body(name)
                self.assertEqual(received, body)
                for key, value in error.items():
                    self.assertIs(type(received['error'][key]), type(value))
                row = self.ledger()[-1]
                self.assertEqual((row['id'], row['code']), (name, 'EndpointFailed'))

    def test_structured_error_without_retry_is_not_augmented(self):
        body = {'error': {'code': 'RequestBad', 'msg': 'bad request', 'status': 400}}
        self.prepare('unmarked', body, code=1)
        self.assertEqual(self.reply_body('unmarked'), body)

    def test_plain_failure_is_retryable(self):
        folder = self.prepare('plain', {}, code=1)
        (folder / 'reply.json').write_text('plain failure\nignored second line')
        self.assertEqual(self.reply_body('plain'), {'error': {
            'code': 'EndpointFailed', 'msg': 'endpoint function exited with code 1: plain failure',
            'retry': True}})
        self.assertEqual(self.ledger()[-1]['code'], 'EndpointFailed')

    def test_unreadable_success_is_retryable(self):
        folder = self.prepare('bad-success', {})
        (folder / 'reply.json').write_text('not JSON')
        error = self.reply_body('bad-success')['error']
        self.assertEqual(error['code'], 'ReplyBad')
        self.assertIs(error['retry'], True)
        self.assertEqual(self.ledger()[-1]['code'], 'ReplyBad')

    def test_runner_environment_failures_are_retryable(self):
        ctx = SimpleNamespace(cfg={'timeout_ms': 42})
        cases = (
            ({'kind': 'launch', 'msg': 'daemon rejected the call'}, 'LaunchFailed'),
            ({'kind': 'twice'}, 'EndpointFailed'),
            ({'kind': 'stopped', 'name': 'llm_held', 'seconds': 300}, 'EndpointFailed'),
            ({'kind': 'exit', 'code': 143, 'timed_out': True}, 'EndpointFailed'),
        )
        for index, (result, code) in enumerate(cases):
            with self.subTest(result=result):
                folder = self.prepare('runner-' + str(index), {'error': {'code': 'X', 'msg': 'y'}})
                error = llm_rules.outcome(ctx, 'runner', str(folder), result)['error']
                self.assertEqual(error['code'], code)
                self.assertIs(error['retry'], True)

    def test_write_failure_has_no_retry_flag(self):
        reply = llm_rules.outcome(None, 'write', str(self.stack),
                                  {'kind': 'write', 'msg': 'cannot write result'})
        self.assertEqual(reply, {'error': {'code': 'WriteFailed', 'msg': 'cannot write result'}})

    def test_success_is_not_augmented(self):
        self.prepare('success', self.reply)
        self.assertEqual(self.reply_body('success'), self.reply)

    def test_request_endpoint_deadline_and_budget_refusals_have_no_retry_flag(self):
        base = json.loads(self.config.read_text())
        cases = (
            ('RequestBad', {}, {'request': {'messages': 'bad'}}),
            ('EndpointUnknown', {}, {'request': {'messages': []}, 'endpoint': 'missing'}),
            ('DeadlineBad', {}, {'request': {'messages': []},
                                 'priority': {'deadline': '2000-01-01T00:00:00+00:00'}}),
            ('BudgetMissing', {'budget': {'max_calls': 0}}, {'request': {'messages': []}}),
        )
        box = self.stack / 'replies'
        for part in ('new', 'tmp', 'cur'):
            (box / part).mkdir(parents=True, exist_ok=True)
        for code, config, body in cases:
            with self.subTest(code=code):
                self.config.write_text(json.dumps(dict(base, **config)))
                folder = self.stack / 'requests/new' / code
                folder.mkdir()
                (folder / 'letter.json').write_text(json.dumps({'reply_to': str(box), 'body': body}))
                self.run_kernel()
                received = next(json.loads(path.read_text())['body'] for path in
                                (box / 'new').glob('*/letter.json')
                                if json.loads(path.read_text())['in_reply_to'] == code)
                self.assertEqual(received['error']['code'], code)
                self.assertNotIn('retry', received['error'])

    def test_hook_rejection_has_no_retry_flag(self):
        self.configure('before_verdict', test_hooks.BEFORE_VERDICT)
        self.send('blocked', 'block me')
        self.run_kernel()
        error = self.replies()['blocked']['error']
        self.assertEqual(error['code'], 'HookRejected')
        self.assertNotIn('retry', error)


if __name__ == '__main__':
    unittest.main()
