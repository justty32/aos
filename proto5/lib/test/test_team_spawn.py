"""第三波 W3-1：T-spawn（spec/team/spawn.md）。

郵差端 on_spawn 的檢查（每條逃逸一個測試）、冪等；人端 aos-team spawn approve 生家、改名冊、回覆；
停掉／收掉走既有的 aos-team rm；工具 spawn_member 經真郵差（may 擋工人）。不叫模型、不碰 kernel。
"""
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
import unittest.mock

import aos_team
import aos_team_ask as ask
import aos_team_format as fmt
import aos_team_post as post
import aos_team_requests as requests
import aos_team_spawn as spawn

PROTO = Path(__file__).resolve().parents[2]
TOOL = PROTO / 'tools' / 'task' / 'spawn_member'
ROSTER = {'_metainfo': {'_type': 'aos_team', '_version': 1}, 'project': '../p', 'tz': 'Asia/Taipei',
          'members': {'lead': {'template': 'lead', 'mail_to': ['worker-1', 'human']},
                      'worker-1': {'template': 'worker', 'mail_to': ['lead', 'human']}},
          'limits': {'max_members': 4},
          'spawn': {'templates': ['worker', 'importer', 'lead'], 'approve': True}}   # 舊測試＝要人批那條路


def req(sender='lead', rid='r1', **over):
    base = {'id': rid, 'from': sender, 'kind': 'spawn', 'at': '2026-09-24T10:00:00+08:00',
            'template': 'worker', 'name': 'worker-2', 'reason': '要同時導入三個專案'}
    base.update(over)
    return base


def quiet(fn, *a, **kw):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
        rc = fn(*a, **kw)
    return rc, buf.getvalue()


class Base(unittest.TestCase):
    roster_obj = ROSTER
    real_homes = False

    def setUp(self):
        self.root = Path(os.path.realpath(tempfile.mkdtemp(prefix='aos-spawn-')))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        (self.root / 'p').mkdir()
        self.team = self.root / 'team'
        self.team.mkdir()
        (self.team / 'team.json').write_text(json.dumps(self.roster_obj, ensure_ascii=False), encoding='utf-8')
        self.lay = fmt.Layout(self.team)
        self.env = {k: v for k, v in os.environ.items() if k != 'AOS_KERNEL_HOME'}
        if self.real_homes:
            rc, out = quiet(aos_team.cmd_init, str(self.team), [])
            self.assertEqual(rc, 0, out)
        else:
            for d in self.lay.skeleton(self.roster_obj['members']):
                d.mkdir(parents=True, exist_ok=True)

    @property
    def roster(self):
        return fmt.load_roster(self.team)

    def err(self, code, fn, *a):
        with self.assertRaises(fmt.TeamError) as cm:
            fn(*a)
        self.assertEqual(cm.exception.code, code, cm.exception.msg)
        return cm.exception.msg

    def open_questions(self):
        return ask.open_questions(self.lay)


