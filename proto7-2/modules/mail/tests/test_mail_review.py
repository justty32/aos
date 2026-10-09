"""審查 1–7 的退化測試，以及人類介面驗收。"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'tests'))
from base import MODULES
import datetime
import fcntl
import io
import json
from pathlib import Path
import signal
import subprocess
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(MODULES) / 'mail'))
import aos7_mail as mail
import aos7_mail_cli as cli
from aos7_events_pub import publish
from aos7_events_read import read


class ReviewCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='aos72-mail-review-')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def run_cli(self, *args, rc=0, env=None):
        p = subprocess.run([str(Path(MODULES) / 'mail/aos7-mail'), '--root', str(self.root), *args],
                           capture_output=True, text=True, timeout=30, env=dict(os.environ, **(env or {})))
        self.assertEqual(p.returncode, rc, p.stderr)
        return p

    def send(self, status='PROGRESS', title='測試', sender='alice', to='bob'):
        return mail.send(self.root, sender, to, status, title)

    def test_review1_archive_never_overwrites(self):
        class Fixed(datetime.datetime):
            @classmethod
            def now(cls):
                return cls(2026, 10, 9, 12, 0, 0)
        with patch.object(mail.datetime, 'datetime', Fixed):
            first = self.send(title='第一封')
            mail.done(self.root, 'bob', Path(first['sent']).name)
            second = self.send(title='第二封')
            self.assertNotEqual(Path(first['sent']).name, Path(second['sent']).name,
                                '投遞必須避開 done 檔名')
            # 故意製造舊版本同名歷史；歸檔仍須保留兩封。
            path = Path(second['sent'])
            collision = path.parent / 'done' / path.name
            (path.parent / 'done' / Path(first['sent']).name).rename(collision)
            mail.done(self.root, 'bob', path.name)
            rows = [mail.letter(p) for p in (path.parent / 'done').glob('*.md')]
            self.assertEqual({r['id'] for r in rows}, {first['id'], second['id']}, '歸檔不可覆蓋舊信')

    def test_minute_filenames_and_collision_retry(self):
        class Fixed(datetime.datetime):
            second = 1
            @classmethod
            def now(cls):
                return cls(2026, 10, 9, 12, 0, cls.second)
        with patch.object(mail.datetime, 'datetime', Fixed):
            first = self.send()
            Fixed.second = 59
            second = self.send()
            self.assertEqual(Path(first['sent']).name, '20261009T1200-alice-PROGRESS.md')
            self.assertEqual(Path(second['sent']).name, '20261009T1200_1-alice-PROGRESS.md')
            self.assertIn('20261009T120001', first['id'])
            self.assertIn('20261009T120059', second['id'])
            original = Path(first['sent']).read_bytes()
            mail.done(self.root, 'bob', first['id'])
            # 模擬既有同名歸檔：link 必須拒覆蓋、重試分鐘格式。
            archived = Path(first['sent']).parent / 'done' / Path(first['sent']).name
            archived.rename(archived.parent / Path(second['sent']).name)
            mail.done(self.root, 'bob', second['id'])
            self.assertEqual((archived.parent / Path(second['sent']).name).read_bytes(), original)
            third = self.send()
            paths = mail.letters(mail.inbox(self.root, 'bob'), True)
            for path in paths:
                self.assertRegex(path.name, r'^\d{8}T\d{4}(_\d+)?-alice-PROGRESS\.md$')
            self.assertEqual(len(paths), 3)
            self.assertEqual(mail.letter(third['sent'])['reply-to'], str(self.root / 'alice/inbox'))

    def test_roster_appends_inside_template_active_section(self):
        path = self.root / 'alice/wf/workflows/inbox/ROSTER.md'
        path.parent.mkdir(parents=True)
        prefix = '# ROSTER — 身份簿\n\n## 規則\n只加自己的格。\n\n'
        active = '## 現役成員\n\n### `existing`\n- **上游**：old-chief\n\n'
        suffix = '## 退役成員\n\n### `retired`\n原樣保留。\n'
        path.write_text(prefix + active + suffix)
        mail.roster(self.root, 'alice', '測試者', 'chief', 'alice/', '寄信', '驗身份')
        text = path.read_text()
        self.assertTrue(text.startswith(prefix + active))
        self.assertEqual(text[text.index('## 退役成員'):], suffix)
        self.assertLess(text.index('### `existing`'), text.index('### `alice`'))
        self.assertLess(text.index('### `alice`'), text.index('## 退役成員'))
        self.assertEqual(mail.upstream(self.root, 'alice'), 'chief')
        self.assertFalse((self.root / 'alice/wf/ROSTER.md').exists())
        # 沒有現役段時只加在檔尾，保留既有內容。
        other = self.root / 'bob/wf/workflows/inbox/ROSTER.md'
        other.parent.mkdir(parents=True)
        other.write_text(prefix + suffix)
        mail.roster(self.root, 'bob', '測試者', 'chief', 'bob/', '寄信', '驗身份')
        self.assertTrue(other.read_text().startswith(prefix + suffix + '\n### `bob`'))

    def test_review2_seen_only_after_flush(self):
        self.run_cli('team', 'dev', 'lead', 'bob')
        self.send(title='個人新信')
        self.send(sender='lead', to='team:dev', title='團隊新信')
        orders = self.root / 'bob/inbox/orders/bob.md'
        orders.parent.mkdir(parents=True, exist_ok=True)
        orders.write_text('## 新指示\n正文\n')
        # 真 SIGKILL：print 已進 buffer，flush 前被殺，三種游標都不得提交。
        self.run_cli('read', 'bob', '--quiet', rc=-signal.SIGKILL,
                     env={'AOS7_TEST_CRASH': 'mail.before_output_flush'})
        box = self.root / 'bob/inbox'
        for marker in ('.seen', '.seen-team', '.orders-offset'):
            self.assertFalse((box / marker).exists(), 'flush 前不得保存 ' + marker)
        # stdout flush 失敗與後段 audit 失敗也不得消耗批次。
        class Broken(io.StringIO):
            def flush(self):
                raise OSError('輸出失敗')
        with patch('sys.stdout', Broken()), patch('sys.stderr', io.StringIO()):
            self.assertEqual(cli.main(['--root', str(self.root), 'read', 'bob', '--quiet']), 2)
        with patch.object(mail, 'audit', side_effect=OSError('掃描失敗')):
            with self.assertRaises(OSError):
                with mail.poll(self.root, 'bob', True):
                    pass
        flushed = self.run_cli('read', 'bob', '--quiet', rc=-signal.SIGKILL,
                               env={'AOS7_TEST_CRASH': 'mail.before_seen_commit'}).stdout
        for title in ('個人新信', '團隊新信', '新指示'):
            self.assertIn(title, flushed, '保存前必須已 flush 輸出')
        out = self.run_cli('read', 'bob', '--quiet').stdout
        for title in ('個人新信', '團隊新信', '新指示'):
            self.assertIn(title, out)
        self.assertEqual(self.run_cli('read', 'bob', '--quiet').stdout, '')

    def test_review3_ack_reconciles_after_retention(self):
        events = self.root / 'bob/events'
        publish(events, 'mail.request', 'seed', {'id': 'seed'}, must=True, node='bob',
                config={'keep': 1, 'segment_bytes': 1})
        # 第一筆也已辦；讓 must seq1 能進位。
        box = self.root / 'bob/inbox'
        (box / 'done').mkdir(parents=True)
        seed = self.send(status='REQUEST', title='第一封')
        # 用寄出的 seq2 請求內容表示 seed 的已辦記錄。
        data = Path(seed['sent']).read_text().replace('id: ' + seed['id'], 'id: seed')
        (box / 'done/seed.md').write_text(data)
        self.run_cli('done', 'bob', seed['id'], 'DONE', '完成', rc=-signal.SIGKILL,
                     env={'AOS7_TEST_CRASH': 'mail.after_event_ack'})
        self.assertEqual(mail.load(box / '.acked'), 0, '本地游標模擬落後')
        # 兩次輪替淘汰 seq1/2；新請求仍需能確認。
        next_mail = self.send(status='REQUEST', title='第二封')
        last_mail = self.send(status='REQUEST', title='第三封')
        self.assertTrue(read(events, 'must', cursor=1)['gaps'], '必須真的觸發 retention')
        self.run_cli('done', 'bob', next_mail['id'], 'DONE', '完成第二封')
        self.run_cli('done', 'bob', last_mail['id'], 'DONE', '完成第三封')
        self.assertEqual(mail.event_ack(events, 0), 4, '本地落後與舊段淘汰不得卡住後續 ack')

    def test_review4_archive_and_scan_share_delivery_lock(self):
        sent = self.send()
        real_link = mail.os.link
        def archive_link(source, target):
            lock = Path(source).parent / '.delivery.lock'
            with lock.open('a') as f:
                with self.assertRaises(BlockingIOError, msg='歸檔必須持 delivery 鎖'):
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return real_link(source, target)
        with patch.object(mail.os, 'link', side_effect=archive_link):
            mail.done(self.root, 'bob', sent['id'])
        real_letter = mail.letter
        def scanned(path):
            box = Path(path).parent
            if box.name == 'done':
                box = box.parent
            with (box / '.delivery.lock').open('a') as f:
                with self.assertRaises(BlockingIOError, msg='audit 必須在 delivery 鎖下列檔讀信'):
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return real_letter(path)
        with patch.object(mail, 'letter', side_effect=scanned):
            mail.audit(self.root)
        # 真並行送／辦／audit，不靠排程時間取得綠燈。
        code = "import sys; sys.path.insert(0,sys.argv[1]); import aos7_mail as m; "
        commands = ["[m.send(sys.argv[2],'a','bob','PROGRESS',str(i)) for i in range(40)]",
                    "[m.handle(sys.argv[2],'bob',lambda l:('DONE','ok','')) for i in range(40)]",
                    "[m.audit(sys.argv[2]) for i in range(40)]"]
        procs = [subprocess.Popen([sys.executable, '-c', code + c, str(Path(MODULES) / 'mail'), str(self.root)],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE) for c in commands]
        for p in procs:
            self.addCleanup(lambda p=p: p.kill() if p.poll() is None else None)
        for p in procs:
            _, err = p.communicate(timeout=30)
            self.assertEqual(p.returncode, 0, err)

    def test_review5_invalid_title_cannot_poison_journal(self):
        sent = self.send(status='REQUEST')
        for title in ('   ', '第一行\n第二行', '第一行\r第二行'):
            self.run_cli('done', 'bob', sent['id'], 'DONE', title, rc=2)
            self.assertFalse((self.root / 'bob/inbox/.handled' / (sent['id'] + '.json')).exists(),
                             '非法回信不得建立日誌')
        mail.done(self.root, 'bob', sent['id'], 'DONE', '正確結論')
        self.assertEqual(mail.audit(self.root), [])

    def test_review6_three_hyphen_names_parse(self):
        first = self.send(status='REQUEST', sender='a---b', to='c---d')
        self.assertEqual(mail.letter(first['sent'])['from'], 'a---b')
        self.send(sender='a---b', to='c---d')
        self.assertEqual(len(mail.audit(self.root)), 1)
        self.run_cli('read', 'c---d')
        mail.done(self.root, 'c---d', first['id'], 'DONE', '已辦')
        self.assertEqual(mail.audit(self.root), [])

    def test_review7_only_people_can_read_done_handle(self):
        self.run_cli('team', 'dev', 'lead', 'bob')
        sent = self.send(sender='lead', to='team:dev')
        self.run_cli('done', 'team:dev', Path(sent['sent']).name, rc=2)
        self.run_cli('read', 'team:dev', rc=2)
        with self.assertRaises(ValueError):
            mail.handle(self.root, 'team:dev', lambda l: ('DONE', 'ok', ''))
        self.assertTrue(Path(sent['sent']).exists(), '任何個人不可移走團隊廣播')
        self.assertIn('團隊', self.run_cli('read', 'bob').stdout)

    def test_round2_numbers_bind_snapshot(self):
        class Fixed(datetime.datetime):
            @classmethod
            def now(cls):
                return cls(2026, 10, 9, 12, 0, 0)
        with patch.object(mail.datetime, 'datetime', Fixed):
            first = self.send(sender='z-last')
            self.assertIn('請先 read', self.run_cli('done', 'bob', '1', rc=2).stderr)
            self.run_cli('read', 'bob')  # 非 JSON 也保存快照。
            box = mail.inbox(self.root, 'bob')
            self.assertEqual(mail.load(box / '.numbers.json'), {'1': first['id']})
            new = self.send(sender='a-first')
            self.assertLess(Path(new['sent']).name, Path(first['sent']).name)
            self.run_cli('done', 'bob', '1')
            self.assertTrue(Path(new['sent']).exists(), '序號不得辦掉後插入的信')
            self.assertFalse(Path(first['sent']).exists())
            again = self.run_cli('done', 'bob', '1').stdout
            self.assertEqual(again, '已辦結過 ' + Path(first['sent']).name + '\n')
            self.assertIn('請先 read', self.run_cli('done', 'bob', '2', rc=2).stderr)
            self.run_cli('read', 'bob', '--quiet', '--json')
            self.assertEqual(mail.load(box / '.numbers.json'), {'1': new['id']})
            self.run_cli('read', 'bob', '--quiet')
            self.assertEqual(mail.load(box / '.numbers.json'), {}, '只綁這次列出的個人信')

    def test_round2_numbers_resume_journal(self):
        class Fixed(datetime.datetime):
            @classmethod
            def now(cls):
                return cls(2026, 10, 9, 12, 0, 0)
        with patch.object(mail.datetime, 'datetime', Fixed):
            first = self.send(status='REQUEST', sender='a-first')
            second = self.send(title='另一封', sender='z-last')
        rows = json.loads(self.run_cli('read', 'bob', '--json').stdout)
        number = str(next(r['number'] for r in rows if r['id'] == first['id']))
        self.run_cli('done', 'bob', number, 'DONE', '已辦', rc=-signal.SIGKILL,
                     env={'AOS7_TEST_CRASH': 'mail.after_journal'})
        self.run_cli('done', 'bob', number)
        self.assertTrue(Path(second['sent']).exists(), '重跑序號必須復原原 journal 的信')
        replies = [mail.letter(p) for p in mail.letters(mail.inbox(self.root, 'a-first'), True)
                   if mail.letter(p).get('re') == first['id']]
        self.assertEqual(len(replies), 1)
        self.assertEqual(replies[0]['status'], 'DONE')
        self.assertIn('已辦結過', self.run_cli('done', 'bob', number).stdout)

    def test_round2_snapshot_only_after_flush(self):
        first = self.send()
        self.run_cli('read', 'bob')
        snapshot = mail.inbox(self.root, 'bob') / '.numbers.json'
        original = snapshot.read_bytes()
        self.send(title='新信')
        self.run_cli('read', 'bob', rc=-signal.SIGKILL,
                     env={'AOS7_TEST_CRASH': 'mail.before_output_flush'})
        self.assertEqual(snapshot.read_bytes(), original)
        self.run_cli('read', 'bob')
        self.assertEqual(len(mail.load(snapshot)), 2)

    def test_round2_roster_atomic_replace(self):
        path = self.root / 'alice/wf/workflows/inbox/ROSTER.md'
        path.parent.mkdir(parents=True)
        original = '# ROSTER\n\n## 現役成員\n既有資料\n'.encode()
        path.write_bytes(original)
        args = ('roster', 'alice', '--who', '測試者', '--up', 'chief',
                '--territory', 'alice/', '--can', '寄信', '--cannot', '驗身份')
        self.run_cli(*args, rc=-signal.SIGKILL,
                     env={'AOS7_TEST_CRASH': 'mail.roster_before_replace'})
        self.assertEqual(path.read_bytes(), original, 'replace 前被殺原 ROSTER 必須不變')
        self.run_cli(*args)
        self.assertIn('### `alice`', path.read_text())
        self.assertTrue(path.read_bytes().startswith(original))

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
        self.run_cli('team', 'dev', 'lead', 'carol', rc=2)
        self.assertEqual((self.root / 'teams/dev/members').read_text(), 'lead\nbob\n')

    def test_round2_team_request_rejected_first(self):
        self.run_cli('team', 'dev', 'lead', 'bob')
        message = '團隊信箱只收廣播（PROGRESS／終局）；要人辦事請直接寄給成員'
        for sender in ('bob', 'outsider'):
            p = self.run_cli('send', sender, 'team:dev', 'REQUEST', '請辦事', rc=2)
            self.assertEqual(p.stderr.strip(), message)
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
        self.assertEqual(p.stderr.strip(), '注意：bob 是新信箱（第一次收信）')
        out = self.run_cli('read', 'bob').stdout
        self.assertEqual(out, '1  ' + Path(first['sent']).name + '  第一封\n')
        self.assertEqual(self.run_cli('read', 'bob', '--quiet').stdout, '')
        self.assertIn('等回信  ', self.run_cli('read', 'alice').stdout)
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


if __name__ == '__main__':
    unittest.main()
