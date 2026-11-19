# Check that a bad procs letter with reply_to gets {"applied": false, "error": {"code": "BodyBad", ...}} (11-12), the rest stay silent, and an unclaimable letter is skipped (11-19).
import json
import os
import subprocess
import time
import unittest

from support import ENV, Fixture, dc, read, until, write


class BadLetter(unittest.TestCase):
    def fixture(self, name):
        f = Fixture(name).start()
        self.addCleanup(f.close)
        return f

    def box(self, f, name):
        box = f.root / name
        subprocess.run(['aos-post', 'init', str(box)], env=ENV, check=True)
        return box

    def send(self, f, body, reply_to=None):
        args = ['aos-post', 'send'] + (['--reply-to', str(reply_to)] if reply_to else []) + [str(f.stack / 'procs_requests')]
        return subprocess.run(args, input=json.dumps(body), env=ENV, capture_output=True, text=True, check=True).stdout.strip()

    def replies(self, box):
        return [read(p / 'letter.json') for p in sorted((box / 'new').iterdir())]

    def warned(self, f, letter):
        return until(lambda: letter in (read(f.stack / 'state_flux.json', {}).get('mailbox_warning') or ''))

    def test_bad_bodies_get_refusal(self):
        f = self.fixture('bad_body_reply')
        box = self.box(f, 'replies')
        cases = {'array': ([], 'body must be an object'),
                 'ping': ({'ping': False}, 'ping must be true'),
                 'removed': ({'procs_removed': 'job'}, 'procs_removed')}
        for case, (body, why) in cases.items():
            with self.subTest(case=case):
                letter = self.send(f, body, box)
                got = until(lambda: [r for r in self.replies(box) if r['in_reply_to'] == letter])
                self.assertEqual(got[0]['body']['applied'], False)
                self.assertEqual(got[0]['body']['error']['code'], 'BodyBad')
                self.assertIn(why, got[0]['body']['error']['msg'])
                self.warned(f, letter)       # mailbox_warning 照舊記
        good = self.send(f, {'ping': True}, box)
        got = until(lambda: [r for r in self.replies(box) if r['in_reply_to'] == good])
        self.assertEqual(got[0]['body'], {'applied': True})

    def test_daemon_ctl_reports_refusal(self):
        f = self.fixture('bad_ctl')
        p = f.ctl('add', '--name', 'a/b', str(f.body('script', 'stop')), ok=1)   # 名字帶 /：命令列不擋、daemon 拒
        self.assertIn('aos-daemon-ctl: error: BodyBad the daemon refused letter', p.stderr)
        self.assertEqual(f.rows(), {})

    def test_no_reply_to_and_bad_envelope_stay_silent(self):
        f = self.fixture('bad_silent')
        box = self.box(f, 'replies')
        letter = self.send(f, [])               # 沒 reply_to：沒地方回
        self.warned(f, letter)
        broken = f.stack / 'procs_requests' / 'new' / 'broken'   # 信封壞（沒有 body）：讀不到 reply_to，回不了
        broken.mkdir()
        write(broken / 'letter.json', {'sender': 'x', 'sent_at': '2026-11-12T00:00:00Z', 'reply_to': str(box)})
        self.warned(f, 'broken')
        time.sleep(.3)
        self.assertEqual(self.replies(box), [])
        self.assertIsNone(f.proc.poll())        # daemon 照跑
        self.assertTrue(dc.ping(str(f.stack), 3, direct=True)['applied'])

    @unittest.skipIf(os.geteuid() == 0, 'root renames a read-only folder anyway')
    def test_unclaimable_letter_is_skipped(self):
        # 11-19 基底體檢 P2：認領不了的一封（夾本身不可寫，rename 到 cur/ 被拒）不擋後面的信，原因進 mailbox_warning
        f = self.fixture('bad_unclaimable')
        box = self.box(f, 'replies')
        stuck = f.stack / 'procs_requests' / 'new' / '000000000001.stuck'   # 有序名：排在所有信前面
        stuck.mkdir()
        write(stuck / 'letter.json', {'sender': 'x', 'sent_at': '2026-11-19T00:00:00Z', 'body': {'ping': True}})
        stuck.chmod(0o555)
        self.addCleanup(stuck.chmod, 0o755)
        good = self.send(f, {'ping': True}, box)
        got = until(lambda: [r for r in self.replies(box) if r['in_reply_to'] == good])
        self.assertEqual(got[0]['body'], {'applied': True})
        self.assertTrue(until(lambda: 'cannot take letter 000000000001.stuck, skipped: WriteFailed' in
                              (read(f.stack / 'state_flux.json', {}).get('mailbox_warning') or '')))
        f.ctl('add', '--name', 'job', str(f.body('script', 'stop')))   # add 也照套
        self.assertIn('job', f.rows())
        self.assertTrue(stuck.is_dir())          # 那封留在 new/，每圈再試
        self.assertIsNone(f.proc.poll())


if __name__ == '__main__':
    unittest.main()
