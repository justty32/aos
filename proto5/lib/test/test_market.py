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

    def board(self, name, t0, t1, status='DONE', verdict='結論：合格', qa='done'):
        """董事下一張單（前台 human 寄件格）＋總裁的結案信（前台 human 收件格）＋中間一張品管總機單。"""
        hq = self.tmp / name / 'teams' / 'hq' / 'team'
        self.n = getattr(self, 'n', 0) + 1
        ask = {'id': '%d-1-human' % self.n, 'from': 'human', 'to': name + '-hq-lead', 'status': 'REQUEST',
               'reply_to': None, 'rev': None, 'text': '補人物 某人', 'at': t0}
        for d in (hq / 'outbox' / 'human' / 'done', hq / 'human'):
            d.mkdir(parents=True, exist_ok=True)
        fmt.write_json(hq / 'outbox' / 'human' / 'done' / (ask['id'] + '.json'), ask)
        close = {'id': '%d-2-%s-hq-lead' % (self.n, name), 'from': name + '-hq-lead', 'to': 'human', 'status': status,
                 'reply_to': 'x', 'rev': None, 'text': '做完了。qa-reports/某人.md %s' % verdict, 'at': t1}
        fmt.write_json(hq / 'human' / (close['id'] + '.json'), close)
        if qa:
            self.order(name, 'o-%04d' % (100 + self.n), t0, t1, status=qa, dept='qa')

    def order(self, name, oid, t0, t1, status='done', replies=1, dept='mfg'):
        folder = self.tmp / name / 'switchboard' / 'orders'
        folder.mkdir(parents=True, exist_ok=True)
        fmt.write_json(folder / (oid + '.json'), {
            'id': oid, 'at': t0, 'status': status, 'from': {'dept': 'hq'}, 'to': {'dept': dept, 'team': dept},
            'replies': [{'letter': 'x%d' % i, 'status': 'DONE', 'at': t1} for i in range(replies)]})


