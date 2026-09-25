"""郵差的驗收工作：`_PostJobs`（混入 Post）交驗收、起 kernel 工作、收結果；結果檔格式檢查；申請 reverify。"""
import hashlib
import os
from pathlib import Path
import signal
import subprocess
import sys

import aos_kernel_store
import aos_team_format as fmt
from aos_team_format import HUMAN, TeamError
import aos_team_task

from aos_team_post_base import (
    _pid_alive, add_effects, CLI_TEAM, crash, JOB_TIMEOUT, JOB_TRIES, JOB_TYPE, KERNEL_ENV,
    team_tag
)


class _PostJobs:
    """Post 的驗收工作那幾格（混入 Post）：交驗收、起 kernel 工作、收結果、檢查器壞、收尾。"""

    # ---------------------------------------------------------- 驗收工作 ----

    def job_dir(self, jid):
        return self.jobs / jid

    def save_job(self, job):
        fmt.write_json(self.job_dir(job['id']) / 'job.json', job)

    def submit_verify(self, tid, rev, attempt, src, again=None):
        """動作 verify：建一份驗收工作並提交第 1 次執行（不在這裡同步跑）。同一個 rev／attempt 只建一次；
        again＝人修好檢查器後的 reverify 申請 id：同一個 rev／attempt 另建一份（id 多一段），不算新的一次交件。"""
        jid = 'v-%s-r%d-a%d' % (tid, rev, attempt)
        if again:
            jid += '-x' + hashlib.sha1(again.encode()).hexdigest()[:8]
        d = self.job_dir(jid)
        if d.exists() or (self.jobs_done / jid).exists():
            return jid
        tmp = self.jobs / ('.%s.tmp' % jid)
        tmp.mkdir(parents=True, exist_ok=True)
        job = {'_metainfo': {'_type': JOB_TYPE, '_version': 1}, 'id': jid, 'task': tid, 'rev': rev,
               'attempt': attempt, 'src': src, 'status': 'open', 'runs': [], 'created_at': self.now_iso(),
               'effects': [], 'complete': False}
        fmt.write_json(tmp / 'job.json', job)
        os.rename(tmp, d)
        if again:                                  # 重驗的工作建好了才拿掉「等人修」標記（期限改看這份工作）
            (self.base / 'checker-broken' / tid).unlink(missing_ok=True)
        self.launch(job)
        return jid

    def run_names(self, job, run):
        """kernel 的單名與行程名：帶團隊識別（同一個 kernel 上別隊的 t-0001 不會撞名）與第幾次執行。"""
        tag = team_tag(self.root)
        return 'post-%s-%s-%d.json' % (tag, job['id'], run['n']), '%s-%s-%d' % (job['id'], tag, run['n'])

    def launch(self, job):
        """提交一次新的執行（第 n 次；結果寫 result-<n>.json，每次各寫各的檔）。
        有 kernel（AOS_KERNEL_HOME）＝aos-kernel add --once；沒有＝另開一個行程（不等它）。"""
        d = self.job_dir(job['id'])
        run = {'n': len(job['runs']) + 1, 'state': 'starting', 'started_at': self.now_iso(), 'acked': False}
        argv = [sys.executable, str(CLI_TEAM), 'verify', job['task'], '--rev', str(job['rev']),
                '--attempt', str(job['attempt']), '--out', str(d / ('result-%d.json' % run['n'])),
                '--target', str(self.root)]
        kernel = self.env.get(KERNEL_ENV)
        if self.submitter is not None:
            run['mode'] = 'test'
        elif kernel and os.path.isabs(kernel) and os.path.isdir(kernel):
            fmt.write_json(d / ('inst-%d.json' % run['n']),
                           {'argv': argv, 'cwd': str(self.root), 'stdout': 'out-%d.log' % run['n'],
                            'stderr': 'err-%d.log' % run['n']})
            run.update(mode='kernel', kernel=kernel)
            run['request'], run['proc'] = self.run_names(job, run)
        else:
            run['mode'] = 'spawn'
        job['runs'].append(run)
        self.save_job(job)                       # 先記「要起這一次」，再真的起
        self.start_run(job, run, argv)

    def start_run(self, job, run, argv=None):
        d = self.job_dir(job['id'])
        if run['mode'] == 'test':
            self.submitter(job, argv)
        elif run['mode'] == 'kernel':
            import aos_client
            import aos_home
            try:
                aos_client.submit(run['kernel'], 'add', {'target': str(d / ('inst-%d.json' % run['n'])), 'once': True,
                                                         'name': run['proc']}, name=run['request'])
            except aos_home.RequestExists:
                pass
        else:
            with open(d / ('out-%d.log' % run['n']), 'ab') as o, open(d / ('err-%d.log' % run['n']), 'ab') as e:
                proc = subprocess.Popen(argv, cwd=str(self.root), stdin=subprocess.DEVNULL, stdout=o, stderr=e,
                                        start_new_session=True)
            run['pid'] = proc.pid
        run['state'] = 'running'
        self.save_job(job)
        crash('job-submitted')
        self.say('驗收 %s rev%d 第 %d 次：提交第 %d 次執行（%s）'
                 % (job['task'], job['rev'], job['attempt'], run['n'], run['mode']))

    def kernel_has(self, run):
        """這次執行 kernel 還記得嗎：原單還在 requests/、回音在 responses/、或帳本有這個行程。"""
        k = Path(run['kernel'])
        if (k / 'requests' / run['request']).exists() or (k / 'responses' / run['request']).exists():
            return True
        try:
            procs = aos_kernel_store.peek_procs(k)  # one-boot（P 隊）：帳本換成 K/ledger.sqlite
        except (OSError, ValueError, AttributeError):
            return False
        return run['proc'] in procs

    def collect_jobs(self):
        for d in sorted(self.jobs.iterdir()):
            if d.name.startswith('.') or not d.is_dir():
                continue
            try:
                self.collect_job(fmt.read_json(d / 'job.json'))
            except (TeamError, OSError, ValueError, KeyError) as e:
                self.warn('驗收工作 %s 收不下去：%s（留著，下一輪再試）' % (d.name, e))

    def read_result(self, job, run):
        """讀第 n 次執行的結果檔：沒有＝None；有但身分或格式不對＝改名成 .bad、回 False。"""
        path = self.job_dir(job['id']) / ('result-%d.json' % run['n'])
        if not path.exists():
            return None
        try:
            res = fmt.read_json(path)
            why = check_result(res, job)
        except TeamError as e:
            why = e.msg
        if why:
            self.warn('驗收工作 %s 第 %d 次的結果不對（%s），不收' % (job['id'], run['n'], why))
            os.replace(path, path.with_name(path.name + '.bad'))
            return False
        return res

    def collect_job(self, job):
        d = self.job_dir(job['id'])
        if job.get('complete'):                     # 崩在「記完成、搬進 jobs-done/」之間
            os.replace(d, self.jobs_done / job['id'])
            return
        for run in job['runs']:
            if run['state'] == 'starting':          # 崩在「記要起、真的起」之間
                if run['mode'] == 'kernel' and not self.kernel_has(run):
                    self.start_run(job, run)
                elif run['mode'] in ('kernel', 'test'):
                    run['state'] = 'running'
                    self.save_job(job)
                else:                               # 另開的行程起了沒不知道：當它丟了，照樣看它的結果檔
                    run['state'] = 'lost'
                    self.save_job(job)
        if job['status'] == 'open':
            res = None
            for run in job['runs']:
                got = self.read_result(job, run)
                if got is False:
                    run['state'] = 'ended'
                elif got is not None:
                    res, run['state'] = got, 'ended'
                    break
            if res is not None and res['broken']:
                self.checker_broken(job, [r for r in res['results'] if r['result'] == 'error'])
            elif res is not None:
                ev = {'type': 'verified', 'src': 'verify:%s' % job['id'], 'pass': res['pass'],
                      'results': res['results'], 'rev': job['rev'], 'attempt': job['attempt']}
                effects = aos_team_task.step(self.lay, job['task'], ev)
                job.update(status='collected', passed=res['pass'], collected_at=self.now_iso())
                add_effects(job, effects)
                self.save_job(job)
                ok = sum(1 for r in res['results'] if r['pass'])
                self.say('驗收 %s rev%d 第 %d 次：%s（%d/%d 條過）' % (job['task'], job['rev'], job['attempt'],
                                                              '過' if res['pass'] else '不過', ok, len(res['results'])))
            else:
                for run in job['runs']:
                    why = self.run_gone(run)
                    if why:
                        run.update(state='ended', why=why)
                if any(r['state'] in ('starting', 'running') for r in job['runs']):
                    self.save_job(job)
                    return
                if len(job['runs']) < JOB_TRIES:
                    self.warn('驗收工作 %s 沒結果（%s），再交一次' % (job['id'], job['runs'][-1].get('why')))
                    self.launch(job)
                    return
                self.checker_broken(job, [{'i': '-', 'why': '驗收跑了 %d 次都沒結果（最後一次：%s；看 %s/err-*.log）'
                                                  % (len(job['runs']), job['runs'][-1].get('why'), d)}])
        self.advance(job, save=self.save_job)
        if not all(e['done'] for e in job['effects']):
            return
        if not self.settle_runs(job):
            return                                  # 還有 kernel 回音沒到：等它到了簽收再收尾
        job['complete'] = True
        self.save_job(job)
        os.replace(d, self.jobs_done / job['id'])

    def checker_broken(self, job, errors):
        """檢查器壞了（不是隊員沒過）：不送 verified、不扣次數；寄 BLOCKED 給人，單子停在 verifying 等人修。"""
        lines = '\n'.join('  %s. %s' % (r.get('i', '?'), r.get('why')) for r in errors)
        try:
            t = aos_team_task.load(self.lay, job['task'])
        except TeamError:
            t = None
        if t is None or (t['status'], t['rev'], t['attempt']) != ('verifying', job['rev'], job['attempt']):
            job.update(status='broken', stale=True)  # 過期的結果（單子已改派、取消、別份驗收先回來）：只記、不寄
            self.save_job(job)
            self.say('驗收 %s rev%d 第 %d 次：檢查器壞了，但單子已經不在等這一次，不寄' % (job['task'], job['rev'], job['attempt']))
            return
        mark = self.base / 'checker-broken'
        mark.mkdir(exist_ok=True)
        (mark / job['task']).write_text('%d %d\n' % (job['rev'], job['attempt']))   # 看期限時略過它（等人修）
        job.update(status='broken')
        add_effects(job, [{'do': 'letter', 'to': HUMAN, 'status': 'BLOCKED', 'reply_to': job['task'], 'rev': job['rev'],
                           'text': '%s 的驗收：檢查器壞了（不是隊員交的東西沒過，不扣次數）。單子停在 verifying 等你修：\n%s\n'
                                   '修好後：aos-team verify %s --again（重交同一次驗收）；不修就 aos-team task cancel／reassign。'
                                   % (job['task'], lines, job['task'])}])
        self.save_job(job)
        self.say('驗收 %s rev%d 第 %d 次：檢查器壞了，寄給人' % (job['task'], job['rev'], job['attempt']))

    def run_gone(self, run):
        """還在跑的那次執行結束了沒（沒寫結果）：回原因或 None。逾時的另開行程會被整組砍掉。"""
        if run['state'] not in ('running', 'lost'):
            return None
        if run['mode'] == 'kernel' and (Path(run['kernel']) / 'responses' / run['request']).exists():
            return 'kernel 回音到了但沒寫結果檔'
        if run['mode'] == 'kernel' and not self.kernel_has(run):
            return 'kernel 已經不記得這次執行'
        if run['mode'] == 'spawn' and run.get('pid') and not _pid_alive(run['pid']):
            return '行程 %d 結束了但沒寫結果檔' % run['pid']
        if run['state'] == 'lost':
            return '起到一半崩了，不確定有沒有起'
        start = fmt.parse_iso(run.get('started_at'))
        if start is None or (self.now() - start).total_seconds() > JOB_TIMEOUT:
            if run['mode'] == 'spawn' and run.get('pid'):
                try:
                    os.killpg(run['pid'], signal.SIGKILL)
                except OSError:
                    pass
            return '超過 %d 秒' % JOB_TIMEOUT
        return None

    def settle_runs(self, job):
        """每一次 kernel 執行的回音都要簽收（綁在那一次上）。回「都結清了」。
        回音還沒到、kernel 也還記得這次執行＝還沒結清；kernel 已經不記得＝沒東西可簽。"""
        import aos_client
        done = True
        for run in job['runs']:
            if run['mode'] != 'kernel' or run.get('acked'):
                continue
            if (Path(run['kernel']) / 'responses' / run['request']).exists():
                aos_client.ack(run['kernel'], run['request'])
                run['acked'] = True
                self.save_job(job)
            elif self.kernel_has(run):
                done = False
        return done


