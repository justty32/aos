from _mailcase import *


class Tests(ReviewCase):
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
        # stdout flush 失敗與讀檔失敗也不得消耗批次。
        class Broken(io.StringIO):
            def flush(self):
                raise OSError('輸出失敗')
        with patch('sys.stdout', Broken()), patch('sys.stderr', io.StringIO()):
            self.assertEqual(cli.main(['--root', str(self.root), 'read', 'bob', '--quiet']), 3)
        with patch.object(boxmod, 'letter', side_effect=OSError('掃描失敗')):
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
        self.assertEqual(mail.load(box / '.acked', 0), 0, '本地游標模擬落後')
        # 兩次輪替淘汰 seq1/2；新請求仍需能確認。
        next_mail = self.send(status='REQUEST', title='第二封')
        last_mail = self.send(status='REQUEST', title='第三封')
        self.assertTrue(read(events, 'must', cursor=1)['gaps'], '必須真的觸發 retention')
        self.run_cli('done', 'bob', next_mail['id'], 'DONE', '完成第二封')
        self.run_cli('done', 'bob', last_mail['id'], 'DONE', '完成第三封')
        self.assertEqual(mail.event_ack(events, 0), 4, '本地落後與舊段淘汰不得卡住後續 ack')


