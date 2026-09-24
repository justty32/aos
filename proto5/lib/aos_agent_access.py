"""agent 權限牆：讀、解、驗 access.json，算信任資料、查重疊，回快照（spec/agent/access.md）。

這層只讀（ensure_default／write_access 例外）；不跑 bwrap。錯一律 AgentError：
格式錯＝AccessInvalid（訊息帶 access 檔路徑＋欄位位置）、access 檔本身不是 JSON＝JsonSyntax（帶行列）、
可寫 mount 跟信任資料重疊＝AccessUnsafe。
"""
import json
import os
import re
from pathlib import Path

import aos_inst
from aos_agent_home import AgentError, load_llm_view, read_info_doc, resolve_field
from aos_directives import (Context, DirectiveError, Document, is_directive, is_option_object,
                            parse_options, resolve_located)

DEFAULT_NAME = 'access.json'
METAINFO = {'_type': 'agent_access', '_version': 1}
TOP_KEYS = ('_metainfo', 'mounts', 'cwd', 'net')
MOUNT_OPTIONS = {'ro': {'val': 'required'}}
NAME = re.compile(r'[a-z0-9_-]+\Z')
# 家裡固定的信任資料（家本身不算，所以 家/workspace 可寫）
HOME_TRUSTED = ('info.json', 'state.json', 'tick.json', '.tick.lock', 'paused', 'resumed',
                'work', 'log', 'tools', 'prompts')


# ---------------------------------------------------------------- 路徑 ----

def _info_access_field(base, env=None):
    """info.json 的 access 欄（解完指示詞）；沒寫＝None。info.json 壞了照傳錯。"""
    doc = read_info_doc(base)
    if 'access' not in doc.root:
        return None
    value = resolve_field(doc, Context(doc, base_dir=str(base), env=env), ['access'])
    if not isinstance(value, str) or not value:
        raise AgentError('FieldTypeMismatch', 'info.json 的 access 必須是非空路徑字串')
    return value


def _locate(base, env=None):
    """回 (access 檔絕對路徑, info.json 有沒有明寫 access 欄)。"""
    base = Path(os.path.abspath(base))
    value = _info_access_field(base, env)
    path = Path(os.path.abspath(os.path.join(base, os.path.expanduser(value or DEFAULT_NAME))))
    return path, value is not None


def configured_path(base, env=None):
    """access 檔應在的絕對路徑（不管存不存在）。"""
    return _locate(base, env)[0]


def access_path(base, env=None):
    """照 info.json 的 access 欄或預設 access.json；檔存在才回路徑，否則 None。"""
    path = configured_path(base, env)
    return path if path.exists() else None


# ---------------------------------------------------------------- 寫 ----

def ensure_default(base, ws_path):
    """家裡沒 access 檔就寫一份預設的；回要印的訊息，已有就回 None。

    呼叫者（tools add）已持 info.json 的 flock，這裡不再鎖（同行程再 flock 會卡住）。
    ws_path 是相對家的路徑時把資料夾建好。
    """
    base = Path(os.path.abspath(base))
    path = configured_path(base)
    if path.exists():
        return None
    obj = {'_metainfo': dict(METAINFO), 'mounts': {'ws': ws_path}, 'cwd': 'ws', 'net': False}
    if not os.path.isabs(os.path.expanduser(ws_path)):
        (base / ws_path).mkdir(parents=True, exist_ok=True)
    write_access(path, obj)
    return ('寫了 %s：工具會關在牢裡，只看得到 /work/ws（＝%s，可寫）、起點 /work/ws、不能上網。\n'
            '要改：aos-agent access set NAME PATH [--ro]、access net on、access ls 看全表'
            % (path, ws_path))


def write_access(path, obj):
    """.tmp＋rename；縮排 2、不跳脫中文。"""
    path = Path(path)
    tmp = path.with_name('.%s.tmp' % path.name)
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)
            f.write('\n')
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


