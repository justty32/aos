#!/usr/bin/env python3
"""公司（spec/team/company.md；examples/company/）：幾支團隊合成一間公司，加一個機械的總機。

一間公司＝一個資料夾：`company.json`（部門、編制、上限）＋每個部門一支普通的 aos 團隊（`teams/<部門>/`）
＋自己的 kernel（`K/`，池的大小＝這家的 cpu 上限）＋總機的帳（`switchboard/`）。
**總機（relay）不叫模型**：每輪看每個部門寄給 human 的信（`team/human/`）——
  - 第一行寫 `〔給 <部門>〕…` 的＝跨部門的單：開一張總機單 `o-NNNN`，照對方門房的規則開單（命中 handoff）
    或寫信給對方的窗口（沒命中），寄件人都是 human（對方看來就是「公司」交辦的）；
  - 回的是總機單（reply_to 對得上單號、對方的任務單、或那封信）＝抄一封回給下單的人；
  - 其他＝留給董事（`company.py mail` 看）。
人（董事）還是 human：`order` 交給前台部門的門房，`answer` 回各部門的題。

子命令（`python3 aos_company.py <子命令> --company 資料夾 …`；examples/company/company.py 是同一支的包裝）：
  new 資料夾 [--prefix c1-] [--project P] [--llm-cpu N] [--cpu N]   照樣板生一家公司（成員名加前綴）
  up／down／status [--json]／order "一句話" [--to 部門]／relay [--quiet]／mail／answer 部門 q-NNNN "…"
"""
import argparse
import contextlib
import fcntl
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zlib

LIB = Path(__file__).resolve().parent
sys.path.insert(0, str(LIB))

import aos_team_format as fmt                                              # noqa: E402
from aos_team_format import HUMAN, BEAT, POST, Layout, TeamError          # noqa: E402

PROTO = LIB.parent
CLI = PROTO / 'cli'
EXAMPLE = PROTO / 'examples' / 'company'
TYPE = 'aos_company'
ORDER_TYPE = 'aos_company_order'
DEPT = re.compile(r'[a-z][a-z0-9]{0,11}\Z')
# 第一行開頭的收件部門：〔給 mfg〕、[給 mfg]、【給 製造部】都認；部門寫 key、title 或 aliases 之一
MARK = re.compile(r'\A[ \t]*[〔\[【][ \t]*給[ \t]*([^\s〕\]】]{1,24})[ \t]*[〕\]】][ \t:：]*')
PREFIX = re.compile(r'([a-z][a-z0-9]{0,7}-)?\Z')
LIMIT_KEYS = ('regular', 'cpu', 'llm_cpu')
STARTUP = {'regular': 10, 'cpu': 20, 'llm_cpu': 5}
CEILING = {'regular': 100, 'cpu': 200, 'llm_cpu': 20}
TOP_KEYS = ('_metainfo', 'name', 'prefix', 'stage', 'limits', 'limits_max', 'pools', 'front', 'project', 'llm',
            'daemon', 'departments', 'staff', 'relay', 'account')
DEPT_KEYS = ('title', 'team', 'part_of', 'desk', 'aliases', 'state', 'open', 'kpi', 'serves', 'delivers', 'lib')
STAFF_KEYS = ('dept', 'employment', 'roles', 'model')
TERMINAL_STATUS = ('DONE', 'FAILED')


class CompanyError(TeamError):
    pass


def bad(where, msg, code='FormatInvalid'):
    raise CompanyError(code, '%s：%s' % (where, msg))


# ------------------------------------------------------------------ 設定 ----

def _limits(obj, where, default):
    if obj is None:
        return dict(default)
    if not isinstance(obj, dict):
        bad(where, '要是物件 {"regular", "cpu", "llm_cpu"}')
    out = dict(default)
    for k, v in obj.items():
        if k not in LIMIT_KEYS:
            bad('%s.%s' % (where, k), '不認得；只有 %s' % '、'.join(LIMIT_KEYS))
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            bad('%s.%s' % (where, k), '要是 ≥ 0 的整數')
        out[k] = v
    return out


