"""第 2 隊追加：使用者五題裁決（2026-09-24）。

① 郵差間隔寫在 team.json 的 post.interval_s（預設 5 秒）；② 心跳用自己的身分 beat 派工；
③ 一次性例行叫 once（catalog 跟程式一致）；④ 檢查器壞≠沒過：不扣次數、寄給人、單子停著等人修；
⑤ 例行做完不寄 DONE 給人，只寄異常。
"""
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

import aos_team_beat as beat
import aos_team_format as fmt
import aos_team_post as post
import aos_team_route as route
import aos_team_task as task
from _team_util import PROTO, TeamCase
from test_team_beat import BeatCase


class IntervalTests(TeamCase):
    def test_default_five_seconds(self):
        self.assertEqual(self.rost['post'], {'interval_s': 5})

    def test_custom_and_bad_values(self):
        roster = json.loads((self.team / 'team.json').read_text())
        roster['post'] = {'interval_s': 1}
        self.assertEqual(fmt.validate_roster(roster)['post']['interval_s'], 1)
        for bad in ({'interval_s': 0}, {'interval_s': 'fast'}, {'interval': 5}, {'interval_s': 99999}):
            roster['post'] = bad
            with self.assertRaises(fmt.TeamError) as cm:
                fmt.validate_roster(roster)
            self.assertEqual(cm.exception.code, 'FormatInvalid')
            self.assertIn('post', cm.exception.msg)

    def test_start_registers_with_roster_interval(self):
        seen = []
        orig = post.register
        post.register = lambda team_dir, what, argv, interval_ms, env=None: seen.append(interval_ms) or 0
        try:
            post.start(self.team, env={})
            roster = json.loads((self.team / 'team.json').read_text())
            roster['post'] = {'interval_s': 1}
            (self.team / 'team.json').write_text(json.dumps(roster))
            post.start(self.team, env={})
        finally:
            post.register = orig
        self.assertEqual(seen, [5000, 1000])


