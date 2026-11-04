"""第 1 隊 astra 審查必修的回歸測試：審查重播、逾期通知、問題綁單、派工信才推狀態、事件要帶版本、
審查子單終止、init 崩潰窗口、團隊控制資料不准可寫多掛、rm 中斷、換模板。"""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import aos_agent_init
from aos_agent_home import AgentError
import aos_team
import aos_team_ask as ask
import aos_team_format as fmt
import aos_team_requests as requests
import aos_team_task as task

PROTO = Path(__file__).resolve().parents[2]
ROSTER = {'project': '../p', 'tz': 'Asia/Taipei',
          'members': {'lead': {'template': 'lead', 'mail_to': ['worker-1', 'worker-2', 'reviewer', 'human']},
                      'worker-1': {'template': 'worker', 'mail_to': ['lead', 'human']},
                      'worker-2': {'template': 'worker', 'mail_to': ['lead', 'human']},
                      'reviewer': {'template': 'reviewer', 'mail_to': ['lead', 'human']}}}


class Base(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='aos-team-fix-'))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.team = self.root / 'team'
        self.team.mkdir()
        (self.root / 'p').mkdir()
        (self.team / 'team.json').write_text(json.dumps(ROSTER), encoding='utf-8')
        self.lay = fmt.Layout(self.team)
        for d in self.lay.skeleton(ROSTER['members']):
            d.mkdir(parents=True, exist_ok=True)
        self.roster = fmt.load_roster(self.team)
        self.letters = []

    def run_effects(self, effects, src='x'):
        for k, e in enumerate(effects):
            if e['do'] == 'letter':
                self.letters.append(e)
            elif e['do'] == 'step':
                self.run_effects(task.step(self.lay, e['task'], e['event']), src)
            elif e['do'] == 'open_review':
                self.run_effects(task.open_review(self.lay, self.roster, e['task'], '%s.e%d' % (src, k),
                                                  e['rev'], e['attempt']), src)

    def open(self, **over):
        req = {'id': fmt.new_id('lead'), 'from': 'lead', 'kind': 'handoff', 'at': fmt.now_iso(),
               'assignee': 'worker-1', 'workflow': '無', 'goal': 'g',
               'done_when': [{'kind': 'file_exists', 'path': 'a'}, {'kind': 'judge', 'text': '好'}]}
        req.update(over)
        self.run_effects(requests.handle(self.lay, self.roster, req), req['id'])

    def t(self, tid='t-0001'):
        return task.load(self.lay, tid)

    def deliver(self, tid='t-0001'):
        e = [x for x in self.letters if x.get('dispatch', {}).get('task') == tid][-1]
        ltr = dict(e, id='L%d' % len(self.letters))
        task.letter_delivered(self.lay, ltr, e['dispatch'])
        task.letter_picked_up(self.lay, ltr, e['dispatch'])

    def done(self, by='worker-1', rev=1):
        ltr = {'id': fmt.new_id(by), 'from': by, 'to': 'lead', 'status': 'DONE', 'reply_to': 't-0001', 'rev': rev,
               'text': 'x', 'at': fmt.now_iso()}
        self.run_effects(task.on_letter(self.lay, self.roster, ltr), ltr['id'])

    def to_reviewing(self):
        self.open()
        self.deliver()
        self.done()
        return task.step(self.lay, 't-0001', {'type': 'verified', 'src': 'v', 'pass': True, 'rev': 1, 'attempt': 1})


