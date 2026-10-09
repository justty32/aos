"""一封信跨回合：真 daemon／ledger、SIGKILL 重接與記憶、技能整合。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

TOP = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(TOP / p) for p in
               ('modules/mail', 'tests', 'modules/up', 'modules/up/examples')]
from base import DaemonCase, read_json, write_json
from brain_node import setup
import aos7_up_brain as brain
from aos7_mail import letter

HOME = Path(os.environ.get('AOS7_WF_HOME', '~/repo/workflows')).expanduser()


@unittest.skipUnless((HOME / 'tools/wf-init.sh').exists(), '找不到 workflows 模板')
class BrainMultiTests(DaemonCase):
    def setUp(self):
        super().setUp()
        self.node = setup(Path(self.mknode('bob')), interval_ms=200)

    def cli(self, tool, *args):
        p = subprocess.run([sys.executable, '-B', str(TOP / tool), *map(str, args)],
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        return p.stdout

    def send(self, text):
        return json.loads(self.cli('modules/mail/aos7-mail', 'send', 'you', 'bob',
                                   'REQUEST', text, '--root', self.root))['id']

    def replies(self, ident):
        return [l for p in (Path(self.root) / 'you/inbox').rglob('*.md')
                if (l := letter(p))['re'] == ident]

    def task(self):
        return read_json(str(self.node / 'brain/task.json'), {}) or {}

    def session(self):
        return (self.node / 'wf/SESSION-LOG.md').read_text()

    def state(self):
        return '\n'.join(p.read_text() for p in
                         (self.node / 'wf/handoffs').glob('*/STATE.md'))

    def start(self, direct=False):
        if direct:
            self.set_tasks(str(self.node), [t for t in self.tasks(str(self.node))
                                           if t['name'] != 'brain'])
            self.direct = self.node / 'direct-brain'
            self.direct.mkdir()
            self.direct_round = 0
        self.start_daemon(register=['bob'])
        self.wait_round(2, 'bob')

    def launch(self, crash=''):
        # 一次只給一個新 tock；恢復程序不會搶跑下一個要殺的回合。
        self.direct_round += 1
        write_json(str(self.direct / 'tock.json'), dict(round=self.direct_round, run=1))
        env = dict(os.environ, AOS7_ROOT=self.root, AOS7_NODE=str(self.node),
                   AOS7_NODE_ID='bob', AOS7_TASK=str(self.direct), AOS7_TID='brain',
                   AOS7_RUN='1', AOS7_TEST_CRASH=crash)
        p = subprocess.Popen([sys.executable, '-B', str(TOP / 'modules/up/aos7_up_brain.py'),
                              'brain', str(self.node)], env=env,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.procs.append(p)
        return p

    def resume(self, finished):
        p = self.launch()
        self.wait_for(finished, timeout=30)
        p.terminate()
        p.wait(5)

    def ended(self, ident):
        return (any(l['status'] != 'PROGRESS' for l in self.replies(ident))
                and not any((self.node / 'brain' / n).exists()
                            for n in ('task.json', 'last.md', 'pending.json')))

    def wait_end(self, ident):
        self.wait_for(lambda: self.ended(ident), timeout=45,
                      msg='沒有結案或 brain 沒清掉暫存狀態')

    def assert_open(self, ident):
        rows = self.session().splitlines()
        mark = '- [brain] 信 ' + ident + '：'
        self.assertEqual(sum(r.startswith(mark) for r in rows), 1)
        first = next(i for i, r in enumerate(rows) if r.startswith('## '))
        self.assertTrue(rows[first + 1].startswith(mark))

    def assert_clean(self, ident):
        self.assertTrue(self.ended(ident))
        self.assertNotIn('- [brain] 信 ' + ident, self.session())

    def assert_mail(self, ident, status, progress=0):
        replies = self.replies(ident)
        self.assertCountEqual([l['status'] for l in replies],
                              [status] + ['PROGRESS'] * progress,
                              '\n'.join(l.get('body', '') for l in replies))

    def assert_calls(self, ident, steps):
        ids = [brain.cid_of(ident if k == 1 else f'{ident}-s{k}')
               for k in range(1, steps + 1)]
        remote = read_json(str(self.node / 'llmcall/fake-remote.json'))
        self.assertEqual(remote['sends'], dict.fromkeys(ids, 1), '不應重問或多問 AI')
        used = [read_json(str(self.node / 'llmcall/llm' / cid / 'receipt.json'))['used']
                for cid in ids]
        self.assertTrue(all(n > 0 for n in used))
        return used

    def assert_state(self, ident, continues):
        rows = self.state().splitlines()
        for k in range(1, continues + 1):
            self.assertEqual(sum(f'第 {k} 回合 {ident}：' in r for r in rows), 1)
        self.assertEqual(sum(('回了 ' + ident) in r for r in rows), 1)

    def test_eight_rounds(self):
        ident = self.send('請分 8 回合做完')
        self.start()
        self.wait_for(lambda: self.task().get('id') == ident, timeout=30)
        self.assert_open(ident)
        self.wait_end(ident)
        self.assert_mail(ident, 'DONE', progress=1)
        self.assertIn('第 5 回合', next(l['title'] for l in self.replies(ident)
                                      if l['status'] == 'PROGRESS'))
        used = self.assert_calls(ident, 8)
        self.assertLessEqual(used[7], used[1] * 1.3, f'各回合 used：{used}')
        self.assert_state(ident, 7)
        journal = [json.loads(r) for r in (self.node / 'notes/journal.jsonl').read_text().splitlines()]
        self.assertEqual([r['step'] for r in journal if r.get('by') == 'brain'
                          and r.get('re') == ident], list(range(1, 8)))
        self.assert_clean(ident)
        self.cli('modules/wfnode/aos7-wfnode', 'check', self.node)

    def test_three_sigkills_resume(self):
        cfg = read_json(str(self.node / '.aos/up.json'))
        write_json(str(self.node / '.aos/up.json'), dict(cfg, progress_every=2))
        self.start(direct=True)
        ident = self.send('請分 4 回合做完')
        self.assertEqual(self.launch('up-brain-after-llm').wait(30), -9)
        self.assertEqual(self.replies(ident), [])
        self.resume(lambda: self.task().get('step') == 2)
        self.assert_open(ident)
        self.assertEqual(self.launch('up-brain-after-step').wait(30), -9)
        self.assertEqual(self.task()['step'], 2, '殺在 task 寫入前')
        self.assert_mail(ident, 'PROGRESS')
        self.resume(lambda: self.task().get('step') == 3)
        self.resume(lambda: self.task().get('step') == 4)
        self.assertEqual(self.launch('up-brain-after-pending').wait(30), -9)
        self.assertTrue((self.node / 'brain/pending.json').exists())
        self.assertFalse(any(l['status'] == 'DONE' for l in self.replies(ident)))
        self.resume(lambda: self.ended(ident))
        self.assert_mail(ident, 'DONE', progress=1)
        self.assertIn('第 2 回合', next(l['title'] for l in self.replies(ident)
                                      if l['status'] == 'PROGRESS'))
        self.assert_calls(ident, 4)
        self.assert_state(ident, 3)
        journal = [json.loads(r) for r in (self.node / 'notes/journal.jsonl').read_text().splitlines()]
        self.assertEqual([r['step'] for r in journal if r.get('re') == ident], [1, 2, 3])
        self.assert_clean(ident)

    def test_stall_then_next_letter(self):
        ident = self.send('沒進展的事')
        self.start()
        self.wait_end(ident)
        self.assert_mail(ident, 'NEEDS-USER')
        self.assert_calls(ident, 4)
        self.assert_clean(ident)
        other = self.send('普通信照常做')
        self.wait_end(other)
        self.assert_mail(other, 'DONE')
        remote = read_json(str(self.node / 'llmcall/fake-remote.json'))['sends']
        self.assertEqual(len(remote), 5)
        self.assertEqual(remote[brain.cid_of(other)], 1)
        self.assert_clean(other)

    def test_needs_user_immediately(self):
        ident = self.send('要你決定的事')
        self.start()
        self.wait_end(ident)
        self.assert_mail(ident, 'NEEDS-USER')
        self.assert_calls(ident, 1)
        self.assert_clean(ident)

    def test_compact_preserves_open_and_shrinks(self):
        # 門檻與保留筆數調小，16 回合內 journal 會超過門檻數次。
        write_json(str(self.node / 'compact.json'), {'max_bytes': 1500, 'keep_recent': 1, 'summary_max_chars': 60})
        ident = self.send('請分 16 回合做完')
        self.start()
        log = self.node / 'compact/log.jsonl'
        observed_open = compact_open = False

        def observe():
            nonlocal observed_open, compact_open
            if self.task().get('id') == ident and not self.replies_done(ident):
                self.assert_open(ident)
                observed_open = True
                if log.exists() and log.stat().st_size:
                    compact_open = True
            return self.ended(ident)

        self.wait_for(observe, timeout=60)
        self.assert_mail(ident, 'DONE', progress=3)
        self.assert_clean(ident)
        self.assertTrue(observed_open, '必須觀察到進行中的 open 行')
        jobs = [json.loads(r) for r in log.read_text().splitlines()] if log.exists() else []
        jobs = [j for j in jobs if j.get('file') == 'notes/journal.jsonl' and 'job' in j]
        self.assertTrue(jobs, 'compact 沒有整理 journal')
        self.assertTrue(compact_open, '整理後、DONE 前仍須有 open 行')
        self.assertLessEqual(jobs[0]['after_bytes'], jobs[0]['before_bytes'] * 0.4, 'journal 須縮小至少 60%')

    def replies_done(self, ident):
        return any(l['status'] != 'PROGRESS' for l in self.replies(ident))

    def test_local_skill_without_budget(self):
        skills = self.node / 'skills'
        skills.mkdir()
        for source in (TOP / 'modules/skills/library').iterdir():
            (skills / source.name).symlink_to(source)
        self.cli('modules/skills/aos7-skills', 'index', self.node)
        ident = self.send('看看信箱，把別的 agent 寄來的信辦掉，分 2 回合')
        self.start()
        self.wait_for(lambda: self.task().get('id') == ident, timeout=30)
        self.assertEqual(self.task()['skill'], 'aos-inbox')
        self.assertFalse((self.node / 'brain/.pick').exists())
        self.wait_end(ident)
        self.assert_mail(ident, 'DONE')
        logs = [json.loads(r) for r in (skills / '.pick/log.jsonl').read_text().splitlines()]
        self.assertTrue(any(r['via'] == 'local' and r['picked'] == 'aos-inbox' for r in logs))
        self.assertTrue(all(r['via'] == 'local' and not r.get('used') for r in logs))
        used = self.assert_calls(ident, 2)
        ledger = read_json(str(self.node / 'budget/llm/ledger.json'))
        self.assertEqual(ledger['used'], sum(used))
        self.assertEqual(ledger['inflight'], 0)
        self.assertTrue(ledger['ops'])
        self.assertTrue(all(op['key']['holder'] == 'brain' for op in ledger['ops'].values()))
        self.assertFalse((self.node / 'brain/.pick').exists())
        self.assert_clean(ident)
