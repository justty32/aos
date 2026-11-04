"""`tools wrap-cli` 機械版之一：CMD 是有 argparse 的 .py → 用 ast 靜態讀 add_argument（不 import、不執行）→ 參數表。"""
import ast
import re

from aos_agent_home import AgentError

from aos_agent_tools_wrapcli_const import FLAG, PARAM_NAME, SKIP_FLAGS


# ------------------------------------------------------------------ 機械版：argparse ----

def _is_call(node, name):
    """node 是 argparse.NAME(...) 或 NAME(...)。"""
    if not isinstance(node, ast.Call):
        return False
    f = node.func
    return (isinstance(f, ast.Name) and f.id == name) or (isinstance(f, ast.Attribute) and f.attr == name
                                                          and isinstance(f.value, ast.Name))


def uses_argparse(source):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    return any(_is_call(n, 'ArgumentParser') for n in ast.walk(tree))


def _dest(flags):
    longs = [f for f in flags if f.startswith('--')]
    return (longs[0] if longs else flags[0]).lstrip('-').replace('-', '_')


def _safe_name(raw):
    name = re.sub(r'[^A-Za-z0-9_]', '_', raw).strip('_') or 'arg'
    return name if PARAM_NAME.match(name) else 'arg_' + name[:59]


def _lit(node):
    try:
        return True, ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, RecursionError):
        return False, None


class _Receivers:
    """每個變數是什麼：parser、群組（同一個 parser）、互斥群組、subparsers、子命令的 parser。"""

    def __init__(self, tree):
        self.kind = {}                                   # 變數名 → ('parser'|'group'|'mutex'|'subs'|'sub', 附註)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                self.kind[node.targets[0].id] = self.of(node.value)

    def of(self, expr):
        if _is_call(expr, 'ArgumentParser'):
            return ('parser', None)
        if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute):
            base = self.resolve(expr.func.value)
            method = expr.func.attr
            if base is None:
                return None
            if method == 'add_argument_group' and base[0] in ('parser', 'group', 'mutex'):
                return ('group', base[1])
            if method == 'add_mutually_exclusive_group' and base[0] in ('parser', 'group'):
                return ('mutex', expr.lineno)
            if method == 'add_subparsers' and base[0] == 'parser':
                return ('subs', None)
            if method == 'add_parser' and base[0] == 'subs':
                ok, name = _lit(expr.args[0]) if expr.args else (False, None)
                return ('sub', name if ok else '?')
        return None

    def resolve(self, expr):
        if isinstance(expr, ast.Name):
            return self.kind.get(expr.id)
        return self.of(expr)


def read_argparse(source, filename):
    """有 argparse 的 .py → {'description', 'params', 'rows', 'unparsed', 'notes'}；不 import、不執行。
    rows：[狀態 'ok'|'reject'|'skip', 名字或旗標, 原因, 行]。"""
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as e:
        raise AgentError('SyntaxError', '%s 第 %s 行語法錯：%s' % (filename, e.lineno, e.msg))
    parsers = [n for n in ast.walk(tree) if _is_call(n, 'ArgumentParser')]
    rec = _Receivers(tree)
    rows, params, notes = [], [], []
    description = None
    whole = None
    if len(parsers) > 1:
        whole = '檔裡有 %d 個 ArgumentParser（第 %s 行），分不出哪個是主的' % (
            len(parsers), '、'.join(str(n.lineno) for n in sorted(parsers, key=lambda n: n.lineno)))
    elif parsers:
        for kw in parsers[0].keywords:
            ok, value = _lit(kw.value)
            if kw.arg == 'description' and ok and isinstance(value, str):
                description = value
            if kw.arg == 'prefix_chars' and (not ok or value != '-'):
                whole = 'prefix_chars 不是 "-"（只認 - 開頭的旗標）'
            if kw.arg == 'parents':
                rows.append(['reject', 'parents=…', '從別的 parser 繼承的參數讀不到', parsers[0].lineno])
    calls = sorted((n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr in ('add_argument', 'add_subparsers')), key=lambda n: (n.lineno, n.col_offset))
    for call in calls:
        line = call.lineno
        if call.func.attr == 'add_subparsers':
            rows.append(['reject', 'subparsers', '子命令（subparsers）不支援；子命令的參數一律拒收', line])
            continue
        label = ast.unparse(call.args[0]) if call.args else '?'
        if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
            label = call.args[0].value
        owner = rec.resolve(call.func.value)
        if whole:
            rows.append(['reject', label, whole, line])
            continue
        if owner is None:
            rows.append(['reject', label, '看不出是哪個 parser 的（%s 不是直接指派的 parser／群組變數）'
                         % ast.unparse(call.func.value), line])
            continue
        if owner[0] == 'sub':
            rows.append(['reject', label, '屬於子命令 %s（subparsers 不支援）' % owner[1], line])
            continue
        param, why, skip = _add_argument(call, owner)
        if skip:
            rows.append(['skip', label, skip, line])
        elif why:
            rows.append(['reject', label, why, line])
        else:
            param['line'] = line
            rows.append(['ok', param['name'], '；'.join(param.pop('_notes', [])), line])
            params.append(param)
    return {'description': description, 'params': params, 'rows': rows, 'unparsed': [], 'notes': notes}


