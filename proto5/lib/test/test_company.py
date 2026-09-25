"""公司（aos_company，spec/team/company.md）：樣板全過驗、開 N 家不撞名、上限計算、總機的機械行為。

不開 kernel、不叫模型：團隊資料夾只建總機會碰的那幾格（team/human、outbox/human、tasks、routes.json）。
"""
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest import mock

import aos_company as co
import aos_team_format as fmt
import aos_team_route as route

PROTO = Path(__file__).resolve().parents[2]
EXAMPLE = PROTO / 'examples' / 'company'


def fake_ls(default=12, llm=5):
    return {'health': 'ok', 'pools': {'default': {'want': default}, 'llm': {'want': llm}}}


class Samples(unittest.TestCase):
    def test_rosters_and_routes_pass(self):
        files = sorted((EXAMPLE / 'teams').glob('*/*.json'))
        self.assertGreaterEqual(len(files), 5)
        for f in files:
            obj = fmt.read_json(f)
            if f.name == 'team.json':
                fmt.validate_roster(obj, str(f))
            else:
                neg, routes = route.load_routes(f)
                bad = [x for x in route.run_tests(neg, routes) if not x[1]]
                self.assertEqual(bad, [], f)

    def test_company_json_valid_and_startup_caps(self):
        cfg = co.load(EXAMPLE)
        self.assertEqual(cfg['limits'], {'regular': 10, 'cpu': 20, 'llm_cpu': 5})
        self.assertEqual(cfg['limits_max'], {'regular': 100, 'cpu': 200, 'llm_cpu': 20})
        self.assertLessEqual(cfg['pools']['default'], 20)
        self.assertLessEqual(cfg['pools']['llm'], 5)
        # 每個有團隊的部門，名冊的成員都用部門前綴
        for key, d in cfg['departments'].items():
            if d['team']:
                roster = fmt.load_roster(EXAMPLE / d['team'])
                for name in roster['members']:
                    self.assertTrue(name.startswith(key + '-'), name)
        # staff 列的正式員工 ≤ 10
        regular = [n for n, s in cfg['staff'].items() if s['employment'] == 'regular']
        self.assertLessEqual(len(regular), 10)

    def test_route_handoff_assignees_in_roster(self):
        cfg = co.load(EXAMPLE)
        for key, d in cfg['departments'].items():
            rp = EXAMPLE / (d['team'] or 'x') / 'routes.json'
            if not rp.is_file():
                continue
            roster = fmt.load_roster(EXAMPLE / d['team'])
            for r in fmt.read_json(rp)['routes']:
                if r['do'] == 'handoff':
                    self.assertIn(r['handoff']['assignee'], roster['members'])


class Validate(unittest.TestCase):
    def base(self):
        return json.loads((EXAMPLE / 'company.json').read_text(encoding='utf-8'))

    def test_pools_over_limits(self):
        c = self.base()
        c['pools'] = {'default': 10, 'llm': 6}
        with self.assertRaises(co.CompanyError) as e:
            co.validate(c)
        self.assertEqual(e.exception.code, 'OverLimit')
        c['pools'] = {'default': 21, 'llm': 5}
        with self.assertRaises(co.CompanyError):
            co.validate(c)

    def test_limits_over_ceiling(self):
        c = self.base()
        c['limits'] = {'regular': 101}
        with self.assertRaises(co.CompanyError):
            co.validate(c)

    def test_unknown_key_and_bad_prefix(self):
        c = self.base()
        c['departmnts'] = {}
        with self.assertRaises(co.CompanyError):
            co.validate(c)
        c = self.base()
        c['prefix'] = 'C1_'
        with self.assertRaises(co.CompanyError):
            co.validate(c)

    def test_part_of_must_have_team(self):
        c = self.base()
        c['departments']['sales']['part_of'] = 'fin'
        with self.assertRaises(co.CompanyError):
            co.validate(c)


class Caps(unittest.TestCase):
    def test_cpu_from_ls(self):
        self.assertEqual(co.cpu_from_ls(fake_ls(12, 5)), (12, 5))          # cpu 不含 llm 池（同 HR）
        self.assertEqual(co.cpu_from_ls({'pools': {'default': {'want': 3}}}), (3, 0))
        self.assertEqual(co.cpu_from_ls(None), (0, 0))

    def test_caps_line_and_over(self):
        lim = {'regular': 10, 'cpu': 20, 'llm_cpu': 5}
        self.assertEqual(co.caps_line({'regular': 6, 'cpu': 12, 'llm_cpu': 5}, lim), '正式 6/10、cpu 12/20、llm cpu 5/5')
        self.assertEqual(co.over_caps({'regular': 11, 'cpu': 17, 'llm_cpu': 6}, lim), ['regular', 'llm_cpu'])


class Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='company-test-'))
        self.proj = self.tmp / 'proj'
        self.proj.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def make(self, prefix='c1-', **kw):
        d = co.new(self.tmp / (prefix[:-1] or 'solo'), EXAMPLE, prefix, self.proj, **kw)
        cfg = co.load(d)
        for dept, tdir in co.team_dirs(d, cfg).items():
            lay = fmt.Layout(tdir)
            for sub in (lay.human_inbox, lay.outbox('human'), lay.tasks):
                sub.mkdir(parents=True, exist_ok=True)
            rp = d / 'config' / ('%s.routes.json' % dept)
            if rp.is_file():
                shutil.copy(rp, lay.routes)
        return d, cfg


class NewCompanies(Tmp):
    def test_five_companies_no_name_clash(self):
        names = []
        for i in range(1, 6):
            d, cfg = self.make('c%d-' % i, llm_cpu=4)
            self.assertEqual(cfg['limits']['llm_cpu'], 4)
            self.assertLessEqual(cfg['pools']['llm'], 4)
            self.assertLessEqual(cfg['pools']['default'], cfg['limits']['cpu'])
            got = co.all_member_names(d, cfg)
            self.assertTrue(all(n.startswith('c%d-' % i) for n in got))
            names += got
            for dept, tdir in co.team_dirs(d, cfg).items():
                roster = fmt.load_roster(tdir)
                self.assertEqual(roster['project'], str(self.proj))
                for m in roster['members'].values():
                    for x in m['mail_to']:
                        self.assertTrue(x == 'human' or x.startswith('c%d-' % i))
        self.assertEqual(len(names), len(set(names)))
        # 五家 × 4 顆 llm cpu = 20，剛好是機器上限
        self.assertEqual(sum(co.load(self.tmp / ('c%d' % i))['pools']['llm'] for i in range(1, 6)), 20)

    def test_new_refuses_existing(self):
        self.make('c1-')
        with self.assertRaises(co.CompanyError):
            co.new(self.tmp / 'c1', EXAMPLE, 'c1-', self.proj)

    def test_status_counts_without_kernel(self):
        d, cfg = self.make('c1-')
        s = co.status_data(d, cfg, ls=fake_ls(12, 5))
        self.assertEqual(s['caps'], '正式 7/10、cpu 12/20、llm cpu 5/5')
        self.assertEqual(s['over'], [])
        # 名冊 employment: temp（spawn 生的一律這樣寫，HR hr.md §7）算臨時工，不算人頭
        mfg = co.team_dirs(d, cfg)['mfg']
        roster = fmt.read_json(mfg / 'team.json')
        roster['members']['c1-mfg-temp1'] = {'template': 'worker', 'mail_to': ['c1-mfg-lead'], 'employment': 'temp'}
        fmt.write_json(mfg / 'team.json', roster, indent=2)
        s = co.status_data(d, cfg, ls=fake_ls(21, 6))
        self.assertEqual(s['counts']['regular'], 7)
        self.assertEqual(s['temp'], 1)
        self.assertEqual(s['over'], ['cpu', 'llm_cpu'])

    def test_hr_policy_follows_company_limits(self):
        d, cfg = self.make('c1-', llm_cpu=4)
        p = co.write_hr_policy(d, cfg)
        import aos_team_hr
        pol = aos_team_hr.load_policy(p.parent)
        self.assertEqual((pol['regular_max'], pol['cpu_max'], pol['llm_cpu_max']), (10, 20, 4))

    def test_team_env_has_no_daemon(self):
        d, cfg = self.make('c1-')
        with mock.patch.dict(os.environ, {'AOS_DAEMON_HOME': '/elsewhere/D', 'AOS_HR_HOME': '/elsewhere/hr'}):
            e = co.env_for(d, cfg)
            self.assertNotIn('AOS_DAEMON_HOME', e)                  # HR 數 cpu 不會數到同一個 daemon 上別家的 kernel
            self.assertEqual(e['AOS_HR_HOME'], str(d / 'K' / 'hr'))
            self.assertTrue(co.env_for(d, cfg, daemon=True)['AOS_DAEMON_HOME'].endswith('/D'))


