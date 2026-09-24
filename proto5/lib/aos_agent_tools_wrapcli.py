"""aos-agent tools wrap-cli（spec/aos-agent/tools-llm.md，第三波 W3-2）：把一支命令列指令包成一支工具。

參數表（spec）怎麼來，三選一：
- 機械版（預設）：CMD 是有 argparse 的 .py → 用 ast 靜態讀 add_argument（不 import、不執行）；
  其他 → 拿 help 文字（--help-file，或跑 `CMD --help`），用規則解 usage 行與選項行。解不出來的列出來，不猜。
- --describe-with-llm：help 文字（或 argparse 那段原始碼）送模型一次，回固定格式的參數表；機械檢查兜底
  （旗標要在原文逐字出現、型別只准那幾種、名字合法），不過的那格丟掉。**不產包**，只寫提案檔等人看。
- --spec FILE：照人看過（可能改過）的參數表產包，不叫模型；help 文字的 sha256 對不上＝拒（help 變了）。
產包重用 tools_dev 的 publish／package_files（暫存資料夾＋rename、--force、BadName）。
產的 run：stdin 的 arguments → argv（不經 shell）→ 跑指令、回 stdout；退出碼非 0＝CommandFailed。
"""
import ast
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile

from aos_agent_home import AgentError
from aos_agent_tools import NAME
import aos_agent_tools_dev as dev

KINDS = ('flag', 'count', 'option', 'positional')
TYPES = ('string', 'integer', 'number', 'boolean')
PARAM_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]{0,63}\Z')
FLAG = re.compile(r'-{1,2}[A-Za-z0-9][A-Za-z0-9_.-]*\Z')
SKIP_FLAGS = ('--help', '--version', '-help', '-version', '-?')
INT_META = {'n', 'num', 'number', 'int', 'integer', 'count'}
FLOAT_META = {'float'}
HELP_TIMEOUT = 10               # 跑 CMD --help 最多等幾秒
HELP_CAP = 256 * 1024           # help 文字最多收多少位元組
LLM_CAP = 12000                 # 送模型的 help 文字最多幾個字
HELP_MAX = 200                  # 參數說明、工具描述最多幾個字
RUN_TIMEOUT = 50                # 產的 run 跑指令的逾時（秒），比 aos-agent 預設的 _timeout_ms 60 秒短
MAX_TIMEOUT = 600               # 參數表 timeout 的上限（秒）
MAX_NARGS = 100
CONTROL = dev.CONTROL           # 控制字元（ESC、NUL…）：描述與說明裡一律不收（審查 S1）
FIXED = ('run', 'wrapcli.json', '_common.py', 'config.json', 'README.md')
SPEC_TYPE = 'aos_wrap_cli'


def _sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _now():
    return datetime.datetime.now().astimezone().isoformat(timespec='seconds')


# ------------------------------------------------------------------ 指令與 help 文字 ----

ESC = re.compile(r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-9;?]*[ -/]*[@-~]|.\x08')


def clean_help(text):
    """去掉終端機控制碼（GNU coreutils 會印超連結與粗體）、backspace 疊字、tab 換空白、行尾空白。"""
    text = ESC.sub('', text.replace('\r\n', '\n'))
    return '\n'.join(line.expandtabs(8).rstrip() for line in text.split('\n')).strip('\n') + '\n'


def resolve_cmd(cmd):
    """CMD → {'kind': 'file', 'path', 'py', 'data'}（檔，產包時存副本）或 {'kind': 'path', 'name'}（PATH 上的指令）。"""
    if '/' in cmd or (cmd.endswith('.py') and os.path.exists(cmd)):
        path = Path(os.path.abspath(os.path.expanduser(cmd)))
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            raise AgentError('NotFound', '找不到 %s' % path)
        except IsADirectoryError:
            raise AgentError('NotFound', '%s 是資料夾，不是指令' % path)
        except OSError as e:
            raise AgentError('ReadFailed', '讀不到 %s：%s' % (path, e.strerror or e))
        return {'kind': 'file', 'path': path, 'py': path.suffix == '.py', 'data': data}
    if shutil.which(cmd) is None:
        raise AgentError('NotFound', '找不到指令 %s（PATH 上沒有；檔案請寫路徑，例如 ./%s）' % (cmd, cmd))
    return {'kind': 'path', 'name': cmd}


def read_help_file(path):
    p = Path(os.path.abspath(os.path.expanduser(path)))
    try:
        data = p.read_bytes()[:HELP_CAP]
    except FileNotFoundError:
        raise AgentError('NotFound', '找不到 --help-file %s' % p)
    except OSError as e:
        raise AgentError('ReadFailed', '讀不到 --help-file %s：%s' % (p, e.strerror or e))
    return clean_help(data.decode('utf-8', 'replace')), str(p)


def run_help(info):
    """跑 `CMD --help`（這一步真的會執行 CMD）：不經 shell、stdin 關、最小環境（PATH、LANG／LC_ALL=C、HOME＝拋棄式資料夾，
    不繼承金鑰）、cwd＝那個拋棄式資料夾。輸出邊讀邊丟（各只留 HELP_CAP），10 秒到了砍整個群組；主行程結束後
    管子被另開 session 的子孫握著也最多再收 2 秒（tools_dev.pump）。stdout 空就拿 stderr。"""
    if info['kind'] == 'file':
        argv = ['python3', str(info['path'])] if info['py'] else [str(info['path'])]
    else:
        argv = [info['name']]
    argv.append('--help')
    home = tempfile.mkdtemp(prefix='aos-wrapcli-help-')
    env = {'PATH': os.environ.get('PATH') or '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C', 'HOME': home}
    try:
        try:
            p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 env=env, cwd=home, start_new_session=True)
        except OSError as e:
            raise AgentError('HelpFailed', '跑不起來 %s：%s' % (' '.join(argv), e.strerror or e))
        code, out, err, timed_out, _, _ = dev.pump(p, b'', HELP_TIMEOUT, HELP_CAP)
    finally:
        shutil.rmtree(home, ignore_errors=True)
    if timed_out:
        raise AgentError('HelpFailed', '%s 跑了 %d 秒還沒結束，砍掉了；改用 --help-file' % (' '.join(argv), HELP_TIMEOUT))
    text = out if out.strip() else err
    if not text.strip():
        raise AgentError('HelpFailed', '%s 什麼都沒印（退出碼 %s）；改用 --help-file' % (' '.join(argv), code))
    return clean_help(text.decode('utf-8', 'replace'))


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


# ------------------------------------------------------------------ 機械版：help 文字 ----

USAGE = re.compile(r'\s*usage:\s*(.*)\Z', re.I)
PLACEHOLDER = {'option', 'options', 'opts', 'flags', 'flag', 'switches'}
ITEM = re.compile(r'-{1,2}[A-Za-z0-9][A-Za-z0-9_.-]*')
MENTION = re.compile(r'(?<![\w/.\-])(-{1,2}[A-Za-z][\w-]*)')
REPEAT = re.compile(r'\b(repeatable|can be repeated|may be repeated|multiple times|more than once)\b', re.I)
CAN_BE = re.compile(r'\b(?:can be|is one of|one of|must be one of)\s*:?\s*'
                    r'([\w.-]+(?:\s*,\s*(?:or\s+)?[\w.-]+)+)', re.I)