def validate(obj, where='company.json'):
    """驗 company.json，回補好預設值的新物件。"""
    if not isinstance(obj, dict):
        bad(where, '要是物件')
    for k in obj:
        if k not in TOP_KEYS:
            bad('%s.%s' % (where, k), '不認得的鍵')
    meta = obj.get('_metainfo')
    if meta is not None and meta != {'_type': TYPE, '_version': 1}:
        bad(where + '._metainfo', '要是 {"_type": "%s", "_version": 1}' % TYPE)
    prefix = obj.get('prefix', '')
    if not isinstance(prefix, str) or not PREFIX.match(prefix):
        bad(where + '.prefix', '要是空字串或 [a-z][a-z0-9]{0,7} 加一個 -（例 c1-）')
    ceiling = _limits(obj.get('limits_max'), where + '.limits_max', CEILING)
    limits = _limits(obj.get('limits'), where + '.limits', STARTUP)
    for k in LIMIT_KEYS:
        if limits[k] > ceiling[k]:
            bad('%s.limits.%s' % (where, k), '%d 超過擴張上限 limits_max.%s=%d' % (limits[k], k, ceiling[k]))
    pools = obj.get('pools', {'default': 10, 'llm': 5})
    if not isinstance(pools, dict) or set(pools) - {'default', 'llm'} or not all(
            isinstance(v, int) and not isinstance(v, bool) and v >= 1 for v in pools.values()):
        bad(where + '.pools', '要是 {"default": 正整數, "llm": 正整數}')
    pools = {'default': pools.get('default', 10), 'llm': pools.get('llm', 5)}
    if pools['llm'] > limits['llm_cpu']:
        bad(where + '.pools.llm', 'llm 池 %d 顆超過 limits.llm_cpu=%d' % (pools['llm'], limits['llm_cpu']), 'OverLimit')
    if pools['default'] > limits['cpu']:       # cpu 不含 llm 池（跟 HR 部 hr.md §5 同一個算法）
        bad(where + '.pools.default', 'default 池 %d 顆超過 limits.cpu=%d' % (pools['default'], limits['cpu']), 'OverLimit')
    depts = obj.get('departments')
    if not isinstance(depts, dict) or not depts:
        bad(where + '.departments', '至少一個部門')
    out_d = {}
    for key, d in depts.items():
        w = '%s.departments.%s' % (where, key)
        if not DEPT.match(key):
            bad(w, '部門代號要是 [a-z][a-z0-9]{0,11}')
        if not isinstance(d, dict):
            bad(w, '要是物件')
        for k in d:
            if k not in DEPT_KEYS:
                bad('%s.%s' % (w, k), '不認得的鍵')
        if d.get('team') is not None and d.get('part_of') is not None:
            bad(w, 'team 與 part_of 只能寫一個（自己一支團隊，或併在別的部門）')
        aliases = d.get('aliases', [])
        if not isinstance(aliases, list) or not all(isinstance(a, str) and a for a in aliases):
            bad(w + '.aliases', '要是字串陣列')
        out_d[key] = {'title': d.get('title') or key, 'team': d.get('team'), 'part_of': d.get('part_of'),
                      'desk': d.get('desk'), 'aliases': list(aliases), 'state': d.get('state', ''),
                      'open': bool(d.get('open', d.get('team') is not None or d.get('part_of') is not None)),
                      'kpi': d.get('kpi', ''), 'serves': d.get('serves', ''), 'delivers': d.get('delivers', ''),
                      'lib': d.get('lib', '')}
    for key, d in out_d.items():
        if d['part_of'] is not None:
            host = out_d.get(d['part_of'])
            if host is None or host['team'] is None:
                bad('%s.departments.%s.part_of' % (where, key), '%r 不是有自己團隊的部門' % d['part_of'])
    front = obj.get('front', 'hq')
    if front not in out_d or out_d[front]['team'] is None:
        bad(where + '.front', '前台部門 %r 要是有自己團隊的部門（董事的單交給它的門房）' % front)
    staff = obj.get('staff', {})
    if not isinstance(staff, dict):
        bad(where + '.staff', '要是物件')
    out_s = {}
    for name, s in staff.items():
        w = '%s.staff.%s' % (where, name)
        if not isinstance(s, dict):
            bad(w, '要是物件')
        for k in s:
            if k not in STAFF_KEYS:
                bad('%s.%s' % (w, k), '不認得的鍵')
        emp = s.get('employment', 'regular')
        if emp not in ('regular', 'temp'):
            bad(w + '.employment', '只有 regular（正式）／temp（臨時）')
        out_s[name] = {'dept': s.get('dept'), 'employment': emp, 'roles': list(s.get('roles', [])),
                       'model': s.get('model')}
    relay = obj.get('relay', {})
    interval = relay.get('interval_s', 5) if isinstance(relay, dict) else None
    if not isinstance(interval, int) or isinstance(interval, bool) or not 1 <= interval <= 3600:
        bad(where + '.relay.interval_s', '1～3600 的整數')
    return {'name': obj.get('name', 'company'), 'prefix': prefix, 'stage': obj.get('stage', 'startup'),
            'limits': limits, 'limits_max': ceiling, 'pools': pools, 'front': front,
            'project': obj.get('project'), 'llm': obj.get('llm', 'llm.json'), 'daemon': obj.get('daemon', 'D'),
            'departments': out_d, 'staff': out_s, 'relay': {'interval_s': interval},
            'account': obj.get('account')}


