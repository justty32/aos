"""工具大開發時代第一波 第 1 隊第 0 步：團隊共用格式（spec/team/）、任務狀態機、問人、申請登記表、aos-team 分派。"""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import aos_agent_say
import aos_team_ask as ask
import aos_team_cli
import aos_team_format as fmt
import aos_team_requests as requests
import aos_team_task as task

PROTO = Path(__file__).resolve().parents[2]
EXAMPLES = PROTO / 'spec' / 'team' / 'examples'
ROSTER = {'_metainfo': {'_type': 'aos_team', '_version': 1}, 'project': '../p', 'tz': 'Asia/Taipei',
          'members': {'lead': {'template': 'lead', 'mail_to': ['worker-1', 'worker-2', 'reviewer', 'human']},
                      'worker-1': {'template': 'worker', 'mail_to': ['lead', 'human']},
                      'worker-2': {'template': 'worker', 'mail_to': ['lead', 'human']},
                      'reviewer': {'template': 'reviewer', 'mail_to': ['lead', 'human']}}}


def handoff(**over):
    req = json.loads((EXAMPLES / 'request-handoff.json').read_text(encoding='utf-8'))
    req.update(over)
    return req


class Base(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='aos-team-fmt-'))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.team = self.root / 'team'
        self.team.mkdir()
        (self.root / 'p').mkdir()
        (self.team / 'team.json').write_text(json.dumps(ROSTER, ensure_ascii=False), encoding='utf-8')
        self.lay = fmt.Layout(self.team)
        for d in self.lay.skeleton(ROSTER['members']):
            d.mkdir(parents=True, exist_ok=True)
        self.roster = fmt.load_roster(self.team)

    def err(self, code, fn, *args):
        with self.assertRaises(fmt.TeamError) as cm:
            fn(*args)
        self.assertEqual(cm.exception.code, code, cm.exception.msg)
        return cm.exception.msg


class ExampleTests(Base):
    def test_examples_all_validate_by_cli(self):
        files = sorted(EXAMPLES.glob('*.json'))
        self.assertGreaterEqual(len(files), 9)
        r = subprocess.run([sys.executable, str(PROTO / 'lib' / 'aos_team_format.py'), *map(str, files)],
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.count('ok  '), len(files))

    def test_cli_reports_bad_file(self):
        bad = self.root / 'bad.json'
        bad.write_text('{"id": "x", "from": "a", "to": "b", "status": "OK", "text": "t", "at": "now"}')
        r = subprocess.run([sys.executable, str(PROTO / 'lib' / 'aos_team_format.py'), str(bad)],
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 1)
        self.assertIn('BadStatus', r.stdout)

    def test_builtin_templates_validate(self):
        for name in ('lead', 'worker', 'reviewer', 'coder'):
            folder, tpl = fmt.load_template(name)
            self.assertTrue((folder / tpl['system']).is_file(), name)
        self.assertEqual(fmt.template_may('lead'), ('handoff', 'cancel', 'reassign', 'ask'))
        self.err('NoSuchTemplate', fmt.load_template, 'nope')


class RosterTests(Base):
    def test_defaults_filled(self):
        r = self.roster
        self.assertEqual(r['limits'], {'stale_minutes': 10, 'max_members': 6})
        self.assertIsNone(r['members']['lead']['model'])
        self.assertEqual(fmt.project_dir(self.team, r), (self.root / 'p').resolve())
        self.assertEqual(fmt.members_by_template(r, 'worker'), ['worker-1', 'worker-2'])

    def bad_roster(self, change, text):
        obj = copy.deepcopy(ROSTER)
        change(obj)
        msg = self.err('FormatInvalid', fmt.validate_roster, obj)
        self.assertIn(text, msg)

    def test_errors_point_at_field(self):
        self.bad_roster(lambda o: o['members']['worker-1']['mail_to'].append('boss'), 'members.worker-1.mail_to')
        self.bad_roster(lambda o: o['members'].update(human={'template': 'x'}), '保留名')
        self.bad_roster(lambda o: o['members'].update(Bob={'template': 'x'}), '小寫')
        self.bad_roster(lambda o: o.update(member={}), '不認得的欄位 member')
        self.bad_roster(lambda o: o['members']['lead']['mail_to'].append('lead'), '不能寄給自己')
        self.bad_roster(lambda o: o.update(limits={'max_members': 2}), 'max_members')
        self.bad_roster(lambda o: o['members']['lead'].update(mounts={'ws': 'x'}), 'ws／outbox／board')
        self.bad_roster(lambda o: o['members']['lead'].update(mounts={'wf': {'$opt': 'rw', '$val': 'x'}}), 'mounts.wf')
        self.bad_roster(lambda o: o.pop('project'), 'project')

    def test_json_syntax(self):
        (self.team / 'team.json').write_text('{"project": ', encoding='utf-8')
        self.err('JsonSyntax', fmt.load_roster, self.team)


