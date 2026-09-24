"""aos-agent access ls／set／rm／cwd／net（spec/aos-agent/access.md §3）。

寫入一律持 info.json 的 flock（跟 tools add 同一把）、.tmp＋rename；access 檔解不開（格式錯）就拒絕寫、
不蓋掉手寫的東西。AccessUnsafe（重疊）的表仍可以用這些指令修。
"""
import fcntl
import json
import os
import shutil
import unicodedata
from pathlib import Path

import aos_agent_access as acc
from aos_agent_home import AgentError

LAST = '下一批工具生效，不用重 start'
ACTIONS = {'ls': 0, 'set': 2, 'rm': 1, 'cwd': 1, 'net': 1}


def usage_problem(action, args, ro=False, rw=False, cwd=False, as_json=False):
    """用法錯的白話（沒錯＝None）；CLI 在看家之前先驗。"""
    if len(args) != ACTIONS[action]:
        want = {'ls': '不收參數', 'set': '要 NAME PATH', 'rm': '要 NAME', 'cwd': '要 NAME', 'net': '要 on 或 off'}
        return 'access %s %s' % (action, want[action])
    if action == 'net' and args[0] not in ('on', 'off'):
        return 'access net 只收 on 或 off：%s' % args[0]
    if action != 'set' and (ro or rw or cwd):
        return '--ro／--rw／--cwd 只給 access set 用'
    if action != 'ls' and as_json:
        return '--json 只給 access ls 用'
    if ro and rw:
        return '--ro 跟 --rw 只能給一個'
    if action in ('set', 'rm', 'cwd') and not acc.NAME.match(args[0]):
        return '名字 %r 只能用小寫英數、底線、連字號（[a-z0-9_-]+）' % args[0]
    return None


def bwrap_ok():
    return shutil.which('bwrap') is not None


def describe(base):
    """ls 的資料：{"file", "exists", "mounts", "cwd", "net", "bwrap", "error"}。"""
    base = os.path.abspath(base)
    path = acc.configured_path(base)
    data = {'file': str(path), 'exists': path.exists(), 'mounts': {}, 'cwd': None, 'net': False,
            'bwrap': bwrap_ok(), 'error': None}
    if not data['exists']:
        return data
    try:
        table, _ = acc.parse(path, base, lenient=True)
        data.update(cwd=table['cwd'], net=table['net'],
                    mounts={n: dict(m, exists=os.path.isdir(m['path'])) for n, m in table['mounts'].items()})
        acc.load(base)          # 嚴格的一遍：路徑在不在、重疊
    except AgentError as exc:
        data['error'] = '%s: %s' % (exc.code, exc.msg)
    return data


def _width(text):
    return sum(2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in text)


def _pad(text, width):
    return text + ' ' * max(0, width - _width(text))


def render(data):
    lines = []
    if not data['exists']:
        lines.append('沒有 access.json：工具不關牢（照舊在 agent 家跑，碰得到你碰得到的所有檔）。')
        lines.append('要關：aos-agent access set ws workspace --cwd（工作資料夾掛成 /work/ws、起點設在那）')
    elif data['mounts'] or not data['error']:
        width = max([_width(n) for n in data['mounts']] + [4])
        lines.append('  '.join([_pad('名字', width), '權限', _pad('存在', 4), '路徑']))
        for name, m in data['mounts'].items():
            lines.append('  '.join([_pad(name, width), _pad('ro' if m['ro'] else 'rw', 4),
                                    _pad('在' if m['exists'] else '不在', 4), m['path']]))
        if not data['mounts']:
            lines.append('（沒有 mount：牢裡只有 /work 空資料夾）')
        lines.append('cwd: /work/%s' % data['cwd'] if data['cwd'] else 'cwd: /work（沒設）')
        lines.append('net: %s' % ('on（共用主機網路，連得到本機服務）' if data['net'] else 'off'))
    if data['error']:
        lines.append('壞了：' + data['error'])
    lines.append('bwrap: ' + ('ok' if data['bwrap'] else '沒有（工具會跑不起來；Arch/Manjaro: sudo pacman -S bubblewrap）'))
    lines.append('檔：' + data['file'])
    return '\n'.join(lines)


