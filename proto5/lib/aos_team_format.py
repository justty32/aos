"""團隊共用格式（spec/team/）：資料夾佈局、名冊 team.json、信、申請、任務單、問題的讀驗，以及 id、時間、寫檔。

這支只管「長怎樣、對不對」，不管誰什麼時候做什麼：
- 郵差（第 2 隊）讀 outbox 用 read_outbox_file()、投信用 mail_message()；
- 申請的處理在 aos_team_requests（登記表）＋各 kind 的模組；
- 任務狀態機在 aos_team_task。
純標準庫；不叫模型。
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time

ROSTER_TYPE = 'aos_team'
TASK_TYPE = 'aos_team_task'
QUESTION_TYPE = 'aos_team_question'
TEMPLATE_TYPE = 'aos_team_template'
ROUTES_TYPE = 'aos_team_routes'

NAME = re.compile(r'[a-z][a-z0-9_-]{0,31}\Z')
HUMAN, POST, BEAT = 'human', 'post', 'beat'
RESERVED = (HUMAN, POST, BEAT)
BEAT_MAY = ('handoff', 'cancel')          # 心跳（定時器）能寄的申請：派例行、撤掉自己派的
SENDER_LABEL = {HUMAN: '人', BEAT: '心跳（定時器）'}
STATUSES = ('REQUEST', 'DONE', 'BLOCKED', 'NEEDS-USER', 'FAILED', 'PROGRESS')
# outbox 裡的檔：<epoch ns>-<pid>-<寄件人>.json；系統（郵差）自己生的信可在後面加 .後綴（例 .e0）
OUTBOX_ID = re.compile(r'[0-9]{1,20}-[0-9]{1,10}-([a-z][a-z0-9_-]{0,31})\Z')
ANY_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._~-]{0,127}\Z')
TASK_ID = re.compile(r't-[0-9]{4,}(\.r[0-9]+)?\Z')
QUESTION_ID = re.compile(r'q-[0-9]{4,}\Z')
TEXT_LIMIT = 20000
DONE_KINDS = ('file_exists', 'table_filled', 'check', 'cmd_ok', 'judge')
CMD_TIMEOUT_MAX = 3600                   # cmd_ok 的 timeout_s 上限（秒；第二波 B 隊）
CMD_TIMEOUT_DEFAULT = 300
LIMIT_DEFAULTS = {'stale_minutes': 10, 'max_members': 6}
POST_DEFAULTS = {'interval_s': 5}       # 郵差多久巡一次信箱（秒；2026-09-24 使用者裁：預設 5）
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / 'templates'


class TeamError(Exception):
    """code：英文代號；msg：白話（帶檔名與位置）。"""

    def __init__(self, code, msg):
        super().__init__('%s: %s' % (code, msg))
        self.code, self.msg = code, msg


def bad(where, msg, code='FormatInvalid'):
    raise TeamError(code, '%s：%s' % (where, msg))


# ------------------------------------------------------------------ 佈局 ----

class Layout:
    """團隊資料夾裡每個固定位置（spec/team/layout.md）。只算路徑，不建。"""

    def __init__(self, team_dir):
        self.root = Path(os.path.abspath(os.path.expanduser(str(team_dir))))
        self.roster = self.root / 'team.json'
        self.members = self.root / 'members'
        self.team = self.root / 'team'
        self.post_sent = self.team / 'post' / 'sent'
        self.tasks = self.team / 'tasks'
        self.wait_user = self.team / 'wait-user'
        self.human_inbox = self.team / 'human'
        self.routes = self.team / 'routes.json'
        self.routines = self.team / 'routines.json'
        self.schedule = self.team / 'schedule.json'
        self.route_log = self.team / 'route.log'
        self.locks = self.team / 'locks'          # T-lock（09-24 W2C）：一個檔一把鎖，team/locks/<名>.json

    def member(self, name):
        return self.members / name

    def outbox(self, name):
        return self.team / 'outbox' / name

    def notes(self, name):
        """成員的長期筆記資料夾（模板 notes: true 的成員 init 時建、掛成牢裡的 /work/notes）。"""
        return self.team / 'notes' / name

    def events(self, name):
        """成員的事件紀錄：在成員家裡（aos_agent_events.EVENTS；寫的人是持那個家 tick 鎖的一方），不在 team/。"""
        return self.member(name) / 'log' / 'events.jsonl'

    def task(self, tid):
        return self.tasks / (tid + '.json')

    def question(self, qid):
        return self.wait_user / (qid + '.json')

    def lock(self, name):
        """鎖檔（09-24 astra M2 修）：name 可以含 `/`、中文（_check_lock_name 只擋 NUL、開頭 /、.. 段），
        直接拿來當檔名會撞「要先建子目錄」「.hidden 被 json_files 排除」「檔名位元組長度上限」三個坑；
        改成固定長度、非隱藏的平面檔名（sha256 十六進位），原名存在 JSON 內容裡（on_lock 寫、describe 讀）。"""
        h = hashlib.sha256(name.encode('utf-8')).hexdigest()
        return self.locks / (h + '.json')

    def skeleton(self, names):
        """init 要建的資料夾（不含成員的家）。"""
        dirs = [self.members, self.post_sent, self.tasks, self.wait_user, self.human_inbox]
        for n in list(names) + [HUMAN, BEAT]:
            dirs += [self.outbox(n), self.outbox(n) / 'done', self.outbox(n) / 'rejected']
        return dirs


# ------------------------------------------------------------ 時間、id、寫檔 ----

def now_iso(tz=None):
    """ISO 8601 含時區，到秒。tz：IANA 名字（例 Asia/Taipei）或 None＝本機。"""
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.astimezone(_zone(tz)).isoformat(timespec='seconds')


def _zone(tz):
    if not tz:
        return None
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(tz)
    except Exception:  # 沒有 tzdata 或名字不對：退回本機，不讓整件事失敗
        return None


def parse_iso(text):
    try:
        return datetime.datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def short_time(iso, tz=None):
    """'09-25 10:03'（信頭用）；讀不懂就原樣。"""
    t = parse_iso(iso)
    if t is None:
        return str(iso)
    if t.tzinfo is not None:
        t = t.astimezone(_zone(tz))
    return t.strftime('%m-%d %H:%M')


def new_id(sender):
    """outbox 檔的 id：<epoch ns>-<pid>-<寄件人>（同一行程同一奈秒不會叫兩次）。"""
    return '%d-%d-%s' % (time.time_ns(), os.getpid(), sender)


def write_json(path, obj, indent=None):
    """暫存檔（. 開頭）＋rename，整份原子換；給會被重寫的檔（任務單、問題、名冊）。"""
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.%s.' % path.name, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(obj, out, ensure_ascii=False, indent=indent, allow_nan=False)
            out.write('\n')
        os.replace(tmp, path)
        tmp = None
    finally:
        if tmp is not None:
            Path(tmp).unlink(missing_ok=True)


def write_new(path, obj, indent=None):
    """只在不存在時建（暫存檔＋link）；建了回 True，已在回 False（不覆蓋）。給 outbox 檔與紀錄檔。"""
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.%s.' % path.name, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(obj, out, ensure_ascii=False, indent=indent, allow_nan=False)
            out.write('\n')
        try:
            os.link(tmp, path)
        except FileExistsError:
            return False
        return True
    finally:
        Path(tmp).unlink(missing_ok=True)


def read_json(path, where=None):
    path = Path(path)
    try:
        raw = path.read_text(encoding='utf-8')
    except FileNotFoundError:
        raise TeamError('NotFound', '%s 不存在' % path)
    except (OSError, UnicodeError) as e:
        raise TeamError('ReadFailed', '讀不到 %s：%s' % (path, e))
    try:
        return json.loads(raw)
    except ValueError as e:
        raise TeamError('JsonSyntax', '%s 不是合法 JSON：%s' % (where or path, e))


def json_files(folder):
    """資料夾裡要處理的 *.json（不含 . 開頭的暫存檔），照名字排。"""
    try:
        return sorted(p for p in Path(folder).iterdir()
                      if p.name.endswith('.json') and not p.name.startswith('.') and p.is_file())
    except FileNotFoundError:
        return []


# ---------------------------------------------------------------- 小驗證 ----

def _obj(value, where):
    if not isinstance(value, dict):
        bad(where, '要是 JSON 物件')
    return value


def _str(value, where, *, empty=False, limit=None):
    if not isinstance(value, str) or (not empty and not value.strip()):
        bad(where, '要是非空字串')
    if '\0' in value:
        bad(where, '不能含 NUL')
    if limit is not None and len(value) > limit:
        bad(where, '太長（%d 字，上限 %d）' % (len(value), limit))
    return value


def _int(value, where, lo=None, hi=None):
    if not isinstance(value, int) or isinstance(value, bool):
        bad(where, '要是整數')
    if (lo is not None and value < lo) or (hi is not None and value > hi):
        bad(where, '要在 %s～%s 之間' % (lo, hi))
    return value


def _opt_str(value, where):
    return None if value is None else _str(value, where)


def _metainfo(obj, kind, where):
    meta = obj.get('_metainfo')
    if meta is None:
        return
    if not (isinstance(meta, dict) and meta.get('_type') == kind and meta.get('_version') == 1
            and not isinstance(meta.get('_version'), bool)):
        bad(where + '._metainfo', '要是 {"_type": "%s", "_version": 1}' % kind)


def check_name(name, where, *, member=True):
    if not isinstance(name, str) or not NAME.match(name):
        bad(where, '名字 %r 只能用小寫英數、底線、連字號，英文字母開頭，最長 32' % (name,))
    if member and name in RESERVED:
        bad(where, '%s 是保留名（%s），不能當成員名' % (name, '、'.join(RESERVED)))
    return name


def _unknown(obj, allowed, where):
    extra = sorted(set(obj) - set(allowed))
    if extra:
        bad(where, '不認得的欄位 %s（可用：%s）' % ('、'.join(extra), '、'.join(allowed)))


# ------------------------------------------------------------------ 名冊 ----

MEMBER_KEYS = ('template', 'model', 'mail_to', 'mounts', 'tools')
ROSTER_KEYS = ('_metainfo', 'project', 'tz', 'members', 'limits', 'post', 'cmd_ok', 'spawn')


def validate_roster(obj, where='team.json'):
    """驗 team.json，回補好預設值的新物件（原物件不動）。"""
    _obj(obj, where)
    _unknown(obj, ROSTER_KEYS, where)
    _metainfo(obj, ROSTER_TYPE, where)
    out = {'project': _str(obj.get('project'), where + '.project'),
           'tz': _opt_str(obj.get('tz'), where + '.tz'),
           'members': {}, 'limits': dict(LIMIT_DEFAULTS), 'post': dict(POST_DEFAULTS),
           'cmd_ok': _cmd_whitelist(obj.get('cmd_ok', []), where + '.cmd_ok'),
           'spawn': _spawn_cfg(obj.get('spawn', {}), where + '.spawn')}
    post = _obj(obj.get('post', {}), where + '.post')
    _unknown(post, tuple(POST_DEFAULTS), where + '.post')
    if 'interval_s' in post:
        out['post']['interval_s'] = _int(post['interval_s'], where + '.post.interval_s', 1, 3600)
    members = _obj(obj.get('members'), where + '.members')
    if not members:
        bad(where + '.members', '至少要有一個成員')
    limits = _obj(obj.get('limits', {}), where + '.limits')
    _unknown(limits, tuple(LIMIT_DEFAULTS), where + '.limits')
    for k, v in limits.items():
        out['limits'][k] = _int(v, '%s.limits.%s' % (where, k), 1, 100000)
    if len(members) > out['limits']['max_members']:
        bad(where + '.members', '%d 個成員，超過 limits.max_members=%d' % (len(members), out['limits']['max_members']))
    for name, m in members.items():
        w = '%s.members.%s' % (where, name)
        check_name(name, w)
        _obj(m, w)
        _unknown(m, MEMBER_KEYS, w)
        mail_to = m.get('mail_to', [])
        if not isinstance(mail_to, list) or not all(isinstance(x, str) for x in mail_to):
            bad(w + '.mail_to', '要是名字的陣列')
        for x in mail_to:
            if x not in (HUMAN, BEAT) and x not in members:
                bad(w + '.mail_to', '%s 不在名冊裡（也不是 human、beat）' % x)
            if x == name:
                bad(w + '.mail_to', '不能寄給自己')
        mounts = _mounts(m.get('mounts', {}), w + '.mounts')
        tools = m.get('tools', [])
        if not isinstance(tools, list):
            bad(w + '.tools', '要是陣列')
        for i, t in enumerate(tools):
            _obj(t, '%s.tools[%d]' % (w, i))
            _unknown(t, TOOL_ENTRY_KEYS, '%s.tools[%d]' % (w, i))
            _str(t.get('pack'), '%s.tools[%d].pack' % (w, i))
        out['members'][name] = {
            'template': _str(m.get('template'), w + '.template'),
            'model': _opt_str(m.get('model'), w + '.model'),
            'mail_to': list(dict.fromkeys(mail_to)),
            'mounts': dict(mounts), 'tools': list(tools)}
    return out


def load_roster(team_dir):
    lay = Layout(team_dir)
    return validate_roster(read_json(lay.roster), str(lay.roster))


def project_dir(team_dir, roster):
    """project 相對 team.json 所在資料夾；回絕對路徑（不檢查存在）。"""
    p = os.path.expanduser(roster['project'])
    return Path(os.path.abspath(os.path.join(Layout(team_dir).root, p)))


def members_by_template(roster, template):
    return [n for n, m in roster['members'].items() if m['template'] == template]


# ------------------------------------------------------------ 信與申請 ----

LETTER_KEYS = ('id', 'from', 'to', 'status', 'reply_to', 'rev', 'text', 'at')


def validate_letter(obj, where='letter'):
    _obj(obj, where)
    _unknown(obj, LETTER_KEYS, where)
    _str(obj.get('id'), where + '.id')
    if not ANY_ID.match(obj['id']):
        bad(where + '.id', 'id %r 只能用英數與 . _ ~ -' % obj['id'])
    _str(obj.get('from'), where + '.from')
    _str(obj.get('to'), where + '.to')
    if obj.get('status') not in STATUSES:
        bad(where + '.status', '%r 不是六個之一：%s' % (obj.get('status'), '、'.join(STATUSES)), 'BadStatus')
    _opt_str(obj.get('reply_to'), where + '.reply_to')
    if obj.get('rev') is not None:
        _int(obj['rev'], where + '.rev', 1)
    _str(obj.get('text'), where + '.text', limit=TEXT_LIMIT)
    _str(obj.get('at'), where + '.at')
    return obj


def validate_cmd(run, where):
    """cmd_ok 的指令：非空字串陣列；第一格是指令名（不含 /，在牢裡照 PATH 找），每格不含 NUL。"""
    if not isinstance(run, list) or not run or not all(isinstance(x, str) and x and '\0' not in x for x in run):
        bad(where, '要是非空字串陣列，例 ["python3", "-m", "unittest"]')
    if '/' in run[0] or run[0].startswith('-'):
        bad(where, '第一格要是指令名（不含 /、不以 - 開頭），例 python3、make；在牢裡照 PATH 找')
    return list(run)


def _spawn_cfg(value, where):
    """team.json 的 spawn（第三波 W3-1，spawn.md）：{"templates": [模板名…]}＝成員能申請生哪幾種新成員；
    沒寫＝[]（不准生）。只收內建模板名（不含 /）：自訂模板的資料夾可能在模型改得到的地方。"""
    _obj(value, where)
    _unknown(value, ('templates',), where)
    names = value.get('templates', [])
    if not isinstance(names, list) or not all(isinstance(x, str) and NAME.match(x) for x in names):
        bad(where + '.templates', '要是內建模板名的陣列（小寫英數、底線、連字號，不含 /）')
    return {'templates': list(dict.fromkeys(names))}


def _cmd_whitelist(value, where):
    """team.json 的 cmd_ok：人寫的白名單 [{"run": [...], "timeout_s": 秒}]；單子上的 cmd_ok 要對得上其中一條。"""
    if not isinstance(value, list):
        bad(where, '要是陣列 [{"run": [...], "timeout_s": 秒}]')
    out = []
    for i, e in enumerate(value):
        w = '%s[%d]' % (where, i)
        _obj(e, w)
        _unknown(e, ('run', 'timeout_s'), w)
        run = validate_cmd(e.get('run'), w + '.run')
        t = _int(e.get('timeout_s', CMD_TIMEOUT_DEFAULT), w + '.timeout_s', 1, CMD_TIMEOUT_MAX)
        out.append({'run': run, 'timeout_s': t})
    return out


def cmd_allowed(roster, item):
    """單子上的 cmd_ok 條目對得上名冊白名單的哪一條：回那一條；對不上＝None。
    run 要整串一樣；單子上的 timeout_s（沒寫＝白名單那條的）不能超過白名單的。"""
    for e in roster.get('cmd_ok', []):
        if e['run'] == item.get('run') and item.get('timeout_s', e['timeout_s']) <= e['timeout_s']:
            return e
    return None


def validate_done_when(items, where='done_when'):
    if not isinstance(items, list) or not items:
        bad(where, '要是非空陣列')
    for i, it in enumerate(items):
        w = '%s[%d]' % (where, i)
        _obj(it, w)
        kind = it.get('kind')
        if kind not in DONE_KINDS:
            bad(w + '.kind', '%r 不是 %s 之一' % (kind, '、'.join(DONE_KINDS)))
        if kind in ('file_exists', 'table_filled'):
            _str(it.get('path'), w + '.path')
        elif kind == 'check':
            _str(it.get('name'), w + '.name')
            if 'args' in it:
                _obj(it['args'], w + '.args')
        elif kind == 'cmd_ok':
            _unknown(it, ('kind', 'run', 'timeout_s'), w)
            validate_cmd(it.get('run'), w + '.run')
            if 'timeout_s' in it:
                _int(it['timeout_s'], w + '.timeout_s', 1, CMD_TIMEOUT_MAX)
        else:
            _str(it.get('text'), w + '.text', limit=2000)
    return items


def _handoff_body(obj, where):
    check_name(obj.get('assignee'), where + '.assignee')
    _str(obj.get('workflow'), where + '.workflow')
    _str(obj.get('goal'), where + '.goal', limit=TEXT_LIMIT)
    _opt_str(obj.get('facts'), where + '.facts')
    validate_done_when(obj.get('done_when'), where + '.done_when')
    if obj.get('max_attempts') is not None:
        _int(obj['max_attempts'], where + '.max_attempts', 1, 10)
    if obj.get('deadline_minutes') is not None:
        _int(obj['deadline_minutes'], where + '.deadline_minutes', 1, 7 * 24 * 60)


ASK_TAGS = ('access', 'persona')   # 借用 kind=ask 的申請種類（09-24 W2C）：aos-team wait ls 靠它挑前綴，不猜字串


def _ask_body(obj, where):
    _str(obj.get('question'), where + '.question', limit=4000)
    opts = obj.get('options')
    if opts is not None:
        if not isinstance(opts, list) or not opts or not all(isinstance(o, str) and o.strip() for o in opts):
            bad(where + '.options', '要是非空字串的陣列')
    default = _opt_str(obj.get('default'), where + '.default')
    if default is not None and opts is not None and default not in opts:
        bad(where + '.default', '%r 不在 options 裡' % default)
    _opt_str(obj.get('reply_to'), where + '.reply_to')
    tag = obj.get('tag')
    if tag is not None and tag not in ASK_TAGS:
        bad(where + '.tag', '要是 %s 之一' % '／'.join(ASK_TAGS))


def _answer_body(obj, where):
    q = _str(obj.get('q'), where + '.q')
    if not QUESTION_ID.match(q):
        bad(where + '.q', '%r 不是問題編號（q-0001 這種）' % q)
    _str(obj.get('text'), where + '.text', limit=TEXT_LIMIT)


def _task_ref(obj, where, key='task'):
    t = _str(obj.get(key), '%s.%s' % (where, key))
    if not TASK_ID.match(t):
        bad('%s.%s' % (where, key), '%r 不是任務單號（t-0001 或審查子單 t-0001.r1）' % t)


def _cancel_body(obj, where):
    _task_ref(obj, where)
    _opt_str(obj.get('reason'), where + '.reason')


def _reassign_body(obj, where):
    _task_ref(obj, where)
    check_name(obj.get('assignee'), where + '.assignee')


def _review_body(obj, where):
    _task_ref(obj, where)
    items = obj.get('items')
    if not isinstance(items, list) or not items:
        bad(where + '.items', '要是非空陣列')
    seen = set()
    for k, it in enumerate(items):
        w = '%s.items[%d]' % (where, k)
        _obj(it, w)
        _int(it.get('i'), w + '.i', 0)
        if it['i'] in seen:
            bad(w + '.i', '第 %d 條重複' % it['i'])
        seen.add(it['i'])
        if not isinstance(it.get('pass'), bool):
            bad(w + '.pass', '要是 true／false')
        _str(it.get('why'), w + '.why', limit=2000)


# kind → (這個 kind 自己的欄位, 驗法)。第 2、4 隊的 kind 在自己的模組驗，這裡只列名字（body=None：只驗共同欄位）。
REQUEST_KINDS = {
    'handoff': (('assignee', 'workflow', 'goal', 'facts', 'done_when', 'max_attempts', 'deadline_minutes'),
                _handoff_body),
    'ask': (('question', 'options', 'default', 'reply_to', 'tag'), _ask_body),
    'answer': (('q', 'text'), _answer_body),
    'cancel': (('task', 'reason'), _cancel_body),
    'reassign': (('task', 'assignee'), _reassign_body),
    'review_result': (('task', 'items'), _review_body),
}
REQUEST_COMMON = ('id', 'from', 'kind', 'at')


def validate_request(obj, where='request'):
    _obj(obj, where)
    kind = obj.get('kind')
    if not isinstance(kind, str):
        bad(where + '.kind', '要是字串', 'UnknownKind')
    if kind not in REQUEST_KINDS:
        from aos_team_requests import KINDS   # 別隊登記的 kind 也認
        if kind not in KINDS:
            bad(where + '.kind', '不認得的申請種類 %r' % (kind,), 'UnknownKind')
        _str(obj.get('id'), where + '.id')
        _str(obj.get('from'), where + '.from')
        _str(obj.get('at'), where + '.at')
        return obj
    keys, body = REQUEST_KINDS[kind]
    _unknown(obj, REQUEST_COMMON + keys, where)
    _str(obj.get('id'), where + '.id')
    if not ANY_ID.match(obj['id']):
        bad(where + '.id', 'id %r 只能用英數與 . _ ~ -' % obj['id'])
    _str(obj.get('from'), where + '.from')
    _str(obj.get('at'), where + '.at')
    body(obj, where)
    return obj


def read_outbox_file(path, roster):
    """郵差讀 team/outbox/<寄件人>/<id>.json：回 ('letter'|'request', obj)。

    身分看檔在哪個 outbox（資料夾名），信裡的 from 只是抄寫、對不上就 NotSender；
    檔名要是 <id>.json 且 id 的寄件人段＝資料夾名；信的 to 要在寄件人的 mail_to（human 可寄給任何成員）。
    """
    path = Path(path)
    sender = path.parent.name
    # 退信會寄回給寄件人（在牢裡看不到主機路徑）：訊息裡只寫團隊資料夾裡的相對位置（wall-r1 試玩）
    where = 'outbox/%s/%s' % (sender, path.name)
    if sender not in (HUMAN, BEAT) and sender not in roster['members']:
        bad(where, '寄件人 %s 不在名冊裡' % sender, 'NotSender')
    stem = path.name[:-5] if path.name.endswith('.json') else path.name
    m = OUTBOX_ID.match(stem)
    if not m or m.group(1) != sender:
        bad(where, '檔名要是 <epoch ns>-<pid>-%s.json' % sender, 'BadId')
    obj = read_json(path, where)
    _obj(obj, where)
    if obj.get('id') != stem:
        bad(where + '.id', 'id 要跟檔名一樣（%s）' % stem, 'BadId')
    if obj.get('from') != sender:
        bad(where + '.from', '信在 %s 的 outbox，from 卻寫 %r' % (sender, obj.get('from')), 'NotSender')
    if 'kind' in obj:
        validate_request(obj, where)
        return 'request', obj
    validate_letter(obj, where)
    to = obj['to']
    if to == BEAT and sender in roster['members']:
        pass                              # 誰都能回信給心跳（它派的例行單回報 DONE 用；郵差只記下、不投）
    elif sender == BEAT:
        if to != HUMAN and to not in roster['members']:
            bad(where + '.to', '%s 不在名冊裡' % to, 'BadRecipient')
    elif sender == HUMAN:
        if to not in roster['members']:
            bad(where + '.to', '%s 不在名冊裡' % to, 'BadRecipient')
    elif to not in roster['members'][sender]['mail_to']:
        bad(where + '.to', '%s 不能寄給 %s（mail_to：%s）'
            % (sender, to, '、'.join(roster['members'][sender]['mail_to']) or '（空）'), 'BadRecipient')
    return 'letter', obj


# ------------------------------------------------------------------ 信頭 ----

def render_header(letter, tz=None):
    """收件人看到的第一行：【來信 lead → worker-1 · REQUEST · t-0007 rev1 · 09-25 10:03】。
    人回答問題：【人 → worker-1 · 回覆 q-0003 · 09-25 10:03】。"""
    when = short_time(letter.get('at'), tz)
    reply = letter.get('reply_to')
    if letter.get('from') == HUMAN and isinstance(reply, str) and QUESTION_ID.match(reply):
        return '【人 → %s · 回覆 %s · %s】' % (letter['to'], reply, when)
    ref = ''
    if reply:
        ref = ' · %s%s' % (reply, ' rev%d' % letter['rev'] if letter.get('rev') else '')
    sender = SENDER_LABEL.get(letter.get('from'), letter.get('from'))
    return '【來信 %s → %s · %s%s · %s】' % (sender, letter['to'], letter['status'], ref, when)


def mail_message(letter, tz=None):
    """投進收件人 input/mail-<id>.json 的內容：一則 user 訊息，第一行是信頭。"""
    return {'role': 'user', 'content': render_header(letter, tz) + '\n' + letter['text']}


def mail_filename(letter_id):
    return 'mail-%s.json' % letter_id


def already_delivered(member_home, filename):
    """投之前查「這封是不是其實已經投過」（spec/team/mail.md〈去重〉）：回 None（沒投過）或說明在哪。

    三處都算投過：還在 input/<檔名>；已被收走、封存在 input/done/<檔名>.<消費 id>.done；
    收件人正在收（state.json 的 intake.files 或 consuming 的 src 是它）。
    """
    inbox = Path(member_home) / 'input'
    if (inbox / filename).exists():
        return 'input'
    done = inbox / 'done'
    try:
        if any(p.name.startswith(filename + '.') and p.name.endswith('.done') for p in done.iterdir()):
            return 'done'
    except FileNotFoundError:
        pass
    try:
        st = json.loads((Path(member_home) / 'state.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        st = {}
    pairs = []
    if isinstance(st, dict):
        if isinstance(st.get('intake'), dict) and isinstance(st['intake'].get('files'), list):
            pairs += st['intake']['files']
        if isinstance(st.get('consuming'), list):
            pairs += st['consuming']
    for pair in pairs:
        if isinstance(pair, dict) and isinstance(pair.get('src'), str) and os.path.basename(pair['src']) == filename:
            return 'intake'
    return None


# -------------------------------------------------------------- 任務與問題 ----

TICKET_STATUSES = ('queued', 'sent', 'working', 'verifying', 'reviewing', 'done',
                   'blocked', 'waiting_user', 'failed', 'cancelled')
TERMINAL = ('done', 'failed', 'cancelled')
TICKET_KEYS = ('_metainfo', 'id', 'parent', 'request', 'opened_by', 'assignee', 'rev', 'attempt',
               'max_attempts', 'workflow', 'goal', 'facts', 'done_when', 'status', 'waiting_on',
               'created_at', 'updated_at', 'deadline', 'review_of', 'verify', 'review', 'history')


def validate_ticket(obj, where='task'):
    _obj(obj, where)
    _unknown(obj, TICKET_KEYS, where)
    _metainfo(obj, TASK_TYPE, where)
    tid = _str(obj.get('id'), where + '.id')
    if not TASK_ID.match(tid):
        bad(where + '.id', '%r 不是任務單號' % tid)
    if obj.get('status') not in TICKET_STATUSES:
        bad(where + '.status', '%r 不是 %s 之一' % (obj.get('status'), '、'.join(TICKET_STATUSES)))
    check_name(obj.get('assignee'), where + '.assignee')
    for k in ('rev', 'attempt', 'max_attempts'):
        _int(obj.get(k), '%s.%s' % (where, k), 1)
    validate_done_when(obj.get('done_when'), where + '.done_when')
    if not isinstance(obj.get('history'), list):
        bad(where + '.history', '要是陣列')
    return obj


def validate_question(obj, where='question'):
    _obj(obj, where)
    _metainfo(obj, QUESTION_TYPE, where)
    qid = _str(obj.get('id'), where + '.id')
    if not QUESTION_ID.match(qid):
        bad(where + '.id', '%r 不是問題編號' % qid)
    if obj.get('status') not in ('open', 'answered', 'cancelled'):
        bad(where + '.status', '要是 open／answered／cancelled')
    _str(obj.get('from'), where + '.from')
    _str(obj.get('question'), where + '.question')
    return obj


def next_number(folder, prefix):
    """資料夾裡 <prefix>NNNN.json 的下一號（只有一個寫的人：郵差）。"""
    top = 0
    pat = re.compile(re.escape(prefix) + r'([0-9]+)\.json\Z')
    try:
        for p in Path(folder).iterdir():
            m = pat.match(p.name)
            if m:
                top = max(top, int(m.group(1)))
    except FileNotFoundError:
        pass
    return '%s%04d' % (prefix, top + 1)


# ------------------------------------------------------------------ 模板 ----

def template_dir(name):
    """模板名字（不含 /）→ proto5/templates/<名>/；含 / → 那個資料夾。"""
    return Path(os.path.abspath(os.path.expanduser(name))) if '/' in name else TEMPLATES_DIR / name


def template_may(name):
    """模板允許寄的申請種類（template.json 的 may）；讀不到＝空。"""
    try:
        obj = read_json(template_dir(name) / 'template.json')
    except TeamError:
        return ()
    may = obj.get('may') if isinstance(obj, dict) else None
    return tuple(x for x in may if isinstance(x, str)) if isinstance(may, list) else ()


def may_send(roster, sender, kind):
    """寄件人能不能寄這種申請：human 什麼都能；成員看自己模板的 may。"""
    if sender == HUMAN:
        return True
    if sender == BEAT:
        return kind in BEAT_MAY
    m = roster['members'].get(sender)
    return m is not None and kind in template_may(m['template'])


# --------------------------------------------------------- 模板、門房規則 ----

TEMPLATE_KEYS = ('_metainfo', 'description', 'system', 'team', 'project', 'notes', 'may', 'llm', 'tick', 'tools',
                 'mounts')
TOOL_ENTRY_KEYS = ('pack', 'only', 'team', 'optional')
RESERVED_MOUNTS = ('ws', 'outbox', 'board', 'notes', 'mem')   # notes、mem：模板 notes: true 時 init 內建掛


def _mounts(mounts, where):
    _obj(mounts, where)
    for mk, mv in mounts.items():
        if not re.match(r'[a-z0-9_-]+\Z', mk) or mk in RESERVED_MOUNTS:
            bad(where, '名字 %r 不行（[a-z0-9_-]+，且 ws／outbox／board／notes／mem 是保留的）' % mk)
        if not (isinstance(mv, str) and mv) and not (
                isinstance(mv, dict) and set(mv) == {'$opt', '$val'} and mv['$opt'] == 'ro'
                and isinstance(mv['$val'], str) and mv['$val']):
            bad('%s.%s' % (where, mk), '要是路徑字串或 {"$opt": "ro", "$val": 路徑}')
    return dict(mounts)


def validate_template(obj, where='template.json'):
    _obj(obj, where)
    _unknown(obj, TEMPLATE_KEYS, where)
    _metainfo(obj, TEMPLATE_TYPE, where)
    _str(obj.get('description'), where + '.description')
    _str(obj.get('system'), where + '.system')
    if not isinstance(obj.get('team', False), bool):
        bad(where + '.team', '要是 true／false')
    if obj.get('project', 'rw') not in ('rw', 'ro'):
        bad(where + '.project', '要是 rw 或 ro')
    if not isinstance(obj.get('notes', False), bool):
        bad(where + '.notes', '要是 true／false')
    if obj.get('notes') and not obj.get('team'):
        bad(where + '.notes', 'notes: true 只給團隊模板（掛的是 team/notes/<名>/）')
    may = obj.get('may', [])
    if not isinstance(may, list) or not all(isinstance(x, str) for x in may):
        bad(where + '.may', '要是申請種類名字的陣列')
    llm = _obj(obj.get('llm', {}), where + '.llm')
    _unknown(llm, ('model', 'timeout_ms'), where + '.llm')
    if 'model' in llm:
        _str(llm['model'], where + '.llm.model')
    if 'timeout_ms' in llm:
        _int(llm['timeout_ms'], where + '.llm.timeout_ms', 1)
    tick = _obj(obj.get('tick', {}), where + '.tick')
    _unknown(tick, ('interval_ms',), where + '.tick')
    if 'interval_ms' in tick:
        _int(tick['interval_ms'], where + '.tick.interval_ms', 1)
    tools = obj.get('tools', [])
    if not isinstance(tools, list):
        bad(where + '.tools', '要是陣列')
    for i, t in enumerate(tools):
        w = '%s.tools[%d]' % (where, i)
        _obj(t, w)
        _unknown(t, TOOL_ENTRY_KEYS, w)
        _str(t.get('pack'), w + '.pack')
        only = t.get('only')
        if only is not None and (not isinstance(only, list) or not only
                                 or not all(isinstance(x, str) for x in only)):
            bad(w + '.only', '要是非空的工具名陣列')
        for k in ('team', 'optional'):
            if not isinstance(t.get(k, False), bool):
                bad('%s.%s' % (w, k), '要是 true／false')
    _mounts(obj.get('mounts', {}), where + '.mounts')
    return obj


def load_template(name):
    folder = template_dir(name)
    path = folder / 'template.json'
    if not path.is_file():
        known = sorted(p.name for p in TEMPLATES_DIR.iterdir() if (p / 'template.json').is_file()) \
            if TEMPLATES_DIR.is_dir() else []
        raise TeamError('NoSuchTemplate', '找不到模板 %s（%s）；內建的有：%s' % (name, path, '、'.join(known) or '（無）'))
    return folder, validate_template(read_json(path), str(path))


ROUTE_KEYS = ('name', 'pattern', 'do', 'run', 'tool', 'args', 'project', 'handoff', 'tests')
DEFAULT_NEGATIONS = ('不要', '別', '取消', '不用', '勿', '不准')
ROUTE_RUN_FORBIDDEN = ('ask', 'init', 'rm', 'start', 'stop')   # 門房的 run 不能跑這幾個子命令


def validate_routes(obj, where='routes.json'):
    """只驗形狀與正規式編不編得過；例句由 aos_team_route 跑。回 (否定詞, [(規則, 編好的正規式)…])。"""
    _obj(obj, where)
    _unknown(obj, ('_metainfo', 'negations', 'routes'), where)
    _metainfo(obj, ROUTES_TYPE, where)
    neg = obj.get('negations', list(DEFAULT_NEGATIONS))
    if not isinstance(neg, list) or not all(isinstance(x, str) and x for x in neg):
        bad(where + '.negations', '要是非空字串的陣列')
    routes = obj.get('routes', [])
    if not isinstance(routes, list):
        bad(where + '.routes', '要是陣列')
    names, out = set(), []
    for i, r in enumerate(routes):
        w = '%s.routes[%d]' % (where, i)
        _obj(r, w)
        _unknown(r, ROUTE_KEYS, w)
        name = _str(r.get('name'), w + '.name')
        if name in names:
            bad(w + '.name', '名字 %s 重複' % name)
        names.add(name)
        try:
            rx = re.compile(_str(r.get('pattern'), w + '.pattern'))
        except re.error as e:
            bad(w + '.pattern', '正規式編不過：%s' % e)
        do = r.get('do')
        if do == 'tool':
            if ('run' in r) == ('tool' in r):
                bad(w, 'do=tool 要恰好給 run（aos-team 子命令）或 tool（"包/工具"）其中一個')
            if 'run' in r and (not isinstance(r['run'], list) or not r['run']
                               or not all(isinstance(x, str) for x in r['run'])):
                bad(w + '.run', '要是非空字串陣列，例 ["task", "ls"]')
            if 'run' in r and r['run'][0] in ROUTE_RUN_FORBIDDEN:
                bad(w + '.run', '門房不能跑 aos-team %s' % r['run'][0])
            if 'run' in r and re.search(r'\{\w+\}', r['run'][0]):
                bad(w + '.run', '第一格（子命令）不能用 {群組}：子命令要寫死')
            if 'tool' in r and not re.match(r'[A-Za-z0-9_-]+/[A-Za-z0-9_-]+\Z', str(r['tool'])):
                bad(w + '.tool', '要寫成 "包/工具"')
            if 'args' in r:
                _obj(r['args'], w + '.args')
            if 'project' in r and ('tool' not in r or r['project'] not in ('ro', 'rw')):
                bad(w + '.project', '只給 tool 規則用：ro（預設，專案唯讀掛進牢）或 rw')
        elif do == 'handoff':
            h = _obj(r.get('handoff'), w + '.handoff')
            _unknown(h, REQUEST_KINDS['handoff'][0], w + '.handoff')
            who = h.get('assignee')
            if isinstance(who, str) and '{' not in who:    # 寫死的負責人：保留名（human、post、beat）不能收單
                check_name(who, w + '.handoff.assignee')
        else:
            bad(w + '.do', '要是 tool 或 handoff')
        tests = _obj(r.get('tests'), w + '.tests')
        _unknown(tests, ('hit', 'miss'), w + '.tests')
        for k in ('hit', 'miss'):
            v = tests.get(k)
            if not isinstance(v, list) or not v or not all(isinstance(x, str) and x.strip() for x in v):
                bad('%s.tests.%s' % (w, k), '至少要一句例句（字串陣列）')
        out.append((r, rx))
    return neg, out


# ------------------------------------------------------------ 命令列驗檔 ----

def detect(obj):
    """看檔的樣子決定用哪一種驗：_metainfo._type，或有 kind（申請）、有 status＋to（信）。"""
    meta = obj.get('_metainfo') if isinstance(obj, dict) else None
    kind = meta.get('_type') if isinstance(meta, dict) else None
    table = {ROSTER_TYPE: ('roster', validate_roster), TASK_TYPE: ('task', validate_ticket),
             QUESTION_TYPE: ('question', validate_question), TEMPLATE_TYPE: ('template', validate_template),
             ROUTES_TYPE: ('routes', validate_routes)}
    if kind in table:
        return table[kind]
    if isinstance(obj, dict) and 'kind' in obj:
        return 'request', validate_request
    if isinstance(obj, dict) and 'status' in obj and 'to' in obj:
        return 'letter', validate_letter
    return None, None


def main(argv=None):
    import sys
    paths = sys.argv[1:] if argv is None else argv
    if not paths:
        print('用法：python3 aos_team_format.py 檔…  （驗名冊、信、申請、任務單、問題、模板、門房規則）')
        return 2
    failed = 0
    for p in paths:
        try:
            obj = read_json(p)
            name, fn = detect(obj)
            if fn is None:
                raise TeamError('Unknown', '%s 看不出是哪種檔（沒有 _metainfo._type，也不像信或申請）' % p)
            fn(obj, str(p))
            print('ok  %-8s %s' % (name, p))
        except TeamError as e:
            failed += 1
            print('bad %s: %s' % (e.code, e.msg))
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
