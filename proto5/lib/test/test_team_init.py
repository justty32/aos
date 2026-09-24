"""第 1 隊：aos-team init／start／stop／ls／rm、模板生家（init_from_template）、task 工具包（handoff／board／review_result／ask_human）。"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import unittest.mock

import aos_agent_access
import aos_agent_init
import aos_agent_say
from aos_agent_home import AgentError
import aos_team_format as fmt
import aos_team_requests as requests
import aos_team_task as task
from _daemon_util import wait_for
from _kernel_util import CLI, PY, KernelCase, read_json

PROTO = Path(__file__).resolve().parents[2]
TOOLS = PROTO / 'tools' / 'task'
ROSTER = json.loads((PROTO / 'spec/team/examples/team.json').read_text(encoding='utf-8'))


def team_cli(*args, env=None, cwd=None):
    e = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    e.update(env or {})
    return subprocess.run([PY, str(CLI / 'aos-team'), *map(str, args)], capture_output=True, text=True,
                          timeout=60, env=e, cwd=cwd, stdin=subprocess.DEVNULL)


class InitTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='aos-team-init-'))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        (self.root / 'p').mkdir()
        self.team = self.root / 'team'
        self.src = self.root / 'roster.json'
        self.src.write_text(json.dumps(ROSTER, ensure_ascii=False), encoding='utf-8')

    def init(self, *extra, code=0):
        r = team_cli('init', *extra, '--target', self.team)
        self.assertEqual(r.returncode, code, r.stdout + r.stderr)
        return r

    def test_init_three_members(self):
        r = self.init('--config', self.src)
        self.assertIn('3 個成員', r.stdout)
        lay = fmt.Layout(self.team)
        for name, tpl in (('lead', 'lead'), ('worker-1', 'worker'), ('reviewer', 'reviewer')):
            home = lay.member(name)
            self.assertEqual(read_json(home / 'state.json'), {'input': 'input/'})
            self.assertTrue((home / 'input').is_dir())
            access = read_json(home / 'access.json')
            self.assertEqual(set(access['mounts']), {'ws', 'outbox', 'board'} | ({'notes', 'mem'} if tpl != 'reviewer' else set()))
            self.assertEqual(access['cwd'], 'ws')
            self.assertFalse(access['net'])
            table = aos_agent_access.load(str(home))              # 解得開、沒蓋到信任資料
            self.assertEqual(table['mounts']['outbox']['path'], str(lay.outbox(name)))
            self.assertFalse(table['mounts']['outbox']['ro'])
            self.assertTrue(table['mounts']['board']['ro'])
            self.assertEqual(table['mounts']['ws']['ro'], tpl != 'worker')
            cfg = read_json(home / 'tools/task/config.json')
            self.assertEqual((cfg['member'], cfg['outbox'], cfg['board']), (name, '/work/outbox', '/work/board'))
            self.assertIn(name, read_json(home / 'prompts/system.json')['content'])
            self.assertTrue(read_json(home / '.aos-template.json')['complete'])
            self.assertTrue(lay.outbox(name).is_dir())
        lead = read_json(lay.member('lead') / 'info.json')
        names = [e['$opt']['only'] if isinstance(e, dict) else e for e in lead['tools']]
        self.assertEqual(names, [['handoff', 'board', 'ask_human', 'compact_me', 'routine_propose'], ['team_say'],
                                 'tools/notes.json', ['read', 'grep', 'find', 'ls']])   # team 包（第 2 隊）已在
        self.assertTrue(lay.outbox('human').is_dir())
        self.assertEqual(read_json(self.team / 'team.json'), ROSTER)

    def test_rerun_adds_new_member_only(self):
        self.init('--config', self.src)
        lay = fmt.Layout(self.team)
        before = (lay.member('lead') / 'prompts/system.json').stat().st_mtime_ns
        roster = read_json(self.team / 'team.json')
        roster['members']['worker-2'] = {'template': 'worker', 'mail_to': ['lead', 'human']}
        roster['members']['lead']['mail_to'].append('worker-2')
        (self.team / 'team.json').write_text(json.dumps(roster), encoding='utf-8')
        r = self.init()
        self.assertIn('worker-2: 生了', r.stdout)
        self.assertIn('lead: 已在，更新工具設定', r.stdout)
        self.assertEqual((lay.member('lead') / 'prompts/system.json').stat().st_mtime_ns, before)
        self.assertIn('worker-2', read_json(lay.member('lead') / 'tools/task/config.json')['mail_to'])
        # --config 給不一樣的內容＝拒絕
        r = self.init('--config', self.src, code=1)
        self.assertIn('AlreadyExists', r.stderr)

    def test_crash_half_way_then_rerun_completes(self):
        self.init('--config', self.src)
        home = fmt.Layout(self.team).member('reviewer')
        info = read_json(home / 'info.json')
        info['tools'] = info['tools'][:1]
        (home / 'info.json').write_text(json.dumps(info), encoding='utf-8')
        (home / 'tools/base.json').unlink()
        (home / '.aos-template.json').write_text(json.dumps({'template': 'reviewer', 'member': 'reviewer',
                                                             'complete': False}))
        r = self.init()
        self.assertIn('reviewer: 已在，補完上次沒生完的', r.stdout)
        self.assertIn('reviewer: 裝了 base', r.stdout)
        self.assertTrue(read_json(home / '.aos-template.json')['complete'])
        self.assertEqual(len(read_json(home / 'info.json')['tools']), 2)

    def test_errors(self):
        r = self.init(code=1)
        self.assertIn('--config', r.stderr)
        (self.root / 'p').rmdir()
        r = self.init('--config', self.src, code=1)
        self.assertIn('專案資料夾', r.stderr)
        # 團隊放在專案裡面
        (self.root / 'p').mkdir()
        inner = self.root / 'p' / 'team'
        roster = dict(ROSTER, project='..')
        self.src.write_text(json.dumps(roster), encoding='utf-8')
        r = team_cli('init', '--config', self.src, '--target', inner)
        self.assertEqual(r.returncode, 1)
        self.assertIn('BadProject', r.stderr)
        # 模板打錯
        roster = json.loads(json.dumps(ROSTER))
        roster['members']['lead']['template'] = 'boss'
        self.src.write_text(json.dumps(roster), encoding='utf-8')
        r = team_cli('init', '--config', self.src, '--target', self.root / 't2')
        self.assertEqual(r.returncode, 1)
        self.assertIn('NoSuchTemplate', r.stderr)

    def test_template_standalone(self):
        home = self.root / 'solo'
        lines = aos_agent_init.init_from_template(home, 'coder')
        self.assertIn('生了', lines[0])
        self.assertEqual(read_json(home / 'access.json')['mounts'], {'ws': 'workspace'})
        with self.assertRaises(AgentError) as cm:
            aos_agent_init.init_from_template(self.root / 'x', 'worker')
        self.assertEqual(cm.exception.code, 'Usage')
        with self.assertRaises(AgentError) as cm:
            aos_agent_init.init_from_template(home, 'coder')
        self.assertEqual(cm.exception.code, 'AlreadyExists')
        (self.root / 'full').mkdir()
        (self.root / 'full' / 'a').write_text('x')
        with self.assertRaises(AgentError) as cm:
            aos_agent_init.init_from_template(self.root / 'full', 'coder')
        self.assertEqual(cm.exception.code, 'NotEmpty')

    def test_rm_moves_home_and_fixes_roster(self):
        self.init('--config', self.src)
        r = team_cli('rm', 'reviewer', '--target', self.team, env={'AOS_KERNEL_HOME': ''})
        self.assertEqual(r.returncode, 0, r.stderr)
        roster = read_json(self.team / 'team.json')
        self.assertNotIn('reviewer', roster['members'])
        self.assertNotIn('reviewer', roster['members']['lead']['mail_to'])
        self.assertFalse((self.team / 'members/reviewer').exists())
        self.assertEqual(len(list((self.team / 'members/.removed').iterdir())), 1)
        r = team_cli('rm', 'nobody', '--target', self.team)
        self.assertEqual(r.returncode, 1)

    def test_rm_purge_deletes_home(self):
        self.init('--config', self.src)
        r = team_cli('rm', 'worker-1', '--purge', '--target', self.team, env={'AOS_KERNEL_HOME': ''})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('已刪除（--purge）', r.stdout)
        self.assertFalse((self.team / 'members/worker-1').exists())
        removed = self.team / 'members/.removed'
        self.assertEqual(list(removed.iterdir()) if removed.exists() else [], [])    # 沒留在已拆資料夾
        self.assertNotIn('worker-1', read_json(self.team / 'team.json')['members'])
        self.assertEqual(list((self.team / 'members').glob('.removing-*')), [])

    def test_ls_without_kernel(self):
        self.init('--config', self.src)
        r = team_cli('ls', '--json', '--target', self.team, env={'AOS_KERNEL_HOME': ''})
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = json.loads(r.stdout)
        self.assertEqual([x['name'] for x in rows], ['lead', 'worker-1', 'reviewer'])
        self.assertTrue(all(x['health'] == 'unregistered' for x in rows), rows)


class ToolUnitTests(unittest.TestCase):
    """工具包不關牢直接跑：config.json 指到主機路徑。"""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='aos-task-tools-'))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.pack = self.root / 'task'
        shutil.copytree(TOOLS, self.pack, ignore=shutil.ignore_patterns('__pycache__'))
        self.outbox, self.board = self.root / 'outbox', self.root / 'board'
        self.outbox.mkdir()
        self.board.mkdir()
        self.config(member='lead')

    def config(self, **over):
        cfg = {'member': 'lead', 'mail_to': ['worker-1', 'reviewer', 'human'],
               'members': ['lead', 'worker-1', 'reviewer'], 'outbox': str(self.outbox), 'board': str(self.board),
               'tz': 'Asia/Taipei'}
        cfg.update(over)
        (self.pack / 'config.json').write_text(json.dumps(cfg))

    def tool(self, name, args, code=0):
        r = subprocess.run([str(self.pack / name)], input=json.dumps(args), capture_output=True, text=True,
                           timeout=20, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        self.assertEqual(r.returncode, code, r.stdout + r.stderr)
        if code:
            return json.loads(r.stdout.strip().splitlines()[-1])
        return r.stdout

    def sent(self):
        files = fmt.json_files(self.outbox)
        return [json.loads(p.read_text()) for p in files]

    def test_handoff_writes_valid_request(self):
        out = self.tool('handoff', {'assignee': 'worker-1', 'workflow': 'IMPORT.md', 'goal': '導入',
                                    'done_when': [{'kind': 'check', 'name': 'wf_residue'}], 'max_attempts': 2})
        self.assertIn('queued handoff', out)
        self.assertIn('end this turn', out)
        [req] = self.sent()
        fmt.validate_request(req)
        self.assertEqual((req['from'], req['kind'], req['assignee']), ('lead', 'handoff', 'worker-1'))
        path = fmt.json_files(self.outbox)[0]
        self.assertEqual(path.stem, req['id'])
        self.assertTrue(req['id'].endswith('-lead'))
        self.assertEqual([p.name for p in self.outbox.iterdir()], [path.name])   # 沒有暫存殘檔

    def test_handoff_auto_adds_wf_lint_strict_for_wording_rewrite(self):
        """G（09-24 W2C）：「改寫 X.md 更白話」這類單，忘記放 wf_lint_strict 就機械補上。"""
        out = self.tool('handoff', {'assignee': 'worker-1', 'workflow': 'IMPORT.md',
                                    'goal': '把 p 的 WORKFLOWS.md 開頭那段說明改寫得更白話，意思不能變',
                                    'done_when': [{'kind': 'judge', 'text': '原意沒變'}]})
        self.assertIn('auto-added to done_when', out)
        self.assertEqual(self.sent()[0]['done_when'], [{'kind': 'judge', 'text': '原意沒變'},
                                                        {'kind': 'check', 'name': 'wf_lint_strict'}])
        # 已經放了就不重複加
        out = self.tool('handoff', {'assignee': 'worker-1', 'workflow': 'IMPORT.md',
                                    'goal': '把 WORKFLOWS.md 改寫更白話',
                                    'done_when': [{'kind': 'check', 'name': 'wf_lint_strict'}]})
        self.assertNotIn('auto-added', out)
        self.assertEqual(self.sent()[1]['done_when'], [{'kind': 'check', 'name': 'wf_lint_strict'}])
        # 不像改寫、或不是 .md：不補
        out = self.tool('handoff', {'assignee': 'worker-1', 'workflow': 'IMPORT.md', 'goal': '導入 heartbeat 包',
                                    'done_when': [{'kind': 'file_exists', 'path': 'x'}]})
        self.assertNotIn('auto-added', out)
        self.assertEqual(self.sent()[2]['done_when'], [{'kind': 'file_exists', 'path': 'x'}])
        # astra 審查 S1 修：facts 提到 .md 不算數（那多半是背景參考，不是要改的檔）
        out = self.tool('handoff', {'assignee': 'worker-1', 'workflow': 'IMPORT.md', 'goal': '改寫 app.py',
                                    'facts': '參考 README.md', 'done_when': [{'kind': 'file_exists', 'path': 'x'}]})
        self.assertNotIn('auto-added', out)
        # astra 審查 S1 修：goal 有否定詞就不補
        out = self.tool('handoff', {'assignee': 'worker-1', 'workflow': 'IMPORT.md',
                                    'goal': '不要把 README.md 改成更白話', 'done_when': [{'kind': 'judge', 'text': 'x'}]})
        self.assertNotIn('auto-added', out)

    def test_handoff_refuses(self):
        e = self.tool('handoff', {'assignee': 'ghost', 'workflow': 'w', 'goal': 'g',
                                  'done_when': [{'kind': 'check', 'name': 'x'}]}, code=1)
        self.assertEqual(e['error'], 'BadArguments')
        self.assertIn('worker-1', e['message'])
        e = self.tool('handoff', {'assignee': 'worker-1', 'workflow': 'w', 'goal': 'g',
                                  'done_when': [{'kind': 'shell', 'cmd': 'ls'}]}, code=1)
        self.assertIn('done_when[0].kind', e['message'])
        e = self.tool('handoff', {'assignee': 'lead', 'workflow': 'w', 'goal': 'g', 'done_when': []}, code=1)
        self.assertIn('yourself', e['message'])
        e = self.tool('handoff', {'assignee': 'worker-1', 'goal': 'g', 'done_when': [], 'extra': 1}, code=1)
        self.assertIn('unknown argument', e['message'])
        self.assertEqual(self.sent(), [])
        (self.pack / 'config.json').unlink()
        e = self.tool('board', {}, code=1)
        self.assertEqual(e['error'], 'ConfigInvalid')

    def test_board_and_review_result(self):
        lay_root = self.root / 'teamdir'
        lay = fmt.Layout(lay_root)
        lay.tasks.mkdir(parents=True)
        (lay_root / 'team.json').write_text(json.dumps(dict(ROSTER, project='.')))
        roster = fmt.load_roster(lay_root)
        req = json.loads((PROTO / 'spec/team/examples/request-handoff.json').read_text(encoding='utf-8'))
        requests.handle(lay, roster, req)
        task.step(lay, 't-0001', {'type': 'delivered', 'src': 'd', 'rev': 1, 'attempt': 1})
        task.step(lay, 't-0001', {'type': 'report', 'src': 'r', 'by': 'worker-1', 'rev': 1, 'status': 'DONE'})
        task.step(lay, 't-0001', {'type': 'verified', 'src': 'v', 'pass': True, 'rev': 1, 'attempt': 1})
        task.open_review(lay, roster, 't-0001', 'o', 1, 1)
        self.config(board=str(lay.tasks), member='reviewer')
        out = self.tool('board', {})
        self.assertIn('t-0001 reviewing worker-1 rev1 try1/3', out)
        self.assertIn('t-0001.r1 queued reviewer', out)
        out = self.tool('board', {'op': 'show', 'task': 't-0001'})
        self.assertIn('done_when:', out)
        self.assertIn('last check (rev1 try1): pass', out)
        # 審查子單保留父單原編號（09-24 W2C 修）：judge 條目在 request-handoff.json 的 done_when 排第 3（0 起算）
        out = self.tool('board', {'op': 'show', 'task': 't-0001.r1'})
        self.assertIn('  3. kind=judge', out)
        e = self.tool('review_result', {'task': 't-0001.r1', 'items': []}, code=1)
        self.assertIn('answer every item', e['message'])
        e = self.tool('review_result', {'task': 't-0001', 'items': []}, code=1)
        self.assertIn('not a review task', e['message'])
        e = self.tool('review_result', {'task': 't-0001.r1', 'items': [{'i': 0, 'pass': True, 'why': '一樣'}]}, code=1)
        self.assertIn('BadArguments', e['error'])
        out = self.tool('review_result', {'task': 't-0001.r1', 'items': [{'i': 3, 'pass': True, 'why': '一樣'}]})
        self.assertIn('PASS', out)
        [req] = self.sent()
        effects = requests.handle(lay, roster, req)
        task.step(lay, effects[0]['task'], effects[0]['event'])
        self.assertEqual(task.load(lay, 't-0001')['status'], 'done')
        self.config(board=str(lay.tasks), member='worker-1')
        e = self.tool('review_result', {'task': 't-0001.r1', 'items': [{'i': 3, 'pass': True, 'why': 'x'}]}, code=1)
        self.assertIn('assigned to reviewer', e['message'])
        e = self.tool('board', {'op': 'show', 'task': 't-0009'}, code=1)
        self.assertEqual(e['error'], 'NotFound')
        self.assertIn('No open tasks', self.tool('board', {}))

    def test_ask_human(self):
        self.config(member='worker-1')
        out = self.tool('ask_human', {'question': '用 main 嗎？', 'options': ['main', '分支'], 'default': 'main',
                                      'reply_to': 't-0001'})
        self.assertIn('Do not wait', out)
        [req] = self.sent()
        fmt.validate_request(req)
        e = self.tool('ask_human', {'question': 'x', 'options': ['a'], 'default': 'b'}, code=1)
        self.assertIn('default', e['message'])

    def test_lock(self):
        self.config(member='worker-1')
        out = self.tool('lock', {'op': 'acquire', 'name': 'shared-file', 'why': '改共用檔', 'ttl_seconds': 300})
        self.assertIn('End this turn', out)
        [req] = self.sent()
        self.assertEqual((req['kind'], req['op'], req['name'], req['ttl_seconds']), ('lock', 'acquire', 'shared-file', 300))
        e = self.tool('lock', {'op': 'bogus'}, code=1)
        self.assertIn('op must be', e['message'])
        e = self.tool('lock', {'op': 'acquire'}, code=1)
        self.assertEqual(e['error'], 'BadArguments')

    def test_access_request(self):
        self.config(member='worker-1')
        out = self.tool('access_request', {'name': 'notes2', 'path_hint': '/home/x/notes2', 'mode': 'ro',
                                           'why': '要查另一份筆記'})
        self.assertIn('End this turn', out)
        [req] = self.sent()
        fmt.validate_request(req)
        self.assertEqual(req['kind'], 'ask')
        self.assertIn('notes2', req['question'])
        self.assertIn('access set', req['question'])
        self.assertEqual(req['options'], ['同意', '不同意'])
        e = self.tool('access_request', {'name': 'x', 'path_hint': 'y', 'mode': 'rwx', 'why': 'z'}, code=1)
        self.assertIn('mode', e['message'])

    def test_access_request_rejects_bad_mount_name(self):
        """astra 審查 M3：name 沒驗過就塞進建議指令；現在照 aos_agent_access.NAME 的規則擋（含殼層夾帶字元、保留字）。"""
        self.config(member='worker-1')
        for bad in ('$(id)', 'Has-Upper', 'has space', 'outbox', 'notes'):
            e = self.tool('access_request', {'name': bad, 'path_hint': 'y', 'mode': 'ro', 'why': 'z'}, code=1)
            self.assertEqual(e['error'], 'BadArguments', bad)
        self.assertEqual(self.sent(), [])
        out = self.tool('access_request', {'name': 'shared-notes', 'path_hint': 'y', 'mode': 'ro', 'why': 'z'})
        self.assertIn('End this turn', out)
        self.assertIn("access set shared-notes", self.sent()[0]['question'])

    def test_persona_propose(self):
        self.config(member='worker-1')
        out = self.tool('persona_propose', {'text': '遇到殘留一律先跑 wf_residue', 'why': '省一次來回'})
        self.assertIn('End this turn', out)
        [req] = self.sent()
        fmt.validate_request(req)
        self.assertEqual(req['kind'], 'ask')
        self.assertIn('殘留', req['question'])
        self.assertIn('persona append', req['question'])

    def test_persona_propose_shell_quotes_the_suggested_command(self):
        """astra 審查：text 裡的 $(…) 以前原樣塞進雙引號，人照抄就會被殼層當替換算；現在要單引號起來。"""
        self.config(member='worker-1')
        out = self.tool('persona_propose', {'text': 'Please preserve literal $(id)'})
        self.assertIn('End this turn', out)
        [req] = self.sent()
        self.assertIn("persona append --target <worker-1 的家> 'Please preserve literal $(id)'", req['question'])

    def test_routine_propose(self):
        self.config(member='lead')
        out = self.tool('routine_propose', {'name': 'count-md', 'every': '2m', 'to': 'worker-1', 'goal': '數 md 檔',
                                            'done_when': [{'kind': 'file_exists', 'path': 'x'}]})
        self.assertIn('End this turn', out)
        [req] = self.sent()
        self.assertEqual((req['kind'], req['op'], req['name'], req['every'], req['to']),
                         ('routine', 'add', 'count-md', '2m', 'worker-1'))
        e = self.tool('routine_propose', {'name': 'x', 'to': 'worker-1', 'goal': 'g', 'done_when': []}, code=1)
        self.assertIn('exactly one of', e['message'])
        out = self.tool('routine_propose', {'op': 'rm', 'name': 'count-md'})
        self.assertIn('End this turn', out)

    def test_descriptions_are_short(self):
        tools = json.loads((TOOLS / 'task.json').read_text(encoding='utf-8'))
        sizes = {t['function']['name']: len(json.dumps(t['function'], ensure_ascii=False)) for t in tools}
        self.assertEqual(set(sizes), {'handoff', 'board', 'review_result', 'ask_human', 'compact_me',
                                      'lock', 'access_request', 'persona_propose', 'routine_propose'})
        # 09-24 W2C 加 4 支申請類工具：整包（9 支全裝）比第一波大，但沒有哪個成員一次全裝——
        # lead／worker 的 template.json 各自只 only 挑幾支（見 templates/*/template.json）。
        self.assertLess(sum(sizes.values()), 5500, sizes)            # 約 1370 token；單支都 < 300 token 起跳
        self.assertTrue(all(v < 1200 for v in sizes.values()), sizes)


# ---------------------------------------------------------- 真 kernel＋牢 ----

def _call(name, args, cid):
    return {'role': 'assistant', 'content': None, 'tool_calls': [
        {'id': cid, 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args, ensure_ascii=False)}}]}


# 每個成員的假模型劇本：看自己（人格裡的名字）與已收到幾則 tool 結果決定下一步。
SCRIPTS = {
    '領隊 lead': [('board', {}), ('handoff', {'assignee': 'worker-1', 'workflow': 'IMPORT.md', 'goal': '寫 hello.txt',
                                            'done_when': [{'kind': 'file_exists', 'path': 'hello.txt'},
                                                          {'kind': 'judge', 'text': '內容是問候'}]})],
    '工人 worker-1': [('write', {'path': 'hello.txt', 'content': 'hi'}), ('board', {'op': 'show', 'task': 't-0001'}),
                    ('ask_human', {'question': '要不要加驚嘆號？', 'reply_to': 't-0001'})],
    # judge 在這張單 done_when 排第 1（0 起算，file_exists 是第 0）：子單保留父單原編號（09-24 W2C 修）
    '審查員 reviewer': [('review_result', {'task': 't-0001.r1', 'items': [{'i': 1, 'pass': True, 'why': '是問候'}]})],
}


class TeamIntegrationTests(KernelCase):
    """真 daemon＋kernel＋bwrap：三個成員從模板生、check 全過、start／ls／stop；工具在牢裡寫得到 outbox、看得到任務表。"""

    def setUp(self):
        super().setUp()
        self.requests = []
        records = self.requests

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                records.append(body)
                system = body['messages'][0]['content']
                script = next(v for k, v in SCRIPTS.items() if k in system)
                step = sum(1 for m in body['messages'] if m['role'] == 'tool')
                last_user = max(i for i, m in enumerate(body['messages']) if m['role'] == 'user')
                done_now = sum(1 for m in body['messages'][last_user:] if m['role'] == 'tool')
                if step < len(script) and (done_now or body['messages'][-1]['role'] == 'user'):
                    name, args = script[step]
                    message = _call(name, args, 'c%d' % step)
                else:
                    message = {'role': 'assistant', 'content': '好'}
                raw = json.dumps({'choices': [{'message': message}]}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .01})
        self.thread.start()
        self.addCleanup(self.close_server)
        config = self.root / 'llm.json'
        self.write(config, {'_metainfo': {'_type': 'llm_config', '_version': 1}, 'models': {
            'default': {'endpoint': 'http://127.0.0.1:%d/v1' % self.server.server_port,
                        'model': 'local-test', 'timeout_ms': 3000}}})
        path = str(CLI) + os.pathsep + os.environ.get('PATH', '/usr/bin:/bin')
        self.env = {'AOS_KERNEL_HOME': str(self.home), 'PATH': path}
        patcher = unittest.mock.patch.dict(os.environ, {'PATH': path})   # daemon 也要找得到 aos-* 指令
        patcher.start()
        self.addCleanup(patcher.stop)
        # 池式（proto5-2 納入）：info 是池表；default 兩顆、llm 一顆，kernel 池不用寫。
        self.pools = {'default': {'count': 2, 'envs': {'PATH': path}},
                      'llm': {'count': 1, 'envs': {'PATH': path, 'AOS_LLM_CONFIG': str(config)}}}
        self.addCleanup(self.orderly_stop)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def orderly_stop(self):
        if self.daemon_process is not None and self.daemon_process.poll() is None:
            if self.state().get('phase') != 'stopped':
                self.kernel_stop()
            self.daemon_stop()

    def team(self, *args, code=0):
        r = team_cli(*args, '--target', self.teamdir, env=self.env)
        self.assertEqual(r.returncode, code, r.stdout + r.stderr)
        return r

    def post_once(self, roster):
        """假郵差走一次：outbox → 處理；信投進收件人 input。回處理了幾份。"""
        lay, n = self.lay, 0
        for name in list(roster['members']) + ['human']:
            for path in fmt.json_files(lay.outbox(name)):
                kind, obj = fmt.read_outbox_file(path, roster)
                effects = requests.handle(lay, roster, obj) if kind == 'request' else []
                self.effects(roster, effects, obj['id'])
                os.rename(path, lay.outbox(name) / 'done' / path.name)
                n += 1
        return n

    def effects(self, roster, effects, src):
        for k, e in enumerate(effects):
            if e['do'] == 'letter':
                ltr = {'id': '%s.e%d' % (src, k), 'from': e.get('from', 'post'), 'to': e['to'],
                       'status': e['status'], 'reply_to': e['reply_to'], 'rev': e['rev'], 'text': e['text'],
                       'at': fmt.now_iso()}
                if ltr['to'] != 'human':
                    aos_agent_say.drop_new(self.lay.member(ltr['to']) / 'input', fmt.mail_filename(ltr['id']),
                                           fmt.mail_message(ltr, roster['tz']))
                    self.effects(roster, task.letter_delivered(self.lay, ltr, e.get('dispatch')), ltr['id'])
            elif e['do'] == 'step':
                self.effects(roster, task.step(self.lay, e['task'], e['event']), src)
            elif e['do'] == 'open_review':
                self.effects(roster, task.open_review(self.lay, roster, e['task'], '%s.e%d' % (src, k),
                                                      e['rev'], e['attempt']), src)

    def history(self, name):
        return read_json(self.lay.member(name) / 'prompts/history.json', [])

    def tool_results(self, name):
        return [m['content'] for m in self.history(name) if m['role'] == 'tool']

    def test_team_in_jail_end_to_end(self):
        if shutil.which('bwrap') is None:
            self.skipTest('沒有 bwrap')
        self.setup_running(pools=self.pools)
        (self.root / 'p').mkdir()
        self.teamdir = self.root / 'team'
        src = self.root / 'roster.json'
        roster_obj = dict(ROSTER)
        src.write_text(json.dumps(roster_obj, ensure_ascii=False), encoding='utf-8')
        self.team('init', '--config', src)
        self.lay = fmt.Layout(self.teamdir)
        roster = fmt.load_roster(self.teamdir)
        for name in roster['members']:
            info = read_json(self.lay.member(name) / 'info.json')
            info['tick']['interval_ms'] = 5
            self.write(self.lay.member(name) / 'info.json', info)
            r = subprocess.run([PY, str(CLI / 'aos-agent'), 'check', '--target', str(self.lay.member(name))],
                               env=dict(os.environ, **self.env), capture_output=True, text=True, timeout=30)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertNotIn('bad', r.stdout)
        self.team('start')
        rows = json.loads(self.team('ls', '--json').stdout)
        self.assertTrue(all(x['health'] == 'ok' for x in rows), rows)
        # start 也登記了真郵差、心跳（第 2 隊）；這條測試用自己的假郵差一步一步走，先把真的撤掉免得搶信
        import contextlib
        import aos_team_beat
        import aos_team_post
        with open(os.devnull, 'w') as null, contextlib.redirect_stdout(null):
            aos_team_post.stop(self.teamdir, env=dict(os.environ, **self.env))
            aos_team_beat.stop(self.teamdir, env=dict(os.environ, **self.env))

        # 人（假門房落穿）→ 領隊：board、handoff（牢裡寫 /work/outbox）
        letter = {'id': fmt.new_id('human'), 'from': 'human', 'to': 'lead', 'status': 'REQUEST', 'reply_to': None,
                  'rev': None, 'text': '寫一個 hello.txt', 'at': fmt.now_iso()}
        fmt.write_new(self.lay.outbox('human') / (letter['id'] + '.json'), letter)
        wait_for(lambda: self.post_once(roster) or True)
        aos_agent_say.drop_new(self.lay.member('lead') / 'input', fmt.mail_filename(letter['id']),
                               fmt.mail_message(letter, roster['tz']))
        wait_for(lambda: len(self.tool_results('lead')) >= 2, timeout=40)
        results = self.tool_results('lead')
        self.assertIn('No open tasks', results[0])
        self.assertIn('queued handoff', results[1])
        self.assertEqual(self.post_once(roster), 1)                 # 郵差開單＋派給工人
        t = task.load(self.lay, 't-0001')
        self.assertEqual((t['status'], t['opened_by']), ('sent', 'lead'))

        # 工人：write（牢裡可寫專案）、board show、ask_human
        wait_for(lambda: len(self.tool_results('worker-1')) >= 3, timeout=40)
        results = self.tool_results('worker-1')
        self.assertIn('created hello.txt', results[0])
        self.assertEqual((self.root / 'p' / 'hello.txt').read_text(), 'hi')
        self.assertIn('t-0001 sent worker-1', results[1])
        self.assertIn('queued question', results[2])
        self.assertEqual(self.post_once(roster), 1)
        self.assertEqual(task.load(self.lay, 't-0001')['status'], 'waiting_user')
        r = self.team('wait', 'ls')
        self.assertIn('q-0001  worker-1 問：要不要加驚嘆號？', r.stdout)

        # 模擬工人回 DONE（team_say 是第 2 隊的）→ 驗收（假）過 → 審查員在牢裡 review_result
        done = {'id': fmt.new_id('worker-1'), 'from': 'worker-1', 'to': 'lead', 'status': 'DONE', 'reply_to': 't-0001',
                'rev': 1, 'text': '好了', 'at': fmt.now_iso()}
        self.effects(roster, task.on_letter(self.lay, roster, done), done['id'])
        self.effects(roster, task.step(self.lay, 't-0001', {'type': 'verified', 'src': 'v1', 'pass': True, 'rev': 1,
                                                            'attempt': 1}), 'v1')
        self.assertEqual(task.load(self.lay, 't-0001')['status'], 'reviewing')
        wait_for(lambda: len(self.tool_results('reviewer')) >= 1, timeout=40)
        self.assertIn('queued review_result', self.tool_results('reviewer')[0])
        self.assertEqual(self.post_once(roster), 1)
        self.assertEqual(task.load(self.lay, 't-0001')['status'], 'done')
        r = self.team('task', 'show', 't-0001')
        self.assertIn('done', r.stdout)

        # 牢：領隊的專案是唯讀、看不到別人的 outbox
        tools = {}
        for body in self.requests:
            who = next(k for k in SCRIPTS if k in body['messages'][0]['content'])
            tools[who] = {t['function']['name'] for t in body['tools']}
        self.assertEqual(tools['領隊 lead'], {'handoff', 'board', 'ask_human', 'compact_me', 'routine_propose',
                                             'team_say', 'note', 'recall', 'context', 'read', 'grep', 'find', 'ls'})
        self.assertEqual(tools['審查員 reviewer'], {'board', 'review_result', 'read', 'grep', 'find', 'ls'})
        self.assertTrue({'write', 'bash', 'board', 'ask_human', 'compact_me', 'team_say', 'note', 'recall', 'context'} <= tools['工人 worker-1'])
        self.assertNotIn('handoff', tools['工人 worker-1'])
        self.team('stop')
        wait_for(lambda: all(x['health'] == 'unregistered' for x in json.loads(self.team('ls', '--json').stdout)),
                 timeout=15)


if __name__ == '__main__':
    unittest.main()
