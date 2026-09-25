"""造工具的工具（spec/aos-agent/tools-dev.md）：aos-agent tools new／test／wrap-py。

三個都不需要 agent 家、都不叫模型：
- new：機械生一個工具包骨架（照 base 的樣子，一支範例工具＋固定案例）。
- test：在拋棄式的假 agent 家裡照 aos-agent 的方式跑工具（預設關牢），驗格式、跑自動與固定案例。
- wrap-py：用 ast 靜態讀一個 Python 檔（不 import、不執行），把有型別註解的頂層函式包成工具包。
寫檔一律先寫進同層的暫存資料夾，整包寫好才 rename 成正式名字。
"""
import ast
import datetime
import errno
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import shutil
import selectors
import shlex
import signal
import stat
import subprocess
import sys
import tempfile
import time

from aos_agent_home import AgentError, read_tools
from aos_agent_tools import NAME, PACKAGES, find_package

BASE_COMMON = PACKAGES / 'base' / '_common.py'
TOOL_NAME = re.compile(r'[A-Za-z0-9_]{1,64}\Z')        # 模型端（OpenAI 相容）的工具名限制，函式名要過這條
TEST_TIMEOUT_MS = 30000                                  # tools test 對每一次執行的封頂
TOKEN_LIMIT = 300                                        # axes.md 資源軸：工具描述 < 300 token＝5 分
OUTPUT_CAP = 1024 * 1024        # tools test：stdout、stderr 各最多留多少位元組（留尾巴）
KILL_GRACE = 5                  # SIGKILL 之後最多再等幾秒
DRAIN_GRACE = 2                 # 主行程結束後，管子還被別人握著最多再收幾秒
TAIL = 200                                               # FAIL 時「得到什麼」最多印幾個字


# ------------------------------------------------------------------ 共用：寫一整包 ----

def _mode(executable):
    umask = os.umask(0)
    os.umask(umask)
    return (0o777 if executable else 0o666) & ~umask


def _out_dir(out):
    folder = Path(os.path.abspath(os.path.expanduser(out or '.')))
    if not folder.is_dir():
        raise AgentError('NotFound', '--out %s 不是存在的資料夾' % folder)
    return folder


def _check_dest(folder, name, force):
    dest = folder / name
    if os.path.lexists(dest):
        if not force:
            raise AgentError('AlreadyExists', '%s 已經在了（要蓋掉加 --force）' % dest)
        if dest.is_symlink() or not dest.is_dir():
            raise AgentError('AlreadyExists', '%s 不是資料夾（或是符號連結），--force 也不蓋' % dest)
    return dest


def _alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def recover(folder, name):
    """清前一次被硬中止留下的殘渣（名字帶 pid，那個行程還活著的不碰）：
    .NAME.new-<pid>-* 直接刪；.NAME.old-<pid>-* 是 --force 的備份——正式包在就刪，
    正式包不在（崩在「舊的改名」與「新的就位」之間）就改回正式名。回印給人看的話（清單）。"""
    notes = []
    pattern = re.compile(r'\.%s\.(new|old)-(\d+)-' % re.escape(name))
    for entry in sorted(folder.iterdir()):
        m = pattern.match(entry.name)
        if not m or _alive(int(m.group(2))) or entry.is_symlink() or not entry.is_dir():
            continue
        dest = folder / name
        if m.group(1) == 'old' and not os.path.lexists(dest):
            os.rename(entry, dest)
            notes.append('上次 --force 中斷：把舊包 %s 改回 %s' % (entry.name, dest))
        else:
            shutil.rmtree(entry, ignore_errors=True)
            notes.append('清掉上次中斷留下的 %s' % entry)
    return notes


def publish(folder, name, files, force=False):
    """files＝{相對路徑: (內容 str 或 bytes, 可執行?)}；寫進 folder/.name.new-<pid>-XXXX/ 再 rename 成 folder/name。
    --force：舊包先改名成 .name.old-<pid>-…，新包就位才刪它；新包 rename 失敗就把舊包改回來。"""
    for note in recover(folder, name):
        print(note, file=sys.stderr)
    dest = _check_dest(folder, name, force)
    tmp = Path(tempfile.mkdtemp(dir=folder, prefix='.%s.new-%d-' % (name, os.getpid())))
    old = None
    try:
        for rel, (content, executable) in files.items():
            path = tmp / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            data = content.encode('utf-8') if isinstance(content, str) else content
            path.write_bytes(data)
            os.chmod(path, _mode(executable))
        for sub in [tmp] + [p for p in tmp.rglob('*') if p.is_dir()]:
            os.chmod(sub, _mode(True))
        if os.path.lexists(dest):
            _check_dest(folder, name, force)                  # 寫檔這段時間裡被換成別的東西就不蓋
            old = folder / ('.%s.old-%d-%d' % (name, os.getpid(), time.time_ns()))
            os.rename(dest, old)
        try:
            os.rename(tmp, dest)
        except BaseException:
            if old is not None and not os.path.lexists(dest):
                os.rename(old, dest)                          # 新的沒就位：舊的放回去
                old = None
            raise
        tmp = None
        if old is not None:
            shutil.rmtree(old, ignore_errors=True)            # 新的就位了才刪備份
            old = None
    finally:
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)
    return dest


def package_files(name, entries):
    """[(相對路徑, 內容, 可執行?)] → dict；同一個路徑出現兩次＝包名撞到必要檔（BadName），不靜默蓋掉。"""
    files = {}
    for rel, content, executable in entries:
        if rel in files:
            raise AgentError('BadName', '包名 %r 會讓 %s 跟包裡另一個必要檔撞名（例如工具描述被設定檔蓋掉）；換個名字'
                             % (name, rel))
        files[rel] = (content, executable)
    return files


def _shown(dest):
    """印給人看、也能直接貼給 tools test／tools add 的路徑：目前資料夾底下的寫 ./相對，其他寫絕對。"""
    rel = os.path.relpath(dest)
    return './' + rel if not rel.startswith('..') and not os.path.isabs(rel) else str(dest)


# ------------------------------------------------------------------ tools new ----

NEW_PROGRAM = '''#!/usr/bin/env python3
"""{name}：範例工具（aos-agent tools new 生的骨架）。改 main() 的本體；參數寫在 {name}.json。

約定（proto5/tools/README.md）：stdin 收 arguments JSON；成功回純文字、退 0；
失敗用 fail(代號, 白話) —— 最後一行印 {{"ok": false, "error", "message"}}、退 1。
"""
import sys
sys.dont_write_bytecode = True
from _common import run, arg, fail  # noqa: E402


def main(args, root):
    """args＝模型給的參數（已確定是 JSON 物件）；root＝工作根目錄（關牢時是牢裡的 /work/ws）。"""
    text = arg(args, 'text', str, required=True)      # 缺了或型別錯 → BadArguments
    count = arg(args, 'count', int, 1)
    if count < 1:
        fail('BadArguments', 'count must be >= 1')
    # TODO: 在這裡寫你的程式（碰檔案用 _common.resolve(root, path) 把路徑關在工作根目錄裡）
    return ' '.join([text] * count)


if __name__ == '__main__':
    sys.exit(run(main))
'''

NEW_README = '''# {name} — 工具包（aos-agent tools new 生的骨架）

一支範例工具 `{name}`：把 `text` 重複 `count` 次。照下面改成你要的。

| 檔 | 做什麼 |
|---|---|
| `{name}.json` | 給模型看的工具描述（英文、越短越好）＋`_meta.argv`（`tools/{name}/{name}`，相對 agent 家） |
| `{name}` | 工具程式（要有執行位）：stdin 收 arguments JSON，成功印純文字退 0，失敗 `fail(代號, 訊息)` |
| `_common.py` | base 包那份的副本（讀參數、工作根目錄、錯誤格式）；**不要改**，要更新就從 `proto5/tools/base/` 再複製一次 |
| `config.json` | `root`＝不關牢時的工作根目錄（相對 agent 家） |
| `cases.json` | 固定案例，`tools test` 會跑 |

## 改

1. 改 `{name}` 的 `main()`：用 `arg(args, 名, 型別, 預設, required=)` 取參數，`# TODO` 那裡寫本體。
2. 改 `{name}.json`：`description` 一句話、`parameters` 照 JSON Schema 寫，跟程式取的參數對上。
3. 改 `cases.json`：每條 `{{"tool", "args", "expect": "ok" 或錯誤代號, "contains": 輸出要含的字}}`。

## 試

```sh
aos-agent tools test {path}             # 預設關在牢裡跑（有 bwrap 時）；--no-jail 直接跑
aos-agent tools test {path} --args '{{"text": "hi", "count": 2}}'   # 只跑一次，看原樣輸出
```

會驗工具檔格式、描述多長（token 粗估）、從 `parameters` 自動生的案例（正例、型別錯、缺必填、參數不是物件），再跑 `cases.json`。

## 裝

```sh
aos-agent tools add {path} --target 家
```

沒寫 `_jail`＝預設關牢：家裡有 `access.json` 時，工具被關進 bwrap 跑，只看得到 access.json 掛進去的資料夾。
'''


