"""aos-agent notes ls／show：人看長期筆記（tools/notes/ 那支 note 工具寫的 wf-table/1 notes.json），
不叫模型（proto5/notes/2026-09-24-tool-era/catalog.md 的 T-notes）。

找筆記檔：<家>/tools/notes/config.json 的 "file"（相對＝相對 agent 家）；沒有這個檔或沒寫 file
＝<家>/notes/notes.json。file 是 "/work/<名>/…" 這種牢裡路徑時，查 <家>/access.json
（aos_agent_access）把 /work/<名> 換成那個 mount 的真路徑。
"""
import json
import os

import aos_agent_access as acc
from aos_agent_home import AgentError

DEFAULT_FILE = 'notes/notes.json'
CONFIG_REL = os.path.join('tools', 'notes', 'config.json')


def _config_file(base):
    """config.json 的 "file"（原樣字串）；沒有檔或沒寫這欄＝None。"""
    cfg = os.path.join(base, CONFIG_REL)
    if not os.path.isfile(cfg):
        return None
    try:
        with open(cfg, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise AgentError('ConfigInvalid', 'cannot read %s: %s' % (cfg, e)) from e
    if not isinstance(data, dict):
        raise AgentError('ConfigInvalid', '%s must be a JSON object' % cfg)
    value = data.get('file')
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise AgentError('ConfigInvalid', '%s: "file" must be a non-empty string' % cfg)
    return value


def _jail_real(base, value):
    """value 是 "/work/<名>/…"：查 access.json 把 /work/<名> 換成那個 mount 的真路徑。"""
    parts = value.split('/', 3)
    if len(parts) < 3 or parts[0] or parts[1] != 'work' or not parts[2]:
        raise AgentError('ConfigInvalid', '%s 不是 /work/<名>/… 形狀的牢裡路徑' % value)
    name, rest = parts[2], parts[3] if len(parts) > 3 else ''
    path, state = acc.access_lookup(base)
    if state != 'present':
        raise AgentError('ConfigInvalid', '筆記檔設成牢裡路徑 %s，但 %s 沒有可用的 access.json' % (value, base))
    table, _ = acc.parse(path, base, lenient=True)
    mount = table['mounts'].get(name)
    if mount is None:
        raise AgentError('ConfigInvalid', '筆記檔在牢裡的 %s，但 %s 的 mounts 沒有 %r（掛一個：aos-agent access set %s <資料夾> --rw）'
                         % (value, path, name, name))
    return os.path.join(mount['path'], rest) if rest else mount['path']


def notes_file(base):
    """算筆記檔絕對路徑（不保證存在）。"""
    base = os.path.abspath(base)
    value = _config_file(base)
    if value is None:
        # 跟 note 工具同一條規則：家裡有 access.json（工具關牢）＝牢裡的 /work/notes/notes.json
        _, state = acc.access_lookup(base)
        if state == 'present':
            return _jail_real(base, '/work/notes/notes.json')
        return os.path.join(base, DEFAULT_FILE)
    if value == '/work' or value.startswith('/work/'):
        return _jail_real(base, value)
    if os.path.isabs(os.path.expanduser(value)):
        return os.path.abspath(os.path.expanduser(value))
    return os.path.join(base, value)


def _read_table(path):
    """檔不在＝空表；壞掉（不是 JSON、不是 wf-table 形狀）＝ConfigInvalid。"""
    if not os.path.isfile(path):
        return {'rows': []}
    try:
        with open(path, encoding='utf-8') as f:
            raw = f.read()
    except OSError as e:
        raise AgentError('ReadFailed', 'cannot read %s: %s' % (path, e)) from e
    try:
        data = json.loads(raw)
    except ValueError as e:
        raise AgentError('ConfigInvalid', '%s is not valid JSON: %s' % (path, e)) from e
    if not isinstance(data, dict) or not isinstance(data.get('rows'), list):
        raise AgentError('ConfigInvalid', '%s is not a wf-table/1 notes file' % path)
    for i, row in enumerate(data['rows']):
        if not isinstance(row, dict) or not isinstance(row.get('key'), str) or not isinstance(row.get('text'), str):
            raise AgentError('ConfigInvalid', '%s: rows[%d] must have a string "key" and "text"' % (path, i))
    return data


def _snippet(text, n):
    return ' '.join(str(text).split())[:n]


def _ls(rows, as_json):
    if as_json:
        print(json.dumps(rows, ensure_ascii=False))
        return 0
    if not rows:
        print('（沒有筆記）')
        return 0
    for row in rows:
        print('  '.join([row.get('key', ''), '[%s]' % row.get('tags', ''), row.get('at', ''),
                         _snippet(row.get('text', ''), 60)]))
    return 0


def _show(rows, args, path, as_json):
    if len(args) != 1:
        raise AgentError('Usage', 'notes show 要恰好一個 KEY')
    key = args[0]
    row = next((r for r in rows if r.get('key') == key), None)
    if row is None:
        raise AgentError('NotFound', '沒有這個筆記：%s（筆記檔 %s）' % (key, path))
    if as_json:
        print(json.dumps(row, ensure_ascii=False))
        return 0
    print('%s [%s] %s' % (row.get('key', ''), row.get('tags', ''), row.get('at', '')))
    print(row.get('text', ''))
    return 0


def main(target, action, args, as_json=False):
    base = os.path.abspath(target)
    path = notes_file(base)
    rows = _read_table(path)['rows']
    if action == 'ls':
        if args:
            raise AgentError('Usage', 'notes ls 不收參數')
        return _ls(rows, as_json)
    if action == 'show':
        return _show(rows, args, path, as_json)
    raise AgentError('Usage', 'notes 只認 ls、show，不是 %r' % (action,))
