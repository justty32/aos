"""aos-agent tools ls／rm／alias／unalias（aos-agent/tools-manage.md），與 tools add 共用的 info.tools 編輯。

改 info.tools 一律：持 info.json 的 flock → 讀驗整個家 → 改記憶體裡的一份 → 整份試算
（load_llm_view(doc=…)，壞了就不寫）→ .tmp＋rename 整份重寫 info.json。不刪任何工具檔。
"""
import contextlib
import copy
import fcntl
import json
import os
from pathlib import Path
import sys
import unicodedata

import aos_home
from aos_agent_home import AgentError, Context, Document, load_llm_view, read_info_doc, resolve_field

DONE = '下一批工具生效，不用重 start'


@contextlib.contextmanager
def info_lock(base):
    """持 <家>/info.json 的 flock（tools 與 access 的寫入指令共用這一把）。

    info.json 會被 rename 整份換掉：拿到鎖後若檔已不是同一份，就放掉重拿新的那份，
    免得排在舊檔上的人跟新來的人同時動手。
    """
    path = Path(base) / 'info.json'
    while True:
        lock = open(path, 'rb')
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            same = os.fstat(lock.fileno()).st_ino == os.stat(path).st_ino
        except FileNotFoundError:
            same = False
        if same:
            break
        lock.close()
    try:
        yield
    finally:
        lock.close()


def _literal_opt(e):
    return (isinstance(e, dict) and set(e) == {'$opt', '$val'}
            and isinstance(e['$opt'], dict) and isinstance(e['$val'], str))


def editable_tools(doc, hint):
    """info.tools 要是字面陣列、每個元素是路徑字串或字面選項物件，才能自動改；回那個陣列（沒寫＝[]）。"""
    tools = doc.root.get('tools', [])
    if not (isinstance(tools, list) and all(isinstance(e, str) or _literal_opt(e) for e in tools)):
        raise AgentError('FieldTypeMismatch', 'info.json 的 tools 不是字面陣列（元素要是路徑字串，或 '
                         '{"$opt": {…}, "$val": 路徑字串}），沒辦法自動改；' + hint)
    return tools


def split_entry(e):
    """字面元素 → (路徑, as 的拷貝, only 的拷貝或 None)。"""
    if isinstance(e, str):
        return e, {}, None
    opt = e['$opt']
    return e['$val'], dict(opt.get('as') or {}), (list(opt['only']) if 'only' in opt else None)


def make_entry(val, as_map, only):
    """(路徑, as, only) → 字面元素；沒有選項就收回成純路徑字串。"""
    opt = {}
    if as_map:
        opt['as'] = as_map
    if only is not None:
        opt['only'] = only
    return {'$opt': opt, '$val': val} if opt else val


def simulate(base, root, files=None):
    """用改過的 info.json 內容整份試算一次；壞了照丟錯（呼叫者什麼都還沒寫）。"""
    return load_llm_view(base, doc=Document(Path(base) / 'info.json', root), files=files)


def commit(base, root, files=None):
    """試算過才整份重寫 info.json（縮排照 aos_home.write_json）。"""
    view = simulate(base, root, files)
    aos_home.write_json(Path(base) / 'info.json', root)
    return view


def rel(base, path):
    """在家裡＝相對家，家外＝絕對路徑。"""
    base = os.path.abspath(base)
    return os.path.relpath(path, base) if path.startswith(base.rstrip(os.sep) + os.sep) else path


def _access_path(base):
    from aos_agent_access import access_path   # A2 的模組；延遲載入
    return access_path(base)


def _find(view, name, *, originals=False):
    """模型看到的名字 → 工具；originals＝找不到時也認原名（alias 用）。"""
    tools = view['tools_raw']
    for t in tools:
        if t['function']['name'] == name:
            return t
    by_orig = [t for t in tools if t['_source']['name'] == name]
    if originals and len(by_orig) == 1:
        return by_orig[0]
    if originals and by_orig:
        raise AgentError('Usage', '原名 %s 有 %d 支（現在叫 %s），請用現在的名字'
                         % (name, len(by_orig), '、'.join(t['function']['name'] for t in by_orig)))
    hint = ('；%s 是原名，現在叫 %s' % (name, by_orig[0]['function']['name'])) if by_orig else ''
    raise AgentError('NotFound', '沒有叫 %s 的工具%s（現在有：%s）'
                     % (name, hint, '、'.join(t['function']['name'] for t in tools) or '（無）'))


def _width(text):
    return sum(2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in text)


def _table(rows):
    widths = [max(_width(r[i]) for r in rows) for i in range(len(rows[0]))]
    for r in rows:
        print('  '.join(c + ' ' * (w - _width(c)) for c, w in zip(r, widths)).rstrip())