def new_files(name, path):
    """tools new 生的整包：{相對路徑: (內容, 可執行?)}。"""
    tool = [{'type': 'function',
             'function': {'name': name,
                          'description': 'Example tool: repeat text. Replace with what your tool does.',
                          'parameters': {'type': 'object',
                                         'properties': {'text': {'type': 'string', 'description': 'Text to repeat.'},
                                                        'count': {'type': 'integer', 'minimum': 1,
                                                                  'description': 'How many times (default 1).'}},
                                         'required': ['text']}},
             '_meta': {'argv': ['tools/%s/%s' % (name, name)]}}]
    cases = [{'name': 'repeat', 'tool': name, 'args': {'text': 'hi', 'count': 2}, 'expect': 'ok', 'contains': 'hi hi'},
             {'name': 'missing-text', 'tool': name, 'args': {'count': 2}, 'expect': 'BadArguments'},
             {'name': 'count-not-int', 'tool': name, 'args': {'text': 'hi', 'count': 'x'}, 'expect': 'BadArguments'},
             {'name': 'count-zero', 'tool': name, 'args': {'text': 'hi', 'count': 0}, 'expect': 'BadArguments'}]
    return [(name + '.json', _dump(tool), False),
            (name, NEW_PROGRAM.format(name=name), True),
            ('_common.py', BASE_COMMON.read_bytes(), False),
            ('config.json', _dump({'root': 'workspace'}), False),
            ('cases.json', _dump(cases), False),
            ('README.md', NEW_README.format(name=name, path=path), False)]


def _dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'


def new(name, out=None, force=False):
    if not NAME.match(name):
        raise AgentError('BadName', '工具包名字 %r 只能用英數、底線、連字號（不能以 . 或 - 開頭）' % name)
    folder = _out_dir(out)
    path = _shown(folder / name)
    files = package_files(name, new_files(name, path))   # new config／new cases 在這裡擋
    _check_dest(folder, name, force)
    dest = publish(folder, name, files, force)
    print('生了 %s/：%s' % (dest, '、'.join(files)))
    print('下一步：改 %s/%s 與 %s.json，然後 aos-agent tools test %s' % (path, name, name, path))
    print('裝進家：aos-agent tools add %s --target 家' % path)
    return 0


# ------------------------------------------------------------------ wrap-py：讀 ----

TYPING = ('typing', 't', 'typing_extensions')
SIMPLE = {'str': 'string', 'int': 'integer', 'float': 'number', 'bool': 'boolean'}
LITERAL_KIND = {str: 'string', int: 'integer', float: 'number', bool: 'boolean'}
SUPPORTED = 'str、int、float、bool、list[X]、dict[str, X]、Literal[...]、X | None'


class Unsupported(Exception):
    pass


def _type_name(node):
    """Name 或 typing.X → 'X'；其他 None。"""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in TYPING:
        return node.attr
    return None


def _union_parts(node):
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _union_parts(node.left) + _union_parts(node.right)
    return [node]


def _is_none(node):
    return isinstance(node, ast.Constant) and node.value is None or _type_name(node) == 'None'


def _optional(parts, text):
    rest = [p for p in parts if not _is_none(p)]
    if len(rest) != 1 or len(rest) == len(parts):
        raise Unsupported('%s：聯集只收 X | None 一種寫法' % text)
    return {'t': 'optional', 'of': type_spec(rest[0])}


def type_spec(node):
    """型別註解 → 型別記號（寫進 wrap.json，run 照它驗）；不支援丟 Unsupported。"""
    text = ast.unparse(node)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):   # "int" 這種字串註解
        try:
            node = ast.parse(node.value, mode='eval').body
        except SyntaxError:
            raise Unsupported('字串註解 %r 讀不懂' % node.value)
        return type_spec(node)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _optional(_union_parts(node), text)
    name = _type_name(node)
    if name in SIMPLE:
        return {'t': name}
    if name in ('list', 'List'):
        return {'t': 'list', 'of': {'t': 'any'}}
    if name in ('dict', 'Dict'):
        return {'t': 'dict', 'of': {'t': 'any'}}
    if isinstance(node, ast.Subscript):
        base = _type_name(node.value)
        args = list(node.slice.elts) if isinstance(node.slice, ast.Tuple) else [node.slice]
        if base in ('list', 'List') and len(args) == 1:
            return {'t': 'list', 'of': type_spec(args[0])}
        if base in ('dict', 'Dict') and len(args) == 2:
            if _type_name(args[0]) != 'str':
                raise Unsupported('%s：dict 的鍵只收 str（JSON 物件的鍵一定是字串）' % text)
            return {'t': 'dict', 'of': type_spec(args[1])}
        if base == 'Optional' and len(args) == 1:
            return {'t': 'optional', 'of': type_spec(args[0])}
        if base == 'Union':
            return _optional(args, text)
        if base == 'Literal':
            values = []
            for a in args:
                if not isinstance(a, ast.Constant) or type(a.value) not in LITERAL_KIND:
                    raise Unsupported('%s：Literal 只收字串、整數、小數、布林常值' % text)
                values.append(a.value)
            if len({type(v) for v in values}) != 1:
                raise Unsupported('%s：Literal 的值要是同一種 JSON 型別' % text)
            return {'t': 'literal', 'values': values}
    raise Unsupported('型別 %s 不支援（只收 %s）' % (text, SUPPORTED))


def schema(spec):
    """型別記號 → JSON Schema（給模型看的）。X | None 只寫 X（模型給 null 也收）。"""
    t = spec['t']
    if t in SIMPLE:
        return {'type': SIMPLE[t]}
    if t == 'list':
        return dict({'type': 'array'}, **({'items': schema(spec['of'])} if spec['of']['t'] != 'any' else {}))
    if t == 'dict':
        return dict({'type': 'object'},
                    **({'additionalProperties': schema(spec['of'])} if spec['of']['t'] != 'any' else {}))
    if t == 'literal':
        return {'type': LITERAL_KIND[type(spec['values'][0])], 'enum': list(spec['values'])}
    if t == 'optional':
        return schema(spec['of'])
    return {}


SECTION = re.compile(r'(Args|Arguments|Parameters|Params|Keyword Args|Keyword Arguments|Returns|Return|Yields|'
                     r'Raises|Examples?|Notes?|See Also|Attributes|Warns|Warnings|References|Todo):\s*\Z')
GOOGLE_ARGS = ('Args', 'Arguments', 'Parameters', 'Params', 'Keyword Args', 'Keyword Arguments')
DASHES = re.compile(r'-{3,}\s*\Z')


def _indent(line):
    return len(line) - len(line.lstrip())


def parse_doc(doc):
    """docstring → (第一段, {參數: 說明})；Google 風格 Args: 段或 NumPy 風格 Parameters／----------。"""
    if not doc:
        return None, {}
    lines = inspect.cleandoc(doc).splitlines()
    first = []
    for i, line in enumerate(lines):
        nxt = lines[i + 1] if i + 1 < len(lines) else ''
        if not line.strip() or SECTION.match(line.strip()) or DASHES.match(nxt.strip()):
            break
        first.append(line.strip())
    params = {}
    for i, line in enumerate(lines):
        head = line.strip()
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ''
        if head in ('Parameters', 'Other Parameters') and DASHES.match(nxt):
            _numpy_params(lines[i + 2:], _indent(line), params)
        elif head.endswith(':') and head[:-1] in GOOGLE_ARGS and not DASHES.match(nxt):
            _google_params(lines[i + 1:], _indent(line), params)
    return ' '.join(first) or None, params


def _google_params(lines, base, params):
    entry, current = None, None
    for line in lines:
        if not line.strip():
            continue
        ind = _indent(line)
        if ind <= base:
            break
        if entry is None:
            entry = ind
        if ind == entry:
            m = re.match(r'\*{0,2}(\w+)\s*(\([^)]*\))?\s*:\s*(.*)\Z', line.strip())
            current = m.group(1) if m else None
            if current:
                params[current] = m.group(3).strip()
        elif current:
            params[current] = (params[current] + ' ' + line.strip()).strip()