def load(cdir):
    cdir = Path(cdir)
    return validate(fmt.read_json(cdir / 'company.json'), str(cdir / 'company.json'))


def host_dept(cfg, dept):
    """部門真正落在哪個部門的團隊（併在別部門的回那個部門）；沒成立回 None。"""
    d = cfg['departments'].get(dept)
    if d is None or not d['open']:
        return None
    host = d['part_of'] or dept
    h = cfg['departments'].get(host)
    if h is None or not h['open'] or h['team'] is None:      # 兼任部門開著、宿主部門關了＝也算沒成立
        return None
    return host


def team_dirs(cdir, cfg):
    """有自己團隊、開著的部門 → 團隊資料夾（絕對路徑）。"""
    return {k: Path(os.path.abspath(Path(cdir) / d['team']))
            for k, d in cfg['departments'].items() if d['team'] is not None and d['open']}


def resolve_dept(cfg, word):
    """〔給 X〕的 X → 部門代號；認 key、title、aliases（全等）。"""
    for key, d in cfg['departments'].items():
        if word == key or word == d['title'] or word in d['aliases']:
            return key
    return None


def desk_member(cfg, dept, roster):
    """跨部門的信沒命中門房時交給誰：company.json 寫的 desk ＞ 第一個 lead ＞ 名冊第一個成員。"""
    d = cfg['departments'][dept]
    desk = d.get('desk')
    if desk:
        name = cfg['prefix'] + desk if not desk.startswith(cfg['prefix']) else desk
        if name in roster['members']:
            return name
    leads = fmt.members_by_template(roster, 'lead')
    return leads[0] if leads else next(iter(roster['members']))


# ------------------------------------------------------------------ 生一家 ----

def _prefixed(prefix, name):
    return name if name in (HUMAN, BEAT, POST) else prefix + name


def materialize_roster(src, prefix, project):
    """樣板名冊 → 這家的名冊：成員名、mail_to、成員層 spawn 不動；名字加前綴，project 換成絕對路徑，mounts 展開 ~。"""
    obj = json.loads(json.dumps(src))
    obj['project'] = str(project)
    members = {}
    for name, m in obj['members'].items():
        m = dict(m)
        m['mail_to'] = [_prefixed(prefix, x) for x in m.get('mail_to', [])]
        for k, v in list(m.get('mounts', {}).items()):
            if isinstance(v, dict):
                v['$val'] = os.path.expanduser(v['$val'])
            else:
                m['mounts'][k] = os.path.expanduser(v)
        members[_prefixed(prefix, name)] = m
    obj['members'] = members
    fmt.validate_roster(obj, 'team.json（前綴 %r）' % prefix)
    return obj


def materialize_routes(src, prefix):
    obj = json.loads(json.dumps(src))
    for r in obj.get('routes', []):
        if r.get('do') == 'handoff':
            r['handoff']['assignee'] = _prefixed(prefix, r['handoff']['assignee'])
    return obj


def new(dst, src=EXAMPLE, prefix='', project=None, llm_cpu=None, cpu=None, name=None):
    """照樣板（examples/company）生一家公司的資料夾。已存在＝AlreadyExists（不蓋）。"""
    src, dst = Path(src), Path(os.path.abspath(os.path.expanduser(str(dst))))
    raw = fmt.read_json(src / 'company.json')
    base = validate(raw, str(src / 'company.json'))
    if (dst / 'company.json').exists():
        raise CompanyError('AlreadyExists', '%s 已經有 company.json' % dst)
    if not PREFIX.match(prefix):
        raise CompanyError('Usage', '前綴要是空字串或 [a-z][a-z0-9]{0,7}-（例 c1-）')
    project = Path(os.path.abspath(os.path.expanduser(str(project or base['project'] or dst / 'proj'))))
    out = json.loads(json.dumps(raw))
    out['prefix'] = prefix
    out['name'] = name or (prefix[:-1] if prefix else base['name'])
    out['project'] = str(project)
    if llm_cpu is not None or cpu is not None:
        lim = dict(base['limits'])
        if llm_cpu is not None:
            lim['llm_cpu'] = llm_cpu
        if cpu is not None:
            lim['cpu'] = cpu
        out['limits'] = lim
        pools = dict(base['pools'])
        pools['llm'] = max(1, min(pools['llm'], lim['llm_cpu']))
        pools['default'] = max(1, min(pools['default'], lim['cpu']))
        out['pools'] = pools
    out['staff'] = {_prefixed(prefix, n): s for n, s in raw.get('staff', {}).items()}
    for d in out['departments'].values():
        if d.get('desk'):
            d['desk'] = _prefixed(prefix, d['desk'])
    validate(out, str(dst / 'company.json'))
    dst.mkdir(parents=True, exist_ok=True)
    for key, d in base['departments'].items():
        if d['team'] is None:
            continue
        tsrc = src / d['team']
        tdst = dst / d['team']
        tdst.mkdir(parents=True, exist_ok=True)
        fmt.write_json(tdst / 'team.json', materialize_roster(fmt.read_json(tsrc / 'team.json'), prefix, project),
                       indent=2)
        if (tsrc / 'routes.json').is_file():
            (dst / 'config').mkdir(exist_ok=True)
            fmt.write_json(dst / 'config' / ('%s.routes.json' % key),
                           materialize_routes(fmt.read_json(tsrc / 'routes.json'), prefix), indent=2)
    if (src / 'persona').is_dir():
        shutil.copytree(src / 'persona', dst / 'persona', dirs_exist_ok=True)
    llm = src / base['llm']
    if llm.is_file():
        shutil.copy(llm, dst / 'llm.json')
    out['llm'] = 'llm.json'
    fmt.write_json(dst / 'company.json', out, indent=2)
    return dst