def check_result(res, job):
    """驗收結果檔的身分與格式：回錯在哪（白話）或 None。"""
    if not isinstance(res, dict):
        return '不是 JSON 物件'
    for key in ('task', 'rev', 'attempt'):
        if res.get(key) != job[key]:
            return '%s 是 %r，這份工作是 %r' % (key, res.get(key), job[key])
    if not isinstance(res.get('pass'), bool):
        return 'pass 要是 true／false'
    items = res.get('results')
    if not isinstance(items, list) or not all(
            isinstance(r, dict) and isinstance(r.get('i'), int) and not isinstance(r.get('i'), bool)
            and isinstance(r.get('pass'), bool) and r.get('result') in ('pass', 'fail', 'error')
            and r['pass'] == (r['result'] == 'pass') for r in items):
        return 'results 每條要有整數 i、result（pass／fail／error）與跟它一致的 pass'
    if res['pass'] != all(r['pass'] for r in items):
        return 'pass 跟逐條結果對不上'
    if not isinstance(res.get('broken'), bool) or res['broken'] != any(r['result'] == 'error' for r in items):
        return 'broken 要是 true／false，而且等於「有一條檢查器壞」'
    return None


def on_reverify(lay, roster, req):
    """申請 kind=reverify（只有人）：檢查器修好了，替停在 verifying 的單重交同一次驗收（不扣次數）。
    冪等：同一份申請回同一份動作；郵差照申請 id 另建一份工作（同一份申請只建一次）。"""
    import aos_team_format as f
    if req['from'] != HUMAN:
        raise TeamError('NotAllowed', '只有人能要求重交驗收')
    extra = sorted(set(req) - set(f.REQUEST_COMMON) - {'task'})
    if extra:
        f.bad('request', '不認得的欄位 %s（reverify 只收 task）' % '、'.join(extra))
    tid = req.get('task')
    if not isinstance(tid, str) or not f.TASK_ID.match(tid):
        f.bad('request.task', '%r 不是任務單號' % (tid,))
    t = aos_team_task.load(lay, tid)
    if t['status'] != 'verifying':
        raise TeamError('NotVerifying', '%s 現在是 %s，不是停在 verifying' % (tid, t['status']))
    prefix = 'v-%s-r%d-a%d' % (tid, t['rev'], t['attempt'])
    jobs = lay.team / 'post' / 'jobs'
    for d in (jobs.iterdir() if jobs.is_dir() else []):
        if d.name.startswith(prefix) and d.is_dir() and not d.name.endswith('-x' + hashlib.sha1(req['id'].encode()).hexdigest()[:8]):
            try:
                busy = fmt.read_json(d / 'job.json').get('status') == 'open'
            except TeamError:
                busy = True
            if busy:
                raise TeamError('Busy', '%s 這一次的驗收（%s）還在跑，等它回來再說' % (tid, d.name))
    return [{'do': 'verify', 'task': tid, 'rev': t['rev'], 'attempt': t['attempt'], 'again': req['id']}]