def _numpy_params(lines, base, params):
    current = []
    for i, line in enumerate(lines):
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ''
        if not line.strip():
            continue
        ind = _indent(line)
        if ind < base or (ind == base and DASHES.match(nxt)):
            break
        if ind == base:
            names = line.split(':', 1)[0]
            current = [n.strip().lstrip('*') for n in names.split(',') if n.strip()]
            for n in current:
                params[n] = ''
        else:
            for n in current:
                params[n] = (params[n] + ' ' + line.strip()).strip()


BLOCK = {'If': 'if', 'For': 'for', 'AsyncFor': 'async for', 'While': 'while', 'Try': 'try', 'TryStar': 'try',
         'With': 'with', 'AsyncWith': 'async with', 'Match': 'match'}


class _Finder(ast.NodeVisitor):
    """找出所有函式定義：頂層的、以及包在函式或類別裡的（後者只為了列「不是頂層」）。"""

    def __init__(self):
        self.found, self.stack = [], []

    def _func(self, node):
        self.found.append((node, self.stack[-1] if self.stack else None))
        self.stack.append(('函式', node.name))
        self.generic_visit(node)
        self.stack.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = _func

    def visit_ClassDef(self, node):
        self.stack.append(('類別', node.name))
        self.generic_visit(node)
        self.stack.pop()


def _literal(node):
    try:
        value = ast.literal_eval(node)
        json.dumps(value, allow_nan=False)
        return True, value
    except (ValueError, TypeError, SyntaxError, RecursionError):
        return False, None


def _function(node):
    """一個頂層函式 → (簽名 dict, 拒收原因清單, 警告清單)。"""
    reasons, warnings = [], []
    if isinstance(node, ast.AsyncFunctionDef):
        reasons.append('async def（不支援）')
    if node.decorator_list:
        reasons.append('有 decorator（@%s），簽名可能被改過' % ast.unparse(node.decorator_list[0]))
    if not TOOL_NAME.match(node.name):
        reasons.append('名字 %r 不能當工具名（只能英數底線、最多 64 字）' % node.name)
    a = node.args
    if a.posonlyargs:
        reasons.append('有 positional-only 參數（/ 前面的 %s）' % '、'.join(p.arg for p in a.posonlyargs))
    if a.vararg:
        reasons.append('有 *%s' % a.vararg.arg)
    if a.kwarg:
        reasons.append('有 **%s' % a.kwarg.arg)
    plain_defaults = [None] * (len(a.args) - len(a.defaults)) + list(a.defaults)
    params = []
    for p, default, kind in ([(p, d, 'normal') for p, d in zip(a.args, plain_defaults)]
                             + [(p, d, 'kwonly') for p, d in zip(a.kwonlyargs, a.kw_defaults)]):
        if p.annotation is None:
            reasons.append('參數 %s 沒有型別註解' % p.arg)
            continue
        try:
            spec = type_spec(p.annotation)
        except Unsupported as e:
            reasons.append('參數 %s：%s' % (p.arg, e))
            continue
        item = {'name': p.arg, 'type': spec, 'required': default is None, 'kind': kind}
        if default is not None:
            ok, value = _literal(default)
            if ok:
                item['default'] = value
        params.append(item)
    summary, docs = parse_doc(ast.get_docstring(node))
    if not summary:
        warnings.append('%s 沒有 docstring（第一段），描述先用函式名' % node.name)
    elif not reasons:
        warnings += ['%s 的參數 %s 沒有說明' % (node.name, p['name']) for p in params if not docs.get(p['name'])]
    sig = {'line': node.lineno, 'description': summary or node.name, 'params': params, 'has_doc': bool(summary),
           'docs': {p['name']: docs[p['name']] for p in params if docs.get(p['name'])}}
    return sig, reasons, warnings