def _usage_tokens(s):
    """usage 字串 → 巢狀清單：('opt', [...]) 方括號、('group', [...]) 圓括號、('choice', [..])、('word', w)、
    ('ellipsis',)、('bar',)。"""
    pos = 0

    def seq(end):
        nonlocal pos
        items = []
        while pos < len(s):
            c = s[pos]
            if c.isspace():
                pos += 1
            elif c == end:
                pos += 1
                return items
            elif c in '])}':
                pos += 1
            elif c == '[':
                pos += 1
                items.append(('opt', seq(']')))
            elif c == '(':
                pos += 1
                items.append(('group', seq(')')))
            elif c in '{<':
                close = '}' if c == '{' else '>'
                j = s.find(close, pos)
                j = len(s) if j < 0 else j
                inner = s[pos + 1:j]
                pos = j + 1
                if c == '{':
                    items.append(('choice', [x.strip() for x in inner.split(',') if x.strip()]))
                else:
                    items.append(('word', inner.strip()))
            elif s.startswith('...', pos) or s.startswith('…', pos):
                pos += 3 if s.startswith('...', pos) else 1
                items.append(('ellipsis',))
            elif c == '|':
                pos += 1
                items.append(('bar',))
            else:
                m = re.match(r'[^\s\[\](){}<>|]+', s[pos:])
                w = m.group()
                pos += len(w)
                if w.endswith('...') and len(w) > 3:
                    items += [('word', w[:-3]), ('ellipsis',)]
                else:
                    items.append(('word', w))
        return items

    return seq(None)


def _usage_walk(items, optional, out):
    """把 usage 的 token 變成 out['pos']（位置參數）與 out['opts']（旗標 → 屬性）。"""
    i = 0
    while i < len(items):
        it = items[i]
        many = i + 1 < len(items) and items[i + 1][0] == 'ellipsis'
        kind = it[0]
        if kind == 'opt':
            inner = it[1]
            words = [x for x in inner if x[0] == 'word']
            if words and all(x[0] in ('word', 'ellipsis') for x in inner) and len(words) == 1 \
                    and words[0][1].lower() in PLACEHOLDER:
                pass                                       # [OPTION]... [options] 這種佔位
            elif inner and inner[0][0] == 'word' and inner[0][1].startswith('-') and len(inner[0][1]) > 1:
                _usage_opts(inner, True, out)
            elif len(inner) == 1 and many:
                _usage_walk(inner + [('ellipsis',)], True, out)
            else:
                _usage_walk(inner, True, out)
        elif kind == 'group':
            _usage_walk(it[1], optional, out)
        elif kind == 'choice':
            out['pos'].append({'raw': 'choice', 'choices': it[1], 'required': not optional, 'array': many})
        elif kind == 'word':
            w = it[1]
            if w.startswith('-') and len(w) > 1:
                arg = None
                nxt = items[i + 1] if i + 1 < len(items) else None
                if nxt and nxt[0] == 'word' and not nxt[1].startswith('-') and re.match(r'[A-Z][A-Z0-9_-]*\Z', nxt[1]):
                    arg = nxt[1]
                    i += 1
                _usage_flag(w, arg, not optional, many, out)
            elif w.lower() not in PLACEHOLDER:
                out['pos'].append({'raw': w, 'required': not optional, 'array': many})
        i += 1


def _usage_opts(inner, optional, out):
    """方括號裡以 - 開頭：[-abc] 一串開關、[-f file]、[--foo=FOO]、[-a | -b]。"""
    if len(inner) == 1 and re.match(r'-[A-Za-z0-9]{2,}\Z', inner[0][1]):
        for ch in inner[0][1][1:]:
            _usage_flag('-' + ch, None, False, False, out)
        return
    parts, cur = [], []
    for x in inner:
        if x[0] == 'bar':
            parts.append(cur)
            cur = []
        else:
            cur.append(x)
    parts.append(cur)
    for part in parts:
        if not part or part[0][0] != 'word' or not part[0][1].startswith('-'):
            continue
        many = any(x[0] == 'ellipsis' for x in part)
        args = [x[1] for x in part[1:] if x[0] == 'word']
        choice = [x[1] for x in part[1:] if x[0] == 'choice']
        _usage_flag(part[0][1], args[0] if args else ('{%s}' % ','.join(choice[0]) if choice else None),
                    False, many, out)


def _usage_flag(word, arg, required, many, out):
    if '=' in word:
        word, arg = word.split('=', 1)
    if not FLAG.match(word):
        return
    out['opts'].setdefault(word, {'arg': arg, 'required': required, 'array': many, 'line': out['line']})


def _parse_usage(lines):
    """找 usage 區塊：回 (第一種用法的 token 解讀, 用到的行號集合, 附註)。"""
    for idx, line in enumerate(lines):
        m = USAGE.match(line)
        if not m:
            continue
        used = {idx}
        first = m.group(1).strip()
        body_lines = []
        j = idx + 1
        if not first:                                     # Usage: 單獨一行，下一行才是用法
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and lines[j].startswith(' '):
                first = lines[j].strip()
                used.add(j)
                j += 1
        prog = first.split()[0] if first else ''
        notes = []
        while j < len(lines) and lines[j].strip() and lines[j].startswith(' '):
            s = lines[j].strip()
            if s.lower().startswith('or:') or (prog and s.split()[0] == prog):
                notes.append((j + 1, '另一種用法，只照第一種解'))
            elif not ITEM.match(s) or s.startswith(('[', '<', '{')):
                body_lines.append(s)
            else:
                break
            used.add(j)
            j += 1
        text = ' '.join([first] + body_lines)
        out = {'pos': [], 'opts': {}, 'line': idx + 1}
        _usage_walk(_usage_tokens(text)[1:], False, out)   # 第一個 token 是程式名
        return out, used, notes
    return {'pos': [], 'opts': {}, 'line': None}, set(), []


