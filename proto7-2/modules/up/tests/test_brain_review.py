"""第二輪回歸測試。"""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

TOP = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(TOP / 'tests'), str(TOP / 'modules/up'), str(TOP / 'modules/up/examples'),
               str(TOP / 'modules/mail')]
from base import DaemonCase, read_json, write_json
from brain_node import setup
import aos7_up_brain as brain
from aos7_up_ask import show_body
from aos7_mail import send, letter
HOME = Path(os.environ.get('AOS7_WF_HOME', '~/repo/workflows')).expanduser()


@unittest.skipUnless((HOME / 'tools/wf-init.sh').exists(), '找不到 workflows 模板')
class BrainReviewTests(DaemonCase):
    def setUp(self):
        super().setUp()
        self.node = setup(Path(self.mknode('bob')), interval_ms=200)
        self.set_tasks(str(self.node), [t for t in self.tasks(str(self.node)) if t['name'] != 'brain'])

    def post(self, who='you', title='測試', body=''):
        return send(self.root, who, 'bob', 'REQUEST', title, body)

    def test_blocked_pending_kill_no_ai(self):
        self.start_daemon(register=['bob'])
        self.wait_round(2, 'bob')
        ident = self.post()['id']
        cfg = read_json(str(self.node / '.aos/up.json'))
        cfg['deadline'] = 5
        write_json(str(self.node / '.aos/up.json'), cfg)
        code = '''import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import aos7_up_brain as b
node = Path(sys.argv[2])
def req(node, letter, cid, cfg):
    p = node / 'brain/req.json'
    b.write_json(str(p), {'fake': {'mode': 'fail', 'usage': 10}})
    return p
b.request = req
b.once(node, 1)
'''
        p = subprocess.run([sys.executable, '-c', code, str(TOP / 'modules/up'), str(self.node)],
                           env=dict(os.environ, AOS7_TEST_CRASH='up-brain-after-pending'),
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, -9, p.stderr)
        pending = read_json(str(self.node / 'brain/pending.json'))
        self.assertEqual(pending['status'], 'BLOCKED')
        self.assertEqual(pending['title'], 'AI 沒回應')
        self.assertEqual(pending['body'], '原因：AI 沒回應\n怎麼辦：' + brain.AI_FIX)
        marker = self.node / 'called-again'
        restart = '''import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import aos7_up_brain as b
node = Path(sys.argv[2])
original = b.ask_ai
def spy(*args):
    (node / 'called-again').touch()
    return original(*args)
b.ask_ai = spy
b.once(node, 2)
'''
        p = subprocess.run([sys.executable, '-c', restart, str(TOP / 'modules/up'), str(self.node)],
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertFalse(marker.exists(), 'pending BLOCKED 重啟又呼叫 AI')
        replies = [letter(p) for p in (Path(self.root) / 'you/inbox').glob('*.md')]
        self.assertEqual([l['status'] for l in replies], ['BLOCKED'])
        self.assertEqual(read_json(str(self.node / 'llmcall/fake-remote.json'))['sends'], {brain.cid_of(ident): 1})
        self.assertFalse((self.node / 'brain/pending.json').exists())

    def test_long_letter_tail_in_request(self):
        tail = '末尾這一句不能消失。'
        sent = self.post(body='字' * 7000 + tail)
        work = self.node / 'brain'
        work.mkdir()
        req = brain.request(self.node, letter(sent['sent']), 'long', {'model': 'real-test'})
        contents = '\n'.join(m['content'] for m in json.loads(req.read_text())['litellm']['messages'])
        self.assertTrue(tail in contents, '7000 字信末尾被折疊，AI 看不到最後一句')
        self.assertFalse((self.node / 'refs').exists())

    def test_fifo_at_id_numeric_sequence(self):
        z = self.post('z', '先寄 z')
        a = self.post('a', '後寄 a')
        ids = [z['id'], a['id']] + [self.post('you', str(i))['id'] for i in range(11)]
        paths = list((self.node / 'inbox').glob('*.md'))
        for p in paths:
            s = p.read_text()
            s = __import__('re').sub(r'(?m)^at: .*$', 'at: 2026-10-09T16:10:00+08:00', s)
            old = letter(p)['id']
            second = 1 if old == z['id'] else 2
            new = __import__('re').sub(r'\d{8}T\d{6}', f'20261009T1610{second:02}', old)
            s = s.replace(old, new)
            ids[ids.index(old)] = new
            p.write_text(s)
        processed = []
        def ai(node, l, cid, cfg):
            processed.append(l['id'])
            return '回信：收到\n停在哪：回了 ' + l['id']
        with patch.object(brain, 'ask_ai', side_effect=ai), contextlib.redirect_stdout(io.StringIO()):
            for rnd in range(13):
                brain.once(self.node, rnd)
        self.assertEqual(processed, ids, 'FIFO 必須先 z 後 a，且 _2 要在 _10 前')

    def test_fixed_files_and_request_replay(self):
        self.start_daemon(register=['bob'])
        self.wait_round(2, 'bob')
        first = self.post()
        brain.once(self.node, 1)
        work = self.node / 'brain'
        self.assertEqual({p.name for p in work.iterdir()}, {'now.md', 'req.json', 'reply.md', 'state.json'})  # state.json：STATE 去重記的 id，最多 50 個（BR2）
        original = json.loads((work / 'req.json').read_text())
        (work / 'req.json').write_text('{}')
        (self.node / 'AGENTS.md').unlink()
        with patch.object(brain, 'checked', side_effect=AssertionError('不該 render')):
            req = brain.request(self.node, letter(first['sent']).copy() if Path(first['sent']).exists()
                                else {'id': first['id']}, brain.cid_of(first['id']), {})
        self.assertEqual(json.loads(req.read_text()), original)

    def test_config_and_render_errors(self):
        self.post()
        path = self.node / '.aos/up.json'
        path.write_text('{bad')
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            brain.once(self.node, 1)
        self.assertIn(brain.trouble('卡住：設定檔 .aos/up.json 壞了', '刪掉它再跑 aos7-up <node>'), out.getvalue())
        self.post()
        path.write_text('{}')
        with patch.object(brain, 'checked', side_effect=ValueError('sensitive exception')):
            with self.assertRaises(brain.Trouble) as caught:
                brain.request(self.node, {'file': '/missing'}, 'missing', {})
        self.assertEqual(str(caught.exception), brain.trouble('讀不到工作簿的檔', brain.CHECK_FIX))


class BrainReviewUnitTests(unittest.TestCase):
    def test_ask_preserves_subheading_and_none(self):
        text = '## 做了什麼\n答案\n## 失敗\n無\n\n## 產出（檔案路徑 / commit / 分支）\n無\n'
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            show_body(text, '答案')
        self.assertEqual(out.getvalue(), '答案\n## 失敗\n無\n', '做了什麼的 ## 失敗／無 必須原文照印')

    def test_none_body_and_duplicate_conclusion(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            show_body('## 做了什麼\n無\n', '結論')
            show_body('## 做了什麼\n結論\n', '結論')
        self.assertEqual(out.getvalue(), '無\n')

    def test_fake_model_and_environment(self):
        for cfg in ({}, {'model': None}, {'model': 'fake'}, {'model': ''}):
            with (self.subTest(cfg=cfg), patch.object(brain, 'request', return_value=Path('/tmp/req')),
                  patch.object(brain, 'run') as run):
                run.return_value = subprocess.CompletedProcess([], 0, '{"text":"收到"}\n')
                with patch.dict(os.environ, AOS7_LITELLM_URL='http://do-not-connect'):
                    brain.ask_ai(Path('/tmp'), {}, 'cid', dict(cfg, litellm_url='http://do-not-connect'))
                args, kw = run.call_args
                self.assertEqual(args[args.index('--deadline') + 1], 60)
                self.assertNotIn('--out', args)
                self.assertNotIn('AOS7_LITELLM_URL', kw['env'])
                self.assertTrue(brain.is_fake(cfg))