def all_member_names(cdir, cfg=None):
    cfg = cfg or load(cdir)
    names = []
    for dept, tdir in team_dirs(cdir, cfg).items():
        roster = fmt.load_roster(tdir)
        names += list(roster['members'])
    return names


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


# ------------------------------------------------------------------ 數人頭、數 cpu ----

def headcount(cdir, cfg):
    """正式／臨時看名冊的 employment（HR 部 hr.md §7：人寫的預設 regular、spawn 生的 temp）；company.json 的 staff 只記兼任角色。"""
    regular, temp, rows = [], [], []
    for dept, tdir in sorted(team_dirs(cdir, cfg).items()):
        try:
            roster = fmt.load_roster(tdir)
        except TeamError:
            continue
        for name, m in roster['members'].items():
            staff = cfg['staff'].get(name)
            emp = m.get('employment', 'regular')
            (regular if emp == 'regular' else temp).append(name)
            rows.append({'dept': dept, 'name': name, 'template': m['template'], 'model': m['model'],
                         'employment': emp, 'roles': (staff or {}).get('roles', [])})
    return regular, temp, rows


def cpu_from_ls(ls):
    """aos-kernel ls --json → (cpu 顆數, llm cpu 顆數)：llm 池以外的 want 加總、llm 池的 want。
    跟 HR 部 count_cpus 同一個算法（cpu 不含 llm 池）。"""
    pools = (ls or {}).get('pools') or {}
    llm = int((pools.get('llm') or {}).get('want') or 0)
    total = sum(int(p.get('want') or 0) for name, p in pools.items() if name != 'llm')
    return total, llm


def caps_line(counts, limits):
    return '正式 %d/%d、cpu %d/%d、llm cpu %d/%d' % (
        counts['regular'], limits['regular'], counts['cpu'], limits['cpu'], counts['llm_cpu'], limits['llm_cpu'])


def over_caps(counts, limits):
    return [k for k in LIMIT_KEYS if counts[k] > limits[k]]


def daemon_dir(cdir, cfg):
    return Path(os.path.abspath(Path(cdir) / cfg['daemon']))


def own_daemon(cdir, cfg):
    """daemon 在公司資料夾裡（預設 <公司>/D，董事 09-25：一家一個 daemon＋kernel）＝只有這家用。"""
    c, d = str(Path(os.path.abspath(str(cdir)))), str(daemon_dir(cdir, cfg))
    return d.startswith(c.rstrip('/') + '/')


def env_for(cdir, cfg, daemon=False):
    """給 aos-team 的環境：這家的 kernel、HR 家＝K/hr（不管外面設了什麼 AOS_HR_HOME）。
    AOS_DAEMON_HOME：daemon 是這家自己的（在公司資料夾裡，預設）＝照帶，HR 數 cpu 只數得到自己；
    幾家共用 daemon（company.json 寫 "daemon": "../D"）＝不帶，免得 HR 把別家的 kernel 也數進來互相擋。
    開關機、建 kernel（daemon=True）一律帶。"""
    cdir = Path(cdir)
    e = dict(os.environ)
    e['PATH'] = '%s:%s' % (CLI, e.get('PATH', os.defpath))
    e['AOS_KERNEL_HOME'] = str(cdir / 'K')
    e['AOS_HR_HOME'] = str(cdir / 'K' / 'hr')
    e.pop('AOS_DAEMON_HOME', None)
    if daemon or own_daemon(cdir, cfg):
        e['AOS_DAEMON_HOME'] = str(daemon_dir(cdir, cfg))
    e['PYTHONDONTWRITEBYTECODE'] = '1'
    e.pop('AOS_TEAM_HOME', None)
    return e


