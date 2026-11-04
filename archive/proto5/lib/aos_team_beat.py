"""心跳（spec/team/beat.md）：kernel 反覆叫 `aos-team beat`（例 60 秒），照 team/routines.json 算誰到期、以開單派出。

- 唯一資料來源 team/routines.json（wf-table/1），**只有郵差寫**（申請 kind=routine 的處理函式 on_routine）；
  人用 `aos-team routine add/rm`（寄申請）、模型寄 routine 申請要先過問人（人答「批准」才生效）。
- 心跳自己的狀態 team/beat.json（只有心跳寫）：每條例行上次處理到哪一次、在途的那一次。
- 每一次到期有自己的時刻；派出去＝一份 handoff 申請，寄件人是心跳自己（`beat`，放在 team/outbox/beat/），郵差開單派給執行者；
  單子的開單人是 beat，信頭寫「心跳（定時器）」。做完不寄信給人，只有失敗、逾時、檢查器壞才寄（2026-09-24 使用者裁）。
  在途不重派；單子 done 才算「上次執行」；failed／cancelled 照 retries 重派，用完報領隊。
- 漏跑（心跳停了好幾次）：只補最近一次，寄一封 PROGRESS 告訴領隊與人漏了幾次。
不叫模型。
這個檔留心跳本體 Beat 與指令（beat、routine ls／add／rm、kernel 登記 start／stop）；
時間表與例行表分在 aos_team_beat_schedule／routines，這裡匯出外部用到的名字。
"""
import argparse
import datetime
import fcntl
import json
import sys
import zlib

import aos_team_format as fmt
from aos_team_format import BEAT, HUMAN, TeamError, Layout
import aos_team_task

from aos_team_beat_schedule import _zone, APPROVE, crash, FIELDS, parse_daily, parse_every, Schedule
from aos_team_beat_routines import authorized, check_routine, load_routines, on_routine


# --------------------------------------------------------------- 心跳 ----

class Beat:
    def __init__(self, team_dir, *, clock=None, out=None):
        self.lay = Layout(team_dir)
        self.clock = clock or (lambda: datetime.datetime.now(datetime.timezone.utc))
        self.out = out if out is not None else print
        self.state_path = self.lay.team / 'beat.json'
        self.box = self.lay.outbox(BEAT)

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
        return '%d-%d-%s' % (int(occ.timestamp()) * 10 ** 9 + attempt, zlib.crc32(ident.encode()) % 10 ** 9, BEAT)

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
        outbox = self.box
        outbox.mkdir(parents=True, exist_ok=True)
        req = {'id': inflight['request'], 'from': BEAT, 'kind': 'handoff',
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
        box = self.box
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
        """寄待寄的報告（給每個領隊與人）：心跳自己的信，寫進 team/outbox/beat/（from beat），郵差投。
        id 由事件、這條例行、收件人算出來（照 outbox 的 <數字>-<數字>-beat 格式）、不覆蓋，重寄不會多一封；
        全部寫好才從待寄拿掉。"""
        if not st.get('reports'):
            return
        self.box.mkdir(parents=True, exist_ok=True)
        ident = '%s|%s' % (row['name'], row.get('request'))
        for r in st['reports']:
            for to in fmt.members_by_template(self.roster, 'lead') + [HUMAN]:
                lid = '%d-%d-%s' % (zlib.crc32(('%s|%s' % (ident, r['tag'])).encode()),
                                    zlib.crc32(to.encode()) % 10 ** 9, BEAT)
                letter = {'id': lid, 'from': BEAT, 'to': to, 'status': 'PROGRESS', 'reply_to': None, 'rev': None,
                          'text': r['text'], 'at': self.now.isoformat(timespec='seconds')}
                fmt.write_new(self.box / (lid + '.json'), letter)
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