class Scores(Base):
    def test_quality_from_eval(self):
        res = {'people': [
            {'mech': {'passed': 7, 'total': 7}, 'evidence': {'checked_rows': 10, 'ok': 10}, 'judge': {'scores': {'a': 5, 'b': 5}}},
            {'mech': {'passed': 0, 'total': 7}, 'evidence': {'checked_rows': 10, 'ok': 5}}]}
        self.assertEqual(mk.quality_from_eval(res), round((100 + 25) / 2, 2))
        self.assertIsNone(mk.quality_from_eval({'people': []}))

    def test_speed_from_board_orders(self):
        self.company('c1')
        # 只有部門間的總機單、沒有董事的單＝這輪沒有成功結案（以前會算成 2 張、平均 900 秒）
        self.order('c1', 'o-0001', '2026-09-25T12:00:00+08:00', '2026-09-25T12:10:00+08:00', replies=2)
        self.order('c1', 'o-0002', '2026-09-25T12:00:00+08:00', '2026-09-25T12:20:00+08:00')
        self.assertEqual(mk.board_from_company(self.tmp / 'c1'), {'done': 0, 'failed': 0, 'timeout': 0, 'timeout_ids': [],
                                                             'seconds': None, 'hops': None, 'reviews': []})
        self.board('c1', '2026-09-25T12:00:00+08:00', '2026-09-25T12:30:00+08:00')
        self.board('c1', '2026-09-25T13:00:00+08:00', '2026-09-25T13:10:00+08:00')
        self.board('c1', '2026-09-25T14:00:00+08:00', '2026-09-25T14:05:00+08:00', status='FAILED', qa=None)
        sp = mk.board_from_company(self.tmp / 'c1')
        self.assertEqual((sp['done'], sp['failed'], sp['seconds']), (2, 1, 1200.0))
        s = mk.record_score(self.mdir, 'c1', quality=70)
        self.assertEqual((s['quality'], s['seconds'], s['done'], s['failed']), (70, 1200.0, 2, 1))


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
        self.assertEqual(p['slots'], {'regular': 100 - 30, 'cpu': 200 - 60, 'llm_cpu': 25 - 15})

    def test_bankrupt_returns_slots_and_leftover_other_kind(self):
        self.spend('c3', 1000)                                         # token 花超（1400／1000）＝倒閉
        (row,) = mk.bankrupt(self.mdir)
        self.assertEqual(row['reason'], 'bankrupt')
        self.assertNotIn('tokens', row['recycled'])                    # token 歸零：沒得收
        self.assertIn('usd', row['recycled'])                          # 美元還剩：收回總池
        self.assertEqual(row['slots'], {'regular': 10, 'cpu': 20, 'llm_cpu': 5})
        p = self.pool()
        self.assertEqual(p['money']['tokens'], 10000 - (200 + 100 + 1400) - (800 + 900))
        self.assertEqual(p['slots']['llm_cpu'], 25 - 10)
        bal = cost.balances(str(self.ledger))['c3']
        self.assertLessEqual(bal['balance']['usd'], 0)
        ev = mk.load(self.mdir)['events'][-1]
        self.assertEqual((ev['kind'], ev['company']), ('bankrupt', 'c3'))

    def test_bankrupt_and_ls_printing(self):
        """五家真跑 §7 第 7 條：總池沒管美元（total 沒 usd）就不印「收回 usd」；ls 不印 -0.0。"""
        self.spend('c3', 1000)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(mk.main(['--market', str(self.mdir), 'bankrupt']), 0)
        line = buf.getvalue()
        self.assertIn('收回總池 "（沒有剩）"', line)                     # 美元有剩但總池不管：不印
        self.assertNotIn('usd', line.split('收回總池')[1].split('；')[0])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(mk.main(['--market', str(self.mdir), 'ls']), 0)
        self.assertNotIn('-0.0', buf.getvalue())
        self.assertEqual(mk._no_neg_zero({'usd': -0.0, 'tokens': -5}), {'usd': 0.0, 'tokens': -5})
        self.assertEqual(json.dumps(mk._no_neg_zero({'usd': -0.0})), '{"usd": 0.0}')
        self.assertEqual(mk._pool_kinds({'usd': 1.0, 'tokens': 9}, {'tokens': 5}), {'tokens': 9})
        self.assertEqual(mk._pool_kinds({'usd': 1.0}, {'usd': None}), {})

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
        lim = mk.grant_slots(self.mdir, 'c1', llm_cpu=6)
        self.assertEqual((lim['llm_cpu'], lim['cpu']), (11, 20))
        cfg = co.load(self.tmp / 'c1')
        self.assertEqual(cfg['pools']['llm'], 11)
        # 機器 llm cpu 25（董事 09-25 14:20：原 20 提高）：c1 11＋c2 5＋c3 5＝21，第四家要 5 顆就不夠
        with self.assertRaises(mk.MarketError) as e:
            self.company('c4')
        self.assertEqual(e.exception.code, 'NoSlots')
        d = co.new(self.tmp / 'c5', EXAMPLE, 'c5-', self.proj, llm_cpu=4)
        mk.open_company(self.mdir, 'c5', d, usd=0.5, tokens=500)      # 縮到 4 顆就開得了
        with self.assertRaises(mk.MarketError):
            mk.grant_slots(self.mdir, 'c1', llm_cpu=1)                  # 25 用完了


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
            mk.record_score(self.mdir, n, quality=50, done=1)
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
        self.board('c1', '2026-09-25T12:00:00+08:00', '2026-09-25T12:10:00+08:00')   # 上輪就結了
        self.board('c1', '2026-09-25T12:20:00+08:00', '2026-09-25T13:20:00+08:00')   # 上輪下單、這輪結
        self.board('c1', '2026-09-25T04:40:00+00:00', '2026-09-25T04:50:00+00:00')   # 別的時區，這輪
        sp = mk.board_from_company(self.tmp / 'c1', since)
        self.assertEqual((sp['done'], sp['seconds']), (2, (3600 + 600) / 2))

    # 必修 11：花光的不撥、不准覆寫救活
    def test_broke_company_gets_nothing(self):
        for n in ('c1', 'c2'):
            self.company(n)
            mk.record_score(self.mdir, n, quality=90, done=1)
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
        mk.record_score(self.mdir, 'c1', quality=90, done=1)
        mk.record_score(self.mdir, 'c2', quality=80, done=1)
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


FIX = Path(__file__).resolve().parent / 'fixtures' / 'market_run'