def analyze(source, filename='<file>', only=None):
    """讀原始碼（不執行）→ {'rows': [(名字, 'ok'|'reject'|'skip', 原因, 行)], 'functions': {名: 簽名}, 'warnings': []}。"""
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as e:
        raise AgentError('SyntaxError', '%s 第 %s 行語法錯：%s' % (filename, e.lineno, e.msg))
    finder = _Finder()
    finder.visit(tree)
    direct = {id(n) for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    blocks = {}                                            # 頂層 if／for／try… 區塊裡的定義 → 區塊種類
    for stmt in tree.body:
        if id(stmt) not in direct:
            for n in ast.walk(stmt):
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    blocks.setdefault(id(n), BLOCK.get(type(stmt).__name__, type(stmt).__name__))
    top = {n.name for n, parent in finder.found if id(n) in direct}
    if only is not None:
        missing = [n for n in only if n not in top]
        if missing:
            raise AgentError('NotFound', '--only 寫了 %s，%s 裡沒有這個頂層函式（有：%s）'
                             % ('、'.join(missing), filename, '、'.join(sorted(top)) or '（無）'))
    rows, functions, warnings, seen = [], {}, [], {}
    for node, parent in sorted(finder.found, key=lambda x: x[0].lineno):
        name, line = node.name, node.lineno
        if parent is not None or id(node) not in direct:
            if name.startswith('_'):
                continue
            if only is not None and name not in only:
                rows.append([name, 'skip', '沒在 --only 裡', line])
            elif parent is not None:
                rows.append([name, 'reject', '不是頂層（在%s %s 裡）' % parent, line])
            else:
                rows.append([name, 'reject', '不是頂層（在頂層的 %s 區塊裡，import 後不一定有這支）' % blocks[id(node)], line])
            continue
        if name.startswith('_'):
            rows.append([name, 'skip', '私有（底線開頭）', line])
            continue
        if only is not None and name not in only:
            rows.append([name, 'skip', '沒在 --only 裡', line])
            continue
        sig, reasons, warns = _function(node)
        if name in seen:                                   # 同名再定義一次：以後面的為準
            earlier = seen[name]
            earlier[1], earlier[2] = 'reject', '第 %d 行又定義了一次同名的，以後面的為準' % line
            functions.pop(name, None)
        row = [name, 'reject' if reasons else 'ok', '；'.join(reasons), line]
        rows.append(row)
        seen[name] = row
        if not reasons:
            functions[name] = sig
            warnings += warns
    return {'rows': rows, 'functions': functions, 'warnings': warnings}


def tool_entry(pack, name, sig):
    props, required = {}, []
    for p in sig['params']:
        prop = schema(p['type'])
        if p['name'] in sig['docs']:
            prop['description'] = sig['docs'][p['name']]
        if 'default' in p and p['default'] is not None:
            prop['default'] = p['default']
        props[p['name']] = prop
        if p['required']:
            required.append(p['name'])
    params = {'type': 'object', 'properties': props}
    if required:
        params['required'] = required
    return {'type': 'function',
            'function': {'name': name, 'description': sig['description'], 'parameters': params},
            '_meta': {'argv': ['tools/%s/run' % pack, name]}}


# ------------------------------------------------------------------ wrap-py：產 ----

WRAP_RUN = r'''#!/usr/bin/env python3
"""aos-agent tools wrap-py 產的 run：run <函式名>，stdin 讀 arguments、照 wrap.json 記下的簽名驗型別，
從 src/ 裡的原檔副本 import 函式來叫。run --check-import 只試 import 一次（tools test 用）。
回傳 str 原樣印；其他 json.dumps；例外＝PythonError（不噴 Traceback）。"""
import sys
sys.dont_write_bytecode = True
import contextlib  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
from _common import HERE, ToolError, fail, report, run  # noqa: E402

KIND = {'str': 'a string', 'int': 'an integer', 'float': 'a number', 'bool': 'a boolean',
        'list': 'an array', 'dict': 'an object'}


def wrap():
    with open(os.path.join(HERE, 'wrap.json'), encoding='utf-8') as f:
        return json.load(f)


def check(value, spec, where):
    """照型別記號驗一個值；回要傳給函式的值（float 參數收整數時轉成小數）。"""
    t = spec['t']
    if t == 'any':
        return value
    if t == 'optional':
        return None if value is None else check(value, spec['of'], where)
    if t == 'literal':
        for v in spec['values']:
            if type(value) is type(v) and value == v:
                return value
        fail('BadArguments', '%s must be one of %s' % (where, json.dumps(spec['values'], ensure_ascii=False)))
    ok = {'str': lambda v: isinstance(v, str),
          'int': lambda v: isinstance(v, int) and not isinstance(v, bool),
          'float': lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
          'bool': lambda v: isinstance(v, bool),
          'list': lambda v: isinstance(v, list),
          'dict': lambda v: isinstance(v, dict)}[t](value)
    if not ok:
        fail('BadArguments', '%s must be %s' % (where, KIND[t]))
    if t == 'float':
        return float(value)
    if t == 'list':
        return [check(v, spec['of'], '%s[%d]' % (where, i)) for i, v in enumerate(value)]
    if t == 'dict':
        return {k: check(v, spec['of'], '%s["%s"]' % (where, k)) for k, v in value.items()}
    return value


def load(info):
    path = os.path.join(HERE, info['copy'])
    name = 'aos_wrapped_' + info['module']
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        with contextlib.redirect_stdout(sys.stderr):     # import 時印的東西不混進結果
            spec.loader.exec_module(module)
    except BaseException as e:  # noqa: B902 —— SystemExit、KeyboardInterrupt 也算 import 失敗
        fail('ImportFailed', 'cannot import %s: %s: %s' % (info['copy'], type(e).__name__, e))
    return module


def main(args, root):
    info = wrap()
    name = sys.argv[1] if len(sys.argv) > 1 else ''
    sig = info['functions'].get(name)
    if sig is None:
        fail('UnknownFunction', 'this package has no function %r' % name)
    known = {p['name'] for p in sig['params']}
    extra = sorted(k for k in args if k not in known)
    if extra:
        fail('BadArguments', 'unknown argument(s): %s' % ', '.join(extra))
    keyword = {}
    for p in sig['params']:
        if p['name'] not in args or (args[p['name']] is None and not p['required']):
            if p['required']:
                fail('BadArguments', 'missing required argument "%s"' % p['name'])
            continue
        value = check(args[p['name']], p['type'], 'argument "%s"' % p['name'])
        keyword[p['name']] = value
    os.chdir(root)                                        # 函式裡的相對路徑從工作根目錄算
    fn = getattr(load(info), name, None)
    if not callable(fn):
        fail('ImportFailed', '%s has no function %s' % (info['copy'], name))
    try:
        with contextlib.redirect_stdout(sys.stderr):     # 函式自己 print 的走 stderr，stdout 只放結果
            result = fn(**keyword)
    except BaseException as e:  # noqa: B902 —— KeyboardInterrupt、SystemExit 也一樣轉成 PythonError，不噴 Traceback
        fail('PythonError', '%s: %s' % (type(e).__name__, e), exception=type(e).__name__)
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, RecursionError) as e:
        fail('ResultNotJSON', '%s returned %s, which is not JSON-serializable: %s'
             % (name, type(result).__name__, e))


def check_import():
    try:
        load(wrap())
    except ToolError as e:
        return report(e)
    except Exception as e:
        return report(ToolError('InternalError', '%s: %s' % (type(e).__name__, e)))
    sys.stdout.write('import ok\n')
    return 0


if __name__ == '__main__':
    sys.exit(check_import() if sys.argv[1:] == ['--check-import'] else run(main))
'''

WRAP_FIXED = ('run', 'wrap.json', '_common.py', 'config.json', 'README.md')
STATUS = {'ok': '收', 'reject': '拒收', 'skip': '跳過'}
STATUS_COL = {'ok': '收  ', 'reject': '拒收', 'skip': '跳過'}   # 中文字佔兩格，對齊用


def _pack_name(stem):
    name = re.sub(r'[^A-Za-z0-9_-]', '_', stem)
    if not name or not NAME.match(name):
        name = '_' + name
    return name


def _wrap_readme(pack, src_name, result, path):
    ok = [r for r in result['rows'] if r[1] == 'ok']
    other = [r for r in result['rows'] if r[1] != 'ok']
    lines = ['# %s — 從 %s 包出來的工具包' % (pack, src_name), '',
             '`aos-agent tools wrap-py` 用 `ast` 靜態讀原檔（沒有 import、沒有執行）產的。原檔副本在 `src/%s`，'
             '`wrap.json` 記了原檔路徑、sha256、每支的簽名與拒收表。' % src_name, '',
             '## 收了哪些', '', '| 工具 | 參數（* 必填） | 描述 |', '|---|---|---|']
    for name, _, _, _ in ok:
        sig = result['functions'][name]
        params = '、'.join(p['name'] + ('*' if p['required'] else '') for p in sig['params']) or '（無）'
        lines.append('| `%s` | %s | %s |' % (name, params, sig['description'].replace('|', '\\|')))
    lines += ['', '## 拒收／跳過', '']
    if other:
        lines += ['| 函式 | 行 | 為什麼 |', '|---|---|---|']
        lines += ['| `%s` | %d | %s：%s |' % (n, line, STATUS[s], why.replace('|', '\\|')) for n, s, why, line in other]
    else:
        lines.append('（沒有）')
    lines += ['', '## 怎麼跑', '',
              '`run <函式名>`：stdin 讀 arguments JSON，照記下的簽名驗型別（多給、少給必填、型別不對＝`BadArguments`），'
              '從 `src/` 的副本 import 函式來叫。回傳字串原樣印，其他 `json.dumps`（不能＝`ResultNotJSON`）；'
              '函式丟例外＝`PythonError`（附例外類別與訊息，不噴 Traceback）；import 失敗＝`ImportFailed`。'
              '函式裡的相對路徑從工作根目錄算（關牢時是牢裡的起點 `/work/ws` 之類）；函式自己 `print` 的走 stderr。', '',
              '## 關牢', '',
              '工具檔沒寫 `_jail`＝預設關牢。這個包**不需要任何額外掛載**：裝進有 `access.json` 的家，就關在牢裡跑，'
              '程式與原檔副本在牢裡的 `/opt/tool`（唯讀），函式碰得到的檔只有 `access.json` 掛進 `/work` 的資料夾。'
              '原檔 import 的套件要在牢裡的 `python3`（主機的 `/usr` 唯讀掛進去）找得到；裝在家目錄的套件（`pip --user`、venv）牢裡看不到。', '',
              '## 試、裝', '', '```sh',
              'aos-agent tools test %s            # 先試 import 一次，再跑自動案例' % path,
              'aos-agent tools add %s --target 家' % path, '```',
              '', '原檔改了要重包：`aos-agent tools wrap-py <原檔> --force`（副本不會自己跟著變）。', '']
    return '\n'.join(lines)


def _print_rows(result):
    width = max([len(r[0]) for r in result['rows']] + [4])
    for name, status, why, line in result['rows']:
        tail = '' if status == 'ok' else '（%s）' % why
        print('%s  %-*s  第 %d 行%s' % (STATUS_COL[status], width, name, line, tail))
    for w in result['warnings']:
        print('警告：' + w)


def _read_py(file):
    src = Path(os.path.abspath(os.path.expanduser(file)))
    try:
        data = src.read_bytes()
    except FileNotFoundError:
        raise AgentError('NotFound', '找不到 %s' % src)
    except OSError as e:
        raise AgentError('ReadFailed', '讀不到 %s：%s' % (src, e.strerror or e))
    try:
        source = data.decode('utf-8')
    except UnicodeDecodeError:
        raise AgentError('ReadFailed', '%s 不是 UTF-8 文字檔' % src)
    return src, data, source


def _wrap_pack(src, name, out):
    pack = name if name is not None else _pack_name(src.stem)
    if not NAME.match(pack):
        raise AgentError('BadName', '工具包名字 %r 只能用英數、底線、連字號（不能以 . 或 - 開頭）' % pack)
    folder = _out_dir(out)
    package_files(pack, [(pack + '.json', '', False)] + [(f, '', False) for f in WRAP_FIXED])  # 先擋撞名（wrap、config）
    return pack, folder


def wrap_py(file, only=None, name=None, out=None, force=False, describe=None):
    src, data, source = _read_py(file)
    pack, folder = _wrap_pack(src, name, out)
    result = analyze(source, str(src), only)
    applied = None
    if describe is not None:                      # 第三波 W3-2：照人看過的描述提案補描述（spec/aos-agent/tools-llm.md）
        applied = apply_describe(describe, result, hashlib.sha256(data).hexdigest())
    _print_rows(result)
    if not result['functions']:
        raise AgentError('NothingToWrap', '%s 沒有一支函式能包成工具（看上面的表：要頂層、非底線開頭、'
                         '每個參數都有支援的型別註解）；不寫任何檔' % src)
    _check_dest(folder, pack, force)
    tools = [tool_entry(pack, n, sig) for n, sig in result['functions'].items()]
    info = {'_type': 'aos_wrap_py', '_version': 1, 'source': str(src), 'copy': 'src/' + src.name,
            'module': re.sub(r'\W', '_', src.stem), 'sha256': hashlib.sha256(data).hexdigest(),
            'generated': datetime.datetime.now().astimezone().isoformat(timespec='seconds'),
            'functions': {n: {'line': s['line'], 'params': s['params']} for n, s in result['functions'].items()},
            'rejected': [{'name': r[0], 'line': r[3], 'reason': r[2]} for r in result['rows'] if r[1] == 'reject'],
            'skipped': [{'name': r[0], 'line': r[3], 'reason': r[2]} for r in result['rows'] if r[1] == 'skip']}
    if applied is not None:
        info['describe'] = applied
    path = _shown(folder / pack)
    files = package_files(pack, [(pack + '.json', _dump(tools), False), ('run', WRAP_RUN, True),
                                 ('src/' + src.name, data, False), ('wrap.json', _dump(info), False),
                                 ('_common.py', BASE_COMMON.read_bytes(), False),
                                 ('config.json', _dump({'root': 'workspace'}), False),
                                 ('README.md', _wrap_readme(pack, src.name, result, path), False)])
    dest = publish(folder, pack, files, force)
    print('生了 %s/：%d 支工具（%s）' % (dest, len(tools), '、'.join(result['functions'])))
    print('下一步：aos-agent tools test %s' % path)
    print('裝進家：aos-agent tools add %s --target 家' % path)
    return 0


# ------------------------------------------------------------------ wrap-py：模型補描述（第三波 W3-2，spec/aos-agent/tools-llm.md） ----

DESCRIBE_TYPE = 'aos_wrap_py_describe'
DESCRIBE_MAX = 200                                       # 描述、參數說明最多幾個字
CONTROL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]')   # 控制字元（ESC、NUL…）：一律不收（審查 S1）
DESCRIBE_SYSTEM = ('You write short descriptions for Python functions that an AI agent will call as tools. '
                   'Read the code to see what each function really does. Reply with one JSON object only.')


