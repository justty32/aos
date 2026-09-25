"""T5 收尾：團隊成員的筆記掛載（模板 notes: true → /work/notes＝team/notes/<名>/）與 compact_me（task 包寄 compact 申請）。"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import aos_agent_access
import aos_agent_init
import aos_agent_notes
import aos_team_format as fmt
from _kernel_util import CLI, PY, read_json
from _team_util import TeamCase

PROTO = Path(__file__).resolve().parents[2]
TOOLS = PROTO / 'tools' / 'task'
ROSTER = json.loads((PROTO / 'spec/team/examples/team.json').read_text(encoding='utf-8'))


def cli(prog, *args):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', AOS_KERNEL_HOME='')
    return subprocess.run([PY, str(CLI / prog), *map(str, args)], capture_output=True, text=True, timeout=60,
                          env=env, stdin=subprocess.DEVNULL)


class CompactMeToolTests(unittest.TestCase):
    """compact_me 不關牢直接跑：config.json 指到主機上的 outbox。"""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='aos-compact-me-'))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.pack = self.root / 'task'
        shutil.copytree(TOOLS, self.pack, ignore=shutil.ignore_patterns('__pycache__'))
        self.outbox = self.root / 'outbox'
        self.outbox.mkdir()
        (self.pack / 'config.json').write_text(json.dumps({
            'member': 'worker-1', 'mail_to': ['lead', 'human'], 'members': ['lead', 'worker-1', 'reviewer'],
            'outbox': str(self.outbox), 'board': str(self.root / 'board'), 'tz': 'Asia/Taipei'}))

    def tool(self, args, code=0):
        r = subprocess.run([str(self.pack / 'compact_me')], input=json.dumps(args), capture_output=True, text=True,
                           timeout=20, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        self.assertEqual(r.returncode, code, r.stdout + r.stderr)
        return json.loads(r.stdout.strip().splitlines()[-1]) if code else r.stdout

    def sent(self):
        return [json.loads(p.read_text()) for p in fmt.json_files(self.outbox)]

    def test_writes_compact_request(self):
        out = self.tool({'reason': '對話太長', 'keep_rounds': 2, 'max_tokens': 8000})
        self.assertIn('queued compact request', out)
        self.assertIn('End this turn', out)
        [req] = self.sent()
        fmt.validate_request(req)
        self.assertEqual({k: req[k] for k in ('from', 'kind', 'reason', 'keep_rounds', 'max_tokens')},
                         {'from': 'worker-1', 'kind': 'compact', 'reason': '對話太長', 'keep_rounds': 2,
                          'max_tokens': 8000})
        self.assertNotIn('member', req)                                 # 只能縮自己
        self.assertTrue(req['id'].endswith('-worker-1'))
        self.assertEqual([p.name for p in self.outbox.iterdir()], [req['id'] + '.json'])   # 沒有暫存殘檔

    def test_all_optional(self):
        self.tool({})
        [req] = self.sent()
        self.assertEqual(set(req), {'id', 'from', 'kind', 'at'})

    def test_bad_arguments(self):
        for args in ({'member': 'lead'}, {'keep_rounds': -1}, {'keep_rounds': 1001}, {'keep_rounds': '2'},
                     {'keep_rounds': True}, {'max_tokens': 99}, {'reason': 'x' * 501}, {'reason': ' '}):
            with self.subTest(args=args):
                self.assertEqual(self.tool(args, code=1)['error'], 'BadArguments')
        self.assertEqual(self.sent(), [])

    def test_not_in_team(self):
        (self.pack / 'config.json').unlink()
        self.assertEqual(self.tool({}, code=1)['error'], 'ConfigInvalid')

    def test_no_outbox(self):
        shutil.rmtree(self.outbox)
        self.assertEqual(self.tool({}, code=1)['error'], 'NoOutbox')


class NotesMountTests(unittest.TestCase):
    """aos-team init：worker、lead 多掛 notes → team/notes/<名>/（rw）；reviewer 沒有。"""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='aos-team-notes-'))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        (self.root / 'p').mkdir()
        self.team = self.root / 'team'
        src = self.root / 'roster.json'
        src.write_text(json.dumps(ROSTER, ensure_ascii=False), encoding='utf-8')
        r = cli('aos-team', 'init', '--config', src, '--target', self.team)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.lay = fmt.Layout(self.team)

    def test_worker_and_lead_have_notes(self):
        for name in ('lead', 'worker-1'):
            home = self.lay.member(name)
            self.assertTrue(self.lay.notes(name).is_dir())
            self.assertEqual(read_json(home / 'access.json')['mounts']['notes'], '../../team/notes/' + name)
            table = aos_agent_access.load(str(home))
            self.assertEqual(table['mounts']['notes']['path'], str(self.lay.notes(name)))
            self.assertFalse(table['mounts']['notes']['ro'])
            self.assertTrue((home / 'tools' / 'notes.json').exists())
            self.check(home)
            # 人看的 aos-agent notes：從 access.json 的 notes 掛載找回主機路徑
            self.assertEqual(aos_agent_notes.notes_file(str(home)), str(self.lay.notes(name) / 'notes.json'))

    def test_reviewer_has_no_notes(self):
        home = self.lay.member('reviewer')
        self.assertNotIn('notes', read_json(home / 'access.json')['mounts'])
        self.assertFalse(self.lay.notes('reviewer').exists())
        self.assertFalse((home / 'tools' / 'notes.json').exists())
        self.check(home)

    def check(self, home):
        """aos-agent check：沒 kernel 時 kernel 那項一定 bad（真 kernel 的全過在 test_team_init 的整合測試），
        其他（工具、access、bwrap）都要 ok。"""
        r = cli('aos-agent', 'check', '--target', home)
        bad = [x for x in r.stdout.splitlines() if x.startswith('bad') and not x.startswith('bad  kernel')]
        self.assertEqual(bad, [], r.stdout + r.stderr)
        self.assertIn('ok   access: ', r.stdout)
        self.assertNotIn('bad  access', r.stdout)

    def test_may_and_tools(self):
        for tpl, want in (('lead', True), ('worker', True), ('reviewer', False)):
            self.assertEqual('compact' in fmt.template_may(tpl), want, tpl)
        info = read_json(self.lay.member('worker-1') / 'info.json')
        only = [e['$opt']['only'] for e in info['tools'] if isinstance(e, dict) and 'task.json' in e['$val']]
        self.assertEqual(only, [['board', 'ask_human', 'compact_me', 'lock', 'access_request', 'persona_propose',
                                 'tool_draft', 'commons_search', 'commons_submit']])   # 09-25 commons 預設開

    def test_rerun_on_old_home_adds_notes_mount_only(self):
        """已生的舊家（notes 前生的）：重跑 init 補 notes 那一格＋資料夾，其他掛載不動。"""
        home = self.lay.member('worker-1')
        access = read_json(home / 'access.json')
        del access['mounts']['notes']
        access['mounts']['extra'] = {'$opt': 'ro', '$val': '../../../p'}       # 人自己加的，不能被蓋
        (home / 'access.json').write_text(json.dumps(access), encoding='utf-8')
        shutil.rmtree(self.lay.notes('worker-1'))
        r = cli('aos-team', 'init', '--target', self.team)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('worker-1: access.json 補掛 notes', r.stdout)
        self.assertNotIn('lead: access.json 補掛', r.stdout)
        after = read_json(home / 'access.json')['mounts']
        self.assertEqual(after['notes'], '../../team/notes/worker-1')
        self.assertEqual(after['extra'], access['mounts']['extra'])
        self.assertTrue(self.lay.notes('worker-1').is_dir())
        # notes 被人改指別處：不動
        after['notes'] = '../../../p'
        access['mounts'] = after
        (home / 'access.json').write_text(json.dumps(access), encoding='utf-8')
        r = cli('aos-team', 'init', '--target', self.team)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(read_json(home / 'access.json')['mounts']['notes'], '../../../p')

    def test_notes_is_reserved_mount_name(self):
        roster = read_json(self.team / 'team.json')
        roster['members']['worker-1']['mounts'] = {'notes': '../elsewhere'}
        with self.assertRaises(fmt.TeamError) as cm:
            fmt.validate_roster(roster)
        self.assertIn('notes', cm.exception.msg)


class LayoutPathTests(unittest.TestCase):
    def test_events_in_member_home(self):
        """事件紀錄在成員家（aos_agent_events 寫的那份），不在 team/events/。"""
        import aos_agent_events
        lay = fmt.Layout('/t')
        self.assertEqual(lay.events('worker-1'), lay.member('worker-1') / aos_agent_events.EVENTS)
        self.assertEqual(lay.notes('worker-1'), Path('/t/team/notes/worker-1'))


class TemplateNotesKeyTests(unittest.TestCase):
    def tpl(self, **over):
        obj = {'_metainfo': {'_type': 'aos_team_template', '_version': 1}, 'description': 'd', 'system': 's.md',
               'team': True}
        obj.update(over)
        return obj

    def test_notes_key(self):
        fmt.validate_template(self.tpl(notes=True))
        for over in ({'notes': 'yes'}, {'notes': True, 'team': False}):
            with self.subTest(over=over), self.assertRaises(fmt.TeamError):
                fmt.validate_template(self.tpl(**over))

    def test_solo_template_has_no_notes(self):
        """coder（不在團隊）沒有 notes 旗標：單獨生的家只有 ws。"""
        root = Path(tempfile.mkdtemp(prefix='aos-solo-'))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        aos_agent_init.init_from_template(root / 'solo', 'coder')
        self.assertEqual(read_json(root / 'solo' / 'access.json')['mounts'], {'ws': 'workspace'})


class CompactRequestPostTests(TeamCase):
    """真郵差：may 有 compact 的成員寄 compact 申請 → 投進自己家的 compact-req/；沒有的退件。"""

    def request(self, sender, **body):
        rid = self.new_id(sender)
        obj = dict({'id': rid, 'from': sender, 'kind': 'compact', 'at': self.now.isoformat()}, **body)
        (self.lay.outbox(sender) / (rid + '.json')).write_text(json.dumps(obj, ensure_ascii=False), encoding='utf-8')
        return rid

    def test_worker_request_lands_in_compact_req(self):
        rid = self.request('worker-1', keep_rounds=3, reason='太長')
        self.assertEqual(self.post(), 0)
        dropped = self.lay.member('worker-1') / 'compact-req' / (rid + '.json')
        body = json.loads(dropped.read_text(encoding='utf-8'))
        self.assertEqual((body['from'], body['keep_rounds'], body['reason']), ('worker-1', 3, '太長'))
        self.assertTrue((self.lay.outbox('worker-1') / 'done' / (rid + '.json')).exists())
        self.assertEqual(self.mails('worker-1'), [])                    # 沒有退件信
        self.post()                                                     # 再跑一輪：原檔還在、不重投
        self.assertEqual(len(list((self.lay.member('worker-1') / 'compact-req').glob('*.json'))), 1)

    def test_lead_may_compact(self):
        rid = self.request('lead')
        self.post()
        self.assertTrue((self.lay.member('lead') / 'compact-req' / (rid + '.json')).exists())

    def test_reviewer_not_allowed(self):
        rid = self.request('reviewer')
        self.post()
        self.assertTrue((self.lay.outbox('reviewer') / 'rejected' / (rid + '.json')).exists())
        self.assertFalse((self.lay.member('reviewer') / 'compact-req').exists())
        self.assertIn('NotAllowed', self.mails('reviewer')[0][1])

    def test_cannot_shrink_someone_else(self):
        rid = self.request('worker-1', member='lead')
        self.post()
        self.assertTrue((self.lay.outbox('worker-1') / 'rejected' / (rid + '.json')).exists())
        self.assertFalse((self.lay.member('lead') / 'compact-req').exists())


if __name__ == '__main__':
    unittest.main()
