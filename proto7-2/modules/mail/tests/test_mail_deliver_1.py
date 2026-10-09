from _mailcase import *


class Tests(MailCase):
    def test_parallel_delivery(self):
        # 固定所有子程序的牆鐘：保證同秒撞名，不依賴机器快慢。
        code = '''import sys, datetime
sys.path.insert(0, sys.argv[1])
import aos7_mail as m
class Fixed(datetime.datetime):
    @classmethod
    def now(cls): return cls(2026, 10, 9, 12, 0, 0)
m.datetime.datetime = Fixed
for n in range(20):
    m.send(sys.argv[2], sys.argv[3], 'bob', 'PROGRESS', sys.argv[3] + ':' + str(n), '完整正文' * 100)
'''
        procs = [subprocess.Popen([sys.executable, '-c', code, str(MAIL), str(self.root), f's{i}'],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for i in range(8)]
        for p in procs:
            self.addCleanup(lambda p=p: p.kill() if p.poll() is None else None)
        for p in procs:
            out, err = p.communicate(timeout=30)
            self.assertEqual(p.returncode, 0, err)
        paths = list(self.box('bob').glob('*.md'))
        self.assertEqual(len(paths), 160, '160 封同秒投遞不可被覆蓋')
        rows = [mail.letter(p) for p in paths]
        self.assertEqual({l['title'] for l in rows}, {f's{i}:{n}' for i in range(8) for n in range(20)})
        self.assertEqual(len({l['id'] for l in rows}), 160)
        for p in paths:
            text = p.read_text()
            self.assertTrue(text.endswith('完整正文' * 100 + '\n'))
            self.assertIn('狀態：還在辦，這是進度\n\n', text)
            self.assertEqual(text.count('\n## '), 0)
        self.assertEqual(list((self.box('bob') / '.tmp').iterdir()), [])


    def test_audit_progress_and_terminal(self):
        sent = self.send()
        for who in ('alice', 'bob'):
            self.assertIn(sent['id'], self.cli('audit', who, '--json', rc=1).stdout)
        self.cli('send', 'bob', 'alice', 'PROGRESS', '仍在處理', '--re', sent['id'])
        self.cli('audit', rc=1)
        self.cli('done', 'bob', Path(sent['sent']).name, 'DONE', '已確認')
        self.assertEqual(json.loads(self.cli('audit', '--json').stdout), [])
        reply = [mail.letter(p) for p in self.box('alice').glob('*.md') if mail.letter(p)['status'] == 'DONE']
        self.assertEqual(len(reply), 1)
        self.assertEqual(reply[0]['re'], sent['id'])
        self.cli('done', 'alice', Path(reply[0]['file']).name)
        self.cli('audit')


    def test_crash_done_recovery(self):
        for point, restart in [('mail.after_journal', 'read'), ('mail.after_reply', 'done')]:
            with self.subTest(point=point):
                sent = self.send()
                filename = Path(sent['sent']).name
                self.cli('done', 'bob', filename, 'DONE', '辦好了', rc=-signal.SIGKILL, env={'AOS7_TEST_CRASH': point})
                self.assertTrue(Path(sent['sent']).exists())
                if restart == 'read':
                    self.assertIn('復原  ' + filename, self.cli('read', 'bob').stdout)
                else:
                    self.cli('done', 'bob', filename)
                self.cli('done', 'bob', filename)
                replies = [mail.letter(p) for p in mail.letters(self.box('alice'), True)
                           if mail.letter(p).get('re') == sent['id']]
                self.assertEqual(len(replies), 1, '復原不可重寄回信')
                self.assertTrue((self.box('bob') / 'done' / filename).exists())
                self.cli('audit')


    def test_handle_crash_side_effect_once(self):
        sent = self.send()
        code = '''import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import aos7_mail as m
root = Path(sys.argv[2])
def handler(letter):
    counter = root / 'count'
    n = int(counter.read_text()) if counter.exists() else 0
    counter.write_text(str(n + 1))
    return 'DONE', '副作用已完成', '計數已加一'
m.handle(root, 'bob', handler)
'''
        command = [sys.executable, '-c', code, str(MAIL), str(self.root)]
        killed = subprocess.run(command, env=dict(os.environ, AOS7_TEST_CRASH='mail.after_journal'), timeout=30)
        self.assertEqual(killed.returncode, -signal.SIGKILL)
        self.assertEqual((self.root / 'count').read_text(), '1')
        p = subprocess.run(command, capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual((self.root / 'count').read_text(), '1', '日誌後復原不得重做 handler')
        self.assertEqual(len(list(self.box('alice').glob('*.md'))), 1)
        self.assertTrue((self.box('bob') / 'done' / Path(sent['sent']).name).exists())
        self.cli('audit')


    def test_validation(self):
        for bad in ('BOGUS', 'done', 'REQUEST\nDONE'):
            with self.assertRaises(ValueError):
                mail.send(self.root, 'alice', 'bob', bad, '拒絕非法狀態')
            self.cli('send', 'alice', 'bob', bad, '拒絕非法狀態', 'extra', rc=2)
        for bad in ('../escape', 'a/b', '..', '.', 'a b', 'a\nstatus: DONE'):
            self.cli('send', bad, 'bob', 'DONE', '拒絕非法名字', rc=2)
            self.cli('read', bad, rc=2)
        sent = self.send()
        self.cli('done', 'bob', Path(sent['sent']).name, rc=2)
        self.cli('done', 'bob', Path(sent['sent']).name, 'PROGRESS', '未辦完', rc=2)
        self.assertTrue(Path(sent['sent']).exists())
        self.cli('done', 'bob', '../escape.md', rc=2)
        self.cli('send', 'alice', '--up', 'DONE', '無上游', rc=1)  # 前提不在
        p = self.cli('send', rc=2)
        self.assertEqual(len(p.stderr.splitlines()), 1)


    def test_events_contiguous_ack(self):
        (self.root / 'bob/events').mkdir(parents=True)
        first, second = self.send(), self.send()
        events = self.root / 'bob/events'
        records = read(events, 'must')['records']
        self.assertEqual([r['kind'] for r in records], ['mail.request', 'mail.request'])
        self.assertEqual(records[0]['event_id'], first['id'])
        self.cli('read', 'bob')
        self.assertEqual(self.acked('bob'), 0, '讀信不算 ack')
        self.cli('done', 'bob', Path(first['sent']).name, 'DONE', '中斷於歸檔前',
                 rc=-signal.SIGKILL, env={'AOS7_TEST_CRASH': 'mail.after_reply'})
        self.assertEqual(self.acked('bob'), 0, '終局回信已落盤但原信未進 done 仍不得 ack')
        self.cli('done', 'bob', Path(second['sent']).name, 'DONE', '第二封先完成')
        self.assertEqual(self.acked('bob'), 0)
        self.cli('done', 'bob', Path(first['sent']).name, 'DONE', '第一封完成')
        self.assertEqual(self.acked('bob'), 2)
        self.assertTrue(publish(events, 'other.request', 'foreign', {}, must=True, node='bob')['ok'])
        third = self.send()
        self.cli('done', 'bob', Path(third['sent']).name, 'DONE', '第三封完成')
        self.assertEqual(self.acked('bob'), 2, '非 mail must 不可越過')


    def test_event_failure_keeps_letter(self):
        (self.root / 'bob/events').mkdir(parents=True)
        for why in ('full', 'unknown'):
            with patch.object(mail, 'publish', return_value={'ok': False, 'why': why}):
                with patch('sys.stderr') as err:
                    sent = mail.send(self.root, 'alice', 'bob', 'REQUEST', '提醒失敗仍寄信')
                    self.assertTrue(Path(sent['sent']).exists())
                    self.assertTrue(err.write.called)


