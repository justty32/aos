from _mailcase import *


class Tests(ReviewCase):
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


