"""09-25 commons：跨團隊公共資料夾（spec/team/commons.md）。

掛載三層（預設開、團隊關、逐成員蓋過、重跑 init 補掛／拿掉）；投稿機械擋（缺欄位、路徑、太大、執行位、完全重複、符號連結）；
入庫後 index.json／INDEX.md；像既有條目才叫圖書館員、判決入庫／退回、非圖書館員寄判決被擋；
兩隊＋圖書館員隊經真郵差走完一圈；成員在牢裡寫 commons 被牆擋；工具與 lib 查法一致；人用 CLI。不叫模型、不碰 kernel。
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

import aos_agent_access
import aos_team
import aos_team_commons as cm
import aos_team_format as fmt
import aos_team_post as post

PROTO = Path(__file__).resolve().parents[2]
TASK_TOOLS = PROTO / 'tools' / 'task'


def roster(members, **top):
    r = {'_metainfo': {'_type': 'aos_team', '_version': 1}, 'project': '../p', 'members': members}
    r.update(top)
    return r


TEAM_A = roster({'lead': {'template': 'lead', 'mail_to': ['worker-a', 'human']},
                 'worker-a': {'template': 'worker', 'mail_to': ['lead', 'human']}})
TEAM_B = roster({'worker-b': {'template': 'worker', 'mail_to': ['human']}})
LIB = roster({'librarian': {'template': 'librarian', 'mail_to': ['human']}})


def quiet(fn, *a, **kw):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
        rc = fn(*a, **kw)
    return rc, buf.getvalue()


def lesson(**over):
    s = {'type': 'lesson', 'title': 'verify done_when paths before handoff', 'tags': ['handoff', 'done_when'],
         'fits': 'leads writing handoff tickets', 'body': 'Check every done_when path exists in the project first.'}
    s.update(over)
    return s


class Base(unittest.TestCase):
    def setUp(self):
        self.root = Path(os.path.realpath(tempfile.mkdtemp(prefix='aos-commons-')))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        (self.root / 'p').mkdir()
        self.commons = cm.Commons(self.root / 'commons')

    def make_team(self, name, obj, init=True):
        team = self.root / name
        team.mkdir()
        (team / 'team.json').write_text(json.dumps(obj, ensure_ascii=False), encoding='utf-8')
        if init:
            rc, out = quiet(aos_team.cmd_init, str(team), [])
            self.assertEqual(rc, 0, out)
        else:
            lay = fmt.Layout(team)
            for d in lay.skeleton(obj['members']):
                d.mkdir(parents=True, exist_ok=True)
        return team

    def home(self, team, name):
        return fmt.Layout(team).member(name)

    def mounts(self, team, name):
        return json.loads((self.home(team, name) / 'access.json').read_text(encoding='utf-8'))['mounts']

    def tools(self, team, name):
        import aos_agent_context
        import aos_agent_info
        return set(aos_agent_context.measure(aos_agent_info.load(str(self.home(team, name))))['tools']['names'])

    def post_once(self, team):
        lines = []
        post.Post(team, out=lines.append, submit=lambda job, argv: {'mode': 'test'},
                  health=lambda n: ('ok', 'ok'), watch_every=0).run()
        return lines

    def drop(self, sub, files=None, cid='c-x--1'):
        """直接擺一份投稿進 inbox（模擬別隊郵差送來的；圖書館員那邊一律再驗）。"""
        folder = self.commons.ensure().inbox / cid
        (folder / 'files').mkdir(parents=True)
        for rel, (data, mode) in (files or {}).items():
            p = folder / 'files' / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            os.chmod(p, mode)
        fmt.write_json(folder / 'submission.json', dict(sub, source={'team': 'x', 'member': 'w', 'task': None}))
        return folder

    def result(self, folder):
        return json.loads((folder / 'result.json').read_text(encoding='utf-8'))


class MountTests(Base):
    def test_default_on_mounts_ro_and_installs_tools(self):
        team = self.make_team('ta', TEAM_A)
        for name in ('lead', 'worker-a'):
            m = self.mounts(team, name)['commons']
            self.assertEqual(m['$opt'], 'ro')
            self.assertEqual(os.path.realpath(self.home(team, name) / m['$val']), str(self.root / 'commons'))
            self.assertLessEqual({'commons_search', 'commons_submit'}, self.tools(team, name))
            cfg = json.loads((self.home(team, name) / 'tools' / 'task' / 'config.json').read_text(encoding='utf-8'))
            self.assertEqual(cfg['commons'], '/work/commons')
        self.assertTrue((self.root / 'commons' / 'index.json').is_file())
        self.assertIn('contribute', fmt.member_may(fmt.load_roster(team), 'worker-a'))
        aos_agent_access.load(str(self.home(team, 'worker-a')))      # 掛得起來、不蓋信任資料

    def test_team_off(self):
        team = self.make_team('ta', dict(TEAM_A, commons=False))
        self.assertNotIn('commons', self.mounts(team, 'worker-a'))
        self.assertFalse({'commons_search', 'commons_submit'} & self.tools(team, 'worker-a'))
        self.assertNotIn('contribute', fmt.member_may(fmt.load_roster(team), 'worker-a'))
        self.assertFalse((self.root / 'commons').exists())

    def test_member_overrides_team(self):
        obj = json.loads(json.dumps(TEAM_A))
        obj['commons'] = False
        obj['members']['worker-a']['commons'] = True
        team = self.make_team('ta', obj)
        self.assertIn('commons', self.mounts(team, 'worker-a'))
        self.assertNotIn('commons', self.mounts(team, 'lead'))
        obj2 = json.loads(json.dumps(TEAM_A))
        obj2['members']['lead']['commons'] = False
        team2 = self.make_team('tb', obj2)
        self.assertNotIn('commons', self.mounts(team2, 'lead'))
        self.assertIn('commons', self.mounts(team2, 'worker-a'))

    def test_reinit_turning_off_removes_mount(self):
        team = self.make_team('ta', TEAM_A)
        obj = json.loads((team / 'team.json').read_text(encoding='utf-8'))
        obj['members']['worker-a']['commons'] = False
        (team / 'team.json').write_text(json.dumps(obj), encoding='utf-8')
        rc, out = quiet(aos_team.cmd_init, str(team), [])
        self.assertEqual(rc, 0, out)
        self.assertIn('拿掉 commons', out)
        self.assertNotIn('commons', self.mounts(team, 'worker-a'))
        self.assertIn('commons', self.mounts(team, 'lead'))

    def test_custom_dir_and_bad_values(self):
        team = self.make_team('ta', dict(TEAM_A, commons={'dir': '../shared'}))
        self.assertTrue((self.root / 'shared' / 'index.json').is_file())
        for bad in ('yes', {'on': 'x'}, {'dir': ''}, {'where': 'x'}):
            with self.assertRaises(fmt.TeamError):
                fmt.validate_roster(dict(TEAM_A, commons=bad))
        with self.assertRaises(fmt.TeamError):
            m = json.loads(json.dumps(TEAM_A))
            m['members']['lead']['commons'] = 'no'
            fmt.validate_roster(m)
        with self.assertRaises(fmt.TeamError):         # commons 是保留掛點名
            m = json.loads(json.dumps(TEAM_A))
            m['members']['lead']['mounts'] = {'commons': '../x'}
            fmt.validate_roster(m)

    def test_commons_inside_project_refused(self):
        with self.assertRaises(fmt.TeamError) as c:
            self.make_team('ta', dict(TEAM_A, commons={'dir': '../p/commons'}))
        self.assertEqual(c.exception.code, 'BadCommons')


class DeskCheckTests(Base):
    """圖書館員那邊的機械檢查：四種壞投稿＋完全重複，全不叫模型。"""

    def setUp(self):
        super().setUp()
        self.lib = self.make_team('lib', LIB, init=False)
        self.lay = fmt.Layout(self.lib)
        self.rost = fmt.load_roster(self.lib)

    def desk(self):
        return cm.desk(self.lay, self.rost)

    def test_missing_field(self):
        sub = lesson()
        del sub['fits']
        f = self.drop(sub)
        self.assertEqual(self.desk(), [])
        self.assertEqual(self.result(f)['status'], 'rejected')
        self.assertIn('MissingField', self.result(f)['reason'])

    def test_bad_path(self):
        for i, bad_path in enumerate(('../escape.sh', '/etc/passwd', 'a/../../b', 'README.md')):
            f = self.drop(lesson(type='tool', files=[bad_path]), cid='c-x--p%d' % i)
            self.desk()
            self.assertIn('BadPath', self.result(f)['reason'], bad_path)

    def test_too_large(self):
        big = b'x' * (cm.LIMITS['file_bytes'] + 1)
        f = self.drop(lesson(type='tool', files=['big.txt']), {'big.txt': (big, 0o644)})
        self.desk()
        self.assertIn('TooLarge', self.result(f)['reason'])
        f2 = self.drop(lesson(body='x' * (cm.LIMITS['body'] + 1)), cid='c-x--2')
        self.desk()
        self.assertIn('TooLarge', self.result(f2)['reason'])

    def test_exec_bit_only_on_scripts(self):
        f = self.drop(lesson(type='tool', files=['notes.txt']), {'notes.txt': (b'plain text', 0o755)})
        self.desk()
        self.assertIn('BadMode', self.result(f)['reason'])
        ok = self.drop(lesson(type='tool', title='runner script', files=['run.sh']),
                       {'run.sh': (b'#!/bin/sh\necho hi\n', 0o755)}, cid='c-x--2')
        self.desk()
        self.assertEqual(self.result(ok)['status'], 'accepted')
        eid = self.result(ok)['id']
        self.assertTrue(os.access(self.commons.root / 'tools' / eid / 'run.sh', os.X_OK))

    def test_symlink_attachment(self):
        f = self.drop(lesson(type='tool', files=['link']))
        os.symlink('/etc/passwd', f / 'files' / 'link')
        self.desk()
        self.assertIn('BadFile', self.result(f)['reason'])

    def test_exact_duplicate(self):
        a = self.drop(lesson())
        self.desk()
        self.assertEqual(self.result(a)['status'], 'accepted')
        b = self.drop(lesson(title='totally different words here'), cid='c-x--2')
        self.desk()
        self.assertIn('Duplicate', self.result(b)['reason'])     # 只換標題、內容（種類＋body＋附件）一樣＝重複
        c = self.drop(lesson(body='a new body'), cid='c-x--3')
        self.desk()
        self.assertNotIn('Duplicate', (self.result(c) if (c / 'result.json').exists() else {}).get('reason') or '')

    def test_ingest_updates_index_and_index_md(self):
        f = self.drop(lesson(task='t-0003'))
        self.desk()
        res = self.result(f)
        self.assertEqual((res['status'], res['by']), ('accepted', 'machine'))
        idx = self.commons.load_index()
        e = idx['entries'][res['id']]
        self.assertEqual(e['path'], 'lessons/%s.md' % res['id'])
        self.assertEqual(e['from'], {'team': 'x', 'member': 'w', 'task': None})
        self.assertTrue(e['date'])
        text = (self.commons.root / e['path']).read_text(encoding='utf-8')
        self.assertIn('適合：leads writing handoff tickets', text)
        self.assertIn(res['id'], (self.commons.root / 'INDEX.md').read_text(encoding='utf-8'))

    def test_similar_asks_librarian_once(self):
        self.drop(lesson())
        self.desk()
        f = self.drop(lesson(body='Another angle: also check the workflow file.'), cid='c-x--2')
        asks = self.desk()
        self.assertEqual(len(asks), 1)
        rid, effects = asks[0]
        self.assertEqual(rid, 'commons.judge.c-x--2')
        self.assertEqual(effects[0]['to'], 'librarian')
        self.assertIn('commons_verdict', effects[0]['text'])
        self.assertFalse((f / 'result.json').exists())
        self.assertEqual([r for r, _ in self.desk()], [rid])      # 每輪都給同一個 id（郵差 notice 去重）

    def test_similar_by_keywords_real_pair(self):
        # 09-25 真跑 r2：種子與 astra 寫的是同一件事，標題重疊只有 0.21，舊判法漏掉、直接入庫
        idx = {'entries': {'seed': {'type': 'lesson', 'title': 'done_when paths must be relative to the project',
                                    'tags': ['handoff', 'done_when', 'paths'], 'fits': 'leads writing handoff tickets'}}}
        new = cm.check_fields(lesson(title='Use project-relative paths in task acceptance checks',
                                     tags=['delegation', 'validation', 'paths'],
                                     fits='適合用 handoff 派工、以 done_when 的檔案檢查驗收交付物的工作。'))
        self.assertEqual(cm.similar(idx, new, 'x'), (None, ['seed']))
        other = cm.check_fields(lesson(title='Keep jail mounts read-only', tags=['wall'], fits='anyone mounting'))
        self.assertEqual(cm.similar(idx, other, 'x'), (None, []))

    def test_no_librarian_no_desk(self):
        team = self.make_team('ta', TEAM_A, init=False)
        self.drop(lesson())
        self.assertEqual(cm.desk(fmt.Layout(team), fmt.load_roster(team)), [])
        self.assertFalse((self.commons.inbox / 'c-x--1' / 'result.json').exists())


class ContributeTests(Base):
    """投稿者團隊的郵差 on_contribute：抄附件的路徑／大小／符號連結檢查。"""

    def setUp(self):
        super().setUp()
        self.team = self.make_team('ta', TEAM_A, init=False)
        self.lay = fmt.Layout(self.team)
        self.rost = fmt.load_roster(self.team)
        self.box = self.lay.outbox('worker-a')

    def req(self, **over):
        r = dict(lesson(), id=fmt.new_id('worker-a'), **{'from': 'worker-a', 'kind': 'contribute', 'at': 'x'})
        r.update(over)
        return r

    def err(self, code, r):
        with self.assertRaises(fmt.TeamError) as c:
            cm.on_contribute(self.lay, self.rost, r)
        self.assertEqual(c.exception.code, code, c.exception.msg)

    def test_ok_and_idempotent(self):
        r = self.req()
        e1 = cm.on_contribute(self.lay, self.rost, r)
        e2 = cm.on_contribute(self.lay, self.rost, r)
        self.assertEqual(e1, e2)
        self.assertEqual(len([p for p in self.commons.inbox.iterdir()]), 1)
        self.assertIn('送到圖書館', e1[0]['text'])

    def test_rejects(self):
        self.err('MissingField', self.req(title=''))
        self.err('BadPath', self.req(type='tool', files=['/etc/passwd']))
        self.err('BadPath', self.req(type='tool', files=['../ta/team.json']))
        self.err('BadFile', self.req(type='tool', files=['nope.txt']))
        os.symlink('/etc/passwd', self.box / 'pw')
        self.err('BadFile', self.req(type='tool', files=['pw']))
        (self.box / 'big').write_bytes(b'x' * (cm.LIMITS['file_bytes'] + 1))
        self.err('TooLarge', self.req(type='tool', files=['big']))
        self.err('FormatInvalid', self.req(files=['x']))           # lesson 不能附檔

    def test_off_member_not_allowed(self):
        obj = json.loads(json.dumps(TEAM_A))
        obj['members']['worker-a']['commons'] = False
        (self.team / 'team.json').write_text(json.dumps(obj), encoding='utf-8')
        rost = fmt.load_roster(self.team)
        self.assertNotIn('contribute', fmt.member_may(rost, 'worker-a'))
        with self.assertRaises(fmt.TeamError):
            cm.on_contribute(self.lay, rost, self.req())


class EndToEndTests(Base):
    """兩隊＋圖書館員隊，工具（不關牢，outbox 指回主機路徑）＋真郵差走一圈。"""

    def setUp(self):
        super().setUp()
        self.ta = self.make_team('ta', TEAM_A)
        self.tb = self.make_team('tb', TEAM_B)
        self.lib = self.make_team('lib', LIB)

    def run_tool(self, team, member, tool, args, commons=True):
        tools = self.home(team, member) / 'tools' / 'task'
        cfg_path = tools / 'config.json'
        cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
        cfg['outbox'] = str(fmt.Layout(team).outbox(member))
        if commons:
            cfg['commons'] = str(self.commons.root)
        cfg_path.write_text(json.dumps(cfg), encoding='utf-8')
        r = subprocess.run([sys.executable, str(tools / tool)], input=json.dumps(args), cwd=str(tools),
                           capture_output=True, text=True, timeout=30)
        return r.returncode, r.stdout

    def inbox_letters(self, team, member):
        box = self.home(team, member) / 'input'
        return [{'text': p.read_text(encoding='utf-8')} for p in box.glob('mail-*.json')]   # 整封當字串比

    def test_a_submits_lib_ingests_b_finds(self):
        rc, out = self.run_tool(self.ta, 'worker-a', 'commons_submit', dict(lesson(), task='t-0001'))
        self.assertEqual(rc, 0, out)
        self.post_once(self.ta)                         # A 郵差：抄進 inbox、回「送到了」
        self.assertEqual(len(list(self.commons.inbox.iterdir())), 1)
        self.post_once(self.lib)                        # 圖書館員郵差：機械檢查過、直接入庫
        idx = self.commons.load_index()
        self.assertEqual(len(idx['entries']), 1)
        (eid, e), = idx['entries'].items()
        self.assertEqual(e['from'], {'team': 'ta', 'member': 'worker-a', 'task': 't-0001'})
        self.post_once(self.ta)                         # A 郵差：看到結果、寄信給投稿者
        texts = [l.get('text', '') for l in self.inbox_letters(self.ta, 'worker-a')]
        self.assertTrue(any('入庫了' in t and e['path'] in t for t in texts), texts)
        self.post_once(self.ta)                         # 不重寄
        self.assertEqual(len([t for t in (l.get('text', '') for l in self.inbox_letters(self.ta, 'worker-a'))
                              if '入庫了' in t]), 1)
        rc, out = self.run_tool(self.tb, 'worker-b', 'commons_search', {'query': 'handoff done_when paths'})
        self.assertEqual(rc, 0, out)
        self.assertIn(eid, out)
        self.assertIn('/work/commons/' + e['path'], out)
        rc, out = self.run_tool(self.tb, 'worker-b', 'commons_search', {'show': eid})
        self.assertIn('Check every done_when path', out)

    def test_similar_goes_to_librarian_verdict(self):
        self.run_tool(self.ta, 'worker-a', 'commons_submit', lesson())
        self.post_once(self.ta)
        self.post_once(self.lib)
        self.run_tool(self.ta, 'worker-a', 'commons_submit',
                      lesson(body='Also: done_when paths must be relative to the project.'))
        self.post_once(self.ta)
        self.post_once(self.lib)
        asks = [l for l in self.inbox_letters(self.lib, 'librarian') if 'commons_verdict' in l.get('text', '')]
        self.assertEqual(len(asks), 1)
        cid = next(p.name for p in self.commons.inbox.iterdir() if (p / 'judge.json').exists())
        rc, out = self.run_tool(self.lib, 'librarian', 'commons_verdict',
                                {'submission': cid, 'verdict': 'accept', 'reason': 'adds the relative-path rule'})
        self.assertEqual(rc, 0, out)
        self.post_once(self.lib)
        res = json.loads((self.commons.inbox / cid / 'result.json').read_text(encoding='utf-8'))
        self.assertEqual((res['status'], res['by']), ('accepted', 'lib/librarian'))
        self.assertEqual(len(self.commons.load_index()['entries']), 2)
        self.post_once(self.ta)
        self.assertTrue(any('入庫了' in l.get('text', '') and cid in l.get('text', '')
                            for l in self.inbox_letters(self.ta, 'worker-a')))

    def test_non_librarian_verdict_rejected(self):
        rid = fmt.new_id('worker-b')
        box = fmt.Layout(self.tb).outbox('worker-b')
        (box / (rid + '.json')).write_text(json.dumps({'id': rid, 'from': 'worker-b', 'kind': 'commons_write',
                                                       'at': 'x', 'submission': 'c-x--1', 'verdict': 'accept',
                                                       'reason': 'me'}), encoding='utf-8')
        self.post_once(self.tb)
        self.assertTrue((box / 'rejected' / (rid + '.json')).exists())

    def test_verdict_only_for_asked(self):
        self.run_tool(self.ta, 'worker-a', 'commons_submit', lesson())
        self.post_once(self.ta)
        cid = next(self.commons.inbox.iterdir()).name
        req = {'id': fmt.new_id('librarian'), 'from': 'librarian', 'kind': 'commons_write', 'at': 'x',
               'submission': cid, 'verdict': 'reject', 'reason': 'no'}
        with self.assertRaises(fmt.TeamError) as c:
            cm.on_commons_write(fmt.Layout(self.lib), fmt.load_roster(self.lib), req)
        self.assertEqual(c.exception.code, 'NotAsked')

    def test_search_tool_matches_lib(self):
        for i, (title, tags) in enumerate((('jail write tips', ['wall']), ('handoff paths', ['handoff']),
                                           ('wall and handoff together', ['wall', 'handoff']))):
            with self.commons.lock():
                cm.ingest(self.commons, cm.check_fields(lesson(title=title, tags=tags, body='b%d' % i)),
                          {'team': 't', 'member': 'm', 'task': None})
        for q, tags in (('wall', []), ('handoff', ['wall']), ('', ['handoff']), ('nothing-here', [])):
            want = [eid for _, eid, _ in cm.search(self.commons.load_index(), q, tags)]
            rc, out = self.run_tool(self.tb, 'worker-b', 'commons_search', {'query': q, 'tags': tags})
            got = [line.split(' ')[0] for line in out.splitlines() if line and not line.startswith(' ')]
            self.assertEqual(got if want else [], want, out)

    def test_tool_off_says_no_commons(self):
        obj = json.loads((self.tb / 'team.json').read_text(encoding='utf-8'))
        obj['commons'] = False
        (self.tb / 'team.json').write_text(json.dumps(obj), encoding='utf-8')
        tools = self.home(self.tb, 'worker-b') / 'tools' / 'task'
        cfg = json.loads((tools / 'config.json').read_text(encoding='utf-8'))
        cfg['commons'] = None
        (tools / 'config.json').write_text(json.dumps(cfg), encoding='utf-8')
        r = subprocess.run([sys.executable, str(TASK_TOOLS / 'commons_submit')], input=json.dumps(lesson()),
                           cwd=str(tools), capture_output=True, text=True, timeout=30)
        self.assertNotEqual(r.returncode, 0)


def _bwrap_ok():
    try:
        from test_jail import bwrap_works
        return bwrap_works()
    except Exception:
        return False


@unittest.skipUnless(_bwrap_ok(), '這台沒有可用的 bwrap')
class WallTests(Base):
    def test_member_cannot_write_commons_in_jail(self):
        team = self.make_team('ta', TEAM_A)
        home = self.home(team, 'worker-a')
        table = aos_agent_access.load(str(home))
        flags = []
        for name, m in table['mounts'].items():
            flags += ['--mount-ro' if m['ro'] else '--mount', '%s=%s' % (name, m['path'])]
        script = 'cat /work/commons/index.json >/dev/null && echo x > /work/commons/lessons/evil.md'
        r = subprocess.run([aos_agent_access.JAIL, *flags, '--chdir', 'ws', '--net', 'off', '--', 'sh', '-c', script],
                           capture_output=True, text=True, timeout=30)
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((self.root / 'commons' / 'lessons' / 'evil.md').exists())
        r = subprocess.run([aos_agent_access.JAIL, *flags, '--chdir', 'ws', '--net', 'off', '--', 'sh', '-c',
                            'echo ok > /work/outbox/probe'], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)              # 對照：自己的 outbox 寫得進去


class CliTests(Base):
    def test_add_ls_show_rm_reindex(self):
        team = self.make_team('ta', TEAM_A, init=False)
        body = self.root / 'b.md'
        body.write_text('hand written lesson', encoding='utf-8')
        rc, out = quiet(cm.cmd_commons, str(team), ['add', 'lesson', '--title', 'by hand', '--fits', 'anyone',
                                                   '--tags', 'x,y', '--body-file', str(body), '--slug', 'by-hand'])
        self.assertEqual(rc, 0, out)
        self.assertIn('by-hand', quiet(cm.cmd_commons, str(team), ['ls'])[1])
        self.assertIn('hand written lesson', quiet(cm.cmd_commons, str(team), ['show', 'by-hand'])[1])
        idx = json.loads((self.commons.root / 'index.json').read_text(encoding='utf-8'))
        idx['entries']['by-hand']['title'] = 'edited in a text editor'
        (self.commons.root / 'index.json').write_text(json.dumps(idx, indent=2), encoding='utf-8')
        quiet(cm.cmd_commons, str(team), ['reindex'])
        self.assertIn('edited in a text editor', (self.commons.root / 'INDEX.md').read_text(encoding='utf-8'))
        with self.assertRaises(fmt.TeamError):                     # 完全重複
            quiet(cm.cmd_commons, str(team), ['add', 'lesson', '--title', 'by hand', '--fits', 'anyone',
                                              '--tags', 'x', '--body-file', str(body)])
        quiet(cm.cmd_commons, str(team), ['rm', 'by-hand'])
        self.assertEqual(self.commons.load_index()['entries'], {})
        self.assertFalse((self.commons.root / 'lessons' / 'by-hand.md').exists())


class ImportTests(Base):
    def test_import_real_playbook_twice(self):
        team = self.make_team('ta', TEAM_A, init=False)
        rc, out = quiet(cm.cmd_commons, str(team), ['import', str(PROTO / 'playbook')])
        self.assertEqual(rc, 0, out)
        idx = self.commons.load_index()['entries']
        lessons = [e for e in idx if e.startswith('playbook-lesson-')]
        self.assertGreaterEqual(len(lessons), 1, idx)
        self.assertIn('playbook', idx[lessons[0]]['tags'])
        rc, out = quiet(cm.cmd_commons, str(team), ['import', str(PROTO / 'playbook')])
        self.assertIn('新加 0、換新 0', out)

    def test_import_replaces_changed(self):
        pb = self.root / 'pb'
        (pb / 'teams').mkdir(parents=True)
        (pb / 'lessons.md').write_text('# x\n\n## 條目\n\n### 1（研發部）first lesson\n\nbody one\n', encoding='utf-8')
        (pb / 'teams' / 'crew.md').write_text('# Crew roster\n\nthree workers\n', encoding='utf-8')
        (pb / 'teams' / 'README.md').write_text('# index\n', encoding='utf-8')
        added, replaced, same = cm.import_dir(self.commons, pb)
        self.assertEqual(sorted(added), ['playbook-lesson-1', 'playbook-team-crew'])
        (pb / 'lessons.md').write_text('# x\n\n## 條目\n\n### 1（研發部）first lesson\n\nbody two\n', encoding='utf-8')
        added, replaced, same = cm.import_dir(self.commons, pb)
        self.assertEqual((added, replaced, same), ([], ['playbook-lesson-1'], ['playbook-team-crew']))
        text = (self.commons.root / 'lessons' / 'playbook-lesson-1.md').read_text(encoding='utf-8')
        self.assertIn('body two', text)


if __name__ == '__main__':
    unittest.main()
