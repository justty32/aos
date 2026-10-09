from _mailcase import *


class Tests(MailCase):
    def post(self, status='DONE', body='事情已經辦妥。'):
        sent = mail.send(self.root, 'alice', 'bob', status, '結論', body)
        path = Path(sent['sent'])
        return path.read_text(), mail.letter(path)

    def test_plain_done_and_frontmatter(self):
        text, data = self.post()
        header, content = text.split('---\n', 2)[1:]
        self.assertEqual([line.split(':', 1)[0] for line in header.splitlines()],
                         ['from', 'to', 'status', 'at', 'reply-to', 'id', 're'])
        self.assertIn('status: DONE\n', header)
        self.assertNotIn('無', content)
        self.assertNotIn('## ', content)
        self.assertEqual(content, '# 結論\n\n狀態：辦好了\n\n事情已經辦妥。\n')
        self.assertEqual(data['body'], '事情已經辦妥。')
        self.assertEqual(data['plain'], '辦好了')
        self.assertEqual(data['status'], 'DONE')
        rows = json.loads(self.cli('read', 'bob', '--json').stdout)
        self.assertEqual(rows[0]['plain'], '辦好了')
        self.assertEqual(rows[0]['body'], data['body'])

    def test_all_statuses_stay_in_header(self):
        expected = {'DONE': '辦好了', 'BLOCKED': '卡住了，下面寫了怎麼辦',
                    'NEEDS-USER': '要你決定，下面寫了要決定什麼',
                    'FAILED': '做不到，下面寫了原因', 'PROGRESS': '還在辦，這是進度', 'REQUEST': ''}
        for status, plain in expected.items():
            with self.subTest(status=status):
                text, data = self.post(status, '請看這一段。\n    保留縮排')
                header, content = text.split('---\n', 2)[1:]
                self.assertIn('status: ' + status + '\n', header)
                for token in expected:
                    self.assertNotIn(token, content, '機器狀態只能出現在信頭')
                self.assertEqual(data['plain'], plain)
                self.assertEqual(data['body'], '請看這一段。\n    保留縮排')
                if plain:
                    self.assertIn('狀態：' + plain + '\n\n', content)
                else:
                    self.assertEqual(content, '# 結論\n\n請看這一段。\n    保留縮排\n')

    def test_protocol_omits_empty_sections(self):
        body = '\n\n'.join('## ' + h + '\n' + value for h, value in
                             zip(mail.HEADINGS, ('已完成檢查', '無', '  ', '請決定日期')))
        text, data = self.post(body=body)
        expected = '## 做了什麼\n已完成檢查\n\n## 需要對方或使用者決定的事\n請決定日期'
        self.assertEqual(data['body'], expected)
        self.assertNotIn('無', text)
        self.assertEqual(text.count('## '), 2)

    def test_empty_done_body(self):
        for body in ('', ' \n\t', '\n\n'.join('## ' + h + '\n無' for h in mail.HEADINGS)):
            with self.subTest(body=body):
                text, data = self.post(body=body)
                self.assertEqual(text.split('---\n', 2)[2], '# 結論\n\n狀態：辦好了\n\n')
                self.assertEqual(data['body'], '')

    def test_status_sentence_in_body_is_preserved(self):
        body = '狀態：辦好了\n這是原正文。'
        _, data = self.post('FAILED', body)
        self.assertEqual(data['body'], body)
        self.assertEqual(data['plain'], '做不到，下面寫了原因')

    def test_other_headings_and_partial_protocol_are_preserved(self):
        extra = '## 備註\n    原文\n無\n\n'
        body = '前言\n\n## 做了什麼\n無\n\n' + extra + '\n\n'.join(
            '## ' + h + '\n無' for h in mail.HEADINGS[1:])
        self.assertEqual(mail.body_text(body), '前言\n\n' + extra.rstrip() + '\n')
        for body in ('  一段話\n', '## 做了什麼\n無\n', '## 備註\n原文\n'):
            with self.subTest(body=body):
                self.assertEqual(mail.body_text(body), body.rstrip() + '\n')

    def test_old_letter_and_exact_status_line(self):
        sent = mail.send(self.root, 'alice', 'bob', 'REQUEST', '結論', '正文')
        path = Path(sent['sent'])
        original = path.read_text().replace('status: REQUEST', 'status: DONE')
        for body in ('正文', ' 狀態：辦好了\n正文', '狀態：辦好了！\n正文'):
            with self.subTest(body=body):
                path.write_text(original.split('# 結論', 1)[0] + '# 結論\n\n' + body + '\n')
                self.assertEqual(mail.letter(path)['body'], body.strip())


if __name__ == '__main__':
    unittest.main()
