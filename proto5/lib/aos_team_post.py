"""郵差兼書記（spec/team/post.md）：kernel 反覆叫 `aos-team post`，每次走一輪，不叫模型。

一輪做的事（照順序）：
1. 接著做上一輪沒做完的紀錄（team/post/open/ 有標記的）：沒做完的後續動作、等收件人收走信。
2. 收驗收工作的結果（team/post/jobs/）：寫回任務單（verified 事件），照回的動作做。
3. 收 outbox：每個成員與 human 的 team/outbox/<名>/、心跳的 team/post/outbox/。
   一封信：驗 → 叫 on_letter → 投進收件人 input/mail-<id>.json（或人的 team/human/）→ 寫投遞紀錄
   post/sent/<id>.json（＝去重憑據，含要做的後續動作）→ 原檔搬進 done/ → 逐件做後續動作、做一件勾一件。
   一份申請：驗 → aos_team_requests.handle → 紀錄 → 搬 → 做動作。不合＝搬進 rejected/、退一封 FAILED。
4. 看停滯與期限（每 WATCH_EVERY 秒一次）。
5. 書記：任務表或問題有變就重寫專案 SESSION-LOG.md／WAIT_USER.md 的那一節。

崩在任何一步，重跑同一行收得回來：投之前先查「是不是已經投過、被收走了」，
處理函式同一個 src 回同一份動作，紀錄裡的動作做一件勾一件。
狀態機不在這裡：任務單只經 aos_team_task 的函式改（spec/team/tasks.md）。
"""
import argparse
import datetime
import fcntl
import glob
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

import aos_team_ask
import aos_team_format as fmt
from aos_team_format import HUMAN, POST, TeamError, Layout
import aos_team_requests
import aos_team_task

RECORD_TYPE = 'aos_team_post_record'
JOB_TYPE = 'aos_team_verify_job'
CRASH_ENV = 'AOS_TEAM_POST_CRASH'          # 測試用：到了這個點就 SIGKILL 自己（模擬崩在窗口裡）
KERNEL_ENV = 'AOS_KERNEL_HOME'
WATCH_EVERY = 30                           # 秒：看停滯、期限多久一次
HEALTH_GRACE = 60                          # 秒：健康不是 ok 要持續多久才報
JOB_TIMEOUT = 600                          # 秒：驗收工作多久沒結果算壞了
JOB_TRIES = 3                              # 驗收工作跑不起來最多試幾次
CLI_TEAM = Path(__file__).resolve().parent.parent / 'cli' / 'aos-team'
CLERK_FILES = (('SESSION-LOG.md', '## 最新進度'), ('WAIT_USER.md', '## 待使用者項'))
EMPTY_LINE = '（目前無）'


def crash(point):
    if point in (os.environ.get(CRASH_ENV) or '').split(','):
        os.kill(os.getpid(), signal.SIGKILL)


def _zone(tz):
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(tz) if tz else None
    except Exception:
        return None


def _mtime(path):
    try:
        return os.stat(path).st_mtime
    except OSError:
        return None


def _pid_alive(pid):
    try:
        with open('/proc/%d/stat' % pid) as f:
            return f.read().rsplit(')', 1)[1].split()[0] != 'Z'
    except (OSError, IndexError):
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


