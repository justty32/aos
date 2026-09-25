"""模板與門房規則：內建模板在哪、模板的 may 與 spawn 政策、誰能寄給誰、模板 template.json 與門房 routes.json 的讀驗。"""
import os
from pathlib import Path
import re

from aos_team_format_base import (
    _int, _metainfo, _obj, _str, _unknown, bad, BEAT, BEAT_MAY, check_name, HUMAN, NAME,
    ROUTES_TYPE, TeamError, TEMPLATE_TYPE, TEMPLATES_DIR
)
from aos_team_format_io import read_json
from aos_team_format_cmd import _mounts, TOOL_ENTRY_KEYS
from aos_team_format_letter import REQUEST_KINDS


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


def builtin_templates():
    """proto5/templates/ 底下有 template.json 的資料夾名（排序）。"""
    try:
        return sorted(p.name for p in TEMPLATES_DIR.iterdir() if NAME.match(p.name) and (p / 'template.json').is_file())
    except OSError:
        return []


def spawn_policy(roster, name):
    """成員 name 能不能生新成員（spawn.md〈誰能生〉）：None＝不能；否則 {"templates": [...], "approve": 布林}。
    順序：成員層 spawn 蓋過團隊層 spawn 蓋過出廠值（模板 may 有沒有 spawn；templates 沒寫＝內建模板都可以；approve＝false）。"""
    m = roster['members'].get(name)
    if m is None:
        return None
    own = m.get('spawn') or {}
    allow = own.get('allow')
    if allow is None:
        allow = 'spawn' in template_may(m['template'])
    if not allow:
        return None
    team = roster.get('spawn') or {}
    templates = own['templates'] if 'templates' in own else team.get('templates')
    if templates is None:
        templates = builtin_templates()
    approve = own['approve'] if 'approve' in own else bool(team.get('approve', False))
    return {'templates': list(templates), 'approve': approve}


def member_may(roster, name):
    """成員實際能寄的申請種類：模板 may，spawn 那格改看 spawn_policy（成員層可以開或關）。"""
    m = roster['members'].get(name)
    if m is None:
        return ()
    may = [k for k in template_may(m['template']) if k != 'spawn']
    if spawn_policy(roster, name) is not None:
        may.append('spawn')
    import aos_team_commons                    # 09-25：開了 commons 的成員都能投稿（commons.md）
    if aos_team_commons.member_on(roster, name) and 'contribute' not in may:
        may.append('contribute')
    return tuple(may)


def may_send(roster, sender, kind):
    """寄件人能不能寄這種申請：human 什麼都能；成員看自己模板的 may（spawn 看名冊，member_may）。"""
    if sender == HUMAN:
        return True
    if sender == BEAT:
        return kind in BEAT_MAY
    return kind in member_may(roster, sender)


# --------------------------------------------------------- 模板、門房規則 ----

TEMPLATE_KEYS = ('_metainfo', 'description', 'system', 'team', 'project', 'notes', 'may', 'llm', 'tick', 'tools',
                 'mounts')


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
    _unknown(llm, ('model', 'timeout_ms', 'params'), where + '.llm')
    if 'params' in llm:                  # 09-25 arknights 隊加：推理型模型要開大 max_tokens，原樣抄進 info.json 的 llm.params
        _obj(llm['params'], where + '.llm.params')
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


ROUTE_KEYS = ('name', 'pattern', 'do', 'run', 'tool', 'args', 'project', 'handoff', 'if_missing', 'tests')
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
        except (re.error, OverflowError, RecursionError) as e:   # 例 a{99999999999999999999}（W3-2 留的一行，09-25）
            bad(w + '.pattern', '正規式編不過：%s' % e)
        do = r.get('do')
        if 'if_missing' in r and do != 'handoff':
            bad(w + '.if_missing', '只給 do=handoff 的規則用')
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
            if 'if_missing' in r:                          # 真跑 09-25：草稿不在時單子要換說法
                im = _obj(r['if_missing'], w + '.if_missing')
                _unknown(im, ('path', 'goal', 'facts'), w + '.if_missing')
                ip = _str(im.get('path'), w + '.if_missing.path')
                if ip.startswith(('/', '~')) or '..' in ip.split('/'):
                    bad(w + '.if_missing.path', '要是專案裡的相對路徑（不能 / 或 ~ 開頭、不能有 ..）：%r' % ip)
                for k in ('goal', 'facts'):
                    if k in im:
                        _str(im[k], '%s.if_missing.%s' % (w, k))
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
