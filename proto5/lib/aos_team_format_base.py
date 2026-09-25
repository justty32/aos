"""團隊格式的底：型別名與保留名、id 規則、各種上限與預設、TeamError／bad、資料夾佈局 Layout、欄位小驗證。"""
import hashlib
import os
from pathlib import Path
import re


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
