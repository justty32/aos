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
這個檔留 Post 本體（一輪、投遞紀錄、投遞、outbox）、指令與 kernel 登記；驗收工作與停滯／書記兩段是混入類別，
其餘分在 aos_team_post_base／recheck／text／jobs／watch，這裡匯出外部用到的名字。
"""
import argparse
import datetime
import fcntl
import hashlib
import os
from pathlib import Path
import re
import sys

import aos_kernel_store
import aos_team_format as fmt
from aos_team_format import BEAT, HUMAN, POST, TeamError, Layout
import aos_team_requests
import aos_team_task

from aos_team_post_base import (
    _zone, add_effects, archive, CLI_TEAM, crash, CRASH_ENV, HEALTH_GRACE, JOB_TIMEOUT, KERNEL_ENV,
    RECORD_TYPE, team_tag, WATCH_EVERY
)
from aos_team_post_recheck import recheck
from aos_team_post_text import BLOCK_BEGIN, BLOCK_END, rec_letter, ref_text, trim, update_section
from aos_team_post_jobs import _PostJobs, check_result, on_reverify
from aos_team_post_watch import _PostWatch


class Post(_PostJobs, _PostWatch):
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
            import aos_team_commons            # 09-25 commons：圖書館員端審投稿、投稿端收結果（commons.md）
            aos_team_commons.post_round(self)
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
                return [], self.submit_verify(e['task'], e['rev'], e['attempt'], e['id'], e.get('again')), None
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
        if to == BEAT:
            return None                   # 心跳不收信（它看任務單）：只留投遞紀錄，aos-team mail 看得到
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
        self.budget = None                       # 這一輪的預算判斷（第一次碰到新 handoff／spawn 才算）
        for sender, path in self.outbox_files():
            try:
                self.process_file(sender, path, over=self.budget_hold(sender, path))
            except (TeamError, OSError, ValueError) as e:
                self.warn('%s 處理不下去：%s（留著，下一輪再試）' % (path, e))

    def budget_hold(self, sender, path):
        """財務部（spec/team/cost.md §4）：超預算時新的 handoff／spawn 申請**退件**——回傳退件理由（開頭
        「財務擋單：超支」），process_file 照一般退件走：原檔進 rejected/、FAILED 退給寄件人（human 寄的＝總機單，
        總機會把 FAILED 轉回下單的部門）。09-25 五家真跑 §7 第 5 條：以前是留在 outbox 等預算調高，
        但發單的人（總裁）永遠收不到回音、董事的單永遠不結案。每天每種超額另寄一封 NEEDS-USER 給 human。
        已處理過的（有紀錄）照走；沒設 AOS_COST_HOME＝不擋。不擋＝None。"""
        import aos_team_cost
        if sender == POST or aos_team_cost.home(self.env) is None:
            return None
        if self.load_rec(self.record_id(sender, path)) is not None:
            return None
        try:
            obj = fmt.read_json(path)
        except (TeamError, OSError, ValueError):
            return None
        if not isinstance(obj, dict) or obj.get('kind') not in aos_team_cost.HOLD_KINDS:
            return None
        if self.budget is None:
            self.budget = aos_team_cost.hold_reason(self.env, str(self.root)) or False
        if not self.budget:
            return None
        why, sig = self.budget
        day = self.now().strftime('%Y%m%d')
        rid = 'budget.%s.%s' % (day, hashlib.sha1(sig.encode()).hexdigest()[:12])
        text = ('財務：超預算，郵差把新的開單／生成員申請退件（FAILED 回給寄件人，已在跑的單照常）：%s。'
                '要繼續就調高預算（$AOS_COST_HOME/budget.json 或 team.json 的 budget），再重新開單；'
                'aos-team cost budget 看幾成。' % why)
        if self.notice(rid, [{'do': 'letter', 'to': HUMAN, 'status': 'NEEDS-USER', 'reply_to': None, 'rev': None,
                              'text': text}], reason=sig):
            self.say('財務：超預算，%s 的 %s 申請退件：%s' % (sender, obj.get('kind'), why))
        return ('財務擋單：超支（%s）。這張%s申請沒有處理；預算調高後要做就重新開單。'
                % (why, '開單' if obj.get('kind') == 'handoff' else '生成員'))

    def record_id(self, sender, path):
        stem = path.name[:-5]
        if sender == POST:
            ok = fmt.ANY_ID.match(stem)
        else:
            m = fmt.OUTBOX_ID.match(stem)
            ok = m and m.group(1) == sender
        return stem if ok else 'x-' + hashlib.sha1(('%s/%s' % (sender, path.name)).encode()).hexdigest()[:20]

    def process_file(self, sender, path, over=None):
        """over：財務擋單的理由（budget_hold），有＝不處理、照一般退件走。"""
        rid = self.record_id(sender, path)
        rec = self.load_rec(rid)
        if rec is None:
            rec = self.reject(sender, path, rid, 'OverBudget', over) if over else self.take(sender, path, rid)
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
                recheck(self.roster, sender, kind, obj)
            if kind == 'letter' and obj['to'] not in (HUMAN, BEAT) and not self.lay.member(obj['to']).is_dir():
                raise TeamError('NoHome', '收件人 %s 的家還沒建（aos-team init）' % obj['to'])
            if kind == 'request':
                try:
                    effects = aos_team_requests.handle(self.lay, self.roster, obj)
                    if obj['kind'] == 'spawn':     # 不用人批的 spawn 當場改了名冊：同一輪後面的信要看新名冊（astra 09-25）
                        self.roster = fmt.load_roster(self.root)
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


# ------------------------------------------------------ kernel 登記 ----

def proc_name(team_dir, what):
    base = re.sub(r'[^A-Za-z0-9_-]', '-', Path(team_dir).resolve().name) or 'team'
    return 'team-%s-%s-%s' % (what, base, team_tag(team_dir))


def bad_notice(lay, what):
    """09-24 tick-gap（P2 隊）：郵差／心跳連錯被 kernel 判 bad 時，kernel 直接往人的收件匣放一封信（不經郵差：壞的可能就是它）。
    {id}{proc}{fails}{at}{look} 由 kernel 當下填（spec/kernel/syscall.md 的 on_bad）。"""
    label = {'post': '郵差', 'beat': '心跳'}.get(what, what)
    lay.human_inbox.mkdir(parents=True, exist_ok=True)
    return {'dir': str(lay.human_inbox),
            'body': {'id': '{id}', 'from': 'kernel', 'to': HUMAN, 'status': 'FAILED', 'reply_to': None, 'rev': None,
                     'text': '%s（kernel 反覆工作 {proc}）連錯 {fails} 次，被 kernel 判 bad、停了（{at}）。'
                             '看 {look}；修好後 aos-team stop 再 aos-team start。' % label,
                     'at': '{at}', 'header': '【kernel 通知 · %s停了 · {at}】' % label}}


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
    params = {'target': str(inst), 'name': name, 'on_bad': bad_notice(lay, what)}  # 09-24 tick-gap：壞了寄給人
    if interval_ms:
        params['interval_ms'] = interval_ms
    res = aos_client.call(kernel, 'add', params, client='team', timeout_ms=10000)
    if 'error' in res:
        code = (res['error'].get('data') or {}).get('code')
        if code == 'AlreadyExists':
            try:
                proc = (aos_kernel_store.peek_proc(kernel, name) or {}).get('proc')  # one-boot（P 隊）：K/ledger.sqlite
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


def start(team_dir, env=None, interval_ms=None):
    """aos-team start 的掛勾（spec/team/cli.md）：郵差每 team.json 的 post.interval_s 秒（預設 5）走一輪。
    改了間隔要 aos-team stop 再 start 才生效（kernel 登記的是當時的間隔）。"""
    if interval_ms is None:
        interval_ms = fmt.load_roster(team_dir)['post']['interval_s'] * 1000
    return register(team_dir, 'post', ['post', '--quiet'], interval_ms, env)


def stop(team_dir, env=None):
    return unregister(team_dir, 'post', env)