class MailTests(Base):
    def put(self, sender, obj, name=None):
        folder = self.lay.outbox(sender)
        path = folder / ((name or obj['id']) + '.json')
        path.write_text(json.dumps(obj, ensure_ascii=False), encoding='utf-8')
        return path

    def letter(self, sender='worker-1', **over):
        obj = {'id': fmt.new_id(sender), 'from': sender, 'to': 'lead', 'status': 'DONE', 'reply_to': 't-0001',
               'rev': 1, 'text': '好了', 'at': fmt.now_iso('Asia/Taipei')}
        obj.update(over)
        return obj

    def test_letter_ok(self):
        kind, obj = fmt.read_outbox_file(self.put('worker-1', self.letter()), self.roster)
        self.assertEqual(kind, 'letter')
        self.assertEqual(obj['to'], 'lead')

    def test_identity_is_folder(self):
        obj = self.letter(sender='worker-1')
        obj['from'] = 'lead'
        path = self.lay.outbox('worker-1') / (obj['id'] + '.json')
        path.write_text(json.dumps(obj), encoding='utf-8')
        self.err('NotSender', fmt.read_outbox_file, path, self.roster)
        # 檔名的寄件人段不是資料夾名
        other = self.letter(sender='lead')
        path = self.lay.outbox('worker-1') / (other['id'] + '.json')
        other['from'] = 'worker-1'
        path.write_text(json.dumps(other), encoding='utf-8')
        self.err('BadId', fmt.read_outbox_file, path, self.roster)

    def test_recipient_and_status(self):
        self.err('BadRecipient', fmt.read_outbox_file, self.put('worker-1', self.letter(to='worker-2')), self.roster)
        self.err('BadStatus', fmt.read_outbox_file, self.put('worker-1', self.letter(status='OK')), self.roster)
        self.err('FormatInvalid', fmt.read_outbox_file, self.put('worker-1', self.letter(extra=1)), self.roster)
        self.err('FormatInvalid', fmt.read_outbox_file, self.put('worker-1', self.letter(text='')), self.roster)
        # human 可以寄給任何成員，但不能寄給名冊外
        kind, _ = fmt.read_outbox_file(self.put('human', self.letter(sender='human', to='worker-2')), self.roster)
        self.assertEqual(kind, 'letter')
        self.err('BadRecipient', fmt.read_outbox_file, self.put('human', self.letter(sender='human', to='x')),
                 self.roster)

    def test_unknown_sender_folder(self):
        folder = self.lay.team / 'outbox' / 'ghost'
        folder.mkdir(parents=True)
        obj = self.letter(sender='ghost')
        path = folder / (obj['id'] + '.json')
        path.write_text(json.dumps(obj), encoding='utf-8')
        self.err('NotSender', fmt.read_outbox_file, path, self.roster)

    def test_requests(self):
        req = handoff(id=fmt.new_id('lead'))
        kind, obj = fmt.read_outbox_file(self.put('lead', req), self.roster)
        self.assertEqual(kind, 'request')
        bad = handoff(id=fmt.new_id('lead'), done_when=[{'kind': 'shell', 'cmd': 'rm -rf /'}])
        self.assertIn('done_when[0].kind', self.err('FormatInvalid', fmt.read_outbox_file,
                                                    self.put('lead', bad), self.roster))
        bad = {'id': fmt.new_id('lead'), 'from': 'lead', 'kind': 'teleport', 'at': 'x'}
        self.err('UnknownKind', fmt.read_outbox_file, self.put('lead', bad), self.roster)
        bad = {'id': fmt.new_id('worker-1'), 'from': 'worker-1', 'kind': 'ask', 'at': 'x', 'question': 'q',
               'options': ['a'], 'default': 'b'}
        self.err('FormatInvalid', fmt.read_outbox_file, self.put('worker-1', bad), self.roster)
        bad = {'id': fmt.new_id('reviewer'), 'from': 'reviewer', 'kind': 'review_result', 'at': 'x',
               'task': 't-0001.r1', 'items': [{'i': 0, 'pass': True, 'why': 'a'}, {'i': 0, 'pass': True, 'why': 'b'}]}
        self.err('FormatInvalid', fmt.read_outbox_file, self.put('reviewer', bad), self.roster)

    def test_header(self):
        ltr = self.letter(at='2026-09-25T10:03:12+08:00', to='lead', status='REQUEST', reply_to='t-0007', rev=2)
        ltr['from'] = 'worker-1'
        self.assertEqual(fmt.render_header(ltr, 'Asia/Taipei'),
                         '【來信 worker-1 → lead · REQUEST · t-0007 rev2 · 09-25 10:03】')
        ans = {'from': 'human', 'to': 'worker-1', 'status': 'DONE', 'reply_to': 'q-0003', 'rev': None,
               'at': '2026-09-25T02:03:00+00:00'}
        self.assertEqual(fmt.render_header(ans, 'Asia/Taipei'), '【人 → worker-1 · 回覆 q-0003 · 09-25 10:03】')
        msg = fmt.mail_message(dict(ltr, text='內容'), 'Asia/Taipei')
        self.assertEqual(msg['role'], 'user')
        self.assertTrue(msg['content'].endswith('\n內容'))

    def test_write_new_and_drop_new_never_overwrite(self):
        p = self.root / 'x.json'
        self.assertTrue(fmt.write_new(p, {'a': 1}))
        self.assertFalse(fmt.write_new(p, {'a': 2}))
        self.assertEqual(json.loads(p.read_text()), {'a': 1})
        inbox = self.root / 'm' / 'input'
        self.assertTrue(aos_agent_say.drop_new(inbox, 'mail-1.json', {'role': 'user', 'content': 'hi'}))
        self.assertFalse(aos_agent_say.drop_new(inbox, 'mail-1.json', 'other'))
        self.assertEqual(json.loads((inbox / 'mail-1.json').read_text())['content'], 'hi')
        self.assertTrue(aos_agent_say.drop_new(inbox, 'mail-2.json', 'plain'))
        self.assertEqual(json.loads((inbox / 'mail-2.json').read_text()), {'role': 'user', 'content': 'plain'})
        self.assertEqual(sorted(p.name for p in inbox.iterdir()), ['mail-1.json', 'mail-2.json'])  # 沒有暫存殘檔

    def test_json_files_skips_temp(self):
        (self.root / '.a.json.tmp').write_text('{}')
        (self.root / '.b.json').write_text('{}')
        (self.root / 'c.json').write_text('{}')
        self.assertEqual([p.name for p in fmt.json_files(self.root)], ['c.json'])