class StateMachineFixTests(Base):
    def test_open_review_replay_after_reassign_is_stale(self):
        effects = self.to_reviewing()
        self.assertEqual(effects[0]['do'], 'open_review')
        first = task.open_review(self.lay, self.roster, 't-0001', 'OR', 1, 1)
        self.assertEqual(first[0]['to'], 'reviewer')
        req = {'id': fmt.new_id('lead'), 'from': 'lead', 'kind': 'reassign', 'at': fmt.now_iso(), 'task': 't-0001',
               'assignee': 'worker-2'}
        self.run_effects(requests.handle(self.lay, self.roster, req))
        self.assertEqual(task.open_review(self.lay, self.roster, 't-0001', 'OR', 1, 1), first)   # 同 src＝同結果
        self.assertEqual(task.open_review(self.lay, self.roster, 't-0001', 'OR2', 1, 1), [])     # 過期的動作
        self.assertEqual(task.open_review(self.lay, self.roster, 't-0001', 'OR2', 1, 1), [])
        self.assertEqual(sorted(p.name for p in fmt.json_files(self.lay.tasks)), ['t-0001.json', 't-0001.r1.json'])
        self.assertEqual(self.t()['status'], 'queued')
        self.assertEqual(self.t()['history'][-1]['event'], 'ignored:stale_review')

    def test_expire_notices_survive_replay(self):
        self.open(deadline_minutes=1)
        [(tid, ev)] = task.due_deadlines(self.lay, now='2099-01-01T00:00:00+00:00')
        first = task.step(self.lay, tid, ev, ev['at'])
        self.assertEqual(self.t()['status'], 'failed')
        self.assertEqual(task.step(self.lay, tid, ev, ev['at']), first)      # 郵差崩了重跑：同一份通知
        self.assertTrue(first)
        self.assertEqual(task.due_deadlines(self.lay, now='2099-01-01T00:00:00+00:00'), [])

    def test_non_dispatch_letters_do_not_advance(self):
        self.open()
        progress = {'id': 'P1', 'from': 'lead', 'to': 'worker-1', 'status': 'PROGRESS', 'reply_to': 't-0001', 'rev': 1}
        self.assertEqual(task.letter_delivered(self.lay, progress, None), [])
        self.assertEqual(task.letter_delivered(self.lay, progress, {'task': 't-0001', 'rev': 1, 'attempt': 2}), [])
        self.assertEqual(self.t()['status'], 'queued')
        self.deliver()
        self.assertEqual(self.t()['status'], 'working')

    def test_versionless_events_rejected(self):
        self.open()
        self.deliver()
        self.done()
        with self.assertRaises(fmt.TeamError) as cm:
            task.step(self.lay, 't-0001', {'type': 'verified', 'src': 'v', 'pass': True})
        self.assertEqual(cm.exception.code, 'BadEvent')
        self.assertEqual(self.t()['status'], 'verifying')

    def test_review_sub_cancelled_blocks_parent(self):
        self.run_effects(self.to_reviewing(), 'v')
        self.assertEqual(self.t('t-0001.r1')['status'], 'queued')
        req = {'id': fmt.new_id('human'), 'from': 'human', 'kind': 'cancel', 'at': fmt.now_iso(), 'task': 't-0001.r1'}
        self.run_effects(requests.handle(self.lay, self.roster, req))
        t = self.t()
        self.assertEqual((t['status'], t['waiting_on']), ('blocked', 'human'))
        self.assertIn('t-0001.r1', self.letters[-1]['text'])

    def test_answer_only_resumes_matching_wait(self):
        self.open()
        self.deliver()
        # 不是負責人的問題掛到別人的單上：只建題，不綁單
        q_other = {'id': fmt.new_id('worker-2'), 'from': 'worker-2', 'kind': 'ask', 'at': fmt.now_iso(),
                   'question': '?', 'reply_to': 't-0001'}
        self.assertEqual(requests.handle(self.lay, self.roster, q_other), [])
        self.assertIsNone(ask.load(self.lay, 'q-0001')['task_rev'])
        # 負責人問 q-0002 → 單子 waiting_user；改派給 worker-2；新負責人問 q-0003
        q1 = {'id': fmt.new_id('worker-1'), 'from': 'worker-1', 'kind': 'ask', 'at': fmt.now_iso(),
              'question': 'a?', 'reply_to': 't-0001'}
        self.run_effects(requests.handle(self.lay, self.roster, q1))
        self.assertEqual(self.t()['waiting_on'], 'q-0002')
        req = {'id': fmt.new_id('lead'), 'from': 'lead', 'kind': 'reassign', 'at': fmt.now_iso(), 'task': 't-0001',
               'assignee': 'worker-2'}
        self.run_effects(requests.handle(self.lay, self.roster, req))
        self.deliver()
        q2 = {'id': fmt.new_id('worker-2'), 'from': 'worker-2', 'kind': 'ask', 'at': fmt.now_iso(),
              'question': 'b?', 'reply_to': 't-0001'}
        self.run_effects(requests.handle(self.lay, self.roster, q2))
        self.assertEqual(self.t()['waiting_on'], 'q-0003')
        for qid in ('q-0001', 'q-0002'):                      # 舊題、別人的題答了都不恢復新的等待
            ans = {'id': fmt.new_id('human'), 'from': 'human', 'kind': 'answer', 'at': fmt.now_iso(), 'q': qid,
                   'text': 'ok'}
            self.run_effects(requests.handle(self.lay, self.roster, ans))
            self.assertEqual(self.t()['status'], 'waiting_user', qid)
        ans = {'id': fmt.new_id('human'), 'from': 'human', 'kind': 'answer', 'at': fmt.now_iso(), 'q': 'q-0003',
               'text': 'ok'}
        self.run_effects(requests.handle(self.lay, self.roster, ans))
        self.assertEqual(self.t()['status'], 'working')

    def test_reassign_restarts_deadline(self):
        self.open(deadline_minutes=5)
        task.check_deadlines(self.lay, now='2099-01-01T00:00:00+00:00')
        req = {'id': fmt.new_id('human'), 'from': 'human', 'kind': 'reassign', 'at': '2099-01-01T00:01:00+00:00',
               'task': 't-0001', 'assignee': 'worker-2'}
        self.run_effects(requests.handle(self.lay, self.roster, req))
        t = self.t()
        self.assertEqual(t['status'], 'queued')
        self.assertEqual(fmt.parse_iso(t['deadline']), fmt.parse_iso('2099-01-01T00:06:00+00:00'))

    def test_already_delivered_three_places(self):
        home = self.root / 'm'
        (home / 'input' / 'done').mkdir(parents=True)
        name = fmt.mail_filename('X.e0')
        self.assertIsNone(fmt.already_delivered(home, name))
        (home / 'input' / name).write_text('{}')
        self.assertEqual(fmt.already_delivered(home, name), 'input')
        os.rename(home / 'input' / name, home / 'input' / 'done' / (name + '.1-2.done'))
        self.assertEqual(fmt.already_delivered(home, name), 'done')
        (home / 'input' / 'done' / (name + '.1-2.done')).unlink()
        (home / 'state.json').write_text(json.dumps({'intake': {'id': '1-2', 'base_len': 0, 'files': [
            {'src': str(home / 'input' / name), 'dst': str(home / 'input/done/x.done')}]}}))
        self.assertEqual(fmt.already_delivered(home, name), 'intake')
        self.assertIsNone(fmt.already_delivered(home, fmt.mail_filename('other')))

    def test_bad_kind_type(self):
        with self.assertRaises(fmt.TeamError) as cm:
            fmt.validate_request({'id': 'a', 'from': 'lead', 'kind': [], 'at': 'x'})
        self.assertEqual(cm.exception.code, 'UnknownKind')


