"""啟動白話錯誤、假 AI 請求與時間比較。"""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

TOP = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(TOP / 'modules/up'))
import aos7_up_brain as brain
from aos7_up_ask import show_body


class BrainErrorTests(unittest.TestCase):
    def test_ask_newline_path_is_one_line(self):
        p = subprocess.run([sys.executable, str(TOP / 'modules/up/aos7-up'), 'ask', '/tmp/missing\nparent/bob', 'hi'],
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(p.returncode, 2)
        self.assertEqual(len(p.stderr.splitlines()), 1, p.stderr)

    def test_start_errors_have_fix_and_no_traceback(self):
        for args in (['ask'], ['brain'], ['ask', '/tmp/missing-brain-node', 'test']):
            p = subprocess.run([sys.executable, str(TOP / 'modules/up/aos7_up_brain.py'), *args],
                               capture_output=True, text=True, timeout=10)
            self.assertEqual(p.returncode, 2)
            self.assertEqual(p.stdout, '')
            self.assertEqual(len(p.stderr.splitlines()), 1)
            self.assertTrue(p.stderr.startswith('aos7-up: '))
            self.assertIn('。', p.stderr)
            self.assertNotIn('怎麼辦：', p.stderr)
            self.assertNotIn('Traceback', p.stdout + p.stderr)

    def test_fake_variants_make_only_fake_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            node = Path(tmp)
            (node / 'brain').mkdir()
            letter = node / 'letter.md'
            letter.write_text('測試正文')
            l = dict(file=str(letter), title='測試', id='request-id')
            def render(*args, **kw):
                (node / 'brain/req.json').write_text(json.dumps({'litellm': {
                    'model': 'never-connect', 'messages': [{'content': 'prompt'}]}}))
            for cfg in ({}, {'model': None}, {'model': 'fake'}, {'model': ''}):
                with self.subTest(cfg=cfg), patch.object(brain, 'checked', side_effect=render):
                    req = brain.request(node, l, 'cid', cfg)
                    self.assertEqual(set(json.loads(req.read_text())), {'fake'})

    def test_fifo_compares_instants_before_id_and_filename(self):
        def row(at, ident, file):
            return dict(at=at, id=ident, file=file)
        first = row('2026-10-09T16:00:00+08:00', 'z-20261009T160001-x', '20261009T1600_10-z.md')
        later = row('2026-10-09T08:00:01Z', 'a-20261009T160000-x', '20261009T1600-a.md')
        self.assertEqual(sorted([later, first], key=brain.fifo), [first, later])
        same = row('2026-10-09T08:00:00Z', first['id'], '20261009T1600_2-z.md')
        self.assertEqual(sorted([first, same], key=brain.fifo), [same, first])

    def test_body_preserves_indentation(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            show_body('## 做了什麼\n    原文縮排\n## 失敗\n無\n', '結論')
        self.assertEqual(out.getvalue(), '    原文縮排\n## 失敗\n無\n')


    def test_ask_reply_labels_and_uncertain_delivery(self):
        import aos7_up_ask as ask
        with tempfile.TemporaryDirectory() as tmp:
            node = Path(tmp) / 'bob'
            node.mkdir()
            for status, suffix in (('DONE', ''), ('BLOCKED', '（卡住了）'),
                                   ('NEEDS-USER', '（要你決定）'), ('FAILED', '（沒辦成）')):
                replies = json.dumps([dict(id='reply-id', re='id', status=status, title='標題')])
                with patch.object(ask, 'mail', side_effect=['{"id":"id"}', replies, '']), \
                     contextlib.redirect_stdout(io.StringIO()) as out, \
                     contextlib.redirect_stderr(io.StringIO()) as err:
                    self.assertEqual(ask.main(['ask', str(node), '一句話']), 0)
                self.assertEqual(out.getvalue(), f'bob 回信{suffix}：標題\n')
                self.assertEqual(err.getvalue(), '')
            for responses in ([OSError('multi\nline')], ['{"id":"id"}', ValueError('bad json')]):
                with patch.object(ask, 'mail', side_effect=responses), \
                     contextlib.redirect_stdout(io.StringIO()) as out, \
                     contextlib.redirect_stderr(io.StringIO()) as err:
                    self.assertEqual(ask.main(['ask', str(node), '一句話']), 3)
                self.assertEqual(out.getvalue(), '')
                self.assertEqual(err.getvalue(), f'aos7-up: 不確定：寄信或讀信沒完成，信可能已寄出。等一下用 aos7-up status {node} 看，別急著重寄\n')
            with patch.object(ask, 'mail', return_value='{"id":"id"}'), \
                 contextlib.redirect_stdout(io.StringIO()) as out, \
                 contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(ask.main(['ask', str(node), '一句話', '--wait', '0']), 0)
            self.assertEqual(out.getvalue(), f'bob 還沒回（等了 0 秒）。等一下用 aos7-up status {node} 看\n')
            self.assertEqual(err.getvalue(), '')

    def test_brain_start_error_codes(self):
        for exception, code, message in (
            (KeyError('task'), 2, 'brain 只能由心跳起。用 aos7-up <node> 起 node'),
            (ValueError('run'), 2, 'brain 只能由心跳起。用 aos7-up <node> 起 node'),
            (OSError('private\nreason'), 3, '不確定：brain 讀寫故障。照原樣再跑 aos7-up <node> 會接續')):
            with patch.object(brain, 'task_env', side_effect=exception), \
                 contextlib.redirect_stderr(io.StringIO()) as err, \
                 contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(brain.main(['brain', '/tmp/bob']), code)
            self.assertEqual(err.getvalue(), 'aos7-up: ' + message + '\n')
            self.assertEqual(out.getvalue(), '')


    def test_llmcall_outcomes(self):
        for rc in (0, 1, 2, 3, 4, 5, -9):
            with self.subTest(rc=rc), \
                 patch.object(brain, 'request', return_value=Path('/tmp/req')), \
                 patch.object(brain, 'run', return_value=subprocess.CompletedProcess([], rc, '{"text":"收到"}\n', '')):
                if rc == 3:
                    with self.assertRaises(brain.Later):
                        brain.ask_ai(Path('/tmp'), {}, 'cid', {})
                elif rc in (0, 4):
                    reply = brain.ask_ai(Path('/tmp'), {}, 'cid', {})
                    self.assertEqual(reply, '收到')
                    self.assertEqual(reply.usage_pending, rc == 4)
                else:
                    with self.assertRaises(brain.Trouble):
                        brain.ask_ai(Path('/tmp'), {}, 'cid', {})