class FakePost:
    """最小的假郵差：只做後續動作裡的 letter／step／open_review，verify 交給測試自己回。"""

    def __init__(self, case):
        self.case, self.letters, self.verifies = case, [], []

    def run(self, effects, src='x'):
        for k, e in enumerate(effects):
            if e['do'] == 'letter':
                self.letters.append(e)
            elif e['do'] == 'step':
                self.run(task.step(self.case.lay, e['task'], e['event']), src)
            elif e['do'] == 'open_review':
                self.run(task.open_review(self.case.lay, self.case.roster, e['task'], '%s.e%d' % (src, k)), src)
            elif e['do'] == 'verify':
                self.verifies.append(e)


class TaskTests(Base):
    def open(self, **over):
        req = handoff(id=fmt.new_id('lead'), **over)
        self.post = FakePost(self)
        effects = requests.handle(self.lay, self.roster, req)
        self.post.run(effects, req['id'])
        return req, effects

    def t(self, tid='t-0001'):
        return task.load(self.lay, tid)

    def report(self, status, rev=1, by='worker-1', tid='t-0001'):
        ltr = {'id': fmt.new_id(by), 'from': by, 'to': 'lead', 'status': status, 'reply_to': tid, 'rev': rev,
               'text': 'x', 'at': fmt.now_iso()}
        effects = task.on_letter(self.lay, self.roster, ltr)
        self.post.run(effects, ltr['id'])
        return ltr, effects

    def deliver(self, tid='t-0001'):
        t = self.t(tid)
        ltr = {'id': 'L%d-%s' % (len(t['history']), tid), 'to': t['assignee'], 'reply_to': tid, 'rev': t['rev']}
        task.letter_delivered(self.lay, ltr)
        task.letter_picked_up(self.lay, ltr)

    def test_open_is_queued_and_idempotent(self):
        req, effects = self.open()
        t = self.t()
        self.assertEqual((t['status'], t['rev'], t['attempt'], t['assignee'], t['opened_by']),
                         ('queued', 1, 1, 'worker-1', 'lead'))
        self.assertEqual(effects[0]['do'], 'letter')
        self.assertIn('t-0001', effects[0]['text'])
        self.assertEqual(task.on_handoff(self.lay, self.roster, req), effects)   # 重跑同一份申請
        self.assertEqual([p.name for p in fmt.json_files(self.lay.tasks)], ['t-0001.json'])
        self.assertIsNotNone(t['deadline'])

    def test_permissions(self):
        req = handoff(id=fmt.new_id('worker-1'), **{'from': 'worker-1'}, assignee='worker-2')
        self.err('NotAllowed', requests.handle, self.lay, self.roster, req)
        req = handoff(id=fmt.new_id('lead'), assignee='ghost')
        self.err('BadAssignee', requests.handle, self.lay, self.roster, req)
        req = handoff(id=fmt.new_id('human'), **{'from': 'human'}, assignee='reviewer')
        self.assertEqual(requests.handle(self.lay, self.roster, req)[0]['to'], 'reviewer')   # 人什麼都能派
        self.err('UnknownKind', requests.handler, 'teleport')

    def test_full_flow_with_review(self):
        self.open()
        self.deliver()
        self.assertEqual(self.t()['status'], 'working')
        _, eff = self.report('DONE')
        self.assertEqual(self.t()['status'], 'verifying')
        self.assertEqual(self.post.verifies[-1], {'do': 'verify', 'task': 't-0001', 'rev': 1, 'attempt': 1})
        self.post.run(task.step(self.lay, 't-0001', {'type': 'verified', 'src': 'v1', 'pass': True, 'rev': 1,
                                                     'attempt': 1, 'results': []}), 'v1')
        self.assertEqual(self.t()['status'], 'reviewing')
        sub = self.t('t-0001.r1')
        self.assertEqual((sub['assignee'], sub['parent'], sub['status']), ('reviewer', 't-0001', 'queued'))
        self.assertEqual(sub['review_of']['indices'], [3])
        self.assertIn('review_result', self.post.letters[-1]['text'])
        rr = {'id': fmt.new_id('reviewer'), 'from': 'reviewer', 'kind': 'review_result', 'at': fmt.now_iso(),
              'task': 't-0001.r1', 'items': [{'i': 0, 'pass': True, 'why': '意思一樣'}]}
        eff = requests.handle(self.lay, self.roster, rr)
        self.post.run(eff, rr['id'])
        self.assertEqual(self.t('t-0001.r1')['status'], 'done')
        t = self.t()
        self.assertEqual(t['status'], 'done')
        self.assertEqual(t['review'][0]['items'][0]['i'], 3)        # 換回父單的原編號
        self.assertEqual({l['to'] for l in self.post.letters if l['status'] == 'DONE'}, {'lead', 'human'})
        self.assertEqual(requests.handle(self.lay, self.roster, rr), eff)      # 重跑同一份

    def test_old_rev_and_wrong_sender_do_not_change(self):
        self.open()
        self.deliver()
        self.report('DONE', rev=0 + 2)
        self.report('DONE', by='worker-2')
        t = self.t()
        self.assertEqual(t['status'], 'working')
        self.assertEqual([h['event'] for h in t['history'][-2:]], ['ignored:report', 'ignored:report'])
        # 改派後 rev 變 2，舊 rev1 的 DONE 不算
        req = {'id': fmt.new_id('lead'), 'from': 'lead', 'kind': 'reassign', 'at': fmt.now_iso(),
               'task': 't-0001', 'assignee': 'worker-2'}
        self.post.run(requests.handle(self.lay, self.roster, req))
        t = self.t()
        self.assertEqual((t['status'], t['rev'], t['assignee']), ('queued', 2, 'worker-2'))
        self.assertEqual({l['to'] for l in self.post.letters[-2:]}, {'worker-1', 'worker-2'})
        self.deliver()
        self.report('DONE', rev=1, by='worker-2')
        self.assertEqual(self.t()['status'], 'working')
        self.report('DONE', rev=2, by='worker-2')
        self.assertEqual(self.t()['status'], 'verifying')

    def test_same_src_replay_returns_same_effects(self):
        self.open()
        self.deliver()
        ltr, eff = self.report('DONE')
        before = self.t()
        again = task.on_letter(self.lay, self.roster, ltr)
        self.assertEqual(again, eff)
        self.assertEqual(self.t(), before)

    def test_verify_fail_retries_then_fails(self):
        self.open(max_attempts=2)
        for attempt in (1, 2):
            self.deliver()
            self.report('DONE')
            self.post.run(task.step(self.lay, 't-0001', {'type': 'verified', 'src': 'v%d' % attempt, 'pass': False,
                                                         'rev': 1, 'attempt': attempt,
                                                         'results': [{'i': 1, 'pass': False, 'why': '殘留 3 處'}]}))
            if attempt == 1:
                t = self.t()
                self.assertEqual((t['status'], t['attempt']), ('queued', 2))
                self.assertIn('REQUEST 修正 t-0001（第 2/2 次）', self.post.letters[-1]['text'])
                self.assertIn('殘留 3 處', self.post.letters[-1]['text'])
        t = self.t()
        self.assertEqual(t['status'], 'failed')
        self.assertEqual({l['to'] for l in self.post.letters[-2:]}, {'lead', 'human'})
        self.assertEqual(self.post.letters[-1]['status'], 'FAILED')
        self.report('DONE')                                          # 結束了再回也不改
        self.assertEqual(self.t()['status'], 'failed')

    def test_blocked_resume_and_cancel(self):
        self.open()
        self.deliver()
        self.report('BLOCKED')
        self.assertEqual((self.t()['status'], self.t()['waiting_on']), ('blocked', 'lead'))
        ltr = {'id': fmt.new_id('lead'), 'from': 'lead', 'to': 'worker-1', 'status': 'REQUEST', 'reply_to': 't-0001',
               'rev': 1, 'text': '事實補在 facts.json 了', 'at': fmt.now_iso()}
        task.on_letter(self.lay, self.roster, ltr)
        self.assertEqual(self.t()['status'], 'sent')
        req = {'id': fmt.new_id('worker-1'), 'from': 'worker-1', 'kind': 'cancel', 'at': fmt.now_iso(), 'task': 't-0001'}
        self.err('NotAllowed', requests.handle, self.lay, self.roster, req)
        req = {'id': fmt.new_id('human'), 'from': 'human', 'kind': 'cancel', 'at': fmt.now_iso(), 'task': 't-0001',
               'reason': '不做了'}
        self.post.run(requests.handle(self.lay, self.roster, req))
        self.assertEqual(self.t()['status'], 'cancelled')
        self.assertIn('取消 t-0001', self.post.letters[-1]['text'])

    def test_judge_only_and_no_reviewer(self):
        roster = copy.deepcopy(ROSTER)
        del roster['members']['reviewer']
        roster['members']['lead']['mail_to'].remove('reviewer')
        (self.team / 'team.json').write_text(json.dumps(roster), encoding='utf-8')
        self.roster = fmt.load_roster(self.team)
        self.open(done_when=[{'kind': 'judge', 'text': '寫得白話'}])
        self.deliver()
        self.report('DONE')
        t = self.t()
        self.assertEqual((t['status'], t['waiting_on']), ('blocked', 'human'))
        self.assertIn('reviewer', self.post.letters[-1]['text'])

    def test_deadline_expire(self):
        self.open(deadline_minutes=1)
        out = task.check_deadlines(self.lay, now='2099-01-01T00:00:00+00:00')
        self.assertEqual(out[0][0], 't-0001')
        self.assertEqual(self.t()['status'], 'failed')
        self.assertEqual(task.check_deadlines(self.lay, now='2099-01-01T00:00:00+00:00'), [])

    def test_review_result_rules(self):
        self.open()
        self.deliver()
        self.report('DONE')
        self.post.run(task.step(self.lay, 't-0001', {'type': 'verified', 'src': 'v', 'pass': True, 'rev': 1,
                                                     'attempt': 1}))
        base = {'from': 'reviewer', 'kind': 'review_result', 'at': fmt.now_iso(), 'task': 't-0001.r1'}
        req = dict(base, id=fmt.new_id('reviewer'), items=[{'i': 1, 'pass': True, 'why': 'x'}])
        self.err('BadItems', requests.handle, self.lay, self.roster, req)
        req = dict(base, id=fmt.new_id('reviewer'), items=[{'i': 0, 'pass': False, 'why': '意思變了'}])
        self.post.run(requests.handle(self.lay, self.roster, req))
        t = self.t()
        self.assertEqual((t['status'], t['attempt']), ('queued', 2))
        self.assertIn('意思變了', self.post.letters[-1]['text'])
        req = dict(base, id=fmt.new_id('reviewer'), items=[{'i': 0, 'pass': True, 'why': 'x'}])
        self.err('Closed', requests.handle, self.lay, self.roster, req)
        # 審查子單回 DONE 信只記下
        self.report('DONE', by='reviewer', tid='t-0001.r1')
        self.assertEqual(self.t('t-0001.r1')['status'], 'done')