class RelayBase(Tmp):
    def setUp(self):
        super().setUp()
        self.d, self.cfg = self.make('c1-')
        self.teams = co.team_dirs(self.d, self.cfg)
        self.n = 0

    def inbox(self, dept, sender, text, status='REQUEST', reply_to=None):
        """模擬郵差把 sender 寄給 human 的信放進部門的 team/human/。"""
        self.n += 1
        lid = '%d-%d-%s' % (time.time_ns() + self.n, 4242, sender)
        obj = {'id': lid, 'from': sender, 'to': 'human', 'status': status, 'reply_to': reply_to, 'rev': None,
               'text': text, 'at': '2026-09-25T15:00:00+08:00', 'header': '【來信 %s → human · %s】' % (sender, status)}
        fmt.write_json(fmt.Layout(self.teams[dept]).human_inbox / (lid + '.json'), obj)
        return lid

    def outbox(self, dept):
        """部門 human 寄件格裡的檔（總機寫的），每一份都要郵差讀得過。"""
        folder = fmt.Layout(self.teams[dept]).outbox('human')
        roster = fmt.load_roster(self.teams[dept])
        out = []
        for p in fmt.json_files(folder):
            out.append(fmt.read_outbox_file(p, roster))
        return out

    def relay(self):
        return co.Switchboard(self.d).round()

    def order(self, oid):
        return fmt.read_json(self.d / 'switchboard' / 'orders' / (oid + '.json'))


