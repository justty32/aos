"""郵差兼書記（aos_team_post；spec/team/post.md）：投遞、退件、任務單後續動作、驗收工作、審查、崩潰窗口、看停滯、書記。"""
import datetime
import json
import os
from pathlib import Path
import shutil
import unittest

import aos_kernel_store
import aos_team_format as fmt
import aos_team_post as post
from _team_util import EXAMPLES, TeamCase


class DeliverTests(TeamCase):
    def test_letter_goes_to_input_sent_record_and_done(self):
        """驗收②：信進收件人 input/mail-<id>.json、post/sent/<id>.json 有紀錄、原檔進 outbox/done/。"""
        lid = self.letter('lead', 'worker-1', 'REQUEST', '先讀 IMPORT.md')
        self.assertEqual(self.post(), 0)
        self.assertEqual(self.inbox('worker-1'), ['mail-%s.json' % lid])
        body = self.mails('worker-1')[0][1]
        self.assertTrue(body.startswith('【來信 lead → worker-1 · REQUEST · '), body)
        self.assertIn('先讀 IMPORT.md', body)
        rec = self.record(lid)
        self.assertEqual((rec['from'], rec['to'], rec['status'], rec['kind']), ('lead', 'worker-1', 'REQUEST', 'letter'))
        self.assertTrue(rec['where'].endswith('input/mail-%s.json' % lid))
        self.assertTrue((self.lay.outbox('lead') / 'done' / (lid + '.json')).exists())
        self.assertFalse((self.lay.outbox('lead') / (lid + '.json')).exists())
        self.assertFalse(rec['complete'])                   # 還沒被收走
        self.pick_up('worker-1')
        self.post()
        rec = self.record(lid)
        self.assertTrue(rec['complete'] and rec['picked_up_at'])
        self.assertEqual(list((self.lay.team / 'post' / 'open').iterdir()), [])

    def test_letter_to_human_goes_to_human_inbox(self):
        lid = self.letter('worker-1', 'human', 'NEEDS-USER', '要你決定分支')
        self.post()
        got = self.human_mail()
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]['id'], lid)
        self.assertTrue(got[0]['header'].startswith('【來信 worker-1 → human · NEEDS-USER'), got[0]['header'])
        self.assertTrue(self.record(lid)['complete'])

    def test_run_twice_does_not_deliver_twice(self):
        lid = self.letter('lead', 'worker-1', 'REQUEST')
        self.post()
        self.pick_up('worker-1')
        (self.lay.outbox('lead') / 'done' / (lid + '.json')).rename(self.lay.outbox('lead') / (lid + '.json'))
        self.post()                                         # 原檔又出現（人搬回來）：紀錄在＝投過了
        self.assertEqual(self.inbox('worker-1'), [])
        self.assertEqual(len(list((self.lay.member('worker-1') / 'input' / 'done').iterdir())), 1)

    def test_letter_in_someone_elses_outbox_is_bounced(self):
        """驗收①：信放在別人的 outbox（from 寫 worker-1、放在 lead 的）＝身分不符，退件＋FAILED 給那格的主人。"""
        lid = self.letter('worker-1', 'lead', 'DONE', folder='lead')
        self.post()
        self.assertTrue(any(p.name == lid + '.json' for p in (self.lay.outbox('lead') / 'rejected').iterdir()))
        self.assertEqual(self.inbox('worker-1'), [])
        bounce = self.mails('lead')
        self.assertEqual(len(bounce), 1)
        self.assertIn('FAILED', bounce[0][1].split('\n')[0])
        self.assertIn('BadId', bounce[0][1])                # 檔名的寄件人段對不上 outbox（先驗檔名）

    def test_from_field_lies_is_not_sender(self):
        lid = self.new_id('lead')
        obj = {'id': lid, 'from': 'worker-1', 'to': 'lead', 'status': 'DONE', 'reply_to': None, 'rev': None,
               'text': '冒名', 'at': self.now.isoformat()}
        (self.lay.outbox('lead') / (lid + '.json')).write_text(json.dumps(obj), encoding='utf-8')
        self.post()
        rec = self.record(lid)
        self.assertEqual((rec['kind'], rec['code']), ('rejected', 'NotSender'))
        self.assertIn('NotSender', self.mails('lead')[0][1])

    def test_unknown_outbox_owner_bounces_to_human(self):
        box = self.lay.team / 'outbox' / 'ghost'
        box.mkdir()
        lid = '%d-1-ghost' % 1790000000000000000
        (box / (lid + '.json')).write_text('{}', encoding='utf-8')
        self.post()
        self.assertTrue((box / 'rejected' / (lid + '.json')).exists())
        self.assertIn('NotSender', self.human_mail()[0]['text'])

    def test_recipient_not_in_mail_to_rejected(self):
        lid = self.letter('worker-1', 'reviewer', 'PROGRESS')
        self.post()
        self.assertEqual(self.record(lid)['code'], 'BadRecipient')
        self.assertEqual(self.inbox('reviewer'), [])
        self.assertIn('BadRecipient', self.mails('worker-1')[0][1])

    def test_bad_status_and_json_rejected(self):
        a = self.letter('worker-1', 'lead', 'OK')
        box = self.lay.outbox('worker-1')
        b = self.new_id('worker-1')
        (box / (b + '.json')).write_text('{壞', encoding='utf-8')
        self.post()
        self.assertEqual(self.record(a)['code'], 'BadStatus')
        self.assertEqual(self.record(b)['code'], 'JsonSyntax')
        self.assertEqual(len(self.mails('worker-1')), 2)

    def test_temp_files_ignored(self):
        (self.lay.outbox('lead') / '.x.json.tmp').write_text('{}')
        (self.lay.outbox('lead') / '.hidden.json').write_text('{}')
        self.post()
        self.assertEqual(sorted(p.name for p in self.lay.outbox('lead').iterdir() if p.is_file()),
                         ['.hidden.json', '.x.json.tmp'])

    def test_recipient_without_home_rejected(self):
        shutil.rmtree(self.lay.member('reviewer'))
        lid = self.letter('lead', 'reviewer', 'REQUEST')
        self.post()
        self.assertEqual(self.record(lid)['code'], 'NoHome')

    def test_lock_busy_skips(self):
        import fcntl
        (self.lay.team / 'post').mkdir(exist_ok=True)
        with open(self.lay.team / 'post' / '.lock', 'a') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            self.letter('lead', 'worker-1', 'REQUEST')
            self.assertEqual(self.post(), 0)
        self.assertEqual(self.inbox('worker-1'), [])
        self.assertIn('郵差正在跑', self.lines[-1])

    def test_symlinked_done_folder_is_not_followed(self):
        """outbox 是模型寫得到的：rejected 被換成指到別人家的連結，郵差也不會搬過去蓋東西（astra M1）。"""
        victim = self.lay.member('lead') / 'state.json'
        before = victim.read_text()
        box = self.lay.outbox('worker-1')
        (box / 'rejected').rmdir()
        (box / 'rejected').symlink_to(self.lay.member('lead'))
        bad = self.new_id('worker-1')
        (box / 'state.json').write_text('{}')            # 名字不對的檔：會被退件、搬進 rejected
        (box / (bad + '.json')).write_text('{壞')
        self.post()
        self.assertEqual(victim.read_text(), before)
        self.assertTrue((box / 'rejected').is_dir() and not (box / 'rejected').is_symlink())
        self.assertTrue((box / 'rejected' / (bad + '.json')).exists())
        self.assertTrue((box / 'rejected' / 'state.json').exists())
        self.assertTrue(any(p.name.startswith('rejected.bad-') for p in box.iterdir()))

    def test_symlinked_letter_not_read(self):
        box = self.lay.outbox('worker-1')
        lid = self.new_id('worker-1')
        (box / (lid + '.json')).symlink_to(self.lay.member('lead') / 'state.json')
        self.post()
        self.assertEqual(self.record(lid)['code'], 'NotARegularFile')
        self.assertTrue((box / 'rejected' / (lid + '.json')).is_symlink())


