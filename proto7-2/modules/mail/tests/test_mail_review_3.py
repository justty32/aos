from _mailcase import *


class Tests(ReviewCase):
    def test_round2_team_atomic_publish(self):
        args = ('team', 'dev', 'lead', 'bob')
        self.run_cli(*args, rc=-signal.SIGKILL,
                     env={'AOS7_TEST_CRASH': 'mail.team_before_publish'})
        self.assertIsNone(mail.team_of(self.root, 'bob'), '中斷時 team_of 不得看到半份名冊')
        self.assertFalse((self.root / 'teams/dev').exists())
        stale = list((self.root / '.staging').glob('mail-team-*'))
        self.assertEqual(len(stale), 1)
        self.assertEqual((stale[0] / 'members').read_text(), 'lead\nbob\n')
        self.assertTrue((stale[0] / 'inbox').is_dir())
        self.run_cli(*args)
        self.assertEqual(mail.team_of(self.root, 'bob'), ('dev', 'lead'))
        self.assertEqual(list((self.root / '.staging').iterdir()), [])
        self.run_cli(*args)  # 完全相同為冪等成功。
        self.run_cli('team', 'dev', 'lead', 'carol', rc=1)  # 做不到：同名不同內容
        self.assertEqual((self.root / 'teams/dev/members').read_text(), 'lead\nbob\n')


    def test_round2_team_request_rejected_first(self):
        self.run_cli('team', 'dev', 'lead', 'bob')
        message = 'aos7-mail: 團隊信箱只收廣播（PROGRESS／終局）。要人辦事請直接寄給成員'
        for sender in ('bob', 'outsider'):
            p = self.run_cli('send', sender, 'team:dev', 'REQUEST', '請辦事', rc=2)
            self.assertIn(message, p.stderr)
        self.assertEqual(mail.letters(mail.inbox(self.root, 'team:dev')), [])
        self.assertFalse((self.root / 'teams/dev/events').exists())
        for status in sorted(mail.STATUSES - {'REQUEST'}):
            self.run_cli('send', 'bob', 'team:dev', status, '廣播')


    def test_newbie_help_and_defaults(self):
        exe = str(Path(MODULES) / 'mail/aos7-mail')
        env = {k: v for k, v in os.environ.items() if k != 'AOS_MAIL_ROOT'}
        for args, rc in ((['--help'], 0), (['send', '--help'], 0), (['help', 'done'], 0), ([], 2)):
            p = subprocess.run([exe, *args], capture_output=True, text=True, timeout=30, env=env)
            self.assertEqual(p.returncode, rc, p.stderr)
            self.assertIn('aos7-mail', p.stdout + p.stderr, '沒設 root 也要看得到用法')
        self.assertIn('沒有 sned', self.run_cli('sned', 'x', rc=2).stderr)
        sent = json.loads(self.run_cli('send', 'alice', 'bob', '請檢查').stdout)
        self.assertTrue(sent['sent'].endswith('-alice-REQUEST.md'), '省略 STATUS 預設 REQUEST')
        self.run_cli('read', 'bob')
        self.assertIn('結論', self.run_cli('done', 'bob', '1', rc=2).stderr)
        self.assertIn('已回 DONE 給 alice', self.run_cli('done', 'bob', '1', '查完了').stdout)
        self.run_cli('audit')


    def test_human_numbers_quiet_and_new_mailbox(self):
        p = self.run_cli('send', 'alice', 'bob', 'REQUEST', '第一封')
        first = json.loads(p.stdout)
        self.assertEqual(p.stderr.strip(), 'aos7-mail: 注意：bob 是新信箱（第一次收信）。確認名字沒打錯；沒錯就不用管')
        out = self.run_cli('read', 'bob').stdout
        self.assertEqual(out, '1  ' + Path(first['sent']).name + '  第一封\n')
        self.assertEqual(self.run_cli('read', 'bob', '--quiet').stdout, '')
        self.assertNotIn('等回信  ', self.run_cli('read', 'alice').stdout)
        self.assertIn('等回信  ', self.run_cli('audit', 'alice', rc=1).stdout)
        self.assertEqual(self.run_cli('read', 'alice', '--quiet').stdout, '')
        second = self.send(title='另一封')
        rows = json.loads(self.run_cli('read', 'bob', '--quiet', '--json').stdout)
        pending = sorted([Path(first['sent']), Path(second['sent'])])
        self.assertEqual(rows[0]['number'], pending.index(Path(second['sent'])) + 1)
        self.assertEqual(self.run_cli('read', 'bob', '--quiet', '--json').stdout, '')
        mail.done(self.root, 'bob', second['id'])
        self.run_cli('read', 'bob')
        self.assertIn('已回 DONE 給 alice', self.run_cli('done', 'bob', '1', 'DONE', '辦好了').stdout)
        self.run_cli('read', 'alice')
        self.assertIn('已歸檔 ', self.run_cli('done', 'alice', '1').stdout)
        self.assertEqual(self.run_cli('read', 'alice').stdout, '（沒有新信）\n')
        self.assertEqual(self.run_cli('read', 'alice', '--quiet').stdout, '')