# ---------------------------------------------------------------- 解 ----

class _Collect(Context):
    """跟 Context 一樣，另外把一路 $ref 到的檔（realpath）收進共用的 files。"""

    __slots__ = ('files',)

    def __init__(self, doc, base_dir=None, env=None, _chain=(), files=None):
        super().__init__(doc, base_dir, env, _chain)
        self.files = set() if files is None else files

    def child(self, doc=None, base_dir=None, env=None):
        return _Collect(self.doc if doc is None else doc,
                        self.base_dir if base_dir is None else base_dir,
                        self.env if env is None else env, self._chain, self.files)

    def _visited(self, ident):
        if isinstance(ident[0], str) and not ident[0].startswith('<'):
            self.files.add(ident[0])
        return _Collect(self.doc, self.base_dir, self.env, self._chain + (ident,), self.files)


def read_doc(path):
    """讀 access 檔；JSON 壞＝JsonSyntax（帶行列）。"""
    try:
        with open(path, encoding='utf-8') as f:
            raw = f.read()
    except (OSError, UnicodeError) as exc:
        raise AgentError('ReadFailed', '讀不到 access 檔 %s：%s' % (path, exc)) from exc
    try:
        root = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AgentError('JsonSyntax', 'access 檔 %s 第 %d 行第 %d 欄不是合法 JSON：%s'
                         % (path, exc.lineno, exc.colno, exc.msg)) from exc
    return Document(path, root)


def _bad(path, where, msg):
    return AgentError('AccessInvalid', 'access 檔 %s 的 %s：%s' % (path, where, msg))


def _loc(path, ctx, value, pos, where):
    try:
        return resolve_located(value, ctx, pos)
    except DirectiveError as exc:
        raise _bad(path, where, str(exc)) from exc


def _deep(path, ctx, value, pos, where):
    loc = _loc(path, ctx, value, pos, where)
    value = loc.value
    if isinstance(value, dict):
        if is_option_object(value):
            raise _bad(path, where, '這裡不吃 $opt')
        return {k: _deep(path, loc.ctx, v, loc.position + [k], where) for k, v in value.items()}
    if isinstance(value, list):
        return [_deep(path, loc.ctx, v, loc.position + [str(i)], where) for i, v in enumerate(value)]
    return value


def mount_value(path, ctx, raw, pos, where):
    """一格 mounts 的值 → (路徑字串, 是否 ro, 原值是不是指示詞)。"""
    loc = _loc(path, ctx, raw, pos, where)
    try:
        names, val, _ = parse_options(loc.value, loc.position, MOUNT_OPTIONS)
    except DirectiveError as exc:
        raise _bad(path, where, str(exc)) from exc
    directive = loc.value is not raw
    if is_option_object(loc.value):
        inner = _loc(path, loc.ctx, val, loc.position + ['$val'], where)
        directive = directive or inner.value is not val
        val = inner.value
    if not isinstance(val, str) or not val:
        raise _bad(path, where, '路徑要是非空字串（或 {"$opt": "ro", "$val": 路徑}）')
    return val, 'ro' in names, directive


def real_mount(base, value):
    """~ 展開、相對的算 agent 家、realpath。"""
    return os.path.realpath(os.path.join(str(base), os.path.expanduser(value)))


