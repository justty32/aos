"""公司設定：路徑與型別常數、收件部門標記、CompanyError／bad、company.json 讀驗、部門與團隊資料夾、窗口成員。"""
import os
from pathlib import Path
import re

import aos_team_format as fmt
from aos_team_format import TeamError

LIB = Path(__file__).resolve().parent      # 跟 aos_company.LIB 同一個資料夾（proto5/lib）


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
CEILING = {'regular': 100, 'cpu': 200, 'llm_cpu': 25}   # 董事 09-25 14:20：llm cpu 總額 20→25（五家各 5 剛好）
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
