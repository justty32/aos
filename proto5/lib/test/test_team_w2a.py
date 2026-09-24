"""第二波 A 隊（w2a）團隊這邊的小改：route try、mail 列題目與落穿信、start／stop 那兩行標郵差／心跳。"""
import contextlib
import io
import json
from pathlib import Path
import shutil
import unittest
from unittest import mock

import aos_team
import aos_team_ask as ask
import aos_team_format as fmt
import aos_team_mail as mail
import aos_team_route as route
from _team_util import EXAMPLES, TeamCase


class RouteTryTests(TeamCase):
    def setUp(self):
        super().setUp()
        shutil.copy(EXAMPLES / 'routes.json', self.lay.routes)

    def try_(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = route.cmd_route(str(self.team), ['try', *argv])
        return code, out.getvalue()

    def assert_nothing_done(self):
        self.assertFalse(self.lay.route_log.exists())
        self.assertEqual(fmt.json_files(self.lay.outbox('human')), [])
        for name in self.roster['members']:
            self.assertEqual(list((self.lay.member(name) / 'input').glob('*.json')), [])

    def test_tool_rule(self):
        code, out = self.try_('列任務')
        self.assertEqual(code, 0)
        self.assertIn('命中 tasks → 門房直接跑：aos-team task ls（不叫任何 agent）', out)
        self.assertIn('（只是試，什麼都沒做）', out)
        self.assert_nothing_done()

    def test_run_rule_shows_filled_groups(self):
        code, out = self.try_('每', '2m', '數一次', 'md', '檔')       # 多個字用空白接起來，跟 ask 一樣
        self.assertIn('抓到：every=2m', out)
        self.assertIn('aos-team routine add count-md --every 2m', out)
        self.assert_nothing_done()

    def test_handoff_rule(self):
        code, out = self.try_('把 workflows 導入 p，照 facts.json')
        self.assertIn('命中 import → 開單給 worker-1（領隊不經手）', out)
        self.assertIn('事實 facts.json', out)
        self.assert_nothing_done()

    def test_fall_through_and_negation(self):
        self.assertIn('沒有規則命中 → 交給領隊 lead', self.try_('幫我想想週末要幹嘛')[1])
        self.assertIn('含否定詞「不要」 → 交給領隊 lead', self.try_('不要看單子')[1])
        self.assert_nothing_done()

    def test_other_file_and_errors(self):
        other = self.tmp / 'r.json'
        other.write_text(json.dumps({'routes': []}), encoding='utf-8')
        self.assertIn('規則檔：%s（0 條）' % other, self.try_('列任務', '--file', str(other))[1])
        with self.assertRaises(fmt.TeamError) as cm:
            self.try_('列任務', '--file', str(self.tmp / 'nope.json'))
        self.assertEqual(cm.exception.code, 'NotFound')
        with self.assertRaises(fmt.TeamError) as cm:
            self.try_()
        self.assertEqual(cm.exception.code, 'Usage')

    def test_warns_when_examples_fail(self):
        obj = json.loads(self.lay.routes.read_text(encoding='utf-8'))
        obj['routes'][0]['tests']['hit'].append('這句不會中')
        self.lay.routes.write_text(json.dumps(obj, ensure_ascii=False), encoding='utf-8')
        self.assertIn('例句沒全過（tasks）', self.try_('列任務')[1])

    def test_test_and_save_still_work(self):
        r = self.cli('route', 'test')
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.cli('route', 'save', 'a', 'b')
        self.assertEqual(r.returncode, 2)


class MailTests(TeamCase):
    def ask_q(self, sender='worker-1', question='要不要保留範例？', reply_to=None, answer=None):
        rid = self.request(sender, 'ask', question=question, reply_to=reply_to)
        req = json.loads((self.lay.outbox(sender) / (rid + '.json')).read_text(encoding='utf-8'))
        ask.on_ask(self.lay, self.rost, req)
        q = [x for x in ask.all_questions(self.lay) if x['request'] == rid][0]
        if answer is not None:
            ask.on_answer(self.lay, self.rost, {'id': 'a-%s' % q['id'], 'from': 'human', 'kind': 'answer',
                                                'q': q['id'], 'text': answer, 'at': self.now.isoformat()})
        return q['id']

    def test_questions_listed_with_answer_first(self):
        self.letter('lead', 'worker-1', 'REQUEST', '第一封')
        self.post()
        q1 = self.ask_q()
        q2 = self.ask_q(sender='lead', question='要改哪一段？', answer='開頭那段')
        r = self.cli('mail')
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.strip().split('\n')
        self.assertTrue(any('worker-1 → 人  ASK  %s  等你回答（aos-team answer %s "…"）  問：要不要保留範例？'
                            % (q1, q1) in ln for ln in lines), r.stdout)
        self.assertTrue(any('lead → 人  ASK  %s  已答「開頭那段」  問：要改哪一段？' % q2 in ln for ln in lines),
                        r.stdout)
        r = self.cli('mail', '--json', '--to', 'human')
        objs = [json.loads(ln) for ln in r.stdout.strip().split('\n')]
        self.assertEqual({o['id']: o.get('state') for o in objs if o['kind'] == 'ask'}, {q1: 'open', q2: 'answered'})

    def test_only_questions(self):
        self.ask_q()
        r = self.cli('mail')
        self.assertIn('ASK', r.stdout)
        self.assertNotIn('還沒有信', r.stdout)

    def test_task_filter_includes_fallthrough_letter_and_questions(self):
        self.letter('human', 'lead', 'REQUEST', '早一點的另一件事')
        self.post()
        self.handoff(goal='先前那張')                                 # t-0001：領隊開的，在第一封之後
        self.post()
        self.now = self.now.replace(second=(self.now.second + 5) % 60)
        self.letter('human', 'lead', 'REQUEST', '把 WORKFLOWS.md 開頭改白話')
        self.post()
        self.handoff(goal='改白話')                                   # t-0002
        self.post()
        q = self.ask_q(reply_to='t-0002')
        r = self.cli('mail', '--task', 't-0002')
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.strip().split('\n')
        self.assertIn('人 → lead  REQUEST', lines[0])
        self.assertIn('把 WORKFLOWS.md 開頭改白話', lines[0])
        self.assertNotIn('早一點的另一件事', r.stdout)
        self.assertTrue(any('post → worker-1  REQUEST  t-0002' in ln for ln in lines), r.stdout)
        self.assertTrue(any('ASK  %s  [t-0002]' % q in ln for ln in lines), r.stdout)
        self.assertNotIn('t-0001', r.stdout)

    def test_human_opened_task_has_no_fallthrough(self):
        self.letter('human', 'lead', 'REQUEST', '跟單子無關')
        self.post()
        self.handoff(sender='human')
        self.post()
        r = self.cli('mail', '--task', 't-0001')
        self.assertNotIn('跟單子無關', r.stdout)
        self.assertIn('t-0001', r.stdout)
        self.assertIsNone(mail.fallthrough_letter(self.lay, 't-9999', []))


class StartLabelTests(TeamCase):
    def test_hook_lines_are_labelled(self):
        def fake(name):
            def fn(team):
                print('started team-%s-x' % name)
                return 0
            return fn
        out = io.StringIO()
        with mock.patch('aos_team_post.start', fake('post')), mock.patch('aos_team_beat.start', fake('beat')), \
                contextlib.redirect_stdout(out):
            code = aos_team._hooks('start', self.lay)
        self.assertEqual(code, 0)
        self.assertEqual(out.getvalue(), '郵差: started team-post-x\n心跳: started team-beat-x\n')

    def test_failed_hook_still_ends_line(self):
        out = io.StringIO()
        with mock.patch('aos_team_post.start', lambda team: 1), mock.patch('aos_team_beat.start', lambda team: 0), \
                contextlib.redirect_stdout(out):
            code = aos_team._hooks('start', self.lay)
        self.assertEqual(code, 1)
        self.assertEqual(out.getvalue(), '郵差: \n心跳: ')


class ImporterTemplateTests(unittest.TestCase):
    """E 工具表瘦身：導入工人模板只裝導入用得到的工具，送給模型的工具表比 worker 少一半以上。"""

    def test_importer_tools_and_size(self):
        import os
        import subprocess
        import sys
        import tempfile
        import aos_agent_context
        import aos_agent_info
        root = Path(tempfile.mkdtemp(prefix='aos-w2a-importer-'))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        (root / 'p').mkdir()
        roster = json.loads((EXAMPLES / 'team.json').read_text(encoding='utf-8'))
        roster['members']['importer-1'] = {'template': 'importer', 'mail_to': ['lead', 'human']}
        roster['members']['lead']['mail_to'].append('importer-1')
        src = root / 'roster.json'
        src.write_text(json.dumps(roster, ensure_ascii=False), encoding='utf-8')
        cli = Path(__file__).resolve().parents[2] / 'cli' / 'aos-team'
        r = subprocess.run([sys.executable, str(cli), 'init', '--config', str(src), '--target', str(root / 'team')],
                           capture_output=True, text=True, timeout=120,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        lay = fmt.Layout(root / 'team')
        sizes = {}
        for name in ('worker-1', 'importer-1'):
            m = aos_agent_context.measure(aos_agent_info.load(str(lay.member(name))))
            sizes[name] = m['tools']
        self.assertEqual(sorted(sizes['importer-1']['names']),
                         sorted(['read', 'edit', 'ls', 'wf_doc', 'wf_init', 'wf_fill', 'wf_residue', 'wf_lint',
                                 'ask_human', 'team_say']))
        self.assertIn('wf_fill', sizes['worker-1']['names'])          # 一般工人也拿得到 wf_fill
        self.assertLess(sizes['importer-1']['tokens'], sizes['worker-1']['tokens'] * 0.55)
        access = json.loads((lay.member('importer-1') / 'access.json').read_text(encoding='utf-8'))
        self.assertEqual(set(access['mounts']), {'ws', 'outbox', 'board'})   # 沒 notes：模板沒開


if __name__ == '__main__':
    unittest.main()
