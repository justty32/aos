"""aos-team hr（spec/team/hr.md）：薪資表、政策、名冊 employment、換模型試用、調薪判定、人頭與 cpu 上限、cmd_hr。

大半是程式（讀寫檔、算數），不叫模型；只有 trial() 跑的那支試用團隊才會去叫 aos-team CLI，這裡把
aos_team_hr._team（叫 CLI 的那個函式）換成假的，只有評分指令（score_cmd）真的用 subprocess 跑一支小
python 腳本。每個測試都用暫存資料夾，不碰真的 HR／kernel 家：AOS_KERNEL_HOME／AOS_DAEMON_HOME／
AOS_HR_HOME／AOS_HR_TRIAL 四個環境變數在 setUp 清掉，測試裡要用哪個就自己設。
"""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import aos_team
import aos_team_format as fmt
import aos_team_hr as hr_mod

ENV_KEYS = ('AOS_KERNEL_HOME', 'AOS_DAEMON_HOME', 'AOS_HR_HOME', 'AOS_HR_TRIAL')


def quiet(fn, *a, **kw):
    """跑 fn，把它印的東西收進字串裡，回 (回傳值, 印出來的字)。"""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn(*a, **kw)
    return rc, buf.getvalue()


def roster_obj(members, project='../p'):
    return {'_metainfo': {'_type': 'aos_team', '_version': 1}, 'project': project, 'members': members}


