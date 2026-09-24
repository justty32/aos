"""心跳（aos_team_beat；spec/team/beat.md）：到期派出、在途不重派、DONE 才更新、漏跑只補一次並報告、模型提的要人批。"""
import datetime
import json
import os
import unittest

import aos_team_beat as beat
import aos_team_format as fmt
import aos_team_task as task
from _team_util import PROTO, ROSTER, TeamCase


class BeatCase(TeamCase):
    def beat(self):
        return beat.Beat(self.team, clock=self.clock, out=self.lines.append).run()

    def add(self, name='count-md', **over):
        """人 aos-team routine add（寄申請）→ 郵差寫進 routines.json。"""
        args = ['routine', 'add', name, '--to', 'worker-1', '--goal', '數 md 檔數量寫進 notes/md-count.txt',
                '--done-file', 'notes/md-count.txt']
        if not any(k in over for k in ('every', 'daily', 'once')):
            over['every'] = '2m'
        for k, v in over.items():
            args += ['--' + k.replace('_', '-'), str(v)]
        r = self.cli(*args)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.post()
        rows = beat.load_routines(self.lay)['rows']
        row = next(r for r in rows if r['name'] == name)
        row['added_at'] = self.now.isoformat()               # 時間表從「現在」（假時鐘）起算
        data = beat.load_routines(self.lay)
        data['rows'] = [row if r['name'] == name else r for r in data['rows']]
        fmt.write_json(self.lay.routines, data, indent=2)
        return row

    def requests(self):
        """心跳寄給郵差的派工申請（outbox/human 與 done/ 裡 kind=handoff 的）。"""
        out = []
        box = self.lay.outbox('human')
        for p in list(box.glob('*.json')) + list((box / 'done').glob('*.json')):
            obj = json.loads(p.read_text())
            if obj.get('kind') == 'handoff':
                out.append(obj)
        return sorted(out, key=lambda o: o['id'])

    def finish(self, tid, passed=True):
        """負責人收單、回 DONE、驗收結果回來。"""
        self.pick_up('worker-1')
        self.post()
        t = self.ticket(tid)
        self.letter('worker-1', 'lead', 'DONE', reply_to=tid, rev=t['rev'])
        self.post()
        self.job_result('v-%s-r%d-a%d' % (tid, t['rev'], t['attempt']), passed)
        self.post()

    def state(self, name='count-md'):
        return json.loads((self.team / 'team' / 'beat.json').read_text())['routines'][name]