class AskTests(Base):
    def test_ask_answer_roundtrip(self):
        post = FakePost(self)
        post.run(requests.handle(self.lay, self.roster, handoff(id=fmt.new_id('lead'))))
        task.letter_delivered(self.lay, {'id': 'a', 'to': 'worker-1', 'reply_to': 't-0001', 'rev': 1})
        req = json.loads((EXAMPLES / 'request-ask.json').read_text(encoding='utf-8'))
        eff = requests.handle(self.lay, self.roster, req)
        post.run(eff)
        self.assertEqual(eff, requests.handle(self.lay, self.roster, req))     # 冪等
        q = ask.load(self.lay, 'q-0001')
        self.assertEqual((q['status'], q['from'], q['reply_to']), ('open', 'worker-1', 't-0001'))
        self.assertEqual(task.load(self.lay, 't-0001')['status'], 'waiting_user')
        self.assertEqual([x['id'] for x in ask.open_questions(self.lay)], ['q-0001'])
        self.assertIn('選項：main / 開分支（預設 main）', ask.describe(q))
        bad = {'id': fmt.new_id('lead'), 'from': 'lead', 'kind': 'answer', 'at': 'x', 'q': 'q-0001', 'text': 'main'}
        self.err('NotAllowed', requests.handle, self.lay, self.roster, bad)
        ans = json.loads((EXAMPLES / 'request-answer.json').read_text(encoding='utf-8'))
        eff = requests.handle(self.lay, self.roster, ans)
        post.run(eff)
        self.assertEqual(post.letters[-1]['from'], 'human')
        self.assertEqual(post.letters[-1]['to'], 'worker-1')
        self.assertEqual(post.letters[-1]['reply_to'], 'q-0001')
        self.assertEqual(ask.open_questions(self.lay), [])
        self.assertEqual(task.load(self.lay, 't-0001')['status'], 'sent')
        self.assertEqual(requests.handle(self.lay, self.roster, ans), eff)     # 同一份答覆重跑
        again = dict(ans, id=fmt.new_id('human'))
        self.err('Closed', requests.handle, self.lay, self.roster, again)
        self.err('NoSuchQuestion', requests.handle, self.lay, self.roster, dict(ans, id='z', q='q-0009'))