class OnSpawnTests(Base):
    def test_ok_opens_question_with_prefix_and_record(self):
        eff = spawn.on_spawn(self.lay, self.roster, req())
        self.assertEqual(eff, [])                       # 不叫醒申請者：人答了才有信
        qs = self.open_questions()
        self.assertEqual(len(qs), 1)
        self.assertTrue(qs[0]['question'].startswith('lead 想生一個新成員 worker-2'), qs[0]['question'])
        self.assertEqual(qs[0]['tag'], 'member')
        self.assertTrue(ask.describe(qs[0]).startswith('[成員] '))
        self.assertIn('aos-team spawn approve %s' % qs[0]['id'], qs[0]['question'])
        rec = spawn.records(self.lay)[0]
        self.assertEqual((rec['id'], rec['name'], rec['mail_to'], rec['q']), ('s-0001', 'worker-2', ['lead', 'human'],
                                                                           qs[0]['id']))
        self.assertNotIn('worker-2', self.roster['members'])       # 郵差不改名冊
        self.assertFalse(self.lay.member('worker-2').exists())     # 也不建家

    def test_idempotent_same_request(self):
        spawn.on_spawn(self.lay, self.roster, req())
        spawn.on_spawn(self.lay, self.roster, req())
        self.assertEqual(len(spawn.records(self.lay)), 1)
        self.assertEqual(len(self.open_questions()), 1)

    def test_through_registry_needs_may(self):
        requests.handle(self.lay, self.roster, req())
        self.err('NotAllowed', requests.handle, self.lay, self.roster, req('worker-1', 'r9', name='worker-9'))

    # ------------------------------------------------ 逃逸：每條一個測試 ----

    def test_escape_mail_to_bigger_than_requester(self):
        r = json.loads(json.dumps(ROSTER))
        r['members']['worker-1']['spawn'] = True        # 人在名冊上讓這個工人也能生（成員層開）
        (self.team / 'team.json').write_text(json.dumps(r), encoding='utf-8')
        msg = self.err('MailToExceeds', spawn.on_spawn, self.lay, self.roster,
                       req('worker-1', mail_to=['lead', 'human', 'worker-3']))
        self.assertIn('worker-3', msg)
        self.assertEqual(spawn.records(self.lay), [])

    def test_escape_mail_to_someone_requester_cannot_reach(self):
        r = json.loads(json.dumps(ROSTER))
        r['members']['reviewer'] = {'template': 'reviewer', 'mail_to': ['lead']}
        (self.team / 'team.json').write_text(json.dumps(r), encoding='utf-8')
        self.err('MailToExceeds', spawn.on_spawn, self.lay, self.roster, req(mail_to=['reviewer']))

    def test_escape_template_with_more_may(self):
        # 自訂模板的申請者只能 spawn、ask；要生 lead（能 handoff、cancel…）＝權限比自己大
        tpl = self.root / 'tpl-small'
        shutil.copytree(PROTO / 'templates' / 'worker', tpl)
        obj = json.loads((tpl / 'template.json').read_text(encoding='utf-8'))
        obj['may'] = ['spawn', 'ask']
        (tpl / 'template.json').write_text(json.dumps(obj), encoding='utf-8')
        r = json.loads(json.dumps(ROSTER))
        r['members']['small'] = {'template': str(tpl), 'mail_to': ['lead', 'human']}
        (self.team / 'team.json').write_text(json.dumps(r), encoding='utf-8')
        msg = self.err('MayExceeds', spawn.on_spawn, self.lay, self.roster, req('small', template='lead'))
        self.assertIn('handoff', msg)

    def test_escape_template_not_allowed(self):
        self.err('BadTemplate', spawn.on_spawn, self.lay, self.roster, req(template='reviewer'))

    def test_escape_template_garbage_names(self):
        for bad in ('../../etc', '/tmp/evil', 'nope', '', 'wor ker'):
            with self.subTest(template=bad):
                self.err('BadTemplate', spawn.on_spawn, self.lay, self.roster, req(template=bad, rid='r-%d' % len(bad)))
        self.assertEqual(self.open_questions(), [])

    def test_escape_allowlist_template_missing_on_disk(self):
        r = json.loads(json.dumps(ROSTER))
        r['spawn']['templates'].append('ghost')
        (self.team / 'team.json').write_text(json.dumps(r), encoding='utf-8')
        self.err('BadTemplate', spawn.on_spawn, self.lay, self.roster, req(template='ghost'))

    def test_escape_over_max_members_counts_pending(self):
        spawn.on_spawn(self.lay, self.roster, req(rid='r1', name='worker-2'))
        spawn.on_spawn(self.lay, self.roster, req(rid='r2', name='worker-3'))
        msg = self.err('TooMany', spawn.on_spawn, self.lay, self.roster, req(rid='r3', name='worker-4'))
        self.assertIn('max_members=4', msg)

    def test_escape_extra_fields_rejected(self):
        for extra in ({'mounts': {'x': '/'}}, {'tools': [{'pack': 'base'}]}, {'model': 'smart'}):
            with self.subTest(extra=extra):
                self.err('BadArguments', spawn.on_spawn, self.lay, self.roster, req(rid=str(extra), **extra))

    def test_escape_name_taken_reserved_or_bad(self):
        self.err('NameTaken', spawn.on_spawn, self.lay, self.roster, req(name='worker-1'))
        for bad in ('human', 'post', 'beat'):
            self.err('FormatInvalid', spawn.on_spawn, self.lay, self.roster, req(name=bad, rid=bad))
        self.err('FormatInvalid', spawn.on_spawn, self.lay, self.roster, req(name='../lead', rid='x'))
        spawn.on_spawn(self.lay, self.roster, req(rid='r1'))
        self.err('NameTaken', spawn.on_spawn, self.lay, self.roster, req(rid='r2'))   # 同名在等人批

    def test_empty_templates_means_nobody_can_spawn(self):
        r = json.loads(json.dumps(ROSTER))
        r['spawn']['templates'] = []                   # 09-25 翻案後：要關就明寫 []
        (self.team / 'team.json').write_text(json.dumps(r), encoding='utf-8')
        msg = self.err('BadTemplate', spawn.on_spawn, self.lay, self.roster, req())
        self.assertIn('是空的', msg)

    def test_roster_spawn_key_validated(self):
        for bad in ({'templates': ['a/b']}, {'templates': 'worker'}, {'who': []}, {'approve': 'yes'}):
            r = dict(ROSTER, spawn=bad)
            with self.subTest(spawn=bad):
                self.err('FormatInvalid', fmt.validate_roster, r)
        self.assertEqual(fmt.validate_roster(dict(ROSTER))['spawn'],
                         {'templates': ['worker', 'importer', 'lead'], 'approve': True})
        self.assertEqual(fmt.validate_roster({k: v for k, v in ROSTER.items() if k != 'spawn'})['spawn'],
                         {'templates': None, 'approve': False})
        for bad in ('yes', {'allow': 1}, {'templates': ['../x']}, {'who': True}):
            r = json.loads(json.dumps(ROSTER))
            r['members']['lead']['spawn'] = bad
            with self.subTest(member_spawn=bad):
                self.err('FormatInvalid', fmt.validate_roster, r)