class Relay(RelayBase):
    def test_order_hits_route_then_reply_comes_back(self):
        src = self.inbox('hq', 'c1-hq-lead', '〔給 mfg〕補人物 老財（只寫詞條）\n先看草稿')
        self.relay()
        got = self.outbox('mfg')
        self.assertEqual(len(got), 1)
        kind, req = got[0]
        self.assertEqual(kind, 'request')
        self.assertEqual(req['kind'], 'handoff')
        self.assertEqual(req['assignee'], 'c1-mfg-writer1')
        self.assertIn('〔總機 o-0001', req['goal'])
        self.assertIn('先看草稿', req['facts'])
        o = self.order('o-0001')
        self.assertEqual((o['via'], o['route'], o['status']), ('handoff', 'one-character-light', 'open'))
        self.assertEqual(o['out_id'], req['id'])
        self.assertEqual(o['from']['letter'], src)
        # 再跑一輪：不重派
        self.relay()
        self.assertEqual(len(self.outbox('mfg')), 1)
        self.assertEqual(len(list((self.d / 'switchboard' / 'orders').glob('o-*.json'))), 1)
        # 郵差開了 t-0001（request＝總機寫的那份申請）；寫手自己的 DONE 不轉，郵差驗完的 DONE 才轉
        fmt.write_json(fmt.Layout(self.teams['mfg']).task('t-0001'), {'id': 't-0001', 'request': req['id']})
        self.inbox('mfg', 'c1-mfg-writer1', '寫好了', 'DONE', 't-0001')
        self.relay()
        self.assertEqual(self.outbox('hq'), [])
        self.assertEqual(self.order('o-0001')['status'], 'open')
        self.inbox('mfg', 'post', 't-0001 完成（審查通過）', 'DONE', 't-0001')
        self.relay()
        back = self.outbox('hq')
        self.assertEqual(len(back), 1)
        kind, letter = back[0]
        self.assertEqual((kind, letter['to'], letter['status'], letter['reply_to']), ('letter', 'c1-hq-lead', 'DONE', src))
        self.assertTrue(letter['text'].startswith('〔總機 o-0001 回覆：mfg 部 post → DONE（t-0001）〕'))
        o = self.order('o-0001')
        self.assertEqual((o['status'], o['task']), ('done', 't-0001'))
        self.assertEqual(co.Switchboard(self.d).board_letters(), [])

    def test_miss_goes_to_desk_and_reply_by_order_id(self):
        self.inbox('hq', 'c1-hq-lead', '〔給 研發部〕幫我做一支數字數的小工具')
        self.relay()
        (kind, letter), = self.outbox('rd')
        self.assertEqual((kind, letter['to'], letter['status']), ('letter', 'c1-rd-smith', 'REQUEST'))
        self.assertIn('reply_to 寫 o-0001', letter['text'])
        self.assertEqual(self.order('o-0001')['via'], 'desk')
        self.inbox('rd', 'c1-rd-smith', '草稿好了：count_chars', 'DONE', 'o-0001')
        self.relay()
        (kind, back), = self.outbox('hq')
        self.assertEqual(back['status'], 'DONE')
        self.assertEqual(self.order('o-0001')['status'], 'done')

    def test_desk_reply_without_reply_to_matches_single_open_order(self):
        self.inbox('hq', 'c1-hq-lead', '〔給 rd〕幫忙看一下工具')
        self.relay()
        self.inbox('rd', 'c1-rd-smith', '看完了', 'DONE', None)
        self.relay()
        self.assertEqual(len(self.outbox('hq')), 1)
        self.assertEqual(self.order('o-0001')['status'], 'done')

    def test_mfg_lead_is_desk_for_batches(self):
        self.inbox('hq', 'c1-hq-lead', '〔給 mfg〕補一批人物：老木頭、老薑')
        self.relay()
        (kind, letter), = self.outbox('mfg')
        self.assertEqual(letter['to'], 'c1-mfg-lead')

    def test_bounces(self):
        self.inbox('hq', 'c1-hq-lead', '〔給 xyz〕做點什麼')
        self.inbox('hq', 'c1-hq-lead', '〔給 fin〕算一下帳')
        self.inbox('hq', 'c1-hq-lead', '〔給 hr〕加一個人')
        self.inbox('hq', 'c1-hq-lead', '〔給 mfg〕')
        self.relay()
        got = self.outbox('hq')
        self.assertEqual(len(got), 4)
        texts = sorted(l['text'] for _, l in got)
        self.assertTrue(all(l['status'] == 'FAILED' and l['to'] == 'c1-hq-lead' for _, l in got))
        self.assertTrue(any('沒有「xyz」' in t for t in texts))
        self.assertTrue(any('尚未成立' in t for t in texts))
        self.assertTrue(any('自己的團隊' in t for t in texts))
        self.assertTrue(any('後面沒寫' in t for t in texts))
        self.assertFalse((self.d / 'switchboard' / 'orders').exists() and
                         list((self.d / 'switchboard' / 'orders').glob('o-*.json')))

    def test_board_letters_and_post_marker_ignored(self):
        self.inbox('hq', 'c1-hq-lead', '董事您好：老財做完了', 'DONE')
        self.inbox('mfg', 'post', '〔給 qa〕這是郵差的信，不該被當成單', 'PROGRESS')
        self.relay()
        self.assertEqual(self.outbox('qa'), [])
        board = co.Switchboard(self.d).board_letters()
        self.assertEqual(sorted(d for d, _ in board), ['hq', 'mfg'])

    def test_tool_route_answers_right_away(self):
        self.inbox('hq', 'c1-hq-lead', '〔給 qa〕看一下單子')
        self.relay()
        self.assertEqual(self.outbox('qa'), [])
        (kind, back), = self.outbox('hq')
        self.assertEqual(back['status'], 'DONE')
        self.assertIn('門房直接處理', back['text'])
        o = self.order('o-0001')
        self.assertEqual((o['via'], o['status']), ('tool', 'done'))

    def test_board_order_skips_president(self):
        sb = co.Switchboard(self.d)
        o = sb.board_order('qa', '驗貨 老財')
        self.assertEqual((o['via'], o['to']['member']), ('handoff', 'c1-qa-inspector'))
        (kind, req), = self.outbox('qa')
        self.assertIn('董事 交辦', req['goal'])
        fmt.write_json(fmt.Layout(self.teams['qa']).task('t-0001'), {'id': 't-0001', 'request': req['id']})
        self.inbox('qa', 'post', 't-0001 完成', 'DONE', 't-0001')
        self.relay()
        self.assertEqual(self.outbox('hq'), [])                     # 董事下的單：回覆不寄給誰，留給董事看
        self.assertEqual([d for d, _ in co.Switchboard(self.d).board_letters()], ['qa'])
        self.assertEqual(self.order('o-0001')['status'], 'done')
        with self.assertRaises(co.CompanyError):
            sb.board_order('fin', '算帳')

    def test_crash_between_record_and_action_does_not_duplicate(self):
        lid = self.inbox('hq', 'c1-hq-lead', '〔給 mfg〕補人物 老財（只寫詞條）')
        sb = co.Switchboard(self.d)
        rec = sb.classify('hq', fmt.read_json(fmt.Layout(self.teams['hq']).human_inbox / (lid + '.json')))
        sb._save_seen('hq', lid, rec)                             # 記了帳、還沒動作就崩
        self.relay()
        self.relay()
        self.assertEqual(len(self.outbox('mfg')), 1)
        self.assertEqual(len(list((self.d / 'switchboard' / 'orders').glob('o-*.json'))), 1)

    def test_mark_variants(self):
        for text, want in (('〔給 mfg〕補人物 老財', 'mfg'), ('[給 qa] 驗貨 老財', 'qa'), ('【給 製造部】補人物 老財', 'mfg'),
                           ('給 mfg 補人物', None)):
            m = co.MARK.match(text)
            got = co.resolve_dept(self.cfg, m.group(1)) if m else None
            self.assertEqual(got, want, text)


