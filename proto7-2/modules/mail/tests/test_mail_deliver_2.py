from _mailcase import *


class Tests(MailCase):
    def test_team_orders_quiet(self):
        self.cli('team', 'dev', 'lead', 'bob', 'carol')
        self.cli('team', 'other', 'x', 'bob', rc=1)
        self.cli('team', 'dev', 'x', rc=1)
        up = self.send('bob', '--up', 'PROGRESS', '向領導回報')
        self.assertEqual(Path(up['sent']).parent, self.box('lead'))
        sent = self.send()
        self.cli('done', 'bob', Path(sent['sent']).name, 'DONE', '已辦結並副本回報')
        self.assertEqual(len([p for p in self.box('lead').glob('*.md') if mail.letter(p).get('re') == sent['id']]), 1)
        lead_request = self.send(to='lead')
        self.cli('done', 'lead', Path(lead_request['sent']).name, 'DONE', '領導辦結也留副本')
        self.assertEqual(len([p for p in self.box('lead').glob('*.md')
                              if mail.letter(p).get('re') == lead_request['id']]), 1)
        self.cli('send', 'alice', 'team:dev', 'PROGRESS', '非成員拒絕', rc=1)
        self.send('carol', 'team:dev', 'PROGRESS', '團隊廣播')
        for who in ('bob', 'carol'):
            self.assertIn('團隊廣播', self.cli('read', who, '--quiet').stdout)
            self.assertEqual(self.cli('read', who, '--quiet').stdout, '')
        orders = self.root / 'bob/inbox/orders/bob.md'
        orders.parent.mkdir(parents=True, exist_ok=True)
        orders.write_text('## 時間 — from: lead — 新指令\n中文正文\n')
        self.assertIn('指示  ## 時間 — from: lead — 新指令', self.cli('read', 'bob').stdout)
        self.assertEqual(self.cli('read', 'bob', '--quiet', '--json').stdout, '')
        with orders.open('a') as f:
            f.write('## 第二段\n追加正文\n')
        out = self.cli('read', 'bob').stdout
        self.assertIn('指示  ## 第二段', out)
        self.assertNotIn('中文正文', out)
        self.assertEqual(self.cli('read', 'bob', '--quiet').stdout, '')


    def test_roster_and_upstream(self):
        args = ('roster', 'alice', '--who', '測試者', '--up', 'chief', '--territory', '我的資料夾',
                '--can', '寄信', '--cannot', '驗身份')
        self.cli(*args)
        text = (self.root / 'alice/wf/workflows/inbox/ROSTER.md').read_text()
        self.assertIn('## 現役成員', text)
        self.assertIn('### `alice`', text)
        self.assertIn('- **上游**：chief', text)
        self.cli(*args, rc=1)  # 撞名：做不到
        self.assertEqual((self.root / 'alice/wf/workflows/inbox/ROSTER.md').read_text(), text)
        sent = self.send('alice', '--up', 'PROGRESS', '讀 ROSTER 路由')
        self.assertEqual(Path(sent['sent']).parent, self.box('chief'))
        self.cli('team', 'dev', 'alice', 'bob')
        sent = self.send('alice', '--up', 'PROGRESS', '領導向自己的上游回報')
        self.assertEqual(Path(sent['sent']).parent, self.box('chief'))


    def test_wfnode_layout_roundtrip(self):
        home = Path(os.environ.get('AOS7_WF_HOME', '~/repo/workflows')).expanduser()
        if not (home / 'tools/wf-init.sh').is_file():
            self.skipTest('找不到 workflows/tools/wf-init.sh（AOS7_WF_HOME 或預設路徑）')
        wfnode = Path(MODULES) / 'wfnode/aos7-wfnode'

        def node_cli(command, who):
            return subprocess.run([str(wfnode), command, str(self.root / who)],
                                  capture_output=True, text=True, timeout=60)

        before = {}
        for who, up in (('alice', 'bob'), ('bob', 'alice')):
            result = node_cli('init', who)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            before[who] = node_cli('check', who).returncode
            box = self.box(who)
            self.assertTrue((box / '.gitkeep').is_file())
            self.assertTrue((box / 'done/.gitkeep').is_file())
            path = self.root / who / 'wf/workflows/inbox/ROSTER.md'
            template = path.read_text()
            self.cli('roster', who, '--who', '測試者', '--up', up,
                     '--territory', who + '/', '--can', '寄信', '--cannot', '驗身份')
            updated = path.read_text()
            # 只插入現役成員格；移除插入內容後須逐字等於真模板。
            entry_start = updated.index('\n### `' + who + '`\n')
            entry_end = updated.index('- **訂閱主題**：無\n\n', entry_start) + len('- **訂閱主題**：無\n\n')
            self.assertEqual(updated[:entry_start] + updated[entry_end:], template)
            active_start = updated.index('## 現役成員')
            following = updated.find('\n## ', active_start + 1)
            self.assertGreater(entry_start, active_start)
            if following != -1:
                self.assertLess(entry_end, following + 1)
            self.assertIn('- **怎麼找我**：' + str(box), updated)
            self.assertEqual(json.loads(self.cli('read', who, '--json').stdout), [])

        request = self.send()
        self.assertEqual(Path(request['sent']).parent, self.box('bob'))
        self.assertEqual(mail.letter(request['sent'])['reply-to'], str(self.box('alice')))
        incoming = json.loads(self.cli('read', 'bob', '--json').stdout)
        self.assertEqual([row['id'] for row in incoming], [request['id']])
        self.cli('done', 'bob', '1', 'DONE', 'wfnode 整合完成')
        replies = json.loads(self.cli('read', 'alice', '--json').stdout)
        self.assertEqual(len(replies), 1)
        self.assertEqual((replies[0]['status'], replies[0]['re']), ('DONE', request['id']))
        self.assertEqual(Path(replies[0]['file']).parent, self.box('alice'))
        self.assertTrue((self.box('bob') / 'done' / Path(request['sent']).name).is_file())
        self.assertEqual(mail.audit(self.root), [])
        for who in ('alice', 'bob'):
            self.assertFalse((self.root / who / 'wf/inbox').exists())
            after = node_cli('check', who)
            self.assertEqual(after.returncode, before[who], after.stdout + after.stderr)
            print(f'wfnode check {who}: {before[who]} → {after.returncode}')


    def test_ignore_hidden_and_non_markdown_files(self):
        (self.root / 'bob/events').mkdir(parents=True)
        self.cli('team', 'dev', 'alice', 'bob')
        for box in (self.box('alice'), self.box('bob'), mail.inbox(self.root, 'team:dev')):
            for folder in (box, box / 'done'):
                folder.mkdir(parents=True, exist_ok=True)
                for filename in ('.gitkeep', '.hidden.md', 'notes.txt', 'state.json'):
                    (folder / filename).write_text('不是信件')
                (folder / 'directory.md').mkdir()
            self.assertEqual(mail.letters(box, True), [])
        self.assertEqual(mail.audit(self.root), [])
        request = self.send()
        self.cli('send', 'alice', 'team:dev', 'PROGRESS', '團隊廣播')
        incoming = json.loads(self.cli('read', 'bob', '--json').stdout)
        self.assertEqual([row['type'] for row in incoming], ['mail', 'team'])
        self.cli('done', 'bob', '1', 'DONE', '略過雜檔完成')
        self.assertEqual(self.acked('bob'), 1)
        self.assertEqual(mail.audit(self.root), [])
        # 去重與 handle 也只解析有效信檔。
        mail.send(self.root, 'alice', 'bob', 'REQUEST', '重寄', ident=request['id'])
        mail.handle(self.root, 'alice', lambda letter: ('DONE', '歸檔', ''))
        self.assertEqual(mail.letters(self.box('alice')), [])
        self.assertTrue((self.box('bob') / 'done/.hidden.md').is_file())


    def test_example(self):
        p = subprocess.run(['sh', str(MAIL / 'examples/two_nodes.sh')], capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.splitlines()[-1], 'OK')