class ApproveTests(Base):
    real_homes = True

    def ask_and_get_q(self, **over):
        spawn.on_spawn(self.lay, self.roster, req(**over))
        return spawn.records(self.lay)[-1]['q']

    def human_box(self):
        return [fmt.read_json(p) for p in fmt.json_files(self.lay.outbox('human'))]

    def test_approve_builds_home_roster_and_answers(self):
        q = self.ask_and_get_q()
        rc, out = quiet(spawn.approve, str(self.team), q, env=self.env)
        self.assertEqual(rc, 0, out)
        r = self.roster
        self.assertEqual(r['members']['worker-2']['template'], 'worker')
        self.assertEqual(r['members']['worker-2']['mail_to'], ['lead', 'human'])
        self.assertIn('worker-2', r['members']['lead']['mail_to'])
        home = self.lay.member('worker-2')
        self.assertTrue((home / 'info.json').is_file())
        self.assertTrue((home / 'access.json').is_file())
        # 領隊工具裡的名冊快照也更新了：handoff 給 worker-2 不會被工具擋
        cfg = json.loads((self.lay.member('lead') / 'tools' / 'task' / 'config.json').read_text(encoding='utf-8'))
        self.assertIn('worker-2', cfg['mail_to'])
        box = self.human_box()
        self.assertEqual([(b['kind'], b['q']) for b in box], [('answer', q)])
        self.assertIn('批准', box[0]['text'])
        self.assertIn('沒設 AOS_KERNEL_HOME', out)

    def test_approve_twice_is_safe(self):
        q = self.ask_and_get_q()
        quiet(spawn.approve, str(self.team), q, env=self.env)
        rc, out = quiet(spawn.approve, str(self.team), q, env=self.env)
        self.assertEqual(rc, 0, out)
        self.assertIn('已經回覆過', out)
        self.assertEqual(len(self.human_box()), 1)
        self.assertEqual(list(self.roster['members']).count('worker-2'), 1)

    def test_approve_after_plain_answer_sends_letter(self):
        q = self.ask_and_get_q()
        ask.on_answer(self.lay, self.roster, {'id': 'a1', 'from': 'human', 'kind': 'answer', 'q': q, 'text': '批准'})
        rc, out = quiet(spawn.approve, str(self.team), q, env=self.env)
        self.assertEqual(rc, 0, out)
        box = self.human_box()
        self.assertEqual((box[0].get('kind'), box[0]['to'], box[0]['reply_to']), (None, 'lead', q))

    def test_denied_cannot_be_approved(self):
        q = self.ask_and_get_q()
        ask.on_answer(self.lay, self.roster, {'id': 'a1', 'from': 'human', 'kind': 'answer', 'q': q, 'text': '不要'})
        self.err('Closed', spawn.approve, str(self.team), q)
        self.assertNotIn('worker-2', self.roster['members'])

    def test_approve_rechecks_roster_changed_meanwhile(self):
        q = self.ask_and_get_q()
        r = json.loads(json.dumps(ROSTER))
        r['spawn']['templates'] = ['importer']         # 人在這中間把 worker 從白名單拿掉
        (self.team / 'team.json').write_text(json.dumps(r), encoding='utf-8')
        self.err('BadTemplate', spawn.approve, str(self.team), q)
        self.assertFalse(self.lay.member('worker-2').exists())

    def test_ls_shows_states(self):
        q = self.ask_and_get_q()
        rc, out = quiet(spawn.cmd_spawn, str(self.team), ['ls'])
        self.assertIn('等你批', out)
        quiet(spawn.approve, str(self.team), q, env=self.env)
        rc, out = quiet(spawn.cmd_spawn, str(self.team), ['ls'])
        self.assertIn('已生', out)

    def test_stop_and_remove_spawned_member(self):
        q = self.ask_and_get_q()
        quiet(spawn.approve, str(self.team), q, env=self.env)
        rc, out = quiet(aos_team.cmd_rm, str(self.team), ['worker-2'])
        self.assertEqual(rc, 0, out)
        self.assertNotIn('worker-2', self.roster['members'])
        self.assertNotIn('worker-2', self.roster['members']['lead']['mail_to'])
        self.assertTrue(any(p.name.startswith('worker-2-') for p in (self.lay.members / '.removed').iterdir()))