def _option_line(text):
    """'-x, --long=ARG  說明' → (items [(旗標, 參數名, 寫法)], 說明或 None, 問題或 None)；不是選項行回 None。"""
    pos, items = 0, []
    while True:
        m = ITEM.match(text, pos)
        if not m:
            break
        flag, pos, arg, style = m.group(), m.end(), None, None
        rest = text[pos:]
        if rest.startswith('[='):
            j = rest.find(']')
            if j > 2:
                arg, style, pos = rest[2:j], '=', pos + j + 1
        elif rest.startswith('='):
            m2 = re.match(r'=([^\s,:]+)', rest)
            if m2:
                arg, style, pos = m2.group(1), '=', pos + m2.end()
        else:
            m2 = (re.match(r' (<[^>]+>|\{[^}]+\}|[A-Z][A-Z0-9_-]*)(?=\s|$|,|:)', rest)
                  or re.match(r' ([^\s,:\-][^\s,:]*)(?=\s{2,}|$|,|:)', rest))
            if m2:
                arg, style, pos = m2.group(1), ' ', pos + m2.end()
        items.append((flag, arg, style))
        sep = re.match(r'\s*[,|/]\s*(?=-)', text[pos:])
        if not sep:
            break
        pos += sep.end()
    if not items:
        return None
    rest = text[pos:]
    if not rest.strip():
        return items, None, None
    if rest.startswith(':'):
        return items, rest[1:].strip(), None
    if re.match(r'\s{2,}', rest):
        return items, rest.strip(), None
    return items, None, '旗標後面只隔一格就接字，分不出是參數名還是說明'


def _meta_type(arg):
    """參數名 → (型別, choices)。{a,b}、a|b＝choices；N、NUM、<n>…＝integer；FLOAT＝number；其他 string。"""
    if arg is None:
        return 'boolean', None
    a = arg.strip('<>')
    if a.startswith('{') and a.endswith('}'):
        return 'string', [x.strip() for x in a[1:-1].split(',') if x.strip()]
    if '|' in a and all(re.match(r'[a-z0-9][\w.-]*\Z', x) for x in a.split('|')):
        return 'string', a.split('|')
    if a.lower() in INT_META:
        return 'integer', None
    if a.lower() in FLOAT_META:
        return 'number', None
    return 'string', None


def parse_help(text):
    """help 文字 → {'description', 'params', 'rows', 'unparsed': [(行, 原文, 為什麼)], 'notes'}。規則見 tools-llm.md。"""
    lines = text.split('\n')
    usage, used, notes = _parse_usage(lines)
    opt_lines = []                                        # (行號, items, 說明, 縮排)
    unparsed, section, cont_indent, current = [], None, None, None
    prose = []
    for idx, line in enumerate(lines):
        if idx in used:
            current = None
            continue
        if not line.strip():
            current = None
            continue
        indent = len(line) - len(line.lstrip())
        s = line.strip()
        if current is not None and cont_indent is None and indent > current[3] and not (
                ITEM.match(s) and _option_line(s)):
            cont_indent = indent                          # 說明寫在下一行：第一行續行定下續行的縮排
        if current is not None and cont_indent is not None and indent >= cont_indent:
            if current[2] is None:
                current[2] = s
            else:
                current[2] += ' ' + s
            continue
        got = _option_line(s) if ITEM.match(s) else None
        if got:
            items, desc, problem = got
            if problem:
                unparsed.append((idx + 1, s, problem))
                current = None
                continue
            current = [idx + 1, items, desc, indent]
            opt_lines.append(current)
            cont_indent = (indent + len(s) - len(desc)) if desc else None
            continue
        current = None
        if indent == 0 and s.endswith(':'):
            section = s
            continue
        if section and indent > 0 and re.search(r'option|flag|argument', section, re.I) \
                and 'positional' not in section.lower():
            unparsed.append((idx + 1, s, '在「%s」段裡，但不是選項行' % section))
            continue
        if section and 'positional' in section.lower() and indent > 0:
            m = re.match(r'(\S+)\s{2,}(.*)', s)
            if m:
                prose.append((idx + 1, s, ('positional', m.group(1), m.group(2))))
                continue
        prose.append((idx + 1, s, None))
    # 同一個旗標有沒有「光溜溜」的寫法：有的話 --check=quiet 這種是固定值別名，不是參數
    bare, values = set(), {}
    for _, items, _, _ in opt_lines:
        for flag, arg, style in items:
            if arg is None:
                bare.add(flag)
            elif style == '=':
                values.setdefault(flag, set()).add(arg)
    params, rows, seen_flags, seen_names = [], [], {}, set()
    for line_no, items, desc, _ in opt_lines:
        flags, arg, joiner, literal = [], None, ' ', []
        for flag, a, style in items:
            if a is not None and style == '=' and re.match(r'[a-z][\w-]*\Z', a) and (
                    flag in bare or len(values.get(flag, ())) > 1):
                literal.append('%s=%s' % (flag, a))
                continue
            if flag not in flags:
                flags.append(flag)
            if a is not None and arg is None:
                arg = a
            if style == '=':
                joiner = '='
        label = ', '.join(f for f, _, _ in items)
        if any(f in SKIP_FLAGS for f in flags) or (flags in (['-h'], ['-?']) and 'help' in (desc or '').lower()):
            rows.append(['skip', label, 'help／version 不收', line_no])
            continue
        dup = [f for f in flags if f in seen_flags]
        if dup:
            rows.append(['reject', label, '旗標 %s 在第 %d 行已經有了' % ('、'.join(dup), seen_flags[dup[0]]), line_no])
            continue
        t, choices = _meta_type(arg)
        desc = desc or ''
        if arg is not None and not choices:
            m = CAN_BE.search(desc)
            if m:
                choices = [x.strip() for x in re.split(r'\s*,\s*(?:or\s+)?', m.group(1)) if x.strip()]
        p = {'name': _safe_name(_dest(flags)), 'flags': flags, 'kind': 'flag' if arg is None else 'option',
             'type': t, 'array': False, 'required': False, 'help': desc, 'line': line_no}
        if arg is None:
            shorts = [f for f in flags if re.match(r'-[A-Za-z]\Z', f)]
            if any(re.search(r'(?<![\w-])-%s{2,}(?![\w-])' % re.escape(f[1]), desc) for f in shorts):
                p.update(kind='count', type='integer')    # 說明裡寫了 -vv：可重複的開關
        else:
            if choices:
                p['choices'] = choices
            if any(f.startswith('--') for f in flags):
                p['joiner'] = joiner
            if REPEAT.search(desc):
                p.update(array=True, multi='repeat')
        note = '；'.join(['固定值寫法 %s 不當參數' % '、'.join(literal)] if literal else [])
        params.append(p)
        rows.append(['ok', p['name'], note, line_no])
        for f in flags:
            seen_flags[f] = line_no
    # usage 裡的旗標：補必填、補選項段沒寫的
    for flag, u in usage['opts'].items():
        if flag in SKIP_FLAGS or flag == '-h':
            continue
        owner = next((p for p in params if flag in p['flags']), None)
        if owner:
            if u['required']:
                owner['required'] = True
            continue
        t, choices = _meta_type(u['arg'])
        p = {'name': _safe_name(_dest([flag])), 'flags': [flag], 'kind': 'flag' if u['arg'] is None else 'option',
             'type': t, 'array': u['array'] and u['arg'] is not None, 'required': u['required'], 'help': '',
             'line': u['line']}
        if choices:
            p['choices'] = choices
        params.append(p)
        rows.append(['ok', p['name'], '只在 usage 行出現', u['line']])
        seen_flags[flag] = u['line']
    # 位置參數
    pos_help = {x[2][1].strip('<>'): x[2][2] for x in prose if x[2]}
    positionals = []
    for u in usage['pos']:
        raw = u['raw'].strip('<>')
        p = {'name': _safe_name(raw.lower()), 'flags': [], 'kind': 'positional', 'type': 'string',
             'array': u['array'], 'required': u['required'], 'help': pos_help.get(raw, ''), 'line': usage['line']}
        if u.get('choices'):
            p['choices'] = u['choices']
            p['help'] = pos_help.get('{%s}' % ','.join(u['choices']), '')
        positionals.append(p)
        rows.append(['ok', p['name'], '位置參數（usage 行）', usage['line']])
    # 名字撞：選項之間撞＝後面的拒收；位置參數撞到選項＝加 _arg
    final = []
    for p in params:
        if p['name'] in seen_names:
            _reject_row(rows, p, '名字 %s 跟前面的撞了' % p['name'])
            continue
        seen_names.add(p['name'])
        final.append(p)
    for p in positionals:
        while p['name'] in seen_names:
            p['name'] += '_arg'
        seen_names.add(p['name'])
    known = {f for p in final for f in p['flags']}
    for line_no, s, extra in prose:
        if extra:
            continue
        unknown = []
        for f in MENTION.findall(s):
            if f in known or f in SKIP_FLAGS or f in unknown:
                continue
            if re.match(r'-([A-Za-z])\1+\Z', f) and '-' + f[1] in known:
                continue
            unknown.append(f)
        if unknown:
            unparsed.append((line_no, s, '提到 %s，但沒有它的選項行' % '、'.join(unknown)))
    return {'description': _describe(lines, used), 'params': positionals + final, 'rows': rows,
            'unparsed': unparsed, 'notes': notes}