class CliTests(unittest.TestCase):
    def run_cli(self, *args, env=None):
        return subprocess.run([sys.executable, str(PROTO / 'cli' / 'aos-team'), *args], capture_output=True,
                              text=True, timeout=30, env=dict(os.environ, **(env or {})))

    def test_usage_and_unknown(self):
        r = self.run_cli()
        self.assertEqual(r.returncode, 2)
        self.assertIn('init', r.stdout)
        r = self.run_cli('-h')
        self.assertEqual(r.returncode, 0)
        r = self.run_cli('fly')
        self.assertEqual(r.returncode, 2)
        self.assertIn('不認得的子命令', r.stderr)

    def test_not_implemented_names_team(self):
        aos_team_cli.COMMANDS['zz-test'] = ('aos_team_nope_module', 'cmd', 7, 'x')
        self.addCleanup(aos_team_cli.COMMANDS.pop, 'zz-test')
        with self.assertRaises(fmt.TeamError) as cm:
            aos_team_cli.resolve('zz-test')
        self.assertEqual(cm.exception.code, 'NotImplemented')
        self.assertIn('第 7 隊', cm.exception.msg)

    def test_split_target_anywhere(self):
        self.assertEqual(aos_team_cli.split_target(['ask', '--target', '/t', 'hi']), ('/t', ['ask', 'hi']))
        self.assertEqual(aos_team_cli.split_target(['--target=/x', 'ls']), ('/x', ['ls']))
        with self.assertRaises(fmt.TeamError):
            aos_team_cli.split_target(['ls', '--target'])


if __name__ == '__main__':
    unittest.main()