class TaskFlowTests(TeamCase):
    def open_ticket(self, done_when=None):
        self.handoff(done_when)
        self.post()
        t = self.ticket()
        self.assertEqual(t['status'], 'sent')
        self.pick_up('worker-1')
        self.post()
        self.assertEqual(self.ticket()['status'], 'working')
        return t

    def done(self, rev=1):
        return self.letter('worker-1', 'lead', 'DONE', '做完了', reply_to='t-0001', rev=rev)

    def test_handoff_request_opens_and_dispatches(self):
        rid = self.handoff()
        self.post()
        t = self.ticket()
        self.assertEqual((t['status'], t['assignee']), ('sent', 'worker-1'))
        mail = self.mails('worker-1')
        self.assertEqual(mail[0][0], 'mail-%s.e0.json' % rid)
        self.assertIn('任務 t-0001（rev1，第 1/3 次）', mail[0][1])
        self.assertIn('【來信 post → worker-1 · REQUEST · t-0001 rev1', mail[0][1])
        self.assertEqual(self.record(rid)['kind'], 'request')

    def test_request_not_allowed_rejected(self):
        rid = self.handoff(sender='worker-1', assignee='lead')        # worker 模板的 may 沒有 handoff
        self.post()
        self.assertEqual(self.record(rid)['code'], 'NotAllowed')
        self.assertFalse(self.lay.task('t-0001').exists())

    def test_done_submits_verify_job_not_run_inline(self):
        """驗收④前半：DONE → verifying，提交一次性驗收工作（郵差裡不跑檢查器）。"""
        self.open_ticket()
        self.done()
        self.post()
        self.assertEqual(self.ticket()['status'], 'verifying')
        self.assertEqual([j for j, _ in self.submitted], ['v-t-0001-r1-a1'])
        argv = self.submitted[0][1]
        self.assertIn('verify', argv)
        self.assertEqual(argv[argv.index('--rev') + 1], '1')
        self.assertFalse((self.lay.team / 'post' / 'jobs' / 'v-t-0001-r1-a1' / 'result.json').exists())
        self.post()                                               # 沒結果：不重交、單子不動
        self.assertEqual(len(self.submitted), 1)
        self.assertEqual(self.ticket()['status'], 'verifying')

    def test_verify_fail_sends_fix_then_failed(self):
        """驗收④：不過＝工人收到「REQUEST 修正（第 2/3 次）＋逐條結果」；attempt 用完＝FAILED 給領隊與人。"""
        self.open_ticket()
        for attempt in (1, 2, 3):
            self.done()
            self.post()
            self.job_result('v-t-0001-r1-a%d' % attempt, False)
            self.post()
            if attempt < 3:
                t = self.ticket()
                self.assertEqual((t['status'], t['attempt']), ('sent', attempt + 1))   # queued → 修正信投到 → sent
                fix = self.mails('worker-1')[-1][1]
                self.assertIn('REQUEST 修正 t-0001（第 %d/3 次）' % (attempt + 1), fix)
                self.assertIn('不過 0. AGENTS.md 不在', fix)
                self.pick_up('worker-1')
                self.post()
        t = self.ticket()
        self.assertEqual(t['status'], 'failed')
        self.assertIn('FAILED', self.mails('lead')[-1][1].split('\n')[0])
        self.assertIn('3 次都沒過', self.mails('lead')[-1][1])
        self.assertEqual(self.human_mail()[-1]['status'], 'FAILED')
        self.assertEqual(len(self.submitted), 3)

    def test_verify_pass_done_notifies(self):
        self.open_ticket()
        self.done()
        self.post()
        self.job_result('v-t-0001-r1-a1', True)
        self.post()
        self.assertEqual(self.ticket()['status'], 'done')
        self.assertIn('完成', self.mails('lead')[-1][1])
        self.assertEqual(self.human_mail()[-1]['status'], 'DONE')
        self.assertTrue((self.lay.team / 'post' / 'jobs-done' / 'v-t-0001-r1-a1').is_dir())

    def kernel_job(self):
        kernel = self.tmp / 'K'
        (kernel / 'requests').mkdir(parents=True)
        (kernel / 'responses').mkdir()
        self.open_ticket()
        self.done()
        env = dict(os.environ, AOS_KERNEL_HOME=str(kernel))
        self.post(submit=None, env=env)
        jobdir = self.lay.team / 'post' / 'jobs' / 'v-t-0001-r1-a1'
        return kernel, env, jobdir

    def test_kernel_submit_crash_recovery(self):
        """崩在「記要起、真的放單」之間：kernel 收了＝不重放；沒收到＝用同一個單名重放（不多一次）。"""
        kernel, env, jobdir = self.kernel_job()
        job = json.loads((jobdir / 'job.json').read_text())
        run = job['runs'][0]
        self.assertEqual((run['mode'], run['state'], run['n']), ('kernel', 'running', 1))
        tag = post.team_tag(self.team)
        self.assertEqual(run['proc'], 'v-t-0001-r1-a1-%s-1' % tag)       # 帶團隊識別：別隊的 t-0001 不撞名
        req = kernel / 'requests' / run['request']
        body = json.loads(req.read_text())
        self.assertEqual((body['method'], body['params']['once'], body['params']['name']), ('add', True, run['proc']))
        run['state'] = 'starting'                          # 假裝崩在記下之前
        fmt.write_json(jobdir / 'job.json', job)
        self.post(submit=None, env=env)
        job = json.loads((jobdir / 'job.json').read_text())
        self.assertEqual([r['state'] for r in job['runs']], ['running'])
        req.unlink()                                       # kernel 沒收到（原單不見、也沒回音、帳本沒有）
        job['runs'][0]['state'] = 'starting'
        fmt.write_json(jobdir / 'job.json', job)
        self.post(submit=None, env=env)
        job = json.loads((jobdir / 'job.json').read_text())
        self.assertEqual(len(job['runs']), 1)
        self.assertTrue(req.exists())
        (kernel / 'responses' / run['request']).write_text('{}')   # 回音到了、結果也在 → 收、ack
        self.job_result('v-t-0001-r1-a1', True)
        self.post(submit=None, env=env)
        self.assertEqual(self.ticket()['status'], 'done')
        acks = [json.loads(p.read_text()) for p in (kernel / 'requests').glob('ack-*.json')]
        self.assertEqual([a['params']['name'] for a in acks], [run['request']])

    def test_retry_each_run_acked_separately(self):
        """第 1 次沒結果（回音到了）→ 簽收那一次、交第 2 次；第 2 次結果先到、回音還沒到＝等回音才收尾（ack 綁在那一次）。"""
        kernel, env, jobdir = self.kernel_job()
        job = json.loads((jobdir / 'job.json').read_text())
        r1 = job['runs'][0]
        (kernel / 'requests' / r1['request']).unlink()
        (kernel / 'responses' / r1['request']).write_text('{}')
        self.post(submit=None, env=env)
        job = json.loads((jobdir / 'job.json').read_text())
        self.assertEqual([r['state'] for r in job['runs']], ['ended', 'running'])
        r2 = job['runs'][1]
        self.assertNotEqual(r1['request'], r2['request'])
        (kernel / 'requests' / r2['request']).unlink()
        self.job_result('v-t-0001-r1-a1', True, run=2)
        aos_kernel_store.write(kernel, {'procs': {r2['proc']: {'status': 'running'}}})  # one-boot：K 帳本是 sqlite
        self.post(submit=None, env=env)
        self.assertEqual(self.ticket()['status'], 'done')
        self.assertTrue(jobdir.exists())                   # 第 2 次的回音還沒到：不收尾
        job = json.loads((jobdir / 'job.json').read_text())
        self.assertEqual([r['acked'] for r in job['runs']], [True, False])
        (kernel / 'responses' / r2['request']).write_text('{}')
        self.post(submit=None, env=env)
        self.assertFalse(jobdir.exists())
        acks = sorted(json.loads(p.read_text())['params']['name'] for p in (kernel / 'requests').glob('ack-*.json'))
        self.assertEqual(acks, sorted([r1['request'], r2['request']]))

    def test_bad_result_not_trusted(self):
        """結果檔的單號／rev／attempt 對不上、pass 不是布林：不收（改名 .bad），換下一次執行。"""
        self.open_ticket()
        self.done()
        self.post()
        self.job_result('v-t-0001-r1-a1', True, task='t-9999')
        self.post()
        self.assertEqual(self.ticket()['status'], 'verifying')
        jobdir = self.lay.team / 'post' / 'jobs' / 'v-t-0001-r1-a1'
        self.assertTrue((jobdir / 'result-1.json.bad').exists())
        self.assertEqual(len(self.submitted), 2)
        self.job_result('v-t-0001-r1-a1', 1, run=2)
        self.post()
        self.assertTrue((jobdir / 'result-2.json.bad').exists())
        self.job_result('v-t-0001-r1-a1', True, run=3)
        self.post()
        self.assertEqual(self.ticket()['status'], 'done')

    def test_complete_job_moved_after_crash(self):
        self.open_ticket()
        self.done()
        self.post()
        jobdir = self.lay.team / 'post' / 'jobs' / 'v-t-0001-r1-a1'
        job = json.loads((jobdir / 'job.json').read_text())
        job['complete'] = True                             # 崩在「記完成、搬走」之間
        fmt.write_json(jobdir / 'job.json', job)
        self.post()
        self.assertFalse(jobdir.exists())
        self.assertTrue((self.lay.team / 'post' / 'jobs-done' / 'v-t-0001-r1-a1').is_dir())

    def test_real_verify_command_result_is_collected(self):
        """真的跑 aos-team verify（就像 kernel 會跑的那一行），郵差下一輪收。"""
        self.open_ticket()
        (self.project / 'AGENTS.md').write_text('# x\n')
        self.done()
        self.post()
        argv = self.submitted[0][1]
        import subprocess
        r = subprocess.run(argv, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.post()
        self.assertEqual(self.ticket()['status'], 'done')

    def test_judge_opens_review_all_pass_done(self):
        """驗收⑤：有 judge 條目＝開審查子任務，逐條全 PASS 才 done。"""
        self.open_ticket([{'kind': 'file_exists', 'path': 'AGENTS.md'}, {'kind': 'judge', 'text': '原意沒變'},
                          {'kind': 'judge', 'text': '語氣白話'}])
        self.done()
        self.post()
        self.job_result('v-t-0001-r1-a1', True)
        self.post()
        self.assertEqual(self.ticket()['status'], 'reviewing')
        sub = self.ticket('t-0001.r1')
        self.assertEqual((sub['assignee'], sub['status']), ('reviewer', 'sent'))
        self.assertIn('審查單 t-0001.r1', self.mails('reviewer')[0][1])
        self.pick_up('reviewer')
        self.request('reviewer', 'review_result', task='t-0001.r1',
                     items=[{'i': 0, 'pass': True, 'why': '意思一樣'}, {'i': 1, 'pass': True, 'why': '白話'}])
        self.post()
        self.assertEqual(self.ticket()['status'], 'done')
        self.assertEqual(self.ticket('t-0001.r1')['status'], 'done')
        self.assertIn('審查通過', self.mails('lead')[-1][1])

    def test_judge_one_fail_goes_back_to_worker(self):
        self.open_ticket([{'kind': 'judge', 'text': '原意沒變'}, {'kind': 'judge', 'text': '語氣白話'}])
        self.done()
        self.post()
        self.assertEqual(self.ticket()['status'], 'reviewing')
        self.assertEqual(self.submitted, [])                    # 只有 judge：不用機械驗收
        self.request('reviewer', 'review_result', task='t-0001.r1',
                     items=[{'i': 0, 'pass': True, 'why': '一樣'}, {'i': 1, 'pass': False, 'why': '還是很硬'}])
        self.post()
        t = self.ticket()
        self.assertEqual(t['attempt'], 2)
        fix = self.mails('worker-1')[-1][1]
        self.assertIn('REQUEST 修正 t-0001（第 2/3 次）：審查沒過', fix)
        self.assertIn('不過 1. 還是很硬', fix)

    def test_review_result_partial_rejected(self):
        self.open_ticket([{'kind': 'judge', 'text': 'a'}, {'kind': 'judge', 'text': 'b'}])
        self.done()
        self.post()
        rid = self.request('reviewer', 'review_result', task='t-0001.r1', items=[{'i': 0, 'pass': True, 'why': 'x'}])
        self.post()
        self.assertEqual(self.record(rid)['code'], 'BadItems')
        self.assertIn('要逐條回', self.mails('reviewer')[-1][1])

    def test_no_reviewer_blocks(self):
        roster = json.loads((self.team / 'team.json').read_text())
        del roster['members']['reviewer']
        roster['members']['lead']['mail_to'] = ['worker-1', 'human']
        (self.team / 'team.json').write_text(json.dumps(roster))
        self.open_ticket([{'kind': 'judge', 'text': 'a'}])
        self.done()
        self.post()
        self.assertEqual(self.ticket()['status'], 'blocked')
        self.assertIn('沒有 template=reviewer', self.human_mail()[-1]['text'])

    def test_old_rev_report_ignored(self):
        self.open_ticket()
        self.done(rev=7)
        self.post()
        self.assertEqual(self.ticket()['status'], 'working')
        self.assertEqual(self.submitted, [])

    def test_ask_and_answer_round_trip(self):
        self.open_ticket()
        self.request('worker-1', 'ask', question='分支？', options=['main', '開分支'], reply_to='t-0001')
        self.post()
        self.assertEqual(self.ticket()['status'], 'waiting_user')
        self.request('human', 'answer', q='q-0001', text='main')
        self.post()
        self.assertIn(self.ticket()['status'], ('sent', 'working'))   # T1 下一版改成 working
        self.assertTrue(self.mails('worker-1')[-1][1].startswith('【人 → worker-1 · 回覆 q-0001'))

    def test_deadline_expire_fails_once(self):
        self.open_ticket()
        t = self.ticket()
        t['deadline'] = (self.now - datetime.timedelta(minutes=1)).isoformat()
        fmt.write_json(self.lay.task('t-0001'), t, indent=2)
        self.post()
        self.assertEqual(self.ticket()['status'], 'failed')
        n = len(self.human_mail())
        self.post()
        self.assertEqual(len(self.human_mail()), n)
        self.assertIn('超過期限', self.human_mail()[-1]['text'])


class WatchTests(TeamCase):
    def working(self):
        self.handoff()
        self.post()
        self.pick_up('worker-1')
        self.post()
        self.assertEqual(self.ticket()['status'], 'working')

    def stalls(self):
        return [m for m in self.mails('lead') if '觀察到停滯' in m[1]]

    def test_unhealthy_reported_once(self):
        """驗收⑥：卡在 think（健康不是 ok）只報一次 PROGRESS 給領隊與人。"""
        self.working()
        self.health['worker-1'] = ('retrying', '重試中（連敗 2/3）')
        self.post()                                            # 剛看到：還在寬限
        self.assertEqual(self.stalls(), [])
        self.now += datetime.timedelta(seconds=61)
        self.post()
        self.assertEqual(len(self.stalls()), 1)
        self.assertIn('健康不是 ok：重試中', self.stalls()[0][1])
        self.assertIn('PROGRESS', self.stalls()[0][1].split('\n')[0])
        self.assertEqual(len([m for m in self.human_mail() if '觀察到停滯' in m['text']]), 1)
        for _ in range(3):
            self.now += datetime.timedelta(minutes=5)
            self.post()
        self.assertEqual(len(self.stalls()), 1)
        self.assertEqual(self.inbox('worker-1'), [])          # 不替工人說話

    def test_idle_after_pickup_reported_once(self):
        """驗收⑥：收單後超過 stale_minutes 沒進展，只報一次；有進展之後又停住＝新的一次。"""
        self.working()
        self.now = datetime.datetime.now(post._zone('Asia/Taipei')).replace(microsecond=0)
        self.now += datetime.timedelta(minutes=9)
        self.post()
        self.assertEqual(self.stalls(), [])
        self.now += datetime.timedelta(minutes=2)
        self.post()
        self.post()
        self.assertEqual(len(self.stalls()), 1)
        self.assertIn('收了單', self.stalls()[0][1])
        history = self.lay.member('worker-1') / 'prompts' / 'history.json'
        history.write_text('[]')
        stamp = self.now.timestamp()
        os.utime(history, (stamp, stamp))                         # 記憶變長＝有進展
        self.post()
        self.assertEqual(len(self.stalls()), 1)
        self.now += datetime.timedelta(minutes=11)
        self.post()
        self.assertEqual(len(self.stalls()), 2)

    def test_waiting_on_others_not_reported(self):
        """驗收⑥：在等別人（blocked、waiting_user）不報。"""
        self.working()
        self.letter('worker-1', 'lead', 'BLOCKED', '缺 facts', reply_to='t-0001', rev=1)
        self.post()
        self.assertEqual(self.ticket()['status'], 'blocked')
        self.health['worker-1'] = ('paused', '連敗暫停')
        self.now += datetime.timedelta(hours=2)
        self.post()
        self.now += datetime.timedelta(hours=2)
        self.post()
        self.assertEqual(self.stalls(), [])

    def test_watch_throttled(self):
        self.working()
        self.health['worker-1'] = ('bad', '壞了')
        self.post(watch_every=30)
        self.now += datetime.timedelta(seconds=10)
        self.post(watch_every=30, health_grace=0)
        self.assertEqual(self.stalls(), [])
        self.now += datetime.timedelta(seconds=25)
        self.post(watch_every=30, health_grace=0)
        self.assertEqual(len(self.stalls()), 1)


SESSION = '''# SESSION-LOG — 進度（只列 open）

說明文字。

## 最新進度

（目前無）

## 各工作流 session-log

| 工作流 | session-log | open 摘要 |
|--------|-------------|----------|
'''
WAIT = '''# WAIT_USER — 等待使用者（只列 open）

## 待使用者項

（目前無）
'''


class ClerkTests(TeamCase):
    def setUp(self):
        super().setUp()
        (self.project / 'SESSION-LOG.md').write_text(SESSION, encoding='utf-8')
        (self.project / 'WAIT_USER.md').write_text(WAIT, encoding='utf-8')

    def block(self, name):
        """書記區塊裡的行（不含兩行標記）。"""
        text = (self.project / name).read_text(encoding='utf-8')
        body = text.split(post.BLOCK_BEGIN + '\n', 1)[1].split('\n' + post.BLOCK_END, 1)[0]
        return body.split('\n')

    def test_session_log_follows_tickets(self):
        self.handoff()
        self.post()
        lines = self.block('SESSION-LOG.md')
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith('- [t-0001 IMPORT.md] 已投、還沒收（worker-1，第 1/3 次）'), lines[0])
        text = (self.project / 'SESSION-LOG.md').read_text()
        self.assertNotIn('（目前無）\n' + post.BLOCK_BEGIN, text)       # 原本那行（目前無）被區塊換掉
        self.assertTrue(text.startswith(SESSION.split('（目前無）')[0]))     # 區塊外逐字不動
        self.assertTrue(text.endswith(SESSION.split('（目前無）')[1]))
        self.request('human', 'cancel', task='t-0001')
        self.post()
        self.assertEqual(self.block('SESSION-LOG.md'), ['（目前無）'])

    def test_wait_user_follows_questions(self):
        self.request('worker-1', 'ask', question='用哪個分支？\n# 不是標題', options=['main', '開分支'])
        self.post()
        lines = self.block('WAIT_USER.md')
        self.assertEqual(len(lines), 1)
        self.assertIn('[q-0001] worker-1 問：用哪個分支？ # 不是標題（選項：main / 開分支） → aos-team answer q-0001',
                      lines[0])
        self.request('human', 'answer', q='q-0001', text='main')
        self.post()
        self.assertEqual(self.block('WAIT_USER.md'), ['（目前無）'])

    def test_human_text_outside_block_untouched(self):
        """人寫的段落、空行、長得像書記的行，都在區塊外逐字留著（astra M9）。"""
        human = '- [dev] 人自己寫的 → 下一步\n\n- [t-0009 x] 人抄的舊單\n\n第二段'
        text = SESSION.replace('（目前無）', human)
        (self.project / 'SESSION-LOG.md').write_text(text, encoding='utf-8')
        self.handoff()
        self.post()
        out = (self.project / 'SESSION-LOG.md').read_text()
        self.assertIn(human, out)
        self.assertTrue(self.block('SESSION-LOG.md')[0].startswith('- [t-0001 '))
        before = os.stat(self.project / 'SESSION-LOG.md').st_mtime_ns
        self.letter('lead', 'worker-1', 'PROGRESS')          # 單子沒變：不重寫
        self.post()
        self.assertEqual(os.stat(self.project / 'SESSION-LOG.md').st_mtime_ns, before)

    def test_no_file_no_write(self):
        (self.project / 'SESSION-LOG.md').unlink()
        self.handoff()
        self.post()
        self.assertFalse((self.project / 'SESSION-LOG.md').exists())

    def test_non_invasive_wf_folder(self):
        (self.project / 'wf').mkdir()
        (self.project / 'SESSION-LOG.md').rename(self.project / 'wf' / 'SESSION-LOG.md')
        self.handoff()
        self.post()
        self.assertIn('- [t-0001 ', (self.project / 'wf' / 'SESSION-LOG.md').read_text())

    def test_update_section_heading_missing_and_code_fence(self):
        p = self.project / 'x.md'
        p.write_text('# 標題\n\n```\n## 最新進度\n```\n一段\n')
        self.assertTrue(post.update_section(p, '## 最新進度', ['- [t-0001 x] a']))
        self.assertEqual(p.read_text(), '# 標題\n\n```\n## 最新進度\n```\n一段\n\n## 最新進度\n\n%s\n- [t-0001 x] a\n%s\n'
                         % (post.BLOCK_BEGIN, post.BLOCK_END))
        self.assertFalse(post.update_section(p, '## 最新進度', ['- [t-0001 x] a']))
        self.assertTrue(post.update_section(p, '## 最新進度', []))
        self.assertIn('%s\n（目前無）\n%s' % (post.BLOCK_BEGIN, post.BLOCK_END), p.read_text())