def _reject_row(rows, p, why):
    for r in rows:
        if r[0] == 'ok' and r[1] == p['name'] and r[3] == p['line']:
            r[0], r[2] = 'reject', why
            return


def _describe(lines, used):
    """一句話描述：第一行不是 usage 也不是選項＝「名字 - 描述」；不然 usage 後第一段文字的第一句。"""
    nonblank = [(i, s.strip()) for i, s in enumerate(lines) if s.strip()]
    if not nonblank:
        return None
    i0, first = nonblank[0]
    if i0 not in used and not ITEM.match(first):
        m = re.match(r'\S+(?:\s+v?[\d.]+)?\s+-{1,2}\s+(.*)', first)
        return (m.group(1) if m else first)[:HELP_MAX]
    after = [(i, s) for i, s in nonblank if i not in used and i > max(used, default=-1)]
    for i, s in after:
        if not ITEM.match(s) and not s.endswith(':') and not lines[i].startswith(' '):
            para = [s]
            for j in range(i + 1, len(lines)):
                if not lines[j].strip() or lines[j].startswith(' '):
                    break
                para.append(lines[j].strip())
            text = ' '.join(para)
            m = re.match(r'(.+?[.!?])(\s|$)', text)
            return (m.group(1) if m else text)[:HELP_MAX]
    return None


# ------------------------------------------------------------------ 參數表的機械檢查（模型回的、人改過的都走這條） ----

def _in_text(flag, evidence):
    return re.search(r'(?<![\w-])%s(?![\w-])' % re.escape(flag), evidence) is not None


def _line_of(flag, evidence):
    for i, line in enumerate(evidence.split('\n')):
        if _in_text(flag, line):
            return i + 1
    return None


def _joiner(flag, evidence):
    return '=' if re.search(r'(?<![\w-])%s\[?=' % re.escape(flag), evidence) else ' '


def check_params(raw, evidence):
    """參數表逐格驗 → (收的 [參數], 丟掉的 [(標籤, 原因)])。旗標要在原文逐字出現、型別只准那幾種、名字合法。"""
    if not isinstance(raw, list):
        return [], [('params', 'params 要是陣列')]
    ok, dropped, names, flags_seen = [], [], set(), set()
    variable = None                                       # 前面可變長度（選填或陣列）的位置參數
    for i, p in enumerate(raw):
        label = '第 %d 格' % (i + 1)
        if not isinstance(p, dict):
            dropped.append((label, '不是物件'))
            continue
        name = p.get('name')
        label = '%s（%s）' % (label, name) if isinstance(name, str) else label
        why = _check_one(p, evidence, names, flags_seen)
        is_var = p.get('kind') == 'positional' and (not p.get('required') or p.get('array'))
        if not why and is_var and variable:
            why = ('前面已有可變長度的位置參數 %s（選填或陣列），再一個就分不清值給誰（跳過前面的也會被配錯）'
                   % variable)
        if why:
            dropped.append((label, why))
            continue
        kind = p['kind']
        q = {'name': name, 'flags': list(p.get('flags') or []), 'kind': kind,
             'type': {'flag': 'boolean', 'count': 'integer'}.get(kind, p.get('type')),
             'array': bool(p.get('array')), 'required': bool(p.get('required')),
             'help': ' '.join(str(p.get('help') or '').split())[:HELP_MAX]}
        if p.get('choices'):
            q['choices'] = list(p['choices'])
        if kind == 'option':
            longs = [f for f in q['flags'] if f.startswith('--')]
            q['joiner'] = p.get('joiner') if p.get('joiner') in ('=', ' ') else (
                _joiner(longs[0], evidence) if longs else ' ')
        if q['array'] and kind == 'option':
            q['multi'] = p.get('multi') if p.get('multi') in ('repeat', 'once') else 'repeat'
        if 'default' in p and (p['default'] is None or isinstance(p['default'], (str, int, float, bool))):
            q['default'] = p['default']
        line = p.get('line') if isinstance(p.get('line'), int) and not isinstance(p.get('line'), bool) else None
        q['line'] = line if line is not None else (_line_of(q['flags'][0], evidence) if q['flags'] else None)
        if p.get('nargs') is not None:
            q['nargs'] = p['nargs']
        if is_var:
            variable = name
        names.add(name)
        flags_seen.update(q['flags'])
        ok.append(q)
    return ok, dropped