class Post:
    """一輪郵差。clock：回有時區的 datetime（測試可換）；submit：驗收工作怎麼提交（測試可換）；
    health：成員健康怎麼看（測試可換）。"""

    def __init__(self, team_dir, *, clock=None, env=None, submit=None, health=None, watch_every=WATCH_EVERY,
                 health_grace=HEALTH_GRACE, out=None):
        self.lay = Layout(team_dir)
        self.root = self.lay.root
        self.env = dict(os.environ if env is None else env)
        self.clock = clock or (lambda: datetime.datetime.now(datetime.timezone.utc))
        self.submitter = submit
        self.health_fn = health
        self.watch_every, self.health_grace = watch_every, health_grace
        self.out = out if out is not None else print
        base = self.lay.team / 'post'
        self.base = base
        self.sent, self.open_dir = self.lay.post_sent, base / 'open'
        self.jobs, self.jobs_done = base / 'jobs', base / 'jobs-done'
        self.sys_outbox = base / 'outbox'
        self.roster = None
        self.tz = None

    # ------------------------------------------------------------ 小工具 ----

    def now(self):
        return self.clock().astimezone(_zone(self.tz))

    def now_iso(self):
        return self.now().isoformat(timespec='seconds')

    def say(self, line):
        self.out(line)

    def warn(self, line):
        sys.stderr.write('aos-team post: %s\n' % line)

    # ------------------------------------------------------------ 一輪 ----

    def run(self):
        self.base.mkdir(parents=True, exist_ok=True)
        with open(self.base / '.lock', 'a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                self.say('郵差正在跑（另一個行程），這次略過')
                return 0
            self.roster = fmt.load_roster(self.root)
            self.tz = self.roster.get('tz')
            for d in (self.sent, self.open_dir, self.jobs, self.jobs_done, self.sys_outbox):
                d.mkdir(parents=True, exist_ok=True)
            self.resume_open()
            self.collect_jobs()
            self.process_outboxes()
            self.watch()
            self.clerk()
        return 0

    # --------------------------------------------------------- 投遞紀錄 ----

    def rec_path(self, rid):
        return self.sent / (rid + '.json')

    def load_rec(self, rid):
        path = self.rec_path(rid)
        if not path.exists():
            return None
        return fmt.read_json(path)

    def save_rec(self, rec):
        fmt.write_json(self.rec_path(rec['id']), rec)

    def mark_open(self, rid):
        (self.open_dir / rid).touch()

    def mark_closed(self, rid):
        (self.open_dir / rid).unlink(missing_ok=True)

    def new_rec(self, rid, kind, *, letter=None, effects=(), src=None, where=None, **extra):
        rec = {'_metainfo': {'_type': RECORD_TYPE, '_version': 1}, 'id': rid, 'kind': kind,
               'recorded_at': self.now_iso(), 'src': src, 'where': where,
               'watch_pickup': bool(letter) and letter['to'] != HUMAN and where is not None,
               'picked_up_at': None, 'effects': [], 'complete': False}
        if letter:
            rec.update({k: letter.get(k) for k in fmt.LETTER_KEYS if k != 'id'})
        rec.update(extra)
        add_effects(rec, effects)
        return rec

    def start_rec(self, rec):
        """先放標記、再寫紀錄：紀錄沒做完的時候標記一定在。"""
        self.mark_open(rec['id'])
        self.save_rec(rec)

    def resume_open(self):
        for mark in sorted(self.open_dir.iterdir()):
            if mark.name.startswith('.'):
                continue
            try:
                rec = self.load_rec(mark.name)
                if rec is None:        # 崩在「放標記、寫紀錄」之間：原檔還在 outbox，這輪會重做
                    mark.unlink(missing_ok=True)
                    continue
                self.finish(rec)
            except (TeamError, OSError, ValueError, KeyError) as e:
                self.warn('紀錄 %s 做不下去：%s（留著，下一輪再試）' % (mark.name, e))

    def finish(self, rec):
        """做完紀錄裡沒勾的動作；投給成員的信要等它被收走（叫 letter_picked_up）。都好了就關標記。"""
        self.advance(rec)
        if rec.get('watch_pickup') and rec.get('picked_up_at') is None:
            if not Path(rec['where']).exists():
                rec['picked_up_at'] = self.now_iso()
                if rec.get('dispatch'):            # 只有派工信推單子（sent → working）
                    add_effects(rec, aos_team_task.letter_picked_up(self.lay, rec_letter(rec), rec['dispatch']))
                self.save_rec(rec)
                self.advance(rec)
        if not rec['complete'] and all(e['done'] for e in rec['effects']) and \
                (not rec.get('watch_pickup') or rec.get('picked_up_at')):
            rec['complete'] = True
            self.save_rec(rec)
        if rec['complete']:
            self.mark_closed(rec['id'])

    def advance(self, rec, save=None):
        """逐件做紀錄裡的動作，做一件勾一件（勾之前崩了，重做同一件：每一件都冪等）。"""
        save = save or self.save_rec
        i = 0
        while i < len(rec['effects']):
            e = rec['effects'][i]
            if not e['done']:
                more, result, error = self.do_effect(e)
                crash('effect')
                e['done'] = True
                if result is not None:
                    e['result'] = result
                if error is not None:
                    e['error'] = error
                    self.warn('%s：%s' % (e['id'], error))
                    more = list(more) + [{'do': 'letter', 'to': HUMAN, 'status': 'FAILED', 'reply_to': None,
                                          'rev': None, 'text': '郵差做不到 %s（%s）：%s' % (e['id'], e['do'], error)}]
                add_effects(rec, more, prefix=rec['id'])
                save(rec)
            i += 1

    def do_effect(self, e):
        """回 (再多出來的動作, 結果, 錯誤)。"""
        try:
            kind = e.get('do')
            if kind == 'letter':
                letter ={'id': e['id'], 'from': e.get('from') or POST, 'to': e['to'], 'status': e['status'],
                          'reply_to': e.get('reply_to'), 'rev': e.get('rev'), 'text': trim(e['text']),
                          'at': self.now_iso()}
                return [], self.send(letter, src=e['id'].rsplit('.e', 1)[0], dispatch=e.get('dispatch')), None
            if kind == 'verify':
                return [], self.submit_verify(e['task'], e['rev'], e['attempt'], e['id']), None
            if kind == 'open_review':
                return aos_team_task.open_review(self.lay, self.roster, e['task'], e['id'], e['rev'], e['attempt']), None, None
            if kind == 'step':
                return aos_team_task.step(self.lay, e['task'], e['event']), None, None
            return [], None, '不認得的動作 %r' % kind
        except TeamError as err:
            if e.get('do') == 'letter' and e.get('to') == HUMAN:
                raise       # 連人的收件匣都寫不進去：這輪停，下一輪再試
            return [], None, '%s：%s' % (err.code, err.msg)

    # -------------------------------------------------------------- 投遞 ----

    def deliver(self, letter):
        """投一封信；回投到的路徑。已經投過（還在 input、已收進 done/、停在 intake）就不再投。"""
        to = letter['to']
        if to == HUMAN:
            self.lay.human_inbox.mkdir(parents=True, exist_ok=True)
            path = self.lay.human_inbox / (letter['id'] + '.json')
            fmt.write_new(path, dict(letter, header=fmt.render_header(letter, self.tz)))
            return str(path)
        home = self.lay.member(to)
        if not home.is_dir():
            raise TeamError('NoHome', '收件人 %s 的家 %s 還沒建（aos-team init）' % (to, home))
        inbox = home / 'input'
        name = fmt.mail_filename(letter['id'])
        if fmt.already_delivered(home, name) is None:      # 還在 input／已收進 done/／正在 intake：都算投過
            import aos_agent_say
            aos_agent_say.drop_new(inbox, name, fmt.mail_message(letter, self.tz))
        return str(inbox / name)

    def send(self, letter, src, dispatch=None):
        """郵差自己生的信（後續動作、退信、通知）：投＋紀錄（id＝動作 id，重跑不重投）。
        dispatch：派工信（spec/team/tasks.md）；投到、被收走時原樣交給 letter_delivered／letter_picked_up。"""
        rid = letter['id']
        rec = self.load_rec(rid)
        if rec is None:
            where = self.deliver(letter)
            crash('delivered')
            effects = aos_team_task.letter_delivered(self.lay, letter, dispatch) \
                if dispatch and letter['to'] != HUMAN else []
            rec = self.new_rec(rid, 'letter', letter=letter, effects=effects, src=src, where=where,
                               dispatch=dispatch)
            self.start_rec(rec)
            crash('recorded')
            self.say('投遞 %s  %s → %s  %s%s' % (rid, letter['from'], letter['to'], letter['status'],
                                              '  ' + ref_text(letter) if letter.get('reply_to') else ''))
        self.finish(rec)
        return rid

    # ------------------------------------------------------------ outbox ----

    def outbox_files(self):
        found = []
        top = self.lay.team / 'outbox'
        if top.is_dir():
            for d in sorted(top.iterdir()):
                if d.is_dir() and not d.name.startswith('.'):
                    found += [(d.name, p) for p in fmt.json_files(d)]
        found += [(POST, p) for p in fmt.json_files(self.sys_outbox)]

        def key(item):
            m = re.match(r'([0-9]+)-', item[1].name)
            return (int(m.group(1)) if m else float('inf'), item[1].name)
        return sorted(found, key=key)

    def process_outboxes(self):
        for sender, path in self.outbox_files():
            try:
                self.process_file(sender, path)
            except (TeamError, OSError, ValueError) as e:
                self.warn('%s 處理不下去：%s（留著，下一輪再試）' % (path, e))

    def record_id(self, sender, path):
        stem = path.name[:-5]
        if sender == POST:
            ok = fmt.ANY_ID.match(stem)
        else:
            m = fmt.OUTBOX_ID.match(stem)
            ok = m and m.group(1) == sender
        return stem if ok else 'x-' + hashlib.sha1(('%s/%s' % (sender, path.name)).encode()).hexdigest()[:20]

    def process_file(self, sender, path):
        rid = self.record_id(sender, path)
        rec = self.load_rec(rid)
        if rec is None:
            rec = self.take(sender, path, rid)
        archive(path, 'rejected' if rec['kind'] == 'rejected' else 'done')
        crash('moved')
        self.finish(rec)

    def take(self, sender, path, rid):
        """第一次看到這個檔：驗、叫處理函式、投；寫紀錄。回紀錄。"""
        try:
            if path.is_symlink() or not path.is_file():      # outbox 是模型寫得到的：不跟連結去讀別處
                raise TeamError('NotARegularFile', '%s 不是一般檔（符號連結或別的東西），不讀' % path.name)
            if sender == POST:
                kind, obj = 'letter', self.read_system_letter(path)
            else:
                kind, obj = fmt.read_outbox_file(path, self.roster)
            if kind == 'letter' and obj['to'] != HUMAN and not self.lay.member(obj['to']).is_dir():
                raise TeamError('NoHome', '收件人 %s 的家還沒建（aos-team init）' % obj['to'])
            if kind == 'request':
                try:
                    effects = aos_team_requests.handle(self.lay, self.roster, obj)
                except TeamError:
                    raise
                except Exception as e:     # 處理函式自己的 bug：退件，不要每輪卡在同一個檔
                    raise TeamError('InternalError', '處理 %s 申請出錯：%s: %s' % (obj['kind'], type(e).__name__, e))
        except TeamError as e:
            return self.reject(sender, path, rid, e.code, e.msg)
        if kind == 'request':
            rec = self.new_rec(rid, 'request', effects=effects, src=str(path), **{
                'from': obj['from'], 'request_kind': obj['kind'], 'at': obj.get('at')})
            self.start_rec(rec)
            self.say('申請 %s  %s %s' % (rid, obj['from'], obj['kind']))
            return rec
        effects = []
        if sender != POST:
            try:
                effects = aos_team_task.on_letter(self.lay, self.roster, obj)
            except TeamError as e:
                effects = [{'do': 'letter', 'to': HUMAN, 'status': 'FAILED', 'reply_to': obj['id'], 'rev': None,
                            'text': '郵差：信 %s 對單子 %s 處理失敗（%s：%s）；信照投。'
                                    % (obj['id'], obj.get('reply_to'), e.code, e.msg)}]
        where = self.deliver(obj)
        crash('delivered')
        rec =self.new_rec(rid, 'letter', letter=obj, effects=effects, src=str(path), where=where)
        self.start_rec(rec)
        crash('recorded')
        self.say('投遞 %s  %s → %s  %s%s' % (rid, obj['from'], obj['to'], obj['status'],
                                          '  ' + ref_text(obj) if obj.get('reply_to') else ''))
        return rec

    def read_system_letter(self, path):
        """team/post/outbox/ 的信（心跳寫的）：from 一定是 post，可以寄給任何成員或人。"""
        obj = fmt.validate_letter(fmt.read_json(path), str(path))
        if obj['id'] != path.name[:-5]:
            fmt.bad(str(path) + '.id', 'id 要跟檔名一樣', 'BadId')
        if obj['from'] != POST:
            fmt.bad(str(path) + '.from', 'team/post/outbox 的信 from 要是 post', 'NotSender')
        if obj['to'] != HUMAN and obj['to'] not in self.roster['members']:
            fmt.bad(str(path) + '.to', '%s 不在名冊裡' % obj['to'], 'BadRecipient')
        return obj

    def reject(self, sender, path, rid, code, msg):
        to = sender if sender == HUMAN or sender in self.roster['members'] else HUMAN
        stem = path.name[:-5]
        where = 'team/%s/rejected/%s' % ('post/outbox' if sender == POST else 'outbox/' + sender, path.name)
        effect = {'do': 'letter', 'to': to, 'status': 'FAILED',
                  'reply_to': stem if fmt.ANY_ID.match(stem) else None, 'rev': None,
                  'text': '退件（%s）：%s\n原檔搬到 %s' % (code, msg, where)}
        rec = self.new_rec(rid, 'rejected', effects=[effect], src=str(path), code=code, message=msg,
                           **{'from': sender})
        self.start_rec(rec)
        self.say('退件 %s  %s：%s' % (path.name, code, msg))
        return rec

    # ---------------------------------------------------------- 驗收工作 ----

    def job_dir(self, jid):
        return self.jobs / jid

    def save_job(self, job):
        fmt.write_json(self.job_dir(job['id']) / 'job.json', job)

    def submit_verify(self, tid, rev, attempt, src):
        """動作 verify：建一份驗收工作並提交第 1 次執行（不在這裡同步跑）。同一個 rev／attempt 只建一次。"""
        jid = 'v-%s-r%d-a%d' % (tid, rev, attempt)
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
            procs = json.loads((k / 'state.json').read_text(encoding='utf-8')).get('procs') or {}
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
            if res is not None:
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
                job.update(status='broken')
                add_effects(job, [{'do': 'letter', 'to': HUMAN, 'status': 'BLOCKED', 'reply_to': job['task'],
                                   'rev': job['rev'],
                                   'text': '%s 的驗收跑了 %d 次都沒結果（最後一次：%s；看 %s/err-*.log）。單子停在 verifying，'
                                           '要重來用 aos-team task reassign 或 cancel。'
                                           % (job['task'], len(job['runs']), job['runs'][-1].get('why'), d)}])
                self.save_job(job)
        self.advance(job, save=self.save_job)
        if not all(e['done'] for e in job['effects']):
            return
        if not self.settle_runs(job):
            return                                  # 還有 kernel 回音沒到：等它到了簽收再收尾
        job['complete'] = True
        self.save_job(job)
        os.replace(d, self.jobs_done / job['id'])

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

    # ------------------------------------------------------------ 停滯 ----

    def watch(self, force=False):
        path = self.base / 'watch.json'
        state = fmt.read_json(path) if path.exists() else {}
        now = self.now()
        last = fmt.parse_iso(state.get('last'))
        if not force and last is not None and (now - last).total_seconds() < self.watch_every:
            return
        for tid, ev in aos_team_task.due_deadlines(self.lay, now.isoformat(timespec='seconds')):
            self.notice('expire.%s.%s' % (tid, hashlib.sha1(ev['src'].encode()).hexdigest()[:10]),
                        [{'do': 'step', 'task': tid, 'event': ev}])
        tickets = aos_team_task.all_tickets(self.lay)
        health = state.get('health', {})
        seen = {}
        stale = self.roster['limits']['stale_minutes'] * 60
        for t in tickets:
            if t['status'] not in ('sent', 'working') or t.get('waiting_on'):
                continue            # 在等別人（blocked／waiting_user）、驗收審查中、結束了：不報
            m = t['assignee']
            if m not in seen:
                code, message = self.member_health(m)
                old = health.get(m) or {}
                # 連續不健康的起點：代碼換來換去（retrying → paused）也算同一段，回到 ok 才重算
                since = None if code == 'ok' else (old.get('since') or now.isoformat(timespec='seconds'))
                seen[m] = {'code': code, 'message': message, 'since': since}
            h = seen[m]
            if h['code'] != 'ok':
                if (now - fmt.parse_iso(h['since'])).total_seconds() >= self.health_grace:
                    key = '%s|%d|%d|health|%s' % (t['id'], t['rev'], t['attempt'], h['since'])
                    self.stall(t, key, '健康不是 ok：%s（從 %s 起）' % (h['message'], fmt.short_time(h['since'], self.tz)))
                continue
            progress = self.last_progress(t, m)
            if (now - progress).total_seconds() >= stale:
                key = '%s|%d|%d|idle|%s' % (t['id'], t['rev'], t['attempt'], progress.isoformat())
                self.stall(t, key, '%s 超過 %d 分鐘沒進展（最後進展 %s）'
                           % ('收了單' if t['status'] == 'working' else '單子投了還沒被收',
                              self.roster['limits']['stale_minutes'], fmt.short_time(progress.isoformat(), self.tz)))
        state = {'last': now.isoformat(timespec='seconds'), 'health': seen}
        fmt.write_json(path, state)

    def member_health(self, name):
        if self.health_fn is not None:
            return self.health_fn(name)
        try:
            import aos_agent_status
            data = aos_agent_status.collect(str(self.lay.member(name)), self.env)
            return data['health']['code'], data['health']['message']
        except Exception as e:
            return 'unreadable', '看不到 %s 的狀態：%s' % (name, e)

    def last_progress(self, t, m):
        """最後進展：單子最後一次變動、成員記憶最後一次變長、事件紀錄最後一次寫。"""
        stamps = [fmt.parse_iso(t.get('updated_at'))]
        home = self.lay.member(m)
        history = home / 'prompts' / 'history.json'
        try:
            h = json.loads((home / 'info.json').read_text(encoding='utf-8')).get('history')
            if isinstance(h, str):
                history = home / h
        except (OSError, ValueError, AttributeError):
            pass
        for p in (history, home / 'log' / 'events.jsonl', self.lay.events(m)):
            mt = _mtime(p)
            if mt is not None:
                stamps.append(datetime.datetime.fromtimestamp(mt, datetime.timezone.utc))
        stamps = [s if s.tzinfo else s.replace(tzinfo=datetime.timezone.utc) for s in stamps if s is not None]
        return max(stamps).astimezone(_zone(self.tz))

    def stall(self, t, key, why):
        """同一次停滯只報一次：紀錄 id 由停滯的鍵算出來，紀錄在＝報過了。"""
        rid = 'stall.%s.%s' % (t['id'], hashlib.sha1(key.encode()).hexdigest()[:12])
        text = '觀察到停滯：%s（%s，%s，rev%d 第 %d 次）%s。這只是觀察，不代表對方 BLOCKED。' % (
            t['id'], t['assignee'], t['status'], t['rev'], t['attempt'], why)
        to = [n for n in fmt.members_by_template(self.roster, 'lead') if n != t['assignee']] + [HUMAN]
        effects = [{'do': 'letter', 'to': n, 'status': 'PROGRESS', 'reply_to': t['id'], 'rev': t['rev'], 'text': text}
                   for n in to]
        if self.notice(rid, effects, key=key):
            self.say('停滯 %s %s：%s' % (t['id'], t['assignee'], why))

    def notice(self, rid, effects, **extra):
        """郵差自己起的事（停滯、期限）：紀錄在＝做過了。回這次有沒有新開。"""
        rec = self.load_rec(rid)
        new = rec is None
        if new:
            rec = self.new_rec(rid, 'notice', effects=effects, **extra)
            self.start_rec(rec)
        self.finish(rec)
        return new

    # ------------------------------------------------------------ 書記 ----

    def clerk(self, force=False):
        path = self.base / 'clerk.json'
        project = fmt.project_dir(self.root, self.roster)
        sig = [os.stat(p).st_mtime_ns if p.exists() else 0 for p in (self.lay.tasks, self.lay.wait_user)]
        sig.append(str(project))
        old = fmt.read_json(path) if path.exists() else {}
        if not force and old.get('sig') == sig:
            return
        tickets = [t for t in aos_team_task.all_tickets(self.lay) if t['status'] not in fmt.TERMINAL]
        questions = aos_team_ask.open_questions(self.lay)
        lines = {'SESSION-LOG.md': [session_line(t) for t in tickets],
                 'WAIT_USER.md': [wait_line(q) for q in questions]}
        for name, heading in CLERK_FILES:
            target = next((p for p in (project / name, project / 'wf' / name) if p.is_file()), None)
            if target is not None and update_section(target, heading, lines[name]):
                self.say('書記 %s：%d 條' % (target, len(lines[name])))
        fmt.write_json(path, {'sig': sig})


# ------------------------------------------------------------ 共用小函式 ----

def add_effects(rec, effects, prefix=None):
    """動作加上 id（<紀錄 id>.e<第幾個>，重跑算出來一樣）與 done。"""
    prefix = prefix or rec['id']
    for e in effects or []:
        e = {k: v for k, v in e.items() if k not in ('id', 'done', 'result', 'error')}
        e.update(id='%s.e%d' % (prefix, len(rec['effects'])), done=False)
        rec['effects'].append(e)


def team_tag(root):
    """團隊的穩定識別（資料夾真路徑的雜湊前 8 碼）：kernel 上的名字都帶它，不同團隊不撞名。"""
    return hashlib.sha1(os.path.realpath(str(root)).encode()).hexdigest()[:8]


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
            and isinstance(r.get('pass'), bool) for r in items):
        return 'results 每條要有整數 i 與 true／false 的 pass'
    if res['pass'] != all(r['pass'] for r in items):
        return 'pass 跟逐條結果對不上'
    return None