class MailCommandTests(TeamCase):
    def test_mail_lists_one_line_per_letter(self):
        self.letter('lead', 'worker-1', 'REQUEST', '第一封\n第二行')
        self.letter('worker-1', 'human', 'PROGRESS', '進度')
        self.letter('worker-1', 'reviewer', 'DONE')
        self.post()
        r = self.cli('mail')
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.strip().split('\n')
        self.assertEqual(len(lines), 4, r.stdout)              # 兩封信＋一件退件＋退信
        self.assertIn('lead → worker-1  REQUEST  未收  第一封 第二行', lines[0])
        self.assertIn('worker-1 → 人  PROGRESS', lines[1])
        self.assertTrue(any('退件' in ln and 'BadRecipient' in ln for ln in lines))
        r = self.cli('mail', '--to', 'human', '--json')
        self.assertTrue(all(json.loads(ln)['to'] == 'human' for ln in r.stdout.strip().split('\n')))

    def test_mail_empty(self):
        r = self.cli('mail')
        self.assertEqual(r.returncode, 0)
        self.assertIn('還沒有信', r.stdout)

    def test_post_command_prints_what_it_did(self):
        self.letter('lead', 'worker-1', 'REQUEST')
        r = self.cli('post')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('投遞 ', r.stdout)
        self.assertIn('lead → worker-1  REQUEST', r.stdout)
        r = self.cli('post', '--quiet')
        self.assertEqual((r.returncode, r.stdout), (0, ''))

    def test_post_bad_roster_exit_1(self):
        (self.team / 'team.json').write_text('{壞')
        r = self.cli('post')
        self.assertEqual(r.returncode, 1)
        self.assertIn('aos-team: JsonSyntax', r.stderr)


if __name__ == '__main__':
    unittest.main()
