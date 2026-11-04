"""真 daemon、mail、ledger 串接與故障恢復。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

TOP = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(TOP / 'modules/mail'), str(TOP / 'tests'), str(TOP / 'modules/up'), str(TOP / 'modules/up/examples')]
from base import DaemonCase, read_json, write_json
from brain_node import setup
import aos7_up_brain as brain

HOME = Path(os.environ.get('AOS7_WF_HOME', '~/repo/workflows')).expanduser()


@unittest.skipUnless((HOME / 'tools/wf-init.sh').exists(), '找不到 workflows 模板')
class BrainTests(DaemonCase):
    def setUp(self):
        super().setUp()
        self.node = setup(Path(self.mknode('bob')), interval_ms=200)

    def cli(self, tool, *args, code=0):
        p = subprocess.run([sys.executable, str(TOP / tool), *map(str, args)],
                           capture_output=True, text=True, timeout=45)
        self.assertEqual(p.returncode, code, p.stdout + p.stderr)
        return p.stdout

    def send(self, text):
        return json.loads(self.cli('modules/mail/aos7-mail', 'send', 'you', 'bob', 'REQUEST', text,
                                   '--root', self.root))['id']

    def rows(self):
        from aos7_mail import letter
        return [dict(id=l['id'], status=r['status'], tokens=(read_json(str(self.node / 'llmcall/llm' / brain.cid_of(l['id']) / 'receipt.json'), {}) or {}).get('used'))
                for l in sorted((letter(p) for p in (self.node / 'inbox/done').glob('*.md')), key=brain.fifo)
                if l['status'] == 'REQUEST'
                for r in self.replies() if r['re'] == l['id']]

    def replies(self):
        from aos7_mail import letter
        return sorted((letter(p) for p in (Path(self.root) / 'you/inbox').rglob('*.md')),
                      key=brain.fifo)

    def start(self):
        daemon = self.start_daemon(register=['bob'])
        self.wait_round(2, 'bob')
        return daemon

    def state_text(self):
        return '\n'.join(p.read_text() for p in (self.node / 'wf/handoffs').glob('*/STATE.md'))

    def test_fake_round_trip(self):
        self.start()
        before = self.node_round('bob')
        p = subprocess.Popen([sys.executable, str(TOP / 'modules/up/aos7_up_brain.py'),
                              'ask', str(self.node), '你好', '--wait', '30'],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.procs.append(p)
        self.wait_for(lambda: self.replies(), timeout=30)
        after = self.node_round('bob')
        output, errors = p.communicate(timeout=35)
        self.assertEqual(p.returncode, 0, errors)
        self.assertIn('練習用的 AI', output)
        self.assertNotIn('DONE', output)
        self.assertEqual(errors, '')
        self.assertLessEqual(after - before, 3, f'練習用的 AI 一圈 {after - before} 回合')
        self.wait_for(lambda: len(self.rows()) == 1 and not (self.node / 'brain/pending.json').exists())
        entry = self.rows()[0]
        self.assertEqual(entry['status'], 'DONE')
        self.assertGreater(entry['tokens'], 0)
        ledger = read_json(str(self.node / 'budget/llm/ledger.json'))
        self.assertGreater(ledger['used'], 0)
        self.assertEqual(ledger['inflight'], 0)
        self.assertIn('回了 ' + entry['id'], self.state_text())
        self.assertIn('STATE.md', (self.node / 'wf/handoffs/NEXT-SESSION.md').read_text())

    def test_killed_after_llm_reuses_request(self):
        tasks = self.tasks(str(self.node))
        self.set_tasks(str(self.node), [t for t in tasks if t['name'] != 'brain'])
        self.start()
        ident = self.send('殺掉後接回')
        slot = self.node / 'direct-brain'
        slot.mkdir()
        env = dict(os.environ, AOS7_ROOT=self.root, AOS7_NODE=str(self.node), AOS7_NODE_ID='bob',
                   AOS7_TASK=str(slot), AOS7_TID='brain', AOS7_RUN='1')
        def launch(rnd, crash=''):
            write_json(str(slot / 'tock.json'), dict(round=rnd, run=1))
            p = subprocess.Popen([sys.executable, str(TOP / 'modules/up/aos7_up_brain.py'), 'brain', str(self.node)],
                                 env=dict(env, AOS7_TEST_CRASH=crash), stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            self.procs.append(p)
            return p
        p = launch(1, 'up-brain-after-llm')
        self.assertEqual(p.wait(30), -9)
        self.assertEqual(len(self.replies()), 0)
        with (self.node / 'wf/SESSION-LOG.md').open('a') as f:
            f.write('\n- [dev] 接回前新增的 open 工作\n')
        launch(2)
        self.wait_for(lambda: len(self.rows()) == 1 and not (self.node / 'brain/pending.json').exists(), timeout=30)
        self.assertEqual(self.rows()[0]['status'], 'DONE', '重啟必須接回原請求，不能 BLOCKED')
        self.assertEqual(len(self.replies()), 1)
        remote = read_json(str(self.node / 'llmcall/fake-remote.json'))
        self.assertEqual(remote['sends'], {brain.cid_of(ident): 1}, '同信只問一次 AI')
        self.assertEqual(self.state_text().count('回了 ' + ident), 1)

    def test_fifo_one_per_round(self):
        ids = [self.send(str(i)) for i in range(3)]
        self.start()
        self.wait_for(lambda: len(self.rows()) == 3, timeout=35)
        rows = self.rows()
        self.assertEqual([r['id'] for r in rows], ids)
        self.assertEqual([l['re'] for l in self.replies()], ids)

    def test_ten_letters_healthy(self):
        for i in range(10):
            self.send('第 ' + str(i) + ' 封')
        self.start()
        self.wait_for(lambda: len(self.rows()) == 10, timeout=60)
        self.assertEqual([r['status'] for r in self.rows()], ['DONE'] * 10)
        self.cli('modules/wfnode/aos7-wfnode', 'check', self.node)
        self.assertNotIn('已完成', (self.node / 'wf/SESSION-LOG.md').read_text())
        self.cli('modules/mail/aos7-mail', 'audit', 'bob', '--root', self.root)

    def test_ai_failure_next_letter(self):
        from unittest.mock import patch
        self.set_tasks(str(self.node), [t for t in self.tasks(str(self.node)) if t['name'] != 'brain'])
        daemon = self.start()
        self.send('故意失敗')
        with patch.object(brain, 'ask_ai', side_effect=brain.Trouble('AI 沒回應', brain.AI_FIX)):
            brain.once(self.node, 1)
        self.assertEqual(self.replies()[0]['status'], 'BLOCKED')
        self.send('下一封照常')
        brain.once(self.node, 2)
        self.assertEqual(self.rows()[1]['status'], 'DONE')
        self.assertIsNone(daemon.poll())

    def test_ask_timeout(self):
        output = self.cli('modules/up/aos7_up_brain.py', 'ask', self.node, '沒有 daemon', '--wait', '1')
        self.assertIn('還沒回', output)

    def test_pending_state_after_mail(self):
        ident = self.send('接回 state')
        self.cli('modules/mail/aos7-mail', 'done', 'bob', ident, 'DONE', '已回信', '--root', self.root)
        work = self.node / 'brain'
        work.mkdir()
        write_json(str(work / 'pending.json'), dict(id=ident, status='DONE', title='已回信', body='已回信', line='接回續行點', state_count=0))
        self.start()
        self.wait_for(lambda: not (work / 'pending.json').exists())
        self.assertEqual(self.state_text().count('接回續行點'), 1)

    def test_uncertain_llm_retries_same_letter_and_call(self):
        from unittest.mock import patch
        import contextlib
        import io
        self.set_tasks(str(self.node), [t for t in self.tasks(str(self.node)) if t['name'] != 'brain'])
        self.start()
        ident = self.send('接續同一筆')
        original = next((self.node / 'inbox').glob('*.md')).read_bytes()
        calls = []
        real_run = brain.run
        def fake_run(tool, *args, **kwargs):
            if Path(tool).name != 'aos7-llmcall':
                return real_run(tool, *args, **kwargs)
            calls.append(args[args.index('--call') + 1])
            req = json.loads(Path(args[args.index('--request') + 1]).read_text())
            if len(calls) == 1:
                saved = self.node / 'llmcall/llm' / calls[-1] / 'request.json'
                write_json(str(saved), {'request': req})
                return subprocess.CompletedProcess([], 3, '', '不確定')
            self.assertEqual(req, json.loads((self.node / 'llmcall/llm' / calls[-1] / 'request.json').read_text())['request'])
            return subprocess.CompletedProcess([], 0, '{"outcome":"answered","text":"回信：收到\\n停在哪：已回覆"}\n', '')
        with patch.object(brain, 'run', side_effect=fake_run), contextlib.redirect_stdout(io.StringIO()) as out:
            brain.once(self.node, 1)
            self.assertIn('下回合再看同一筆', out.getvalue())
            self.assertFalse((self.node / 'brain/pending.json').exists())
            self.assertEqual(self.replies(), [])
            self.assertEqual(next((self.node / 'inbox').glob('*.md')).read_bytes(), original)
            with patch.object(brain, 'request', wraps=brain.request):
                brain.once(self.node, 2)
        self.assertEqual(calls, [brain.cid_of(ident)] * 2)
        self.assertEqual(self.replies()[0]['status'], 'DONE')
        self.assertEqual(list((self.node / 'inbox').glob('*.md')), [])
        self.assertFalse((self.node / 'brain/pending.json').exists())

    def test_delivered_with_unsettled_usage_replies(self):
        from unittest.mock import patch
        import contextlib
        import io
        self.set_tasks(str(self.node), [t for t in self.tasks(str(self.node)) if t['name'] != 'brain'])
        self.start()
        self.send('用量稍後對')
        real_run = brain.run
        def fake_run(tool, *args, **kwargs):
            if Path(tool).name == 'aos7-llmcall':
                return subprocess.CompletedProcess([], 4, '{"outcome":"answered","text":"收到"}\n', '')
            return real_run(tool, *args, **kwargs)
        with patch.object(brain, 'run', side_effect=fake_run), contextlib.redirect_stdout(io.StringIO()) as out:
            brain.once(self.node, 1)
        self.assertEqual(self.replies()[0]['status'], 'DONE')
        self.assertIn('用量還沒對清', out.getvalue())
        self.assertFalse((self.node / 'brain/pending.json').exists())



class BrainParseTests(unittest.TestCase):
    def test_parse_and_cid(self):
        reply, title, line = brain.parse('回信：\n# 答案\n第二行\n停在哪：已回覆', 'id')
        self.assertEqual(title, '答案')
        self.assertEqual(line, '已回覆')
        self.assertEqual(brain.parse('沒有格式', 'id'), ('沒有格式', '沒有格式', '回了 id'))
        cid = brain.cid_of('x.' * 90)
        self.assertEqual(len(cid), 64)
        self.assertNotIn('.', cid)

    def test_ask_bad_node(self):
        p = subprocess.run([sys.executable, str(TOP / 'modules/up/aos7_up_brain.py'),
                            'ask', '/tmp/not-existing-up-node', '你好'], capture_output=True, text=True, timeout=10)
        self.assertEqual(p.returncode, 2)
        self.assertIn('找不到 node', p.stderr)
        self.assertEqual(p.stdout, '')