class RelayAstra(RelayBase):
    """astra 唯讀審查（09-25）必修 6～8、建議 2、可不拍 2：每條重現→修好。"""

    def orders(self):
        return sorted((self.d / 'switchboard' / 'orders').glob('o-*.json'))

    # 必修 6：有填但配不到的 reply_to 不套單一窗口單的 fallback
    def test_wrong_reply_to_is_not_matched_by_fallback(self):
        self.inbox('hq', 'c1-hq-lead', '〔給 rd〕幫忙看一下工具')
        self.relay()
        self.inbox('rd', 'c1-rd-smith', '這是別的事', 'DONE', 'o-0999')
        self.relay()
        self.assertEqual(self.outbox('hq'), [])                        # 沒抄給總裁
        self.assertEqual(self.order('o-0001')['status'], 'open')
        self.assertEqual([d for d, _ in co.Switchboard(self.d).board_letters()], ['rd'])   # 留給董事

    # 必修 6：desk 單只有窗口本人能結
    def test_desk_order_closed_only_by_desk_member(self):
        self.inbox('hq', 'c1-hq-lead', '〔給 mfg〕補一批人物：老木頭、老薑')
        self.relay()
        self.assertEqual(self.order('o-0001')['to']['member'], 'c1-mfg-lead')
        self.inbox('mfg', 'c1-mfg-writer1', '我這邊好了', 'DONE', 'o-0001')
        self.relay()
        self.assertEqual(len(self.outbox('hq')), 1)                    # 回覆照抄
        self.assertEqual(self.order('o-0001')['status'], 'open')       # 但不結案
        self.inbox('mfg', 'c1-mfg-lead', '整批好了', 'DONE', 'o-0001')
        self.relay()
        o = self.order('o-0001')
        self.assertEqual(o['status'], 'done')
        self.assertTrue(o['closed_at'])

    # 必修 7：單寫好、單號還沒記回 seen 就崩＝不另開
    def test_crash_after_order_written_does_not_orphan(self):
        lid = self.inbox('hq', 'c1-hq-lead', '〔給 mfg〕補人物 老財（只寫詞條）')
        real = co.Switchboard._save_seen
        state = {'n': 0}

        def crash_on_second(sb, dept, l, rec):
            state['n'] += 1
            if state['n'] == 2:                                       # 第 1 次＝classify 後；第 2 次＝記單號
                raise RuntimeError('崩在記單號前')
            return real(sb, dept, l, rec)
        with mock.patch.object(co.Switchboard, '_save_seen', crash_on_second):
            with self.assertRaises(RuntimeError):
                self.relay()
        self.assertEqual(len(self.orders()), 1)
        self.relay()
        self.assertEqual(len(self.orders()), 1)                        # 找回同一張，沒有孤兒
        self.assertEqual(len(self.outbox('mfg')), 1)
        self.assertEqual(self.order('o-0001')['from']['letter'], lid)

    # 必修 7：董事單崩在派送前，relay 接著派
    def test_board_order_crash_before_dispatch_resumed(self):
        sb = co.Switchboard(self.d)
        with mock.patch.object(co.Switchboard, 'dispatch', side_effect=RuntimeError('崩在派送前')):
            with self.assertRaises(RuntimeError):
                sb.board_order('qa', '驗貨 老財')
        self.assertIsNone(self.order('o-0001')['via'])
        self.relay()
        o = self.order('o-0001')
        self.assertEqual((o['via'], o['to']['member']), ('handoff', 'c1-qa-inspector'))
        self.relay()
        self.assertEqual(len(self.outbox('qa')), 1)                    # 不重寄

    # 必修 8：門房工具跑完、存結果前崩＝不重跑，標 failed
    def test_tool_not_rerun_after_crash(self):
        import aos_team_cli
        runs = []

        def fake_resolve(_name):
            def run(_tdir, _args):
                runs.append(1)
                print('ok')
                return 0
            return run
        self.inbox('hq', 'c1-hq-lead', '〔給 qa〕看一下單子')
        with mock.patch.object(aos_team_cli, 'resolve', fake_resolve), \
                mock.patch.object(co.Switchboard, '_reply_to_origin', side_effect=RuntimeError('崩在回信前')):
            with self.assertRaises(RuntimeError):
                self.relay()
        self.assertEqual(self.order('o-0001')['status'], 'running')
        with mock.patch.object(aos_team_cli, 'resolve', fake_resolve):
            self.relay()
            self.relay()
        self.assertEqual(len(runs), 1)                                 # 只跑過一次
        o = self.order('o-0001')
        self.assertEqual(o['status'], 'failed')
        (kind, back), = self.outbox('hq')
        self.assertEqual(back['status'], 'FAILED')
        self.assertIn('不自動重跑', back['text'])

    # 建議 2：兼任部門開著、宿主關了＝退信，不中斷整輪
    def test_part_of_closed_host_bounces(self):
        raw = fmt.read_json(self.d / 'company.json')
        raw['departments']['rd']['open'] = False
        host_of = [k for k, v in raw['departments'].items() if v.get('part_of') == 'rd']
        if not host_of:
            raw['departments']['sales'] = dict(raw['departments'].get('sales', {}), part_of='rd', open=True)
            raw['departments']['sales'].pop('team', None)
            host_of = ['sales']
        else:
            raw['departments'][host_of[0]]['open'] = True
        fmt.write_json(self.d / 'company.json', raw, indent=2)
        cfg = co.load(self.d)
        self.assertIsNone(co.host_dept(cfg, host_of[0]))
        self.inbox('hq', 'c1-hq-lead', '〔給 %s〕做點事' % host_of[0])
        self.inbox('hq', 'c1-hq-lead', '〔給 mfg〕補人物 老財（只寫詞條）')
        self.relay()
        self.assertEqual(len(self.outbox('mfg')), 1)                   # 別的信照常處理
        self.assertTrue(any('尚未成立' in l['text'] for _, l in self.outbox('hq')))

    # 可不拍 2：〔給 …〕只認第一行
    def test_mark_only_first_line(self):
        self.assertIsNone(co.MARK.match('\n〔給 mfg〕補人物'))              # 第一行空的、標記在第二行
        self.assertIsNotNone(co.MARK.match('  〔給 mfg〕補人物'))