def _check_one(p, evidence, names, flags_seen):
    name, kind, flags = p.get('name'), p.get('kind'), p.get('flags', [])
    if not isinstance(name, str) or not PARAM_NAME.match(name):
        return '名字 %r 不合法（英數底線、不以數字開頭、≤ 64 字）' % (name,)
    if name in names:
        return '名字 %s 重複' % name
    if kind not in KINDS:
        return 'kind %r 不認得（只收 %s）' % (kind, '、'.join(KINDS))
    if flags is None:
        flags = []
    if not isinstance(flags, list) or not all(isinstance(f, str) for f in flags):
        return 'flags 要是字串陣列'
    if kind == 'positional' and flags:
        return '位置參數不能有旗標'
    if kind != 'positional' and not flags:
        return '%s 至少要一個旗標' % kind
    for f in flags:
        if not FLAG.match(f):
            return '旗標 %r 寫法不對（- 或 -- 開頭，不含 = 與空白）' % f
        if f in SKIP_FLAGS or (f == '-h' and 'help' in str(p.get('help') or '').lower()):
            return '%s 是 help／version，不收' % f
        if not _in_text(f, evidence):
            return '旗標 %s 在原文裡找不到' % f
        if f in flags_seen:
            return '旗標 %s 已經有別格用了' % f
    if len(set(flags)) != len(flags):
        return '旗標重複'
    t = p.get('type')
    if kind == 'flag' and t not in (None, 'boolean'):
        return 'flag 的型別只能是 boolean'
    if kind == 'count' and t not in (None, 'integer'):
        return 'count 的型別只能是 integer'
    if kind in ('option', 'positional') and t not in ('string', 'integer', 'number'):
        return '型別 %r 不收（option／positional 只收 string、integer、number；開關請用 kind flag）' % (t,)
    for key in ('array', 'required'):
        if key in p and not isinstance(p[key], bool) and p[key] is not None:
            return '%s 要是 true／false' % key
    if p.get('array') and kind in ('flag', 'count'):
        return '%s 不能是陣列' % kind
    choices = p.get('choices')
    if choices is not None and choices != []:
        want = {'string': str, 'integer': int, 'number': (int, float)}.get(t)
        if not isinstance(choices, list) or len(choices) > 100 or want is None or not all(
                isinstance(c, want) and not isinstance(c, bool) for c in choices):
            return 'choices 要是跟型別一致的清單（≤ 100 個）'
    if 'help' in p and p['help'] is not None and not isinstance(p['help'], str):
        return 'help 要是字串'
    if CONTROL.search(str(p.get('help') or '')) or any(isinstance(c, str) and CONTROL.search(c)
                                                       for c in (choices or [])):
        return 'help 或 choices 含控制字元（ESC、NUL…）'
    nargs = p.get('nargs')
    if nargs is not None:
        if nargs in ('+', '*') or (isinstance(nargs, int) and not isinstance(nargs, bool) and 1 <= nargs <= MAX_NARGS):
            if not p.get('array') or kind not in ('option', 'positional'):
                return 'nargs 只給陣列的 option／positional'
        else:
            return 'nargs 只收 +、*、1～%d' % MAX_NARGS
    return None


# ------------------------------------------------------------------ 模型版 ----

LLM_SYSTEM = ('You read the help text (or argparse source) of a command-line program and list its parameters as JSON. '
              'Reply with one JSON object only, no prose.')
LLM_FORMAT = '''Return {"description": "<one sentence: what the program does>", "params": [ ... ]}.
Each param is an object:
  "name": snake_case identifier (letters, digits, underscore),
  "flags": ["-x", "--long"] exactly as written in the text, without "=VALUE" (empty list for positional arguments),
  "kind": "flag" (on/off switch) | "count" (switch that can be repeated, like -vv) | "option" (takes a value) | "positional",
  "type": "boolean" for flag, "integer" for count, otherwise "string" | "integer" | "number",
  "array": true if it can take several values (repeatable option, or FILE...),
  "required": true or false,
  "choices": list of allowed values, or null,
  "help": short description.
List positional arguments in order. Skip -h/--help and --version.'''


def llm_prompt(cmd, mode, evidence):
    what = 'argparse source code' if mode == 'argparse' else 'help text'
    body = evidence if len(evidence) <= LLM_CAP else evidence[:LLM_CAP] + '\n[...truncated]\n'
    return '%s\n\nProgram: %s\nIts %s:\n<<<\n%s>>>' % (LLM_FORMAT, cmd, what, body)


def llm_table(cmd, mode, evidence, alias=None, ask=None):
    """問模型一次 → (描述, 收的參數, 丟掉的, ask 的回傳)。模型回的格式不對＝BadModelOutput。"""
    import aos_llm_ask
    ask = ask or aos_llm_ask.ask_json
    data, got = ask(LLM_SYSTEM, llm_prompt(cmd, mode, evidence), alias=alias)
    if isinstance(data, list):
        data = {'params': data}
    if not isinstance(data, dict) or 'params' not in data:
        raise AgentError('BadModelOutput', '模型回的 JSON 沒有 params 陣列')
    params, dropped = check_params(data['params'], evidence)
    desc = data.get('description')
    if isinstance(desc, str) and CONTROL.search(desc):
        dropped.append(('description', '含控制字元（ESC、NUL…），不收'))
        desc = None
    desc = ' '.join(desc.split())[:HELP_MAX] if isinstance(desc, str) and desc.strip() else None
    return desc, params, dropped, got


# ------------------------------------------------------------------ 產包 ----

