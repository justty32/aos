"""郵差的崩潰窗口（驗收③）：真的 SIGKILL 在窗口裡（AOS_TEAM_POST_CRASH），收件人在重跑前把信收走，重跑不重投、不漏動作。"""
import json
import unittest

from _team_util import TeamCase


class CrashWindowTests(TeamCase):
    def crash_run(self, point):
        r = self.cli('post', env={'AOS_TEAM_POST_CRASH': point})
        self.assertEqual(r.returncode, -9, '沒崩在 %s：%s%s' % (point, r.stdout, r.stderr))
        return r

    def ok_run(self):
        r = self.cli('post')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def all_mail(self, name):
        """收件人拿到過的每一封（還在 input 的＋已收進 done/ 的），照信 id。"""
        home = self.lay.member(name) / 'input'
        now = [p.name for p in home.glob('mail-*.json')]
        done = [p.name.split('.json.')[0] + '.json' for p in (home / 'done').glob('mail-*.done')] \
            if (home / 'done').is_dir() else []
        return sorted(now + done)

    def jobs(self):
        base = self.lay.team / 'post'
        return sorted(p.name for d in ('jobs', 'jobs-done') if (base / d).is_dir()
                      for p in (base / d).iterdir() if not p.name.startswith('.'))

    def test_killed_after_drop_recipient_took_it_to_done(self):
        """投進 input 之後、寫 sent 紀錄之前 KILL；收件人重跑前收走（進 done/）→ 重跑不重投。"""
        lid = self.letter('lead', 'worker-1', 'REQUEST', '第一件')
        self.crash_run('delivered')
        self.assertEqual(self.inbox('worker-1'), ['mail-%s.json' % lid])
        self.assertFalse((self.lay.post_sent / (lid + '.json')).exists())
        self.pick_up('worker-1')
        self.ok_run()
        self.ok_run()
        self.assertEqual(self.inbox('worker-1'), [])
        self.assertEqual(self.all_mail('worker-1'), ['mail-%s.json' % lid])
        rec = self.record(lid)
        self.assertTrue(rec['complete'] and rec['picked_up_at'])
        self.assertTrue((self.lay.outbox('lead') / 'done' / (lid + '.json')).exists())

    def test_killed_after_drop_recipient_stuck_in_intake(self):
        """同一個窗口，收件人停在 intake（state.json 記了、檔已搬）→ 重跑不重投。"""
        lid = self.letter('lead', 'worker-1', 'REQUEST')
        self.crash_run('delivered')
        self.pick_up('worker-1', how='intake')
        self.ok_run()
        self.assertEqual(self.all_mail('worker-1'), ['mail-%s.json' % lid])
        self.assertTrue(self.record(lid)['where'].endswith('mail-%s.json' % lid))

    def test_killed_after_drop_of_task_letter(self):
        """開單後派給負責人的那封：投了、紀錄前 KILL、收件人收走 → 重跑不重投，單子照樣走到 working。"""
        rid = self.handoff()
        self.crash_run('delivered')
        self.assertEqual(self.ticket()['status'], 'queued')
        self.pick_up('worker-1')
        self.ok_run()
        self.ok_run()
        self.assertEqual(self.all_mail('worker-1'), ['mail-%s.e0.json' % rid])
        t = self.ticket()
        self.assertEqual(t['status'], 'working')
        self.assertEqual([h['event'] for h in t['history']], ['opened', 'delivered', 'picked_up'])

    def test_killed_after_record_before_move(self):
        """sent 紀錄寫了、原檔還沒搬 → 重跑只搬、不重投。"""
        lid = self.letter('lead', 'worker-1', 'REQUEST')
        self.crash_run('recorded')
        self.assertTrue((self.lay.outbox('lead') / (lid + '.json')).exists())
        self.pick_up('worker-1')
        self.ok_run()
        self.assertEqual(self.all_mail('worker-1'), ['mail-%s.json' % lid])
        self.assertFalse((self.lay.outbox('lead') / (lid + '.json')).exists())
        self.assertTrue((self.lay.outbox('lead') / 'done' / (lid + '.json')).exists())

    def working_ticket(self):
        self.handoff()
        self.post()
        self.pick_up('worker-1')
        self.post()
        self.assertEqual(self.ticket()['status'], 'working')

    def test_killed_after_move_before_effects(self):
        """原檔搬進 done/ 之後、做後續動作之前 KILL → 重跑照紀錄把動作做完（驗收工作只交一次）。"""
        self.working_ticket()
        lid = self.letter('worker-1', 'lead', 'DONE', reply_to='t-0001', rev=1)
        self.crash_run('moved')
        self.assertTrue((self.lay.outbox('worker-1') / 'done' / (lid + '.json')).exists())
        self.assertEqual(self.jobs(), [])
        self.assertEqual(self.ticket()['status'], 'verifying')
        self.ok_run()
        self.ok_run()
        self.assertEqual(self.jobs(), ['v-t-0001-r1-a1'])
        self.assertTrue(all(e['done'] for e in self.record(lid)['effects']))
        self.assertEqual(self.all_mail('lead'), ['mail-%s.json' % lid])

    def test_killed_after_effect_before_tick(self):
        """動作做了、還沒勾 KILL → 重跑重做同一件，但不多交一份工作、不多投一封。"""
        self.working_ticket()
        self.letter('worker-1', 'lead', 'DONE', reply_to='t-0001', rev=1)
        self.crash_run('effect')
        self.assertEqual(self.jobs(), ['v-t-0001-r1-a1'])
        self.ok_run()
        self.assertEqual(self.jobs(), ['v-t-0001-r1-a1'])

    def test_killed_after_effect_letter(self):
        rid = self.handoff()
        self.crash_run('effect')
        self.assertEqual(len(self.all_mail('worker-1')), 1)
        self.ok_run()
        self.assertEqual(self.all_mail('worker-1'), ['mail-%s.e0.json' % rid])
        effects = self.record(rid)['effects']
        self.assertEqual([(e['do'], e['done']) for e in effects], [('letter', True)])

    def test_killed_after_job_submitted(self):
        self.working_ticket()
        self.letter('worker-1', 'lead', 'DONE', reply_to='t-0001', rev=1)
        self.crash_run('job-submitted')
        self.ok_run()
        self.assertEqual(self.jobs(), ['v-t-0001-r1-a1'])
        job = json.loads((self.lay.team / 'post' / ('jobs' if (self.lay.team / 'post' / 'jobs' / 'v-t-0001-r1-a1').exists()
                                                  else 'jobs-done') / 'v-t-0001-r1-a1' / 'job.json').read_text())
        self.assertEqual(job['tries'], 1)

    def test_ten_kills_in_a_row_still_one_delivery(self):
        """穩定：同一封信在每個窗口各崩一次，最後只投一封、紀錄完整。"""
        rid = self.handoff()
        for point in ('delivered', 'recorded', 'moved', 'effect'):
            r = self.cli('post', env={'AOS_TEAM_POST_CRASH': point})
            self.assertIn(r.returncode, (0, -9), r.stderr)
        self.pick_up('worker-1')
        self.ok_run()
        self.assertEqual(self.all_mail('worker-1'), ['mail-%s.e0.json' % rid])
        self.assertEqual(self.ticket()['status'], 'working')


if __name__ == '__main__':
    unittest.main()
