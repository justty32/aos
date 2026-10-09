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
    def test_start_errors_have_fix_and_no_traceback(self):
        for args in (['ask'], ['brain'], ['ask', '/tmp/missing-brain-node', 'test']):
            p = subprocess.run([sys.executable, str(TOP / 'modules/up/aos7_up_brain.py'), *args],
                               capture_output=True, text=True, timeout=10)
            self.assertEqual(p.returncode, 2)
            self.assertIn('怎麼辦：', p.stdout + p.stderr)
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