def _needs(result):
    """收了的函式裡缺什麼：{函式: {'description': 缺描述?, 'params': [缺說明的參數]}}（什麼都不缺的不列）。"""
    need = {}
    for fname, sig in result['functions'].items():
        miss = [p['name'] for p in sig['params'] if p['name'] not in sig['docs']]
        if not sig.get('has_doc') or miss:
            need[fname] = {'description': not sig.get('has_doc'), 'params': miss}
    return need


def _clean_text(value):
    return ' '.join(value.split()) if isinstance(value, str) else None


def check_describe(data, result):
    """模型回的（或人改過的）描述 → (收的 {函式: {'description'?, 'params': {}}}, 丟掉的 [(標籤, 原因)])。
    只收已知的函式與參數名；描述非空、≤ 200 字；已有 docstring／說明的不覆蓋。"""
    if not isinstance(data, dict):
        return {}, [('（整份）', '要是 {函式名: {"description", "params"}} 物件')]
    functions, need = result['functions'], _needs(result)
    ok, dropped = {}, []
    for fname, entry in data.items():
        if fname not in functions:
            dropped.append((fname, '不認得的函式（這次收的只有 %s）' % ('、'.join(functions) or '（無）')))
            continue
        if not isinstance(entry, dict):
            dropped.append((fname, '要是 {"description", "params"} 物件'))
            continue
        got = {'params': {}}
        if entry.get('description') is not None:
            text = _clean_text(entry['description'])
            if fname not in need or not need[fname]['description']:
                dropped.append((fname, '已有 docstring，不覆蓋'))
            elif not text:
                dropped.append((fname, '描述是空的或不是字串'))
            elif CONTROL.search(text):
                dropped.append((fname, '描述含控制字元（ESC、NUL…）'))
            elif len(text) > DESCRIBE_MAX:
                dropped.append((fname, '描述 %d 字，超過 %d' % (len(text), DESCRIBE_MAX)))
            else:
                got['description'] = text
        params = entry.get('params') or {}
        if not isinstance(params, dict):
            dropped.append((fname, 'params 要是 {參數: 說明}'))
            params = {}
        known = [p['name'] for p in functions[fname]['params']]
        for pname, ptext in params.items():
            label = '%s.%s' % (fname, pname)
            text = _clean_text(ptext)
            if pname not in known:
                dropped.append((label, '%s 沒有這個參數（有：%s）' % (fname, '、'.join(known) or '（無）')))
            elif pname in functions[fname]['docs']:
                dropped.append((label, '已有說明，不覆蓋'))
            elif not text:
                dropped.append((label, '說明是空的或不是字串'))
            elif CONTROL.search(text):
                dropped.append((label, '說明含控制字元（ESC、NUL…）'))
            elif len(text) > DESCRIBE_MAX:
                dropped.append((label, '說明 %d 字，超過 %d' % (len(text), DESCRIBE_MAX)))
            else:
                got['params'][pname] = text
        if 'description' in got or got['params']:
            ok[fname] = got
    return ok, dropped


def describe_prompt(sources, need):
    """sources＝{函式名: 原始碼}；need＝_needs() 的結果。"""
    lines = []
    for fname, what in need.items():
        want = (['a "description"'] if what['description'] else []) + (
            ['"params" for %s' % ', '.join(what['params'])] if what['params'] else [])
        lines.append('- %s: %s' % (fname, ' and '.join(want)))
    code = '\n\n'.join(sources.get(f) or '' for f in need)
    return ('For the functions below, return {"<function name>": {"description": "<one sentence: what it does and '
            'what it returns>", "params": {"<param>": "<what to pass>"}}}.\n'
            'Only these functions and fields:\n%s\n'
            'Each text: one short sentence, under %d characters. Describe what the code actually does, '
            'not what the name suggests.\n\n```python\n%s\n```' % ('\n'.join(lines), DESCRIBE_MAX, code))