def ls(agent_dir, as_json=False):
    base = os.path.abspath(agent_dir)
    view = load_llm_view(base)
    doc = read_info_doc(base)
    pool = resolve_field(doc, Context(doc, base_dir=base), ['tool_pool']) if 'tool_pool' in doc.root else 'default'
    access, access_error = None, None
    try:
        access = _access_path(base)
    except AgentError as e:
        access_error = str(e)
    rows = []
    for t in view['tools_raw']:
        src = t['_source']
        jail = None if access is None or access_error else t.get('_jail', True) is not False
        rows.append({'name': t['function']['name'], 'original': src['name'], 'file': src['file'],
                     'index': src['index'], 'entry': src['entry'], 'jail': jail, 'pool': pool})
    if as_json:
        print(json.dumps({'_type': 'aos_agent_tools_ls', '_version': 1, 'dir': base,
                          'access': None if access is None else str(access), 'tools': rows},
                         ensure_ascii=False, indent=2))
        return 0
    if access_error:
        print('warn: 讀不到 access 設定，關牢欄印 ?：%s' % access_error, file=sys.stderr)
    if not rows:
        print('沒有工具（info.json 的 tools 是空的）；裝內建的：aos-agent tools add base')
        return 0
    mark = {True: 'jail', False: 'no', None: '?' if access_error else '-'}
    _table([('名字', '原名', '來源檔', '關牢', '池')] +
           [(r['name'], r['original'] if r['original'] != r['name'] else '-',
             rel(base, r['file']), mark[r['jail']], str(r['pool'])) for r in rows])
    where = ('關牢照 %s' % access) if access else '沒有 access 檔：工具不關牢'
    print('%d 個工具；%s' % (len(rows), where))
    return 0


def _edit(agent_dir, fn):
    """持鎖、讀驗、叫 fn(base, view, doc, tools) 改一份拷貝並回要印的行，試算過才寫。"""
    base = os.path.abspath(agent_dir)
    with info_lock(base):
        view = load_llm_view(base)
        doc = read_info_doc(base)
        root = copy.deepcopy(doc.root)
        tools = editable_tools(doc, '請直接編 info.json')
        lines = fn(base, view, root, tools)
        if lines is None:
            return 0
        commit(base, root)
    for line in lines:
        print(line)
    print(DONE)
    return 0


def rm(agent_dir, name):
    def change(base, view, root, tools):
        tool = _find(view, name)
        src = tool['_source']
        e = src['entry']
        val, as_map, only = split_entry(tools[e])
        others = [t['_source']['name'] for t in view['tools_raw']
                  if t['_source']['entry'] == e and t is not tool]
        if not others:
            del root['tools'][e]
            lines = ['拿掉 %s：info.tools 第 %d 條 %s 整條拿掉' % (name, e, json.dumps(val, ensure_ascii=False))]
        else:
            as_map.pop(src['name'], None)
            root['tools'][e] = make_entry(val, as_map, others)
            lines = ['拿掉 %s：info.tools 第 %d 條改成只挑（原名）%s' % (name, e, '、'.join(others))]
            if os.path.isdir(os.path.join(base, val)):
                lines.append('注意：這條是整個資料夾，之後放進去的新工具要加進 only（或 tools add）才會出現')
        lines.append('檔還在 %s（第 %d 個，原名 %s）；沒刪任何檔' % (src['file'], src['index'], src['name']))
        return lines
    return _edit(agent_dir, change)


def alias(agent_dir, name, new):
    def change(base, view, root, tools):
        tool = _find(view, name, originals=True)
        src, now = tool['_source'], tool['function']['name']
        if now == new:
            print('%s 已經叫 %s，沒改' % (name, new))
            return None
        val, as_map, only = split_entry(tools[src['entry']])
        if new == src['name']:
            as_map.pop(src['name'], None)
        else:
            as_map[src['name']] = new
        root['tools'][src['entry']] = make_entry(val, as_map, only)
        return ['%s 改叫 %s（原名 %s；info.tools 第 %d 條）' % (now, new, src['name'], src['entry'])]
    return _edit(agent_dir, change)


def unalias(agent_dir, new):
    def change(base, view, root, tools):
        tool = _find(view, new)
        src = tool['_source']
        if src['name'] == new:
            raise AgentError('NotFound', '%s 沒有改過名（它就是原名）' % new)
        val, as_map, only = split_entry(tools[src['entry']])
        as_map.pop(src['name'], None)
        entry = make_entry(val, as_map, only)
        root['tools'][src['entry']] = entry
        lines = ['%s 改回原名 %s（info.tools 第 %d 條）' % (new, src['name'], src['entry'])]
        if isinstance(entry, str):
            lines.append('第 %d 條沒有選項了，收回成 %s' % (src['entry'], json.dumps(entry, ensure_ascii=False)))
        return lines
    return _edit(agent_dir, change)
