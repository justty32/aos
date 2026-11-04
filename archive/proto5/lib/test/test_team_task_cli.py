"""第 1 隊 T-handoff／T-ask 的人用指令：aos-team task ls／show／cancel／reassign、wait ls、answer。"""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import aos_team_ask_cli as ask_cli
import aos_team_format as fmt
import aos_team_requests as requests
import aos_team_task as task
import aos_team_task_cli as task_cli

PROTO = Path(__file__).resolve().parents[2]
EXAMPLES = PROTO / 'spec' / 'team' / 'examples'
ROSTER = {'project': '../p', 'tz': 'Asia/Taipei',
          'members': {'lead': {'template': 'lead', 'mail_to': ['worker-1', 'worker-2', 'reviewer', 'human']},
                      'worker-1': {'template': 'worker', 'mail_to': ['lead', 'human']},
                      'worker-2': {'template': 'worker', 'mail_to': ['lead', 'human']},
                      'reviewer': {'template': 'reviewer', 'mail_to': ['lead', 'human']}}}


class Base(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='aos-team-taskcli-'))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.team = self.root / 'team'
        self.team.mkdir()
        (self.root / 'p').mkdir()
        (self.team / 'team.json').write_text(json.dumps(ROSTER), encoding='utf-8')
        self.lay = fmt.Layout(self.team)
        for d in self.lay.skeleton(ROSTER['members']):
            d.mkdir(parents=True, exist_ok=True)
        self.roster = fmt.load_roster(self.team)

    def call(self, fn, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = fn(str(self.team), list(args))
        return code, out.getvalue()

    def err(self, code, fn, *args):
        with self.assertRaises(fmt.TeamError) as cm:
            self.call(fn, *args)
        self.assertEqual(cm.exception.code, code, cm.exception.msg)
        return cm.exception.msg

    def open(self, **over):
        req = json.loads((EXAMPLES / 'request-handoff.json').read_text(encoding='utf-8'))
        req.update(id=fmt.new_id('lead'), **over)
        return requests.handle(self.lay, self.roster, req)

    def outbox(self):
        files = fmt.json_files(self.lay.outbox('human'))
        return [fmt.read_outbox_file(p, self.roster)[1] for p in files]


class TaskCliTests(Base):
    def test_ls_and_show(self):
        code, out = self.call(task_cli.cmd_task, 'ls')
        self.assertIn('沒有進行中的任務單', out)
        self.open()
        self.open(goal='第二件事' * 20)
        code, out = self.call(task_cli.cmd_task, 'ls')
        lines = out.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn('t-0001  queued', lines[0])
        self.assertIn('worker-1', lines[0])
        self.assertIn('rev1 第1/3次', lines[0])
        self.assertTrue(lines[1].endswith('…'))
        t = task.load(self.lay, 't-0002')
        t['status'] = 'done'
        task.save(self.lay, t)
        self.assertEqual(len(self.call(task_cli.cmd_task, 'ls')[1].splitlines()), 1)
        self.assertEqual(len(self.call(task_cli.cmd_task, 'ls', '--all')[1].splitlines()), 2)
        data = json.loads(self.call(task_cli.cmd_task, 'ls', '--all', '--json')[1])
        self.assertEqual([x['id'] for x in data], ['t-0001', 't-0002'])
        code, out = self.call(task_cli.cmd_task, 'show', 't-0001')
        self.assertIn('負責人：worker-1（開單：lead）', out)
        self.assertIn('0. 檔案在：AGENTS.md', out)
        self.assertIn('3. （審查員判）', out)
        self.assertIn('opened  -→queued  by lead', out)
        self.assertEqual(json.loads(self.call(task_cli.cmd_task, 'show', 't-0001', '--json')[1])['id'], 't-0001')
        self.err('NoSuchTask', task_cli.cmd_task, 'show', 't-0099')
        self.err('Usage', task_cli.cmd_task, 'fly')

    def test_show_review_subtask_keeps_parent_numbering(self):
        """astra 審查 M5：aos-team task show 對審查子單也要用父單的原編號（board、render_review 已修，這條之前漏了）。"""
        self.open()
        task.step(self.lay, 't-0001', {'type': 'delivered', 'src': 'd', 'rev': 1, 'attempt': 1})
        task.step(self.lay, 't-0001', {'type': 'report', 'src': 'r', 'by': 'worker-1', 'rev': 1, 'status': 'DONE'})
        task.step(self.lay, 't-0001', {'type': 'verified', 'src': 'v', 'pass': True, 'rev': 1, 'attempt': 1})
        task.open_review(self.lay, self.roster, 't-0001', 'o', 1, 1)
        code, out = self.call(task_cli.cmd_task, 'show', 't-0001.r1')
        self.assertIn('3. （審查員判）', out)          # judge 在 request-handoff.json 的 done_when 排第 3
        self.assertNotIn('0. （審查員判）', out)

    def test_cancel_and_reassign_are_requests(self):
        self.open()
        code, out = self.call(task_cli.cmd_task, 'cancel', 't-0001', '--reason', '不做了')
        self.assertIn('已交給郵差：取消 t-0001', out)
        code, out = self.call(task_cli.cmd_task, 'reassign', 't-0001', 'worker-2')
        self.assertIn('改派給 worker-2', out)
        reqs = sorted(self.outbox(), key=lambda r: r['kind'])
        self.assertEqual([(r['kind'], r['task']) for r in reqs], [('cancel', 't-0001'), ('reassign', 't-0001')])
        self.assertEqual(reqs[0]['reason'], '不做了')
        self.assertEqual(reqs[1]['assignee'], 'worker-2')
        # 郵差照申請做得下去
        requests.handle(self.lay, self.roster, reqs[1])
        self.assertEqual(task.load(self.lay, 't-0001')['assignee'], 'worker-2')
        self.err('BadAssignee', task_cli.cmd_task, 'reassign', 't-0001', 'ghost')
        t = task.load(self.lay, 't-0001')
        t['status'] = 'cancelled'
        task.save(self.lay, t)
        self.err('Closed', task_cli.cmd_task, 'cancel', 't-0001')
        self.err('Closed', task_cli.cmd_task, 'reassign', 't-0001', 'worker-1')
        self.err('NoSuchTask', task_cli.cmd_task, 'cancel', 't-0042')


class WaitAnswerTests(Base):
    def ask(self):
        req = json.loads((EXAMPLES / 'request-ask.json').read_text(encoding='utf-8'))
        req['reply_to'] = None
        requests.handle(self.lay, self.roster, req)

    def test_wait_and_answer(self):
        self.assertIn('沒有在等你回答的問題', self.call(ask_cli.cmd_wait, 'ls')[1])
        self.ask()
        out = self.call(ask_cli.cmd_wait, 'ls')[1]
        self.assertIn('q-0001  worker-1 問：', out)
        self.assertEqual(json.loads(self.call(ask_cli.cmd_wait, 'ls', '--json')[1])[0]['id'], 'q-0001')
        code, out = self.call(ask_cli.cmd_answer, 'q-0001', 'main')
        self.assertEqual(code, 0)
        self.assertIn('已交給郵差：回答 q-0001 給 worker-1', out)
        self.assertNotIn('提醒', out)
        req = self.outbox()[0]
        self.assertEqual((req['kind'], req['q'], req['text']), ('answer', 'q-0001', 'main'))
        code, out = self.call(ask_cli.cmd_answer, 'q-0001', '先別動', '等我')
        self.assertIn('提醒', out)
        # 郵差處理第一份後，再答就 Closed
        requests.handle(self.lay, self.roster, req)
        self.err('Closed', ask_cli.cmd_answer, 'q-0001', 'main')
        self.err('NoSuchQuestion', ask_cli.cmd_answer, 'q-0009', 'x')
        self.err('Usage', ask_cli.cmd_answer, 'q-0001')

    def test_wait_ls_shows_tag_prefix(self):
        """借用 kind=ask 的 access_request／persona_propose：wait ls 靠 tag 印 [權限]／[人格] 前綴，一般問題不加
        （09-24 W2C 待拍題，2026-09-24 已裁決要加）。"""
        req = json.loads((EXAMPLES / 'request-ask.json').read_text(encoding='utf-8'))
        req['reply_to'] = None
        requests.handle(self.lay, self.roster, req)                              # 一般問題，沒有 tag
        req2 = dict(req, id='1790000000200000001-4242-worker-1', tag='access', reply_to=None,
                   question='想申請多掛一個資料夾')
        requests.handle(self.lay, self.roster, req2)
        req3 = dict(req, id='1790000000200000002-4242-worker-1', tag='persona', reply_to=None,
                   question='想改自己的人格')
        requests.handle(self.lay, self.roster, req3)
        out = self.call(ask_cli.cmd_wait, 'ls')[1]
        lines = out.splitlines()
        self.assertTrue(any(l.startswith('q-0001  worker-1 問：') for l in lines))
        self.assertTrue(any(l.startswith('[權限] q-0002  worker-1 問：想申請多掛一個資料夾') for l in lines))
        self.assertTrue(any(l.startswith('[人格] q-0003  worker-1 問：想改自己的人格') for l in lines))

    def test_cli_end_to_end(self):
        self.ask()
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', AOS_TEAM_HOME=str(self.team))
        cli = str(PROTO / 'cli' / 'aos-team')
        r = subprocess.run([sys.executable, cli, 'wait', 'ls'], capture_output=True, text=True, timeout=30, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('q-0001', r.stdout)
        r = subprocess.run([sys.executable, cli, 'answer', 'q-0007', 'x'], capture_output=True, text=True,
                           timeout=30, env=env)
        self.assertEqual(r.returncode, 1)
        self.assertIn('NoSuchQuestion', r.stderr)
        r = subprocess.run([sys.executable, cli, 'task', 'ls'], capture_output=True, text=True, timeout=30, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == '__main__':
    unittest.main()