def _function_sources(source):
    tree = ast.parse(source)
    return {n.name: ast.get_source_segment(source, n) for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def describe_with_llm(file, only=None, name=None, out=None, force=False, model=None, ask=None):
    """wrap-py --describe-with-llm：缺描述的函式一次打包問模型，寫提案檔 <out>/<PACK>.describe.json；不產包。"""
    import aos_llm_ask
    src, data, source = _read_py(file)
    pack, folder = _wrap_pack(src, name, out)
    result = analyze(source, str(src), only)
    if not result['functions']:
        _print_rows(result)
        raise AgentError('NothingToWrap', '%s 沒有一支函式能包成工具；不問模型' % src)
    need = _needs(result)
    if not need:
        raise AgentError('NothingToDescribe', '收的函式都有 docstring 與參數說明，不用問模型；直接 wrap-py 就好')
    target = folder / (pack + '.describe.json')
    if os.path.lexists(target) and not force:                # 問模型之前先擋，免得白花一次
        raise AgentError('AlreadyExists', '%s 已經在了（要蓋掉加 --force）' % target)
    ask = ask or aos_llm_ask.ask_json
    reply, got = ask(DESCRIBE_SYSTEM, describe_prompt(_function_sources(source), need), alias=model)
    ok, dropped = check_describe(reply, result)
    proposal = {'_type': DESCRIBE_TYPE, '_version': 1, 'source': str(src), 'sha256': hashlib.sha256(data).hexdigest(),
                'generated': datetime.datetime.now().astimezone().isoformat(timespec='seconds'),
                'model': got.get('model'), 'alias': got.get('alias'), 'usage': got.get('usage'), 'ms': got.get('ms'),
                'functions': ok, 'dropped': [{'item': a, 'reason': b} for a, b in dropped]}
    write_json_file(target, proposal, force)
    _print_describe(result, ok, dropped)
    print(aos_llm_ask.usage_line(got), file=sys.stderr)
    print('提案寫在 %s（%d 支有提案、%d 條丟掉；還沒產包）' % (target, len(ok), len(dropped)))
    extra = ''.join(' %s %s' % (k, shlex.quote(v)) for k, v in (('--only', ','.join(only) if only else None),
                                                                ('--name', name), ('--out', out)) if v)
    print('看過沒問題（可以先改提案檔；這一步不叫模型）：aos-agent tools wrap-py %s --describe %s%s'
          % (shlex.quote(file), shlex.quote(_shown(target)), extra))
    return 0


def _print_describe(result, ok, dropped):
    """函式｜現在的描述（機械版＝函式名）｜模型提的。"""
    width = max([len(n) for n in result['functions']] + [4])
    print('%-*s  %-30s  %s' % (width, '函式', '現在的描述', '模型提的'))
    for fname, sig in result['functions'].items():
        now = sig['description'] if sig.get('has_doc') else '%s（沒 docstring）' % fname
        new = ok.get(fname, {})
        fallback = '（有 docstring，不改）' if sig.get('has_doc') else '（沒提）'
        print('%-*s  %-30s  %s' % (width, fname, now[:30], new.get('description', fallback)))
        for pname, text in new.get('params', {}).items():
            print('%-*s    參數 %s：%s' % (width, '', pname, text))
    for label, why in dropped:
        print('丟掉  %s（%s）' % (label, why))


def write_json_file(target, value, force):
    """寫一個 JSON 檔（暫存＋rename）；已在要 --force，符號連結或非一般檔一律不蓋。"""
    if os.path.lexists(target) and not force:
        raise AgentError('AlreadyExists', '%s 已經在了（要蓋掉加 --force）' % target)
    if os.path.islink(target) or (os.path.lexists(target) and not target.is_file()):
        raise AgentError('AlreadyExists', '%s 不是一般檔（或是符號連結），--force 也不蓋' % target)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix='.%s.' % target.name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(_dump(value))
        os.replace(tmp, target)
    except BaseException:
        os.unlink(tmp)
        raise


def apply_describe(path, result, sha):
    """wrap-py --describe FILE：照提案補描述（改 result 裡的簽名）。原檔 sha 對不上＝SourceChanged；
    提案有任何一條沒過機械檢查＝DescribeInvalid（人給的就要整份對）。回寫進 wrap.json 的紀錄。"""
    p = Path(os.path.abspath(os.path.expanduser(path)))
    try:
        raw = p.read_bytes()
        data = json.loads(raw.decode('utf-8'))
    except FileNotFoundError:
        raise AgentError('NotFound', '找不到 --describe %s' % p)
    except (OSError, ValueError, UnicodeError) as e:
        raise AgentError('DescribeInvalid', '讀不了 --describe %s：%s' % (p, e))
    if not isinstance(data, dict) or data.get('_type') != DESCRIBE_TYPE or data.get('_version') != 1 \
            or not isinstance(data.get('functions'), dict):
        raise AgentError('DescribeInvalid', '%s 不是 wrap-py 描述提案（要 _type %s、_version 1、functions）'
                         % (p, DESCRIBE_TYPE))
    if data.get('sha256') != sha:
        raise AgentError('SourceChanged', '原檔跟提案記的不一樣了（sha256 %s… ≠ %s…）；重新提案'
                         % (sha[:12], str(data.get('sha256'))[:12]))
    wanted = {k: v for k, v in data['functions'].items() if k in result['functions']}
    skipped = [k for k in data['functions'] if k not in result['functions']]
    ok, dropped = check_describe(wanted, result)
    if dropped:
        raise AgentError('DescribeInvalid', '提案有 %d 條沒過機械檢查：%s' % (
            len(dropped), '；'.join('%s：%s' % d for d in dropped)))
    done = set()
    for fname, entry in ok.items():
        sig = result['functions'][fname]
        if 'description' in entry:
            sig['description'] = entry['description']
            sig['has_doc'] = True
            done.add('%s 沒有 docstring（第一段），描述先用函式名' % fname)
        sig['docs'].update(entry['params'])
        done.update('%s 的參數 %s 沒有說明' % (fname, q) for q in entry['params'])
    result['warnings'] = [w for w in result['warnings'] if w not in done]
    for fname in skipped:
        result['warnings'].append('提案裡的 %s 這次沒包（沒收或沒在 --only 裡），略過' % fname)
    print('照 %s 補了 %d 支的描述' % (p, len(ok)))
    return {'file': str(p), 'sha256': hashlib.sha256(raw).hexdigest(), 'functions': sorted(ok)}


# ------------------------------------------------------------------ tools test ----

def _tokens(tool):
    from aos_agent_context import tokens
    return tokens(json.dumps(tool['function'], ensure_ascii=False))


def jail_ready():
    """aos-jail 跑不跑得起來（真的開一次 bwrap 跑 true）。回 (可以?, 白話)。"""
    from aos_agent_access import JAIL
    if shutil.which('bwrap') is None:
        return False, '找不到 bwrap'
    try:
        r = subprocess.run([JAIL, '--', 'true'], stdin=subprocess.DEVNULL, capture_output=True, text=True,
                           timeout=15)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, 'aos-jail 跑不起來：%s' % e
    if r.returncode != 0:
        return False, 'aos-jail 跑不起來：%s' % (r.stderr.strip().splitlines() or ['退 %d' % r.returncode])[-1]
    return True, ''


class Result:
    def __init__(self, code=None, out='', err='', ms=0, timed_out=False, spawn_error=None, dropped=0,
                 stuck=None):
        self.code, self.out, self.err, self.ms = code, out, err, ms
        self.timed_out, self.spawn_error = timed_out, spawn_error
        self.dropped, self.stuck = dropped, stuck        # 丟掉的輸出位元組；殺不掉的行程說明


def _killpg(pid):
    try:
        os.killpg(pid, signal.SIGKILL)
    except OSError:
        pass


def pump(proc, data, limit, cap=None):
    """餵 stdin、收 stdout／stderr（每條只留最後 cap 位元組，邊讀邊丟），不靠執行緒、不會無限等：
    - 到 limit 秒整個行程群組 SIGKILL，再最多等 KILL_GRACE 秒；
    - 主行程結束後管子還被別人（另開 session 的子孫）握著，最多再收 DRAIN_GRACE 秒就關掉。
    回 (退出碼或 None, stdout bytes, stderr bytes, 逾時?, 丟了幾位元組, 殺不掉的說明或 None)。"""
    cap = OUTPUT_CAP if cap is None else cap
    sel = selectors.DefaultSelector()
    bufs = {proc.stdout: bytearray(), proc.stderr: bytearray()}
    dropped = 0
    for f in bufs:
        os.set_blocking(f.fileno(), False)
        sel.register(f, selectors.EVENT_READ)
    if data:
        os.set_blocking(proc.stdin.fileno(), False)
        sel.register(proc.stdin, selectors.EVENT_WRITE)
    else:
        proc.stdin.close()
    offset, timed_out, stop_at = 0, False, None
    deadline = time.monotonic() + limit
    try:
        while sel.get_map():
            now = time.monotonic()
            if stop_at is None and proc.poll() is not None:
                stop_at = now + DRAIN_GRACE
            if not timed_out and now >= deadline:
                timed_out = True
                _killpg(proc.pid)
                stop_at = now + KILL_GRACE
            if stop_at is not None and now >= stop_at:
                break
            ends = [now + 0.2] + ([deadline] if not timed_out else []) + ([stop_at] if stop_at else [])
            for key, _ in sel.select(max(min(ends) - now, 0)):
                f = key.fileobj
                if f is proc.stdin:
                    try:
                        offset += os.write(f.fileno(), data[offset:offset + 65536])
                    except BlockingIOError:
                        continue
                    except OSError:                       # 對方不讀了（BrokenPipe 等）
                        offset = len(data)
                    if offset >= len(data):
                        sel.unregister(f)
                        f.close()
                    continue
                try:
                    chunk = os.read(f.fileno(), 65536)
                except BlockingIOError:
                    continue
                if not chunk:
                    sel.unregister(f)
                    continue
                buf = bufs[f]
                buf += chunk
                if len(buf) > cap:
                    dropped += len(buf) - cap
                    del buf[:len(buf) - cap]
    finally:
        sel.close()
        for f in (proc.stdin, proc.stdout, proc.stderr):
            try:
                f.close()
            except OSError:
                pass
    _killpg(proc.pid)                                     # 同一群組留下的背景行程也收掉
    stuck = None
    try:
        proc.wait(KILL_GRACE)
    except subprocess.TimeoutExpired:
        stuck = '行程 %d 送了 SIGKILL 還是沒結束（可能卡在核心裡），沒等它' % proc.pid
    return proc.returncode, bytes(bufs[proc.stdout]), bytes(bufs[proc.stderr]), timed_out, dropped, stuck


class Runner:
    """拋棄式的假 agent 家：home/tools/<包>/（程式）＋home/workspace/（工作根目錄；關牢時掛成 /work/ws）。"""

    def __init__(self, home, jail):
        self.home, self.jail = home, jail
        self.ws = home / 'workspace'

    def decode(self, tool):
        """照 aos-agent 送件的方式解 _meta（中心＝家）；解不開丟 AgentError。"""
        import aos_inst
        try:
            return aos_inst.load_obj(tool['_meta'], str(self.home), env=os.environ)
        except aos_inst.InstError as e:
            raise AgentError('MetaInvalid', '_meta 解不開：%s: %s' % (e.code, e.msg))

    def argv(self, tool):
        """回 (argv, cwd, env)；關牢就照 aos-agent 的 jail_argv 包成 aos-jail。"""
        decoded = self.decode(tool)
        if self.jail:
            from aos_agent_batch import jail_argv
            access = {'mounts': {'ws': {'path': str(self.ws), 'ro': False}}, 'cwd': 'ws', 'net': False}
            return jail_argv(decoded, access), decoded['cwd'], dict(os.environ)
        env = {} if decoded['envs_clear'] else dict(os.environ)
        env.update(decoded['envs'])
        env.pop('AOS_TOOL_ROOT', None)                   # 不關牢時工作根目錄照 config.json，別吃到外面殼的設定
        env.pop('AOS_TOOL_FENCE', None)
        return decoded['argv'], decoded['cwd'], env

    def program(self, tool):
        """程式在不在、有沒有執行位（牢外看）；回白話的問題或 None。"""
        try:
            decoded = self.decode(tool)
        except AgentError as e:
            return e.msg
        if not decoded['argv']:
            return '_meta.argv 是空的'
        prog = decoded['argv'][0]
        if '/' in prog:
            full = os.path.join(decoded['cwd'], prog)
            if not os.path.isfile(full):
                return '找不到程式 %s' % prog
            if not os.access(full, os.X_OK):
                return '程式 %s 沒有執行位（chmod +x）' % prog
            return None
        if self.jail:
            return None                                   # 牢裡只找 /usr/local/bin:/usr/bin:/bin，跑了才知道
        return None if shutil.which(prog) else '在 PATH 上找不到程式 %s' % prog

    def run(self, tool, stdin):
        try:
            argv, cwd, env = self.argv(tool)
        except AgentError as e:
            return Result(spawn_error=e.msg)
        limit = tool.get('_timeout_ms', 60000) or TEST_TIMEOUT_MS
        limit = min(limit, TEST_TIMEOUT_MS) / 1000
        start = time.monotonic()
        try:
            proc = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, start_new_session=True)
        except OSError as e:
            return Result(spawn_error='跑不起來：%s' % (e.strerror or e))
        code, out, err, timed_out, dropped, stuck = pump(proc, stdin.encode('utf-8'), limit)
        ms = int((time.monotonic() - start) * 1000)
        return Result(code, out.decode('utf-8', 'replace'), err.decode('utf-8', 'replace'), ms, timed_out,
                      dropped=dropped, stuck=stuck)

    def write_file(self, rel, content):
        """固定案例的 files 寫進 workspace：從 workspace 的目錄 fd 一層層開，每層都不跟符號連結（O_NOFOLLOW），
        最後的檔也 O_NOFOLLOW、有硬連結（nlink > 1）不寫——前面的工具在 workspace 放的連結帶不出去。"""
        parts = Path(rel).parts
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, 'O_CLOEXEC', 0)
        fd = os.open(self.ws, flags)
        try:
            for part in parts[:-1]:
                try:
                    nxt = os.open(part, flags, dir_fd=fd)
                except FileNotFoundError:
                    os.mkdir(part, 0o755, dir_fd=fd)
                    nxt = os.open(part, flags, dir_fd=fd)
                os.close(fd)
                fd = nxt
            out = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | getattr(os, 'O_CLOEXEC', 0),
                          0o644, dir_fd=fd)
            try:
                st = os.fstat(out)
                if not stat.S_ISREG(st.st_mode) or st.st_nlink > 1:
                    raise OSError(errno.EPERM, '%s 不是一般檔或有硬連結' % rel)
                os.ftruncate(out, 0)
                os.write(out, content.encode('utf-8'))
            finally:
                os.close(out)
        finally:
            os.close(fd)