def parse(path, base, env=None, lenient=False):
    """解 access 檔 → (表, $ref 到的檔集合)。表＝{"mounts": {名: {"path", "ro"}}, "cwd", "net"}。

    lenient：mount 路徑不存在不算錯（給 access ls 與 access 寫入指令用，好讓人修）。
    """
    base = os.path.abspath(base)
    doc = read_doc(path)
    root = doc.root
    if not isinstance(root, dict) or is_directive(root):
        raise _bad(path, '頂層', '要是字面物件')
    for key in root:
        if key not in TOP_KEYS:
            raise _bad(path, key, '不認得的鍵（只認 mounts／cwd／net／_metainfo）')
    ctx = _Collect(doc, base_dir=base, env=env)
    if '_metainfo' in root:
        mi = _deep(path, ctx, root['_metainfo'], ['_metainfo'], '_metainfo')
        if (not isinstance(mi, dict) or mi.get('_type') != METAINFO['_type']
                or type(mi.get('_version')) is not int or mi['_version'] != 1):
            raise _bad(path, '_metainfo', '要是 {"_type": "agent_access", "_version": 1}（可整個省略）')
    mounts = {}
    if 'mounts' in root:
        loc = _loc(path, ctx, root['mounts'], ['mounts'], 'mounts')
        if not isinstance(loc.value, dict) or is_option_object(loc.value):
            raise _bad(path, 'mounts', '要是物件 {名字: 路徑}')
        for name, raw in loc.value.items():
            where = 'mounts.' + name
            if not NAME.match(name):
                raise _bad(path, where, '名字只能用小寫英數、底線、連字號（[a-z0-9_-]+）')
            value, ro, _ = mount_value(path, loc.ctx, raw, loc.position + [name], where)
            real = real_mount(base, value)
            if not os.path.isdir(real) and not lenient:
                raise _bad(path, where, '%s 不存在或不是資料夾（解完是 %s）' % (value, real))
            mounts[name] = {'path': real, 'ro': ro}
    cwd = None
    if 'cwd' in root:
        cwd = _deep(path, ctx, root['cwd'], ['cwd'], 'cwd')
        if not isinstance(cwd, str) or cwd not in mounts:
            raise _bad(path, 'cwd', '要是 mounts 裡的名字（有：%s）；不寫＝起點 /work'
                       % ('、'.join(mounts) or '沒有'))
    net = False
    if 'net' in root:
        net = _deep(path, ctx, root['net'], ['net'], 'net')
        if type(net) is not bool:
            raise _bad(path, 'net', '只收 true／false')
    return {'mounts': mounts, 'cwd': cwd, 'net': net}, ctx.files


# ---------------------------------------------------------------- 信任資料 ----

def _collect_all(value, ctx, pos):
    """盡量解一格裡所有指示詞，只為了收 $ref 到的檔；解不過的略過。"""
    try:
        loc = resolve_located(value, ctx, pos)
    except DirectiveError:
        return
    value = loc.value
    if isinstance(value, dict):
        for k, v in value.items():
            _collect_all(v, loc.ctx, loc.position + [k])
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _collect_all(v, loc.ctx, loc.position + [str(i)])


def _raw_refs(value, out):
    """_meta 裡字面的 $ref 檔名（不解，只收字串）。"""
    if isinstance(value, dict):
        ref = value.get('$ref')
        if isinstance(ref, str) and ref.partition('#')[0]:
            out.append(ref.partition('#')[0])
        for v in value.values():
            _raw_refs(v, out)
    elif isinstance(value, list):
        for v in value:
            _raw_refs(v, out)


def _info_entries(base, env):
    """info.json：$ref 到的檔、tools 列到的檔與資料夾（解不過的略過）。"""
    try:
        doc = read_info_doc(base)
    except AgentError:
        return set(), []
    ctx = _Collect(doc, base_dir=base, env=env)
    for key, value in doc.root.items():
        _collect_all(value, ctx, [key])
    listed = []
    try:
        loc = resolve_located(doc.root.get('tools', []), ctx, ['tools'])
        items = loc.value if isinstance(loc.value, list) else []
        for i, entry in enumerate(items):
            pos, val = loc.position + [str(i)], entry
            if is_option_object(entry):
                pos, val = pos + ['$val'], entry.get('$val')
            try:
                got = resolve_located(val, loc.ctx, pos).value
            except DirectiveError:
                continue
            if isinstance(got, str) and got:
                listed.append(os.path.join(base, os.path.expanduser(got)))
    except DirectiveError:
        pass
    return ctx.files, listed


