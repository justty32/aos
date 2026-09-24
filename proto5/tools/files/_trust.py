"""沒關牢時擋「改到 agent 的信任資料」（catalog T-json、審查 M1）：看實際設定，不看檔名。

關牢時（環境變數 AOS_TOOL_ROOT 有值）不在這裡擋：權限牆本來就不准可寫的資料夾蓋到信任資料
（access.md 的 AccessUnsafe），工具在牢裡根本寫不到那些檔。

沒關牢時工具的 cwd＝agent 家（agent.md §3.3）。家裡有 info.json 才算：照它列出
  - 家裡固定的：info.json、state.json、tick.json、.tick.lock、paused、resumed、work、log、tools、prompts、
    input、input.json、access.json；
  - info.json 的 system／history／access 字面路徑、tools 列到的檔與資料夾（含 {"$opt":…, "$val": 路徑}）；
  - 工具檔裡每支 _meta.argv[0]（含 / 的）指到的程式與它的資料夾；
  - info.json、access 檔、工具檔裡字面寫的 $ref 檔（一路追下去，最多 10 層）；
  - state.json 的 input 清單。
每個位置保護「途中每個符號連結本身＋最後的真路徑」（同 lib/aos_agent_access.path_chain）。
算不到的（用 $env／$fmt 拼出來的路徑）不在內——這條是防手滑，真的邊界是權限牆。
proto5/lib/aos_agent_access.trusted() 是權限牆用的完整版；工具裝進 agent 家後找不到 lib，才另寫這份精簡版。
"""
import glob
import json
import os

HOME_FIXED = ('info.json', 'state.json', 'tick.json', '.tick.lock', 'paused', 'resumed', 'work', 'log',
              'tools', 'prompts', 'input', 'input.json', 'access.json')
MAX_REF_DEPTH = 10


def path_chain(path, limit=40):
    found = []
    cur, todo, hops = '/', os.path.abspath(path).split('/')[1:], 0
    while todo:
        name = todo.pop(0)
        if name in ('', '.'):
            continue
        if name == '..':
            cur = os.path.dirname(cur)
            continue
        nxt = os.path.join(cur, name)
        if hops < limit and os.path.islink(nxt):
            hops += 1
            found.append(nxt)
            try:
                target = os.readlink(nxt)
            except OSError:
                cur = nxt
                continue
            if target.startswith('/'):
                cur = '/'
            todo = target.split('/') + todo
            continue
        cur = nxt
    found.append(os.path.realpath(path))
    return found


def _load(path):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _raw_refs(value, out):
    if isinstance(value, dict):
        ref = value.get('$ref')
        if isinstance(ref, str) and ref.partition('#')[0]:
            out.append(ref.partition('#')[0])
        for v in value.values():
            _raw_refs(v, out)
    elif isinstance(value, list):
        for v in value:
            _raw_refs(v, out)


def _val(entry):
    if isinstance(entry, dict) and '$opt' in entry:
        entry = entry.get('$val')
    return entry if isinstance(entry, str) and entry else None


def trusted(home):
    """{位置: 說明}；家裡沒有 info.json＝空（不是 agent 家）。"""
    home = os.path.abspath(home)
    info_path = os.path.join(home, 'info.json')
    if not os.path.isfile(info_path):
        return {}
    out = {}

    def add(p, label, base=home):
        for q in path_chain(os.path.join(base, os.path.expanduser(p))):
            out.setdefault(q, label)

    for name in HOME_FIXED:
        add(name, "the agent's " + name)
    json_files = [(info_path, 0)]
    info = _load(info_path)
    if isinstance(info, dict):
        for key, label in (('system', 'persona file'), ('history', 'memory file'), ('access', 'access file')):
            p = _val(info.get(key))
            if p:
                add(p, label)
                if key == 'access':
                    json_files.append((os.path.join(home, p), 0))
        tools = info.get('tools')
        for entry in tools if isinstance(tools, list) else []:
            p = _val(entry)
            if not p:
                continue
            full = os.path.join(home, os.path.expanduser(p))
            add(full, 'tool file')
            files = sorted(glob.glob(os.path.join(full, '*.json'))) if os.path.isdir(full) else [full]
            for tf in files:
                add(tf, 'tool file')
                json_files.append((tf, 0))
                _programs(home, _load(tf), add)
    seen = set()
    while json_files:
        path, depth = json_files.pop()
        real = os.path.realpath(path)
        if real in seen or depth > MAX_REF_DEPTH:
            continue
        seen.add(real)
        refs = []
        _raw_refs(_load(path), refs)
        for r in refs:
            for base in {home, os.path.dirname(os.path.abspath(path))}:
                target = os.path.join(base, os.path.expanduser(r))
                add(target, 'file referenced by $ref')
                json_files.append((target, depth + 1))
    state = _load(os.path.join(home, 'state.json'))
    if isinstance(state, dict) and isinstance(state.get('input'), list):
        for p in state['input']:
            if isinstance(p, str) and p:
                add(p, 'input file')
    return out


def _programs(home, tools, add):
    for tool in tools if isinstance(tools, list) else []:
        meta = tool.get('_meta') if isinstance(tool, dict) else None
        if not isinstance(meta, dict):
            continue
        argv, cwd = meta.get('argv'), meta.get('cwd')
        base = os.path.join(home, cwd) if isinstance(cwd, str) else home
        if isinstance(argv, list) and argv and isinstance(argv[0], str) and '/' in argv[0]:
            prog = os.path.join(base, os.path.expanduser(argv[0]))
            add(prog, 'tool program')
            add(os.path.dirname(os.path.realpath(prog)), "tool program's folder")


def _under(child, parent):
    return child == parent or child.startswith(parent.rstrip('/') + '/')


def blocked(full, home=None, env=None):
    """要寫的真路徑 full 落在信任資料裡＝回說明；否則 None。關牢時一律 None（牆在管）。"""
    env = os.environ if env is None else env
    if env.get('AOS_TOOL_ROOT'):
        return None
    trust = trusted(home or os.getcwd())
    for q in path_chain(full):
        for t, label in trust.items():
            if _under(q, t):
                return label
    return None
