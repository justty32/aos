"""名冊裡人寫的白名單與生成設定：cmd_ok 指令與白名單（含 pattern 與唯讀掛載）、單子上的 cmd_ok 對白名單、spawn 設定、成員與模板的掛載（mounts）與工具條目欄位。"""
import os
import re

from aos_team_format_base import (
    _int, _obj, _unknown, bad, CMD_TIMEOUT_DEFAULT, CMD_TIMEOUT_MAX, NAME
)


def validate_cmd(run, where):
    """cmd_ok 的指令：非空字串陣列；第一格是指令名（不含 /，在牢裡照 PATH 找），每格不含 NUL。"""
    if not isinstance(run, list) or not run or not all(isinstance(x, str) and x and '\0' not in x for x in run):
        bad(where, '要是非空字串陣列，例 ["python3", "-m", "unittest"]')
    if '/' in run[0] or run[0].startswith('-'):
        bad(where, '第一格要是指令名（不含 /、不以 - 開頭），例 python3、make；在牢裡照 PATH 找')
    return list(run)


def _spawn_cfg(value, where):
    """team.json 的 spawn（第三波 W3-1，spawn.md；09-25 使用者翻案：預設開、預設不用人批）：
    {"templates": [模板名…], "approve": 布林}。templates 沒寫＝None＝內建模板都可以（builtin_templates）；
    寫 [] ＝這隊不准生。approve 沒寫＝false＝郵差檢查過就直接生，不問人。只收內建模板名（不含 /）：
    自訂模板的資料夾可能在模型改得到的地方。"""
    _obj(value, where)
    _unknown(value, ('templates', 'approve'), where)
    out = {'templates': _spawn_templates(value, where), 'approve': False}
    if 'approve' in value:
        if not isinstance(value['approve'], bool):
            bad(where + '.approve', '要是 true 或 false')
        out['approve'] = value['approve']
    return out


def _spawn_templates(value, where):
    if 'templates' not in value:
        return None
    names = value['templates']
    if not isinstance(names, list) or not all(isinstance(x, str) and NAME.match(x) for x in names):
        bad(where + '.templates', '要是內建模板名的陣列（小寫英數、底線、連字號，不含 /）')
    return list(dict.fromkeys(names))


def _member_spawn(value, where):
    """成員層的 spawn（蓋過團隊層）：沒寫＝None（照模板 may 有沒有 spawn、團隊層的設定）；
    true／false＝能不能生；物件 {"allow"?, "templates"?, "approve"?}＝逐項蓋過，allow 沒寫＝照模板 may。"""
    if value is None:
        return None
    if isinstance(value, bool):
        return {'allow': value}
    _obj(value, where)
    _unknown(value, ('allow', 'templates', 'approve'), where)
    out = {}
    for k in ('allow', 'approve'):
        if k in value:
            if not isinstance(value[k], bool):
                bad('%s.%s' % (where, k), '要是 true 或 false')
            out[k] = value[k]
    t = _spawn_templates(value, where)
    if t is not None:
        out['templates'] = t
    return out


def _cmd_whitelist(value, where):
    """team.json 的 cmd_ok：人寫的白名單 [{"run": [...], "timeout_s": 秒, "mounts"?: {名: 路徑}}]；單子上的 cmd_ok 要對得上其中一條。"""
    if not isinstance(value, list):
        bad(where, '要是陣列 [{"run": [...], "timeout_s": 秒}]')
    out = []
    for i, e in enumerate(value):
        w = '%s[%d]' % (where, i)
        _obj(e, w)
        _unknown(e, ('run', 'timeout_s', 'mounts', 'pattern'), w)
        run = validate_cmd(e.get('run'), w + '.run')
        t = _int(e.get('timeout_s', CMD_TIMEOUT_DEFAULT), w + '.timeout_s', 1, CMD_TIMEOUT_MAX)
        entry = {'run': run, 'timeout_s': t}
        # 09-25 市場真跑 §7 第 4 條：白名單照人名寫死，換個人就退件。pattern: true＝run 裡的 {名字} 可換成一格路徑段
        if 'pattern' in e:
            if not isinstance(e['pattern'], bool):
                bad(w + '.pattern', '要是 true 或 false')
            if e['pattern']:
                _cmd_pattern(run, w + '.run')
                entry['pattern'] = True
        # 09-25 arknights 隊加：指令要讀專案外的資料（例：原文庫）時，人在白名單寫要多掛哪幾個資料夾；一律唯讀
        mounts = _obj(e.get('mounts', {}), w + '.mounts')
        for mk, mv in mounts.items():
            if not re.match(r'[a-z0-9_-]+\Z', mk) or mk == 'ws':
                bad('%s.mounts.%s' % (w, mk), '名字要是小寫英數與 _ -，不能是 ws')
            if not isinstance(mv, str) or not (mv.startswith('/') or mv.startswith('~')):
                bad('%s.mounts.%s' % (w, mk), '要是絕對路徑或 ~ 開頭的路徑（一律唯讀掛到 /work/%s）' % mk)
        if mounts:
            entry['mounts'] = {mk: os.path.expanduser(mv) for mk, mv in mounts.items()}
        out.append(entry)
    return out


CMD_VAR = re.compile(r'\{([a-z_][a-z0-9_]*)\}')


def _cmd_pattern(run, where):
    """pattern 白名單：{名字} 只能出現在第 2 格以後（指令名不能換）；至少要有一個，不然寫 pattern 沒意義。"""
    if '{' in run[0]:
        bad(where + '[0]', '指令名不能用 {名字}')
    if not any(CMD_VAR.search(a) for a in run[1:]):
        bad(where, 'pattern: true 的白名單要有 {名字}，例 "lore/characters/{name}.md"')


def _cmd_pattern_match(pattern, run):
    """整串比：每格照白名單那格，{名字} 換成一格路徑段（不含 /、不是 . 或 ..、不以 - 開頭）；
    同一個名字在各格要是同一個值。其他字一個都不能差。"""
    if not isinstance(run, list) or len(run) != len(pattern) or run[0] != pattern[0]:
        return False
    seen = {}
    for pat, arg in zip(pattern, run):
        if not isinstance(arg, str):
            return False
        parts, pos, names = [], 0, []
        for m in CMD_VAR.finditer(pat):
            parts.append(re.escape(pat[pos:m.start()]))
            parts.append('([^/\0]+)')
            names.append(m.group(1))
            pos = m.end()
        parts.append(re.escape(pat[pos:]))
        m = re.fullmatch(''.join(parts), arg, re.S)
        if m is None:
            return False
        for name, val in zip(names, m.groups()):
            if val in ('.', '..') or val.startswith('-') or seen.setdefault(name, val) != val:
                return False
    return True


def cmd_allowed(roster, item):
    """單子上的 cmd_ok 條目對得上名冊白名單的哪一條：回那一條；對不上＝None。
    run 要整串一樣（pattern 白名單：{名字} 那段可以換，見 _cmd_pattern_match）；
    單子上的 timeout_s（沒寫＝白名單那條的）不能超過白名單的。"""
    run = item.get('run')
    for e in roster.get('cmd_ok', []):
        same = _cmd_pattern_match(e['run'], run) if e.get('pattern') else e['run'] == run
        if same and item.get('timeout_s', e['timeout_s']) <= e['timeout_s']:
            return e
    return None


TOOL_ENTRY_KEYS = ('pack', 'only', 'team', 'optional')
RESERVED_MOUNTS = ('ws', 'outbox', 'board', 'notes', 'mem', 'commons')   # notes、mem：模板 notes: true 時 init 內建掛；commons：09-25


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