ACTIONS = {'store', 'store_true', 'store_false', 'store_const', 'count', 'append', 'help', 'version'}
TYPE_NAMES = {'int': 'integer', 'float': 'number', 'str': 'string'}
KEYWORDS = {'action', 'nargs', 'type', 'choices', 'required', 'default', 'help', 'dest', 'metavar', 'const'}


def _add_argument(call, owner):
    """一個 add_argument(...) → (參數 dict, 拒收原因, 跳過原因)。影響 argv 的欄（旗標、action、type、nargs、choices、
    required、dest）一定要字面值；help、default、metavar 不是字面值就丟掉那欄、記一句。"""
    notes = []
    if any(isinstance(a, ast.Starred) for a in call.args) or any(kw.arg is None for kw in call.keywords):
        return None, '參數用 * 或 ** 展開（不是字面值）', None
    names = []
    for a in call.args:
        ok, v = _lit(a)
        if not ok or not isinstance(v, str):
            return None, '旗標／名字 %s 不是字串字面值' % ast.unparse(a), None
        names.append(v)
    if not names:
        return None, 'add_argument 沒給名字', None
    kw = {}
    for k in call.keywords:
        if k.arg not in KEYWORDS:
            notes.append('%s= 不管' % k.arg)
            continue
        if k.arg == 'type':
            kw['type'] = k.value
            continue
        if k.arg == 'action' and isinstance(k.value, ast.Attribute):
            return None, 'action=%s 不支援' % ast.unparse(k.value), None
        if k.arg == 'help' and isinstance(k.value, ast.Attribute) and k.value.attr == 'SUPPRESS':
            return None, None, '隱藏的參數（help=SUPPRESS）'
        if k.arg == 'choices' and _is_range(k.value):
            kw['choices'] = _is_range(k.value)
            continue
        ok, v = _lit(k.value)
        if not ok:
            if k.arg in ('help', 'default', 'metavar'):
                notes.append('%s 不是字面值，丟掉' % k.arg)
                continue
            return None, '%s=%s 不是字面值' % (k.arg, ast.unparse(k.value)), None
        kw[k.arg] = v
    action = kw.get('action', 'store')
    if action not in ACTIONS:
        return None, 'action=%r 不支援（只收 %s）' % (action, '、'.join(sorted(ACTIONS - {'help', 'version'}))), None
    if action in ('help', 'version'):
        return None, None, 'help／version 不收'
    positional = not names[0].startswith('-')
    if positional and len(names) > 1:
        return None, '位置參數只能有一個名字', None
    if not positional and not all(FLAG.match(n) for n in names):
        return None, '旗標 %s 讀不懂（只認 - 開頭的旗標）' % '、'.join(names), None
    if not positional and any(n in SKIP_FLAGS or n == '-h' for n in names):
        return None, None, 'help／version 不收'
    kind_type = 'string'
    if 'type' in kw:
        t = kw['type']
        tname = t.id if isinstance(t, ast.Name) else None
        if tname == 'bool':
            return None, 'type=bool 是陷阱（任何非空字串都是 True），請改用 store_true', None
        if tname not in TYPE_NAMES:
            return None, 'type=%s 不支援（只收 int、float、str）' % ast.unparse(t), None
        kind_type = TYPE_NAMES[tname]
    nargs = kw.get('nargs')
    if nargs is not None and nargs not in ('?', '*', '+') and not (isinstance(nargs, int) and not isinstance(nargs, bool)
                                                                    and nargs >= 1):
        return None, 'nargs=%r 不支援（只收 ?、*、+、正整數）' % (nargs,), None
    param = {'flags': [] if positional else names, 'type': kind_type, 'array': False, 'required': False,
             'help': (kw.get('help') or '') if isinstance(kw.get('help'), str) else ''}
    if action in ('store_true', 'store_false', 'store_const'):
        param.update(kind='flag', type='boolean')
    elif action == 'count':
        param.update(kind='count', type='integer')
    else:
        param['kind'] = 'positional' if positional else 'option'
        many = nargs in ('*', '+') or (isinstance(nargs, int) and nargs > 1)
        if action == 'append':
            if positional:
                return None, '位置參數不能 action=append', None
            if nargs is not None:
                return None, 'action=append 搭配 nargs 不支援（每次要一組值，argv 表示不了）', None
            param.update(array=True, multi='repeat')
        elif many:
            param.update(array=True, nargs=nargs)
            if not positional:
                param['multi'] = 'once'
        if positional:
            param['required'] = nargs not in ('?', '*')
        if 'choices' in kw:
            choices = kw['choices']
            if not isinstance(choices, (list, tuple)) or not choices or not all(
                    isinstance(c, (str, int, float)) and not isinstance(c, bool) for c in choices):
                return None, 'choices 要是字串或數字的字面清單', None
            param['choices'] = list(choices)
    if kw.get('required') is True and not positional:
        param['required'] = True
    if action == 'store_false' or 'dest' not in kw:
        name = names[0] if positional else _dest(names)     # store_false 用旗標取名（--no-header → no_header）
    else:
        name = kw['dest']
    if not isinstance(name, str) or not PARAM_NAME.match(name):
        return None, '參數名 %r 不合法（英數底線、不以數字開頭、≤ 64 字）' % (name,), None
    param['name'] = name
    if owner[0] == 'mutex':
        notes.append('互斥群組（第 %d 行）：同時給由指令自己報錯' % owner[1])
    if 'default' in kw and isinstance(kw['default'], (str, int, float, bool)) and action not in ('store_true',
                                                                                                  'store_false', 'count'):
        param['default'] = kw['default']
    param['_notes'] = notes
    return param, None, None


def _is_range(node):
    """choices=range(a, b) 且都是整數常值、≤ 100 個 → 清單；否則 None。"""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'range' \
            and 1 <= len(node.args) <= 2 and not node.keywords:
        vals = [_lit(a) for a in node.args]
        if all(ok and isinstance(v, int) and not isinstance(v, bool) for ok, v in vals):
            r = range(*[v for _, v in vals])
            if 0 < len(r) <= 100:
                return list(r)
    return None


def argparse_segment(source):
    """給模型看的「argparse 那段」：第一個 ArgumentParser 到最後一個 add_argument 那幾行。"""
    tree = ast.parse(source)
    nodes = [n for n in ast.walk(tree) if _is_call(n, 'ArgumentParser') or (
        isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr.startswith('add_'))]
    lines = source.splitlines()
    if not nodes:
        return source
    start = min(n.lineno for n in nodes)
    end = max(n.end_lineno for n in nodes)
    return '\n'.join(lines[start - 1:end]) + '\n'