def trusted(base, env=None, info=None, st=None, extra=()):
    """信任集合 T：{realpath: 說明}。info／st 沒給就自己盡量讀（讀不到只用家裡的固定清單）。"""
    base = os.path.abspath(base)
    out = {}

    def add(p, label):
        out.setdefault(os.path.realpath(os.path.join(base, p)), label)

    for name in HOME_TRUSTED:
        add(name, '家裡的 ' + name)
    for p in extra:
        add(p, 'access 設定')
    if st is None:
        try:
            import aos_agent_info
            st = aos_agent_info.load_state(base, env=env)
        except (AgentError, OSError, ValueError):
            st = None
    inputs = st['input'] if st else ['input.json']
    for p in inputs:
        add(p, '輸入檔')
    for entry in (st or {}).get('_waits', []):
        for p in entry['paths']:
            add(p, '門檔')
    refs, listed = _info_entries(base, env)
    for p in refs:
        add(p, 'info.json 引用的檔')
    for p in listed:
        add(p, 'tools 列的工具檔')
    if info is None:
        try:
            info = load_llm_view(base, env=env)
        except (AgentError, OSError):
            info = None
    if info is not None:
        add(info['system_path'], '人格檔')
        add(info['history_path'], '記憶檔')
        for p in info['tool_paths']:
            add(p, '工具檔')
        for tool in info['tools_raw']:
            source = tool.get('_source')
            if isinstance(source, dict) and isinstance(source.get('file'), str):
                add(source['file'], '工具檔')
            _tool_program(base, env, tool, add)
    return out


def _tool_program(base, env, tool, add):
    meta = tool.get('_meta')
    refs = []
    _raw_refs(meta, refs)
    try:
        decoded = aos_inst.load_obj(meta, base, env=env)
    except aos_inst.InstError:
        decoded = None
    for r in refs:
        add(r, '工具 _meta 引用的檔')
        if decoded:
            add(os.path.join(decoded['cwd'], r), '工具 _meta 引用的檔')
    if decoded and decoded['argv'] and '/' in decoded['argv'][0]:
        prog = os.path.realpath(os.path.join(decoded['cwd'], decoded['argv'][0]))
        add(os.path.dirname(prog), '工具程式所在的資料夾')


def _under(child, parent):
    return child.startswith(parent.rstrip('/') + '/')


def overlap(mount_path, trust):
    """可寫 mount 跟信任資料重疊？回白話（沒重疊＝None）。"""
    for t, label in trust.items():
        if mount_path == t or _under(t, mount_path):
            return '可寫、但包含 %s（%s）' % (t, label)
        if _under(mount_path, t):
            return '可寫、但位在 %s（%s）裡面' % (t, label)
    return None


def check_overlap(path, table, trust):
    for name, m in table['mounts'].items():
        if m['ro']:
            continue
        why = overlap(m['path'], trust)
        if why:
            raise AgentError('AccessUnsafe', 'access 檔 %s 的 mounts.%s %s；改成唯讀 '
                             '（{"$opt": "ro", "$val": …} 或 aos-agent access set %s PATH --ro）或換一個資料夾'
                             % (path, name, why, name))


# ---------------------------------------------------------------- 快照 ----

def load(base, env=None, info=None, st=None):
    """沒 access 檔＝None；好＝快照表；壞＝raise AgentError。"""
    base = os.path.abspath(base)
    path, explicit = _locate(base, env)
    if not path.exists():
        if explicit:
            raise AgentError('AccessInvalid', 'info.json 的 access 指到 %s，但檔不在' % path)
        return None
    table, refs = parse(path, base, env)
    check_overlap(path, table, trusted(base, env, info, st, extra=[str(path), *refs]))
    return table


def snapshot(base, env=None, info=None, st=None):
    """送件用：None／好的表／{"error": "代號: 白話"}，不丟錯。"""
    try:
        return load(base, env, info, st)
    except AgentError as exc:
        return {'error': '%s: %s' % (exc.code, exc.msg)}
