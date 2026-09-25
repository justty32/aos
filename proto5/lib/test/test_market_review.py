"""市場公式第 74、75 題（經理人 09-25 晚裁決）：品質 × 成功率 × 審查係數；「快」只在成功張數最多的幾家之間比。"""
import contextlib
import io
import unittest

import aos_market as mk
import aos_team_cost as cost
import aos_team_format as fmt

from test_market import Base


class ReviewFactor(unittest.TestCase):
    def test_three_levels_failed_and_none(self):
        f = mk.load('/nonexistent-market-dir')['params']['review_factors']
        self.assertEqual(f, [1.0, 0.7, 0.4])
        self.assertEqual([mk.review_factor(n, f) for n in (1, 2, 3, 4)], [1.0, 0.7, 0.4, 0.4])
        self.assertEqual(mk.review_factor('FAILED', f), 0.0)
        self.assertIsNone(mk.review_factor(None, f))


class Formula(Base):
    def mfg(self, name, tid, t0, status='done', review=(True,)):
        """前台之外的製造部：一張有單號的製造總機單＋那張部門單子（review 是每次審查過沒過）。"""
        folder = self.tmp / name / 'switchboard' / 'orders'
        folder.mkdir(parents=True, exist_ok=True)
        fmt.write_json(folder / ('o-m%s.json' % tid), {
            'id': 'o-m' + tid, 'at': t0, 'status': 'done', 'from': {'dept': 'hq'},
            'to': {'dept': 'mfg', 'team': 'mfg'}, 'task': tid, 'replies': []})
        tasks = self.tmp / name / 'teams' / 'mfg' / 'team' / 'tasks'
        tasks.mkdir(parents=True, exist_ok=True)
        fmt.write_json(tasks / (tid + '.json'), {
            'id': tid, 'status': status,
            'review': [{'rev': 1, 'attempt': i, 'pass': p} for i, p in enumerate(review, 1)]})

    def one(self, name, hour, status='done', review=(True,)):
        t0, t1 = '2026-09-25T%02d:00:00+08:00' % hour, '2026-09-25T%02d:05:00+08:00' % hour
        self.board(name, t0, t1)
        self.mfg(name, 't-%04d' % hour, '2026-09-25T%02d:01:00+08:00' % hour, status, review)

    def set_scores(self, **scores):
        m = mk.load(self.mdir)
        for n, s in scores.items():
            m['scores'][n] = dict(s, round=1)
        mk.save(self.mdir, m)
        return {r['name']: r for r in mk.rank(mk.load(self.mdir), cost.balances(str(self.ledger)))}

    def test_review_rounds_from_ticket(self):
        self.company('c1')
        self.one('c1', 10, review=(True,))
        self.one('c1', 11, review=(False, True))
        self.one('c1', 12, review=(False, False, True))
        b = mk.board_from_company(self.tmp / 'c1')
        self.assertEqual((b['done'], b['reviews']), (3, [1, 2, 3]))
        s = mk.record_score(self.mdir, 'c1', quality=90)
        self.assertEqual((s['review_rounds'], s['review_factor']), ([1, 2, 3], 0.7))   # (1.0＋0.7＋0.4)／3
        self.assertFalse(any('審查紀錄' in n for n in s.get('notes') or []))
        row = mk.rank(mk.load(self.mdir), cost.balances(str(self.ledger)))[0]
        self.assertEqual((row['raw_quality'], row['success_rate'], row['review_factor'], row['quality']),
                         (90, 1.0, 0.7, 63.0))

    def test_overlapping_asks_each_get_own_mfg_order(self):
        """astra 審查必修 1：董事兩張單時間重疊（A 10:00～10:05、B 10:02～10:06），各自的製造總機單不能共用。"""
        self.company('c1')
        self.board('c1', '2026-09-25T10:00:00+08:00', '2026-09-25T10:05:00+08:00')
        self.board('c1', '2026-09-25T10:02:00+08:00', '2026-09-25T10:06:00+08:00')
        self.mfg('c1', 't-0001', '2026-09-25T10:01:00+08:00', review=(True,))                  # A 一次過
        self.mfg('c1', 't-0002', '2026-09-25T10:03:00+08:00', review=(False, False, True))     # B 第三次過
        b = mk.board_from_company(self.tmp / 'c1')
        self.assertEqual((b['done'], b['reviews']), (2, [1, 3]))
        s = mk.record_score(self.mdir, 'c1', quality=100)
        self.assertEqual(s['review_factor'], 0.7)                                       # (1.0＋0.4)／2
        self.assertEqual([mk.review_factor(r, [1.0, 0.7, 0.4]) for r in s['review_rounds']], [1.0, 0.4])

    def test_overlapping_both_orders_after_second_ask(self):
        """兩張製造總機單都在 B 下單之後才發：照時間一對一，A 拿先的、B 拿後的。"""
        self.company('c1')
        self.board('c1', '2026-09-25T10:00:00+08:00', '2026-09-25T10:05:00+08:00')
        self.board('c1', '2026-09-25T10:02:00+08:00', '2026-09-25T10:06:00+08:00')
        self.mfg('c1', 't-0001', '2026-09-25T10:03:00+08:00', review=(True,))
        self.mfg('c1', 't-0002', '2026-09-25T10:04:00+08:00', review=(False, True))
        self.assertEqual(mk.board_from_company(self.tmp / 'c1')['reviews'], [1, 2])

    def test_overlapping_one_order_short_gets_none_with_note(self):
        """重疊的兩張只有一張製造總機單：先下的配走，另一張記 None、說明寫是哪張。"""
        self.company('c1')
        self.board('c1', '2026-09-25T10:00:00+08:00', '2026-09-25T10:05:00+08:00')
        self.board('c1', '2026-09-25T10:02:00+08:00', '2026-09-25T10:06:00+08:00')
        self.mfg('c1', 't-0001', '2026-09-25T10:03:00+08:00', review=(False, True))
        b = mk.board_from_company(self.tmp / 'c1')
        self.assertEqual(b['reviews'], [2, None])
        self.assertTrue(any('2-1-human' in n and '配不到製造總機單' in n for n in b['notes']), b['notes'])
        s = mk.record_score(self.mdir, 'c1', quality=100)
        self.assertTrue(any('配不到製造總機單' in n for n in s['notes']), s['notes'])

    def test_resent_order_same_ask_uses_last(self):
        """沒有重疊：同一張董事的單總裁發了兩張製造總機單（重發），照舊用最後一張。"""
        self.company('c1')
        self.board('c1', '2026-09-25T10:00:00+08:00', '2026-09-25T10:09:00+08:00')
        self.mfg('c1', 't-0001', '2026-09-25T10:01:00+08:00', status='failed', review=(False, False, False))
        self.mfg('c1', 't-0002', '2026-09-25T10:05:00+08:00', review=(True,))
        self.assertEqual(mk.board_from_company(self.tmp / 'c1')['reviews'], [1])

    def test_timed_out_ask_does_not_take_later_order(self):
        """沒結案的單（逾時）不搶後面那張單的製造總機單。"""
        self.company('c1')
        hq = self.tmp / 'c1' / 'teams' / 'hq' / 'team' / 'outbox' / 'human' / 'done'
        hq.mkdir(parents=True, exist_ok=True)
        fmt.write_json(hq / '0-1-human.json', {'id': '0-1-human', 'from': 'human', 'to': 'c1-hq-lead',
                                               'status': 'REQUEST', 'reply_to': None, 'rev': None, 'text': '補人物 甲',
                                               'at': '2026-09-25T09:00:00+08:00'})
        self.board('c1', '2026-09-25T10:00:00+08:00', '2026-09-25T10:05:00+08:00')
        self.mfg('c1', 't-0001', '2026-09-25T10:01:00+08:00', review=(False, True))
        b = mk.board_from_company(self.tmp / 'c1')
        self.assertEqual((b['done'], b['timeout'], b['reviews']), (1, 1, [2]))

    def test_failed_ticket_is_zero(self):
        self.company('c1')
        self.one('c1', 10, status='failed', review=(False, False, False))      # 總裁照樣結案、品管也過
        s = mk.record_score(self.mdir, 'c1', quality=100)
        self.assertEqual((s['done'], s['review_rounds'], s['review_factor']), (1, ['FAILED'], 0.0))
        row = mk.rank(mk.load(self.mdir), cost.balances(str(self.ledger)))[0]
        self.assertEqual((row['quality'], row['raw_quality']), (0.0, 100))

    def test_no_review_record_defaults_to_one_with_warning(self):
        self.company('c1')
        self.board('c1', '2026-09-25T10:00:00+08:00', '2026-09-25T10:05:00+08:00')   # 沒有製造總機單
        s = mk.record_score(self.mdir, 'c1', quality=80)
        self.assertEqual((s['review_rounds'], s['review_factor']), ([None], 1.0))
        self.assertTrue(any('沒有審查紀錄' in n and '1.0' in n for n in s['notes']), s['notes'])
        # 舊資料：分數裡根本沒有 review_factor 這一欄
        by = self.set_scores(c1={'quality': 80, 'done': 1, 'failed': 0, 'seconds': 60})
        self.assertEqual((by['c1']['quality'], by['c1']['review_factor']), (80.0, None))
        self.assertIn('沒有審查紀錄：審查係數當 1.0', by['c1']['note'])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            mk._print_rank(list(by.values()))
        self.assertIn('原品質 成功率 審查', out.getvalue())
        self.assertIn('沒有審查紀錄', out.getvalue())

    def test_success_rate_multiplies_quality(self):
        for n in ('c1', 'c2'):
            self.company(n)
        by = self.set_scores(c1={'quality': 100, 'done': 3, 'failed': 0, 'seconds': 300, 'review_factor': 1.0},
                             c2={'quality': 90, 'done': 1, 'failed': 2, 'seconds': 300, 'review_factor': 1.0})
        self.assertEqual((by['c1']['success_rate'], by['c1']['quality']), (1.0, 100.0))
        self.assertEqual((by['c2']['success_rate'], by['c2']['quality']), (0.3333, 30.0))
        # 逾時算在失敗裡、進分母
        by = self.set_scores(c2={'quality': 90, 'done': 1, 'failed': 1, 'timeout': 1, 'seconds': 300,
                                 'review_factor': 0.7})
        self.assertEqual(by['c2']['quality'], round(90 * 0.5 * 0.7, 2))

    def test_speed_only_among_same_success_count(self):
        for n in ('c1', 'c2', 'c3'):
            self.company(n)
        by = self.set_scores(c1={'quality': 100, 'done': 2, 'failed': 1, 'seconds': 300, 'review_factor': 1.0},
                             c2={'quality': 100, 'done': 1, 'failed': 2, 'seconds': 100, 'review_factor': 1.0},
                             c3={'quality': 100, 'done': 2, 'failed': 1, 'seconds': 600, 'review_factor': 1.0})
        self.assertEqual((by['c1']['speed'], by['c3']['speed']), (100.0, 50.0))
        self.assertEqual(by['c2']['speed'], 0.0)                     # 最快，但成功張數比較少：不比快
        self.assertIn('不比快', by['c2']['note'])
        self.assertIsNone(by['c1']['note'])
        # 成功張數一樣：照舊比
        by = self.set_scores(c2={'quality': 100, 'done': 2, 'failed': 1, 'seconds': 100, 'review_factor': 1.0})
        self.assertEqual((by['c2']['speed'], by['c1']['speed'], by['c3']['speed']), (100.0, 33.33, 16.67))

    def test_score_cli_prints_factors(self):
        self.company('c1')
        self.one('c1', 10, review=(False, True))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(mk.main(['--market', str(self.mdir), 'score', 'c1', '--quality', '80']), 0)
        self.assertIn('成功率 1/1、審查輪數 [2] → 審查係數 0.7', out.getvalue())


if __name__ == '__main__':
    unittest.main()
