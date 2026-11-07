# Verify ask/recv full replies and unchanged defaults using local mailbox fixtures.
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest


BIN = Path(__file__).resolve().parents[1] / 'bin' / 'aos-llm'
FAKE = Path(__file__).resolve().parents[3] / 'lib' / 'base' / 'llm_fake' / '_entry'


class FullReply(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = subprocess.run(
            [sys.executable, str(FAKE)],
            input=json.dumps({'endpoint': {}, 'request': {
                'messages': [{'role': 'user', 'content': 'local reply'}]}}),
            capture_output=True, text=True, timeout=5, check=True)
        cls.reply_body = json.loads(result.stdout)
        cls.reply_body['extra'] = 'preserved'

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-llm-full-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ('AOS_DAEMON', 'AOS_LLM_KERNEL')}
        self.env['AOS_LLM_KERNEL'] = str(self.root)

    def mailbox(self, box):
        for part in ('new', 'cur', 'tmp'):
            (box / part).mkdir(parents=True, exist_ok=True)

    def reply(self, box, name, body):
        self.mailbox(box)
        letter = box / 'new' / 'reply-test'
        letter.mkdir()
        (letter / 'letter.json').write_text(json.dumps(
            {'in_reply_to': name, 'body': body}))

    def check_output(self, result, body, full):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(result.stdout.splitlines()), 1)
        self.assertEqual(json.loads(result.stdout), body if full else body['message'])

    def test_recv_outputs(self):
        for full in (False, True):
            for body in (self.reply_body, {'message': self.reply_body['message']}):
                with self.subTest(full=full, body=body):
                    box = self.root / 'replies'
                    self.reply(box, 'request-test', body)
                    args = [str(BIN), 'recv'] + (['--full'] if full else [])
                    result = subprocess.run(args + [str(box), 'request-test'],
                                            capture_output=True, text=True, env=self.env, timeout=5)
                    self.check_output(result, body, full)
                    missing = subprocess.run(args + [str(box), 'request-test'],
                                             capture_output=True, text=True, env=self.env, timeout=5)
                    self.assertEqual((missing.returncode, missing.stdout), (10, ''))

    def test_ask_outputs(self):
        for full in (False, True):
            with self.subTest(full=full):
                args = [str(BIN), 'ask'] + (['--full'] if full else [])
                with subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, text=True, env=self.env) as proc:
                    proc.stdin.write(json.dumps({'request': {'messages': []}}))
                    proc.stdin.close()
                    deadline = time.monotonic() + 5
                    request = None
                    while time.monotonic() < deadline:
                        letters = list((self.root / 'requests' / 'new').glob('*/letter.json'))
                        if letters:
                            request = letters[0]
                            break
                        time.sleep(0.01)
                    if request is None:
                        proc.kill()
                        self.fail('ask did not send a request')
                    envelope = json.loads(request.read_text())
                    box = (self.root / 'requests' / envelope['reply_to']).resolve()
                    self.reply(box, request.parent.name, self.reply_body)
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                        self.fail('ask did not consume the reply')
                    result = subprocess.CompletedProcess(args, proc.returncode,
                                                         proc.stdout.read(), proc.stderr.read())
                    self.check_output(result, self.reply_body, full)
                    # Leave the fixture mailbox clean for the next request.
                    request.unlink()
                    (request.parent / 'sender.flock').unlink()
                    request.parent.rmdir()

    def test_full_errors_stay_errors(self):
        box = self.root / 'errors'
        self.reply(box, 'request-test', {'error': {'code': 'EndpointFailed', 'msg': 'local failure'}})
        result = subprocess.run([str(BIN), 'recv', '--full', str(box), 'request-test'],
                                capture_output=True, text=True, env=self.env, timeout=5)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, '')
        self.assertIn('aos-llm: error: EndpointFailed local failure', result.stderr)

    def test_help(self):
        for command in ('ask', 'recv'):
            result = subprocess.run([str(BIN), command, '--help'], capture_output=True,
                                    text=True, env=self.env, timeout=5)
            self.assertEqual(result.returncode, 0)
            self.assertIn('--full', result.stdout)


if __name__ == '__main__':
    unittest.main()