class BeatTests(BeatCase):
    def test_due_dispatch_inflight_not_redispatched_done_updates(self):
        """驗收⑦：到期派出、在途不重派、DONE 才更新上次執行。"""
        self.add()
        self.beat()
        reqs = self.requests()
        self.assertEqual(len(reqs), 1)
        self.assertEqual(reqs[0]['assignee'], 'worker-1')
        self.assertIn('〔例行 count-md @', reqs[0]['goal'])
        self.post()
        self.assertEqual(self.ticket()['status'], 'sent')
        self.assertIsNone(self.state().get('last_run'))
        self.now += datetime.timedelta(minutes=5)              # 又到期兩次，但上一件還在途
        self.beat()
        self.beat()
        self.assertEqual(len(self.requests()), 1)
        self.finish('t-0001')
        self.assertEqual(self.ticket()['status'], 'done')
        self.beat()
        st = self.state()
        self.assertEqual(st['last_result'], 'done')
        self.assertEqual(st['last_run'], self.now.isoformat())
        self.assertEqual(len(self.requests()), 2)              # 完成後補最近一次
        self.post()
        self.assertIn('次沒跑', self.mails('lead')[-1][1])

    def test_done_then_next_occurrence(self):
        self.add()
        self.beat()
        self.post()
        self.finish('t-0001')
        self.now += datetime.timedelta(seconds=30)
        self.beat()
        self.assertEqual(len(self.requests()), 1)              # 下一次還沒到
        self.now += datetime.timedelta(minutes=2)
        self.beat()
        self.assertEqual(len(self.requests()), 2)
        self.assertFalse([m for m in self.mails('lead') if '沒跑' in m[1]])

    def test_missed_three_dispatches_once_and_reports(self):
        """驗收⑦：漏三次只補一次（最近那次）並報告。"""
        self.add()
        self.now += datetime.timedelta(minutes=4, seconds=10)   # T、T+2、T+4 三次都沒跑
        self.beat()
        reqs = self.requests()
        self.assertEqual(len(reqs), 1)
        occ = (self.now - datetime.timedelta(seconds=10)).strftime('%m-%d %H:%M')
        self.assertIn(occ, reqs[0]['goal'])
        self.post()
        report = [m for m in self.mails('lead') if '心跳' in m[1]]
        self.assertEqual(len(report), 1)
        self.assertIn('有 3 次沒跑', report[0][1])
        self.assertIn('只補最近一次', report[0][1])
        self.assertEqual(len([m for m in self.human_mail() if '心跳' in m['text']]), 1)
        self.beat()
        self.post()
        self.assertEqual(len([m for m in self.mails('lead') if '心跳' in m[1]]), 1)

    def test_failed_retries_then_reports(self):
        self.add(retries=1)
        self.beat()
        self.post()
        self.request('human', 'cancel', task='t-0001')
        self.post()
        self.beat()
        reqs = self.requests()
        self.assertEqual(len(reqs), 2)                          # 重派一次（同一個到期時刻、第 2 次）
        self.assertEqual(reqs[0]['goal'], reqs[1]['goal'])
        self.post()
        self.request('human', 'cancel', task='t-0002')
        self.post()
        self.beat()
        self.assertEqual(len(self.requests()), 2)
        self.assertEqual(self.state()['last_result'], 'failed')
        self.post()
        self.assertIn('2 次都沒成', self.mails('lead')[-1][1])

    def test_daily_and_at(self):
        self.now = self.now.replace(hour=8, minute=0, second=0)
        self.add('morning', daily='09:00')
        self.beat()
        self.assertEqual(self.requests(), [])
        self.now = self.now.replace(hour=9, minute=1)
        self.beat()
        self.assertEqual(len(self.requests()), 1)
        at = (self.now + datetime.timedelta(minutes=5)).isoformat()
        self.add('once', once=at)
        self.beat()
        self.assertEqual(len(self.requests()), 1)
        self.now += datetime.timedelta(minutes=6)
        self.beat()
        self.assertEqual(len(self.requests()), 2)

    def test_schedule_counts(self):
        row = {'name': 'x', 'every': '2m', 'added_at': '2026-09-25T10:00:00+08:00'}
        s = beat.Schedule(row, 'Asia/Taipei')
        t = fmt.parse_iso('2026-09-25T10:07:00+08:00')
        self.assertEqual(s.latest(t).isoformat(), '2026-09-25T10:06:00+08:00')
        self.assertEqual(s.count(None, s.latest(t)), 4)
        self.assertEqual(s.count(fmt.parse_iso('2026-09-25T10:02:00+08:00'), s.latest(t)), 2)
        self.assertEqual(s.next(t).isoformat(), '2026-09-25T10:08:00+08:00')
        d = beat.Schedule({'name': 'y', 'daily': '09:00', 'added_at': '2026-09-25T10:00:00+08:00'}, 'Asia/Taipei')
        self.assertIsNone(d.latest(t))                        # 今天 9 點在登記之前：明天才第一次
        t2 = fmt.parse_iso('2026-09-28T09:30:00+08:00')
        self.assertEqual(d.latest(t2), fmt.parse_iso('2026-09-28T09:00:00+08:00'))
        self.assertEqual(d.count(None, d.latest(t2)), 3)
        with self.assertRaises(fmt.TeamError):
            beat.parse_every('2 weeks')
        with self.assertRaises(fmt.TeamError):
            beat.parse_daily('25:00')

    def test_daily_dst_repeated_hour(self):
        """紐約 2026-11-01 01:00～02:00 重複一次：第二次的 01:15 時，最近一次到期是當天第一次的 01:30（astra M11）。"""
        d = beat.Schedule({'name': 'z', 'daily': '01:30', 'tz': 'America/New_York',
                           'added_at': '2026-10-20T00:00:00-04:00'}, None)
        second_0115 = fmt.parse_iso('2026-11-01T01:15:00-05:00')
        self.assertEqual(d.latest(second_0115), fmt.parse_iso('2026-11-01T01:30:00-04:00'))
        self.assertEqual(d.latest(fmt.parse_iso('2026-11-01T00:59:00-04:00')),
                         fmt.parse_iso('2026-10-31T01:30:00-04:00'))

    def test_bad_timezone_rejected(self):
        r = self.cli('routine', 'add', 'x', '--daily', '09:00', '--tz', 'Asia/Taipie', '--to', 'worker-1',
                     '--goal', 'g', '--done-file', 'a')
        self.assertEqual(r.returncode, 1)
        self.assertIn('BadRoutine', r.stderr)
        self.assertIn('Asia/Taipie', r.stderr)

    def test_readded_routine_gets_new_tickets(self):
        """同名的一次性例行刪掉、同一個時刻重加：是新的一條，不沿用舊的單（astra M6）。"""
        at = (self.now + datetime.timedelta(minutes=1)).isoformat()
        self.add('once-x', once=at)
        self.now += datetime.timedelta(minutes=2)
        self.beat()
        self.post()
        self.finish('t-0001')
        self.beat()
        self.assertTrue(self.state('once-x')['finished'])
        self.assertEqual(self.cli('routine', 'rm', 'once-x').returncode, 0)
        self.post()
        row = self.add('once-x', once=at)
        data = beat.load_routines(self.lay)
        data['rows'][0]['added_at'] = (self.now - datetime.timedelta(minutes=2)).isoformat()
        fmt.write_json(self.lay.routines, data, indent=2)
        self.beat()
        reqs = self.requests()
        self.assertEqual(len(reqs), 2)
        self.assertNotEqual(reqs[0]['id'], reqs[1]['id'])
        self.post()
        self.assertEqual(self.ticket('t-0002')['status'], 'sent')
        self.assertFalse(self.state('once-x').get('finished'))

    def test_failure_report_survives_crash(self):
        """放棄這一次之後、寄報告之前崩了：報告記在待寄裡，下一輪照寄（astra M7）。"""
        self.add()
        self.beat()
        self.post()
        self.request('human', 'cancel', task='t-0001')
        self.post()
        orig = beat.Beat.flush_reports
        beat.Beat.flush_reports = lambda *a: None                 # 模擬：寫完狀態就崩，報告沒寄
        try:
            self.beat()
        finally:
            beat.Beat.flush_reports = orig
        self.assertEqual(self.state()['last_result'], 'failed')
        self.assertEqual(len(self.state()['reports']), 1)
        self.beat()
        self.post()
        self.assertIn('1 次都沒成', self.mails('lead')[-1][1])
        self.assertEqual(self.state()['reports'], [])

    def test_routine_command_errors_and_ls(self):
        r = self.cli('routine', 'add', 'x', '--every', '2m', '--to', 'worker-1', '--goal', 'g')
        self.assertEqual(r.returncode, 2)            # 用法錯
        self.assertIn('--done-file', r.stderr)
        r = self.cli('routine', 'add', 'x', '--every', 'soon', '--to', 'worker-1', '--goal', 'g', '--done-file', 'a')
        self.assertEqual(r.returncode, 1)
        self.assertIn('BadRoutine', r.stderr)
        r = self.cli('routine', 'add', 'x', '--every', '2m', '--to', 'boss', '--goal', 'g', '--done-file', 'a')
        self.assertIn('BadAssignee', r.stderr)
        r = self.cli('routine', 'rm', 'nope')
        self.assertIn('NoSuchRoutine', r.stderr)
        self.add()
        r = self.cli('routine', 'ls')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('count-md  every 2m → worker-1  人登記的  上次 —', r.stdout)
        self.beat()
        r = self.cli('routine', 'ls', '--json')
        self.assertTrue(json.loads(r.stdout)[0]['inflight'])
        r = self.cli('routine', 'rm', 'count-md')
        self.assertEqual(r.returncode, 0)
        self.post()
        self.assertEqual(beat.load_routines(self.lay)['rows'], [])

    def test_same_name_twice_rejected(self):
        self.add()
        r = self.cli('routine', 'add', 'count-md', '--every', '5m', '--to', 'worker-1', '--goal', 'g',
                     '--done-file', 'a')
        self.assertEqual(r.returncode, 0)
        self.post()
        self.assertIn('NameTaken', self.human_mail()[-1]['text'])

    def test_beat_crash_between_state_and_request(self):
        self.add()
        r = self.cli('beat', env={'AOS_TEAM_POST_CRASH': 'beat-dispatch'})
        self.assertEqual(r.returncode, -9)
        self.assertEqual(self.requests(), [])
        self.assertTrue(self.state()['inflight'])
        r = self.cli('beat')
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.cli('beat')
        self.assertEqual(len(self.requests()), 1)