class BeatIdentityTests(BeatCase):
    def test_dispatch_is_from_beat_and_says_so(self):
        """② 心跳派的單：申請在 outbox/beat、開單人 beat、派工信寫明是定時器派的。"""
        self.add()
        self.beat()
        reqs = self.requests()
        self.assertEqual(reqs[0]['from'], 'beat')
        self.assertTrue(reqs[0]['id'].endswith('-beat'))
        self.assertFalse(list(self.lay.outbox('human').glob('*.json')))
        self.post()
        t = self.ticket()
        self.assertEqual((t['opened_by'], t['status']), ('beat', 'sent'))
        body = self.mails('worker-1')[0][1]
        self.assertIn('這張單是心跳（定時器）照例行派的', body)
        self.assertIn('回 DONE 給 beat', body)
        self.assertTrue((self.lay.outbox('beat') / 'done' / (reqs[0]['id'] + '.json')).exists())

    def test_worker_reply_to_beat_is_recorded_not_delivered(self):
        self.add()
        self.beat()
        self.post()
        self.pick_up('worker-1')
        self.post()
        lid = self.letter('worker-1', 'beat', 'DONE', '數好了', reply_to='t-0001', rev=1)
        self.post()
        rec = self.record(lid)
        self.assertEqual((rec['kind'], rec['to'], rec['where'], rec['watch_pickup']), ('letter', 'beat', None, False))
        self.assertEqual(self.ticket()['status'], 'verifying')
        self.assertFalse((self.lay.members / 'beat').exists())

    def test_beat_report_header_shows_timer(self):
        """漏跑報告是心跳自己的信（from beat），信頭寫「心跳（定時器）」。"""
        self.add()
        self.now += datetime.timedelta(minutes=4, seconds=10)
        self.beat()
        self.post()
        rep = [m for m in self.mails('lead') if '次沒跑' in m[1]]
        self.assertEqual(len(rep), 1)
        self.assertTrue(rep[0][1].startswith('【來信 心跳（定時器） → lead · PROGRESS'), rep[0][1])
        self.assertTrue(any(m['from'] == 'beat' and '次沒跑' in m['text'] for m in self.human_mail()))

    def test_beat_is_reserved_and_has_limited_rights(self):
        roster = json.loads((self.team / 'team.json').read_text())
        roster['members']['beat'] = {'template': 'worker'}
        with self.assertRaises(fmt.TeamError) as cm:
            fmt.validate_roster(roster)
        self.assertIn('保留名', cm.exception.msg)
        self.assertTrue(fmt.may_send(self.rost, 'beat', 'handoff'))
        self.assertTrue(fmt.may_send(self.rost, 'beat', 'cancel'))
        self.assertFalse(fmt.may_send(self.rost, 'beat', 'answer'))
        self.assertFalse(fmt.may_send(self.rost, 'beat', 'routine'))
        rid = self.new_id('beat')
        (self.lay.outbox('beat') / (rid + '.json')).write_text(json.dumps(
            {'id': rid, 'from': 'beat', 'kind': 'answer', 'at': self.now.isoformat(), 'q': 'q-0001', 'text': '批准'}))
        self.post()
        self.assertEqual(self.record(rid)['code'], 'NotAllowed')   # 心跳不能替人批准

    def test_routes_do_not_accept_beat_as_assignee(self):
        """routes.json 認得 beat：它是保留名，派工規則不能派給它；例子裡有「看例行」一條。"""
        rules = {'routes': [{'name': 'x', 'pattern': '給心跳', 'do': 'handoff',
                             'handoff': {'assignee': 'beat', 'workflow': '無', 'goal': 'g',
                                         'done_when': [{'kind': 'file_exists', 'path': 'a'}]},
                             'tests': {'hit': ['給心跳'], 'miss': ['不給']}}]}
        path = self.tmp / 'routes.json'
        path.write_text(json.dumps(rules, ensure_ascii=False))
        with self.assertRaises(fmt.TeamError) as cm:
            route.load_routes(path)
        self.assertIn('保留名', cm.exception.msg)
        neg, routes = route.load_routes(PROTO / 'spec' / 'team' / 'examples' / 'routes.json')
        result, rule, _, _ = route.decide('看一下例行', neg, routes)
        self.assertEqual((result, rule['run']), ('tool', ['routine', 'ls']))

    def test_team_say_can_reply_to_beat(self):
        import shutil
        pack = self.tmp / 'pack'
        shutil.copytree(PROTO / 'tools' / 'team', pack)
        (pack / 'config.json').write_text(json.dumps({'member': 'worker-1', 'mail_to': ['lead', 'human'],
                                                      'outbox': str(self.lay.outbox('worker-1'))}))
        r = subprocess.run([str(pack / 'team_say')], input=json.dumps(
            {'to': 'beat', 'status': 'DONE', 'reply_to': 't-0001', 'rev': 1, 'text': '好了'}),
            capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn('DONE → beat', r.stdout)
        path = next(self.lay.outbox('worker-1').glob('*.json'))
        self.assertEqual(fmt.read_outbox_file(path, self.rost)[0], 'letter')


class QuietRoutineTests(BeatCase):
    def test_routine_done_does_not_mail_human(self):
        """⑤ 例行做完：人收不到 DONE；上次執行照樣更新。"""
        self.add()
        self.beat()
        self.post()
        self.finish('t-0001')
        self.assertEqual(self.ticket()['status'], 'done')
        self.assertFalse([m for m in self.human_mail() if m['status'] == 'DONE'])
        self.beat()
        self.assertEqual(self.state()['last_result'], 'done')

    def test_routine_timeout_mails_human(self):
        """⑤ 逾時（deadline 到了）還是寄 FAILED 給人。"""
        self.add(timeout=5)
        self.beat()
        self.post()
        self.now += datetime.timedelta(minutes=6)
        self.post()
        self.assertEqual(self.ticket()['status'], 'failed')
        self.assertTrue([m for m in self.human_mail() if m['status'] == 'FAILED' and '期限' in m['text']])

    def test_human_handoff_still_mails_done(self):
        """人開的單照舊：完成寄 DONE 給人。"""
        self.handoff(sender='human')
        self.post()
        self.pick_up('worker-1')
        self.post()
        self.letter('worker-1', 'human', 'DONE', reply_to='t-0001', rev=1)
        self.post()
        self.job_result('v-t-0001-r1-a1', True)
        self.post()
        self.assertTrue([m for m in self.human_mail() if m['status'] == 'DONE' and '完成' in m['text']])


class CheckerBrokenTests(TeamCase):
    def working(self, done_when):
        self.handoff(done_when)
        self.post()
        self.pick_up('worker-1')
        self.post()
        self.letter('worker-1', 'lead', 'DONE', reply_to='t-0001', rev=1)
        self.post()
        self.assertEqual(self.ticket()['status'], 'verifying')

    def broken_result(self, jid, run=1):
        self.job_result(jid, False, run=run, broken=True, results=[
            {'i': 0, 'kind': 'check:nope', 'result': 'error', 'pass': False, 'why': '不認得的檢查器 nope'}])

    def test_broken_checker_no_attempt_used_mail_human_then_again(self):
        """④ 檢查器壞：attempt 不動、隊員沒收到修正信、人收到 BLOCKED；人 --again 之後重交同一次、過了就 done。"""
        self.working([{'kind': 'check', 'name': 'nope'}])
        self.broken_result('v-t-0001-r1-a1')
        self.post()
        t = self.ticket()
        self.assertEqual((t['status'], t['attempt'], t['verify']), ('verifying', 1, []))
        self.assertFalse([m for m in self.mails('worker-1') if '修正' in m[1]])
        blocked = [m for m in self.human_mail() if m['status'] == 'BLOCKED']
        self.assertEqual(len(blocked), 1)
        self.assertIn('檢查器壞了（不是隊員交的東西沒過，不扣次數）', blocked[0]['text'])
        self.assertIn('aos-team verify t-0001 --again', blocked[0]['text'])
        self.post()
        self.assertEqual(len([m for m in self.human_mail() if m['status'] == 'BLOCKED']), 1)   # 只寄一次
        r = self.cli('verify', 't-0001', '--again')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('已交給郵差', r.stdout)
        self.post()
        jobs = sorted(p.name for p in (self.lay.team / 'post' / 'jobs').iterdir() if not p.name.startswith('.'))
        self.assertEqual(len(jobs), 1)
        self.assertTrue(jobs[0].startswith('v-t-0001-r1-a1-x'))
        self.job_result(jobs[0], True)
        self.post()
        t = self.ticket()
        self.assertEqual((t['status'], t['attempt']), ('done', 1))

    def test_real_unknown_checker_result_is_broken(self):
        """真的跑 aos-team verify：不認得的檢查器＝broken，退 1、stderr CheckerBroken；檔不在＝不過（不是壞）。"""
        self.working([{'kind': 'check', 'name': 'nope'}, {'kind': 'file_exists', 'path': 'AGENTS.md'}])
        r = self.cli('verify', 't-0001', '--json')
        self.assertEqual(r.returncode, 1)
        self.assertIn('CheckerBroken', r.stderr)
        res = json.loads(r.stdout)
        self.assertEqual((res['pass'], res['broken']), (False, True))
        self.assertEqual([x['result'] for x in res['results']], ['error', 'fail'])

    def test_missing_file_is_fail_not_broken(self):
        self.working([{'kind': 'check', 'name': 'contains', 'args': {'path': 'nope.md', 'text': 'x'}}])
        r = self.cli('verify', 't-0001', '--json')
        res = json.loads(r.stdout)
        self.assertEqual((res['pass'], res['broken'], res['results'][0]['result']), (False, False, 'fail'))
        self.assertIn('NotPassed', r.stderr)

    def test_no_result_three_times_is_also_broken(self):
        self.working([{'kind': 'file_exists', 'path': 'AGENTS.md'}])
        self.now += datetime.timedelta(seconds=post.JOB_TIMEOUT + 1)
        for _ in range(3):
            self.post()
            self.now += datetime.timedelta(seconds=post.JOB_TIMEOUT + 1)
        self.post()
        self.assertEqual(self.ticket()['attempt'], 1)
        self.assertTrue([m for m in self.human_mail() if '檢查器壞了' in m['text']])

    def test_deadline_does_not_fail_while_waiting_for_checker(self):
        """astra2 M1：檢查器壞、等人修的時候過了期限，不判隊員逾時；人 --again 之後的那份還在跑也不判。"""
        self.working([{'kind': 'check', 'name': 'nope'}])
        t = self.ticket()
        t['deadline'] = (self.now + datetime.timedelta(minutes=1)).isoformat()
        fmt.write_json(self.lay.task('t-0001'), t, indent=2)
        self.broken_result('v-t-0001-r1-a1')
        self.post()
        self.now += datetime.timedelta(minutes=5)
        self.post()
        self.assertEqual(self.ticket()['status'], 'verifying')
        self.request('human', 'reverify', task='t-0001')
        self.post()
        self.post()
        self.assertEqual(self.ticket()['status'], 'verifying')      # 重驗的工作在跑：照樣不判逾時
        self.assertFalse((self.lay.team / 'post' / 'checker-broken' / 't-0001').exists())

    def test_stale_broken_result_not_mailed(self):
        """astra2 M5：人先取消，舊的驗收才回「檢查器壞」＝只記，不寄「等你修」。"""
        self.working([{'kind': 'check', 'name': 'nope'}])
        self.request('human', 'cancel', task='t-0001')
        self.post()
        self.broken_result('v-t-0001-r1-a1')
        self.post()
        self.assertFalse([m for m in self.human_mail() if '檢查器壞了' in m['text']])
        job = json.loads((self.lay.team / 'post' / 'jobs-done' / 'v-t-0001-r1-a1' / 'job.json').read_text())
        self.assertTrue(job['stale'])

    def test_result_without_broken_field_rejected(self):
        """astra2 M4：結果檔漏了 broken（或逐條 result 跟 pass 對不上）＝不收，不會把 error 當成不過扣次數。"""
        self.working([{'kind': 'check', 'name': 'nope'}])
        self.job_result('v-t-0001-r1-a1', False, results=[
            {'i': 0, 'kind': 'check:nope', 'result': 'error', 'pass': False, 'why': 'x'}], broken=None)
        self.post()
        jobdir = self.lay.team / 'post' / 'jobs' / 'v-t-0001-r1-a1'
        self.assertTrue((jobdir / 'result-1.json.bad').exists())
        self.assertEqual(self.ticket()['attempt'], 1)
        self.self_check_result_mismatch()

    def self_check_result_mismatch(self):
        job = {'task': 't-0001', 'rev': 1, 'attempt': 1}
        res = {'task': 't-0001', 'rev': 1, 'attempt': 1, 'pass': False, 'broken': False,
               'results': [{'i': 0, 'result': 'pass', 'pass': False}]}
        self.assertIn('result', post.check_result(res, job))

    def test_blocked_routine_tells_human(self):
        """astra2 M2：例行單負責人回 BLOCKED（寄給 beat）：人收到一封，等的是人。"""
        import aos_team_task as task_mod
        rid = self.new_id('beat')
        (self.lay.outbox('beat') / (rid + '.json')).write_text(json.dumps(
            {'id': rid, 'from': 'beat', 'kind': 'handoff', 'at': self.now.isoformat(), 'assignee': 'worker-1',
             'workflow': '無', 'goal': '〔例行 x〕做事', 'done_when': [{'kind': 'file_exists', 'path': 'a'}]},
            ensure_ascii=False))
        self.post()
        self.pick_up('worker-1')
        self.post()
        self.letter('worker-1', 'beat', 'BLOCKED', '缺 facts.json', reply_to='t-0001', rev=1)
        self.post()
        t = self.ticket()
        self.assertEqual((t['status'], t['waiting_on']), ('blocked', 'human'))
        got = [m for m in self.human_mail() if m['status'] == 'BLOCKED']
        self.assertEqual(len(got), 1)
        self.assertIn('缺 facts.json', got[0]['text'])
        self.letter('worker-1', 'human', 'NEEDS-USER', '要你決定', reply_to='t-0001', rev=1)
        self.post()
        self.assertEqual(len([m for m in self.human_mail() if m['status'] == 'NEEDS-USER']), 1)   # 原信給人＝不重複

    def test_bad_done_when_is_broken_even_if_file_missing(self):
        """astra2 M3：條目寫錯（缺 text、column 寫法不對）先判檢查器壞，不看交付物在不在。"""
        import aos_team_verify as verify
        with self.assertRaises(verify.CheckError):
            verify.check_contains(self.project, {'path': 'nope.md'})
        with self.assertRaises(verify.CheckError):
            verify.check_table_filled(self.project, {'path': 'nope.json', 'column': 3})

    def test_again_busy_while_verify_running(self):
        """astra2 S1：這一次的驗收還在跑就不收 --again。"""
        self.working([{'kind': 'file_exists', 'path': 'AGENTS.md'}])
        rid = self.request('human', 'reverify', task='t-0001')
        self.post()
        self.assertEqual(self.record(rid)['code'], 'Busy')

    def test_again_only_for_verifying(self):
        self.handoff()
        self.post()
        r = self.cli('verify', 't-0001', '--again')
        self.assertEqual(r.returncode, 1)
        self.assertIn('NotVerifying', r.stderr)
        rid = self.request('human', 'reverify', task='t-0001')
        self.post()
        self.assertEqual(self.record(rid)['code'], 'NotVerifying')
        rid = self.request('worker-1', 'reverify', task='t-0001')
        self.post()
        self.assertEqual(self.record(rid)['code'], 'NotAllowed')


class CatalogTests(unittest.TestCase):
    def test_catalog_uses_once(self):
        """③ catalog 的 T-beat 寫 once（跟程式一致），不再寫一次性的 at。"""
        text = (PROTO / 'notes' / '2026-09-24-tool-era' / 'catalog.md').read_text(encoding='utf-8')
        sec = text.split('### T-beat', 1)[1].split('\n### ', 1)[0]
        self.assertIn('`once`', sec)
        self.assertNotIn('`at`', sec)


if __name__ == '__main__':
    unittest.main()