def archive(path, sub):
    """把 outbox 裡處理完的檔搬進同一格的 done/ 或 rejected/。outbox 是模型寫得到的地方：
    用資料夾的 fd 搬、不跟符號連結（done／rejected 被換成連結或檔＝先改名成 <名>.bad-<ns> 再建真的資料夾）。"""
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, 'O_NOFOLLOW', 0)
    box = os.open(str(path.parent), flags)
    try:
        try:
            os.mkdir(sub, dir_fd=box)
        except FileExistsError:
            pass
        try:
            dest = os.open(sub, flags, dir_fd=box)
        except OSError:
            os.rename(sub, '%s.bad-%d' % (sub, time.time_ns()), src_dir_fd=box, dst_dir_fd=box)
            os.mkdir(sub, dir_fd=box)
            dest = os.open(sub, flags, dir_fd=box)
        try:
            os.rename(path.name, path.name, src_dir_fd=box, dst_dir_fd=dest)
        except FileNotFoundError:
            pass                                  # 上一輪搬過了
        finally:
            os.close(dest)
    finally:
        os.close(box)


def rec_letter(rec):
    return {'id': rec['id'], 'from': rec.get('from'), 'to': rec.get('to'), 'status': rec.get('status'),
            'reply_to': rec.get('reply_to'), 'rev': rec.get('rev'), 'text': rec.get('text'), 'at': rec.get('at')}


