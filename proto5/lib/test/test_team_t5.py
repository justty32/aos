"""收尾隊（T5）的小改動：審查單帶事實、aos-team ls 列郵差與心跳、模板人格的變數與關鍵句。"""
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

import aos_kernel_store
import aos_team
import aos_team_post
import aos_team_task as task

PROTO = Path(__file__).resolve().parents[2]


class ReviewLetterTests(unittest.TestCase):
    def parent(self, facts):
        return {'id': 't-0001', 'goal': '把 WORKFLOWS.md 開頭改白話，意思不能變', 'facts': facts}

    def sub(self):
        return {'id': 't-0001.r1', 'review_of': {'rev': 1, 'attempt': 1},
                'done_when': [{'kind': 'judge', 'text': '原意沒變'}]}

    def test_facts_shown_to_reviewer(self):
        text = task.render_review(self.sub(), self.parent('原文：使用者要做事 → 從派發表選工作流'))
        self.assertIn('事實（開單人給的，例如改之前的原文）：原文：使用者要做事', text)
        self.assertIn('0. 原意沒變', text)

    def test_no_facts_no_line(self):
        self.assertNotIn('事實', task.render_review(self.sub(), self.parent(None)))


class MachineLinesTests(unittest.TestCase):
    def setUp(self):
        self.team = Path(tempfile.mkdtemp(prefix='aos-team-t5-'))
        self.addCleanup(shutil.rmtree, self.team, ignore_errors=True)

    def lines(self, procs, env=None):
        env = {'AOS_KERNEL_HOME': '/k'} if env is None else env
        with mock.patch.object(aos_kernel_store, 'procs', return_value=procs):
            return aos_team.machine_lines(str(self.team), env)

    def test_ok_bad_missing(self):
        post = aos_team_post.proc_name(str(self.team), 'post')
        out = self.lines({post: {'status': 'bad', 'fails': 10}})
        self.assertEqual(len(out), 2)
        self.assertTrue(out[0].startswith('郵差  %s  壞了（連錯 10 次）' % post), out[0])
        self.assertIn('post.err', out[0])
        self.assertIn('沒登記', out[1])
        out = self.lines({post: {'status': 'queued'}})
        self.assertTrue(out[0].endswith('  ok'))

    def test_no_kernel_env(self):
        self.assertEqual(self.lines({}, env={}), ['郵差、心跳：沒設 AOS_KERNEL_HOME，看不到'])

    def test_ledger_unreadable_does_not_raise(self):
        with mock.patch.object(aos_kernel_store, 'procs', side_effect=OSError('x')):
            out = aos_team.machine_lines(str(self.team), {'AOS_KERNEL_HOME': '/k'})
        self.assertIn('帳本讀不到', out[0])


class RouteRunGuardTests(unittest.TestCase):
    """astra M1：門房 run 的第一格不能用群組；群組的值不能變成選項。"""

    def routes(self, run, pattern):
        return {'routes': [{'name': 'x', 'pattern': pattern, 'do': 'tool', 'run': run,
                            'tests': {'hit': ['執行 ls'], 'miss': ['別的']}}]}

    def test_group_in_subcommand_rejected(self):
        import aos_team_format as fmt
        with self.assertRaises(fmt.TeamError) as cm:
            fmt.validate_routes(self.routes(['{cmd}'], '執行 (?P<cmd>\\w+)'), 'routes.json')
        self.assertIn('第一格', str(cm.exception))

    def test_group_value_as_option_rejected(self):
        import json
        import aos_team_format as fmt
        import aos_team_route as route
        team = Path(tempfile.mkdtemp(prefix='aos-team-t5r-'))
        self.addCleanup(shutil.rmtree, team, ignore_errors=True)
        (team / 'p').mkdir()
        t = team / 'team'
        t.mkdir()
        (t / 'team.json').write_text(json.dumps({'project': '../p', 'members': {
            'lead': {'template': 'lead', 'mail_to': ['human']}}}), encoding='utf-8')
        lay = fmt.Layout(t)
        lay.routes.parent.mkdir(parents=True, exist_ok=True)
        lay.routes.write_text(json.dumps({'routes': [{'name': 'x', 'pattern': '看 (?P<w>\\S+)', 'do': 'tool',
                                                      'run': ['task', 'show', '{w}'],
                                                      'tests': {'hit': ['看 t-0001'], 'miss': ['別的']}}]}),
                              encoding='utf-8')
        with self.assertRaises(fmt.TeamError) as cm:
            route.ask(str(t), '看 --all')
        self.assertEqual(cm.exception.code, 'BadRoute')


class NotesLandingTests(unittest.TestCase):
    """astra M3：內建 notes 掛點途中有符號連結（例如指到任務表）就拒絕。"""

    def test_symlink_rejected(self):
        import aos_agent_init
        from aos_agent_home import AgentError
        team = Path(tempfile.mkdtemp(prefix='aos-team-t5n-'))
        self.addCleanup(shutil.rmtree, team, ignore_errors=True)
        (team / 'team' / 'tasks').mkdir(parents=True)
        (team / 'team' / 'notes').mkdir()
        os.symlink('../tasks', team / 'team' / 'notes' / 'worker-1')
        member = {'team_dir': str(team), 'name': 'worker-1'}
        with self.assertRaises(AgentError) as cm:
            aos_agent_init._check_notes_dir(member)
        self.assertEqual(cm.exception.code, 'AccessUnsafe')
        os.unlink(team / 'team' / 'notes' / 'worker-1')
        aos_agent_init._check_notes_dir(member)          # 不在：可以（init 會建）
        (team / 'team' / 'notes' / 'worker-1').mkdir()
        aos_agent_init._check_notes_dir(member)          # 普通資料夾：可以


class PersonaTests(unittest.TestCase):
    """人格定稿：只用 init 認得的三個變數，關鍵句在（改人格時這裡提醒要重跑真跑）。"""

    def read(self, name):
        return (PROTO / 'templates' / name / 'system.md').read_text(encoding='utf-8')

    def test_only_known_vars(self):
        import re
        for name in ('lead', 'worker', 'reviewer', 'coder'):
            for var in re.findall(r'\{(\w+)\}', self.read(name)):
                self.assertIn(var, ('name', 'mail_to', 'members'), name)

    def test_key_sentences(self):
        worker = self.read('worker')
        for s in ('wf_doc', 'ask_human', '一次叫好幾個', 'team_say 寄 DONE', '不要等回信'):
            self.assertIn(s, worker)
        lead = self.read('lead')
        for s in ('handoff', '「無」', 'judge', 'facts', '不要等'):
            self.assertIn(s, lead)
        self.assertIn('review_result', self.read('reviewer'))


if __name__ == '__main__':
    unittest.main()