WRAPCLI_RUN = r'''#!/usr/bin/env python3
"""aos-agent tools wrap-cli 產的 run：stdin 讀 arguments，照 wrapcli.json 的參數表驗型別、組 argv，
不經 shell 跑指令（cwd＝工作根目錄、stdin 關），回 stdout。
退出碼非 0＝CommandFailed（附 stderr 尾巴）；逾時＝Timeout（砍整個行程群組）。"""
import sys
sys.dont_write_bytecode = True
import json  # noqa: E402
import os  # noqa: E402
import signal  # noqa: E402
import subprocess  # noqa: E402
import threading  # noqa: E402
from _common import HERE, fail, run, truncate_tail  # noqa: E402

KIND = {'string': 'a string', 'integer': 'an integer', 'number': 'a number', 'boolean': 'a boolean'}
KEEP = 200 * 1024        # stdout、stderr 各只留最後這麼多位元組
STDERR_TAIL = 2000       # 錯誤 JSON 附的 stderr 尾巴（字元）
MAX_LINES = 2000
MAX_COUNT = 50


def spec():
    with open(os.path.join(HERE, 'wrapcli.json'), encoding='utf-8') as f:
        return json.load(f)


def check(value, p, where):
    t = p['type']
    ok = {'string': lambda v: isinstance(v, str),
          'integer': lambda v: isinstance(v, int) and not isinstance(v, bool),
          'number': lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
          'boolean': lambda v: isinstance(v, bool)}[t](value)
    if not ok:
        fail('BadArguments', '%s must be %s' % (where, KIND[t]))
    if t == 'string' and '\0' in value:
        fail('BadArguments', '%s must not contain NUL' % where)
    if p.get('choices') and value not in p['choices']:
        fail('BadArguments', '%s must be one of %s' % (where, json.dumps(p['choices'], ensure_ascii=False)))
    return value


def text(v):
    return v if isinstance(v, str) else json.dumps(v)


def flag(p):
    longs = [f for f in p['flags'] if f.startswith('--')]
    return longs[0] if longs else p['flags'][0]


UNSAFE = 'value %r of argument "%s" starts with "-" and cannot be passed safely to this command (it would be read as a flag)'


def bind(p, value, mode):
    """帶值選項的一個值 → argv 片段。- 開頭的值：寫成 --opt=值 才不會被當成別的旗標，
    這要指令認得 = 寫法（argparse 的長旗標、help 寫了 --opt=）；做不到就 BadArguments。"""
    f = flag(p)
    if p.get('joiner') == '=':
        return [f + '=' + value]
    if value.startswith('-'):
        if f.startswith('--') and mode == 'argparse':
            return [f + '=' + value]
        fail('BadArguments', UNSAFE % (value, p['name']))
    return [f, value]


def build(info, args):
    """arguments → argv（不含指令本身）：開關、帶值選項照參數表順序，位置參數最後；
    位置參數有 - 開頭的值就先放一個 --；帶值選項的 - 開頭值見 bind()。"""
    known = {p['name'] for p in info['params']}
    extra = sorted(k for k in args if k not in known)
    if extra:
        fail('BadArguments', 'unknown argument(s): %s' % ', '.join(extra))
    argv, pos = [], []
    for p in info['params']:
        name = p['name']
        where = 'argument "%s"' % name
        value = args.get(name)
        if value is None:
            if p.get('required'):
                fail('BadArguments', 'missing required argument "%s"' % name)
            continue
        kind = p['kind']
        if kind == 'flag':
            if not isinstance(value, bool):
                fail('BadArguments', '%s must be a boolean' % where)
            if value:
                argv.append(flag(p))
            continue
        if kind == 'count':
            if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= MAX_COUNT:
                fail('BadArguments', '%s must be an integer 0..%d' % (where, MAX_COUNT))
            argv += [flag(p)] * value
            continue
        if p.get('array'):
            if not isinstance(value, list):
                fail('BadArguments', '%s must be an array' % where)
            values = [text(check(v, p, '%s[%d]' % (where, i))) for i, v in enumerate(value)]
            n = p.get('nargs')
            if isinstance(n, int) and len(values) != n:
                fail('BadArguments', '%s must have exactly %d items' % (where, n))
            if n == '+' and not values:
                fail('BadArguments', '%s must have at least 1 item' % where)
        else:
            values = [text(check(value, p, where))]
        if kind == 'positional':
            pos += values
        elif p.get('array') and p.get('multi') == 'once':
            for v in values:                          # 一個旗標接好幾個值：- 開頭的沒有安全寫法
                if v.startswith('-'):
                    fail('BadArguments', UNSAFE % (v, name))
            if values:
                argv += [flag(p)] + values
        else:
            for v in values:
                argv += bind(p, v, info.get('mode'))
    if any(v.startswith('-') for v in pos):
        argv.append('--')
    return argv + pos


class Tail:
    def __init__(self):
        self.buf, self.total = bytearray(), 0

    def drain(self, stream):
        try:
            for chunk in iter(lambda: stream.read1(65536), b''):
                self.total += len(chunk)
                self.buf += chunk
                if len(self.buf) > 2 * KEEP:
                    del self.buf[:-KEEP]
        except (OSError, ValueError):
            pass

    def text(self):
        return bytes(self.buf[-KEEP:]).decode('utf-8', 'replace')


def killpg(pid):
    try:
        os.killpg(pid, signal.SIGKILL)
    except OSError:
        pass


def main(args, root):
    info = spec()
    argv = [os.path.join(HERE, a[1:]) if a.startswith('@') else a for a in info['exec']] + build(info, args)
    try:
        p = subprocess.Popen(argv, cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, start_new_session=True)
    except OSError as e:
        fail('SpawnFailed', 'cannot start %s: %s' % (argv[0], e.strerror or e))
    signal.signal(signal.SIGTERM, lambda *_: (killpg(p.pid), os._exit(143)))
    out, err = Tail(), Tail()
    readers = [threading.Thread(target=t.drain, args=(s,), daemon=True) for t, s in ((out, p.stdout), (err, p.stderr))]
    for r in readers:
        r.start()
    limit = info.get('timeout', 50)
    timed_out = False
    try:
        code = p.wait(timeout=limit)
    except subprocess.TimeoutExpired:
        timed_out = True
        killpg(p.pid)
        code = p.wait()
    killpg(p.pid)                                         # 背景孩子一起收
    for r in readers:
        r.join(timeout=2)
    shown, cut = truncate_tail(out.text(), MAX_LINES)
    if cut or out.total > len(shown.encode('utf-8')):
        shown = '[output truncated: %d bytes total, showing only the end]\n' % out.total + shown
    tail = err.text()[-STDERR_TAIL:]
    if timed_out:
        fail('Timeout', 'command timed out after %d s and was killed' % limit, output=shown, timeout=limit,
             stderr=tail)
    if code != 0:
        fail('CommandFailed', 'command exited with code %d' % code, output=shown, exit_code=code, stderr=tail)
    if shown.strip():
        return shown
    return '(no output on stdout; stderr:)\n' + tail if tail.strip() else '(no output)'


if __name__ == '__main__':
    sys.exit(run(main))
'''


def _param_desc(p):
    where = ', '.join(p['flags']) if p['flags'] else '(positional)'
    text = '%s: %s' % (where, p['help']) if p.get('help') else where
    return text[:160]


def tool_entry(pack, spec):
    props, required = {}, []
    for p in spec['params']:
        if p['kind'] == 'flag':
            prop = {'type': 'boolean'}
        elif p['kind'] == 'count':
            prop = {'type': 'integer', 'minimum': 0}
        else:
            base = {'type': p['type']}
            if p.get('choices'):
                base['enum'] = list(p['choices'])
            prop = {'type': 'array', 'items': base} if p.get('array') else base
            if isinstance(p.get('nargs'), int):
                prop.update(minItems=p['nargs'], maxItems=p['nargs'])
            elif p.get('nargs') == '+':
                prop['minItems'] = 1
        prop['description'] = _param_desc(p)
        props[p['name']] = prop
        if p.get('required'):
            required.append(p['name'])
    params = {'type': 'object', 'properties': props}
    if required:
        params['required'] = required
    desc = (spec.get('description') or 'Run a command-line program.').rstrip()
    shown = os.path.basename(spec['command'])
    desc = '%s (runs `%s`; returns its stdout)' % (desc, shown)
    return {'type': 'function',
            'function': {'name': pack.replace('-', '_'), 'description': desc, 'parameters': params},
            '_meta': {'argv': ['tools/%s/run' % pack]}}


def _exec(info):
    if info['kind'] == 'path':
        return [info['name']]
    rel = '@src/' + info['path'].name
    return ['python3', rel] if info['py'] else [rel]