def trim(text):
    text = text or '（空）'
    return text if len(text) <= fmt.TEXT_LIMIT else text[:fmt.TEXT_LIMIT - 20] + '\n…（太長，後面截掉）'


def ref_text(letter):
    return '%s%s' % (letter['reply_to'], ' rev%d' % letter['rev'] if letter.get('rev') else '')


STATUS_WORDS = {'queued': '等投遞', 'sent': '已投、還沒收', 'working': '做事中', 'verifying': '驗收中',
                'reviewing': '審查中', 'blocked': '卡住', 'waiting_user': '等人回答'}


def one_line(text, limit):
    """攤成一行（換行、連續空白變一格），太長截掉：插不進新標題、新清單。"""
    text = ' '.join(str(text or '').split())
    text = text[:limit] + ('…' if len(text) > limit else '')
    return text


def session_line(t):
    nxt = {'blocked': '等 %s 決定' % (t.get('waiting_on') or '開單人'),
           'waiting_user': '等人回答 %s' % (t.get('waiting_on') or ''),
           'verifying': '等驗收結果', 'reviewing': '等審查'}.get(t['status'], '等 %s 回報' % t['assignee'])
    return '- [%s %s] %s（%s，第 %d/%d 次）→ %s：%s' % (
        t['id'], one_line(t['workflow'], 40), STATUS_WORDS.get(t['status'], t['status']), t['assignee'],
        t['attempt'], t['max_attempts'], nxt, one_line(t['goal'], 80))


