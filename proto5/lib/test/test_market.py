"""市場層（aos_market，spec/team/market.md）：用假帳本跑排名、撥額度、倒閉、合併；不開 kernel、不叫模型。"""
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

import aos_company as co
import aos_market as mk
import aos_team_cost as cost
import aos_team_format as fmt

PROTO = Path(__file__).resolve().parents[2]
EXAMPLE = PROTO / 'examples' / 'company'


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='market-test-'))
        self.ledger = self.tmp / 'cost'
        self.mdir = self.tmp / 'market'
        self.proj = self.tmp / 'proj'
        self.proj.mkdir()
        self.env = mock.patch.dict(os.environ, {'AOS_COST_HOME': str(self.ledger)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def company(self, name, **kw):
        d = co.new(self.tmp / name, EXAMPLE, name + '-', self.proj, **kw)
        mk.open_company(self.mdir, name, d, usd=1.0, tokens=1000)
        return d

    def spend(self, name, tokens, member='x'):
        d = self.tmp / name / 'teams' / 'mfg'
        cost.append(str(self.ledger), [cost.make_row(model='deepseek-chat', source='think', team=str(d.resolve()),
                                                     member=member, usage={'prompt_tokens': tokens, 'completion_tokens': 0})])

    def order(self, name, oid, t0, t1, status='done', replies=1):
        folder = self.tmp / name / 'switchboard' / 'orders'
        folder.mkdir(parents=True, exist_ok=True)
        fmt.write_json(folder / (oid + '.json'), {
            'id': oid, 'at': t0, 'status': status, 'from': {'dept': 'hq'}, 'to': {'dept': 'mfg', 'team': 'mfg'},
            'replies': [{'letter': 'x%d' % i, 'status': 'DONE', 'at': t1} for i in range(replies)]})


class Scores(Base):
    def test_quality_from_eval(self):
        res = {'people': [
            {'mech': {'passed': 7, 'total': 7}, 'evidence': {'checked_rows': 10, 'ok': 10}, 'judge': {'scores': {'a': 5, 'b': 5}}},
            {'mech': {'passed': 0, 'total': 7}, 'evidence': {'checked_rows': 10, 'ok': 5}}]}
        self.assertEqual(mk.quality_from_eval(res), round((100 + 25) / 2, 2))
        self.assertIsNone(mk.quality_from_eval({'people': []}))

    def test_speed_from_company_orders(self):
        self.company('c1')
        self.order('c1', 'o-0001', '2026-09-25T12:00:00+08:00', '2026-09-25T12:10:00+08:00', replies=2)
        self.order('c1', 'o-0002', '2026-09-25T12:00:00+08:00', '2026-09-25T12:20:00+08:00')
        self.order('c1', 'o-0003', '2026-09-25T12:00:00+08:00', '2026-09-25T13:00:00+08:00', status='open')
        sp = mk.speed_from_company(self.tmp / 'c1')
        self.assertEqual(sp, {'done': 2, 'seconds': 900.0, 'hops': 2.5})
        s = mk.record_score(self.mdir, 'c1', quality=70)
        self.assertEqual((s['quality'], s['seconds'], s['done']), (70, 900.0, 2))


class RankGrant(Base):
    def setUp(self):
        super().setUp()
        for n in ('c1', 'c2', 'c3'):
            self.company(n)
        mk.record_score(self.mdir, 'c1', quality=90, seconds=600)
        mk.record_score(self.mdir, 'c2', quality=80, seconds=300)
        mk.record_score(self.mdir, 'c3', quality=40, seconds=1200)
        self.spend('c1', 200)
        self.spend('c2', 100)
        self.spend('c3', 400)

    def test_rank_formula(self):
        m = mk.load(self.mdir)
        rows = mk.rank(m, cost.balances(str(self.ledger)))
        by = {r['name']: r for r in rows}
        self.assertEqual((by['c2']['speed'], by['c1']['speed'], by['c3']['speed']), (100.0, 50.0, 25.0))
        self.assertEqual((by['c2']['cost'], by['c1']['cost'], by['c3']['cost']), (100.0, 50.0, 25.0))
        # c1：0.6×90＋0.25×50＋0.15×50＝74；c2：0.6×80＋25＋15＝88；c3：24＋6.25＋3.75＝34
        self.assertEqual([(r['name'], r['score']) for r in rows], [('c2', 88.0), ('c1', 74.0), ('c3', 34.0)])

    def test_weights_are_params(self):
        m = mk.load(self.mdir)
        m['params']['weights'] = {'quality': 1.0, 'speed': 0.0, 'cost': 0.0}
        mk.save(self.mdir, m)
        rows = mk.rank(mk.load(self.mdir), cost.balances(str(self.ledger)))
        self.assertEqual([r['name'] for r in rows], ['c1', 'c2', 'c3'])

    def test_grant_shares_override_and_history(self):
        rnd, rows, grants = mk.do_grant(self.mdir, dry_run=True)
        # 三家：shares 0.35／0.25／0.2 放大到 1
        self.assertAlmostEqual(grants['c2']['share'], 0.4375, places=4)
        self.assertAlmostEqual(grants['c3']['usd'], round(2.0 * 0.25, 4))
        self.assertEqual(cost.balances(str(self.ledger))['c2']['quota'], {'usd': 1.0, 'tokens': 1000})   # dry-run 不寫帳
        rnd, rows, grants = mk.do_grant(self.mdir, usd_over={'c3': 0.0})
        self.assertEqual(rnd, 1)
        self.assertTrue(grants['c3']['override'])
        bal = cost.balances(str(self.ledger))
        self.assertAlmostEqual(bal['c2']['quota']['usd'], 1.0 + 0.875)
        self.assertEqual(bal['c3']['quota']['usd'], 1.0)          # 覆寫成 0：只撥 token
        m = mk.load(self.mdir)
        self.assertEqual(m['history'][0]['spent'], {'c2': 100, 'c1': 200, 'c3': 400})
        # 下一輪只算這輪新花的：c1 再花 50，其他沒花 → c1 以外沒結單也沒花＝省 0
        self.spend('c1', 50)
        rows = mk.rank(mk.load(self.mdir), cost.balances(str(self.ledger)))
        self.assertEqual({r['name']: r['spent_tokens'] for r in rows}, {'c1': 50, 'c2': 0, 'c3': 0})

    def test_min_quality_gate(self):
        m = mk.load(self.mdir)
        m['params']['min_quality'] = 50
        mk.save(self.mdir, m)
        _r, _rows, grants = mk.do_grant(self.mdir, dry_run=True)
        self.assertEqual(grants['c3']['usd'], 0.0)
        self.assertAlmostEqual(grants['c2']['share'] + grants['c1']['share'], 1.0)

    def test_bankrupt(self):
        self.spend('c3', 1000)                                  # token 配額 1000，花了 1400
        out = mk.bankrupt(self.mdir, dry_run=True)
        self.assertEqual([o['name'] for o in out], ['c3'])
        self.assertTrue((self.tmp / 'c3').is_dir())
        out = mk.bankrupt(self.mdir)
        self.assertFalse((self.tmp / 'c3').exists())
        self.assertTrue(Path(out[0]['archive']).is_dir())
        self.assertIn('c3-hq-lead', out[0]['freed'])
        m = mk.load(self.mdir)
        self.assertEqual(m['companies']['c3']['status'], 'bankrupt')
        self.assertEqual(mk.operating(m), ['c1', 'c2'])
        # 經理人再撥款不會自己復活（市場裡已經收掉）；前綴 c3- 可以再開一家
        mk.open_company(self.mdir, 'c3b', co.new(self.tmp / 'c3b', EXAMPLE, 'c3-', self.proj))
        self.assertIn('c3b', mk.operating(mk.load(self.mdir)))


class Pool(Base):
    def setUp(self):
        super().setUp()
        mk.save(self.mdir, dict(mk.load(self.mdir), params=dict(mk.DEFAULT_PARAMS, total={'tokens': 10000})))
        for n in ('c1', 'c2', 'c3'):
            self.company(n)
        self.spend('c1', 200)
        self.spend('c2', 100)
        self.spend('c3', 400)

    def pool(self):
        return mk.pool_status(mk.load(self.mdir), cost.balances(str(self.ledger)))

    def test_pool_money_and_slots(self):
        p = self.pool()
        self.assertEqual(p['money'], {'tokens': 10000 - 3000})          # 總量 − 已花 − 手上沒花的＝總量 − 撥出去的
        self.assertEqual(p['slots'], {'regular': 100 - 30, 'cpu': 200 - 60, 'llm_cpu': 20 - 15})

    def test_bankrupt_returns_slots_and_leftover_other_kind(self):
        self.spend('c3', 1000)                                         # token 花超（1400／1000）＝倒閉
        (row,) = mk.bankrupt(self.mdir)
        self.assertEqual(row['reason'], 'bankrupt')
        self.assertNotIn('tokens', row['recycled'])                    # token 歸零：沒得收
        self.assertIn('usd', row['recycled'])                          # 美元還剩：收回總池
        self.assertEqual(row['slots'], {'regular': 10, 'cpu': 20, 'llm_cpu': 5})
        p = self.pool()
        self.assertEqual(p['money']['tokens'], 10000 - (200 + 100 + 1400) - (800 + 900))
        self.assertEqual(p['slots']['llm_cpu'], 20 - 10)
        bal = cost.balances(str(self.ledger))['c3']
        self.assertLessEqual(bal['balance']['usd'], 0)
        ev = mk.load(self.mdir)['events'][-1]
        self.assertEqual((ev['kind'], ev['company']), ('bankrupt', 'c3'))

    def test_manager_close_recycles_unspent(self):
        before = self.pool()['money']['tokens']
        row = mk.close(self.mdir, 'c2')
        self.assertEqual(row['recycled']['tokens'], 900)
        self.assertEqual(self.pool()['money']['tokens'], before + 900)
        self.assertEqual(mk.load(self.mdir)['companies']['c2']['status'], 'closed')

    def test_grant_capped_by_pool(self):
        m = mk.load(self.mdir)
        m['params']['total'] = {'tokens': 3000 + 1000}                 # 總池只剩 1000，這輪要撥 4,000,000
        mk.save(self.mdir, m)
        mk.record_score(self.mdir, 'c1', quality=90, seconds=100)
        _r, _rows, grants = mk.do_grant(self.mdir)
        self.assertLessEqual(sum(g['tokens'] for g in grants.values()), 1000)
        self.assertGreaterEqual(self.pool()['money']['tokens'], 0)
        self.assertIn('tokens', mk.load(self.mdir)['history'][-1]['capped'])

    def test_slots_grant_and_open_needs_slots(self):
        lim = mk.grant_slots(self.mdir, 'c1', llm_cpu=1)
        self.assertEqual((lim['llm_cpu'], lim['cpu']), (6, 21))
        cfg = co.load(self.tmp / 'c1')
        self.assertEqual(cfg['pools']['llm'], 6)
        # 機器 llm cpu 20：c1 6＋c2 5＋c3 5＝16，第四家要 5 顆就不夠
        with self.assertRaises(mk.MarketError) as e:
            self.company('c4')
        self.assertEqual(e.exception.code, 'NoSlots')
        d = co.new(self.tmp / 'c5', EXAMPLE, 'c5-', self.proj, llm_cpu=4)
        mk.open_company(self.mdir, 'c5', d, usd=0.5, tokens=500)      # 縮到 4 顆就開得了
        with self.assertRaises(mk.MarketError):
            mk.grant_slots(self.mdir, 'c1', llm_cpu=1)                  # 20 用完了


class Merge(Base):
    def setUp(self):
        super().setUp()
        self.a = self.company('c1')
        self.b = self.company('c2')
        notes = fmt.Layout(self.b / 'teams' / 'mfg').notes('c2-mfg-writer1')
        notes.mkdir(parents=True)
        fmt.write_json(notes / 'notes.json', {'notes': [{'k': '老財', 'v': '證據檔要小於 5KB'}]})
        lead_notes = fmt.Layout(self.b / 'teams' / 'mfg').notes('c2-mfg-lead')
        lead_notes.mkdir(parents=True)
        fmt.write_json(lead_notes / 'notes.json', {'notes': []})

    def test_plan_room_then_temp(self):
        raw = fmt.read_json(self.a / 'company.json')
        raw['limits']['regular'] = 8                          # c1 有 6 個正式，只剩 2 個名額
        fmt.write_json(self.a / 'company.json', raw, indent=2)
        plan = mk.plan_merge(self.a, self.b, 'c2')
        by = {mv['from']: mv for mv in plan['moves']}
        self.assertEqual(by['c2-hq-lead']['action'], 'layoff')
        self.assertEqual(by['c2-mfg-lead']['action'], 'layoff')
        self.assertEqual((by['c2-mfg-writer1']['to'], by['c2-mfg-writer1']['employment']), ('c1-mfg-writer1-c2', 'regular'))
        self.assertEqual(by['c2-mfg-reviewer']['employment'], 'regular')
        self.assertEqual(by['c2-qa-inspector']['employment'], 'temp')
        self.assertEqual(by['c2-rd-smith']['employment'], 'temp')
        self.assertEqual(plan['room_left'], 0)
        self.assertEqual([mv['dept'] for mv in plan['moves']][:3], ['mfg', 'mfg', 'mfg'])  # 部門優先序

    def test_apply(self):
        self.spend('c2', 300)
        plan = mk.plan_merge(self.a, self.b, 'c2')
        res = mk.apply_merge(self.mdir, 'c1', 'c2', plan)
        self.assertEqual(len(res['moved']), 4)
        self.assertEqual(len(res['laid_off']), 2)
        roster = fmt.load_roster(self.a / 'teams' / 'mfg')
        self.assertIn('c1-mfg-writer1-c2', roster['members'])
        self.assertIn('c1-mfg-writer1-c2', roster['members']['c1-mfg-lead']['mail_to'])
        self.assertEqual(roster['members']['c1-mfg-writer1-c2']['mail_to'], ['c1-mfg-lead', 'human'])
        cfg = co.load(self.a)
        regular, temp, _ = co.headcount(self.a, cfg)
        self.assertEqual((len(regular), len(temp)), (10, 0))
        names = co.all_member_names(self.a, cfg)
        self.assertEqual(len(names), len(set(names)))
        got = fmt.read_json(fmt.Layout(self.a / 'teams' / 'mfg').notes('c1-mfg-writer1-c2') / 'notes.json')
        self.assertEqual(got['notes'][0]['k'], '老財')
        self.assertTrue((fmt.Layout(self.a / 'teams' / 'mfg').notes('_merged') / 'c2-mfg-lead' / 'notes.json').is_file())
        bal = cost.balances(str(self.ledger))
        self.assertEqual(bal['c1']['quota']['tokens'], 1000 + 700)
        self.assertEqual(bal['c2']['balance']['tokens'], 0)
        m = mk.load(self.mdir)
        self.assertEqual((m['companies']['c2']['status'], m['companies']['c2']['merged_into']), ('merged', 'c1'))
        self.assertFalse(self.b.exists())


if __name__ == '__main__':
    unittest.main()