def _readme(pack, spec, path):
    lines = ['# %s — 從指令 `%s` 包出來的工具' % (pack, spec['command']), '',
             '`aos-agent tools wrap-cli` 產的（參數表來源：%s）。參數表在 `wrapcli.json`；'
             '要改參數表就改那個檔，再 `aos-agent tools wrap-cli %s --spec %s/wrapcli.json --force`。'
             % ({'mechanical': '機械解析', 'llm': '模型提案、人看過', 'spec': '人給的參數表'}.get(
                 spec['made_by'], spec['made_by']), spec['command'], path), '',
             '| 參數 | 旗標 | 型別 | 必填 | 說明 |', '|---|---|---|---|---|']
    for p in spec['params']:
        t = p['type'] + ('[]' if p.get('array') else '')
        if p.get('choices'):
            t += ' ∈ ' + '/'.join(map(str, p['choices']))
        lines.append('| `%s` | %s | %s | %s | %s |' % (p['name'], ', '.join(p['flags']) or '（位置）', t,
                                                        '是' if p.get('required') else '', p.get('help', '').replace('|', '\\|')))
    lines += ['', '## 怎麼跑', '',
              '`run`：stdin 讀 arguments JSON，照參數表驗型別（多給、少給必填、型別或 choices 不對＝`BadArguments`），'
              '組成 argv **不經 shell** 跑指令：開關給 true 才加、count 重複 N 次、帶值選項照參數表順序、位置參數最後'
              '（有 `-` 開頭的值先放 `--`）。cwd＝工作根目錄、stdin 關。回 stdout；退出碼非 0＝`CommandFailed`'
              '（stdout 原樣在前、JSON 帶 `exit_code` 與 `stderr` 尾巴）；%d 秒沒跑完＝`Timeout`（砍整個行程群組）。'
              % spec.get('timeout', RUN_TIMEOUT), '',
              '## 關牢', '',
              '工具檔沒寫 `_jail`＝預設關牢。指令在牢裡要找得到：PATH 上的指令來自主機唯讀掛進去的 `/usr`；'
              '檔案指令的副本在 `src/`（牢裡的 `/opt/tool/src/`）。指令碰得到的檔只有 `access.json` 掛進 `/work` 的資料夾。', '',
              '## 試、裝', '', '```sh', 'aos-agent tools test %s' % path, 'aos-agent tools add %s --target 家' % path,
              '```', '']
    return '\n'.join(lines)


def _pack_files(pack, spec, info, path):
    tools = [tool_entry(pack, spec)]
    files = [(pack + '.json', dev._dump(tools), False), ('run', WRAPCLI_RUN, True),
             ('wrapcli.json', dev._dump(spec), False), ('_common.py', dev.BASE_COMMON.read_bytes(), False),
             ('config.json', dev._dump({'root': 'workspace'}), False), ('README.md', _readme(pack, spec, path), False)]
    if info['kind'] == 'file':
        files.append(('src/' + info['path'].name, info['data'], not info['py']))
    return dev.package_files(pack, files)


# ------------------------------------------------------------------ 印表 ----

STATUS = {'ok': '收  ', 'reject': '拒收', 'skip': '不收'}


def _type_text(p):
    t = p['type'] + ('[]' if p.get('array') else '')
    if p['kind'] == 'count':
        t = 'count'
    if p.get('choices'):
        t += '∈{%s}' % ','.join(map(str, p['choices']))
    return t


def print_table(params, rows=None, unparsed=(), dropped=(), notes=()):
    """每個參數一行：收／拒收（原因）、從哪一行解出來。"""
    width = max([len(p['name']) for p in params] + [len(str(r[1])) for r in rows or []] + [6])
    for p in params:
        flags = ', '.join(p['flags']) or '（位置）'
        line = ('第 %d 行' % p['line']) if p.get('line') else ''
        print('收    %-*s  %-28s %-18s %s  %s' % (width, p['name'], flags, _type_text(p), '必填' if p.get('required')
                                                 else '選填', line))
    for status, label, why, line in rows or []:
        if status == 'ok':
            continue
        print('%s  %-*s  第 %s 行（%s）' % (STATUS[status], width, label, line, why))
    for label, why in dropped:
        print('丟掉  %s（%s）' % (label, why))
    for line, text, why in unparsed:
        print('解不出來：第 %d 行：%s（%s）' % (line, text[:80], why))
    for line, why in notes:
        print('附註：第 %d 行：%s' % (line, why))


# ------------------------------------------------------------------ 主流程 ----

def _evidence(info, help_file, spec_data=None):
    """回 (mode, 原文, help_file 絕對路徑或 None)。--help-file 優先；--spec 記了 help_file 就用它；
    .py 有 argparse＝argparse；其他跑 CMD --help。"""
    if help_file is None and spec_data and spec_data.get('mode') == 'help' and spec_data.get('help_file'):
        help_file = spec_data['help_file']
    if help_file is not None:
        text, path = read_help_file(help_file)
        return 'help', text, path
    if info['kind'] == 'file' and info['py']:
        try:
            source = info['data'].decode('utf-8')
        except UnicodeDecodeError:
            raise AgentError('ReadFailed', '%s 不是 UTF-8 文字檔' % info['path'])
        if uses_argparse(source):
            return 'argparse', source, None
    return 'help', run_help(info), None


def load_spec(path):
    p = Path(os.path.abspath(os.path.expanduser(path)))
    try:
        data = json.loads(p.read_text(encoding='utf-8'))
    except FileNotFoundError:
        raise AgentError('NotFound', '找不到 --spec %s' % p)
    except (OSError, ValueError, UnicodeError) as e:
        raise AgentError('SpecInvalid', '讀不了 --spec %s：%s' % (p, e))
    if not isinstance(data, dict) or data.get('_type') != SPEC_TYPE or data.get('_version') != 1:
        raise AgentError('SpecInvalid', '%s 不是 wrap-cli 參數表（要 _type %s、_version 1）' % (p, SPEC_TYPE))
    bad = spec_problems(data)
    if bad:
        raise AgentError('SpecInvalid', '%s 的頂層欄位不對：%s' % (p, '；'.join(bad)))
    return data, p


def spec_problems(data):
    """參數表頂層欄位一次驗完（審查 M9）：回問題清單，空＝沒問題。"""
    bad = []
    if not isinstance(data.get('command'), str) or not data['command']:
        bad.append('command 要是非空字串')
    if data.get('mode') not in ('help', 'argparse'):
        bad.append('mode 要是 help 或 argparse')
    if not isinstance(data.get('help_sha256'), str):
        bad.append('help_sha256 要是字串')
    if data.get('help_file') is not None and (not isinstance(data['help_file'], str) or not data['help_file']):
        bad.append('help_file 要是非空字串或 null')
    desc = data.get('description')
    if desc is not None and (not isinstance(desc, str) or len(desc) > 1000 or CONTROL.search(desc)):
        bad.append('description 要是字串或 null（≤ 1000 字、不含控制字元）')
    if not isinstance(data.get('params'), list):
        bad.append('params 要是陣列')
    t = data.get('timeout', RUN_TIMEOUT)
    if not isinstance(t, int) or isinstance(t, bool) or not 1 <= t <= MAX_TIMEOUT:
        bad.append('timeout 要是 1～%d 的整數（秒）' % MAX_TIMEOUT)
    return bad


def _same_cmd(a, b):
    norm = (lambda c: os.path.abspath(os.path.expanduser(c)) if '/' in c or c.endswith('.py') else c)
    return norm(a) == norm(b)


