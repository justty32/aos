# 驗證 listen --mailbox：等一封信的回答時，對方改用信回（落在叫的人信箱、in_reply_to 是這封，例 BLOCKED）也結束等待（11-24 晚 home-listen-1124，narr-amber 回報②）。
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest

PROTO = Path(__file__).resolve().parents[4]
BIN = PROTO / 'bin/aos-agent'
SIG = '000000000001.q'


class ListenMailbox(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='listen-mailbox-')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.daemon = self.root / 'daemon'
        self.stack = self.daemon / 'procs/kid'
        for name in ('queue/new', 'queue/cur', 'queue/tmp'):
            (self.stack / name).mkdir(parents=True)
        (self.stack / 'state.json').write_text('{"phase":"running"}')
        (self.stack / 'history.jsonl').write_text(json.dumps({'role': 'user', 'content': 'hi', 'aos': {'letter': SIG}}) + '\n')
        (self.stack / 'letters.json').write_text(json.dumps({'pending': [SIG], 'dropped': []}))
        (self.daemon / 'procs_state.json').write_text(json.dumps({'procs': {'kid': {'phase': 'running', 'stack': 'procs/kid'}}}))
        self.box = self.root / 'me/mailbox'
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}

    def mail(self, in_reply_to, name='01795000000000000001.1.1'):
        d = self.box / 'new' / name
        d.mkdir(parents=True)
        (d / 'letter.json').write_text(json.dumps({'sender': str(self.stack), 'sent_at': '2026-11-24T13:00:00Z', 'reply_to': '../kid/mailbox',
                                                   'in_reply_to': in_reply_to,
                                                   'body': {'from': 'kid', 'status': 'BLOCKED', 'title': 'need the key', 'what': 'no key in ws'}}))
        return d

    def listen(self, *extra, timeout='20'):
        start = time.monotonic()
        r = subprocess.run([sys.executable, str(BIN), '-d', str(self.daemon), 'listen', '-t', 'kid', *extra, '--timeout-s', timeout],
                           env=self.env, capture_output=True, text=True, timeout=40)
        return r, time.monotonic() - start

    def test_a_letter_answering_it_ends_the_wait(self):
        d = self.mail(SIG)
        r, took = self.listen('--letter', SIG, '--mailbox', str(self.box))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertLess(took, 10)
        first, rest = r.stdout.split('\n', 1)
        self.assertTrue(first.startswith('[aos] listen: kid answered %s with a letter in %s, not with a reply: BLOCKED "need the key"' % (SIG, self.box)), first)
        self.assertIn('01795000000000000001.1.1', first)
        self.assertEqual(rest, 'no key in ws\n')
        self.assertTrue((d / 'letter.json').exists())          # 信留在信箱

    def test_a_letter_arriving_later_ends_the_wait(self):
        threading.Timer(1.5, self.mail, (SIG,)).start()         # 信箱還沒建也照看
        r, took = self.listen('--letter', SIG, '--mailbox', str(self.box))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertGreater(took, 1.4)
        self.assertLess(took, 10)
        self.assertIn('BLOCKED', r.stdout)

    def test_without_letter_flag_it_waits_on_the_pending_letter(self):
        self.mail(SIG)
        r, _ = self.listen('--mailbox', str(self.box))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('kid answered %s with a letter' % SIG, r.stdout)

    def test_other_letters_do_not_count(self):
        self.mail('000000000009.q')
        r, _ = self.listen('--letter', SIG, '--mailbox', str(self.box), timeout='2')
        self.assertEqual(r.returncode, 1)
        self.assertIn('error: AnswerMissing', r.stderr)

    def test_no_mailbox_flag_keeps_the_old_wait(self):
        self.mail(SIG)
        r, _ = self.listen('--letter', SIG, timeout='2')
        self.assertEqual(r.returncode, 1)
        self.assertIn('error: AnswerMissing', r.stderr)

    def test_mailbox_is_only_for_waiting(self):
        r = subprocess.run([sys.executable, str(BIN), '-d', str(self.daemon), 'listen', '-t', 'kid', '--last', '1', '--mailbox', str(self.box)],
                           env=self.env, capture_output=True, text=True, timeout=40)
        self.assertEqual(r.returncode, 1)
        self.assertIn('ArgumentsBad --mailbox is only for waiting on a letter', r.stderr)


if __name__ == '__main__':
    unittest.main()