class ToolAndPostTests(Base):
    real_homes = True

    def run_tool(self, member, args):
        tools = self.lay.member(member) / 'tools' / 'task'
        r = subprocess.run([sys.executable, str(tools / 'spawn_member')], input=json.dumps(args), cwd=str(tools),
                           capture_output=True, text=True, timeout=30)
        return r.returncode, r.stdout

    def point_outbox(self, member):
        cfg_path = self.lay.member(member) / 'tools' / 'task' / 'config.json'
        cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
        cfg['outbox'] = str(self.lay.outbox(member))
        cfg_path.write_text(json.dumps(cfg), encoding='utf-8')

    def post_once(self):
        lines = []
        post.Post(self.team, out=lines.append, submit=lambda job, argv: {'mode': 'test'},
                  health=lambda n: ('ok', 'ok'), watch_every=0).run()
        return lines

    def test_lead_tool_to_question(self):
        self.point_outbox('lead')
        code, out = self.run_tool('lead', {'template': 'worker', 'name': 'worker-2', 'reason': '三個專案'})
        self.assertEqual(code, 0, out)
        self.post_once()
        qs = self.open_questions()
        self.assertEqual(len(qs), 1, qs)
        self.assertEqual(qs[0]['tag'], 'member')

    def test_tool_catches_mail_to_typo(self):
        self.point_outbox('lead')
        code, out = self.run_tool('lead', {'template': 'worker', 'name': 'w2', 'reason': 'x', 'mail_to': ['boss']})
        self.assertEqual(json.loads(out.splitlines()[-1])['error'], 'BadArguments')

    def test_forged_request_from_worker_rejected_by_post(self):
        # 工人手上沒有 spawn_member；自己在 outbox 寫一份也會被郵差用 may 退件
        rid = fmt.new_id('worker-1')
        box = self.lay.outbox('worker-1')
        (box / (rid + '.json')).write_text(json.dumps(req('worker-1', rid, name='worker-9')), encoding='utf-8')
        self.post_once()
        self.assertTrue((box / 'rejected' / (rid + '.json')).exists())
        self.assertEqual(self.open_questions(), [])


ROSTER_DEFAULT = {k: v for k, v in ROSTER.items() if k != 'spawn'}   # 名冊沒寫 spawn＝09-25 翻案後的預設


def with_member(roster, name, spawn_value):
    r = json.loads(json.dumps(roster))
    r['members'][name]['spawn'] = spawn_value
    return r


def task_tools(lay, name):
    info = fmt.read_json(lay.member(name) / 'info.json')
    return next(e['$opt']['only'] for e in info['tools'] if isinstance(e, dict) and 'board' in e['$opt'].get('only', []))