def error_code(out):
    """最後一行（非空）是 {"ok": false, "error": 代號, …} 就回代號，否則 None。"""
    lines = [l for l in out.splitlines() if l.strip()]
    if not lines:
        return None
    try:
        obj = json.loads(lines[-1])
    except ValueError:
        return None
    if isinstance(obj, dict) and obj.get('ok') is False and isinstance(obj.get('error'), str):
        return obj['error']
    return None


def _cut(text):
    text = ' '.join(text.split())
    return text if len(text) <= TAIL else text[:TAIL] + '…'


def got(res):
    if res.spawn_error:
        return res.spawn_error
    if res.timed_out:
        return '逾時被砍（%d 毫秒）%s' % (res.ms, '；' + res.stuck if res.stuck else '')
    lines = [l for l in res.out.splitlines() if l.strip()]
    last = lines[-1] if lines else '（stdout 空的）'
    text = '退 %s，最後一行：%s' % (res.code, _cut(last))
    if res.code not in (0, 1) or (res.code == 1 and error_code(res.out) is None):
        err = [l for l in res.err.splitlines() if l.strip()]
        if err:
            text += '；stderr 最後一行：%s' % _cut(err[-1])
    if res.dropped:
        text += '（輸出太多，前面丟了 %d 位元組）' % res.dropped
    if res.stuck:
        text += '；' + res.stuck
    return text


def judge(res, expect, contains=None):
    """expect：'contract'（正例：照契約回話就算過）、'ok'（退 0）或錯誤代號。回 (過?, 期待的白話)。"""
    want = {'contract': '照契約回話（退 0，或退 1 且最後一行 JSON 錯誤、代號不是 InternalError／BadArguments）',
            'ok': '成功（退 0）'}.get(expect, '錯誤 %s（退 1，最後一行 JSON）' % expect)
    if contains:
        want += '，輸出含 %r' % contains
    if res.spawn_error or res.timed_out or 'Traceback (most recent call last)' in res.out:
        return False, want
    code = error_code(res.out)
    if expect == 'contract':
        ok = res.code == 0 or (res.code == 1 and code is not None and code not in ('InternalError', 'BadArguments'))
    elif expect == 'ok':
        ok = res.code == 0
    else:
        ok = res.code == 1 and code == expect
    if ok and contains and contains not in res.out:
        ok = False
    return ok, want