def ls(base, as_json=False):
    data = describe(base)
    print(json.dumps(data, ensure_ascii=False) if as_json else render(data))
    return 1 if data['error'] else 0


def _raw_table(base, path):
    """讀要改的原始 JSON；檔在但解不開＝拒絕。回 (原始物件, 解好的表)。"""
    if not path.exists():
        return {'_metainfo': dict(acc.METAINFO), 'mounts': {}, 'net': False}, None
    try:
        table, _ = acc.parse(path, base, lenient=True)
    except AgentError as exc:
        raise AgentError(exc.code, '%s；access 檔壞了，先手修好（或刪掉重來）再用 access 指令' % exc.msg) from exc
    raw = acc.read_doc(path).root
    if not isinstance(raw.get('mounts', {}), dict) or acc.is_directive(raw.get('mounts', {})):
        raise AgentError('AccessInvalid', 'access 檔 %s 的 mounts 是指示詞，access 指令改不了；請手改' % path)
    return raw, table


def change(base, action, args, ro=False, rw=False, cwd=False):
    base = Path(os.path.abspath(base))
    with open(base / 'info.json', 'rb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        notes = _change(base, action, args, ro, rw, cwd)
    for note in notes:
        print(note)
    data = describe(base)
    print(render(data))
    print(LAST)
    return 0


def _change(base, action, args, ro, rw, cwd):
    path = acc.configured_path(base)
    raw, table = _raw_table(base, path)
    mounts = raw.setdefault('mounts', {})
    notes = []
    if action == 'set':
        name, given = args
        target = os.path.abspath(os.path.expanduser(given))
        if not os.path.isdir(target):
            raise AgentError('NotFound', '%s 不存在或不是資料夾（照目前資料夾算成 %s）' % (given, target))
        old = (table or {'mounts': {}})['mounts'].get(name)
        if name in mounts and _is_directive_value(mounts[name]):
            notes.append('mounts.%s 原本是指示詞 %s，換成字面路徑' % (name, json.dumps(mounts[name], ensure_ascii=False)))
        mode = 'ro' if ro else 'rw' if rw else None
        why = acc.overlap(os.path.realpath(target), acc.trusted(str(base), extra=[str(path)]))
        if mode is None and old is not None:
            mode = 'ro' if old['ro'] else 'rw'
            if mode == 'rw' and why:
                raise AgentError('AccessUnsafe', '%s %s；加 --ro 或換資料夾（沒寫）' % (name, why))
        elif mode is None:
            mode = 'ro' if why else 'rw'
            if why:
                notes.append('%s %s，所以設成唯讀（ro）' % (name, why))
        elif mode == 'rw' and why:
            raise AgentError('AccessUnsafe', '%s %s；改 --ro 或換資料夾（沒寫）' % (name, why))
        mounts[name] = {'$opt': 'ro', '$val': target} if mode == 'ro' else target
        if cwd:
            raw['cwd'] = name
    else:
        name = args[0]
        if action in ('rm', 'cwd') and name not in mounts:
            raise AgentError('NotFound', 'access 檔 %s 沒有 %s（有：%s）' % (path, name, '、'.join(mounts) or '沒有'))
        if action == 'rm':
            if raw.get('cwd') == name:
                raise AgentError('AccessInvalid', '%s 是目前的起點（cwd），先 aos-agent access cwd 別的名字 再 rm' % name)
            del mounts[name]
        elif action == 'cwd':
            raw['cwd'] = name
        else:
            raw['net'] = name == 'on'
    acc.write_access(path, raw)
    return notes


def _is_directive_value(value):
    if acc.is_option_object(value):
        return acc.is_directive(value.get('$val')) if isinstance(value.get('$val'), dict) else False
    return acc.is_directive(value)


def main(base, action, args, ro=False, rw=False, cwd=False, as_json=False):
    if action == 'ls':
        return ls(base, as_json=as_json)
    return change(base, action, args, ro=ro, rw=rw, cwd=cwd)
