"""市場層（aos_market，spec/team/market.md）：用假帳本跑排名、撥額度、倒閉、合併；不開 kernel、不叫模型。"""
import contextlib
import io
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
        self.assertEqual((lim['llm_cpu'], lim['cpu']), (6, 20))
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
        raw['limits']['regular'] = 9                          # c1 有 7 個正式，只剩 2 個名額
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
        self.assertEqual(len(res['moved']), 5)
        self.assertEqual(len(res['laid_off']), 2)
        roster = fmt.load_roster(self.a / 'teams' / 'mfg')
        self.assertIn('c1-mfg-writer1-c2', roster['members'])
        self.assertIn('c1-mfg-writer1-c2', roster['members']['c1-mfg-lead']['mail_to'])
        self.assertEqual(roster['members']['c1-mfg-writer1-c2']['mail_to'], ['c1-mfg-lead', 'human'])
        cfg = co.load(self.a)
        regular, temp, _ = co.headcount(self.a, cfg)
        self.assertEqual((len(regular), len(temp)), (10, 2))
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


class AstraMust(Base):
    """astra 唯讀審查（09-25）必修：每條一個重現→修好的測試。"""

    def grants_of(self, name):
        return cost.load_accounts(str(self.ledger))[name]['grants']

    def quotas(self):
        return {n: b['quota'] for n, b in cost.balances(str(self.ledger)).items()}

    # 必修 1：撥款崩在逐家撥款途中，重跑不重撥
    def test_grant_crash_midway_resumes_without_double_grant(self):
        for n in ('c1', 'c2', 'c3'):
            self.company(n)
            mk.record_score(self.mdir, n, quality=50)
        real = cost.account_grant
        calls = []

        def flaky(*a, **kw):
            calls.append(a[1])
            if len(calls) == 2:
                raise RuntimeError('崩在第二家')
            return real(*a, **kw)
        with mock.patch.object(cost, 'account_grant', flaky):
            with self.assertRaises(RuntimeError):
                mk.do_grant(self.mdir)
        m = mk.load(self.mdir)
        self.assertEqual(m['pending']['kind'], 'grant')
        self.assertEqual(m['history'], [])
        mk.do_grant(self.mdir)                                   # 接著做
        m = mk.load(self.mdir)
        self.assertNotIn('pending', m)
        self.assertEqual(len(m['history']), 1)
        for n in ('c1', 'c2', 'c3'):
            ops = [g['op'] for g in self.grants_of(n) if g.get('op', '').startswith('grant-')]
            self.assertEqual(len(ops), 1, n)                     # 每家這輪只撥一次

    def test_transfer_is_one_step_and_dedups(self):
        self.company('c1')
        self.company('c2')
        base = str(self.ledger)
        before = sum(q['tokens'] for q in self.quotas().values())
        cost.account_transfer(base, 'c2', 'c1', tokens=300, op='t1')
        cost.account_transfer(base, 'c2', 'c1', tokens=300, op='t1')      # 重跑：不再轉
        q = self.quotas()
        self.assertEqual((q['c1']['tokens'], q['c2']['tokens']), (1300, 700))
        self.assertEqual(sum(x['tokens'] for x in q.values()), before)   # 守恆

    # 必修 2：封存視窗崩潰
    def test_close_crash_during_archive_move_recovers(self):
        self.company('c1')
        self.company('c2')
        with mock.patch.object(mk.shutil, 'move', side_effect=RuntimeError('崩在搬家')):
            with self.assertRaises(RuntimeError):
                mk.close(self.mdir, 'c2')
        m = mk.load(self.mdir)
        self.assertEqual(m['companies']['c2']['status'], 'closing')
        self.assertTrue((self.tmp / 'c2').is_dir())
        self.assertEqual(mk.pool_status(m, cost.balances(str(self.ledger)))['slots_used']['llm_cpu'], 10)  # 名額還占著
        row = mk.close(self.mdir, 'c2')                           # 重跑接著做
        self.assertEqual(row['recycled'], {'usd': 1.0, 'tokens': 1000})
        self.assertFalse((self.tmp / 'c2').exists())
        self.assertEqual(mk.load(self.mdir)['companies']['c2']['status'], 'closed')
        recycles = [g for g in self.grants_of('c2') if (g.get('op') or '').endswith(':recycle')]
        self.assertEqual(len(recycles), 1)
        self.assertEqual(cost.balances(str(self.ledger))['c2']['balance'], {'usd': 0.0, 'tokens': 0})

    def test_merge_crash_after_transfer_resumes(self):
        self.company('c1')
        self.company('c2')
        total = sum(q['tokens'] for q in self.quotas().values())
        with mock.patch.object(mk.shutil, 'move', side_effect=RuntimeError('崩在搬家')):
            with self.assertRaises(RuntimeError):
                mk.apply_merge(self.mdir, 'c1', 'c2')
        m = mk.load(self.mdir)
        self.assertEqual((m['pending']['kind'], m['companies']['c2']['status']), ('merge', 'merging'))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(mk.main(['--market', str(self.mdir), 'merge']), 0)     # merge 不帶名字＝接著做
        m = mk.load(self.mdir)
        self.assertNotIn('pending', m)
        self.assertEqual(m['companies']['c2']['status'], 'merged')
        q = self.quotas()
        self.assertEqual(sum(x['tokens'] for x in q.values()), total)         # 沒憑空多出額度
        self.assertEqual(q['c1']['tokens'], 2000)
        names = co.all_member_names(self.tmp / 'c1')
        self.assertEqual(len(names), len(set(names)))

    # 必修 3：市場鎖
    def test_market_lock_serializes_writers(self):
        import threading
        self.company('c1')
        done = []
        with mk.market_lock(self.mdir):
            t = threading.Thread(target=lambda: done.append(mk.grant_slots(self.mdir, 'c1', regular=1)))
            t.start()
            t.join(0.3)
            self.assertEqual(done, [])                            # 鎖在別人手上：等
        t.join(5)
        self.assertEqual(len(done), 1)

    # 必修 4：停機失敗不封存、不收回、不放名額；停好後才算餘額
    def test_stop_failure_keeps_company_and_slots(self):
        self.company('c1')
        self.company('c2')
        (self.tmp / 'c2' / 'K').mkdir()
        with mock.patch.object(co, 'down', return_value=1):
            with self.assertRaises(mk.MarketError) as e:
                mk.close(self.mdir, 'c2')
        self.assertEqual(e.exception.code, 'StopFailed')
        self.assertTrue((self.tmp / 'c2').is_dir())
        self.assertEqual(cost.balances(str(self.ledger))['c2']['quota']['tokens'], 1000)   # 沒收回
        m = mk.load(self.mdir)
        self.assertEqual(mk.pool_status(m, cost.balances(str(self.ledger)))['slots_used']['llm_cpu'], 10)

        def down_and_spend(*a, **kw):                             # 停的途中還在跑的單記了 300
            self.spend('c2', 300)
            return 0
        with mock.patch.object(co, 'down', side_effect=down_and_spend):
            row = mk.close(self.mdir, 'c2')
        self.assertEqual(row['recycled']['tokens'], 700)          # 停好後才算：不會把 300 再發出去
        self.assertEqual(cost.balances(str(self.ledger))['c2']['balance']['tokens'], 0)

    # 必修 5：開戶路徑重疊、重用
    def test_open_rejects_overlapping_or_reused_dirs(self):
        d1 = self.company('c1')
        inner = co.new(d1 / 'inner', EXAMPLE, 'c9-', self.proj)
        with self.assertRaises(mk.MarketError) as e:
            mk.open_company(self.mdir, 'c9', inner)
        self.assertEqual(e.exception.code, 'Conflict')
        self.assertNotIn('c9', cost.load_accounts(str(self.ledger)))           # 被擋的沒開戶
        mk.close(self.mdir, 'c1')
        again = co.new(self.tmp / 'c1', EXAMPLE, 'c1-', self.proj)             # 舊公司的原路徑
        with self.assertRaises(mk.MarketError) as e:
            mk.open_company(self.mdir, 'c1b', again)
        self.assertEqual(e.exception.code, 'Conflict')
        with self.assertRaises(mk.MarketError) as e:
            mk.open_company(self.mdir, 'c1', co.new(self.tmp / 'c1new', EXAMPLE, 'c1-', self.proj))
        self.assertEqual(e.exception.code, 'AlreadyExists')                   # 收掉的名字不再用

    # 必修 9：分數綁輪次
    def test_scores_do_not_carry_over_after_grant(self):
        self.company('c1')
        self.company('c2')
        mk.record_score(self.mdir, 'c1', quality=90, seconds=100)
        mk.do_grant(self.mdir)
        rows = mk.rank(mk.load(self.mdir), cost.balances(str(self.ledger)))
        self.assertEqual([(r['quality'], r['speed'], r['done']) for r in rows], [(0.0, 0.0, 0), (0.0, 0.0, 0)])

    # 必修 10：按結案時間算這一輪
    def test_speed_counts_orders_closed_this_round(self):
        self.company('c1')
        since = '2026-09-25T12:30:00+08:00'
        self.order('c1', 'o-0001', '2026-09-25T12:00:00+08:00', '2026-09-25T13:00:00+08:00')   # 上輪下單、這輪結
        self.order('c1', 'o-0002', '2026-09-25T12:00:00+08:00', '2026-09-25T12:10:00+08:00')   # 上輪就結了
        self.order('c1', 'o-0003', '2026-09-25T04:40:00+00:00', '2026-09-25T04:50:00+00:00')   # 別的時區，這輪
        sp = mk.speed_from_company(self.tmp / 'c1', since)
        self.assertEqual((sp['done'], sp['seconds']), (2, (3600 + 600) / 2))
        o = fmt.read_json(self.tmp / 'c1' / 'switchboard' / 'orders' / 'o-0002.json')
        o['closed_at'] = '2026-09-25T12:45:00+08:00'                                           # 有 closed_at 看它
        fmt.write_json(self.tmp / 'c1' / 'switchboard' / 'orders' / 'o-0002.json', o)
        self.assertEqual(mk.speed_from_company(self.tmp / 'c1', since)['done'], 3)

    # 必修 11：花光的不撥、不准覆寫救活
    def test_broke_company_gets_nothing(self):
        for n in ('c1', 'c2'):
            self.company(n)
            mk.record_score(self.mdir, n, quality=90)
        self.spend('c2', 1000)
        _r, _rows, grants = mk.do_grant(self.mdir, dry_run=True)
        self.assertEqual((grants['c2']['usd'], grants['c2']['tokens']), (0.0, 0))
        self.assertEqual(grants['c1']['tokens'], mk.DEFAULT_PARAMS['round_pool']['tokens'])
        with self.assertRaises(mk.MarketError) as e:
            mk.do_grant(self.mdir, tok_over={'c2': 5000})
        self.assertEqual(e.exception.code, 'Broke')
        mk.do_grant(self.mdir)
        self.assertEqual([o['name'] for o in mk.bankrupt(self.mdir)], ['c2'])

    # 必修 12：slots 不收負數
    def test_slots_rejects_negative(self):
        self.company('c1')
        with self.assertRaises(mk.MarketError) as e:
            mk.grant_slots(self.mdir, 'c1', llm_cpu=-3)
        self.assertEqual(e.exception.code, 'Usage')
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(mk.main(['--market', str(self.mdir), 'slots', 'c1', '--cpu', '-1']), 1)
        self.assertEqual(co.load(self.tmp / 'c1')['limits']['cpu'], 20)

    # 必修 14：合併改名撞名
    def test_merge_rename_collision_gets_suffix(self):
        a = self.company('c1')
        self.company('c2')
        tdir = a / 'teams' / 'mfg'
        roster = fmt.read_json(tdir / 'team.json')
        roster['members']['c1-mfg-writer1-c2'] = {'template': 'worker', 'mail_to': ['human'], 'employment': 'temp'}
        fmt.write_json(tdir / 'team.json', roster, indent=2)
        plan = mk.plan_merge(a, self.tmp / 'c2', 'c2')
        to = {mv['from']: mv.get('to') for mv in plan['moves']}
        self.assertEqual(to['c2-mfg-writer1'], 'c1-mfg-writer1-c2-2')
        mk.apply_merge(self.mdir, 'c1', 'c2', plan)
        got = fmt.load_roster(tdir)['members']
        self.assertEqual(got['c1-mfg-writer1-c2']['employment'], 'temp')           # 原員工沒被蓋掉
        self.assertIn('c1-mfg-writer1-c2-2', got)

    def test_merge_stale_plan_refused(self):
        a = self.company('c1')
        self.company('c2')
        plan = mk.plan_merge(a, self.tmp / 'c2', 'c2')
        raw = fmt.read_json(a / 'company.json')
        raw['limits']['regular'] = 8                                              # 計畫之後名額變了
        fmt.write_json(a / 'company.json', raw, indent=2)
        with self.assertRaises(mk.MarketError) as e:
            mk.apply_merge(self.mdir, 'c1', 'c2', plan)
        self.assertEqual(e.exception.code, 'Stale')

    # 必修 15：美元縮額不超發
    def test_usd_capping_never_overshoots(self):
        m = mk.load(self.mdir)
        m['params']['total'] = {'usd': 2.0001}
        m['params']['shares'] = [0.5, 0.5]                      # 兩家各要一半：縮完各 0.00005，四捨五入會變 0.0001×2
        mk.save(self.mdir, m)
        self.company('c1')
        self.company('c2')
        mk.record_score(self.mdir, 'c1', quality=90)
        mk.record_score(self.mdir, 'c2', quality=80)
        p = mk.pool_status(mk.load(self.mdir), cost.balances(str(self.ledger)))
        self.assertAlmostEqual(p['money']['usd'], 0.0001)
        _r, _rows, grants = mk.do_grant(self.mdir)
        self.assertLessEqual(sum(g['usd'] for g in grants.values()), 0.0001 + 1e-12)
        p = mk.pool_status(mk.load(self.mdir), cost.balances(str(self.ledger)))
        self.assertGreaterEqual(p['money']['usd'], -1e-9)

    # 建議 1：分數驗證
    def test_score_rejects_bad_numbers(self):
        self.company('c1')
        for kw in ({'quality': 120}, {'quality': float('nan')}, {'seconds': -5}, {'hops': float('inf')}):
            with self.assertRaises(mk.MarketError, msg=kw):
                mk.record_score(self.mdir, 'c1', **kw)

    # 可不拍 1：freed 寫進事件
    def test_close_event_has_freed(self):
        self.company('c1')
        mk.close(self.mdir, 'c1')
        ev = mk.load(self.mdir)['events'][-1]
        self.assertIn('c1-hq-lead', ev['freed'])


