"""心跳（spec/team/beat.md）：kernel 反覆叫 `aos-team beat`（例 60 秒），照 team/routines.json 算誰到期、以開單派出。

- 唯一資料來源 team/routines.json（wf-table/1），**只有郵差寫**（申請 kind=routine 的處理函式 on_routine）；
  人用 `aos-team routine add/rm`（寄申請）、模型寄 routine 申請要先過問人（人答「批准」才生效）。
- 心跳自己的狀態 team/beat.json（只有心跳寫）：每條例行上次處理到哪一次、在途的那一次。
- 每一次到期有自己的時刻；派出去＝一份 handoff 申請（寄件人 human：例行是人登記或人批准的），郵差開單派給執行者。
  在途不重派；單子 done 才算「上次執行」；failed／cancelled 照 retries 重派，用完報領隊。
- 漏跑（心跳停了好幾次）：只補最近一次，寄一封 PROGRESS 告訴領隊與人漏了幾次。
不叫模型。
"""
import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import re
import sys
import zlib

import aos_team_ask
import aos_team_format as fmt
from aos_team_format import HUMAN, POST, TeamError, Layout
import aos_team_task

ROUTINE_COLUMNS = ('name', 'every', 'daily', 'once', 'tz', 'to', 'workflow', 'goal', 'done_when', 'timeout_minutes',
                   'retries', 'added_by', 'added_at', 'q', 'request')
FIELDS = ('op', 'name', 'every', 'daily', 'once', 'tz', 'to', 'workflow', 'goal', 'done_when', 'timeout_minutes',
          'retries')
APPROVE = ('批准', '同意', '好', '可以', 'yes', 'y', 'ok', 'approve')
UNITS = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
CRASH_ENV = 'AOS_TEAM_POST_CRASH'


def crash(point):
    if point in (os.environ.get(CRASH_ENV) or '').split(','):
        import signal
        os.kill(os.getpid(), signal.SIGKILL)


def _zone(tz):
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(tz) if tz else None
    except Exception:
        return None


# ------------------------------------------------------------ 時間表 ----

def check_tz(tz):
    """IANA 時區名字要載得起來；打錯字不要默默變成本機時間。"""
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo(str(tz))
    except Exception:
        raise TeamError('BadRoutine', 'tz %r 不是認得的 IANA 時區（例 Asia/Taipei）' % (tz,))
    return tz

def parse_every(text):
    m = re.fullmatch(r'\s*([0-9]+)\s*([smhd])\s*', str(text or ''))
    if not m or int(m.group(1)) <= 0:
        raise TeamError('BadRoutine', 'every 要寫成 30s／10m／6h／1d 這種（收到 %r）' % (text,))
    return int(m.group(1)) * UNITS[m.group(2)]


def parse_daily(text):
    m = re.fullmatch(r'\s*([01]?[0-9]|2[0-3]):([0-5][0-9])\s*', str(text or ''))
    if not m:
        raise TeamError('BadRoutine', 'daily 要寫成 09:00 這種（收到 %r）' % (text,))
    return int(m.group(1)), int(m.group(2))


def parse_at(text):
    t = fmt.parse_iso(text)
    if t is None or t.tzinfo is None:
        raise TeamError('BadRoutine', 'once 要是含時區的 ISO 時刻，例 2026-09-25T10:00:00+08:00（收到 %r）' % (text,))
    return t