def team_cli(*args):
    return subprocess.run([sys.executable, str(PROTO / 'cli/aos-team'), *map(str, args)], capture_output=True,
                          text=True, timeout=60, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', AOS_KERNEL_HOME=''))


class InitFixTests(Base):
    def member(self, name='worker-1', **over):
        m = aos_team.member_context(self.lay, self.roster, name)
        m.update(over)
        return m

    def test_crash_before_info_json(self):
        home = self.lay.member('worker-1')
        home.mkdir()
        (home / 'prompts').mkdir()
        (home / '.aos-template.json').write_text(json.dumps({'template': 'worker', 'member': 'worker-1',
                                                             'complete': False}))
        lines = aos_agent_init.init_from_template(home, 'worker', member=self.member())
        self.assertIn('生了', lines[0])
        self.assertTrue(json.loads((home / '.aos-template.json').read_text())['complete'])

    def test_manifest_without_info_entry_is_reinstalled(self):
        home = self.lay.member('reviewer')
        aos_agent_init.init_from_template(home, 'reviewer', member=self.member('reviewer'))
        info = json.loads((home / 'info.json').read_text())
        info['tools'] = [e for e in info['tools'] if e['$val'] != 'tools/base.json']
        (home / 'info.json').write_text(json.dumps(info))
        (home / '.aos-template.json').write_text(json.dumps({'template': 'reviewer', 'member': 'reviewer',
                                                             'complete': False}))
        self.assertTrue((home / 'tools/base.json').exists())
        lines = aos_agent_init.init_from_template(home, 'reviewer', member=self.member('reviewer'))
        self.assertIn('裝了 base（read、grep、find、ls）', lines)
        vals = [e['$val'] for e in json.loads((home / 'info.json').read_text())['tools']]
        self.assertEqual(sorted(vals), ['tools/base.json', 'tools/task.json'])

    def test_template_change_refused(self):
        home = self.lay.member('worker-1')
        aos_agent_init.init_from_template(home, 'worker', member=self.member())
        with self.assertRaises(AgentError) as cm:
            aos_agent_init.init_from_template(home, 'lead', member=self.member())
        self.assertEqual(cm.exception.code, 'AlreadyExists')

    def test_extra_rw_mount_on_team_data_refused(self):
        for target in ('team', 'team/outbox/human', 'members', 'team/tasks', '.'):
            with self.subTest(target=target):
                home = self.root / ('h-' + target.replace('/', '_').replace('.', 'dot'))
                with self.assertRaises(AgentError) as cm:
                    aos_agent_init.init_from_template(home, 'worker', member=self.member(mounts={'x': target}))
                self.assertEqual(cm.exception.code, 'AccessUnsafe')
        home = self.root / 'h-ro'
        aos_agent_init.init_from_template(home, 'worker', member=self.member(mounts={'x': {'$opt': 'ro', '$val': 'team/tasks'}}))
        (self.root / 'extra').mkdir()
        home = self.root / 'h-ok'
        aos_agent_init.init_from_template(home, 'worker', member=self.member(mounts={'x': '../extra'}))

    def test_custom_template_inside_project_refused(self):
        shutil.copytree(PROTO / 'templates/worker', self.root / 'p' / 'tpl')
        roster = copy.deepcopy(ROSTER)
        roster['members']['worker-1']['template'] = str(self.root / 'p' / 'tpl')
        (self.team / 'team.json').write_text(json.dumps(roster))
        r = team_cli('init', '--target', self.team)
        self.assertEqual(r.returncode, 1)
        self.assertIn('BadTemplate', r.stderr)

    def test_rm_interrupted_then_completed(self):
        r = team_cli('init', '--target', self.team)
        self.assertEqual(r.returncode, 0, r.stderr)
        # 模擬：記了 intent、家搬走了、名冊還沒改就崩
        dest = self.lay.members / '.removed' / 'worker-2-1'
        (self.lay.members / '.removing-worker-2.json').write_text(json.dumps({'name': 'worker-2', 'dest': str(dest)}))
        dest.parent.mkdir()
        shutil.move(str(self.lay.member('worker-2')), str(dest))
        r = team_cli('init', '--target', self.team)
        self.assertEqual(r.returncode, 1)
        self.assertIn('aos-team rm worker-2', r.stderr)
        self.assertFalse(self.lay.member('worker-2').exists())          # 沒被 init 生回來
        r = team_cli('rm', 'worker-2', '--target', self.team)
        self.assertEqual(r.returncode, 0, r.stderr)
        roster = json.loads((self.team / 'team.json').read_text())
        self.assertNotIn('worker-2', roster['members'])
        self.assertNotIn('worker-2', roster['members']['lead']['mail_to'])
        self.assertFalse((self.lay.members / '.removing-worker-2.json').exists())
        self.assertEqual(team_cli('init', '--target', self.team).returncode, 0)


if __name__ == '__main__':
    unittest.main()
