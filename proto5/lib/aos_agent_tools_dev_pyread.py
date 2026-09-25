"""`tools wrap-py` 的讀：用 ast 靜態讀 Python 檔（不 import、不執行），型別註解→型別記號／JSON Schema、docstring 參數說明、拒收表。"""
import ast
import inspect
import json
import re

from aos_agent_home import AgentError


TOOL_NAME = re.compile(r'[A-Za-z0-9_]{1,64}\Z')        # 模型端（OpenAI 相容）的工具名限制，函式名要過這條


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