class PlaytestFixes(Base):
    """試玩員（09-25）給研發部的市場層三件事。"""

    def test_negative_override_refused(self):
        self.company('c1')
        with self.assertRaises(mk.MarketError) as e:
            mk.do_grant(self.mdir, usd_over={'c1': -1.0})
        self.assertEqual(e.exception.code, 'Usage')
        self.assertEqual(cost.balances(str(self.ledger))['c1']['quota']['usd'], 1.0)

    def test_zero_spend_with_done_is_cheapest(self):
        for n, q, sec in (('c1', 85, 300), ('c2', 70, 200), ('c3', 40, 600)):
            self.company(n)
            mk.record_score(self.mdir, n, quality=q, seconds=sec)
        rows = mk.rank(mk.load(self.mdir), cost.balances(str(self.ledger)))
        self.assertEqual({r['cost'] for r in rows}, {100.0})             # 三家都沒花：並列最省
        self.spend('c1', 100)
        by = {r['name']: r for r in mk.rank(mk.load(self.mdir), cost.balances(str(self.ledger)))}
        self.assertEqual((by['c1']['cost'], by['c2']['cost']), (100.0, 100.0))

    def test_every_subcommand_has_help(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), self.assertRaises(SystemExit):
            mk.main(['--help'])
        text = buf.getvalue()
        for cmd in ('open', 'score', 'rank', 'grant', 'bankrupt', 'close', 'pool', 'slots', 'merge', 'ls'):
            line = next((ln for ln in text.splitlines() if ln.strip().startswith(cmd + ' ')), '')
            self.assertTrue(line.strip()[len(cmd):].strip(), cmd)

    def test_seed_covers_several_orders(self):
        self.assertGreaterEqual(mk.DEFAULT_PARAMS['seed']['tokens'], 5 * 4513016)   # 試玩一張單 451 萬 token


if __name__ == '__main__':
    unittest.main()
