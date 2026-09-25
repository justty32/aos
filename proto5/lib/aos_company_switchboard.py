"""機械總機 Switchboard：〔給 部門〕→ 對方門房開單或窗口信，回覆照 reply_to／任務單 request 抄回，先記帳再動作。"""
import contextlib
import fcntl
import io
import os
from pathlib import Path

import aos_team_format as fmt
from aos_team_format import HUMAN, BEAT, POST, Layout, TeamError

from aos_company_config import (
    CompanyError, desk_member, host_dept, load, MARK, ORDER_TYPE, resolve_dept, team_dirs,
    TERMINAL_STATUS
)


# ------------------------------------------------------------------ 總機 ----

@contextlib.contextmanager
def _lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a') as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


class Switchboard:
    def __init__(self, cdir, cfg=None, now=None):
        self.cdir = Path(os.path.abspath(str(cdir)))
        self.cfg = cfg or load(self.cdir)
        self.root = self.cdir / 'switchboard'
        self.orders = self.root / 'orders'
        self.seen = self.root / 'seen'
        self.teams = team_dirs(self.cdir, self.cfg)
        self.now = now or fmt.now_iso
        self.log = []

    # -- 單 --
    def order_path(self, oid):
        return self.orders / (oid + '.json')

    def all_orders(self):
        return [fmt.read_json(p) for p in fmt.json_files(self.orders)] if self.orders.is_dir() else []

    def save_order(self, o):
        fmt.write_json(self.order_path(o['id']), o, indent=1)

    def new_order(self, src_dept, member, letter_id, dept, text, out_id=None):
        self.orders.mkdir(parents=True, exist_ok=True)
        oid = fmt.next_number(self.orders, 'o-')
        host = host_dept(self.cfg, dept)
        o = {'_metainfo': {'_type': ORDER_TYPE, '_version': 1}, 'id': oid, 'at': self.now(),
             'from': {'dept': src_dept, 'member': member, 'letter': letter_id},
             'to': {'dept': dept, 'team': host, 'member': None}, 'text': text,
             'via': None, 'route': None, 'out_id': out_id or fmt.new_id(HUMAN), 'task': None, 'status': 'open',
             'replies': [], 'result': None}
        self.save_order(o)
        return o

    # -- 寫信（寄件人一律 human）--
    def _put(self, dept, obj):
        lay = Layout(self.teams[dept])
        folder = lay.outbox(HUMAN)
        folder.mkdir(parents=True, exist_ok=True)
        fmt.write_new(folder / (obj['id'] + '.json'), obj)      # 已在＝上次寫過（崩了重來），不覆蓋

    def letter(self, dept, lid, to, status, text, reply_to=None):
        roster = fmt.load_roster(self.teams[dept])
        obj = {'id': lid, 'from': HUMAN, 'to': to, 'status': status, 'reply_to': reply_to, 'rev': None,
               'text': text[:fmt.TEXT_LIMIT], 'at': fmt.now_iso(roster.get('tz'))}
        fmt.validate_letter(obj)
        self._put(dept, obj)

    # -- 派一張總機單 --
    def dispatch(self, o):
        """照對方門房：handoff 規則命中＝開單；tool 規則＝在這裡跑、結果當回覆；其他＝寫信給窗口。"""
        import aos_team_route as route
        dept = o['to']['team']
        tdir = self.teams[dept]
        roster = fmt.load_roster(tdir)
        text = o['text']
        first, _sep, rest = text.strip().partition('\n')      # 門房只比第一行；後面幾行是補充
        result, rule, groups = 'lead', None, {}
        routes_path = Layout(tdir).routes
        if routes_path.is_file():
            neg, routes = route.load_routes(routes_path)
            if not [x for x in route.run_tests(neg, routes) if not x[1]]:
                result, rule, groups, _why = route.decide(first.strip(), neg, routes)
        if result == 'handoff':
            req = dict(route.fill(rule['handoff'], groups))
            route.apply_if_missing(rule, groups, req, fmt.project_dir(tdir, roster))   # 草稿不在＝單子寫從原文起
            req.update(id=o['out_id'], kind='handoff', at=fmt.now_iso(roster.get('tz')))
            req['from'] = HUMAN
            req['goal'] = '〔總機 %s，%s 交辦〕%s' % (o['id'], self._who(o), req['goal'])
            if rest.strip():
                req['facts'] = ((req.get('facts') or '') + '\n交辦人補充：' + rest.strip())[:4000]
            fmt.validate_request(req, 'routes.json 規則 %s' % rule['name'])
            self._put(dept, req)
            o.update(via='handoff', route=rule['name'])
            o['to']['member'] = req['assignee']
        elif result == 'tool' and 'run' in rule:
            from aos_team_cli import resolve
            run = route.fill(list(rule['run']), groups)
            # 先記「要跑了」再跑：崩在跑完、存結果之前，重跑看到 running 就不再跑（工具可能有副作用，astra 必修 8）
            o.update(via='tool', route=rule['name'], status='running')
            self.save_order(o)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                try:
                    code = resolve(run[0])(str(tdir), run[1:])
                except TeamError as e:
                    code = 1
                    print('%s: %s' % (e.code, e.msg))
            o.update(via='tool', route=rule['name'], status='done' if code == 0 else 'failed',
                     result=buf.getvalue()[-4000:], closed_at=self.now())
            self._reply_to_origin(o, 'DONE' if code == 0 else 'FAILED',
                                  '%s 部門房直接處理（規則 %s，退出 %d）：\n%s' % (dept, rule['name'], code, o['result']),
                                  o['out_id'])
        else:
            to = desk_member(self.cfg, dept, roster)
            head = ('〔總機 %s：%s 交辦。做完用 team_say 回 human，reply_to 寫 %s；'
                    '要別的部門幫忙，信第一行寫〔給 部門〕〕' % (o['id'], self._who(o), o['id']))
            self.letter(dept, o['out_id'], to, 'REQUEST', head + '\n' + text)
            o.update(via='desk')
            o['to']['member'] = to
        self.save_order(o)
        self.log.append('總機 %s：%s → %s（%s）' % (o['id'], self._who(o), o['to']['dept'], o['via']))

    def _who(self, o):
        f = o['from']
        return '董事' if f['dept'] == 'board' else '%s 部 %s' % (f['dept'], f['member'])

    def _reply_to_origin(self, o, status, text, lid):
        f = o['from']
        if f['dept'] == 'board' or f['member'] is None:
            return                                   # 董事下的單：回信就留在對方部門的 human 收件匣，mail 看
        self.letter(f['dept'], lid, f['member'], status, text, reply_to=f['letter'])

    # -- 一封寄給 human 的信怎麼處理 --
    def _match_order(self, dept, letter):
        r = letter.get('reply_to')
        orders = [o for o in self.all_orders() if o['to']['team'] == dept]
        if r:
            base = r.split('.r')[0]
            req = None
            tpath = Layout(self.teams[dept]).task(base) if fmt.TASK_ID.match(r) else None
            if tpath is not None and tpath.is_file():
                req = fmt.read_json(tpath).get('request')
            for o in orders:
                if r in (o['id'], o['out_id']) or (o['task'] and base == o['task']) or (req and req == o['out_id']):
                    if fmt.TASK_ID.match(r) and not o['task']:
                        o['task'] = base
                    return o
        if not r and letter.get('from') not in (POST, BEAT, HUMAN):
            desk_open = [o for o in orders if o['status'] == 'open' and o['via'] == 'desk'
                         and o['to']['member'] == letter.get('from')]
            if len(desk_open) == 1:                  # 窗口回信沒寫 reply_to：它手上只有一張總機單就是那張
                return desk_open[0]
        return None

    def classify(self, dept, letter):
        text = letter.get('text', '')
        m = MARK.match(text)
        sender = letter.get('from')
        if m and sender not in (POST, BEAT, HUMAN):
            target = resolve_dept(self.cfg, m.group(1))
            body = text[m.end():].strip()
            rec = {'action': 'order', 'target': target, 'word': m.group(1), 'body': body,
                   'out_id': fmt.new_id(HUMAN)}
            if target is None:
                rec.update(action='bounce', why='沒有「%s」這個部門；有：%s' % (
                    m.group(1), '、'.join('%s（%s）' % (k, d['title']) for k, d in self.cfg['departments'].items())))
            elif host_dept(self.cfg, target) is None:
                rec.update(action='bounce', why='%s（%s）尚未成立：%s' % (
                    target, self.cfg['departments'][target]['title'], self.cfg['departments'][target]['state']))
            elif host_dept(self.cfg, target) == dept:
                rec.update(action='bounce', why='%s 就在你自己的團隊裡，直接寄給隊友' % target)
            elif not body:
                rec.update(action='bounce', why='〔給 %s〕後面沒寫要做什麼' % m.group(1))
            return rec
        o = self._match_order(dept, letter)
        if o is not None and o['via'] == 'handoff' and sender != POST and letter.get('status') == 'DONE':
            # 開單類：負責人自己說的 DONE 還沒驗收，不轉；等郵差驗完寄的那封（DONE／FAILED）才算
            self.save_order(o)
            return {'action': 'note', 'order': o['id']}
        if o is not None:
            self.save_order(o)
            return {'action': 'reply', 'order': o['id'], 'task': o['task'], 'out_id': fmt.new_id(HUMAN)}
        return {'action': 'board'}

    def perform(self, dept, letter, rec):
        if rec['action'] == 'order':
            oid = rec.get('order')
            if oid is None:
                # 崩在「單寫好、單號還沒記回 seen」之間：照來信找回那張，不另開（astra 必修 7）
                o = next((x for x in self.all_orders() if x['from'].get('dept') == dept
                          and x['from'].get('letter') == letter['id']), None)
                if o is None:
                    o = self.new_order(dept, letter['from'], letter['id'], rec['target'], rec['body'],
                                       out_id=rec['out_id'])
                rec['order'] = o['id']
                self._save_seen(dept, letter['id'], rec)       # 單號先記下，崩了重來不會多開一張
            else:
                o = fmt.read_json(self.order_path(oid))
            if o['via'] is None:
                self.dispatch(o)
        elif rec['action'] == 'reply':
            o = fmt.read_json(self.order_path(rec['order']))
            if rec.get('task') and not o['task']:
                o['task'] = rec['task']
            st = letter['status']
            head = '〔總機 %s 回覆：%s 部 %s → %s%s〕' % (
                o['id'], o['to']['team'], letter['from'], st, '（%s）' % letter['reply_to'] if letter.get('reply_to') else '')
            self._reply_to_origin(o, st, head + '\n' + letter['text'], rec['out_id'])
            if not any(x['letter'] == letter['id'] for x in o['replies']):
                o['replies'].append({'letter': letter['id'], 'status': st, 'at': letter.get('at')})
            closer = POST if o['via'] == 'handoff' else o['to']['member'] if o['via'] == 'desk' else None
            if st in TERMINAL_STATUS and o['status'] == 'open' and (closer is None or letter.get('from') == closer):
                o['status'] = 'done' if st == 'DONE' else 'failed'     # desk 單只有窗口本人能結（astra 必修 6）
                o['closed_at'] = self.now()
            self.save_order(o)
            self.log.append('總機 %s：%s 回 %s' % (o['id'], o['to']['team'], st))
        elif rec['action'] == 'bounce':
            self.letter(dept, rec['out_id'], letter['from'], 'FAILED', '〔總機退信〕' + rec['why'],
                        reply_to=letter['id'])
            self.log.append('總機退信給 %s 部 %s：%s' % (dept, letter['from'], rec['why']))

    def _seen_path(self, dept, lid):
        return self.seen / dept / (lid + '.json')

    def _save_seen(self, dept, lid, rec):
        p = self._seen_path(dept, lid)
        p.parent.mkdir(parents=True, exist_ok=True)
        fmt.write_json(p, rec)

    def round(self):
        """走一輪：每個部門寄給 human 的信，沒處理過的處理一次（先記帳再動作，崩了重跑不重寄）。"""
        with _lock(self.root / '.lock'):
            for dept, tdir in sorted(self.teams.items()):
                inbox = Layout(tdir).human_inbox
                if not inbox.is_dir():
                    continue
                for path in fmt.json_files(inbox):
                    try:
                        letter = fmt.read_json(path)
                        fmt.validate_letter({k: v for k, v in letter.items() if k != 'header'})  # 郵差多存一格信頭
                    except TeamError:
                        continue
                    p = self._seen_path(dept, letter['id'])
                    rec = fmt.read_json(p) if p.is_file() else None
                    if rec is not None and rec.get('done'):
                        continue
                    if rec is None:
                        rec = self.classify(dept, letter)
                        self._save_seen(dept, letter['id'], rec)
                    try:
                        self.perform(dept, letter, rec)
                    except TeamError as e:
                        rec['error'] = '%s: %s' % (e.code, e.msg)
                        self.log.append('總機處理 %s/%s 失敗：%s' % (dept, letter['id'], rec['error']))
                        self._save_seen(dept, letter['id'], rec)
                        continue
                    rec['done'] = True
                    self._save_seen(dept, letter['id'], rec)
            self.resume_orders()
        return self.log

    def resume_orders(self):
        """接續沒派完的單（astra 必修 7、8）：via 還是空的（董事單崩在派送前、或信的 seen 還沒走到）＝再派一次
        （out_id 固定、write_new 不覆蓋，不會重寄）；tool 單停在 running＝上次跑到一半崩了，不確定做完沒，
        **不自動重跑**，標 failed 回報下單的人。"""
        for o in self.all_orders():
            if o.get('status') == 'running' and o.get('via') == 'tool':
                f = o['from']
                sent = (Layout(self.teams[f['dept']]).outbox(HUMAN) / (o['out_id'] + '.json')
                        if f['dept'] in self.teams else None)
                if sent is not None and sent.is_file():      # 跑完、回信也寄了，只是單子沒存：照回信補記
                    st = fmt.read_json(sent).get('status')
                    o.update(status='done' if st == 'DONE' else 'failed', closed_at=self.now(),
                             result=o.get('result') or '（結果見回信 %s）' % o['out_id'])
                    self.save_order(o)
                    continue
                o.update(status='failed', closed_at=self.now(),
                         result='總機上次跑這個工具時中斷，不確定有沒有做完；不自動重跑，請人看過再決定要不要重下單')
                self._reply_to_origin(o, 'FAILED', '〔總機 %s〕%s' % (o['id'], o['result']), o['out_id'])
                self.save_order(o)
                self.log.append('總機 %s：工具中斷，標 failed' % o['id'])
            elif o.get('via') is None and o.get('status') == 'open' and o['to'].get('team') in self.teams:
                try:
                    self.dispatch(o)
                except TeamError as e:
                    self.log.append('總機接續 %s 失敗：%s: %s' % (o['id'], e.code, e.msg))

    def board_order(self, dept, text):
        """董事直接下單給某部門（跳過總裁）：一樣開總機單，回覆留在那個部門的 human 收件匣。"""
        with _lock(self.root / '.lock'):
            if host_dept(self.cfg, dept) is None:
                raise CompanyError('NotOpen', '%s 部門不在或尚未成立' % dept)
            o = self.new_order('board', None, None, dept, text)
            self.dispatch(o)
            return o

    def board_letters(self):
        """留給董事的信：各部門 human 收件匣裡總機判成 board、或還沒判的。"""
        out = []
        for dept, tdir in sorted(self.teams.items()):
            inbox = Layout(tdir).human_inbox
            for path in fmt.json_files(inbox) if inbox.is_dir() else []:
                try:
                    letter = fmt.read_json(path)
                except TeamError:
                    continue
                p = self._seen_path(dept, letter.get('id', ''))
                rec = fmt.read_json(p) if p.is_file() else {'action': 'board'}
                if rec.get('action') == 'board':
                    out.append((dept, letter))
                elif rec.get('action') == 'reply':
                    o = self.order_path(rec['order'])
                    if o.is_file() and fmt.read_json(o)['from']['dept'] == 'board':
                        out.append((dept, letter))
        return out