PROPOSER = PROTO / 'templates' / 'lead'


class ProposalTests(BeatCase):
    """成員提的例行：開一題問人，人答「批准」才跑。"""
    roster = json.loads(json.dumps(ROSTER))

    def setUp(self):
        super().setUp()
        tpl = self.tmp / 'tpl-lead'
        tpl.mkdir()
        obj = json.loads((PROPOSER / 'template.json').read_text())
        obj['may'] = obj['may'] + ['routine']
        (tpl / 'template.json').write_text(json.dumps(obj))
        roster = json.loads((self.team / 'team.json').read_text())
        roster['members']['lead']['template'] = str(tpl)
        (self.team / 'team.json').write_text(json.dumps(roster))

    def propose(self):
        self.request('lead', 'routine', op='add', name='tidy', every='2m', to='worker-1', goal='整理 notes',
                     done_when=[{'kind': 'file_exists', 'path': 'notes'}])
        self.post()
        row = beat.load_routines(self.lay)['rows'][0]
        self.assertEqual((row['added_by'], row['q']), ('lead', 'q-0001'))

    def test_unanswered_does_not_run(self):
        """驗收⑦：模型提出的列未經 answer 不跑。"""
        self.propose()
        for _ in range(3):
            self.beat()
            self.now += datetime.timedelta(minutes=3)
        self.assertEqual(self.requests(), [])
        r = self.cli('routine', 'ls')
        self.assertIn('等人批准（aos-team answer q-0001 批准）', r.stdout)

    def test_answer_no_does_not_run(self):
        self.propose()
        self.request('human', 'answer', q='q-0001', text='不要')
        self.post()
        self.beat()
        self.assertEqual(self.requests(), [])

    def test_answer_yes_runs(self):
        self.propose()
        self.request('human', 'answer', q='q-0001', text='批准')
        self.post()
        self.beat()
        self.assertEqual(len(self.requests()), 1)
        self.assertIn('批准', self.mails('lead')[-1][1])     # 提議的人收到答案

    def test_worker_cannot_propose(self):
        rid = self.request('worker-1', 'routine', op='add', name='x', every='2m', to='worker-1', goal='g',
                           done_when=[{'kind': 'file_exists', 'path': 'a'}])
        self.post()
        self.assertEqual(self.record(rid)['code'], 'NotAllowed')

    def test_proposer_request_idempotent(self):
        self.propose()
        rows = beat.load_routines(self.lay)['rows']
        req = {'id': rows[0]['request'], 'from': 'lead', 'kind': 'routine', 'at': self.now.isoformat(), 'op': 'add',
               'name': 'tidy', 'every': '2m', 'to': 'worker-1', 'goal': '整理 notes',
               'done_when': [{'kind': 'file_exists', 'path': 'notes'}]}
        self.assertEqual(beat.on_routine(self.lay, self.rost, req), [])
        self.assertEqual(len(beat.load_routines(self.lay)['rows']), 1)
        self.assertEqual(len(list(self.lay.wait_user.glob('q-*.json'))), 1)


if __name__ == '__main__':
    unittest.main()