class Schedule:
    """一條例行的時間表：occurrences 都是有時區的 datetime。"""

    def __init__(self, row, team_tz):
        self.tz = _zone(row.get('tz') or team_tz)
        self.anchor = fmt.parse_iso(row.get('added_at')) or datetime.datetime.now(datetime.timezone.utc)
        if self.anchor.tzinfo is None:
            self.anchor = self.anchor.replace(tzinfo=datetime.timezone.utc)
        if row.get('every'):
            self.kind, self.period = 'every', parse_every(row['every'])
        elif row.get('daily'):
            self.kind, self.hm = 'daily', parse_daily(row['daily'])
        elif row.get('once'):
            self.kind, self.at = 'at', parse_at(row['once'])
        else:
            raise TeamError('BadRoutine', '%s 沒寫 every／daily／once' % row.get('name'))

    def _daily(self, day):
        """那一天的當地時刻，換成 UTC 回（同一個 ZoneInfo 的兩個時刻比大小會照牆上時間比、不管夏令，所以一律用 UTC 比）。
        夏令時間重複的那一小時取第一次（fold=0）；跳過的那一小時照 zoneinfo 換算（等於往後推一小時）。"""
        local = datetime.datetime(day.year, day.month, day.day, self.hm[0], self.hm[1])
        local = local.replace(tzinfo=self.tz) if self.tz else local.astimezone()
        return local.astimezone(datetime.timezone.utc)

    def _first_daily(self):
        day = self.anchor.astimezone(self.tz).date()
        t = self._daily(day)
        return t if t >= self.anchor else self._daily(day + datetime.timedelta(days=1))

    def latest(self, now):
        """now 以前（含）最近的一次；還沒有＝None。"""
        if self.kind == 'every':
            if now < self.anchor:
                return None
            k = int((now - self.anchor).total_seconds() // self.period)
            return self.anchor + datetime.timedelta(seconds=k * self.period)
        if self.kind == 'daily':
            day = now.astimezone(self.tz).date()
            t = self._daily(day)
            if t > now:
                t = self._daily(day - datetime.timedelta(days=1))
            return t if t >= self._first_daily() else None
        return self.at if now >= self.at else None

    def count(self, after, upto):
        """(after, upto] 之間該跑幾次；after 是 None＝從頭算。"""
        if upto is None:
            return 0
        if self.kind == 'every':
            k_up = int(round((upto - self.anchor).total_seconds() / self.period))
            k_af = -1 if after is None else int(round((after - self.anchor).total_seconds() / self.period))
            return max(0, k_up - k_af)
        if self.kind == 'daily':
            first = self._first_daily() if after is None else after
            days = (upto.astimezone(self.tz).date() - first.astimezone(self.tz).date()).days
            return max(0, days + (1 if after is None else 0))
        return 0 if after is not None else 1

    def next(self, now):
        if self.kind == 'every':
            last = self.latest(now)
            return self.anchor if last is None else last + datetime.timedelta(seconds=self.period)
        if self.kind == 'daily':
            last = self.latest(now)
            if last is None:
                return self._first_daily()
            return self._daily(last.astimezone(self.tz).date() + datetime.timedelta(days=1))
        return self.at if now < self.at else None

    def describe(self):
        if self.kind == 'every':
            return 'every %s' % fmt_period(self.period)
        if self.kind == 'daily':
            return 'daily %02d:%02d' % self.hm
        return 'once %s' % self.at.isoformat(timespec='minutes')


def fmt_period(seconds):
    for unit, size in (('d', 86400), ('h', 3600), ('m', 60)):
        if seconds % size == 0:
            return '%d%s' % (seconds // size, unit)
    return '%ds' % seconds


# ------------------------------------------------------------- 資料檔 ----

def load_routines(lay):
    if not lay.routines.exists():
        return {'contract': 'wf-table/1', 'source': None, 'columns': list(ROUTINE_COLUMNS), 'rows': [],
                'removed_requests': []}
    data = fmt.read_json(lay.routines)
    if not isinstance(data, dict) or data.get('contract') != 'wf-table/1' or not isinstance(data.get('rows'), list):
        raise TeamError('FormatInvalid', '%s 要是 wf-table/1（{"contract": "wf-table/1", "rows": […]}）' % lay.routines)
    data.setdefault('removed_requests', [])
    return data


def check_routine(req, roster):
    """驗 routine 申請（或 aos-team routine add 要寄的）的欄位；回整理好的列（字串值，照 wf-table/1）。"""
    where = 'routine'
    extra = sorted(set(req) - set(FIELDS) - set(fmt.REQUEST_COMMON))
    if extra:
        fmt.bad(where, '不認得的欄位 %s（可用：%s）' % ('、'.join(extra), '、'.join(FIELDS)))
    op = req.get('op')
    if op not in ('add', 'rm'):
        fmt.bad(where + '.op', '要是 add 或 rm')
    fmt.check_name(req.get('name'), where + '.name', member=False)
    if req.get('tz') is not None:
        check_tz(req['tz'])
    if op == 'rm':
        return {'name': req['name']}
    when = [k for k in ('every', 'daily', 'once') if req.get(k)]
    if len(when) != 1:
        fmt.bad(where, 'every／daily／once（一次性時刻）要恰好給一個')
    if req.get('to') not in roster['members']:
        fmt.bad(where + '.to', '%r 不在名冊裡' % (req.get('to'),), 'BadAssignee')
    fmt._str(req.get('goal'), where + '.goal', limit=4000)
    fmt.validate_done_when(req.get('done_when'), where + '.done_when')
    row = {c: '' for c in ROUTINE_COLUMNS}
    row.update(name=req['name'], to=req['to'], goal=req['goal'], done_when=req['done_when'],
               workflow=req.get('workflow') or '無', tz=req.get('tz') or '')
    row[when[0]] = str(req[when[0]])
    for key, lo, hi in (('timeout_minutes', 1, 7 * 24 * 60), ('retries', 0, 5)):
        if req.get(key) is not None:
            row[key] = str(fmt._int(req[key], '%s.%s' % (where, key), lo, hi))
    Schedule(dict(row, added_at=fmt.now_iso()), roster.get('tz'))      # 時間表寫法不對就在這裡擋
    return row


def on_routine(lay, roster, req):
    """申請 kind=routine（郵差叫）：op=add 加一列、op=rm 拿掉一列。人加的直接生效；成員提的開一題問人。

    冪等：同一份申請（看列的 request、removed_requests）再來＝不多做。
    """
    row = check_routine(req, roster)
    data = load_routines(lay)
    rows = data['rows']
    if req['op'] == 'rm':
        if req['id'] in data['removed_requests']:
            return []
        hit = [r for r in rows if r.get('name') == row['name']]
        if not hit:
            raise TeamError('NoSuchRoutine', '沒有例行 %s' % row['name'])
        if req['from'] not in (HUMAN, hit[0].get('added_by')):
            raise TeamError('NotAllowed', '只有人或提出的 %s 能拿掉 %s' % (hit[0].get('added_by'), row['name']))
        data['rows'] = [r for r in rows if r.get('name') != row['name']]
        data['removed_requests'] = (data['removed_requests'] + [req['id']])[-200:]
        fmt.write_json(lay.routines, data, indent=2)
        return []
    if any(r.get('request') == req['id'] for r in rows):
        return []
    if any(r.get('name') == row['name'] for r in rows):
        raise TeamError('NameTaken', '例行 %s 已經有了（先 aos-team routine rm）' % row['name'])
    row.update(added_by=req['from'], added_at=req.get('at') or fmt.now_iso(roster.get('tz')), request=req['id'])
    effects = []
    if req['from'] != HUMAN:
        ask = {'id': req['id'] + '.q', 'from': req['from'], 'kind': 'ask', 'at': row['added_at'],
               'question': '%s 提議加一條例行「%s」：%s 叫 %s 做：%s。要讓心跳自動跑嗎？'
                           % (req['from'], row['name'], Schedule(row, roster.get('tz')).describe(), row['to'],
                              row['goal']),
               'options': ['批准', '不要'], 'reply_to': None}
        effects = aos_team_ask.on_ask(lay, roster, ask)
        row['q'] = next(q['id'] for q in aos_team_ask.all_questions(lay) if q.get('request') == ask['id'])
    lay.routines.parent.mkdir(parents=True, exist_ok=True)
    data['rows'] = rows + [row]
    fmt.write_json(lay.routines, data, indent=2)
    return effects


def authorized(lay, row):
    """(會不會自動跑, 白話)：人加的會；成員提的要那一題被人答「批准」。"""
    if row.get('added_by') == HUMAN:
        return True, '人登記的'
    q = row.get('q')
    if not q:
        return False, '成員提的、沒有問人'
    try:
        question = aos_team_ask.load(lay, q)
    except TeamError:
        return False, '問題 %s 不見了' % q
    if question['status'] != 'answered':
        return False, '等人批准（aos-team answer %s 批准）' % q
    answer = str(question.get('answer') or '').strip().lower()
    if answer in APPROVE:
        return True, '人批准了（%s）' % q
    return False, '人沒批准（%s 答：%s）' % (q, question.get('answer'))


# --------------------------------------------------------------- 心跳 ----

class Beat:
    def __init__(self, team_dir, *, clock=None, out=None):
        self.lay = Layout(team_dir)
        self.clock = clock or (lambda: datetime.datetime.now(datetime.timezone.utc))
        self.out = out if out is not None else print
        self.state_path = self.lay.team / 'beat.json'
        self.sys_outbox = self.lay.team / 'post' / 'outbox'

    def run(self):
        self.lay.team.mkdir(parents=True, exist_ok=True)
        with open(self.lay.team / '.beat.lock', 'a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                self.out('心跳正在跑（另一個行程），這次略過')
                return 0
            self.roster = fmt.load_roster(self.lay.root)
            self.tz = self.roster.get('tz')
            self.state = fmt.read_json(self.state_path) if self.state_path.exists() else {'routines': {}}
            self.now = self.clock().astimezone(_zone(self.tz))
            for row in load_routines(self.lay)['rows']:
                try:
                    self.one(row)
                except TeamError as e:
                    sys.stderr.write('aos-team beat: 例行 %s：%s\n' % (row.get('name'), e))
        return 0

    def save(self):
        fmt.write_json(self.state_path, self.state, indent=2)

    def one(self, row):
        name = row['name']
        st = self.state['routines'].setdefault(name, {})
        if st.get('request') != row.get('request'):      # 同名的列被拿掉又重加：從頭算
            st.clear()
            st['request'] = row.get('request')
        self.flush_reports(row, st)
        if st.get('finished'):
            return
        ok, _ = authorized(self.lay, row)
        if not ok:
            return
        sched = Schedule(row, self.tz)
        inflight = st.get('inflight')
        if inflight:
            self.check_inflight(row, st, inflight)
            if st.get('inflight') or st.get('finished'):
                return
        latest = sched.latest(self.now)
        handled = fmt.parse_iso(st.get('handled'))
        if latest is None or (handled is not None and latest <= handled):
            return
        n = sched.count(handled, latest)
        if n >= 2:      # 報告先記進待寄（跟在途同一次寫），寄完才勾掉
            self.queue_report(st, 'missed-%d' % int(latest.timestamp()),
                              '心跳：例行 %s 到 %s 為止有 %d 次沒跑（心跳沒在跑，或上一次做太久），只補最近一次（%s）。'
                              % (name, fmt.short_time(latest.isoformat(), self.tz), n,
                                 fmt.short_time(latest.isoformat(), self.tz)))
        self.dispatch(row, st, latest, 1)
        self.flush_reports(row, st)

    def request_id(self, row, occ, attempt):
        """派工申請的 id：那一次的時刻＋第幾次＋這條例行（名字＋登記它的申請），重跑算出來一樣；刪掉重加是新的一條。"""
        ident = '%s|%s' % (row['name'], row.get('request'))
        return '%d-%d-%s' % (int(occ.timestamp()) * 10 ** 9 + attempt, zlib.crc32(ident.encode()) % 10 ** 9, HUMAN)

    def dispatch(self, row, st, occ, attempt):
        """先記在途、再寫申請（不覆蓋）：崩在中間，下一輪看到在途但沒申請檔就補寫同一份。"""
        rid = self.request_id(row, occ, attempt)
        st['inflight'] = {'occ': occ.isoformat(timespec='seconds'), 'try': attempt, 'request': rid,
                          'dispatched_at': self.now.isoformat(timespec='seconds')}
        self.save()
        crash('beat-dispatch')
        self.write_request(row, st['inflight'])
        self.out('心跳 派出 %s @ %s（第 %d 次）→ %s' % (row['name'], fmt.short_time(st['inflight']['occ'], self.tz),
                                                  attempt, row['to']))

    def write_request(self, row, inflight):
        outbox = self.lay.outbox(HUMAN)
        outbox.mkdir(parents=True, exist_ok=True)
        req = {'id': inflight['request'], 'from': HUMAN, 'kind': 'handoff',
               'at': self.now.isoformat(timespec='seconds'), 'assignee': row['to'],
               'workflow': row.get('workflow') or '無',
               'goal': '〔例行 %s @ %s〕%s' % (row['name'], fmt.short_time(inflight['occ'], self.tz), row['goal']),
               'done_when': row['done_when']}
        if row.get('timeout_minutes'):
            req['deadline_minutes'] = int(row['timeout_minutes'])
        fmt.write_new(outbox / (req['id'] + '.json'), req)

    def request_state(self, rid):
        """那份申請現在在哪：ticket（開了單）／rejected（被退）／pending（還在 outbox 或郵差剛收）／missing。"""
        t = aos_team_task.find_by_request(self.lay, rid)
        if t is not None:
            return 'ticket', t
        box = self.lay.outbox(HUMAN)
        if (box / 'rejected' / (rid + '.json')).exists():
            return 'rejected', None
        if (box / (rid + '.json')).exists() or (box / 'done' / (rid + '.json')).exists():
            return 'pending', None
        return 'missing', None

    def check_inflight(self, row, st, inflight):
        where, t = self.request_state(inflight['request'])
        if where == 'missing':
            self.write_request(row, inflight)
            return
        if where == 'pending':
            return
        if where == 'ticket' and t['status'] == 'done':
            st.update(handled=inflight['occ'], last_run=self.now.isoformat(timespec='seconds'), last_result='done',
                      last_task=t['id'], inflight=None)
            if row.get('once'):
                st['finished'] = True
            self.save()
            self.out('心跳 %s @ %s 完成（%s）' % (row['name'], fmt.short_time(inflight['occ'], self.tz), t['id']))
            return
        if where == 'ticket' and t['status'] not in ('failed', 'cancelled'):
            return                                   # 在途：不重派
        why = '郵差退了派工申請' if where == 'rejected' else '%s %s' % (t['id'], t['status'])
        retries = int(row.get('retries') or 0)
        if inflight['try'] <= retries:
            occ = fmt.parse_iso(inflight['occ'])
            self.out('心跳 %s @ %s 沒成（%s），重派' % (row['name'], fmt.short_time(inflight['occ'], self.tz), why))
            self.dispatch(row, st, occ, inflight['try'] + 1)
            return
        st.update(handled=inflight['occ'], last_result='failed', last_task=t['id'] if t else None, inflight=None)
        if row.get('once'):
            st['finished'] = True
        self.queue_report(st, 'failed-%s' % inflight['request'],
                          '心跳：例行 %s（%s 那一次）%d 次都沒成（%s），這一次放棄，下次到期照常派。'
                          % (row['name'], fmt.short_time(inflight['occ'], self.tz), inflight['try'], why))
        self.save()                              # 放棄這一次與「待寄報告」同一次寫
        self.flush_reports(row, st)

    def queue_report(self, st, tag, text):
        st.setdefault('reports', [])
        if not any(r['tag'] == tag for r in st['reports']):
            st['reports'].append({'tag': tag, 'text': text})

    def flush_reports(self, row, st):
        """寄待寄的報告（給每個領隊與人）：寫進郵差的 team/post/outbox/（from post），郵差投。
        id 由事件與這條例行算出來、不覆蓋，重寄不會多一封；全部寫好才從待寄拿掉。"""
        if not st.get('reports'):
            return
        self.sys_outbox.mkdir(parents=True, exist_ok=True)
        ident = '%08x' % zlib.crc32(('%s|%s' % (row['name'], row.get('request'))).encode())
        for r in st['reports']:
            for to in fmt.members_by_template(self.roster, 'lead') + [HUMAN]:
                lid = 'beat-%s-%s-%s-%s' % (row['name'], ident, r['tag'], to)
                letter = {'id': lid, 'from': POST, 'to': to, 'status': 'PROGRESS', 'reply_to': None, 'rev': None,
                          'text': r['text'], 'at': self.now.isoformat(timespec='seconds')}
                fmt.write_new(self.sys_outbox / (lid + '.json'), letter)
            self.out(r['text'])
        st['reports'] = []
        self.save()


# --------------------------------------------------------------- 指令 ----

def cmd_beat(team_dir, argv):
    p = argparse.ArgumentParser(prog='aos-team beat', description='心跳走一輪（kernel 反覆叫它；人也可以手動跑）')
    p.add_argument('--quiet', action='store_true', help='不印做了什麼（kernel 用）')
    args = p.parse_args(argv)
    return Beat(team_dir, out=(lambda line: None) if args.quiet else None).run()


def cmd_routine(team_dir, argv):
    p = argparse.ArgumentParser(prog='aos-team routine', description='心跳的例行：ls 看、add／rm 寄申請給郵差')
    sub = p.add_subparsers(dest='op', required=True)
    ls = sub.add_parser('ls', help='列出例行：時間表、授權、上次、在途、下次')
    ls.add_argument('--json', action='store_true')
    add = sub.add_parser('add', help='加一條（人加的直接生效）')
    add.add_argument('name')
    when = add.add_mutually_exclusive_group(required=True)
    when.add_argument('--every', help='間隔，例 2m、6h、1d')
    when.add_argument('--daily', help='每天幾點，例 09:00')
    when.add_argument('--once', help='一次性：含時區的 ISO 時刻，例 2026-09-25T10:00:00+08:00')
    add.add_argument('--to', required=True, help='誰做（成員名）')
    add.add_argument('--goal', required=True, help='做什麼（一句話）')
    add.add_argument('--workflow', help='照哪份工作流（沒寫＝無）')
    add.add_argument('--done-file', action='append', default=[], help='做完時這個檔要在（相對專案，可給多次）')
    add.add_argument('--done-when', help='完整的 done_when JSON 陣列（跟 --done-file 疊加）')
    add.add_argument('--tz', help='時區（沒寫＝團隊的）')
    add.add_argument('--timeout', type=int, help='幾分鐘沒完成算這次失敗')
    add.add_argument('--retries', type=int, help='失敗重派幾次（預設 0）')
    rm = sub.add_parser('rm', help='拿掉一條')
    rm.add_argument('name')
    args = p.parse_args(argv)
    lay = Layout(team_dir)
    roster = fmt.load_roster(team_dir)
    if args.op == 'ls':
        return routine_ls(lay, roster, args.json)
    req = {'id': fmt.new_id(HUMAN), 'from': HUMAN, 'kind': 'routine', 'at': fmt.now_iso(roster.get('tz')),
           'op': args.op, 'name': args.name}
    if args.op == 'add':
        done = [{'kind': 'file_exists', 'path': f} for f in args.done_file]
        if args.done_when:
            try:
                extra = json.loads(args.done_when)
            except ValueError as e:
                raise TeamError('Usage', '--done-when 不是合法 JSON：%s' % e)
            done += extra if isinstance(extra, list) else [extra]
        if not done:
            raise TeamError('Usage', '要給 --done-file 或 --done-when（做完怎麼驗；心跳派的單一樣要驗收）')
        req.update(to=args.to, goal=args.goal, done_when=done)
        for key in ('every', 'daily', 'once', 'workflow', 'tz'):
            if getattr(args, key):
                req[key] = getattr(args, key)
        if args.timeout is not None:
            req['timeout_minutes'] = args.timeout
        if args.retries is not None:
            req['retries'] = args.retries
    check_routine(req, roster)
    if args.op == 'rm' and not any(r.get('name') == args.name for r in load_routines(lay)['rows']):
        raise TeamError('NoSuchRoutine', '沒有例行 %s（aos-team routine ls 看有哪些）' % args.name)
    box = lay.outbox(HUMAN)
    box.mkdir(parents=True, exist_ok=True)
    fmt.write_new(box / (req['id'] + '.json'), req)
    print('已交給郵差：routine %s %s（郵差下一輪改 team/routines.json；aos-team routine ls 看）' % (args.op, args.name))
    return 0


def routine_ls(lay, roster, as_json=False):
    rows = load_routines(lay)['rows']
    state_path = lay.team / 'beat.json'
    state = (fmt.read_json(state_path) if state_path.exists() else {}).get('routines', {})
    now = datetime.datetime.now(datetime.timezone.utc)
    out = []
    for row in rows:
        st = state.get(row['name'], {})
        if st.get('request') != row.get('request'):
            st = {}
        ok, why = authorized(lay, row)
        try:
            sched = Schedule(row, roster.get('tz'))
            when, nxt = sched.describe(), sched.next(now)
        except TeamError as e:
            when, nxt = '壞的：%s' % e.msg, None
        inflight = st.get('inflight')
        out.append({'name': row['name'], 'when': when, 'to': row['to'], 'active': ok, 'auth': why,
                    'last_run': st.get('last_run'), 'last_result': st.get('last_result'),
                    'inflight': inflight, 'finished': bool(st.get('finished')),
                    'next': nxt.isoformat(timespec='seconds') if nxt and not st.get('finished') else None})
    if as_json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    if not out:
        print('沒有例行（aos-team routine add NAME --every 2m --to worker-1 --goal … --done-file …）')
        return 0
    tz = roster.get('tz')
    for r in out:
        state_text = '已完成（一次性）' if r['finished'] else \
            ('在途：%s 那一次' % fmt.short_time(r['inflight']['occ'], tz) if r['inflight'] else
             '下次 %s' % (fmt.short_time(r['next'], tz) if r['next'] else '—'))
        print('%s  %s → %s  %s  上次 %s%s  %s' % (
            r['name'], r['when'], r['to'], r['auth'], fmt.short_time(r['last_run'], tz) if r['last_run'] else '—',
            '（%s）' % r['last_result'] if r['last_result'] else '', state_text))
    return 0


def start(team_dir, env=None, interval_ms=60000):
    """aos-team start 的掛勾：心跳每 interval_ms 走一輪。"""
    import aos_team_post
    return aos_team_post.register(team_dir, 'beat', ['beat', '--quiet'], interval_ms, env)


def stop(team_dir, env=None):
    import aos_team_post
    return aos_team_post.unregister(team_dir, 'beat', env)
