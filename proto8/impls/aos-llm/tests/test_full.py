# Verify ask/recv full replies, request names, error bodies, and unchanged default output.
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest


BIN = Path(__file__).resolve().parents[1] / 'bin' / 'aos-llm'
FAKE = Path(__file__).resolve().parents[3] / 'lib/base/llm_fake/_entry'


class FullReply(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = subprocess.run(
            [sys.executable, str(FAKE)],
            input=json.dumps({'endpoint': {}, 'request': {
                'messages': [{'role': 'user', 'content': 'local reply'}]}}),
            capture_output=True, text=True, timeout=5, check=True)
        cls.reply_body = dict(json.loads(result.stdout), extra='preserved')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-llm-full-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}
        self.env['AOS_LLM_KERNEL'] = str(self.root)
        (self.root / 'state.json').write_text(json.dumps({'phase': 'running', 'pid': os.getpid()}))

    def reply(self, box, name, body):
        for part in ('new', 'cur', 'tmp'):
            (box / part).mkdir(parents=True, exist_ok=True)
        letter = box / 'new/reply-test'
        letter.mkdir()
        (letter / 'letter.json').write_text(json.dumps({'in_reply_to': name, 'body': body}))

    def ask(self, body, full):
        args = [str(BIN), 'ask'] + (['--full'] if full else [])
        with subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True, env=self.env) as proc:
            try:
                proc.stdin.write(json.dumps({'request': {'messages': []}}))
                proc.stdin.close()
                request = None
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    letters = list((self.root / 'requests/new').glob('*/letter.json'))
                    if letters:
                        request = letters[0]
                        break
                    time.sleep(0.01)
                self.assertIsNotNone(request, 'ask did not send a request')
                envelope = json.loads(request.read_text())
                box = (self.root / 'requests' / envelope['reply_to']).resolve()
                self.reply(box, request.parent.name, body)
                proc.wait(timeout=5)
                result = subprocess.CompletedProcess(args, proc.returncode,
                                                     proc.stdout.read(), proc.stderr.read())
                name = request.parent.name
                shutil.rmtree(request.parent)
                return result, name
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=5)

    def check_output(self, result, body, full, name):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(result.stdout.splitlines()), 1)
        self.assertEqual(json.loads(result.stdout), dict(body, letter=name) if full else body['message'])
        self.assertEqual(result.stderr, '')

    def test_recv_outputs(self):
        for full in (False, True):
            for body in (self.reply_body, {'message': self.reply_body['message']},
                         dict(self.reply_body, letter='endpoint-cannot-override-request-name')):
                with self.subTest(full=full, body=body):
                    box = self.root / 'replies'
                    self.reply(box, 'request-test', body)
                    args = [str(BIN), 'recv'] + (['--full'] if full else [])
                    result = subprocess.run(args + [str(box), 'request-test'],
                                            capture_output=True, text=True, env=self.env, timeout=5)
                    self.check_output(result, body, full, 'request-test')
                    missing = subprocess.run(args + [str(box), 'request-test'],
                                             capture_output=True, text=True, env=self.env, timeout=5)
                    self.assertEqual((missing.returncode, missing.stdout, missing.stderr), (10, '', ''))

    def test_ask_outputs(self):
        for full in (False, True):
            with self.subTest(full=full):
                result, name = self.ask(self.reply_body, full)
                self.check_output(result, self.reply_body, full, name)

    def check_error(self, result, body, full):
        self.assertEqual(result.returncode, 1)
        if full:
            self.assertEqual(len(result.stdout.splitlines()), 1)
            self.assertEqual(json.loads(result.stdout), body)
        else:
            self.assertEqual(result.stdout, '')
        self.assertEqual(result.stderr, 'aos-llm: error: X local failure\n')

    def test_recv_error_body_and_default(self):
        body = {'error': {'code': 'X', 'msg': 'local failure', 'details': {'retry': False}}}
        for full in (False, True):
            with self.subTest(full=full):
                box = self.root / 'errors'
                self.reply(box, 'request-test', body)
                args = [str(BIN), 'recv'] + (['--full'] if full else [])
                result = subprocess.run(args + [str(box), 'request-test'],
                                        capture_output=True, text=True, env=self.env, timeout=5)
                self.check_error(result, body, full)
                self.assertFalse(list((box / 'new').iterdir()))
                self.assertFalse(list((box / 'cur').iterdir()))

    def test_ask_error_body_and_default(self):
        body = {'error': {'code': 'X', 'msg': 'local failure', 'details': {'retry': False}}}
        for full in (False, True):
            with self.subTest(full=full):
                result, _ = self.ask(body, full)
                self.check_error(result, body, full)

    def test_full_local_errors_do_not_print_reply_body(self):
        result = subprocess.run([str(BIN), 'ask', '--full'], input='{}', capture_output=True,
                                text=True, env=self.env, timeout=5)
        self.assertEqual((result.returncode, result.stdout), (1, ''))
        self.assertIn('aos-llm: error: RequestBad', result.stderr)

    def test_help(self):
        for command in ('ask', 'recv'):
            result = subprocess.run([str(BIN), command, '--help'], capture_output=True,
                                    text=True, env=self.env, timeout=5)
            self.assertEqual(result.returncode, 0)
            for word in ('--full', 'letter', 'error body', 'stderr', 'exit code'):
                self.assertIn(word, result.stdout)


if __name__ == '__main__':
    unittest.main()