def wait_line(q):
    opts = '（選項：%s）' % ' / '.join(one_line(o, 30) for o in q['options']) if q.get('options') else ''
    ref = ' [%s]' % q['reply_to'] if q.get('reply_to') else ''
    return '- [%s] %s 問：%s%s%s → aos-team answer %s "…"' % (q['id'], q['from'], one_line(q['question'], 120),
                                                           opts, ref, q['id'])


BLOCK_BEGIN = '<!-- aos-team 書記：這一段自動產生，別手改 -->'
BLOCK_END = '<!-- /aos-team 書記 -->'


def _outside_fences(lines):
    """每一行在不在 ``` 程式碼區塊外。"""
    out, inside = [], False
    for ln in lines:
        fence = ln.lstrip().startswith('```')
        out.append(not inside and not fence)
        if fence:
            inside = not inside
    return out


def update_section(path, heading, managed_lines):
    """書記只改自己的區塊（BLOCK_BEGIN～BLOCK_END 之間），區塊外逐字不動。回有沒有改。

    沒有區塊：放在標題底下（那一節只有「（目前無）」就換掉它）；標題也沒有：加在檔尾。區塊空＝寫「（目前無）」。"""
    text = path.read_text(encoding='utf-8')
    lines = text.split('\n')
    ok = _outside_fences(lines)
    block = [BLOCK_BEGIN] + (list(managed_lines) or [EMPTY_LINE]) + [BLOCK_END]
    begin = next((i for i, ln in enumerate(lines) if ok[i] and ln.strip() == BLOCK_BEGIN), None)
    end = next((i for i, ln in enumerate(lines) if ok[i] and ln.strip() == BLOCK_END
                and begin is not None and i > begin), None)
    if begin is not None and end is not None:
        new = lines[:begin] + block + lines[end + 1:]
    else:
        start = next((i for i, ln in enumerate(lines) if ok[i] and ln.strip() == heading), None)
        if start is None:
            tail = lines[:-1] if lines and lines[-1] == '' else lines
            new = tail + ([''] if tail and tail[-1].strip() else []) + [heading, ''] + block + ['']
        else:
            stop = next((i for i in range(start + 1, len(lines)) if ok[i] and lines[i].startswith('#')), len(lines))
            body = [i for i in range(start + 1, stop) if lines[i].strip()]
            if len(body) == 1 and lines[body[0]].strip() == EMPTY_LINE:
                new = lines[:body[0]] + block + lines[body[0] + 1:]
            else:
                new = lines[:start + 1] + [''] + block + lines[start + 1:]
    out = '\n'.join(new)
    if out == text:
        return False
    tmp = path.with_name('.%s.%d.tmp' % (path.name, os.getpid()))
    tmp.write_text(out, encoding='utf-8')
    os.chmod(tmp, os.stat(path).st_mode & 0o7777)
    os.replace(tmp, path)
    return True