def kernel_ls(cdir, cfg):
    if not (Path(cdir) / 'K').is_dir():
        return None
    r = subprocess.run([str(CLI / 'aos-kernel'), 'ls', '--json'], env=env_for(cdir, cfg, daemon=True), capture_output=True,
                       text=True, timeout=60, stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except ValueError:
        return None


def status_data(cdir, cfg=None, ls=None, use_kernel=True):
    cdir = Path(os.path.abspath(str(cdir)))
    cfg = cfg or load(cdir)
    regular, temp, rows = headcount(cdir, cfg)
    if ls is None and use_kernel:
        ls = kernel_ls(cdir, cfg)
    if ls is not None:
        cpu, llm = cpu_from_ls(ls)
        h = ls.get('health')
        code = h if isinstance(h, str) else (h or {}).get('code') if isinstance(h, dict) else None
        # health 不是 ok＝照實說（down 之後是 stopped，不再印 up；試玩 09-25）
        kernel = 'up' if code in (None, 'ok') else '%s（%s）' % (code, (h.get('message') if isinstance(h, dict) else '') or '')
    else:
        cpu, llm = cfg['pools']['default'], cfg['pools']['llm']
        kernel = 'down（cpu 照 company.json 的池算）'
    counts = {'regular': len(regular), 'cpu': cpu, 'llm_cpu': llm}
    sb = Switchboard(cdir, cfg)
    depts = []
    tdirs = team_dirs(cdir, cfg)
    for key, d in cfg['departments'].items():
        row = {'dept': key, 'title': d['title'], 'state': d['state'], 'team': d['team'], 'part_of': d['part_of'],
               'members': [r['name'] for r in rows if r['dept'] == key], 'tasks_open': 0, 'tasks_all': 0,
               'questions': 0}
        if key in tdirs:
            lay = Layout(tdirs[key])
            for p in fmt.json_files(lay.tasks) if lay.tasks.is_dir() else []:
                try:
                    t = fmt.read_json(p)
                except TeamError:
                    continue
                if t.get('parent'):
                    continue
                row['tasks_all'] += 1
                row['tasks_open'] += t.get('status') not in fmt.TERMINAL
            for p in fmt.json_files(lay.wait_user) if lay.wait_user.is_dir() else []:
                try:
                    row['questions'] += fmt.read_json(p).get('status') == 'open'
                except TeamError:
                    pass
        depts.append(row)
    orders = sb.all_orders()
    return {'name': cfg['name'], 'stage': cfg['stage'], 'kernel': kernel, 'counts': counts, 'limits': cfg['limits'],
            'limits_max': cfg['limits_max'], 'over': over_caps(counts, cfg['limits']), 'temp': len(temp),
            'caps': caps_line(counts, cfg['limits']), 'departments': depts, 'staff': rows,
            'orders': [{k: o[k] for k in ('id', 'status', 'via', 'task', 'text')} | {'to': o['to']['dept'],
                        'from': sb._who(o)} for o in orders],
            'board_letters': len(sb.board_letters())}


def print_status(s):
    print('公司 %s（%s）  kernel %s' % (s['name'], s['stage'], s['kernel']))
    print(s['caps'] + ('  ← 超過：%s' % '、'.join(s['over']) if s['over'] else '') + '  （臨時工 %d，不算人頭）' % s['temp'])
    for d in s['departments']:
        where = d['team'] or ('併在 %s' % d['part_of'] if d['part_of'] else '沒有團隊')
        print('  %-5s %-8s %-18s 成員 %-2d 單 %d 進行／%d 全部  等人答 %d  %s' % (
            d['dept'], d['title'][:8], where, len(d['members']), d['tasks_open'], d['tasks_all'], d['questions'],
            d['state']))
    for o in s['orders'][-8:]:
        print('  總機 %s  %s → %s  %s  %s  %s' % (o['id'], o['from'], o['to'], o['status'], o['task'] or '-',
                                              o['text'][:40].replace('\n', ' ')))
    print('董事收件匣：%d 封（company.py mail 看）' % s['board_letters'])


# ------------------------------------------------------------------ 開機、關機 ----

def _run(argv, env, check=True, timeout=300):
    r = subprocess.run([str(a) for a in argv], env=env, capture_output=True, text=True, timeout=timeout,
                       stdin=subprocess.DEVNULL)
    if check and r.returncode != 0:
        raise CompanyError('Failed', '%s 失敗（%d）：%s%s' % (' '.join(map(str, argv)), r.returncode, r.stdout[-2000:],
                                                          r.stderr[-2000:]))
    return r


def relay_proc_name(cdir):
    return 'company-relay-%08x' % (zlib.crc32(str(Path(os.path.abspath(str(cdir)))).encode()) & 0xffffffff)


def up(cdir, out=print):
    cdir = Path(os.path.abspath(str(cdir)))
    cfg = load(cdir)
    regular, _temp, _rows = headcount(cdir, cfg)
    if len(regular) > cfg['limits']['regular']:
        raise CompanyError('OverLimit', '正式員工 %d 人超過上限 %d；先改名冊或 company.json staff'
                           % (len(regular), cfg['limits']['regular']))
    names = all_member_names(cdir, cfg)
    dup = sorted({n for n in names if names.count(n) > 1})
    if dup:
        raise CompanyError('NameTaken', '部門之間有同名成員：%s' % '、'.join(dup))
    env = env_for(cdir, cfg)
    kenv = env_for(cdir, cfg, daemon=True)
    llm = cdir / cfg['llm']
    kcfg = {'pools': {'default': {'count': cfg['pools']['default']},
                      'llm': {'count': cfg['pools']['llm'], 'envs': {'AOS_LLM_CONFIG': str(llm)}}}}
    if os.environ.get('AOS_COST_HOME'):
        for p in kcfg['pools'].values():
            p.setdefault('envs', {})['AOS_COST_HOME'] = os.environ['AOS_COST_HOME']
    fmt.write_json(cdir / 'kernel.json', kcfg, indent=1)
    if not (cdir / 'K').exists():
        _run([CLI / 'aos-kernel', 'init', '--config', cdir / 'kernel.json'], kenv)
    else:
        for line in sync_kernel_pools(cdir, cfg):
            out(line)
    _run([CLI / 'aos', 'up'], kenv, timeout=120)
    write_hr_policy(cdir, cfg)
    out('kernel 開了：%s（default %d、llm %d 顆）' % (cdir / 'K', cfg['pools']['default'], cfg['pools']['llm']))
    for dept, tdir in sorted(team_dirs(cdir, cfg).items()):
        _run([CLI / 'aos-team', 'init', '--target', tdir], env)
        routes = cdir / 'config' / ('%s.routes.json' % dept)
        if routes.is_file():
            _run([CLI / 'aos-team', 'route', 'save', routes, '--target', tdir], env)
        roster = fmt.load_roster(tdir)
        for name in roster['members']:
            _persona(cdir, cfg, dept, tdir, name, env)
        _run([CLI / 'aos-team', 'start', '--target', tdir], env)
        out('%s 部開工：%s' % (dept, '、'.join(roster['members'])))
    out(register_relay(cdir, cfg, env))
    return 0


def sync_kernel_pools(cdir, cfg):
    """K 已經在：把 K/info.json 兩池的顆數對到 company.json 的 pools（aos-kernel cpu add／rm），
    再驗一次；對不上＝不開（astra 必修 13：市場層 slots 改了上限，下次 up 才真的生效）。回印出來的幾行。
    池的 envs（AOS_COST_HOME 等）cpu add／rm 不改：K 建好後改 envs 要手編 K/info.json。"""
    import aos_kernel_cpu
    from aos_kernel_info import load_info
    home = Path(cdir) / 'K'
    want = {'default': cfg['pools']['default'], 'llm': cfg['pools']['llm']}
    lines = []
    try:
        pools = (load_info(home).get('pools') or {})
        for name, n in want.items():
            cur = pools.get(name)
            if cur is None:
                env = ['AOS_LLM_CONFIG=%s' % (Path(cdir) / cfg['llm'])] if name == 'llm' else None
                lines.append(aos_kernel_cpu.cpu_add(home, name, n, env))
                continue
            have = int(cur.get('count') or 0)
            if n > have:
                lines.append(aos_kernel_cpu.cpu_add(home, name, n - have))
            elif n < have:
                lines.append(aos_kernel_cpu.cpu_rm(home, pool=name, count=have - n))
        got = {name: int(((load_info(home).get('pools') or {}).get(name) or {}).get('count') or 0) for name in want}
    except TeamError:
        raise
    except Exception as e:           # kernel 那邊的錯（NotLiteral、Busy…）：包成公司的錯，不開
        raise CompanyError('KernelSync', 'K/info.json 的池對不上 company.json：%s' % getattr(e, 'msg', e))
    if got != want:
        raise CompanyError('KernelSync', 'K/info.json 的池 %s 對不上 company.json 的 %s' % (got, want))
    return lines


def write_hr_policy(cdir, cfg):
    """這家的名額寫進這家的 HR 政策（K/hr/policy.json）：company.json 的 limits 是來源，HR 的擋點（init／start／spawn）
    與 status 用同一組數。policy 其他欄位（margin、expand）原樣留著。"""
    p = Path(cdir) / 'K' / 'hr' / 'policy.json'
    raw = fmt.read_json(p) if p.is_file() else {'_metainfo': {'_type': 'aos_hr_policy', '_version': 1}}
    raw.update({'stage': 'startup' if cfg['limits'] == STARTUP else 'grown', 'regular_max': cfg['limits']['regular'],
                'cpu_max': cfg['limits']['cpu'], 'llm_cpu_max': cfg['limits']['llm_cpu']})
    p.parent.mkdir(parents=True, exist_ok=True)
    fmt.write_json(p, raw, indent=2)
    return p


def _persona(cdir, cfg, dept, tdir, name, env):
    """公司層的人格（persona/<去掉前綴的名字>.md，再沒有就 persona/<部門>.md）接在模板人格後面；每個家只接一次。"""
    bare = name[len(cfg['prefix']):] if cfg['prefix'] and name.startswith(cfg['prefix']) else name
    src = None
    for cand in (cdir / 'persona' / ('%s.md' % bare), cdir / 'persona' / ('%s.md' % dept)):
        if cand.is_file():
            src = cand
            break
    if src is None:
        return
    mark = cdir / 'state' / 'persona' / name
    if mark.exists():
        return
    common = cdir / 'persona' / '_company.md'
    text = (common.read_text(encoding='utf-8') + '\n' if common.is_file() else '') + src.read_text(encoding='utf-8')
    text = text.replace('{prefix}', cfg['prefix']).replace('{dept}', dept)
    _run([CLI / 'aos-agent', 'persona', 'append', text, '--target', Path(tdir) / 'members' / name], env)
    mark.parent.mkdir(parents=True, exist_ok=True)
    mark.write_text('ok\n', encoding='utf-8')


def register_relay(cdir, cfg, env):
    import aos_client
    kernel = env['AOS_KERNEL_HOME']
    folder = Path(cdir) / 'switchboard'
    folder.mkdir(parents=True, exist_ok=True)
    inst = folder / 'relay.inst.json'
    fmt.write_json(inst, {'_metainfo': {'_type': 'posix', '_version': 1},
                          'argv': [sys.executable, str(LIB / 'aos_company.py'), 'relay', '--quiet',
                                   '--company', str(cdir)],
                          'cwd': str(cdir), 'envs': {'AOS_KERNEL_HOME': kernel, 'PYTHONDONTWRITEBYTECODE': '1'},
                          'stderr': {'$opt': ['append', 'mkdir'], '$val': str(folder / 'relay.err')}}, indent=2)
    name = relay_proc_name(cdir)
    res = aos_client.call(kernel, 'add', {'target': str(inst), 'name': name,
                                          'interval_ms': cfg['relay']['interval_s'] * 1000},
                          client='company', timeout_ms=10000)
    if 'error' in res and (res['error'].get('data') or {}).get('code') != 'AlreadyExists':
        raise CompanyError('Failed', '總機登記失敗：%s' % res['error'].get('message'))
    return '總機開了：%s（每 %d 秒一輪）' % (name, cfg['relay']['interval_s'])


def down(cdir, out=print):
    import aos_client
    cdir = Path(os.path.abspath(str(cdir)))
    cfg = load(cdir)
    env = env_for(cdir, cfg)
    if not (cdir / 'K').is_dir():
        out('kernel 沒開過')
        return 0
    res = aos_client.call(env['AOS_KERNEL_HOME'], 'rm', {'name': relay_proc_name(cdir)}, client='company', timeout_ms=10000)
    out('總機撤了：%s' % relay_proc_name(cdir) if 'error' not in (res or {}) else
        '總機沒撤到（%s；kernel 停了它也不會再跑）' % ((res.get('error') or {}).get('message') or res['error']))
    failed = []
    for dept, tdir in sorted(team_dirs(cdir, cfg).items()):
        if (Path(tdir) / 'members').is_dir():
            r = _run([CLI / 'aos-team', 'stop', '--target', tdir], env, check=False)
            if r.returncode != 0:
                failed.append('%s 部 aos-team stop 退 %d' % (dept, r.returncode))
            out('%s 部收工' % dept if r.returncode == 0 else '%s 部收工失敗（%d）' % (dept, r.returncode))
    r = _run([CLI / 'aos', 'down'], env_for(cdir, cfg, daemon=True), check=False, timeout=180)
    for line in (r.stdout or '').strip().splitlines():
        out(line)                                         # kernel 停了沒、daemon 停了沒（aos down 自己的摘要）
    if r.returncode != 0:
        failed.append('aos down 退 %d：%s' % (r.returncode, (r.stdout + r.stderr).strip()[-500:]))
    if failed:                      # 市場層靠這個退出碼決定能不能封存、放名額（astra 必修 4）
        out('沒停乾淨：' + '；'.join(failed))
        return 1
    out('kernel 關了')
    return 0


def order(cdir, text, to=None, out=print):
    cdir = Path(os.path.abspath(str(cdir)))
    cfg = load(cdir)
    if to is None:
        tdir = team_dirs(cdir, cfg)[cfg['front']]
        r = _run([CLI / 'aos-team', 'ask', text, '--target', tdir], env_for(cdir, cfg), check=False)
        out((r.stdout + r.stderr).strip())
        return r.returncode
    o = Switchboard(cdir, cfg).board_order(to, text)
    out('董事直接下單給 %s：總機 %s（%s，交給 %s）' % (to, o['id'], o['via'], o['to']['member']))
    return 0


def mail(cdir, out=print, last=20):
    sb = Switchboard(cdir)
    letters = sorted(sb.board_letters(), key=lambda x: x[1].get('at', ''))
    for dept, l in letters[-last:]:
        out('%s  %-4s %s → 董事  %s  %s  %s' % (fmt.short_time(l.get('at', '')) if l.get('at') else '-', dept,
                                              l.get('from'), l.get('status'), l.get('reply_to') or '-',
                                              l.get('text', '')[:120].replace('\n', ' ')))
    if not letters:
        out('董事收件匣是空的')
    return 0


# ------------------------------------------------------------------ 指令 ----

def main(argv=None, default_src=EXAMPLE):
    ap = argparse.ArgumentParser(prog='company.py', description='公司：幾支 aos 團隊＋機械總機（spec/team/company.md）')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('new', help='照樣板生一家公司')
    p.add_argument('dir')
    p.add_argument('--prefix', default='')
    p.add_argument('--project')
    p.add_argument('--llm-cpu', type=int)
    p.add_argument('--cpu', type=int)
    p.add_argument('--name')
    p.add_argument('--from', dest='src', default=str(default_src))
    for name in ('up', 'down', 'status', 'relay', 'mail'):
        p = sub.add_parser(name)
        p.add_argument('--company', '-C', default=os.environ.get('AOS_COMPANY_HOME', '.'))
        if name == 'status':
            p.add_argument('--json', action='store_true')
            p.add_argument('--no-kernel', action='store_true')
        if name == 'relay':
            p.add_argument('--quiet', action='store_true')
    p = sub.add_parser('order', help='董事下單：預設交給前台部門的門房；--to 直接交給某部門')
    p.add_argument('text', nargs='+')
    p.add_argument('--to')
    p.add_argument('--company', '-C', default=os.environ.get('AOS_COMPANY_HOME', '.'))
    p = sub.add_parser('answer', help='回某部門的題')
    p.add_argument('dept')
    p.add_argument('q')
    p.add_argument('text', nargs='+')
    p.add_argument('--company', '-C', default=os.environ.get('AOS_COMPANY_HOME', '.'))
    a = ap.parse_args(argv)
    try:
        if a.cmd == 'new':
            d = new(a.dir, a.src, a.prefix, a.project, a.llm_cpu, a.cpu, a.name)
            cfg = load(d)
            print('生好了 %s：%s；%s' % (d, '、'.join(all_member_names(d, cfg)), caps_line(
                {'regular': len(headcount(d, cfg)[0]), 'cpu': cfg['pools']['default'],   # cpu 不含 llm（同 status、HR）
                 'llm_cpu': cfg['pools']['llm']}, cfg['limits'])))
            return 0
        if a.cmd == 'up':
            return up(a.company)
        if a.cmd == 'down':
            return down(a.company)
        if a.cmd == 'status':
            s = status_data(a.company, use_kernel=not a.no_kernel)
            if a.json:
                print(json.dumps(s, ensure_ascii=False, indent=1))
            else:
                print_status(s)
            return 1 if s['over'] else 0
        if a.cmd == 'relay':
            log = Switchboard(a.company).round()
            if not a.quiet or log:
                for line in log:
                    print(line)
            return 0
        if a.cmd == 'mail':
            return mail(a.company)
        if a.cmd == 'order':
            return order(a.company, ' '.join(a.text), a.to)
        if a.cmd == 'answer':
            cfg = load(a.company)
            tdir = team_dirs(a.company, cfg).get(host_dept(cfg, a.dept) or '')
            if tdir is None:
                raise CompanyError('NotOpen', '%s 部門沒有團隊' % a.dept)
            r = _run([CLI / 'aos-team', 'answer', a.q, ' '.join(a.text), '--target', tdir], env_for(a.company, cfg),
                     check=False)
            print((r.stdout + r.stderr).strip())
            return r.returncode
    except TeamError as e:
        print('company.py: %s: %s' % (e.code, e.msg), file=sys.stderr)
        return 1
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