class HrCase(unittest.TestCase):
    """每個測試自己的暫存資料夾＋一個乾淨的 hr 家；四個 HR／kernel 環境變數清掉，不動真的家。"""

    def setUp(self):
        patcher = mock.patch.dict(os.environ, {}, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        for k in ENV_KEYS:
            os.environ.pop(k, None)
        self.tmp = Path(tempfile.mkdtemp(prefix='aos-hr-'))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.hr = self.tmp / 'hr'
        self.hr.mkdir(parents=True)

    def err(self, code, fn, *a, **kw):
        with self.assertRaises(fmt.TeamError) as cm:
            fn(*a, **kw)
        self.assertEqual(cm.exception.code, code, cm.exception.msg)
        return cm.exception.msg


# ------------------------------------------------------------------ 薪資表 ----

class SalaryTests(HrCase):
    def test_missing_file_returns_defaults(self):
        sal = hr_mod.load_salary(self.hr)
        self.assertEqual(sal['tiers']['deepseek-chat'], '笨')
        self.assertEqual(sal['tiers']['chatgpt-gpt-6-astra'], '強')
        self.assertEqual(sal['positions'], {})

    def test_save_load_roundtrip(self):
        sal = hr_mod.empty_salary()
        sal['positions']['worker'] = {'model': 'deepseek-chat', 'tier': '笨'}
        hr_mod.save_salary(self.hr, sal)
        self.assertEqual(hr_mod.load_salary(self.hr), sal)

    def test_bad_tier_value_is_format_invalid(self):
        (self.hr / 'salary.json').write_text(json.dumps({'tiers': {'m': 'boss'}, 'positions': {}}),
                                              encoding='utf-8')
        self.err('FormatInvalid', hr_mod.load_salary, self.hr)


# -------------------------------------------------------------------- 政策 ----

class PolicyTests(HrCase):
    def test_defaults(self):
        p = hr_mod.load_policy(self.hr)
        self.assertEqual((p['stage'], p['regular_max'], p['cpu_max'], p['llm_cpu_max'], p['margin']),
                         ('startup', 10, 20, 5, 5))          # 董事 09-25：預設新創

    def test_stage_grown(self):
        (self.hr / 'policy.json').write_text(json.dumps({'stage': 'grown'}), encoding='utf-8')
        p = hr_mod.load_policy(self.hr)
        self.assertEqual((p['regular_max'], p['cpu_max'], p['llm_cpu_max']), (100, 200, 20))

    def test_stage_then_number_overrides(self):
        (self.hr / 'policy.json').write_text(json.dumps({'stage': 'grown', 'cpu_max': 50}), encoding='utf-8')
        p = hr_mod.load_policy(self.hr)
        self.assertEqual((p['regular_max'], p['cpu_max']), (100, 50))

    def test_bad_stage(self):
        (self.hr / 'policy.json').write_text(json.dumps({'stage': 'huge'}), encoding='utf-8')
        self.err('FormatInvalid', hr_mod.load_policy, self.hr)

    def test_override_from_file(self):
        (self.hr / 'policy.json').write_text(json.dumps({'regular_max': 7}), encoding='utf-8')
        p = hr_mod.load_policy(self.hr)
        self.assertEqual(p['regular_max'], 7)
        self.assertEqual(p['cpu_max'], 20)           # 沒改的維持預設（新創）

    def test_unknown_key_is_format_invalid(self):
        (self.hr / 'policy.json').write_text(json.dumps({'foo': 1}), encoding='utf-8')
        self.err('FormatInvalid', hr_mod.load_policy, self.hr)


# ----------------------------------------------------------- 名冊 employment ----

class RosterEmploymentTests(unittest.TestCase):
    def obj(self, **member_over):
        m = {'template': 'worker', 'mail_to': []}
        m.update(member_over)
        return roster_obj({'worker-1': m})

    def test_missing_defaults_to_regular(self):
        r = fmt.validate_roster(self.obj())
        self.assertEqual(r['members']['worker-1']['employment'], 'regular')

    def test_temp_ok(self):
        r = fmt.validate_roster(self.obj(employment='temp'))
        self.assertEqual(r['members']['worker-1']['employment'], 'temp')

    def test_boss_is_bad(self):
        with self.assertRaises(fmt.TeamError) as cm:
            fmt.validate_roster(self.obj(employment='boss'))
        self.assertEqual(cm.exception.code, 'FormatInvalid')


# --------------------------------------------------------------- trial_roster ----

class TrialRosterTests(unittest.TestCase):
    def test_copies_project_and_member_model_without_touching_original(self):
        raw = roster_obj({'worker-1': {'template': 'worker', 'model': 'old-model', 'mail_to': []}})
        saved = copy.deepcopy(raw)
        out = hr_mod.trial_roster(raw, 'worker-1', 'new-model')
        self.assertEqual(out['project'], '../proj')
        self.assertEqual(out['members']['worker-1']['model'], 'new-model')
        self.assertEqual(raw, saved)                 # 原物件一個位元都沒動


# -------------------------------------------------------------------- trial ----

class TrialTests(HrCase):
    """trial()：換模型跑一份任務集。aos-team CLI 走假的（_team），只有 score_cmd 真的跑一支小腳本。"""

    def setUp(self):
        super().setUp()
        self.ts_dir = self.tmp / 'taskset'
        self.ts_dir.mkdir()
        proj_src = self.ts_dir / 'project'
        proj_src.mkdir()
        (proj_src / 'hello.txt').write_text('hi', encoding='utf-8')
        score_py = self.ts_dir / 'score.py'
        score_py.write_text('import json\nprint(json.dumps({"score": 90, "mech_ok": True}))\n', encoding='utf-8')
        self.taskset = self.ts_dir / 'taskset.json'
        self.taskset.write_text(json.dumps({'name': 'X', 'project': 'project', 'asks': ['do the thing'],
                                            'score_cmd': [sys.executable, str(score_py)]}), encoding='utf-8')
        self.team_dir = self.tmp / 'team'
        self.team_dir.mkdir()
        (self.team_dir / 'p').mkdir()                # team.json 的 project；trial 不碰它，擺著求逼真
        obj = roster_obj({'lead': {'template': 'lead', 'mail_to': ['worker-1']},
                          'worker-1': {'template': 'worker', 'mail_to': ['lead']}})
        (self.team_dir / 'team.json').write_text(json.dumps(obj, ensure_ascii=False), encoding='utf-8')
        self.orig_bytes = (self.team_dir / 'team.json').read_bytes()

    @staticmethod
    def fake_team(cli_env, team, *argv, timeout=300):
        """假的 aos-team CLI：只認 argv 裡有沒有 task／score／wait，其餘一律當成功、沒輸出。"""
        av = [str(a) for a in argv]
        if 'task' in av:
            return SimpleNamespace(returncode=0, stdout=json.dumps([{'id': 't-0001', 'parent': None,
                                                                     'status': 'done'}]), stderr='')
        if 'score' in av:
            return SimpleNamespace(returncode=0, stdout=json.dumps(
                {'axes': {'L': {'score': 3, 'think': 4, 'by_member': {'worker-1': 4}},
                          'R': {'score': 4, 'tokens': 12345}, 'F': {'score': 5}}}), stderr='')
        if 'wait' in av:
            return SimpleNamespace(returncode=0, stdout='[]', stderr='')
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    def test_trial_leaves_original_untouched_and_records_everything(self):
        with mock.patch.object(hr_mod, '_team', side_effect=self.fake_team), \
             mock.patch.object(hr_mod.time, 'sleep', lambda s: None), \
             mock.patch.object(hr_mod, 'check_cpus', lambda *a, **kw: {'cpu': 0, 'llm_cpu': 0, 'kernels': []}):
            rec = hr_mod.trial(self.team_dir, self.hr, 'worker-1', 'deepseek-chat', self.taskset,
                               out=lambda *a, **kw: None)

        # 原團隊的 team.json 一個位元都沒被動過
        self.assertEqual((self.team_dir / 'team.json').read_bytes(), self.orig_bytes)

        # trials.jsonl 多一行，欄位齊全
        lines = (self.hr / 'trials.jsonl').read_text(encoding='utf-8').splitlines()
        self.assertEqual(len(lines), 1)
        row = json.loads(lines[0])
        for k in ('id', 'at', 'team', 'member', 'position', 'from_model', 'model', 'tier', 'taskset', 'status',
                  'score', 'mech_ok', 'tokens', 'wall_s', 'think', 'axes', 'verdict', 'why', 'dir'):
            self.assertIn(k, row, k)
        self.assertEqual(set(row['axes']), set('LSRFHB'))
        self.assertEqual(row, rec)                    # 寫進檔的跟 trial() 回傳的是同一份

        self.assertEqual(row['member'], 'worker-1')
        self.assertEqual(row['position'], 'worker')
        self.assertEqual(row['model'], 'deepseek-chat')
        self.assertEqual(row['tier'], '笨')
        self.assertEqual(row['status'], 'done')
        self.assertEqual(row['score'], 90)
        self.assertTrue(row['mech_ok'])
        self.assertEqual(row['tokens'], 12345)
        self.assertEqual(row['think'], 4)

        # 試用副本：roster.json 換了模型與 project，proj/ 真的複製過去
        trial_dir = Path(row['dir'])
        roster_copy = json.loads((trial_dir / 'roster.json').read_text(encoding='utf-8'))
        self.assertEqual(roster_copy['project'], '../proj')
        self.assertEqual(roster_copy['members']['worker-1']['model'], 'deepseek-chat')
        self.assertTrue((trial_dir / 'proj' / 'hello.txt').is_file())


# ------------------------------------------------------------------ 調薪判定 ----

class VerdictTests(HrCase):
    def base_rec(self, **over):
        rec = {'id': 'tr-0001', 'at': '2026-09-25T10:00:00+08:00', 'position': 'worker', 'taskset': 'X',
               'tier': '強', 'mech_ok': True, 'score': 100, 'model': 'chatgpt-gpt-6-astra'}
        rec.update(over)
        return rec

    def test_strong_model_is_the_baseline(self):
        v, why = hr_mod.verdict(self.hr, self.base_rec(), hr_mod.load_policy(self.hr), hr_mod.empty_salary())
        self.assertEqual(v, '基準')

    def test_pass_updates_min_pass_with_evidence(self):
        hr_mod.append_trial(self.hr, self.base_rec())      # 強模型基準：分數 100、機械全過
        policy, sal = hr_mod.load_policy(self.hr), hr_mod.empty_salary()
        rec = self.base_rec(id='tr-0002', tier='笨', score=96, model='deepseek-chat')
        v, why = hr_mod.verdict(self.hr, rec, policy, sal)
        self.assertEqual(v, '通過', why)
        mp = sal['positions']['worker']['min_pass']
        self.assertEqual((mp['model'], mp['tier'], mp['trial']), ('deepseek-chat', '笨', 'tr-0002'))
        self.assertIn('tr-0001', sal['positions']['worker']['evidence'])
        self.assertIn('tr-0002', sal['positions']['worker']['evidence'])

    def test_fail_leaves_min_pass_alone(self):
        hr_mod.append_trial(self.hr, self.base_rec())
        policy, sal = hr_mod.load_policy(self.hr), hr_mod.empty_salary()
        rec = self.base_rec(id='tr-0003', tier='笨', score=90, model='deepseek-chat')
        v, why = hr_mod.verdict(self.hr, rec, policy, sal)
        self.assertEqual(v, '不通過', why)
        self.assertNotIn('min_pass', sal['positions'].get('worker', {}))

    def test_no_strong_baseline(self):
        policy, sal = hr_mod.load_policy(self.hr), hr_mod.empty_salary()
        rec = self.base_rec(id='tr-0004', tier='笨', score=96, model='deepseek-chat', taskset='沒試過的任務集')
        v, why = hr_mod.verdict(self.hr, rec, policy, sal)
        self.assertEqual(v, '沒有基準', why)

    def test_model_not_in_tiers(self):
        policy, sal = hr_mod.load_policy(self.hr), hr_mod.empty_salary()
        rec = self.base_rec(id='tr-0005', tier='?', model='沒登記過的模型')
        v, why = hr_mod.verdict(self.hr, rec, policy, sal)
        self.assertEqual(v, '等級不明', why)


# ------------------------------------------------------------------- set_member ----

class SetMemberTests(HrCase):
    def setUp(self):
        super().setUp()
        self.team_dir = self.tmp / 'team'
        self.team_dir.mkdir()
        self.lay = fmt.Layout(self.team_dir)

    def write_roster(self, members):
        (self.team_dir / 'team.json').write_text(json.dumps(roster_obj(members), ensure_ascii=False),
                                                  encoding='utf-8')

    def test_changes_model_in_team_json(self):
        self.write_roster({'worker-1': {'template': 'worker', 'mail_to': [], 'employment': 'temp'}})
        hr_mod.set_member(self.team_dir, self.hr, 'worker-1', model='new-model', restart=False,
                          out=lambda *a, **kw: None)
        after = json.loads((self.team_dir / 'team.json').read_text(encoding='utf-8'))
        self.assertEqual(after['members']['worker-1']['model'], 'new-model')

    def test_updates_info_json_when_home_exists(self):
        self.write_roster({'worker-1': {'template': 'worker', 'mail_to': [], 'employment': 'temp'}})
        home = self.lay.member('worker-1')
        home.mkdir(parents=True)
        (home / 'info.json').write_text(json.dumps({'llm': {'model': 'default'}}), encoding='utf-8')
        hr_mod.set_member(self.team_dir, self.hr, 'worker-1', model='new-model', restart=False,
                          out=lambda *a, **kw: None)
        info = json.loads((home / 'info.json').read_text(encoding='utf-8'))
        self.assertEqual(info['llm']['model'], 'new-model')

    def test_unknown_member_is_not_found(self):
        self.write_roster({'worker-1': {'template': 'worker', 'mail_to': [], 'employment': 'temp'}})
        self.err('NotFound', hr_mod.set_member, self.team_dir, self.hr, 'nope', 'x', None, False)

    def test_employment_regular_over_regular_max_is_too_many(self):
        self.write_roster({'lead': {'template': 'lead', 'mail_to': ['worker-1'], 'employment': 'temp'},
                           'worker-1': {'template': 'worker', 'mail_to': ['lead'], 'employment': 'regular'}})
        (self.hr / 'policy.json').write_text(json.dumps({'regular_max': 1}), encoding='utf-8')
        self.err('TooMany', hr_mod.set_member, self.team_dir, self.hr, 'lead', None, 'regular', False)
        after = json.loads((self.team_dir / 'team.json').read_text(encoding='utf-8'))
        self.assertEqual(after['members']['lead']['employment'], 'temp')     # 沒寫進去

    def test_employment_temp_works(self):
        self.write_roster({'worker-1': {'template': 'worker', 'mail_to': [], 'employment': 'regular'}})
        hr_mod.set_member(self.team_dir, self.hr, 'worker-1', None, 'temp', False, out=lambda *a, **kw: None)
        after = json.loads((self.team_dir / 'team.json').read_text(encoding='utf-8'))
        self.assertEqual(after['members']['worker-1']['employment'], 'temp')


# ------------------------------------------------------ count_regular／check_regular ----

class RegularTests(HrCase):
    def make_team(self, name, members):
        d = self.tmp / name
        d.mkdir()
        (d / 'team.json').write_text(json.dumps(roster_obj(members), ensure_ascii=False), encoding='utf-8')
        return d

    def test_count_across_registered_teams(self):
        t1 = self.make_team('team1', {'a': {'template': 'worker', 'mail_to': []},
                                      'b': {'template': 'worker', 'mail_to': []}})              # 2 個正式
        t2 = self.make_team('team2', {'c': {'template': 'worker', 'mail_to': []},
                                      'd': {'template': 'worker', 'mail_to': []},
                                      'e': {'template': 'worker', 'mail_to': [], 'employment': 'temp'}})  # 2 正式 1 臨時
        hr_mod.register_team(self.hr, t1)
        hr_mod.register_team(self.hr, t2)
        total, by = hr_mod.count_regular(self.hr)
        self.assertEqual(total, 4)
        self.assertEqual(by[str(t1.resolve())], 2)
        self.assertEqual(by[str(t2.resolve())], 2)

    def test_check_regular_raises_too_many(self):
        t1 = self.make_team('team1', {'a': {'template': 'worker', 'mail_to': []},
                                      'b': {'template': 'worker', 'mail_to': []}})
        t2 = self.make_team('team2', {'c': {'template': 'worker', 'mail_to': []},
                                      'd': {'template': 'worker', 'mail_to': []}})
        hr_mod.register_team(self.hr, t1)
        hr_mod.register_team(self.hr, t2)
        # t1 名冊換成 3 個正式員工：跨公司會變成 3 + 2 = 5，超過 regular_max=4
        after = fmt.validate_roster(roster_obj({'a': {'template': 'worker', 'mail_to': []},
                                                'b': {'template': 'worker', 'mail_to': []},
                                                'f': {'template': 'worker', 'mail_to': []}}))
        policy = json.loads(json.dumps(hr_mod.DEFAULT_POLICY))
        policy['regular_max'] = 4
        self.err('TooMany', hr_mod.check_regular, self.hr, t1, after, policy)


# ---------------------------------------------------------------------- cpu ----

class CpuTests(HrCase):
    def test_count_cpus_sums_pools_minus_skip(self):
        kdir = self.tmp / 'kernel'
        kdir.mkdir()
        info = {'pools': {'default': {'count': 3}, 'llm': {'count': 2, 'envs': {'AOS_LLM_CONFIG': '/x'}},
                          'big': {'count': 5, 'skip': [1]}}}
        (kdir / 'info.json').write_text(json.dumps(info), encoding='utf-8')
        env = {'AOS_KERNEL_HOME': str(kdir)}
        c = hr_mod.count_cpus(env)
        self.assertEqual((c['cpu'], c['llm_cpu']), (7, 2))          # 3 + (5-1) 一般；llm 池另算

    def test_check_cpus_raises_too_many_over_cpu_max(self):
        kdir = self.tmp / 'kernel'
        kdir.mkdir()
        info = {'pools': {'default': {'count': 3}, 'llm': {'count': 2, 'envs': {'AOS_LLM_CONFIG': '/x'}},
                          'big': {'count': 5, 'skip': [1]}}}
        (kdir / 'info.json').write_text(json.dumps(info), encoding='utf-8')
        env = {'AOS_KERNEL_HOME': str(kdir)}
        policy = json.loads(json.dumps(hr_mod.DEFAULT_POLICY))
        policy['cpu_max'] = 5
        self.err('TooMany', hr_mod.check_cpus, self.hr, env, policy)


# -------------------------------------------------------------------- backlog ----

class BacklogTests(HrCase):
    def test_counts_non_terminal_top_level_tasks_only(self):
        team_dir = self.tmp / 'team'
        lay = fmt.Layout(team_dir)
        lay.tasks.mkdir(parents=True)
        (lay.tasks / 't-0001.json').write_text(json.dumps({'parent': None, 'status': 'working'}), encoding='utf-8')
        (lay.tasks / 't-0002.json').write_text(json.dumps({'parent': None, 'status': 'done'}), encoding='utf-8')
        (lay.tasks / 't-0003.json').write_text(json.dumps({'parent': 't-0001', 'status': 'working'}),
                                               encoding='utf-8')
        self.assertEqual(hr_mod.backlog(team_dir), 1)


# --------------------------------------------------------------------- cmd_hr ----

class CmdHrTests(HrCase):
    def setUp(self):
        super().setUp()
        self.team_dir = self.tmp / 'team'
        self.team_dir.mkdir()
        obj = roster_obj({'lead': {'template': 'lead', 'mail_to': ['worker-1']},
                          'worker-1': {'template': 'worker', 'mail_to': ['lead']}})
        (self.team_dir / 'team.json').write_text(json.dumps(obj, ensure_ascii=False), encoding='utf-8')

    def test_ls_prints_one_row_per_member(self):
        rc, out = quiet(hr_mod.cmd_hr, str(self.team_dir), ['--hr', str(self.hr), 'ls'])
        self.assertEqual(rc, 0)
        self.assertIn('lead', out)
        self.assertIn('worker-1', out)

    def test_trials_empty_says_so(self):
        rc, out = quiet(hr_mod.cmd_hr, str(self.team_dir), ['--hr', str(self.hr), 'trials'])
        self.assertEqual(rc, 0)
        self.assertIn('還沒有試用紀錄', out)


# ----------------------------------------------------------------- _hr_gate ----

class HrGateTests(HrCase):
    def make_roster(self):
        raw = roster_obj({'lead': {'template': 'lead', 'mail_to': ['worker-1']},
                          'worker-1': {'template': 'worker', 'mail_to': ['lead']}})
        return fmt.validate_roster(raw)                 # 兩個成員都預設 regular

    def test_over_regular_max_raises_too_many(self):
        (self.hr / 'policy.json').write_text(json.dumps({'regular_max': 1}), encoding='utf-8')
        lay = fmt.Layout(self.tmp / 'team')
        roster = self.make_roster()
        with mock.patch.dict(os.environ, {'AOS_HR_HOME': str(self.hr)}, clear=False):
            os.environ.pop('AOS_HR_TRIAL', None)
            self.err('TooMany', aos_team._hr_gate, lay, roster)

    def test_hr_trial_env_skips_gate_and_registers_nothing(self):
        (self.hr / 'policy.json').write_text(json.dumps({'regular_max': 1}), encoding='utf-8')
        lay = fmt.Layout(self.tmp / 'team')
        roster = self.make_roster()
        with mock.patch.dict(os.environ, {'AOS_HR_HOME': str(self.hr), 'AOS_HR_TRIAL': 'tr-0001'}, clear=False):
            aos_team._hr_gate(lay, roster)               # 不丟例外
        self.assertFalse((self.hr / 'teams.json').exists())


# ------------------------------------------------------- astra 09-25 必修補測 ----

class ReviewFixTests(HrCase):
    def score(self, body):
        f = self.tmp / 'sc.py'
        f.write_text(body, encoding='utf-8')
        return hr_mod.run_score_cmd([sys.executable, str(f)], self.tmp, dict(os.environ))

    def test_nonzero_exit_voids_score(self):
        r = self.score('import json,sys\nprint(json.dumps({"score": 100, "mech_ok": True}))\nsys.exit(3)\n')
        self.assertEqual((r['score'], r['mech_ok']), (None, False))
        self.assertIn('退 3', r['error'])

    def test_nan_and_out_of_range_score_voided(self):
        for bad in ('NaN', '150', '-1', 'true'):
            r = self.score('print(\'{"score": %s, "mech_ok": true}\')\n' % bad)
            self.assertEqual((r['score'], r['mech_ok']), (None, False), bad)

    def test_trial_roster_drops_mounts(self):
        raw = roster_obj({'worker-1': {'template': 'worker', 'mail_to': [], 'mounts': {'orig': '/abs/orig'}}})
        out = hr_mod.trial_roster(raw, 'worker-1', 'm')
        self.assertNotIn('mounts', out['members']['worker-1'])
        self.assertIn('mounts', raw['members']['worker-1'])

    def test_trial_copy_still_checks_cpus(self):
        kdir = self.tmp / 'kernel'
        kdir.mkdir()
        (kdir / 'info.json').write_text(json.dumps({'pools': {'default': {'count': 30}}}), encoding='utf-8')
        roster = fmt.validate_roster(roster_obj({'lead': {'template': 'lead'}}))
        with mock.patch.dict(os.environ, {'AOS_HR_HOME': str(self.hr), 'AOS_HR_TRIAL': 'tr-0001',
                                          'AOS_KERNEL_HOME': str(kdir)}, clear=False):
            self.err('TooMany', aos_team._hr_gate, fmt.Layout(self.tmp / 'team'), roster, cpus=True)
        self.assertFalse((self.hr / 'teams.json').exists())

    def test_trial_out_inside_original_refused(self):
        team = self.tmp / 'team'
        (self.tmp / 'p').mkdir()
        team.mkdir()
        (team / 'team.json').write_text(json.dumps(roster_obj({'lead': {'template': 'lead'}})), encoding='utf-8')
        ts = self.tmp / 'ts'
        (ts / 'project').mkdir(parents=True)
        (ts / 't.json').write_text(json.dumps({'name': 'X', 'project': 'project', 'asks': ['a'],
                                               'score_cmd': ['true']}), encoding='utf-8')
        with mock.patch.object(hr_mod, 'check_cpus', lambda *a, **kw: None):
            self.err('BadProject', hr_mod.trial, team, self.hr, 'lead', 'm', ts / 't.json',
                     out_dir=str(self.tmp / 'p' / 'x'), out=lambda *a: None)


if __name__ == '__main__':
    unittest.main()
