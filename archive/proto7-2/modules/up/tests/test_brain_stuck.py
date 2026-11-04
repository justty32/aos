"""不確定的 AI 呼叫逾期結案、人工放預留與唯讀狀態。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

import test_up_brain_multi as multi
from test_up_brain_multi import HOME, TOP, brain
from base import DaemonCase, read_json, write_json
from brain_node import setup


@unittest.skipUnless((HOME / 'tools/wf-init.sh').exists(), '找不到 workflows 模板')
class BrainStuckTests(DaemonCase):
    cli = multi.BrainMultiTests.cli
    send = multi.BrainMultiTests.send
    replies = multi.BrainMultiTests.replies
    start = multi.BrainMultiTests.start
    ended = multi.BrainMultiTests.ended
    session = multi.BrainMultiTests.session

    def setUp(self):
        super().setUp()
        self.node = setup(Path(self.mknode('bob')), interval_ms=200)
        cfg = dict(v=1, node=str(self.node), house=self.root, name='bob', you='you',
                   mail_root=self.root, litellm_url='', budget='budget/llm', holder='brain',
                   gateway='llm.fake', model='fake', deadline=3, fake_delay=2)
        write_json(str(self.node / '.aos/up.json'), cfg)

    def launch(self, crash=''):
        self.direct_round += 1
        write_json(str(self.direct / 'tock.json'), dict(round=self.direct_round, run=1))
        env = dict(os.environ, AOS7_ROOT=self.root, AOS7_NODE=str(self.node),
                   AOS7_NODE_ID='bob', AOS7_TASK=str(self.direct), AOS7_TID='brain',
                   AOS7_RUN='1', AOS7_TEST_CRASH=crash)
        p = subprocess.Popen([sys.executable, '-B', str(TOP / 'modules/up/aos7_up_brain.py'),
                              'brain', str(self.node)], env=env, start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.procs.append(p)
        return p

    def resume(self, finished):
        p = self.launch()
        try:
            self.wait_for(finished, timeout=15)
        finally:
            p.terminate()
            p.wait(5)

    def test_tree_kill_then_blocked_and_next(self):
        self.start(direct=True)
        first, second = self.send('A：先辦這封'), self.send('B：後面照常辦')
        cid = brain.call_id(first, 1)
        (self.node / 'llmcall').mkdir(exist_ok=True)
        (self.node / 'llmcall/.crash').write_text('after-intent')
        self.assertEqual(self.launch().wait(30), -9)
        unsure = self.node / 'brain/unsure.json'
        self.resume(unsure.exists)
        mark = read_json(str(unsure))
        self.assertEqual((mark['call'], mark['id']), (cid, first))
        self.assertEqual(self.replies(first), [])
        # 再看同一筆不能重設 since；期限仍未到。
        p = self.launch()
        time.sleep(.5)
        p.terminate()
        p.wait(5)
        self.assertEqual(read_json(str(unsure)), mark)
        time.sleep(max(0, 3.1 - (time.time() - mark['since'])))
        self.assertEqual(self.launch('up-brain-after-pending').wait(15), -9)
        self.assertEqual(read_json(str(self.node / 'brain/pending.json'))['status'], 'BLOCKED')
        self.assertEqual(self.launch('up-brain-after-mail').wait(15), -9)
        self.resume(lambda: self.ended(first))
        replies = self.replies(first)
        self.assertEqual([l['status'] for l in replies], ['BLOCKED'])
        body = replies[0]['body']
        plain = body
        # 回信只有白話：不露 call、帳、給維護者的指令、新手打不開的路徑與內部詞
        for word in (cid, '回合', 'adopt', '預留', 'LiteLLM', 'reply.json', 'call', '進階', '秒',
                     'ADVANCED', '假 AI', '系統', 'run', 'tock'):
            self.assertNotIn(word, plain)
        self.assertIn('bob 不會自己再問一次，要不要重問由你決定。', body)
        self.assertTrue(body.rstrip().endswith('練習用的 AI（不連網、不花錢），重寄不花錢。'), body)
        self.assertIn('等了約 1 分鐘', body)
        how = (self.node / 'brain/stuck' / cid / 'how.md').read_text()
        self.assertIn(cid, how)
        # 工作簿（STATE）那行白話：哪封信被打斷，不露 call id
        state = ''.join(p.read_text() for p in (self.node / 'wf/handoffs').glob('*/STATE.md'))
        self.assertIn('卡住：「A：先辦這封」問 AI 時被打斷', state)
        self.assertNotIn(cid, state)
        self.assertIn('什麼都不做', plain)
        self.assertIn('把同一句話再寄一次（跟第一次一樣用 aos7-up ask 寄）', plain)
        self.assertIn('練習用的 AI（不連網、不花錢）', plain)
        self.assertNotIn('多付', plain)
        self.assertNotIn(cid, replies[0]['title'])
        self.assertIn('帳上預留 1000000', how)
        self.assertIn('--reserve', how)
        self.assertEqual(body.count('怎麼辦：'), 1)
        self.assertFalse(unsure.exists())
        remote = read_json(str(self.node / 'llmcall/fake-remote.json'), {}) or {}
        self.assertLessEqual(remote.get('sends', {}).get(cid, 0), 1)
        # 不處理 A 的預留，brain 仍要先辦完 B。
        self.resume(lambda: self.ended(second))
        self.assertEqual([l['status'] for l in self.replies(second)], ['DONE'])
        ledger = read_json(str(self.node / 'budget/llm/ledger.json'))
        self.assertEqual(ledger['inflight'], 1000000)
        a_op = next(op for op in ledger['ops'].values() if op['key']['request'] == cid)
        self.assertEqual((a_op['stage'], a_op['amount']), ('reserved', 1000000))
        sends_before = read_json(str(self.node / 'llmcall/fake-remote.json'), {}).get('sends', {})
        # 直接跑人拿到的一行，不借用 brain 的結算函式。
        commands = [line for line in how.splitlines() if line.startswith('cd ')]
        self.assertEqual(len(commands), 1)
        self.assertIn(' && python3 ', commands[0])
        self.assertNotIn('aos7-budget cancel', commands[0])
        # adopt 拒絕時，&& 必須擋住後面的 call。
        reply_path = self.node / 'brain/stuck' / cid / 'reply.json'
        supplied = read_json(str(reply_path))
        write_json(str(reply_path), dict(supplied, call_id='wrong-call'))
        refused = subprocess.run(commands[0], shell=True, cwd=self.node, capture_output=True,
                                 text=True, timeout=30)
        self.assertNotEqual(refused.returncode, 0)
        self.assertEqual(read_json(str(self.node / 'budget/llm/ledger.json')), ledger)
        self.assertFalse((self.node / 'llmcall/llm' / cid / 'raw.json').exists())
        self.assertEqual(read_json(str(self.node / 'llmcall/fake-remote.json'), {}).get('sends', {}),
                         sends_before)
        write_json(str(reply_path), supplied)
        p = subprocess.run(commands[0], shell=True, cwd=self.node, capture_output=True,
                           text=True, timeout=30)
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        ledger = read_json(str(self.node / 'budget/llm/ledger.json'))
        self.assertEqual(ledger['inflight'], 0)
        a_op = next(op for op in ledger['ops'].values() if op['key']['request'] == cid)
        self.assertEqual(a_op['settle']['used'], 0)
        self.assertEqual(read_json(str(self.node / 'llmcall/fake-remote.json'), {}).get('sends', {}),
                         sends_before)
        self.assertNotIn('- [brain]', self.session())
        self.assertFalse(any((self.node / 'brain' / n).exists()
                             for n in ('task.json', 'pending.json', 'unsure.json')))
        remote = read_json(str(self.node / 'llmcall/fake-remote.json'))['sends']
        self.assertLessEqual(remote.get(cid, 0), 1)
        self.assertEqual(remote[brain.call_id(second, 1)], 1)

    def test_stuck_after_reserve_before_intent(self):
        self.start(direct=True)
        ident = self.send('預留後還沒送出的信')
        cid = brain.call_id(ident, 1)
        (self.node / 'llmcall').mkdir(exist_ok=True)
        (self.node / 'llmcall/.crash').write_text('after-reserve')
        self.assertEqual(self.launch().wait(30), -9)
        ledger = read_json(str(self.node / 'budget/llm/ledger.json'))
        self.assertEqual(ledger['inflight'], 1000000)
        cfg = read_json(str(self.node / '.aos/up.json'))
        # 不恢復 llmcall；status 唯讀，不能順手把 intent 補出來。
        letter = brain.stuck_reply(self.node, cid, 1, 99, cfg)[1]
        self.assertNotIn('aos7-budget', letter)
        body = (self.node / 'brain/stuck' / cid / 'how.md').read_text()
        self.assertIn('這筆還沒送出給 AI', body)
        self.assertIn('aos7-budget cancel', body)
        self.assertIn('aos7-budget settle', body)
        self.assertNotIn('adopt', body)
        self.assertFalse((self.node / 'brain/stuck' / cid / 'reply.json').exists())
        sends_before = read_json(str(self.node / 'llmcall/fake-remote.json'), {}).get('sends', {})
        self.assertNotIn(cid, sends_before)
        commands = [line for line in body.splitlines() if line.startswith('cd ')]
        self.assertEqual(len(commands), 1)
        p = subprocess.run(commands[0], shell=True, cwd=self.node, capture_output=True,
                           text=True, timeout=30)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        ledger = read_json(str(self.node / 'budget/llm/ledger.json'))
        self.assertEqual((ledger['inflight'], ledger['used']), (0, 0))
        a_op = next(op for op in ledger['ops'].values() if op['key']['request'] == cid)
        self.assertEqual(a_op['settle']['used'], 0)
        sends_after = read_json(str(self.node / 'llmcall/fake-remote.json'), {}).get('sends', {})
        self.assertEqual(sends_after, sends_before)
        self.assertNotIn(cid, sends_after)

    def test_stuck_wording_real_ai(self):
        cfg = dict(read_json(str(self.node / '.aos/up.json')), model='chatgpt-x')
        title, body, line, fix = brain.stuck_reply(self.node, 'some-call', 2, 700, cfg, '幫我寫一首短詩')
        plain = body
        self.assertIn('等了約 12 分鐘', plain)
        self.assertEqual(line, '卡住：「幫我寫一首短詩」問 AI 時被打斷')
        self.assertIn('「幫我寫一首短詩」', title)
        self.assertIn('「幫我寫一首短詩」', plain)
        self.assertIn('真 AI', plain)
        self.assertIn('多付一次', plain)
        self.assertNotIn('不花錢', plain)
        for word in ('some-call', '回合', '預留', '進階', 'call'):
            self.assertNotIn(word, plain + title + fix + line)
        self.assertIn('some-call', (self.node / 'brain/stuck/some-call/how.md').read_text())

    def test_saved_request_without_usable_status(self):
        cid = 'saved-but-not-sent'
        saved = self.node / 'llmcall/llm' / cid / 'request.json'
        saved.parent.mkdir(parents=True)
        write_json(str(saved), dict(request={}, req_sha='sha', reserve=1000000))
        cfg = read_json(str(self.node / '.aos/up.json'))
        cases = [
            subprocess.CompletedProcess([], 0, json.dumps(dict(gateway=None, ledger=dict(stage=None))), ''),
            subprocess.CompletedProcess([], 0, json.dumps(dict(gateway=None, ledger=dict(error='壞帳'))), ''),
            subprocess.CompletedProcess([], 3, '{}', ''),
            subprocess.CompletedProcess([], 0, '{', ''),
        ]
        for result in cases:
            with self.subTest(stdout=result.stdout), patch.object(brain, 'run', return_value=result):
                brain.stuck_reply(self.node, cid, 1, 99, cfg)
                body = (self.node / 'brain/stuck' / cid / 'how.md').read_text()
                self.assertNotIn('adopt', body)
                self.assertNotIn('aos7-budget cancel', body)
                self.assertFalse(any(line.startswith('cd ') for line in body.splitlines()))
                self.assertFalse((self.node / 'brain/stuck' / cid / 'reply.json').exists())

    def up_status(self):
        return self.cli('modules/up/aos7-up', 'status', self.node).splitlines()

    def test_status_readonly_and_unsure(self):
        self.assertEqual(self.up_status()[1], '信：bob 還沒收到信；你的信箱有 0 封回信還沒看')
        first = self.send('辦完的信')
        self.cli('modules/mail/aos7-mail', 'done', 'bob', first, 'DONE', '做完了', '--root', self.root)
        ident = self.send('卡住的標題')
        self.send('排隊的信')
        self.cli('modules/mail/aos7-mail', 'send', 'bob', 'you', 'BLOCKED', 'BLOCKED', '--root', self.root)
        # 只有說卡住的信：看看就好，不叫人照信做（卡住那行說過不用動手）
        self.assertTrue(self.up_status()[1].endswith(f'（1 封說卡住了；信在 {self.root}/you/inbox，打開看看就好）'))
        self.cli('modules/mail/aos7-mail', 'send', 'bob', 'you', 'NEEDS-USER', 'NEEDS-USER', '--root', self.root)
        expected = ('信：bob 一共收到 3 封，回了 1 封、正在辦 1 封、排隊 1 封；你的信箱有 3 封回信還沒看'
                    f'（1 封要你決定、1 封說卡住了；信在 {self.root}/you/inbox，打開照信做）')
        self.assertEqual(self.up_status()[1], expected)
        unsure = self.node / 'brain/unsure.json'
        unsure.parent.mkdir(exist_ok=True)
        write_json(str(unsure), dict(call=brain.call_id(ident, 1), id=ident, since=time.time()-1))
        before = {str(p): p.read_bytes() for p in Path(self.root).rglob('*') if p.is_file()}
        lines = self.up_status()
        self.assertEqual(len(lines), 7)
        self.assertEqual(lines[1], expected)
        # 卡住那行：哪封信、被打斷、還要等多久就會寄信給你（不露已等秒數與時限）
        self.assertEqual(lines[2], '卡住了：「卡住的標題」問 AI 時被打斷，bob 不知道 AI 回了沒；不用動手，約 1 分鐘內 bob 會寄信給你')
        self.assertEqual(before, {str(p): p.read_bytes() for p in Path(self.root).rglob('*') if p.is_file()})
        write_json(str(unsure), dict(call=brain.call_id(ident, 1), id=ident, since=time.time()-10))
        self.assertTrue(self.up_status()[2].endswith('不用動手，馬上 bob 會寄信給你'))
        unsure.write_text('{')
        self.assertEqual(len(self.up_status()), 6)
        write_json(str(unsure), dict(id='已離開信箱', since=time.time()))
        self.assertEqual(len(self.up_status()), 6)
        # 問了沒收到回答（卡住那筆）也算一次，另外註明
        asked = self.node / 'llmcall/llm' / brain.call_id(ident, 1)
        asked.mkdir(parents=True, exist_ok=True)
        (asked / 'request.json').write_text('{}')
        self.assertTrue(self.up_status()[4].endswith('bob 一共問過 AI 1 次（其中 1 次還沒收到回答）'))
        # 說卡住的那封不算「回了」：回了 1 封、1 封卡住
        unsure.unlink()
        self.cli('modules/mail/aos7-mail', 'done', 'bob', ident, 'BLOCKED', '卡住了', '--root', self.root)
        self.assertTrue(self.up_status()[1].startswith('信：bob 一共收到 3 封，回了 1 封、1 封卡住（已寄信說明）、正在辦 1 封；'))
        # 人看過（信移到 done）也一樣
        Path(self.root, 'you/inbox/done').mkdir(exist_ok=True)
        for p in Path(self.root, 'you/inbox').glob('*.md'):
            p.rename(p.parent / 'done' / p.name)
        self.assertTrue(self.up_status()[1].startswith('信：bob 一共收到 3 封，回了 1 封、1 封卡住（已寄信說明）、正在辦 1 封；你的信箱有 0 封'))

    def test_open_line_neutral(self):
        brain.open_line(self.node, 'x', '英文草稿已完成；DONE ✅ 已結案 已收線（完成）✔ ~~ (done) [done]')
        self.cli('modules/wfnode/aos7-wfnode', 'check', self.node)
        self.assertIn('英文草稿已做好；done', self.session())

    def test_raw_wait_does_not_time_out(self):
        ident = self.send('已回但帳還沒對上')
        work = self.node / 'brain'
        work.mkdir(exist_ok=True)
        write_json(str(work / 'unsure.json'), dict(call=brain.call_id(ident, 1), id=ident, since=0))
        with patch.object(brain, 'ask_ai', side_effect=brain.Later(unsure=False)):
            brain.once(self.node, 1)
        self.assertFalse((work / 'unsure.json').exists())
        self.assertEqual(self.replies(ident), [])

    def test_ask_ai_raw_flag_and_success_cleanup(self):
        ident = self.send('測試回條')
        letter = json.loads(brain.mail(self.node, 'read', 'bob', '--json'))[0]
        cid = brain.call_id(ident, 1)
        raw = self.node / 'llmcall/llm' / cid / 'raw.json'
        raw.parent.mkdir(parents=True)
        work = self.node / 'brain'
        work.mkdir(exist_ok=True)
        cfg = read_json(str(self.node / '.aos/up.json'))
        with patch.object(brain, 'request', return_value=work / 'req.json'), patch.object(brain, 'run') as run:
            run.return_value = subprocess.CompletedProcess([], 3, '', '')
            with self.assertRaises(brain.Later) as caught:
                brain.ask_ai(self.node, letter, cid, cfg)
            self.assertTrue(caught.exception.unsure)
            raw.write_text('{}')
            with self.assertRaises(brain.Later) as caught:
                brain.ask_ai(self.node, letter, cid, cfg)
            self.assertFalse(caught.exception.unsure)
            (work / 'unsure.json').write_text('{}')
            run.return_value = subprocess.CompletedProcess([], 0, '{"outcome":"answered","text":"回信：好"}', '')
            self.assertEqual(brain.ask_ai(self.node, letter, cid, cfg), '回信：好')
            self.assertFalse((work / 'unsure.json').exists())

    def test_blocked_without_saved_request(self):
        ident = self.send('還沒預留就卡住')
        work = self.node / 'brain'
        work.mkdir(exist_ok=True)
        write_json(str(work / 'unsure.json'), dict(call=brain.call_id(ident, 1), id=ident, since=0))
        with patch.object(brain, 'ask_ai', side_effect=brain.Later()):
            brain.once(self.node, 1)
        replies = self.replies(ident)
        self.assertEqual([l['status'] for l in replies], ['BLOCKED'])
        how = (work / 'stuck' / brain.call_id(ident, 1) / 'how.md').read_text()
        self.assertIn('帳上沒有這筆的預留', how)
        self.assertNotIn('adopt', how)
        self.assertFalse((work / 'stuck' / brain.call_id(ident, 1) / 'reply.json').exists())
        self.assertFalse((work / 'unsure.json').exists())
