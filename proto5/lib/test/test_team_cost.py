"""財務部（spec/team/cost.md）：記帳、查帳、預算擋郵差、回填。本機假端點，不打真模型。"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

import aos_llm_ask
import aos_team_cost as cost
import aos_team_format as fmt
from _team_util import TeamCase, CLI_TEAM

PRICES = {'families': {'claude': ['claude-'], 'gpt': ['chatgpt-', 'gpt-'], 'deepseek': ['deepseek-'],
                       'local': ['lm-', 'ollama-']},
          'models': {'deepseek-chat': {'in': 1.0, 'out': 2.0}, 'claude-opus-5*': {'in': 5.0, 'out': 25.0},
                     'lm-*': {'in': 0, 'out': 0}}}


def ledger(base):
    rows, bad = cost.read_ledger(str(base))
    assert bad == 0
    return rows


class CostHome(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='aos-cost-'))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.base = self.tmp / 'cost'
        self.base.mkdir()
        (self.base / 'prices.json').write_text(json.dumps(PRICES), encoding='utf-8')
        self.env = {'AOS_COST_HOME': str(self.base)}

    def put(self, **kw):
        kw.setdefault('source', 'think')
        cost.append(str(self.base), [cost.make_row(prices=cost.load_prices(str(self.base)), **kw)])


class RecordTest(CostHome):
    def test_off_without_env(self):
        self.assertFalse(cost.record({}, model='deepseek-chat', usage={'prompt_tokens': 1}))
        self.assertFalse((self.base / 'ledger.jsonl').exists())

    def test_one_row(self):
        self.assertTrue(cost.record(self.env, model='deepseek-chat', alias='cheap', ms=12, source='think',
                                    usage={'prompt_tokens': 1000, 'completion_tokens': 500}))
        [r] = ledger(self.base)
        self.assertEqual((r['model'], r['family'], r['prompt_tokens'], r['completion_tokens']),
                         ('deepseek-chat', 'deepseek', 1000, 500))
        self.assertAlmostEqual(r['usd'], 0.002)
        self.assertEqual(r['source'], 'think')
        self.assertFalse(r['usage_missing'])

    def test_agent_dir_gives_team_member_task(self):
        team = self.tmp / 'team'
        home = team / 'members' / 'worker-1'
        home.mkdir(parents=True)
        (team / 'team.json').write_text('{}', encoding='utf-8')
        (team / 'team' / 'tasks').mkdir(parents=True)
        for tid, st, up in (('t-0001', 'done', '2'), ('t-0002', 'working', '1'), ('t-0003', 'sent', '3')):
            (team / 'team' / 'tasks' / (tid + '.json')).write_text(json.dumps(
                {'id': tid, 'assignee': 'worker-1', 'status': st, 'updated_at': up}), encoding='utf-8')
        cost.record(self.env, model='deepseek-chat', usage={'prompt_tokens': 1, 'completion_tokens': 1},
                    agent_dir=str(home))
        [r] = ledger(self.base)
        self.assertEqual((r['team'], r['member'], r['task']), (os.path.realpath(team), 'worker-1', 't-0003'))

    def test_env_tags(self):
        env = dict(self.env, AOS_COST_TEAM='eval', AOS_COST_MEMBER='judge', AOS_COST_TASK='case-3',
                   AOS_COST_SOURCE='eval-judge')
        cost.record(env, model='claude-opus-5-high', usage=None)
        [r] = ledger(self.base)
        self.assertEqual((r['team'], r['member'], r['task'], r['source'], r['family']),
                         ('eval', 'judge', 'case-3', 'eval-judge', 'claude'))
        self.assertTrue(r['usage_missing'])

    def test_write_failure_never_raises(self):
        (self.base / 'ledger.jsonl').mkdir()          # 帳本位置是資料夾：寫不進去
        self.assertFalse(cost.record(self.env, model='deepseek-chat', usage={'prompt_tokens': 1}))
        (self.base / 'prices.json').write_text('{壞', encoding='utf-8')
        os.rmdir(self.base / 'ledger.jsonl')
        self.assertTrue(cost.record(self.env, model='deepseek-chat', usage={'prompt_tokens': 1}))
        self.assertIsNone(ledger(self.base)[0]['usd'])     # 價格表壞了：照記 token，不算錢

    def test_ask_books_through_real_http(self):
        body = {'choices': [{'message': {'role': 'assistant', 'content': 'ok'}}],
                'usage': {'prompt_tokens': 30, 'completion_tokens': 7, 'total_tokens': 37}}

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                data = json.dumps(body).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass
        srv = ThreadingHTTPServer(('127.0.0.1', 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        cfg = self.tmp / 'llm.json'
        cfg.write_text(json.dumps({'_metainfo': {'_type': 'llm_config', '_version': 1}, 'models': {
            'default': {'endpoint': 'http://127.0.0.1:%d/v1' % srv.server_port, 'model': 'deepseek-chat'}}}),
            encoding='utf-8')
        got = aos_llm_ask.ask('s', 'u', env=dict(self.env, AOS_LLM_CONFIG=str(cfg), AOS_COST_SOURCE='crystal'))
        self.assertEqual(got['text'], 'ok')
        [r] = ledger(self.base)
        self.assertEqual((r['source'], r['prompt_tokens'], r['completion_tokens']), ('crystal', 30, 7))


class ReportTest(CostHome):
    def setUp(self):
        super().setUp()
        self.put(model='deepseek-chat', team='/t/a', member='lead', task='t-0001',
                 usage={'prompt_tokens': 1_000_000, 'completion_tokens': 0})
        self.put(model='deepseek-chat', team='/t/a', member='worker-1', task='t-0001',
                 usage={'prompt_tokens': 0, 'completion_tokens': 1_000_000})
        self.put(model='claude-opus-5-high', team='/t/b', member='lead', task='t-0009',
                 usage={'prompt_tokens': 100_000, 'completion_tokens': 10_000})
        self.put(model='chatgpt-gpt-6-astra', team='/t/b', member='lead', task=None,
                 usage={'prompt_tokens': 500, 'completion_tokens': 50})
        self.prices = cost.load_prices(str(self.base))
        self.rows = ledger(self.base)

    def group(self, by):
        groups, unpriced = cost.summarize(self.rows, by, self.prices)
        return {g['key']: g for g in groups}, unpriced

    def test_by_family(self):
        g, unpriced = self.group('family')
        self.assertEqual(set(g), {'deepseek', 'claude', 'gpt'})
        self.assertAlmostEqual(g['deepseek']['usd'], 3.0)
        self.assertAlmostEqual(g['claude']['usd'], 0.75)
        self.assertEqual(g['gpt']['unpriced_tokens'], 550)
        self.assertEqual(unpriced, {'chatgpt-gpt-6-astra': 550})      # 缺價：記 token 不記錢

    def test_by_member_team_model_task(self):
        g, _ = self.group('member')
        self.assertEqual(g['lead']['calls'], 3)
        self.assertEqual(g['worker-1']['tokens'], 1_000_000)
        g, _ = self.group('team')
        self.assertEqual(g['/t/a']['calls'], 2)
        g, _ = self.group('model')
        self.assertEqual(g['claude-opus-5-high']['prompt_tokens'], 100_000)
        g, _ = self.group('task')
        self.assertEqual(g['t-0001']['calls'], 2)
        self.assertEqual(g['-']['calls'], 1)

    def test_prices_edit_reprices_history(self):
        p = dict(PRICES, models=dict(PRICES['models'], **{'chatgpt-*': {'in': 0, 'out': 0}}))
        (self.base / 'prices.json').write_text(json.dumps(p), encoding='utf-8')
        groups, unpriced = cost.summarize(self.rows, 'family', cost.load_prices(str(self.base)))
        self.assertEqual(unpriced, {})

    def test_since(self):
        old = cost.make_row(model='deepseek-chat', usage={'prompt_tokens': 5}, source='x', at='2020-01-01T00:00:00+08:00')
        rows = cost.select(self.rows + [old], cost.since_time('今天'))
        self.assertEqual(len(rows), 4)
        self.assertEqual(len(cost.select(self.rows + [old], cost.since_time('全部'))), 5)
        with self.assertRaises(cost.CostError):
            cost.since_time('昨天吧')

    def test_cli_table_and_warning(self):
        e = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', AOS_COST_HOME=str(self.base))
        e.pop('AOS_KERNEL_HOME', None)
        p = subprocess.run([sys.executable, str(CLI_TEAM), 'cost', '--by', 'family', '--target', str(self.tmp)],
                           capture_output=True, text=True, env=e, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('deepseek', p.stdout)
        self.assertIn('警告：價格表', p.stdout)
        self.assertIn('chatgpt-gpt-6-astra', p.stdout)
        self.assertIn('cpu：沒設 AOS_KERNEL_HOME', p.stdout)
        p = subprocess.run([sys.executable, str(CLI_TEAM), 'cost', '--by', 'member', '--json', '--target', str(self.tmp)],
                           capture_output=True, text=True, env=e, timeout=30)
        data = json.loads(p.stdout)
        self.assertEqual({g['key'] for g in data['groups']}, {'lead', 'worker-1'})

    def test_cli_without_home(self):
        e = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        e.pop('AOS_COST_HOME', None)
        p = subprocess.run([sys.executable, str(CLI_TEAM), 'cost', '--target', str(self.tmp)],
                           capture_output=True, text=True, env=e, timeout=30)
        self.assertEqual(p.returncode, 1)
        self.assertIn('NotConfigured', p.stderr)


class BudgetShapeTest(unittest.TestCase):
    def test_ok(self):
        b = cost.check_budget({'claude': {'usd': 1.0}, 'gpt': {'tokens': 50_000_000}}, 'b')
        self.assertEqual(b['since'], 'week')
        b = cost.check_budget({'deepseek': {'usd': 5, 'since': '2026-09-25'}}, 'b')
        self.assertEqual(b['deepseek']['since'], '2026-09-25')

    def test_per_family_since(self):
        now = datetime.datetime(2026, 9, 25, 12, tzinfo=datetime.timezone(datetime.timedelta(hours=8)))
        rows = [cost.make_row(model='deepseek-chat', source='x', at='2026-09-24T10:00:00+08:00',
                              usage={'prompt_tokens': 100, 'completion_tokens': 0}),
                cost.make_row(model='deepseek-chat', source='x', at='2026-09-25T10:00:00+08:00',
                              usage={'prompt_tokens': 1, 'completion_tokens': 0})]
        prices = {'families': cost.DEFAULT_FAMILIES, 'models': {}}
        b = cost.check_budget({'since': 'week', 'all': {'tokens': 1000},
                               'deepseek': {'tokens': 1000, 'since': '2026-09-25'}}, 'b')
        got = {x['family']: x['used'] for x in cost.usage_against(b, rows, prices, 'company', now)}
        self.assertEqual(got, {'all': 101, 'deepseek': 1})

    def test_bad(self):
        for obj in ({'claude': 3}, {'claude': {'usd': -1}}, {'gpt': {'tokens': 1.5}}, {'gpt': {'money': 1}},
                    {'since': '上週'}, {'claude': {'usd': True}}, [], {'claude': {'since': 'day'}},
                    {'claude': {'usd': 1, 'since': 'x'}}):
            with self.assertRaises(ValueError, msg=obj):
                cost.check_budget(obj, 'b')


class PostBudgetTest(TeamCase):
    def setUp(self):
        super().setUp()
        self.base = self.tmp / 'cost'
        self.base.mkdir()
        (self.base / 'prices.json').write_text(json.dumps(PRICES), encoding='utf-8')
        self.env = dict(os.environ, AOS_COST_HOME=str(self.base))

    def spend(self, n, team=None):
        cost.append(str(self.base), [cost.make_row(model='deepseek-chat', source='think',
                                                   team=team or os.path.realpath(self.team), member='lead',
                                                   usage={'prompt_tokens': n, 'completion_tokens': 0})])

    def set_team_budget(self, budget):
        roster = json.loads((self.team / 'team.json').read_text(encoding='utf-8'))
        roster['budget'] = budget
        (self.team / 'team.json').write_text(json.dumps(roster, ensure_ascii=False), encoding='utf-8')

    def human(self):
        return sorted(self.lay.human_inbox.glob('*.json')) if self.lay.human_inbox.is_dir() else []

    def test_roster_budget_validated(self):
        self.set_team_budget({'deepseek': {'tokens': 'many'}})
        with self.assertRaises(fmt.TeamError) as cm:
            fmt.load_roster(self.team)
        self.assertIn('team.json.budget.deepseek.tokens', cm.exception.msg)

    def test_under_budget_dispatches(self):
        self.set_team_budget({'deepseek': {'tokens': 1000}})
        self.spend(10)
        self.handoff()
        self.post(env=self.env)
        self.assertEqual(len(self.inbox('worker-1')), 1)

    def test_over_team_budget_holds_new_task_and_mails_human_once(self):
        self.set_team_budget({'deepseek': {'tokens': 1000}})
        self.spend(5000)
        self.spend(10 ** 9, team='/別的團隊')             # 別隊的帳不算進本隊
        rid = self.handoff()
        self.post(env=self.env)
        self.assertEqual(self.inbox('worker-1'), [])
        self.assertTrue((self.lay.outbox('lead') / (rid + '.json')).exists())     # 留在 outbox
        [mail] = self.human()
        letter = json.loads(mail.read_text(encoding='utf-8'))
        self.assertEqual(letter['status'], 'NEEDS-USER')
        self.assertIn('超預算', letter['text'])
        self.handoff()
        self.post(env=self.env)
        self.assertEqual(len(self.human()), 1)                  # 同一天同一種超額只寄一封
        # 預算調高：下一輪兩張單都走
        self.set_team_budget({'deepseek': {'tokens': 10 ** 7}})
        self.post(env=self.env)
        self.assertEqual(len(self.inbox('worker-1')), 2)       # 兩張留著的單都派出去
        tickets = sorted(p.name for p in self.lay.tasks.glob('t-*.json'))
        self.assertEqual(len(tickets), 2)

    def test_company_budget_and_letters_still_flow(self):
        (self.base / 'budget.json').write_text(json.dumps({'since': 'day', 'all': {'usd': 0.001}}), encoding='utf-8')
        self.spend(10 ** 6, team='/別的團隊')             # 全公司帳：別隊花的也算
        self.handoff()
        self.letter('lead', 'worker-1', 'PROGRESS', text='普通的信照投')
        self.post(env=self.env)
        self.assertEqual(len(self.inbox('worker-1')), 1)       # 只有那封信
        self.assertEqual(list(self.lay.tasks.glob('t-*.json')), [])
        self.assertEqual(len(self.human()), 1)

    def test_no_cost_home_no_gate(self):
        self.set_team_budget({'deepseek': {'tokens': 0}})
        self.spend(5)
        env = dict(os.environ)
        env.pop('AOS_COST_HOME', None)
        self.handoff()
        self.post(env=env)
        self.assertEqual(len(self.inbox('worker-1')), 1)

    def test_ls_first_line(self):
        self.set_team_budget({'deepseek': {'tokens': 1}})
        self.spend(5)
        p = self.cli('ls', env={'AOS_COST_HOME': str(self.base)})
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(p.stdout.startswith('財務：超預算'), p.stdout)
        p = self.cli('cost', 'budget', env={'AOS_COST_HOME': str(self.base)})
        self.assertEqual(p.returncode, 1)
        self.assertIn('← 超了', p.stdout)


class ImportTest(CostHome):
    def test_import_once(self):
        log = self.tmp / 'runs' / 'r1' / 'members' / 'writer-1' / 'log'
        log.mkdir(parents=True)
        (log / 'usage.jsonl').write_text(
            json.dumps({'at': '2026-09-25T11:07:18.334+08:00', 'batch': 'aw-writer-1-1', 'alias': 'x',
                        'model': 'deepseek-chat', 'ms': 5, 'usage': {'prompt_tokens': 100, 'completion_tokens': 10}})
            + '\n壞行\n', encoding='utf-8')
        prices = cost.load_prices(str(self.base))
        new, skipped, files = cost.import_usage(str(self.base), [str(self.tmp / 'runs')], prices)
        self.assertEqual((len(new), skipped, len(files)), (1, 1, 1))
        [r] = ledger(self.base)
        self.assertEqual((r['member'], r['team'], r['source']), ('writer-1', os.path.realpath(self.tmp / 'runs' / 'r1'), 'import'))
        new, skipped, _ = cost.import_usage(str(self.base), [str(self.tmp / 'runs')], prices)
        self.assertEqual(len(new), 0)
        self.assertEqual(len(ledger(self.base)), 1)

    def test_import_skips_live_duplicate(self):
        team = self.tmp / 'runs' / 'r2'
        log = team / 'members' / 'lead' / 'log'
        log.mkdir(parents=True)
        (log / 'usage.jsonl').write_text(json.dumps({'at': '2026-09-25T11:00:00+08:00', 'batch': 'b1', 'model': 'deepseek-chat',
                                                     'usage': {'prompt_tokens': 7, 'completion_tokens': 3}}) + '\n',
                                         encoding='utf-8')
        self.put(model='deepseek-chat', team=os.path.realpath(team), member='lead', batch='b1',
                 usage={'prompt_tokens': 7, 'completion_tokens': 3})
        new, skipped, _ = cost.import_usage(str(self.base), [str(self.tmp / 'runs')], cost.load_prices(str(self.base)))
        self.assertEqual((len(new), skipped), (0, 1))


if __name__ == '__main__':
    unittest.main()