class DefaultOnTests(Base):
    """09-25 使用者翻案（WAIT_USER 39）：預設開、預設不用人批；每個成員能各自設（成員層蓋過團隊層）。"""
    roster_obj = ROSTER_DEFAULT
    real_homes = True

    def setUp(self):
        super().setUp()
        patch = unittest.mock.patch.dict(os.environ, {}, clear=False)
        patch.start()
        self.addCleanup(patch.stop)
        os.environ.pop('AOS_KERNEL_HOME', None)        # 郵差裡生：沒 kernel＝只生家、不登記

    def set_roster(self, r):
        (self.team / 'team.json').write_text(json.dumps(r, ensure_ascii=False), encoding='utf-8')

    def test_default_on_no_approval_builds_member_at_once(self):
        eff = requests.handle(self.lay, self.roster, req())
        self.assertEqual([(e['to'], e['status']) for e in eff], [('lead', 'DONE'), ('human', 'DONE')])
        self.assertIn('已經生好', eff[0]['text'])
        self.assertEqual(self.open_questions(), [])                 # 不開 [成員] 題
        r = self.roster
        self.assertEqual(r['members']['worker-2']['mail_to'], ['lead', 'human'])
        self.assertIn('worker-2', r['members']['lead']['mail_to'])
        self.assertIsNone(r['members']['worker-2']['spawn'])        # 工人模板不能生：不寫
        self.assertTrue((self.lay.member('worker-2') / 'info.json').is_file())
        cfg = json.loads((self.lay.member('lead') / 'tools' / 'task' / 'config.json').read_text(encoding='utf-8'))
        self.assertIn('worker-2', cfg['mail_to'])
        self.assertIn('importer', cfg['spawn_templates'])           # templates 沒寫＝內建模板都可以
        self.assertFalse(cfg['spawn_approve'])
        rec = spawn.records(self.lay)[0]
        self.assertIsNone(rec['q'])
        rc, out = quiet(spawn.cmd_spawn, str(self.team), ['ls'])
        self.assertIn('已生（不用人批）', out)

    def test_default_on_idempotent(self):
        a = spawn.on_spawn(self.lay, self.roster, req())
        b = spawn.on_spawn(self.lay, self.roster, req())
        self.assertEqual(a, b)
        self.assertEqual(len(spawn.records(self.lay)), 1)

    def test_crash_half_way_finishes_on_retry(self):
        # 郵差記了紀錄（effects: null）就崩：同一份申請再來＝補生、回信，不再檢查名字撞到自己
        spawn.on_spawn(self.lay, self.roster, req())
        p = spawn.folder(self.lay) / 's-0001.json'
        rec = fmt.read_json(p)
        rec['effects'] = None
        fmt.write_json(p, rec)
        eff = spawn.on_spawn(self.lay, self.roster, req())
        self.assertEqual(eff[0]['status'], 'DONE')

    def test_member_off(self):
        self.set_roster(with_member(ROSTER_DEFAULT, 'lead', False))
        self.err('NotAllowed', requests.handle, self.lay, self.roster, req())
        self.assertEqual(spawn.records(self.lay), [])
        self.assertNotIn('spawn', fmt.member_may(self.roster, 'lead'))
        # 重生家：工具裡看不到 spawn_member、白名單快照是空的
        rc, out = quiet(aos_team.cmd_rm, str(self.team), ['lead'])
        self.set_roster(with_member(ROSTER_DEFAULT, 'lead', False))
        rc, out = quiet(aos_team.cmd_init, str(self.team), [])
        self.assertEqual(rc, 0, out)
        self.assertNotIn('spawn_member', task_tools(self.lay, 'lead'))
        cfg = json.loads((self.lay.member('lead') / 'tools' / 'task' / 'config.json').read_text(encoding='utf-8'))
        self.assertEqual(cfg['spawn_templates'], [])

    def test_team_off_with_empty_list(self):
        self.set_roster(dict(ROSTER_DEFAULT, spawn={'templates': []}))
        self.err('BadTemplate', requests.handle, self.lay, self.roster, req())

    def test_member_needs_approval(self):
        self.set_roster(with_member(ROSTER_DEFAULT, 'lead', {'approve': True}))
        eff = requests.handle(self.lay, self.roster, req())
        self.assertEqual(eff, [])
        qs = self.open_questions()
        self.assertEqual([q['tag'] for q in qs], ['member'])
        self.assertNotIn('worker-2', self.roster['members'])
        rc, out = quiet(spawn.approve, str(self.team), qs[0]['id'], env=self.env)
        self.assertEqual(rc, 0, out)
        self.assertIn('worker-2', self.roster['members'])

    def test_team_needs_approval_member_overrides_to_no(self):
        r = dict(ROSTER_DEFAULT, spawn={'approve': True})
        self.set_roster(with_member(r, 'lead', {'approve': False}))
        eff = requests.handle(self.lay, self.roster, req())
        self.assertEqual(eff[0]['status'], 'DONE')
        self.assertEqual(self.open_questions(), [])

    def test_member_turns_on_for_worker(self):
        self.set_roster(with_member(ROSTER_DEFAULT, 'worker-1', {'allow': True, 'templates': ['worker']}))
        quiet(aos_team.cmd_rm, str(self.team), ['worker-1'])
        self.set_roster(with_member(ROSTER_DEFAULT, 'worker-1', {'allow': True, 'templates': ['worker']}))
        rc, out = quiet(aos_team.cmd_init, str(self.team), [])
        self.assertEqual(rc, 0, out)
        self.assertIn('spawn_member', task_tools(self.lay, 'worker-1'))
        eff = requests.handle(self.lay, self.roster, req('worker-1', name='worker-3', mail_to=['worker-1', 'lead']))
        self.assertEqual(eff[0]['status'], 'DONE', eff)
        self.err('BadTemplate', requests.handle, self.lay, self.roster, req('worker-1', 'r2', template='importer',
                                                                            name='imp'))

    # ------------------------------------------ 不用人批以後，牆還是關牢 ----

    def test_wall_worker_cannot_spawn_bigger_template(self):
        self.set_roster(with_member(ROSTER_DEFAULT, 'worker-1', True))
        self.err('MayExceeds', requests.handle, self.lay, self.roster, req('worker-1', template='lead'))
        self.assertNotIn('worker-2', self.roster['members'])

    def test_wall_only_builtin_templates(self):
        for bad in ('../../etc', '/tmp/evil', 'nope'):
            with self.subTest(template=bad):
                self.err('BadTemplate', requests.handle, self.lay, self.roster, req(template=bad, rid='r-' + bad[-3:]))
        self.assertEqual(spawn.records(self.lay), [])

    def test_wall_max_members_without_approval(self):
        requests.handle(self.lay, self.roster, req('lead', 'r1', name='worker-2'))
        requests.handle(self.lay, self.roster, req('lead', 'r2', name='worker-3'))
        self.err('TooMany', requests.handle, self.lay, self.roster, req('lead', 'r3', name='worker-4'))
        self.assertEqual(len(self.roster['members']), 4)

    def test_wall_mail_to_not_bigger(self):
        self.err('MailToExceeds', requests.handle, self.lay, self.roster, req(mail_to=['lead', 'reviewer']))

    def test_child_inherits_stricter_setting(self):
        # 申請者被設成「只能生 importer、要人批」：它生的 lead 不能比它寬
        self.set_roster(with_member(ROSTER_DEFAULT, 'lead', {'templates': ['lead'], 'approve': True}))
        requests.handle(self.lay, self.roster, req(template='lead', name='lead-2'))
        q = self.open_questions()[0]['id']
        quiet(spawn.approve, str(self.team), q, env=self.env)
        self.assertEqual(self.roster['members']['lead-2']['spawn'], {'templates': ['lead'], 'approve': True})
        self.assertEqual(fmt.spawn_policy(self.roster, 'lead-2'), {'templates': ['lead'], 'approve': True})

    def test_child_follows_team_when_parent_is_default(self):
        requests.handle(self.lay, self.roster, req(template='lead', name='lead-2'))
        self.assertIsNone(self.roster['members']['lead-2']['spawn'])

    def test_post_end_to_end(self):
        tools = self.lay.member('lead') / 'tools' / 'task'
        cfg = json.loads((tools / 'config.json').read_text(encoding='utf-8'))
        cfg['outbox'] = str(self.lay.outbox('lead'))
        (tools / 'config.json').write_text(json.dumps(cfg), encoding='utf-8')
        r = subprocess.run([sys.executable, str(tools / 'spawn_member')], cwd=str(tools), capture_output=True, text=True,
                           input=json.dumps({'template': 'worker', 'name': 'worker-2', 'reason': '三個專案'}), timeout=30)
        self.assertIn('postman creates it', r.stdout)
        for _ in range(2):
            post.Post(self.team, out=lambda s: None, submit=lambda job, argv: {'mode': 'test'},
                      health=lambda n: ('ok', 'ok'), watch_every=0).run()
        self.assertIn('worker-2', self.roster['members'])
        self.assertEqual(self.open_questions(), [])


if __name__ == '__main__':
    unittest.main()