# --------------------------------------------------------------- 指令 ----

def cmd_post(team_dir, argv):
    p = argparse.ArgumentParser(prog='aos-team post', description='郵差走一輪（kernel 反覆叫它；人也可以手動跑）')
    p.add_argument('--quiet', action='store_true', help='不印做了什麼（kernel 用）')
    args = p.parse_args(argv)
    post = Post(team_dir, out=(lambda line: None) if args.quiet else None)
    return post.run()


def load_records(lay):
    out = []
    for path in fmt.json_files(lay.post_sent):
        try:
            rec = fmt.read_json(path)
        except TeamError:
            continue
        if isinstance(rec, dict) and rec.get('kind') in ('letter', 'rejected'):
            out.append(rec)
    return sorted(out, key=lambda r: (r.get('recorded_at') or '', r['id']))


def mail_line(rec, tz, full=False):
    when = fmt.short_time(rec.get('recorded_at'), tz)
    if rec['kind'] == 'rejected':
        return '%s  退件  %s 的 %s：%s' % (when, rec.get('from'), rec.get('src', '').rsplit('/', 1)[-1],
                                         '%s %s' % (rec.get('code'), rec.get('message')))
    sender = '人' if rec.get('from') == HUMAN else rec.get('from')
    to = '人' if rec.get('to') == HUMAN else rec.get('to')
    text = rec.get('text') or ''
    if not full:
        text = ' '.join(text.split())
        text = text[:60] + ('…' if len(text) > 60 else '')
    ref = '  %s' % ref_text(rec) if rec.get('reply_to') else ''
    got = '' if not rec.get('watch_pickup') else ('  ✓收' if rec.get('picked_up_at') else '  未收')
    return '%s  %s → %s  %s%s%s  %s' % (when, sender, to, rec.get('status'), ref, got, text)