def wrap_cli(cmd, name=None, out=None, force=False, help_file=None, describe_with_llm=False, model=None,
             spec=None, ask=None):
    info = resolve_cmd(cmd)
    stem = info['path'].stem if info['kind'] == 'file' else info['name']
    pack = name if name is not None else dev._pack_name(stem)
    if not NAME.match(pack) or not dev.TOOL_NAME.match(pack.replace('-', '_')):
        raise AgentError('BadName', '工具包名字 %r 只能用英數、底線、連字號（不能以 . 或 - 開頭，≤ 64 字）' % pack)
    folder = dev._out_dir(out)
    dev.package_files(pack, [(pack + '.json', '', False)] + [(f, '', False) for f in FIXED])   # 先擋撞名
    command = str(info['path']) if info['kind'] == 'file' else info['name']
    spec_data = spec_path = None
    if spec is not None:
        spec_data, spec_path = load_spec(spec)
    mode, evidence, hf = _evidence(info, help_file, spec_data)
    sha = _sha(evidence)
    base = {'_type': SPEC_TYPE, '_version': 1, 'command': command, 'mode': mode, 'help_sha256': sha,
            'help_file': hf, 'generated': _now()}
    if spec_data is not None:
        if not _same_cmd(spec_data.get('command', ''), command):
            raise AgentError('SpecMismatch', '參數表是給 %s 的，不是 %s' % (spec_data.get('command'), command))
        if spec_data['mode'] != mode:
            raise AgentError('SpecMismatch', '參數表的來源是 %s，這次讀到的是 %s' % (spec_data['mode'], mode))
        if spec_data.get('help_sha256') != sha:
            raise AgentError('HelpChanged', '%s 跟參數表記的不一樣了（sha256 %s… ≠ %s…）；重新提案或重新機械解析'
                             % ('help 文字' if mode == 'help' else '原始碼', sha[:12], str(spec_data.get('help_sha256'))[:12]))
        params, dropped = check_params(spec_data['params'], evidence)
        if dropped:
            raise AgentError('SpecInvalid', '參數表有 %d 格沒過機械檢查：%s' % (
                len(dropped), '；'.join('%s：%s' % d for d in dropped)))
        if not params:
            raise AgentError('NothingToWrap', '參數表是空的')
        spec_out = dict(base, made_by='spec', from_spec=str(spec_path), description=spec_data.get('description'),
                        params=params, timeout=spec_data.get('timeout', RUN_TIMEOUT))
        print_table(params)
        return _publish(pack, folder, spec_out, info, force)
    if describe_with_llm:
        import aos_llm_ask
        target = folder / (pack + '.wrapcli.json')
        if os.path.lexists(target) and not force:          # 問模型之前先擋，免得白花一次
            raise AgentError('AlreadyExists', '%s 已經在了（要蓋掉加 --force）' % target)
        desc, params, dropped, got = llm_table(os.path.basename(command), mode,
                                               argparse_segment(evidence) if mode == 'argparse' else evidence,
                                               alias=model, ask=ask)
        # argparse 模式：旗標逐字檢查拿整份原始碼（段落是它的子集，結果一樣）
        proposal = dict(base, made_by='llm', model=got.get('model'), alias=got.get('alias'), usage=got.get('usage'),
                        ms=got.get('ms'),
                        description=desc, params=params, dropped=[{'item': a, 'reason': b} for a, b in dropped],
                        timeout=RUN_TIMEOUT)
        print_table(params, dropped=dropped)
        print(aos_llm_ask.usage_line(got), file=sys.stderr)
        dev.write_json_file(target, proposal, force)
        print('提案寫在 %s（%d 格收、%d 格丟掉；還沒產包）' % (target, len(params), len(dropped)))
        print('看過沒問題（可以先改提案檔；這一步不叫模型）：aos-agent tools wrap-cli %s --spec %s --name %s%s' % (
            shlex.quote(cmd), shlex.quote(dev._shown(target)), shlex.quote(pack),
            ' --out %s' % shlex.quote(out) if out else ''))
        return 0
    parsed = read_argparse(evidence, command) if mode == 'argparse' else parse_help(evidence)
    params, dropped = check_params(parsed['params'], evidence)   # 機械版照理全過；沒過的也列出來
    desc = parsed['description']
    print_table(params, parsed['rows'], parsed['unparsed'], dropped, parsed['notes'])
    if not params:
        raise AgentError('NothingToWrap', '%s 沒解出任何參數（看上面的表）；要包就自己寫一份參數表給 --spec' % command)
    spec_out = dict(base, made_by='mechanical', description=desc, params=params, timeout=RUN_TIMEOUT,
                    rejected=[{'item': r[1], 'line': r[3], 'reason': r[2]} for r in parsed['rows'] if r[0] != 'ok'],
                    unparsed=[{'line': u[0], 'text': u[1], 'reason': u[2]} for u in parsed['unparsed']])
    return _publish(pack, folder, spec_out, info, force)


def _publish(pack, folder, spec_out, info, force):
    spec_out['exec'] = _exec(info)
    dev._check_dest(folder, pack, force)
    path = dev._shown(folder / pack)
    files = _pack_files(pack, spec_out, info, path)
    dest = dev.publish(folder, pack, files, force)
    print('生了 %s/：1 支工具 %s（%d 個參數）' % (dest, pack.replace('-', '_'), len(spec_out['params'])))
    print('下一步：aos-agent tools test %s' % path)
    print('裝進家：aos-agent tools add %s --target 家' % path)
    return 0


# ------------------------------------------------------------------ 對照用：跟標準答案比 ----

def score(params, answer):
    """參數表 vs 標準答案（fixtures/wrapcli/answers.json 的一份）→ 找對、多抓、少抓、型別對、必填對、choices 對。
    選項用旗標有交集配對，位置參數用順序配對。"""
    pred_pos = [p for p in params if p['kind'] == 'positional']
    pred_opt = [p for p in params if p['kind'] != 'positional']
    ans_pos = [a for a in answer if not a['flags']]
    ans_opt = [a for a in answer if a['flags']]
    pairs = list(zip(pred_pos, ans_pos))
    used = set()
    for a in ans_opt:
        for i, p in enumerate(pred_opt):
            if i not in used and set(p['flags']) & set(a['flags']):
                used.add(i)
                pairs.append((p, a))
                break
    total_pred = len(params)

    def ptype(p):
        return ('integer' if p['kind'] == 'count' else p['type'], bool(p.get('array')))

    def same_choices(p, a):
        return sorted(map(str, p.get('choices') or [])) == sorted(map(str, a.get('choices') or []))

    return {'answer': len(answer), 'found': len(pairs), 'extra': total_pred - len(pairs),
            'missed': len(answer) - len(pairs),
            'type_ok': sum(ptype(p) == (a['type'], a['array']) for p, a in pairs),
            'required_ok': sum(bool(p.get('required')) == a['required'] for p, a in pairs),
            'choices_ok': sum(same_choices(p, a) for p, a in pairs)}