class FormulaFix(Base):
    """市場真跑一輪（09-25，notes/2026-09-25-company/market-run）暴露的公式問題；fixture 是那次的原始紀錄（唯讀複製）。"""

    def real(self, name):
        shutil.copytree(FIX / name, self.tmp / name)
        mk.open_company(self.mdir, name, self.tmp / name, usd=1.0, tokens=25000000)

    def two_real(self):
        self.real('c1')
        self.real('c2')
        self.spend('c1', 5954228)
        self.spend('c2', 900020)

    def rows(self):
        return {r['name']: r for r in mk.rank(mk.load(self.mdir), cost.balances(str(self.ledger)))}

    # 3：快＝董事從下單到收到結案信的秒數
    def test_speed_is_board_wait(self):
        self.real('c1')
        self.real('c2')
        b1 = mk.board_from_company(self.tmp / 'c1')
        self.assertEqual((b1['done'], b1['failed'], b1['seconds']), (1, 0, 401.0))    # 13:49:06 → 13:55:47
        b2 = mk.board_from_company(self.tmp / 'c2')
        self.assertEqual((b2['done'], b2['failed'], b2['seconds']), (0, 1, None))      # FAILED 結案＝不算成功
        # 這一輪之後才結案的才算
        self.assertEqual(mk.board_from_company(self.tmp / 'c1', '2026-09-25T13:56:00+08:00')['done'], 0)

    def test_success_needs_qa_pass(self):
        self.real('c1')
        inbox = self.tmp / 'c1' / 'teams' / 'hq' / 'team' / 'human'
        p = next(q for q in inbox.glob('*.json') if fmt.read_json(q)['status'] == 'DONE')
        letter = fmt.read_json(p)
        letter['text'] = letter['text'].replace('結論：合格', '結論：不合格')
        fmt.write_json(p, letter)
        b = mk.board_from_company(self.tmp / 'c1')
        self.assertEqual((b['done'], b['failed']), (0, 1))
        letter['text'] = '老木頭做完了'                                                # 沒寫品管結論＝不算
        fmt.write_json(p, letter)
        self.assertEqual(mk.board_from_company(self.tmp / 'c1')['done'], 0)

    def test_success_verdict_wording(self):
        """五家真跑 09-25：c2 總裁三封結案信都寫「結論為：合格」（品管報告本身是「結論：合格」），以前全算失敗。"""
        self.real('c1')
        inbox = self.tmp / 'c1' / 'teams' / 'hq' / 'team' / 'human'
        p = next(q for q in inbox.glob('*.json') if fmt.read_json(q)['status'] == 'DONE')
        letter = fmt.read_json(p)
        for text, done in (('`qa-reports/老木頭.md` 結論為：合格。', 1), ('結論是: 合格', 1), ('結論： 合格', 1),
                           ('結論為：不合格', 0), ('結論：不合格', 0), ('合格', 0)):
            letter['text'] = text
            fmt.write_json(p, letter)
            self.assertEqual(mk.board_from_company(self.tmp / 'c1')['done'], done, text)

    # 五家真跑 §7 第 1 條長遠版：看品管報告檔本身，結案信次之
    def qa_setup(self, report, letter, qa_status='done'):
        """c1：董事一張單 → 總裁發品管單（o-0001，task t-0001，報告 qa-reports/某人.md）→ 總裁結案信 reply_to 那封。"""
        d = self.company('c1')
        qa = co.team_dirs(d, co.load(d))['qa']
        fmt.Layout(qa).tasks.mkdir(parents=True, exist_ok=True)
        fmt.write_json(fmt.Layout(qa).task('t-0001'), {'id': 't-0001', 'done_when': [
            {'kind': 'file_exists', 'path': 'qa-reports/某人.md'},
            {'kind': 'check', 'name': 'contains', 'args': {'path': 'qa-reports/某人.md', 'text': '結論：'}}]})
        (self.proj / 'qa-reports').mkdir(exist_ok=True)
        (self.proj / 'qa-reports' / '某人.md').write_text(report, encoding='utf-8')
        hq = d / 'teams' / 'hq' / 'team'
        for f in (hq / 'outbox' / 'human' / 'done', hq / 'human'):
            f.mkdir(parents=True, exist_ok=True)
        fmt.write_json(hq / 'outbox' / 'human' / 'done' / '1-1-human.json', {
            'id': '1-1-human', 'from': 'human', 'to': 'c1-hq-lead', 'status': 'REQUEST', 'reply_to': None,
            'rev': None, 'text': '補人物 某人', 'at': '2026-09-25T15:00:00+08:00'})
        folder = d / 'switchboard' / 'orders'
        folder.mkdir(parents=True, exist_ok=True)
        fmt.write_json(folder / 'o-0001.json', {
            'id': 'o-0001', 'at': '2026-09-25T15:03:00+08:00', 'status': qa_status,
            'from': {'dept': 'hq', 'member': 'c1-hq-lead', 'letter': '2-1-c1-hq-lead'},
            'to': {'dept': 'qa', 'team': 'qa', 'member': 'c1-qa-inspector'}, 'task': 't-0001', 'replies': []})
        fmt.write_json(hq / 'human' / '3-1-c1-hq-lead.json', {
            'id': '3-1-c1-hq-lead', 'from': 'c1-hq-lead', 'to': 'human', 'status': 'DONE',
            'reply_to': '2-1-c1-hq-lead', 'rev': None, 'text': letter, 'at': '2026-09-25T15:05:00+08:00'})
        return d

    def test_success_reads_qa_report_first(self):
        d = self.qa_setup('結論：合格\n抽三列都對', '某人做完了，品管說沒問題')     # 信沒抄結論：看報告
        b = mk.board_from_company(d)
        self.assertEqual((b['done'], b['failed'], b['seconds']), (1, 0, 300.0))
        (self.proj / 'qa-reports' / '某人.md').write_text('結論：不合格\n第 2 列行號錯', encoding='utf-8')
        fmt.write_json(d / 'teams' / 'hq' / 'team' / 'human' / '3-1-c1-hq-lead.json', dict(
            fmt.read_json(d / 'teams' / 'hq' / 'team' / 'human' / '3-1-c1-hq-lead.json'), text='結論：合格'))
        b = mk.board_from_company(d)                                         # 總裁轉述錯了：照報告算失敗
        self.assertEqual((b['done'], b['failed']), (0, 1))
        (self.proj / 'qa-reports' / '某人.md').write_text('結論為：合格', encoding='utf-8')
        self.assertEqual(mk.board_from_company(d)['done'], 1)
        (self.proj / 'qa-reports' / '某人.md').unlink()                       # 報告不在：退回看結案信
        self.assertEqual(mk.board_from_company(d)['done'], 1)

    def test_qa_report_pass_but_order_failed_is_failure(self):
        d = self.qa_setup('結論：合格', '結論：合格', qa_status='failed')
        self.assertEqual((mk.board_from_company(d)['done'], mk.board_from_company(d)['failed']), (0, 1))

    # 五家真跑 §7 第 6 條：逾時沒結案＝失敗，只算一次；結案信照 reply_to 配回自己的單
    def ask(self, name, aid, t0):
        box = self.tmp / name / 'teams' / 'hq' / 'team' / 'outbox' / 'human' / 'done'
        box.mkdir(parents=True, exist_ok=True)
        fmt.write_json(box / (aid + '.json'), {'id': aid, 'from': 'human', 'to': name + '-hq-lead',
                                               'status': 'REQUEST', 'reply_to': None, 'rev': None,
                                               'text': '補人物 某人', 'at': t0})

    def test_timeout_counts_as_failed_once(self):
        self.company('c1')
        self.company('c2')
        self.ask('c1', '9-1-human', '2026-09-25T15:00:00+08:00')
        b = mk.board_from_company(self.tmp / 'c1')
        self.assertEqual((b['done'], b['failed'], b['timeout'], b['timeout_ids']), (0, 1, 1, ['9-1-human']))
        s = mk.record_score(self.mdir, 'c1', quality=0)
        self.assertEqual((s['failed'], s['timeout']), (1, 1))
        s = mk.record_score(self.mdir, 'c1', quality=0)                     # 同一輪重打分：照樣算
        self.assertEqual(s['timeout'], 1)
        mk.record_score(self.mdir, 'c2', quality=90, seconds=10)
        mk.do_grant(self.mdir)
        # 下一輪才補到結案信：上輪已算逾時，不再算（也不會配給別張單）
        hq = self.tmp / 'c1' / 'teams' / 'hq' / 'team' / 'human'
        hq.mkdir(parents=True, exist_ok=True)
        fmt.write_json(hq / '9-2-c1-hq-lead.json', {'id': '9-2-c1-hq-lead', 'from': 'c1-hq-lead', 'to': 'human',
                                                    'status': 'DONE', 'reply_to': None, 'rev': None,
                                                    'text': '結論：合格', 'at': mk.now()})
        s = mk.record_score(self.mdir, 'c1', quality=0)
        self.assertEqual((s['done'], s['failed'], s['timeout']), (0, 0, 0))

    def test_close_pairs_by_reply_to_not_first_ask(self):
        """先下的單還沒結案、後下的單先結案：結案信 reply_to 指到後一張單之後發的總機單，就配給後一張。"""
        self.company('c1')
        self.ask('c1', '1-1-human', '2026-09-25T15:00:00+08:00')
        self.ask('c1', '2-1-human', '2026-09-25T15:10:00+08:00')
        self.order('c1', 'o-0001', '2026-09-25T15:11:00+08:00', '2026-09-25T15:12:00+08:00', dept='qa')
        o = fmt.read_json(self.tmp / 'c1' / 'switchboard' / 'orders' / 'o-0001.json')
        o['from']['letter'] = '5-1-c1-hq-lead'
        fmt.write_json(self.tmp / 'c1' / 'switchboard' / 'orders' / 'o-0001.json', o)
        hq = self.tmp / 'c1' / 'teams' / 'hq' / 'team' / 'human'
        hq.mkdir(parents=True, exist_ok=True)
        fmt.write_json(hq / '6-1-c1-hq-lead.json', {'id': '6-1-c1-hq-lead', 'from': 'c1-hq-lead', 'to': 'human',
                                                    'status': 'DONE', 'reply_to': '5-1-c1-hq-lead', 'rev': None,
                                                    'text': '結論：合格', 'at': '2026-09-25T15:13:00+08:00'})
        b = mk.board_from_company(self.tmp / 'c1')
        self.assertEqual((b['done'], b['seconds'], b['timeout_ids']), (1, 180.0, ['1-1-human']))

    # 1：沒有成功結案的，品質、快、省、總分都 0，撥 0
    def test_failed_company_scores_zero(self):
        self.two_real()
        s2 = mk.record_score(self.mdir, 'c2', eval_path=str(FIX / 'c2-quality.json'))
        self.assertEqual((s2['quality'], s2['done'], s2['failed']), (100.0, 0, 1))
        mk.record_score(self.mdir, 'c1', quality=93.75)
        by = self.rows()
        self.assertEqual((by['c2']['quality'], by['c2']['speed'], by['c2']['cost'], by['c2']['score']), (0.0, 0.0, 0.0, 0.0))
        self.assertEqual(by['c1']['score'], 96.25)
        _r, _rows, grants = mk.do_grant(self.mdir, dry_run=True)
        self.assertEqual((grants['c2']['usd'], grants['c2']['tokens']), (0.0, 0))
        self.assertEqual((grants['c1']['usd'], grants['c1']['tokens']), (2.0, 50000000))

    # 4：省只在成功者之間比；只剩一家成功＝滿分、註明無對照
    def test_cost_only_among_successful(self):
        self.two_real()
        mk.record_score(self.mdir, 'c1', quality=93.75)
        mk.record_score(self.mdir, 'c2', quality=100)
        by = self.rows()
        self.assertEqual(by['c1']['cost'], 100.0)
        self.assertEqual(by['c1'].get('note'), '省、快：無對照（這輪只有它成功）')
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            mk._print_rank(mk.rank(mk.load(self.mdir), cost.balances(str(self.ledger))))
        self.assertIn('無對照', buf.getvalue())
        # 三家、兩家成功：失敗那家花得少也不拉低別人
        self.company('c3')
        mk.record_score(self.mdir, 'c3', quality=80, seconds=300)
        self.spend('c3', 5954228 * 2)
        by = self.rows()
        self.assertEqual((by['c1']['cost'], by['c3']['cost']), (100.0, 50.0))
        self.assertIsNone(by['c1'].get('note'))

    # 2：沒人有分＝grant 拒絕（dry-run 也說）；同分均分
    def test_grant_refuses_without_scores(self):
        self.company('c1')
        self.company('c2')
        for dry in (True, False):
            with self.assertRaises(mk.MarketError) as e:
                mk.do_grant(self.mdir, dry_run=dry)
            self.assertEqual(e.exception.code, 'NoScores')
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = mk.main(['--market', str(self.mdir), 'grant', '--dry-run'])
        self.assertEqual(code, 1)
        self.assertIn('本輪無分數', err.getvalue())
        self.assertEqual(cost.balances(str(self.ledger))['c1']['quota'], {'usd': 1.0, 'tokens': 1000})
        mk.record_score(self.mdir, 'c1', quality=90, done=1)
        mk.do_grant(self.mdir)
        with self.assertRaises(mk.MarketError):                      # 撥完再跑一次：新的一輪沒分數，不多發
            mk.do_grant(self.mdir)
        self.assertEqual(len(mk.load(self.mdir)['history']), 1)

    def test_ties_split_evenly(self):
        for n in ('c2', 'c1', 'c3'):
            self.company(n)
        for n in ('c1', 'c2'):
            mk.record_score(self.mdir, n, quality=80, seconds=300)
        mk.record_score(self.mdir, 'c3', quality=40, seconds=300)
        _r, rows, grants = mk.do_grant(self.mdir, dry_run=True)
        self.assertEqual(grants['c1']['tokens'], grants['c2']['tokens'])
        self.assertEqual(grants['c1']['share'], round((0.35 + 0.25) / 2 / 0.8, 4))
        self.assertEqual({r['name']: r['rank'] for r in rows}, {'c1': 1, 'c2': 1, 'c3': 3})

    # 5：證據檔用「A L30」代號也算得出品質
    def fake_project(self, evidence):
        proj = self.tmp / 'evproj'
        src = proj / 'corpus' / 'extracted' / 'story' / 'story_ju_set_1_奇石.md'
        src.parent.mkdir(parents=True)
        src.write_text(''.join('第 %d 行\n' % i for i in range(1, 51)), encoding='utf-8')
        ev = proj / 'lore' / 'evidence' / 'characters' / '老木頭.md'
        ev.parent.mkdir(parents=True)
        ev.write_text(evidence, encoding='utf-8')
        return proj

    def test_eval_expands_file_codes(self):
        proj = self.fake_project('行號依據 A 檔 `corpus/extracted/story/story_ju_set_1_奇石.md`（全 50 行）。\n\n'
                                 '| 節點 | 原文檔名＋行號 | 內容 |\n|---|---|---|\n'
                                 '| 一 | A L3-L5 | 甲 |\n| 二 | A L10、L12 | 乙 |\n| 三 | A L60 | 超界 |\n')
        res = fmt.read_json(FIX / 'c1-quality.json')                  # 真跑：機械 7/7、證據 0/8 全「無檔名」
        self.assertEqual(mk.quality_from_eval(res), 50.0)
        q, notes = mk.quality_from_eval(res, project=proj, notes=True)
        self.assertEqual(q, round(50 + 50 * 2 / 3, 2))                # 展開後 3 列：2 ok、1 超界
        self.assertTrue(any('展開' in n for n in notes), notes)

    def test_eval_unexpandable_reports_zero_with_reason(self):
        proj = self.fake_project('| 節點 | 原文檔名＋行號 | 內容 |\n|---|---|---|\n| 一 | A L3-L5 | 甲 |\n')
        q, notes = mk.quality_from_eval(fmt.read_json(FIX / 'c1-quality.json'), project=proj, notes=True)
        self.assertEqual(q, 50.0)                                     # 證據那半 0
        self.assertTrue(any('無檔名' in n and '展開不了' in n for n in notes), notes)

    def test_real_run_recomputed(self):
        """修完後照那一輪重算：c1 排名分 96.25、撥全額；c2 0 分、撥 0。"""
        self.two_real()
        mk.record_score(self.mdir, 'c1', quality=93.75)             # 展開代號後的真值（報告 §3）
        mk.record_score(self.mdir, 'c2', eval_path=str(FIX / 'c2-quality.json'))
        rows = mk.rank(mk.load(self.mdir), cost.balances(str(self.ledger)))
        self.assertEqual([(r['name'], r['rank'], r['score']) for r in rows], [('c1', 1, 96.25), ('c2', 2, 0.0)])
        self.assertEqual(rows[0]['seconds'], 401.0)


if __name__ == '__main__':
    unittest.main()