def cmd_mail(team_dir, argv):
    p = argparse.ArgumentParser(prog='aos-team mail', description='一封信一行（郵差的投遞紀錄），照時間排')
    p.add_argument('--last', type=int, default=30, help='只看最後幾封（預設 30；0＝全部）')
    p.add_argument('--to', help='只看寄給誰的（human＝人）')
    p.add_argument('--from', dest='sender', help='只看誰寄的')
    p.add_argument('--task', help='只看回某張單的（t-0001）')
    p.add_argument('--full', action='store_true', help='印全文')
    p.add_argument('--json', action='store_true', help='一行一個 JSON 紀錄')
    p.add_argument('--follow', action='store_true', help='印完繼續等新的（Ctrl-C 停）')
    args = p.parse_args(argv)
    lay = Layout(team_dir)
    tz = fmt.load_roster(team_dir).get('tz')

    def pick(recs):
        return [r for r in recs if (not args.to or r.get('to') == args.to)
                and (not args.sender or r.get('from') == args.sender)
                and (not args.task or str(r.get('reply_to', '')).split('.r')[0] == args.task)]

    def show(recs):
        for r in recs:
            print(json.dumps(r, ensure_ascii=False) if args.json else mail_line(r, tz, args.full), flush=True)

    recs = pick(load_records(lay))
    if not recs and not args.follow:
        print('還沒有信（郵差沒投過任何一封）')
        return 0
    show(recs[-args.last:] if args.last else recs)
    if not args.follow:
        return 0
    seen = {r['id'] for r in recs}
    try:
        while True:
            time.sleep(1)
            new = [r for r in pick(load_records(lay)) if r['id'] not in seen]
            seen.update(r['id'] for r in new)
            show(new)
    except KeyboardInterrupt:
        return 0


