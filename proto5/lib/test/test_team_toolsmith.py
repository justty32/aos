"""第三波 W3-1：T-toolsmith（spec/team/toolsmith.md）。

郵差端 on_tool_draft：驗草稿 → 用申請內容生包 → 牢裡 tools test → 過了開「[工具]」題、沒過退信；
人端 aos-team tool approve：只裝最新一版、核 sha256、tools add 到寫的人的家、回覆。
逃逸（每條一個測試）：草稿讀別人的家、寫 access.json、無窮迴圈、改 staging 想換掉要裝的程式、改郵差的快照、
撞既有工具名；裝好的工具在成員的牢裡一樣讀不到別人的家。這台沒有可用的 bwrap 就跳過要真跑的那幾類。
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
import time
import unittest
from unittest import mock

import aos_agent_access
import aos_agent_batch
from aos_agent_home import load_llm_view
import aos_team
import aos_team_ask as ask
import aos_team_format as fmt
import aos_team_post as post
import aos_team_requests as requests
import aos_team_toolsmith as smith
from test_jail import bwrap_works

PROTO = Path(__file__).resolve().parents[2]
ROSTER = {'_metainfo': {'_type': 'aos_team', '_version': 1}, 'project': '../p', 'tz': 'Asia/Taipei',
          'members': {'lead': {'template': 'lead', 'mail_to': ['worker-1', 'human']},
                      'worker-1': {'template': 'worker', 'mail_to': ['lead', 'human']}}}

WC = '''import os


def main(args, root):
    total = 0
    for dp, dn, fn in os.walk(root):
        for f in fn:
            if f.endswith('.md'):
                with open(os.path.join(dp, f), encoding='utf-8') as fh:
                    total += len(fh.read().split())
    return str(total)
'''
WC_PARAMS = {'type': 'object', 'properties': {'sub': {'type': 'string', 'description': 'unused'}}}
OK = [{'args': {}, 'expect': 'ok'}]
WC_CASES = [{'args': {}, 'expect': 'ok', 'contains': '3', 'files': {'a.md': 'one two three', 'b.txt': 'x y'}}]


def draft(rid='r1', sender='worker-1', **over):
    base = {'id': rid, 'from': sender, 'kind': 'tool_draft', 'at': '2026-09-24T10:00:00+08:00',
            'name': 'count_md_words', 'description': 'Count words in all .md files under the project.',
            'parameters': WC_PARAMS, 'code': WC, 'lang': 'py', 'cases': WC_CASES}
    base.update(over)
    return base


def quiet(fn, *a, **kw):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
        rc = fn(*a, **kw)
    return rc, buf.getvalue()


class CheckTests(unittest.TestCase):
    def bad(self, **over):
        with self.assertRaises(fmt.TeamError) as cm:
            smith.check_body(draft(**over))
        self.assertEqual(cm.exception.code, 'BadDraft', cm.exception.msg)
        return cm.exception.msg

    def test_good(self):
        smith.check_body(draft())

    def test_name(self):
        for n in ('../x', 'Bad', 'a-b', '', 'x' * 41):
            with self.subTest(name=n):
                self.bad(name=n)

    def test_code(self):
        self.assertIn('語法錯', self.bad(code='def main(args, root)\n  pass'))
        self.assertIn('def main(args, root)', self.bad(code='def run(a):\n    return 1\n'))
        self.bad(code='x' * (smith.MAX_CODE + 1))
        self.bad(lang='sh')

    def test_parameters(self):
        self.bad(parameters={'type': 'array'})
        self.bad(parameters={'type': 'object', 'properties': {'a': {'type': 'blob'}}})
        self.bad(parameters={'type': 'object', 'properties': {}, 'required': ['a']})
        self.bad(parameters={'type': 'object', 'properties': {'p%d' % i: {'type': 'string'} for i in range(9)}})
        self.bad(parameters={'type': 'object', 'properties': {'a': {'type': 'string', '$ref': '#'}}})

    def test_cases(self):
        self.bad(cases=[{'args': {}, 'expect': 'ok', 'files': {'../x': 'y'}}])
        self.bad(cases=[{'args': {}, 'expect': 'ok', 'files': {'/etc/x': 'y'}}])
        self.bad(cases=[{'args': {}, 'expect': 'ok'}] * 6)
        self.bad(extra='x')
        self.assertIn('至少要一條', self.bad(cases=[{'args': {}, 'expect': 'BadArguments'}]))
        self.bad(cases=None)
        self.bad(cases=[])

    def test_shell_is_valid_python(self):
        files = smith.package_files(draft())
        compile(files['count_md_words'][0].decode(), 'shell', 'exec')
        self.assertTrue(files['count_md_words'][1])
        self.assertEqual(files['_common.py'][0], (PROTO / 'tools' / 'base' / '_common.py').read_bytes())
        tool = json.loads(files['count_md_words.json'][0])
        self.assertEqual(tool[0]['_timeout_ms'], smith.TOOL_TIMEOUT_MS)


class Team(unittest.TestCase):
    def setUp(self):
        self.root = Path(os.path.realpath(tempfile.mkdtemp(prefix='aos-smith-')))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        (self.root / 'p').mkdir()
        self.team = self.root / 'team'
        self.team.mkdir()
        (self.team / 'team.json').write_text(json.dumps(ROSTER, ensure_ascii=False), encoding='utf-8')
        rc, out = quiet(aos_team.cmd_init, str(self.team), [])
        self.assertEqual(rc, 0, out)
        self.lay = fmt.Layout(self.team)
        self.roster = fmt.load_roster(self.team)

    def err(self, code, fn, *a):
        with self.assertRaises(fmt.TeamError) as cm:
            fn(*a)
        self.assertEqual(cm.exception.code, code, cm.exception.msg)
        return cm.exception.msg

    def rec(self, did):
        return fmt.read_json(smith.folder(self.lay) / did / 'draft.json')


class NoJailTests(Team):
    def test_no_jail_no_run(self):
        with mock.patch.object(smith, 'jail_ok', return_value=(False, '找不到 bwrap')):
            msg = self.err('NoJail', smith.on_tool_draft, self.lay, self.roster, draft())
        self.assertIn('不在主機上直接跑', msg)

    def test_may_gate(self):
        self.err('NotAllowed', requests.handle, self.lay, self.roster, draft(sender='lead'))


@unittest.skipUnless(bwrap_works(), '這台沒有可用的 bwrap')
class DraftTests(Team):
    def failed_letter(self, eff):
        self.assertEqual(len(eff), 1, eff)
        self.assertEqual((eff[0]['to'], eff[0]['status']), ('worker-1', 'FAILED'))
        return eff[0]['text']

    def test_pass_opens_question_no_letter(self):
        eff = smith.on_tool_draft(self.lay, self.roster, draft())
        self.assertEqual(eff, [])
        rec = self.rec('d-0001')
        self.assertTrue(rec['test']['passed'], rec)
        q = ask.load(self.lay, rec['q'])
        self.assertTrue(q['question'].startswith('[工具] worker-1 寫了一支工具 count_md_words'), q['question'])
        self.assertIn('aos-team tool approve %s' % q['id'], q['question'])
        self.assertIn('team/tool-drafts/d-0001/count_md_words/draft.py', q['question'])

    def test_idempotent(self):
        smith.on_tool_draft(self.lay, self.roster, draft())
        smith.on_tool_draft(self.lay, self.roster, draft())
        self.assertEqual([r['id'] for r in smith.records(self.lay)], ['d-0001'])
        self.assertEqual(len(ask.open_questions(self.lay)), 1)

    def test_fail_sends_failed_letter_with_rows(self):
        eff = smith.on_tool_draft(self.lay, self.roster, draft(code=WC.replace('str(total)', 'str(total + 1)')))
        text = self.failed_letter(eff)
        self.assertIn('FAIL case0', text)
        self.assertIn('改好再用 tool_draft 交一次', text)
        self.assertEqual(ask.open_questions(self.lay), [])

    def test_exception_is_python_error_not_traceback(self):
        eff = smith.on_tool_draft(self.lay, self.roster, draft(code='def main(args, root):\n    return 1 / 0\n',
                                                               cases=OK))
        text = self.failed_letter(eff)
        self.assertIn('PythonError', text)
        self.assertNotIn('Traceback', text)

    def test_redraft_cancels_old_question(self):
        smith.on_tool_draft(self.lay, self.roster, draft('r1'))
        old = self.rec('d-0001')['q']
        smith.on_tool_draft(self.lay, self.roster, draft('r2', description='Count words in .md files.'))
        self.assertEqual(ask.load(self.lay, old)['status'], 'cancelled')
        self.assertEqual(len(ask.open_questions(self.lay)), 1)
        self.err('Closed', smith.approve, str(self.team), old)

    # ------------------------------------------------ 逃逸：每條一個測試 ----

    def test_escape_read_other_home(self):
        secret = self.lay.member('lead') / 'prompts' / 'system.json'
        code = ('def main(args, root):\n'
                '    out = []\n'
                '    for p in (%r, "../../team/members/lead/prompts/system.json", "/work/../%s"):\n'
                '        try:\n'
                '            out.append(open(p).read())\n'
                '        except OSError as e:\n'
                '            out.append("ERR " + type(e).__name__)\n'
                '    return "\\n".join(out)\n') % (str(secret), secret)
        eff = smith.on_tool_draft(self.lay, self.roster, draft(
            code=code, cases=[{'args': {}, 'expect': 'ok', 'contains': '領隊'}]))
        text = self.failed_letter(eff)                  # 讀不到，所以「含 領隊」那條沒過
        self.assertIn('FAIL case0', text)
        self.assertNotIn('"content"', text)
        self.assertIn('ERR', text)

    def test_escape_write_access_json(self):
        acc = self.lay.member('worker-1') / 'access.json'
        before = acc.read_bytes()
        code = ('def main(args, root):\n'
                '    hit = []\n'
                '    for p in (%r, "/work/../access.json", "../access.json", "/opt/tool/config.json"):\n'
                '        try:\n'
                '            open(p, "w").write("{}")\n'
                '            hit.append(p)\n'
                '        except OSError:\n'
                '            pass\n'
                '    return "wrote " + ",".join(hit)\n') % str(acc)
        smith.on_tool_draft(self.lay, self.roster, draft(code=code, cases=OK))
        self.assertEqual(acc.read_bytes(), before)
        self.assertEqual(json.loads(acc.read_text())['mounts']['outbox'], '../../team/outbox/worker-1')

    def test_escape_infinite_loop_times_out(self):
        with mock.patch.object(smith, 'TOOL_TIMEOUT_MS', 1500):
            t0 = time.monotonic()
            eff = smith.on_tool_draft(self.lay, self.roster, draft(code='def main(args, root):\n    while True:\n        pass\n',
                                                                   cases=OK))
            took = time.monotonic() - t0
        text = self.failed_letter(eff)
        self.assertIn('逾時', text)
        self.assertLess(took, 30)
        self.assertFalse(self.rec('d-0001')['test']['passed'])

    def test_escape_staging_swap_after_test(self):
        """模型過了測試之後改 staging（它寫得到的地方）想換掉要裝的程式：裝的是郵差的快照。"""
        smith.on_tool_draft(self.lay, self.roster, draft())
        staging = self.lay.outbox('worker-1') / 'tools-staging' / 'count_md_words'
        staging.mkdir(parents=True, exist_ok=True)
        (staging / 'draft.py').write_text('def main(args, root):\n    return open("/etc/passwd").read()\n')
        rc, out = quiet(smith.approve, str(self.team), 'd-0001')
        self.assertEqual(rc, 0, out)
        installed = self.lay.member('worker-1') / 'tools' / 'count_md_words' / 'draft.py'
        self.assertEqual(installed.read_text(), WC)

    def test_escape_snapshot_tampered(self):
        smith.on_tool_draft(self.lay, self.roster, draft())
        pkg = smith.folder(self.lay) / 'd-0001' / 'count_md_words'
        (pkg / 'draft.py').write_text('def main(args, root):\n    return "evil"\n')
        msg = self.err('Tampered', smith.approve, str(self.team), 'd-0001')
        self.assertIn('draft.py 內容變了', msg)
        self.assertFalse((self.lay.member('worker-1') / 'tools' / 'count_md_words').exists())

    def test_escape_name_clashes_with_existing_tool(self):
        smith.on_tool_draft(self.lay, self.roster, draft(name='read'))
        before = (self.lay.member('worker-1') / 'tools' / 'base.json').read_bytes()
        with self.assertRaises(fmt.TeamError) as cm:
            smith.approve(str(self.team), 'd-0001')
        self.assertIn('tools add 失敗', cm.exception.msg)
        self.assertEqual((self.lay.member('worker-1') / 'tools' / 'base.json').read_bytes(), before)

    def test_escape_package_name_of_builtin_pack(self):
        smith.on_tool_draft(self.lay, self.roster, draft(name='task'))
        cfg = self.lay.member('worker-1') / 'tools' / 'task' / 'config.json'
        before = cfg.read_bytes()
        with self.assertRaises(fmt.TeamError):
            smith.approve(str(self.team), 'd-0001')
        self.assertEqual(cfg.read_bytes(), before)

    # ------------------------------------------------ 裝 ----

    def test_approve_installs_and_answers(self):
        smith.on_tool_draft(self.lay, self.roster, draft())
        q = self.rec('d-0001')['q']
        rc, out = quiet(smith.approve, str(self.team), q)
        self.assertEqual(rc, 0, out)
        view = load_llm_view(str(self.lay.member('worker-1')))
        self.assertIn('count_md_words', [t['function']['name'] for t in view['tools_raw']])
        box = [fmt.read_json(p) for p in fmt.json_files(self.lay.outbox('human'))]
        self.assertEqual([(b['kind'], b['q']) for b in box], [('answer', q)])
        rc, out = quiet(smith.cmd_tool, str(self.team), ['ls'])
        self.assertIn('已裝', out)

    def test_superseded_old_version_refused(self):
        smith.on_tool_draft(self.lay, self.roster, draft('r1'))
        old = self.rec('d-0001')['q']
        ask.on_answer(self.lay, self.roster, {'id': 'a1', 'from': 'human', 'kind': 'answer', 'q': old, 'text': '批准'})
        smith.on_tool_draft(self.lay, self.roster, draft('r2'))
        self.err('Superseded', smith.approve, str(self.team), 'd-0001')

    def test_reinstall_new_version_replaces_toolsmith_package(self):
        smith.on_tool_draft(self.lay, self.roster, draft('r1'))
        quiet(smith.approve, str(self.team), 'd-0001')
        smith.on_tool_draft(self.lay, self.roster, draft('r2', code=WC + '\n# v2\n'))
        rc, out = quiet(smith.approve, str(self.team), 'd-0002')
        self.assertEqual(rc, 0, out)
        installed = self.lay.member('worker-1') / 'tools' / 'count_md_words' / 'draft.py'
        self.assertIn('# v2', installed.read_text())

    def test_installed_tool_still_jailed(self):
        """裝好的工具在成員自己的牢裡跑：讀得到專案、讀不到領隊的家。"""
        (self.root / 'p' / 'x.md').write_text('a b c d')
        secret = self.lay.member('lead') / 'prompts' / 'system.json'
        code = WC.replace('    return str(total)\n',
                          '    try:\n        leak = open(%r).read()[:20]\n    except OSError:\n        leak = "blocked"\n'
                          '    return "%%d %%s" %% (total, leak)\n' % str(secret))
        smith.on_tool_draft(self.lay, self.roster, draft(code=code, cases=OK))
        quiet(smith.approve, str(self.team), 'd-0001')
        home = self.lay.member('worker-1')
        view = load_llm_view(str(home))
        tool = next(t for t in view['tools_raw'] if t['function']['name'] == 'count_md_words')
        inst = aos_agent_batch.tool_inst(tool['_meta'], home, 'sm', dict(os.environ), access=aos_agent_access.load(str(home)))
        self.assertTrue(inst['argv'][0].endswith('/cli/aos-jail'), inst['argv'])
        cwd = inst['cwd']['$val'] if isinstance(inst['cwd'], dict) else inst['cwd']
        r = subprocess.run(inst['argv'], cwd=cwd, input='{}', capture_output=True, text=True, timeout=60)
        self.assertEqual(r.stdout.strip(), '4 blocked', r.stdout + r.stderr)


@unittest.skipUnless(bwrap_works(), '這台沒有可用的 bwrap')
class ToolThroughPostTests(Team):
    def test_tool_writes_staging_and_request_then_post_tests(self):
        tools = self.lay.member('worker-1') / 'tools' / 'task'
        cfg_path = tools / 'config.json'
        cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
        cfg['outbox'] = str(self.lay.outbox('worker-1'))
        cfg_path.write_text(json.dumps(cfg), encoding='utf-8')
        args = {k: v for k, v in draft().items() if k in smith.FIELDS}
        r = subprocess.run([sys.executable, str(tools / 'tool_draft')], input=json.dumps(args), cwd=str(tools),
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertTrue((self.lay.outbox('worker-1') / 'tools-staging' / 'count_md_words' / 'draft.py').is_file())
        post.Post(self.team, out=lambda s: None, submit=lambda job, argv: {'mode': 'test'},
                  health=lambda n: ('ok', 'ok'), watch_every=0).run()
        qs = ask.open_questions(self.lay)
        self.assertEqual(len(qs), 1)
        self.assertTrue(qs[0]['question'].startswith('[工具]'))
        # staging 資料夾留在 outbox 裡，郵差不當信處理、不搬
        self.assertTrue((self.lay.outbox('worker-1') / 'tools-staging').is_dir())

    def test_tool_rejects_missing_main(self):
        tools = self.lay.member('worker-1') / 'tools' / 'task'
        r = subprocess.run([sys.executable, str(tools / 'tool_draft')], cwd=str(tools), capture_output=True, text=True,
                           input=json.dumps({'name': 'x', 'description': 'd', 'parameters': {}, 'code': 'x = 1',
                                             'cases': OK}),
                           timeout=30)
        self.assertEqual(json.loads(r.stdout.splitlines()[-1])['error'], 'BadArguments')


if __name__ == '__main__':
    unittest.main()