class KernelPoolSync(Tmp):
    # 必修 13：K 已經在時 up 要把池對到 company.json
    def test_sync_pools_to_company_json(self):
        import aos_kernel_info
        d, cfg = self.make('c1-')
        aos_kernel_info.init(d / 'K', {'pools': {'default': {'count': 3}, 'llm': {'count': 2}}})
        lines = co.sync_kernel_pools(d, cfg)
        info = aos_kernel_info.load_info(d / 'K')
        self.assertEqual((info['pools']['default']['count'], info['pools']['llm']['count']),
                         (cfg['pools']['default'], cfg['pools']['llm']))
        self.assertTrue(lines)
        raw = fmt.read_json(d / 'company.json')
        raw['pools']['llm'] = 1                                         # 上限降了：池也要收
        fmt.write_json(d / 'company.json', raw, indent=2)
        co.sync_kernel_pools(d, co.load(d))
        self.assertEqual(aos_kernel_info.load_info(d / 'K')['pools']['llm']['count'], 1)
        self.assertEqual(co.sync_kernel_pools(d, co.load(d)), [])       # 對齊了就不動

    def test_down_reports_failure(self):
        d, cfg = self.make('c1-')
        (d / 'K').mkdir()
        fail = mock.Mock(returncode=3, stdout='', stderr='stop 失敗')
        with mock.patch.object(co, '_run', return_value=fail), mock.patch('aos_client.call', return_value={}):
            self.assertEqual(co.down(d, out=lambda *_: None), 1)


if __name__ == '__main__':
    unittest.main()
