"""ER-mail：可選提醒、自身鎖、單次 ack 與統一錯誤路徑。"""
from _mailcase import *


class Tests(MailCase):
    def test_request_events_opt_in(self):
        with patch.object(mail, 'publish', wraps=mail.publish) as pub:
            self.send()
            self.assertFalse((self.root / 'bob/events').exists())
            # 用 in-process send 另外驗證完全不呼叫 publish。
            mail.send(self.root, 'alice', 'carol', 'REQUEST', '無提醒')
            pub.assert_not_called()
            events = self.root / 'bob/events'
            events.mkdir()
            sent = mail.send(self.root, 'alice', 'bob', 'REQUEST', '有提醒')
            self.assertEqual(pub.call_count, 1)
            self.assertEqual(read(events, 'must')['records'][0]['payload']['id'], sent['id'])

    def test_read_only_own_lock(self):
        self.send()
        # 另一個程序拿 alice 的 delivery 鎖，read bob 不得等它。
        lock = self.box('alice') / '.delivery.lock'
        code = '''import fcntl, sys
with open(sys.argv[1], 'a') as f:
    fcntl.flock(f, fcntl.LOCK_EX)
    print('locked', flush=True)
    sys.stdin.read()
'''
        p = subprocess.Popen([sys.executable, '-B', '-c', code, str(lock)],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        def stop():
            p.communicate('', timeout=5)
        self.addCleanup(stop)
        self.assertEqual(p.stdout.readline().strip(), 'locked')
        result = subprocess.run([str(MAIL / 'aos7-mail'), '--root', str(self.root), 'read', 'bob'],
                                capture_output=True, text=True, timeout=3)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('請確認完整信件', result.stdout)

    def test_ack_one_call_and_idle_zero(self):
        events = self.root / 'bob/events'
        events.mkdir(parents=True)
        sent = self.send()
        with patch.object(ackmod, 'event_ack', wraps=ackmod.event_ack) as confirm:
            mail.done(self.root, 'bob', sent['id'], 'DONE', '已完成')
            self.assertEqual(confirm.call_count, 1, 'done 有進展只確認一次')
            confirm.assert_called_once_with(events, 1)
            confirm.reset_mock()
            with mail.poll(self.root, 'bob'):
                pass
            confirm.assert_not_called()
        self.assertEqual(mail.load(self.box('bob') / '.acked'), 1)

    def test_ack_stops_at_unproven_gap_or_error(self):
        (self.root / 'bob/events').mkdir(parents=True)
        sent = self.send()
        mail.done(self.root, 'bob', sent['id'], 'DONE', '完成')
        marker = self.box('bob') / '.acked'
        marker.unlink()
        for result in (
            {'records': [], 'gaps': [{'kind': 'unknown'}], 'errors': []},
            {'records': [], 'gaps': [{'kind': 'retention', 'from': 1, 'to': 2}],
             'errors': [{'kind': 'bad_line'}]},
        ):
            with patch.object(ackmod, 'events_read', return_value=result), patch.object(ackmod, 'event_ack', return_value=0) as confirm:
                mail.ack(self.root, 'bob')
                # 讀不清只以原值 ack 一次（讓 events 復原），不得越過
                confirm.assert_called_once_with(self.root / 'bob/events', 0)
                self.assertEqual(mail.load(marker, 0), 0)

    def test_error_usage_format_and_help(self):
        for args in (('send',), ('read', '../bad'), ('sned',), ('--root',)):
            with self.subTest(args=args):
                p = self.cli(*args, rc=2)
                self.assertEqual(len(p.stderr.splitlines()), 1)
                self.assertTrue(p.stderr.startswith('aos7-mail: '))
                self.assertIn('。', p.stderr)
                self.assertIn('例：', p.stderr)
        self.assertEqual(self.cli('--help').stderr, '')

    def test_error_oserror_unknown(self):
        self.box('bob').mkdir(parents=True)
        for err in (PermissionError('不能寫\n第二行'), BlockingIOError('鎖忙')):
            with patch.object(mail.os, 'link', side_effect=err), patch('sys.stderr', io.StringIO()) as stderr:
                self.assertEqual(cli.main(['--root', str(self.root), 'send', 'alice', 'bob', '請確認']), 3)
                msg = stderr.getvalue()
                self.assertEqual(len(msg.splitlines()), 1)
                self.assertTrue(msg.startswith('aos7-mail: 不確定：'))
                self.assertIn('留著。read／done 照原樣再跑一次會接續', msg)
        sent = self.send()
        with patch.object(boxmod, 'letter', side_effect=OSError('讀檔失敗')), patch('sys.stderr', io.StringIO()) as stderr:
            self.assertEqual(cli.main(['--root', str(self.root), 'read', 'bob']), 3)
            self.assertTrue(Path(sent['sent']).exists())
            self.assertTrue(stderr.getvalue().startswith('aos7-mail: 不確定：'))