# ------------------------------------------------------ kernel 登記 ----

def proc_name(team_dir, what):
    base = re.sub(r'[^A-Za-z0-9_-]', '-', Path(team_dir).resolve().name) or 'team'
    return 'team-%s-%s-%s' % (what, base, team_tag(team_dir))


def register(team_dir, what, argv, interval_ms, env=None):
    """把郵差／心跳登記成 kernel 的反覆工作（等於 aos-kernel add inst --name … --interval-ms …）。"""
    import aos_client
    env = os.environ if env is None else env
    kernel = env.get(KERNEL_ENV)
    if not kernel or not os.path.isabs(kernel):
        sys.stderr.write('aos-team: Usage: 要設 %s（kernel 家的絕對路徑）\n' % KERNEL_ENV)
        return 1
    lay = Layout(team_dir)
    folder = lay.team / 'post'
    folder.mkdir(parents=True, exist_ok=True)
    inst = folder / ('%s.inst.json' % what)
    fmt.write_json(inst, {'_metainfo': {'_type': 'posix', '_version': 1},
                          'argv': [sys.executable, str(CLI_TEAM)] + argv + ['--target', str(lay.root)],
                          'cwd': str(lay.root), 'envs': {KERNEL_ENV: kernel},
                          'stderr': {'$opt': ['append', 'mkdir'], '$val': str(folder / ('%s.err' % what))}},
                   indent=2)
    name = proc_name(team_dir, what)
    params = {'target': str(inst), 'name': name}
    if interval_ms:
        params['interval_ms'] = interval_ms
    res = aos_client.call(kernel, 'add', params, client='team', timeout_ms=10000)
    if 'error' in res:
        code = (res['error'].get('data') or {}).get('code')
        if code == 'AlreadyExists':
            try:
                proc = (json.loads((Path(kernel) / 'state.json').read_text(encoding='utf-8')).get('procs') or {}).get(name)
            except (OSError, ValueError, AttributeError):
                proc = None
            if isinstance(proc, dict) and proc.get('target') == str(inst) and proc.get('status') != 'bad':
                print('already started %s' % name)
                return 0
            sys.stderr.write('aos-team: AlreadyExists: kernel 裡的 %s 不是這個團隊的（或被判 bad）：%s\n'
                             % (name, (proc or {}).get('target') if isinstance(proc, dict) else proc))
            return 1
        sys.stderr.write('aos-team: %s: %s\n' % (code or res['error'].get('code'), res['error'].get('message')))
        return 1
    print('started %s' % name)
    return 0


def unregister(team_dir, what, env=None):
    import aos_client
    env = os.environ if env is None else env
    kernel = env.get(KERNEL_ENV)
    if not kernel or not os.path.isabs(kernel):
        sys.stderr.write('aos-team: Usage: 要設 %s\n' % KERNEL_ENV)
        return 1
    name = proc_name(team_dir, what)
    res = aos_client.call(kernel, 'rm', {'name': name}, client='team', timeout_ms=10000)
    if 'error' in res and (res['error'].get('data') or {}).get('code') != 'NotFound':
        sys.stderr.write('aos-team: %s\n' % res['error'].get('message'))
        return 1
    print('stopped %s' % name)
    return 0


def start(team_dir, env=None, interval_ms=1000):
    """aos-team start 的掛勾（spec/team/cli.md）：郵差每 interval_ms 走一輪。"""
    return register(team_dir, 'post', ['post', '--quiet'], interval_ms, env)


def stop(team_dir, env=None):
    return unregister(team_dir, 'post', env)
