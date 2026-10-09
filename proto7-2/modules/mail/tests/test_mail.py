"""郵局整合測試：真子程序投遞、SIGKILL 復原與公開 events 介面。"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'tests'))
from base import MODULES
import json
from pathlib import Path
import signal
import subprocess
import tempfile
import unittest
from unittest.mock import patch

MAIL = Path(MODULES) / 'mail'
sys.path.insert(0, str(MAIL))
import aos7_mail as mail
from aos7_events_read import read
from aos7_events_pub import publish


class MailCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='aos72-mail-')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def cli(self, *args, rc=0, env=None):
        p = subprocess.run([str(MAIL / 'aos7-mail'), '--root', str(self.root), *args],
                           capture_output=True, text=True, timeout=30, env=dict(os.environ, **(env or {})))
        self.assertEqual(p.returncode, rc, p.stderr)
        return p

    def send(self, sender='alice', to='bob', status='REQUEST', title='請確認完整信件'):
        return json.loads(self.cli('send', sender, to, status, title).stdout)

    def box(self, who):
        return self.root / who / 'inbox'

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
            self.assertTrue(text.endswith('無\n'))
            self.assertIn('完整正文' * 100, text)
            self.assertEqual(text.count('\n## '), 4)
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
            self.cli('send', 'alice', 'bob', bad, '拒絕非法狀態', rc=2)
        for bad in ('../escape', 'a/b', '..', '.', 'a b', 'a\nstatus: DONE'):
            self.cli('send', bad, 'bob', 'DONE', '拒絕非法名字', rc=2)
            self.cli('read', bad, rc=2)
        sent = self.send()
        self.cli('done', 'bob', Path(sent['sent']).name, rc=2)
        self.cli('done', 'bob', Path(sent['sent']).name, 'PROGRESS', '未辦完', rc=2)
        self.assertTrue(Path(sent['sent']).exists())
        self.cli('done', 'bob', '../escape.md', rc=2)
        self.cli('send', 'alice', '--up', 'DONE', '無上游', rc=2)
        p = self.cli('send', rc=2)
        self.assertEqual(len(p.stderr.splitlines()), 1)

    def acked(self, who):
        # ack 0 是公开 CLI 查目前累積確認值；不替事件進位。
        p = subprocess.run([sys.executable, str(Path(MODULES) / 'events/aos7-events'), 'read',
                            '--events', str(self.root / who / 'events'), '--channel', 'must', '--ack', '0'],
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)['acked_upto']

    def test_events_contiguous_ack(self):
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
        for why in ('full', 'unknown'):
            with patch.object(mail, 'publish', return_value={'ok': False, 'why': why}):
                with patch('sys.stderr') as err:
                    sent = mail.send(self.root, 'alice', 'bob', 'REQUEST', '提醒失敗仍寄信')
                    self.assertTrue(Path(sent['sent']).exists())
                    self.assertTrue(err.write.called)

    def test_team_orders_quiet(self):
        self.cli('team', 'dev', 'lead', 'bob', 'carol')
        self.cli('team', 'other', 'x', 'bob', rc=2)
        self.cli('team', 'dev', 'x', rc=2)
        up = self.send('bob', '--up', 'PROGRESS', '向領導回報')
        self.assertEqual(Path(up['sent']).parent, self.box('lead'))
        sent = self.send()
        self.cli('done', 'bob', Path(sent['sent']).name, 'DONE', '已辦結並副本回報')
        self.assertEqual(len([p for p in self.box('lead').glob('*.md') if mail.letter(p).get('re') == sent['id']]), 1)
        lead_request = self.send(to='lead')
        self.cli('done', 'lead', Path(lead_request['sent']).name, 'DONE', '領導辦結也留副本')
        self.assertEqual(len([p for p in self.box('lead').glob('*.md')
                              if mail.letter(p).get('re') == lead_request['id']]), 1)
        self.cli('send', 'alice', 'team:dev', 'PROGRESS', '非成員拒絕', rc=2)
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
        self.cli(*args, rc=2)
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


if __name__ == '__main__':
    unittest.main()