def sample(prop):
    """照 JSON Schema 給一個合法的樣本值；不認得的型別回 (False, None)。"""
    if not isinstance(prop, dict):
        return False, None
    if isinstance(prop.get('enum'), list) and prop['enum']:
        return True, prop['enum'][0]
    kind = prop.get('type')
    if isinstance(kind, list):
        kind = next((k for k in kind if k != 'null'), None)
    if kind == 'string':
        return True, 'x'
    if kind == 'integer':
        lo, hi = prop.get('minimum'), prop.get('maximum')
        if isinstance(lo, (int, float)) and not isinstance(lo, bool):
            return True, int(-(-lo // 1))
        return True, 1 if not isinstance(hi, (int, float)) or hi >= 1 else int(hi // 1)
    if kind == 'number':
        lo, hi = prop.get('minimum'), prop.get('maximum')
        if isinstance(lo, (int, float)) and not isinstance(lo, bool) and lo > 1.5:
            return True, lo
        if isinstance(hi, (int, float)) and not isinstance(hi, bool) and hi < 1.5:
            return True, hi
        return True, 1.5
    if kind == 'boolean':
        return True, True
    if kind == 'array':
        return True, []
    if kind == 'object':
        return True, {}
    return False, None


WRONG = {'string': 123, 'integer': 'x', 'number': 'x', 'boolean': 'x', 'array': 'x', 'object': 'x'}


def auto_cases(tool):
    """從 parameters 生案例：[(案例名, arguments 的 JSON 字串, 期待)]。"""
    params = tool['function'].get('parameters') or {}
    props = params.get('properties') if isinstance(params.get('properties'), dict) else {}
    required = [r for r in params.get('required') or [] if isinstance(r, str)]
    base, strings = {}, 0
    for name in required:
        ok, value = sample(props.get(name, {}))
        if value == 'x' and not (isinstance(props.get(name), dict) and 'enum' in props[name]):
            strings += 1                                  # 每個字串參數給不同的值（edit 的 old／new 一樣會被拒）
            value = 'x' if strings == 1 else 'x%d' % strings
        base[name] = value if ok else 'x'
    cases = [('ok', json.dumps(base, ensure_ascii=False), 'contract')]
    for name, prop in props.items():
        kind = prop.get('type') if isinstance(prop, dict) else None
        if isinstance(kind, list):
            kind = next((k for k in kind if k != 'null'), None)
        if kind in WRONG:
            args = dict(base, **{name: WRONG[kind]})
            cases.append(('type:' + name, json.dumps(args, ensure_ascii=False), 'BadArguments'))
    for name in required:
        args = {k: v for k, v in base.items() if k != name}
        cases.append(('missing:' + name, json.dumps(args, ensure_ascii=False), 'BadArguments'))
    cases.append(('not-object', '[]', 'BadArguments'))
    return cases


def load_cases(path, names):
    """固定案例檔：JSON 陣列，每條 {tool, args, expect, contains?, name?, files?}。壞了＝CasesInvalid。"""
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:
        raise AgentError('NotFound', '找不到案例檔 %s' % path)
    except (OSError, ValueError, UnicodeError) as e:
        raise AgentError('CasesInvalid', '讀不了案例檔 %s：%s' % (path, e))
    if not isinstance(data, list):
        raise AgentError('CasesInvalid', '%s 頂層要是陣列' % path)
    out = []
    for i, c in enumerate(data):
        where = '%s 第 %d 條' % (path, i)
        if not isinstance(c, dict) or not isinstance(c.get('tool'), str) or 'args' not in c \
                or not isinstance(c.get('expect'), str) or not c['expect']:
            raise AgentError('CasesInvalid', '%s：要是物件，有 tool（字串）、args、expect（"ok" 或錯誤代號）' % where)
        if c['tool'] not in names:
            raise AgentError('CasesInvalid', '%s：包裡沒有工具 %s（有：%s）' % (where, c['tool'], '、'.join(names)))
        if 'contains' in c and not isinstance(c['contains'], str):
            raise AgentError('CasesInvalid', '%s：contains 要是字串' % where)
        files = c.get('files', {})
        if not isinstance(files, dict) or not all(isinstance(v, str) for v in files.values()):
            raise AgentError('CasesInvalid', '%s：files 要是 {相對路徑: 內容字串}' % where)
        for rel in files:
            parts = Path(rel).parts
            if not rel or os.path.isabs(rel) or '..' in parts:
                raise AgentError('CasesInvalid', '%s：files 的路徑要是工作根目錄底下的相對路徑：%r' % (where, rel))
        name = c.get('name') if isinstance(c.get('name'), str) and c.get('name') else 'case%d' % i
        out.append({'tool': c['tool'], 'name': name, 'stdin': json.dumps(c['args'], ensure_ascii=False),
                    'expect': c['expect'], 'contains': c.get('contains'), 'files': files})
    return out


def _common_drift(folder):
    mine = folder / '_common.py'
    if mine.is_file() and mine.read_bytes() != BASE_COMMON.read_bytes():
        return '_common.py 跟 proto5/tools/base/_common.py 不一樣（要跟著 base 更新就複製一份過來）'
    return None


REQUIRE_JAIL_ENV = 'AOS_TOOLS_REQUIRE_JAIL'   # =1：tools test 關不了牢就拒跑，不退回主機直接跑


def test(spec, args=None, case_file=None, no_jail=False, as_json=False, tool=None):
    name, folder, tools_file = find_package(spec)
    tools = read_tools([str(tools_file)])                 # 格式照 agent §3.3 驗；壞了＝ToolInvalid
    names = [t['function']['name'] for t in tools]
    if tool is not None:
        if tool not in names:
            raise AgentError('NotFound', '%s 裡沒有工具 %s（有：%s）' % (folder, tool, '、'.join(names)))
        tools = [t for t in tools if t['function']['name'] == tool]
    if args is not None and len(tools) != 1:
        raise AgentError('Usage', '--args 只跑一支：%s 有 %d 支（%s），加 --tool NAME 挑一支'
                         % (name, len(tools), '、'.join(names)))
    cases = None
    if args is None:
        path = Path(os.path.abspath(case_file)) if case_file else folder / 'cases.json'
        if case_file or path.is_file():
            cases = [c for c in load_cases(path, names) if tool is None or c['tool'] == tool]
    if no_jail:
        jail, why = False, '給了 --no-jail'
    else:
        jail, why = jail_ready()
    if not jail and os.environ.get(REQUIRE_JAIL_ENV) == '1':   # toolsmith 設的：關不了牢就一支都不跑（astra 09-25）
        raise AgentError('NoJail', '要求一定關牢（%s=1），但關不了（%s）：一支都沒跑' % (REQUIRE_JAIL_ENV, why))
    note = None if jail else '沒關牢（%s）：工具直接在這台機器上跑，碰得到你碰得到的檔' % why
    if note:                                              # 跑任何程式之前就講（卡住或崩了也看得到）
        sys.stderr.write(note + '\n')
        sys.stderr.flush()
    with tempfile.TemporaryDirectory(prefix='aos-tools-test-', ignore_cleanup_errors=True) as tmp:
        home = Path(os.path.realpath(tmp))
        shutil.copytree(folder, home / 'tools' / name, symlinks=True,
                        ignore=shutil.ignore_patterns(name + '.json', '__pycache__', '*.pyc'))
        (home / 'workspace').mkdir()
        runner = Runner(home, jail)
        if args is not None:
            return _single(runner, tools[0], args, jail, note, as_json)
        return _suite(runner, name, folder, tools, cases, jail, note, as_json)


def _single(runner, tool, args, jail, note, as_json):
    res = runner.run(tool, args)
    if as_json:
        print(json.dumps({'_type': 'aos_agent_tools_run', '_version': 1, 'tool': tool['function']['name'],
                          'jail': jail, 'jail_note': note, 'exit_code': res.code, 'ms': res.ms,
                          'timed_out': res.timed_out, 'error': res.spawn_error or res.stuck,
                          'dropped': res.dropped, 'stdout': res.out, 'stderr': res.err}, ensure_ascii=False))
    else:
        sys.stdout.write(res.out)
        sys.stdout.flush()
        sys.stderr.write(res.err)
        extra = ''.join(x for x in ('，逾時被砍' if res.timed_out else '',
                                    '，前面丟了 %d 位元組輸出' % res.dropped if res.dropped else '',
                                    '；' + res.stuck if res.stuck else ''))
        sys.stderr.write('（%s：%s，%d 毫秒%s）\n' % (tool['function']['name'],
                                                   '退出碼 %s' % res.code if res.spawn_error is None else res.spawn_error,
                                                   res.ms, extra))
    return 0 if res.code == 0 and not res.timed_out else 1


def _suite(runner, name, folder, tools, cases, jail, note, as_json):
    warnings, rows, sizes = [], [], []
    drift = _common_drift(folder)
    if drift:
        warnings.append(drift)
    for t in tools:
        n = _tokens(t)
        sizes.append({'name': t['function']['name'], 'tokens': n, 'over': n > TOKEN_LIMIT})
    if not as_json:                                       # 表頭先印（跑任何工具之前），每條跑完就印
        print('包 %s（%s）：%d 支工具；%s' % (name, folder, len(tools),
                                         '關在牢裡跑（aos-jail，拋棄式 workspace 掛成 /work/ws，net off）' if jail
                                         else '在拋棄式的假 agent 家裡跑（沒關牢）'))
        for size in sizes:
            print('描述  %s  約 %d token%s' % (size['name'], size['tokens'],
                                           '（超過 %d，資源軸扣分：描述再短一點）' % TOKEN_LIMIT if size['over'] else ''))
        for w in warnings:
            print('警告：' + w)
        sys.stdout.flush()

    def add(row):
        rows.append(row)
        if not as_json:
            print('%s  %s  %s  (%d ms)' % ('PASS' if row['pass'] else 'FAIL', row['tool'], row['case'], row['ms']))
            if not row['pass']:
                print('      期待 %s；得到 %s' % (row['expect'], row['got']))
            sys.stdout.flush()

    def record(tool_name, case, res, expect, contains=None):
        ok, want = judge(res, expect, contains)
        add({'tool': tool_name, 'case': case, 'pass': ok, 'ms': res.ms, 'expect': want,
             'got': got(res), 'exit_code': res.code})

    if (folder / 'wrap.json').is_file():                  # wrap-py 產的：先試 import 一次原檔副本
        probe = {'type': 'function', 'function': {'name': name},
                 '_meta': {'argv': ['tools/%s/run' % name, '--check-import']}}
        record(name, 'import', runner.run(probe, ''), 'ok')
    runnable = []
    for t in tools:
        tname = t['function']['name']
        problem = runner.program(t)
        add({'tool': tname, 'case': 'program', 'pass': problem is None, 'ms': 0,
             'expect': '程式在、有執行位', 'got': problem or '', 'exit_code': None})
        if problem is None:
            runnable.append(t)
    for t in runnable:
        for case, stdin, expect in auto_cases(t):
            record(t['function']['name'], case, runner.run(t, stdin), expect)
    by_name = {t['function']['name']: t for t in runnable}
    for c in cases or []:
        if c['tool'] not in by_name:
            continue
        try:
            for rel, content in c['files'].items():
                runner.write_file(rel, content)
        except OSError as e:
            add({'tool': c['tool'], 'case': c['name'], 'pass': False, 'ms': 0,
                 'expect': '先把 files 寫進 workspace',
                 'got': '寫不進去（路徑經過符號連結、硬連結，或不是資料夾）：%s' % (e.strerror or e),
                 'exit_code': None})
            continue
        record(c['tool'], c['name'], runner.run(by_name[c['tool']], c['stdin']), c['expect'], c['contains'])
    failed = sum(1 for r in rows if not r['pass'])
    if as_json:
        print(json.dumps({'_type': 'aos_agent_tools_test', '_version': 1, 'package': name, 'dir': str(folder),
                          'jail': jail, 'jail_note': note, 'warnings': warnings, 'tools': sizes,
                          'cases': rows, 'total': len(rows), 'failed': failed}, ensure_ascii=False))
        return 1 if failed else 0
    print('%d 條，%d 條沒過' % (len(rows), failed))
    return 1 if failed else 0
